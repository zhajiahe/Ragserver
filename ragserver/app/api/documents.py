"""
文档管理 API

包含文档的上传、删除、更新、查询、处理等功能
"""
from typing import List, Optional
from uuid import UUID
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status, Query, UploadFile, File, Form
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession

from ragserver.app.dependencies import get_db, get_current_active_user
from ragserver.app.models import Document, Collection, DocumentChunk, User
from ragserver.app.utils.date_util import get_current_time
from ragserver.app.utils.minio_client import minio_client
from ragserver.config import settings

router = APIRouter(tags=["文档管理"])


# ==================== Pydantic Schemas ====================

class DocumentBase(BaseModel):
    """文档基础模型"""
    filename: str = Field(..., description="文件名")
    file_type: str = Field(..., description="文件类型")
    file_size: int = Field(..., description="文件大小（字节）")
    meta: Optional[dict] = Field(default_factory=dict, description="元数据")


class DocumentCreate(DocumentBase):
    """文档创建模型"""
    pass


class DocumentUpdate(BaseModel):
    """文档更新模型"""
    chunking_config: Optional[dict] = Field(None, description="分块配置")
    meta: Optional[dict] = Field(None, description="元数据")


class DocumentResponse(BaseModel):
    """文档响应模型"""
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    collection_id: UUID
    uploaded_by: UUID
    filename: str
    file_type: str
    file_size: int
    s3_url: str
    mime_type: str
    file_hash: str
    status: str
    progress: int
    error_message: Optional[str]
    processed_at: Optional[datetime]
    meta: dict
    chunking_config: Optional[dict]
    chunk_count: int
    created_at: datetime
    updated_at: datetime


class DocumentStatusResponse(BaseModel):
    """文档状态响应模型"""
    id: UUID
    status: str
    progress: int
    error_message: Optional[str]
    chunk_count: int
    processed_at: Optional[datetime]


class DocumentListResponse(BaseModel):
    """文档列表响应"""
    total: int
    items: List[DocumentResponse]


class DocumentChunkResponse(BaseModel):
    """文档分块响应模型"""
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    document_id: UUID
    collection_id: UUID
    content: str
    chunk_index: int
    summary: Optional[str]
    meta: dict
    created_at: datetime


class BatchDeleteRequest(BaseModel):
    """批量删除请求"""
    document_ids: List[UUID] = Field(..., description="文档ID列表")


# ==================== Helper Functions ====================

async def verify_collection_access(
    db: AsyncSession,
    collection_id: UUID,
    user_id: UUID
) -> Collection:
    """验证用户是否有权限访问知识库"""
    result = await db.execute(
        select(Collection).where(
            Collection.id == collection_id,
            Collection.user_id == user_id
        )
    )
    collection = result.scalar_one_or_none()
    if not collection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="知识库未找到或无权访问"
        )
    return collection


async def verify_document_access(
    db: AsyncSession,
    document_id: UUID,
    user_id: UUID
) -> Document:
    """验证用户是否有权限访问文档"""
    result = await db.execute(
        select(Document).where(
            Document.id == document_id,
            Document.uploaded_by == user_id
        )
    )
    document = result.scalar_one_or_none()
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="文档未找到或无权访问"
        )
    return document


# ==================== API Endpoints ====================

