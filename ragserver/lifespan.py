from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from loguru import logger
from sqlalchemy import text

from ragserver.app.dependencies.db import async_engine
from ragserver.app.models import Base
from ragserver.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    """应用生命周期管理"""
    # 启动时
    logger.info("🚀 应用启动中...")
    logger.info(f"📦 环境: {'开发' if settings.debug else '生产'}")
    logger.info(f"🗄️  数据库: {settings.postgres_host}:{settings.postgres_port}/{settings.postgres_db}")
    logger.info(f"🔑 Redis: {settings.redis_host}:{settings.redis_port}")
    logger.info(f"📦 MinIO: {settings.minio_host}:{settings.minio_port}")

    # 开发模式：自动创建数据库表
    if settings.debug:
        logger.info("🔧 开发模式：自动创建数据库扩展和表...")
        try:
            # 创建必要的 PostgreSQL 扩展和表
            async with async_engine.begin() as conn:
                # 创建 pgvector 扩展（必需）
                await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
                logger.info("  ✓ pgvector 扩展已启用")

                # 创建所有表
                await conn.run_sync(Base.metadata.create_all)
                logger.info("  ✓ 数据库表创建完成")

            # 尝试创建 ParadeDB 扩展（可选，单独事务）
            paradedb_available = False
            try:
                async with async_engine.begin() as conn:
                    # ParadeDB 由多个扩展组成：pg_search（全文搜索）和 pg_analytics（分析）
                    await conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_search"))
                    logger.info("  ✓ ParadeDB (pg_search) 扩展已启用")
                    paradedb_available = True
            except Exception:
                logger.info("  ℹ️  ParadeDB 扩展不可用（全文搜索将使用 LIKE 回退）")

            # 如果 ParadeDB 可用，创建 BM25 索引
            if paradedb_available:
                try:
                    async with async_engine.begin() as conn:
                        # 检查索引是否已存在
                        result = await conn.execute(
                            text("""
                            SELECT indexname FROM pg_indexes 
                            WHERE tablename = 'document_chunks' 
                            AND indexname = 'document_chunks_bm25_idx'
                        """)
                        )
                        if not result.scalar():
                            # 使用 CREATE INDEX 创建 BM25 索引（ParadeDB v0.18+ 方式）
                            await conn.execute(
                                text("""
                                CREATE INDEX document_chunks_bm25_idx 
                                ON document_chunks 
                                USING bm25 (id, content)
                                WITH (key_field='id')
                            """)
                            )
                            logger.info("  ✓ BM25 索引已创建")
                        else:
                            logger.info("  ✓ BM25 索引已存在")
                except Exception as e:
                    logger.warning(f"  ⚠️  BM25 索引创建失败: {str(e)[:100]}")
                    logger.warning("  提示：全文搜索仍可使用，但性能可能受影响")

        except Exception as e:
            logger.error(f"  ⚠️  数据库初始化失败: {e}")
            logger.error("  提示：请确保数据库已安装 pgvector 扩展")
            raise

    logger.info("✅ 应用启动完成！")

    yield

    # 关闭时
    logger.info("🛑 应用关闭中...")
    await async_engine.dispose()
    logger.info("✅ 应用已关闭")
