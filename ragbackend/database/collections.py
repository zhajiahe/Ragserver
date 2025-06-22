"""Collections database operations."""

import asyncpg
import logging
from typing import List, Optional, Dict, Any
from uuid import UUID
from datetime import datetime

from ragbackend.database.connection import get_db_connection

logger = logging.getLogger(__name__)


async def create_collection(
    name: str, 
    description: Optional[str] = None,
    embedding_model: str = "bge-m3",
    embedding_provider: str = "ollama"
) -> Dict[str, Any]:
    """Create a new collection."""
    async with get_db_connection() as conn:
        # Insert collection
        row = await conn.fetchrow("""
            INSERT INTO collections (name, description, embedding_model, embedding_provider)
            VALUES ($1, $2, $3, $4)
            RETURNING id, name, description, embedding_model, embedding_provider, created_at, updated_at
        """, name, description, embedding_model, embedding_provider)
        
        collection_id = row['id']
        
        # Create vector table for this collection
        vector_table_name = f"collection_{str(collection_id).replace('-', '_')}_vectors"
        await conn.execute(f"""
            CREATE TABLE {vector_table_name} (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                file_id UUID NOT NULL REFERENCES files(id) ON DELETE CASCADE,
                content TEXT NOT NULL,
                metadata JSONB,
                embedding vector(1024),
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            );
        """)
        
        # Create index for vector similarity search
        await conn.execute(f"""
            CREATE INDEX ON {vector_table_name} 
            USING ivfflat (embedding vector_cosine_ops)
            WITH (lists = 100);
        """)
        
        logger.info(f"Created collection {collection_id} with vector table {vector_table_name}")
        
        return {
            'id': str(row['id']),
            'name': row['name'],
            'description': row['description'],
            'embedding_model': row['embedding_model'],
            'created_at': row['created_at'].isoformat(),
            'updated_at': row['updated_at'].isoformat()
        }


async def get_collection_by_id(collection_id: str) -> Optional[Dict[str, Any]]:
    """Get collection by ID."""
    async with get_db_connection() as conn:
        row = await conn.fetchrow("""
            SELECT id, name, description, embedding_model, created_at, updated_at
            FROM collections
            WHERE id = $1
        """, UUID(collection_id))
        
        if not row:
            return None
            
        return {
            'id': str(row['id']),
            'name': row['name'],
            'description': row['description'],
            'embedding_model': row['embedding_model'],
            'created_at': row['created_at'].isoformat(),
            'updated_at': row['updated_at'].isoformat()
        }


async def get_all_collections() -> List[Dict[str, Any]]:
    """Get all collections."""
    async with get_db_connection() as conn:
        rows = await conn.fetch("""
            SELECT id, name, description, embedding_model, created_at, updated_at
            FROM collections
            ORDER BY created_at DESC
        """)
        
        return [
            {
                'id': str(row['id']),
                'name': row['name'],
                'description': row['description'],
                'embedding_model': row['embedding_model'],
                'created_at': row['created_at'].isoformat(),
                'updated_at': row['updated_at'].isoformat()
            }
            for row in rows
        ]


async def update_collection(
    collection_id: str,
    name: Optional[str] = None,
    description: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """Update collection."""
    updates = []
    values = []
    param_count = 1
    
    if name is not None:
        updates.append(f"name = ${param_count}")
        values.append(name)
        param_count += 1
        
    if description is not None:
        updates.append(f"description = ${param_count}")
        values.append(description)
        param_count += 1
    
    if not updates:
        return await get_collection_by_id(collection_id)
    
    updates.append(f"updated_at = NOW()")
    values.append(UUID(collection_id))
    
    query = f"""
        UPDATE collections 
        SET {', '.join(updates)}
        WHERE id = ${param_count}
        RETURNING id, name, description, embedding_model, created_at, updated_at
    """
    
    async with get_db_connection() as conn:
        row = await conn.fetchrow(query, *values)
        
        if not row:
            return None
            
        return {
            'id': str(row['id']),
            'name': row['name'],
            'description': row['description'],
            'embedding_model': row['embedding_model'],
            'embedding_provider': row['embedding_provider'],
            'created_at': row['created_at'].isoformat(),
            'updated_at': row['updated_at'].isoformat()
        }


async def delete_collection(collection_id: str) -> bool:
    """Delete collection and its vector table."""
    async with get_db_connection() as conn:
        async with conn.transaction():
            # Check if collection exists
            collection = await conn.fetchrow("""
                SELECT id FROM collections WHERE id = $1
            """, UUID(collection_id))
            
            if not collection:
                return False
            
            # Drop vector table
            vector_table_name = f"collection_{str(collection['id']).replace('-', '_')}_vectors"
            try:
                await conn.execute(f"DROP TABLE IF EXISTS {vector_table_name} CASCADE;")
                logger.info(f"Dropped vector table {vector_table_name}")
            except Exception as e:
                logger.warning(f"Failed to drop vector table {vector_table_name}: {e}")
            
            # Delete collection (files will be deleted by CASCADE)
            result = await conn.execute("""
                DELETE FROM collections WHERE id = $1
            """, UUID(collection_id))
            
            deleted_count = int(result.split()[-1])
            return deleted_count > 0


async def get_vector_table_name(collection_id: str) -> str:
    """Get vector table name for collection."""
    return f"collection_{str(collection_id).replace('-', '_')}_vectors"