@router.get(
    "/api/v1/collections/{collection_id}/documents",
    response_model=DocumentListResponse,
    summary="获取知识库文档列表"
)
async def get_documents(
    collection_id: UUID,
    status_filter: Optional[str] = Query(None, description="按状态过滤: pending/processing/completed/failed"),
    limit: int = Query(20, ge=1, le=100, description="每页数量"),
    offset: int = Query(0, ge=0, description="偏移量"),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    获取指定知识库的文档列表
    
    支持分页和状态过滤
    """
    # 验证权限
    await verify_collection_access(db, collection_id, current_user.id)
    
    # 构建查询
    query = select(Document).where(
        Document.collection_id == collection_id,
        Document.uploaded_by == current_user.id
    )
    
    if status_filter:
        query = query.where(Document.status == status_filter)
    
    # 获取总数
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar()
    
    # 获取分页数据
    query = query.order_by(Document.created_at.desc()).limit(limit).offset(offset)
    result = await db.execute(query)
    documents = result.scalars().all()
    
    return DocumentListResponse(total=total, items=documents)


@router.post(
    "/api/v1/collections/{collection_id}/upload",
    response_model=List[DocumentResponse],
    status_code=status.HTTP_201_CREATED,
    summary="上传文档（批量）"
)
async def upload_documents(
    collection_id: UUID,
    files: List[UploadFile] = File(...),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    上传文档到指定知识库（支持批量上传）
    
    """
    # 验证权限
    collection = await verify_collection_access(db, collection_id, current_user.id)
    
    created_documents = []
    
    for file in files:
        minio_info = await minio_client.upload_file(
            bucket_name=settings.minio_bucket_documents,
            file=file.file,
            file_name=file.filename or "unknown.txt",
        )
        document = Document(
            collection_id=collection_id,
            uploaded_by=current_user.id,
            filename=minio_info['filename'],
            file_type=minio_info['file_type'],
            file_size=minio_info['file_size'],
            s3_url=minio_info['s3_url'],
            mime_type=minio_info['mime_type'],
            file_hash=minio_info['file_hash'],
            status="pending",
            progress=0,
        )
        db.add(document)
        created_documents.append(document)
    
    # 更新知识库统计信息
    collection.document_count += len(created_documents)
    collection.last_updated_at = get_current_time()
    
    await db.commit()
    
    # 刷新所有文档以获取生成的ID
    for doc in created_documents:
        await db.refresh(doc)
    
    return created_documents


@router.get(
    "/api/v1/documents/{document_id}",
    response_model=DocumentResponse,
    summary="获取文档详情"
)
async def get_document_detail(
    document_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """获取文档详细信息"""
    document = await verify_document_access(db, document_id, current_user.id)
    return document


@router.delete(
    "/api/v1/documents",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="删除文档（批量）"
)
async def delete_documents(
    request: BatchDeleteRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    批量删除文档
    
    会级联删除相关的文档分块
    TODO: 实现删除MinIO中的文件
    """
    if not request.document_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="文档ID列表不能为空"
        )
    
    # 验证所有文档的权限
    for doc_id in request.document_ids:
        await verify_document_access(db, doc_id, current_user.id)
    
    # 批量删除
    # TODO: 删除 MinIO 中的文件
    await db.execute(
        delete(Document).where(
            Document.id.in_(request.document_ids),
            Document.uploaded_by == current_user.id
        )
    )
    
    await db.commit()
    return None




@router.put(
    "/api/v1/documents/{document_id}",
    response_model=DocumentResponse,
    summary="更新文档解析配置"
)
async def update_document(
    document_id: UUID,
    update_data: DocumentUpdate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    更新文档的解析配置（如分块配置、语言等）
    
    修改配置后可能需要重新处理文档
    """
    document = await verify_document_access(db, document_id, current_user.id)
    
    # 更新字段
    update_dict = update_data.model_dump(exclude_unset=True)
    for key, value in update_dict.items():
        setattr(document, key, value)
    
    document.updated_at = get_current_time()
    
    await db.commit()
    await db.refresh(document)
    
    return document


@router.get(
    "/api/v1/documents/{document_id}/status",
    response_model=DocumentStatusResponse,
    summary="查询文档处理状态"
)
async def get_document_status(
    document_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    查询文档的处理状态
    
    可用于前端轮询获取处理进度
    """
    document = await verify_document_access(db, document_id, current_user.id)
    
    return DocumentStatusResponse(
        id=document.id,
        status=document.status,
        progress=document.progress,
        error_message=document.error_message,
        chunk_count=document.chunk_count,
        processed_at=document.processed_at,
    )


@router.get(
    "/api/v1/documents-chunks/{document_id}",
    response_model=List[DocumentChunkResponse],
    summary="获取文档分块列表"
)
async def get_document_chunks(
    document_id: UUID,
    limit: int = Query(100, ge=1, le=1000, description="每页数量"),
    offset: int = Query(0, ge=0, description="偏移量"),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    获取文档的分块列表
    
    返回文档的所有分块，按chunk_index排序
    """
    # 验证权限
    document = await verify_document_access(db, document_id, current_user.id)
    
    # 查询分块
    result = await db.execute(
        select(DocumentChunk)
        .where(
            DocumentChunk.document_id == document_id,
            DocumentChunk.user_id == current_user.id
        )
        .order_by(DocumentChunk.chunk_index)
        .limit(limit)
        .offset(offset)
    )
    chunks = result.scalars().all()
    
    return chunks

