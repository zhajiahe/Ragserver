# conftest.py

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from ragserver.app.models import Base
from ragserver.config import settings
from ragserver.main import app

TEST_DATABASE_URL = settings.async_database_url

# 全局 engine 缓存（用于 class-scoped fixture）
_test_engine_cache = None


# Function-scoped fixture: 为每个测试创建独立的 engine 和会话
@pytest.fixture(scope="function")
async def db_session():
    """创建测试数据库会话（每个测试使用独立的 engine）"""
    # 为每个测试创建独立的 engine
    test_engine = create_async_engine(
        TEST_DATABASE_URL,
        echo=False,  # 减少日志输出
        poolclass=StaticPool,  # 使用单连接池避免并发问题
    )

    # 每个测试前重建表
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

        # 创建 BM25 索引（如果 ParadeDB 可用）
        try:
            # 检查 ParadeDB 扩展是否可用
            result = await conn.execute(
                text("""
                SELECT 1 FROM pg_extension WHERE extname = 'pg_search'
            """)
            )
            if result.scalar():
                # 创建 BM25 索引
                await conn.execute(
                    text("""
                    CREATE INDEX IF NOT EXISTS document_chunks_bm25_idx 
                    ON document_chunks 
                    USING bm25 (id, content)
                    WITH (key_field='id')
                """)
                )
        except Exception:
            # ParadeDB 不可用，跳过
            pass

    # 创建会话工厂
    AsyncSessionLocal = async_sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    # 创建会话
    async with AsyncSessionLocal() as session:
        yield session

    # 清理
    await test_engine.dispose()


@pytest.fixture(scope="function")
async def async_client():
    """创建异步HTTP客户端"""
    from httpx import ASGITransport

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client


# ==================== Class-scoped Fixtures（性能优化）====================


@pytest.fixture(scope="class")
async def db_engine_class():
    """类级别的数据库引擎（同一测试类共享）"""
    global _test_engine_cache

    if _test_engine_cache is None:
        _test_engine_cache = create_async_engine(
            TEST_DATABASE_URL,
            echo=False,
            poolclass=StaticPool,
        )

    # 在测试类开始时重建表
    async with _test_engine_cache.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

        # 创建 BM25 索引
        try:
            result = await conn.execute(
                text("""
                SELECT 1 FROM pg_extension WHERE extname = 'pg_search'
            """)
            )
            if result.scalar():
                await conn.execute(
                    text("""
                    CREATE INDEX IF NOT EXISTS document_chunks_bm25_idx 
                    ON document_chunks 
                    USING bm25 (id, content)
                    WITH (key_field='id')
                """)
                )
        except Exception:
            pass

    yield _test_engine_cache

    # 注意：不在这里 dispose，因为可能有其他测试类还在使用


@pytest.fixture(scope="function")
async def db_session_class(db_engine_class: AsyncEngine):
    """类级别的数据库会话（每个测试使用独立会话，但共享表结构）

    性能优化版本：
    - 同一测试类的所有测试共享数据库表结构
    - 每个测试后清理数据（TRUNCATE）而不是删除表
    - 大幅减少表重建时间
    """
    AsyncSessionLocal = async_sessionmaker(
        bind=db_engine_class,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with AsyncSessionLocal() as session:
        yield session

        # 测试后清理所有表的数据（保留表结构）
        try:
            # 按依赖顺序清理表
            await session.execute(text("TRUNCATE TABLE document_chunks CASCADE"))
            await session.execute(text("TRUNCATE TABLE documents CASCADE"))
            await session.execute(text("TRUNCATE TABLE collection_shares CASCADE"))
            await session.execute(text("TRUNCATE TABLE collections CASCADE"))
            await session.execute(text("TRUNCATE TABLE users CASCADE"))
            await session.commit()
        except Exception:
            await session.rollback()
