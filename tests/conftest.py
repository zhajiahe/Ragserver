# conftest.py
import pytest
import asyncio
from fastapi.testclient import TestClient
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy import text
from ragserver.main import app
from ragserver.app.models import Base
from ragserver.app.dependencies import get_db
from ragserver.config import settings

TEST_DATABASE_URL = settings.async_database_url

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
            result = await conn.execute(text("""
                SELECT 1 FROM pg_extension WHERE extname = 'pg_search'
            """))
            if result.scalar():
                # 创建 BM25 索引
                await conn.execute(text("""
                    CREATE INDEX IF NOT EXISTS document_chunks_bm25_idx 
                    ON document_chunks 
                    USING bm25 (id, content)
                    WITH (key_field='id')
                """))
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
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as client:
        yield client