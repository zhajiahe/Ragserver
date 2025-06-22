"""Collections API routes."""

import logging
from typing import List

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import JSONResponse

from ragbackend.schemas.collections import (
    CollectionCreate,
    CollectionUpdate,
    CollectionResponse,
    CollectionListResponse
)
from ragbackend.database import collections as db_collections

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("", response_model=CollectionResponse, status_code=status.HTTP_201_CREATED, tags=["collections"])
async def create_collection(collection_data: CollectionCreate):
    """Create a new collection."""
    try:
        collection = await db_collections.create_collection(
            name=collection_data.name,
            description=collection_data.description,
            embedding_model=collection_data.embedding_model
        )
        return CollectionResponse(**collection)
    except Exception as e:
        logger.error(f"Failed to create collection: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create collection"
        )


@router.get("", response_model=CollectionListResponse)
async def get_collections():
    """Get all collections."""
    try:
        collections = await db_collections.get_all_collections()
        return CollectionListResponse(
            collections=[CollectionResponse(**col) for col in collections],
            total=len(collections)
        )
    except Exception as e:
        logger.error(f"Failed to get collections: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get collections"
        )


@router.get("/{collection_id}", response_model=CollectionResponse, tags=["collections"])
async def get_collection(collection_id: str):
    """Get collection by ID."""
    try:
        collection = await db_collections.get_collection_by_id(collection_id)
        if not collection:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Collection not found"
            )
        return CollectionResponse(**collection)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get collection {collection_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get collection"
        )


@router.put("/{collection_id}", response_model=CollectionResponse)
async def update_collection(collection_id: str, collection_data: CollectionUpdate):
    """Update collection."""
    try:
        collection = await db_collections.update_collection(
            collection_id=collection_id,
            name=collection_data.name,
            description=collection_data.description
        )
        if not collection:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Collection not found"
            )
        return CollectionResponse(**collection)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update collection {collection_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update collection"
        )


@router.delete("/{collection_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["collections"])
async def delete_collection(collection_id: str):
    """Delete collection."""
    try:
        success = await db_collections.delete_collection(collection_id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Collection not found"
            )
        return JSONResponse(
            status_code=status.HTTP_204_NO_CONTENT,
            content=None
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete collection {collection_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete collection"
        )
