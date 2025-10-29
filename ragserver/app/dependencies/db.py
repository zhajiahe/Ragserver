"""
数据库引擎与会话管理（异步）

提供全局异步引擎与 SessionFactory，供 FastAPI 依赖注入使用。
"""
from __future__ import annotations

from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from ragserver.config import settings


def _create_async_engine() -> AsyncEngine:
    return create_async_engine(
        settings.async_database_url,
        echo=settings.db_echo,
        pool_pre_ping=True,
        pool_recycle=settings.db_pool_recycle,
        pool_timeout=settings.db_pool_timeout,
        # 注意：pool_size/max_overflow 仅在使用 QueuePool 时有效；asyncpg 默认支持
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
    )


async_engine: AsyncEngine = _create_async_engine()

async_session_factory = sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)



async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        yield session


