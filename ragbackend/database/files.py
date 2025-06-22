"""Files database operations."""

import asyncpg
import logging
from typing import List, Optional, Dict, Any
from uuid import UUID

from ragbackend.database.connection import get_db_connection
from ragbackend.utils.validators import validate_uuid

logger = logging.getLogger(__name__)


async def create_file(
    collection_id: str,
    filename: str,
    content_type: str,
    size: int,
    object_path: str
) -> Dict[str, Any]:
    """Create a new file record."""
    # Validate UUID format
    uuid_obj = validate_uuid(collection_id)
    
    async with get_db_connection() as conn:
        row = await conn.fetchrow("""
            INSERT INTO files (collection_id, filename, content_type, size, object_path)
            VALUES ($1, $2, $3, $4, $5)
            RETURNING id, collection_id, filename, content_type, size, object_path, status, created_at, updated_at
        """, uuid_obj, filename, content_type, size, object_path)
        
        return {
            'id': str(row['id']),
            'collection_id': str(row['collection_id']),
            'filename': row['filename'],
            'content_type': row['content_type'],
            'size': row['size'],
            'object_path': row['object_path'],
            'status': row['status'],
            'created_at': row['created_at'].isoformat(),
            'updated_at': row['updated_at'].isoformat()
        }


async def get_file_by_id(file_id: str) -> Optional[Dict[str, Any]]:
    """Get file by ID."""
    # Validate UUID format
    uuid_obj = validate_uuid(file_id)
    
    async with get_db_connection() as conn:
        row = await conn.fetchrow("""
            SELECT id, collection_id, filename, content_type, size, object_path, status, created_at, updated_at
            FROM files
            WHERE id = $1
        """, uuid_obj)
        
        if not row:
            return None
            
        return {
            'id': str(row['id']),
            'collection_id': str(row['collection_id']),
            'filename': row['filename'],
            'content_type': row['content_type'],
            'size': row['size'],
            'object_path': row['object_path'],
            'status': row['status'],
            'created_at': row['created_at'].isoformat(),
            'updated_at': row['updated_at'].isoformat()
        }


async def get_files_by_collection(collection_id: str) -> List[Dict[str, Any]]:
    """Get all files in a collection."""
    # Validate UUID format
    uuid_obj = validate_uuid(collection_id)
    
    async with get_db_connection() as conn:
        rows = await conn.fetch("""
            SELECT id, collection_id, filename, content_type, size, object_path, status, created_at, updated_at
            FROM files
            WHERE collection_id = $1
            ORDER BY created_at DESC
        """, uuid_obj)
        
        return [
            {
                'id': str(row['id']),
                'collection_id': str(row['collection_id']),
                'filename': row['filename'],
                'content_type': row['content_type'],
                'size': row['size'],
                'object_path': row['object_path'],
                'status': row['status'],
                'created_at': row['created_at'].isoformat(),
                'updated_at': row['updated_at'].isoformat()
            }
            for row in rows
        ]


async def update_file_status(file_id: str, status: str) -> Optional[Dict[str, Any]]:
    """Update file status."""
    # Validate UUID format
    uuid_obj = validate_uuid(file_id)
    
    async with get_db_connection() as conn:
        row = await conn.fetchrow("""
            UPDATE files 
            SET status = $1, updated_at = NOW()
            WHERE id = $2
            RETURNING id, collection_id, filename, content_type, size, object_path, status, created_at, updated_at
        """, status, uuid_obj)
        
        if not row:
            return None
            
        return {
            'id': str(row['id']),
            'collection_id': str(row['collection_id']),
            'filename': row['filename'],
            'content_type': row['content_type'],
            'size': row['size'],
            'object_path': row['object_path'],
            'status': row['status'],
            'created_at': row['created_at'].isoformat(),
            'updated_at': row['updated_at'].isoformat()
        }


async def delete_file(file_id: str) -> bool:
    """Delete file record."""
    # Validate UUID format
    uuid_obj = validate_uuid(file_id)
    
    async with get_db_connection() as conn:
        result = await conn.execute("""
            DELETE FROM files WHERE id = $1
        """, uuid_obj)
        
        deleted_count = int(result.split()[-1])
        return deleted_count > 0


async def get_files_by_status(status: str) -> List[Dict[str, Any]]:
    """Get files by status."""
    async with get_db_connection() as conn:
        rows = await conn.fetch("""
            SELECT id, collection_id, filename, content_type, size, object_path, status, created_at, updated_at
            FROM files
            WHERE status = $1
            ORDER BY created_at ASC
        """, status)
        
        return [
            {
                'id': str(row['id']),
                'collection_id': str(row['collection_id']),
                'filename': row['filename'],
                'content_type': row['content_type'],
                'size': row['size'],
                'object_path': row['object_path'],
                'status': row['status'],
                'created_at': row['created_at'].isoformat(),
                'updated_at': row['updated_at'].isoformat()
            }
            for row in rows
        ]
