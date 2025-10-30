"""
文档解析 API
"""
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from ragserver.app.dependencies import get_db, get_current_active_user
from ragserver.app.models import User, Document
from ragserver.app.utils.date_util import get_current_time

router = APIRouter(prefix="/api/v1/documents", tags=["文档解析"])


# ==================== Pydantic Schemas ====================

class BatchProcessRequest(BaseModel):
    """批量处理请求"""
    document_ids: List[UUID] = Field(..., description="文档ID列表")


# ==================== Helper Functions ====================

async def verify_document_access(db: AsyncSession, document_id: UUID, user_id: UUID) -> Document:
    """验证文档访问权限"""
    from sqlalchemy import select
    from ragserver.app.models import Collection
    
    query = select(Document).join(Collection).where(
        Document.id == document_id,
        Collection.user_id == user_id
    )
    result = await db.execute(query)
    document = result.scalar_one_or_none()
    
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="文档不存在或无权访问"
        )
    
    return document


# ==================== API Endpoints ====================

@router.post(
    "/process",
    status_code=status.HTTP_202_ACCEPTED,
    summary="处理文档（批量）"
)
async def process_documents(
    request: BatchProcessRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    批量处理文档（解析、分块、向量化）
    
    - 支持批量提交多个文档
    - 异步处理，返回任务ID
    - 可通过状态接口查询进度
    
    TODO: 实现实际的异步任务队列调用
    当前为 Mock 实现，仅更新状态为 processing
    """
    if not request.document_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="文档ID列表不能为空"
        )
    
    # 验证所有文档的权限并更新状态
    processed_ids = []
    for doc_id in request.document_ids:
        document = await verify_document_access(db, doc_id, current_user.id)
        
        if document.status == "completed":
            # 已经处理完成的文档跳过
            continue
        
        # TODO: 在此处触发异步任务
        # await process_document_task.kiq(document_id=doc_id)
        
        # Mock: 更新状态
        document.status = "processing"
        document.progress = 10
        document.updated_at = get_current_time()
        processed_ids.append(doc_id)
    
    await db.commit()
    
    return {
        "message": f"已提交 {len(processed_ids)} 个文档进行处理",
        "document_ids": processed_ids,
        "note": "这是 Mock 实现，实际处理需要集成 Taskiq 异步任务队列"
    }


@router.post(
    "/reprocess",
    status_code=status.HTTP_202_ACCEPTED,
    summary="重新处理文档"
)
async def reprocess_documents(
    request: BatchProcessRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    重新处理文档（重新解析、分块、向量化）
    
    - 会删除现有的分块并重新生成
    - 适用于修改了配置后需要重新处理的场景
    
    TODO: 实现实际的异步任务队列调用
    """
    if not request.document_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="文档ID列表不能为空"
        )
    
    # 验证所有文档的权限
    reprocessed_ids = []
    for doc_id in request.document_ids:
        document = await verify_document_access(db, doc_id, current_user.id)
        
        # TODO: 删除现有的分块
        # await db.execute(
        #     delete(DocumentChunk).where(DocumentChunk.document_id == doc_id)
        # )
        
        # TODO: 触发异步任务
        # await reprocess_document_task.kiq(document_id=doc_id)
        
        # Mock: 重置状态
        document.status = "processing"
        document.progress = 0
        document.chunk_count = 0
        document.error_message = None
        document.updated_at = get_current_time()
        reprocessed_ids.append(doc_id)
    
    await db.commit()
    
    return {
        "message": f"已提交 {len(reprocessed_ids)} 个文档进行重新处理",
        "document_ids": reprocessed_ids,
        "note": "这是 Mock 实现，实际处理需要集成 Taskiq 异步任务队列"
    }

