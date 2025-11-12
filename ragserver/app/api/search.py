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
from loguru import logger

from ragserver.app.dependencies import get_db, get_current_active_user
from ragserver.app.models import Collection, User, CollectionShare, DocumentChunk
from ragserver.config import settings
from ragserver.app.utils.date_util import get_current_time
from ragserver.app.utils.embedding_service import embedding_service

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
    
    try:
        # 1. 生成查询向量
        logger.info(f"用户 {current_user.id} 搜索: {req.query}")
        query_embedding = await embedding_service.encode_single(req.query)
        
        # 2. 构建查询条件
        query_stmt = select(
            DocumentChunk,
            (1 - DocumentChunk.content_embedding.cosine_distance(query_embedding)).label('similarity')
        ).where(
            DocumentChunk.user_id == current_user.id,
            (1 - DocumentChunk.content_embedding.cosine_distance(query_embedding)) >= req.threshold
        )
        
        # 如果指定了知识库列表，则限定范围
        if req.collection_ids:
            query_stmt = query_stmt.where(
                DocumentChunk.collection_id.in_(req.collection_ids)
            )
        
        # 3. 按相似度排序并限制结果数量
        query_stmt = query_stmt.order_by(
            DocumentChunk.content_embedding.cosine_distance(query_embedding)
        ).limit(req.top_k)
        
        # 4. 执行查询
        result = await db.execute(query_stmt)
        rows = result.all()
        
        # 5. 构建响应
        results = []
        for chunk, similarity in rows:
            results.append(SearchResultItem(
                chunk_id=chunk.id,
                document_id=chunk.document_id,
                collection_id=chunk.collection_id,
                content=chunk.content,
                similarity=float(similarity),
                metadata=chunk.meta or {},
                chunk_index=chunk.chunk_index
            ))
        
        search_time_ms = int((time.time() - start_time) * 1000)
        
        logger.info(f"搜索完成，找到 {len(results)} 个结果，耗时 {search_time_ms}ms")
        
        return SearchResponse(
            query=req.query,
            total=len(results),
            results=results,
            search_time_ms=search_time_ms,
        )
        
    except Exception as e:
        logger.error(f"搜索失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"搜索失败: {str(e)}"
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
    if share.expires_at and share.expires_at < get_current_time():
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
    share.last_used_at = get_current_time()
    await db.commit()
    
    try:
        # 1. 生成查询向量
        logger.info(f"分享链接 {share_token} 搜索: {req.query}")
        query_embedding = await embedding_service.encode_single(req.query)
        
        # 2. 构建查询条件（限定到分享的知识库）
        query_stmt = select(
            DocumentChunk,
            (1 - DocumentChunk.content_embedding.cosine_distance(query_embedding)).label('similarity')
        ).where(
            DocumentChunk.collection_id == share.collection_id,
            (1 - DocumentChunk.content_embedding.cosine_distance(query_embedding)) >= req.threshold
        )
        
        # 3. 按相似度排序并限制结果数量
        query_stmt = query_stmt.order_by(
            DocumentChunk.content_embedding.cosine_distance(query_embedding)
        ).limit(req.top_k)
        
        # 4. 执行查询
        result = await db.execute(query_stmt)
        rows = result.all()
        
        # 5. 构建响应
        results = []
        for chunk, similarity in rows:
            results.append(SearchResultItem(
                chunk_id=chunk.id,
                document_id=chunk.document_id,
                collection_id=chunk.collection_id,
                content=chunk.content,
                similarity=float(similarity),
                metadata=chunk.meta or {},
                chunk_index=chunk.chunk_index
            ))
        
        search_time_ms = int((time.time() - start_time) * 1000)
        
        logger.info(f"分享链接搜索完成，找到 {len(results)} 个结果，耗时 {search_time_ms}ms")
        
        return SearchResponse(
            query=req.query,
            total=len(results),
            results=results,
            search_time_ms=search_time_ms,
        )
        
    except Exception as e:
        logger.error(f"分享链接搜索失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"搜索失败: {str(e)}"
        )

