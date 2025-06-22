"""Database connection management using asyncpg."""

import asyncpg
import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from ragbackend.config import DATABASE_URL

logger = logging.getLogger(__name__)

# Global connection pool
_pool: asyncpg.Pool = None


async def init_db_pool() -> asyncpg.Pool:
    """Initialize database connection pool."""
    global _pool
    try:
        _pool = await asyncpg.create_pool(
            DATABASE_URL,
            min_size=5,
            max_size=20,
            command_timeout=60
        )
        logger.info("Database connection pool initialized successfully")
        return _pool
    except Exception as e:
        logger.error(f"Failed to initialize database pool: {e}")
        raise


async def close_db_pool():
    """Close database connection pool."""
    global _pool
    if _pool:
        await _pool.close()
        logger.info("Database connection pool closed")


def get_db_pool() -> asyncpg.Pool:
    """Get the database connection pool."""
    global _pool
    if _pool is None:
        raise RuntimeError("Database pool not initialized. Call init_db_pool() first.")
    return _pool


@asynccontextmanager
async def get_db_connection() -> AsyncGenerator[asyncpg.Connection, None]:
    """Get a database connection from the pool."""
    pool = get_db_pool()
    async with pool.acquire() as connection:
        try:
            yield connection
        except Exception as e:
            logger.error(f"Database operation error: {e}")
            raise


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
                    embedding_model VARCHAR(100) NOT NULL DEFAULT 'ollama',
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                );
            """)
            logger.info("Collections table created")
            
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
