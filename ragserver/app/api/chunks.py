"""文档分块查询 API

提供文档分块的查询功能
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ragserver.app.dependencies import get_current_active_user, get_db
from ragserver.app.models import Collection, Document, DocumentChunk, User

router = APIRouter(prefix="/api/v1/chunks", tags=["文档分块"])


# ==================== Pydantic Schemas ====================


class ChunkResponse(BaseModel):
    """分块响应模型"""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    document_id: UUID
    collection_id: UUID
    content: str
    content_hash: str
    chunk_index: int
    embedding_model: str
    meta: dict
    created_at: str

    @classmethod
    def from_orm_with_similarity(cls, chunk: DocumentChunk, similarity: float | None = None):
        """从ORM对象创建响应，可选包含相似度"""
        data = {
            "id": chunk.id,
            "document_id": chunk.document_id,
            "collection_id": chunk.collection_id,
            "content": chunk.content,
            "content_hash": chunk.content_hash,
            "chunk_index": chunk.chunk_index,
            "embedding_model": chunk.embedding_model,
            "meta": chunk.meta or {},
            "created_at": chunk.created_at.isoformat(),
        }
        if similarity is not None:
            data["similarity"] = similarity
        return cls(**data)


class ChunkListResponse(BaseModel):
    """分块列表响应"""

    total: int
    items: list[ChunkResponse]


# ==================== Helper Functions ====================


async def verify_document_access(db: AsyncSession, document_id: UUID, user_id: UUID) -> Document:
    """验证文档访问权限"""
    query = select(Document).join(Collection).where(Document.id == document_id, Collection.user_id == user_id)
    result = await db.execute(query)
    document = result.scalar_one_or_none()

    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文档不存在或无权访问")

    return document


# ==================== API Endpoints ====================


@router.get("/document/{document_id}", response_model=ChunkListResponse)
async def get_document_chunks(
    document_id: UUID,
    limit: int = Query(20, ge=1, le=100, description="每页数量"),
    offset: int = Query(0, ge=0, description="偏移量"),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """获取文档的所有分块

    - 需要认证
    - 只能查询自己的文档
    - 支持分页
    - 按 chunk_index 排序
    """
    # 验证文档访问权限
    await verify_document_access(db, document_id, current_user.id)

    # 查询总数
    count_query = select(func.count()).select_from(DocumentChunk).where(DocumentChunk.document_id == document_id)
    total_result = await db.execute(count_query)
    total = total_result.scalar()

    # 查询分块列表
    query = (
        select(DocumentChunk)
        .where(DocumentChunk.document_id == document_id)
        .order_by(DocumentChunk.chunk_index)
        .limit(limit)
        .offset(offset)
    )
    result = await db.execute(query)
    chunks = result.scalars().all()

    # 转换为响应模型
    items = [
        ChunkResponse(
            id=chunk.id,
            document_id=chunk.document_id,
            collection_id=chunk.collection_id,
            content=chunk.content,
            content_hash=chunk.content_hash,
            chunk_index=chunk.chunk_index,
            embedding_model=chunk.embedding_model,
            meta=chunk.meta or {},
            created_at=chunk.created_at.isoformat(),
        )
        for chunk in chunks
    ]

    return ChunkListResponse(total=total, items=items)


@router.get("/{chunk_id}", response_model=ChunkResponse)
async def get_chunk_detail(
    chunk_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """获取单个分块的详细信息

    - 需要认证
    - 只能查询自己的分块
    - 返回完整的分块信息（包含向量维度等）
    """
    # 查询分块
    query = (
        select(DocumentChunk)
        .join(Document)
        .join(Collection)
        .where(DocumentChunk.id == chunk_id, Collection.user_id == current_user.id)
    )
    result = await db.execute(query)
    chunk = result.scalar_one_or_none()

    if not chunk:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="分块不存在或无权访问")

    return ChunkResponse(
        id=chunk.id,
        document_id=chunk.document_id,
        collection_id=chunk.collection_id,
        content=chunk.content,
        content_hash=chunk.content_hash,
        chunk_index=chunk.chunk_index,
        embedding_model=chunk.embedding_model,
        meta=chunk.meta or {},
        created_at=chunk.created_at.isoformat(),
    )


@router.get("/collection/{collection_id}", response_model=ChunkListResponse)
async def get_collection_chunks(
    collection_id: UUID,
    limit: int = Query(20, ge=1, le=100, description="每页数量"),
    offset: int = Query(0, ge=0, description="偏移量"),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """获取知识库的所有分块

    - 需要认证
    - 只能查询自己的知识库
    - 支持分页
    - 按创建时间倒序排序
    """
    # 验证知识库访问权限
    collection_query = select(Collection).where(Collection.id == collection_id, Collection.user_id == current_user.id)
    collection_result = await db.execute(collection_query)
    collection = collection_result.scalar_one_or_none()

    if not collection:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="知识库不存在或无权访问")

    # 查询总数
    count_query = select(func.count()).select_from(DocumentChunk).where(DocumentChunk.collection_id == collection_id)
    total_result = await db.execute(count_query)
    total = total_result.scalar()

    # 查询分块列表
    query = (
        select(DocumentChunk)
        .where(DocumentChunk.collection_id == collection_id)
        .order_by(DocumentChunk.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    result = await db.execute(query)
    chunks = result.scalars().all()

    # 转换为响应模型
    items = [
        ChunkResponse(
            id=chunk.id,
            document_id=chunk.document_id,
            collection_id=chunk.collection_id,
            content=chunk.content,
            content_hash=chunk.content_hash,
            chunk_index=chunk.chunk_index,
            embedding_model=chunk.embedding_model,
            meta=chunk.meta or {},
            created_at=chunk.created_at.isoformat(),
        )
        for chunk in chunks
    ]

    return ChunkListResponse(total=total, items=items)


@router.delete("/{chunk_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_chunk(
    chunk_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """删除单个分块

    - 需要认证
    - 只能删除自己的分块
    - 会更新文档的分块统计
    """
    # 查询分块
    query = (
        select(DocumentChunk)
        .join(Document)
        .join(Collection)
        .where(DocumentChunk.id == chunk_id, Collection.user_id == current_user.id)
    )
    result = await db.execute(query)
    chunk = result.scalar_one_or_none()

    if not chunk:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="分块不存在或无权访问")

    # 获取文档和知识库
    document_query = select(Document).where(Document.id == chunk.document_id)
    doc_result = await db.execute(document_query)
    document = doc_result.scalar_one()

    collection_query = select(Collection).where(Collection.id == chunk.collection_id)
    coll_result = await db.execute(collection_query)
    collection = coll_result.scalar_one()

    # 删除分块
    await db.delete(chunk)

    # 更新统计
    if document.chunk_count > 0:
        document.chunk_count -= 1
    if collection.chunk_count > 0:
        collection.chunk_count -= 1

    await db.commit()
