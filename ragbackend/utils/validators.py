"""Validation utilities for RagBackend."""

import re
from uuid import UUID
from typing import Optional
from fastapi import HTTPException


def validate_uuid(uuid_string: str) -> UUID:
    """
    Validate and convert string to UUID.
    
    Args:
        uuid_string: String representation of UUID
        
    Returns:
        UUID object
        
    Raises:
        HTTPException: If UUID format is invalid
    """
    try:
        return UUID(uuid_string)
    except ValueError:
        raise HTTPException(
            status_code=400, 
            detail=f"Invalid UUID format: {uuid_string}"
        )


def validate_and_sanitize_table_name(collection_id: str) -> str:
    """
    Validate collection ID and generate safe table name.
    
    Args:
        collection_id: Collection UUID string
        
    Returns:
        Safe table name
        
    Raises:
        HTTPException: If collection ID is invalid
    """
    try:
        # Validate UUID format
        uuid_obj = validate_uuid(collection_id)
        
        # Generate safe table name
        table_name = f"collection_{str(uuid_obj).replace('-', '_')}_vectors"
        
        # Validate table name format (extra safety check)
        if not re.match(r'^collection_[a-f0-9_]+_vectors$', table_name):
            raise ValueError("Invalid table name format")
            
        return table_name
    except ValueError as e:
        raise HTTPException(
            status_code=400, 
            detail=f"Invalid collection ID format: {str(e)}"
        )


def validate_collection_name(name: str) -> str:
    """
    Validate collection name format.
    
    Args:
        name: Collection name
        
    Returns:
        Validated name
        
    Raises:
        HTTPException: If name format is invalid
    """
    if not name or len(name.strip()) == 0:
        raise HTTPException(status_code=400, detail="Collection name cannot be empty")
    
    name = name.strip()
    
    if len(name) > 255:
        raise HTTPException(status_code=400, detail="Collection name too long (max 255 characters)")
    
    # Allow alphanumeric, spaces, hyphens, underscores, Chinese characters
    if not re.match(r'^[a-zA-Z0-9_\-\s\u4e00-\u9fff]+$', name):
        raise HTTPException(
            status_code=400, 
            detail="Collection name contains invalid characters"
        )
    
    return name


def validate_file_size(size: int, max_size: Optional[int] = None) -> int:
    """
    Validate file size.
    
    Args:
        size: File size in bytes
        max_size: Maximum allowed size (default: 100MB)
        
    Returns:
        Validated size
        
    Raises:
        HTTPException: If file size is invalid
    """
    if max_size is None:
        max_size = 100 * 1024 * 1024  # 100MB
    
    if size < 0:
        raise HTTPException(status_code=400, detail="File size cannot be negative")
    
    if size > max_size:
        raise HTTPException(
            status_code=400, 
            detail=f"File size exceeds limit ({max_size / 1024 / 1024:.1f}MB)"
        )
    
    return size
