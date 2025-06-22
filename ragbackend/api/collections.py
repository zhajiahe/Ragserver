"""Collections API routes."""

import logging
from typing import List, Optional

from fastapi import APIRouter, HTTPException, status, Response
from fastapi.responses import JSONResponse

from ragbackend.schemas.collections import (
    CollectionCreate,
    CollectionUpdate,
    CollectionResponse,
    CollectionListResponse
)
from ragbackend.database import collections as db_collections

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/collections", tags=["collections"])


@router.post("/", response_model=CollectionResponse, status_code=status.HTTP_201_CREATED)
async def create_collection(collection: CollectionCreate):
    """Create a new collection."""
    try:
        result = await db_collections.create_collection(
            name=collection.name,
            description=collection.description,
            embedding_model=collection.embedding_model,
            embedding_provider=collection.embedding_provider
        )
        return CollectionResponse(**result)
    except Exception as e:
        logger.error(f"Failed to create collection: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/", response_model=List[CollectionResponse])
async def get_collections():
    """Get all collections."""
    try:
        collections = await db_collections.get_all_collections()
        return [CollectionResponse(**collection) for collection in collections]
    except Exception as e:
        logger.error(f"Failed to get collections: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{collection_id}", response_model=CollectionResponse)
async def get_collection(collection_id: str):
    """Get collection by ID."""
    try:
        collection = await db_collections.get_collection_by_id(collection_id)
        if not collection:
            raise HTTPException(status_code=404, detail="Collection not found")
        return CollectionResponse(**collection)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get collection {collection_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{collection_id}", response_model=CollectionResponse)
async def update_collection(collection_id: str, collection: CollectionUpdate):
    """Update collection."""
    try:
        result = await db_collections.update_collection(
            collection_id=collection_id,
            name=collection.name,
            description=collection.description
        )
        if not result:
            raise HTTPException(status_code=404, detail="Collection not found")
        return CollectionResponse(**result)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update collection {collection_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{collection_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_collection(collection_id: str):
    """Delete collection."""
    try:
        deleted = await db_collections.delete_collection(collection_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Collection not found")
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete collection {collection_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
