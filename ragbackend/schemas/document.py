from typing import Any, Union
from uuid import UUID

from pydantic import BaseModel, field_validator


class DocumentCreate(BaseModel):
    content: str | None = None
    metadata: dict[str, Any] | None = None


class DocumentUpdate(BaseModel):
    content: str | None = None
    metadata: dict[str, Any] | None = None


class DocumentResponse(BaseModel):
    id: Union[str, UUID]
    collection_id: Union[str, UUID]
    content: str | None = None
    metadata: dict[str, Any] | None = None
    created_at: str | None = None
    updated_at: str | None = None

    @field_validator('id', 'collection_id')
    @classmethod
    def validate_uuid_fields(cls, v):
        """Convert UUID to string if needed."""
        if isinstance(v, UUID):
            return str(v)
        return v


class SearchQuery(BaseModel):
    query: str
    limit: int | None = 10
    filter: dict[str, Any] | None = None


class SearchResult(BaseModel):
    id: Union[str, UUID]
    page_content: str
    metadata: dict[str, Any] | None = None
    score: float

    @field_validator('id')
    @classmethod
    def validate_id(cls, v):
        """Convert UUID to string if needed."""
        if isinstance(v, UUID):
            return str(v)
        return v
