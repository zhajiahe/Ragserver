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
    status_code=status.HTTP_200_OK,
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
    - 同步处理，直接返回结果
    - 可通过状态接口查询进度
    """
    from ragserver.app.services.document_pipeline import process_document
    
    if not request.document_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="文档ID列表不能为空"
        )
    
    # 验证所有文档的权限并处理
    processed_ids = []
    results = []
    errors = []
    
    for doc_id in request.document_ids:
        try:
            document = await verify_document_access(db, doc_id, current_user.id)
            
            if document.status == "completed":
                # 已经处理完成的文档跳过
                results.append({
                    "document_id": str(doc_id),
                    "status": "skipped",
                    "message": "文档已处理完成"
                })
                continue
            
            # 直接处理文档
            result = await process_document(db, doc_id)
            results.append(result)
            processed_ids.append(doc_id)
            
        except Exception as e:
            errors.append({
                "document_id": str(doc_id),
                "error": str(e)
            })
    
    return {
        "message": f"已处理 {len(processed_ids)} 个文档",
        "document_ids": processed_ids,
        "results": results,
        "errors": errors if errors else None,
    }


@router.post(
    "/reprocess",
    status_code=status.HTTP_200_OK,
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
    """
    from ragserver.app.services.document_pipeline import reprocess_document
    
    if not request.document_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="文档ID列表不能为空"
        )
    
    # 验证所有文档的权限并处理
    reprocessed_ids = []
    results = []
    errors = []
    
    for doc_id in request.document_ids:
        try:
            document = await verify_document_access(db, doc_id, current_user.id)
            
            # 直接重新处理文档
            result = await reprocess_document(db, doc_id)
            results.append(result)
            reprocessed_ids.append(doc_id)
            
        except Exception as e:
            errors.append({
                "document_id": str(doc_id),
                "error": str(e)
            })
    
    return {
        "message": f"已重新处理 {len(reprocessed_ids)} 个文档",
        "document_ids": reprocessed_ids,
        "results": results,
        "errors": errors if errors else None,
    }

