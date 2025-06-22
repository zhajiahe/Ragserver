"""Database connection management using asyncpg."""

import asyncpg
import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional

from ragbackend.config import DATABASE_URL

logger = logging.getLogger(__name__)


class DatabaseManager:
    """Database connection manager using dependency injection pattern."""
    
    def __init__(self):
        self._pool: Optional[asyncpg.Pool] = None
    
    async def init_pool(self) -> asyncpg.Pool:
        """Initialize database connection pool."""
        try:
            # 定义连接初始化函数
            async def init_connection(conn):
                await conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
                # 注册vector类型编解码器
                await conn.set_type_codec(
                    'vector',
                    encoder=lambda v: '[' + ','.join(map(str, v)) + ']',
                    decoder=lambda s: [float(x) for x in s.strip('[]').split(',')]
                )
            
            # 使用init参数创建连接池
            self._pool = await asyncpg.create_pool(
                DATABASE_URL,
                min_size=5,
                max_size=20,
                command_timeout=60,
                init=init_connection  # 正确的方式传递初始化函数
            )
            
            logger.info("Database connection pool initialized successfully")
            logger.info("pgvector类型已注册到所有连接")
            return self._pool
        except Exception as e:
            logger.error(f"Failed to initialize database pool: {e}")
            raise
    
    async def close_pool(self):
        """Close database connection pool."""
        if self._pool:
            await self._pool.close()
            logger.info("Database connection pool closed")
    
    def get_pool(self) -> asyncpg.Pool:
        """Get the database connection pool."""
        if self._pool is None:
            raise RuntimeError("Database pool not initialized. Call init_pool() first.")
        return self._pool
    
    @asynccontextmanager
    async def get_connection(self) -> AsyncGenerator[asyncpg.Connection, None]:
        """Get a database connection from the pool."""
        pool = self.get_pool()
        async with pool.acquire() as connection:
            try:
                yield connection
            except Exception as e:
                logger.error(f"Database operation error: {e}")
                raise


# Global database manager instance
db_manager = DatabaseManager()


# Legacy functions for backward compatibility
async def init_db_pool() -> asyncpg.Pool:
    """Initialize database connection pool."""
    return await db_manager.init_pool()


async def close_db_pool():
    """Close database connection pool."""
    await db_manager.close_pool()


def get_db_pool() -> asyncpg.Pool:
    """Get the database connection pool."""
    return db_manager.get_pool()


@asynccontextmanager
async def get_db_connection() -> AsyncGenerator[asyncpg.Connection, None]:
    """Get a database connection from the pool."""
    async with db_manager.get_connection() as conn:
        yield conn


async def execute_query(query: str, *args) -> None:
    """Execute a query without returning results."""
    async with get_db_connection() as conn:
        await conn.execute(query, *args)


async def fetch_one(query: str, *args) -> asyncpg.Record:
    """Fetch one row from query."""
    async with get_db_connection() as conn:
        return await conn.fetchrow(query, *args)


async def fetch_all(query: str, *args) -> list[asyncpg.Record]:
    """Fetch all rows from query."""
    async with get_db_connection() as conn:
        return await conn.fetch(query, *args)


async def init_database_tables():
    """Initialize database tables and extensions."""
    async with get_db_connection() as conn:
        try:
            # Enable pgvector extension
            await conn.execute("CREATE EXTENSION IF NOT EXISTS vector;")
            logger.info("pgvector extension enabled")
            
            # Create collections table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS collections (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    name VARCHAR(255) NOT NULL,
                    description TEXT,
                    embedding_model VARCHAR(100) NOT NULL DEFAULT 'bge-m3',
                    embedding_provider VARCHAR(100) NOT NULL DEFAULT 'ollama',
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                );
            """)
            logger.info("Collections table created")
            
            # Add embedding_provider column if it doesn't exist (for existing tables)
            try:
                await conn.execute("""
                    ALTER TABLE collections 
                    ADD COLUMN IF NOT EXISTS embedding_provider VARCHAR(100) NOT NULL DEFAULT 'ollama';
                """)
                logger.info("embedding_provider column added to collections table")
            except Exception as e:
                logger.warning(f"Failed to add embedding_provider column (may already exist): {e}")
            
            # Create files table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS files (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    collection_id UUID NOT NULL REFERENCES collections(id) ON DELETE CASCADE,
                    filename VARCHAR(255) NOT NULL,
                    content_type VARCHAR(100),
                    size BIGINT NOT NULL,
                    object_path TEXT NOT NULL,
                    status VARCHAR(20) DEFAULT 'processing' CHECK (status IN ('processing', 'completed', 'failed')),
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                );
            """)
            logger.info("Files table created")
            
            # Create indexes for better performance
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_files_collection_id ON files(collection_id);")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_files_status ON files(status);")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_collections_name ON collections(name);")
            
            logger.info("Database tables initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize database tables: {e}")
            raise
