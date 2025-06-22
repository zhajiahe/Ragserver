"""Collection schemas for API."""

from typing import Optional
from pydantic import BaseModel, Field


class CollectionCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255, description="Collection name")
    description: Optional[str] = Field(None, description="Collection description")
    embedding_model: str = Field("ollama", description="Embedding model to use")


class CollectionUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255, description="Collection name")
    description: Optional[str] = Field(None, description="Collection description")


class CollectionResponse(BaseModel):
    id: str
    name: str
    description: Optional[str]
    embedding_model: str
    created_at: str
    updated_at: str


class CollectionListResponse(BaseModel):
    collections: list[CollectionResponse]
    total: int
