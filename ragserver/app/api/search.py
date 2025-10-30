"""
搜索 API
"""
from typing import List, Optional
from uuid import UUID
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from ragserver.app.dependencies import get_db, get_current_active_user
from ragserver.app.models import Collection, User, CollectionShare, DocumentChunk
from ragserver.config import settings

router = APIRouter(tags=["搜索"])


# ==================== Pydantic Schemas ====================

class SearchRequest(BaseModel):
    """搜索请求"""
    query: str = Field(..., min_length=1, max_length=1000, description="搜索查询")
    top_k: int = Field(default=10, ge=1, le=100, description="返回结果数量")
    threshold: float = Field(default=0.7, ge=0.0, le=1.0, description="相似度阈值")
    collection_ids: Optional[List[UUID]] = Field(default=None, description="知识库ID列表（可选）")


class SearchResultItem(BaseModel):
    """搜索结果项"""
    model_config = ConfigDict(from_attributes=True)
    
    chunk_id: UUID
    document_id: UUID
    collection_id: UUID
    content: str
    similarity: float
    metadata: dict
    chunk_index: int


class SearchResponse(BaseModel):
    """搜索响应"""
    query: str
    total: int
    results: List[SearchResultItem]
    search_time_ms: int


# ==================== API Endpoints ====================

@router.post("/api/v1/search", response_model=SearchResponse)
async def search(
    req: SearchRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """搜索知识库
    
    - 需要认证
    - 支持多知识库搜索
    - 基于向量相似度搜索
    """
    import time
    start_time = time.time()
    
    # TODO: 实现向量搜索逻辑
    # 1. 生成查询向量
    # 2. 查询 DocumentChunk 表
    # 3. 按相似度排序
    # 4. 返回结果
    
    # 临时返回空结果
    search_time_ms = int((time.time() - start_time) * 1000)
    
    return SearchResponse(
        query=req.query,
        total=0,
        results=[],
        search_time_ms=search_time_ms,
    )


@router.post("/api/v1/share/{share_token}/search", response_model=SearchResponse)
async def search_by_share_token(
    share_token: str,
    req: SearchRequest,
    db: AsyncSession = Depends(get_db)
):
    """通过分享链接搜索知识库
    
    - 无需认证
    - 仅搜索分享的知识库
    - 受分享配置限制
    """
    import time
    start_time = time.time()
    
    # 查询分享链接
    share_query = select(CollectionShare).where(
        CollectionShare.share_token == share_token
    )
    share_result = await db.execute(share_query)
    share = share_result.scalar_one_or_none()
    
    if not share:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="分享链接不存在"
        )
    
    # 检查分享是否激活
    if not share.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="分享链接已停用"
        )
    
    # 检查是否过期
    if share.expires_at and share.expires_at < datetime.utcnow():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="分享链接已过期"
        )
    
    # 应用分享配置的限制
    search_config = share.search_config or {}
    max_top_k = search_config.get("max_top_k", 20)
    if req.top_k > max_top_k:
        req.top_k = max_top_k
    
    # 更新使用统计
    share.usage_count += 1
    share.last_used_at = datetime.utcnow()
    await db.commit()
    
    # TODO: 实现向量搜索逻辑
    # 1. 生成查询向量
    # 2. 查询 DocumentChunk 表（限定 collection_id）
    # 3. 按相似度排序
    # 4. 返回结果
    
    # 临时返回空结果
    search_time_ms = int((time.time() - start_time) * 1000)
    
    return SearchResponse(
        query=req.query,
        total=0,
        results=[],
        search_time_ms=search_time_ms,
    )

