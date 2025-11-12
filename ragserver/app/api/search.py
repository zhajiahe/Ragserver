"""
搜索 API
"""
from typing import List, Optional, Literal
from uuid import UUID
from datetime import datetime, timezone
from enum import Enum

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy import select, func, text, Integer
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from ragserver.app.dependencies import get_db, get_current_active_user
from ragserver.app.models import Collection, User, CollectionShare, DocumentChunk
from ragserver.config import settings
from ragserver.app.utils.date_util import get_current_time
from ragserver.app.utils.embedding_service import embedding_service

router = APIRouter(tags=["搜索"])


# ==================== Pydantic Schemas ====================

class SearchMode(str, Enum):
    """搜索模式"""
    VECTOR = "vector"  # 向量搜索
    FULLTEXT = "fulltext"  # 全文搜索 (BM25)
    HYBRID = "hybrid"  # 混合搜索


class SearchRequest(BaseModel):
    """搜索请求"""
    query: str = Field(..., min_length=1, max_length=1000, description="搜索查询")
    mode: SearchMode = Field(default=SearchMode.VECTOR, description="搜索模式: vector/fulltext/hybrid")
    top_k: int = Field(default=10, ge=1, le=100, description="返回结果数量")
    threshold: float = Field(default=0.7, ge=0.0, le=1.0, description="相似度阈值（向量搜索）")
    collection_ids: Optional[List[UUID]] = Field(default=None, description="知识库ID列表（可选）")
    
    # 混合搜索权重配置
    vector_weight: float = Field(default=0.7, ge=0.0, le=1.0, description="向量搜索权重（混合模式）")
    fulltext_weight: float = Field(default=0.3, ge=0.0, le=1.0, description="全文搜索权重（混合模式）")


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
    mode: str
    total: int
    results: List[SearchResultItem]
    search_time_ms: int


# ==================== Helper Functions ====================

async def vector_search(
    db: AsyncSession,
    query: str,
    user_id: Optional[UUID],
    collection_ids: Optional[List[UUID]],
    top_k: int,
    threshold: float
) -> List[tuple]:
    """
    向量搜索
    
    Returns:
        List[tuple]: [(chunk, similarity), ...]
    """
    # 生成查询向量
    query_embedding = await embedding_service.encode_single(query)
    
    # 构建查询
    query_stmt = select(
        DocumentChunk,
        (1 - DocumentChunk.content_embedding.cosine_distance(query_embedding)).label('similarity')
    ).where(
        (1 - DocumentChunk.content_embedding.cosine_distance(query_embedding)) >= threshold
    )
    
    # 添加用户过滤
    if user_id:
        query_stmt = query_stmt.where(DocumentChunk.user_id == user_id)
    
    # 添加知识库过滤
    if collection_ids:
        query_stmt = query_stmt.where(DocumentChunk.collection_id.in_(collection_ids))
    
    # 排序和限制
    query_stmt = query_stmt.order_by(
        DocumentChunk.content_embedding.cosine_distance(query_embedding)
    ).limit(top_k)
    
    result = await db.execute(query_stmt)
    return result.all()


async def fulltext_search(
    db: AsyncSession,
    query: str,
    user_id: Optional[UUID],
    collection_ids: Optional[List[UUID]],
    top_k: int
) -> List[tuple]:
    """
    全文搜索 (BM25 或 LIKE 回退)
    
    Returns:
        List[tuple]: [(chunk, score), ...]
    """
    try:
        # 首先检查 BM25 索引是否存在
        check_index_query = text("""
            SELECT indexname FROM pg_indexes 
            WHERE tablename = 'document_chunks' 
            AND indexname = 'document_chunks_bm25_idx'
        """)
        index_result = await db.execute(check_index_query)
        has_bm25_index = index_result.scalar() is not None
        
        if has_bm25_index:
            # 使用 ParadeDB BM25 搜索
            base_query = """
                SELECT 
                    dc.*,
                    paradedb.score(dc.id) as score
                FROM document_chunks dc
                WHERE dc.id @@@ paradedb.parse(:query)
            """
            
            params = {"query": query}
            
            # 添加用户过滤
            if user_id:
                base_query += " AND dc.user_id = :user_id"
                params["user_id"] = str(user_id)
            
            # 添加知识库过滤
            if collection_ids:
                placeholders = ",".join([f":cid_{i}" for i in range(len(collection_ids))])
                base_query += f" AND dc.collection_id IN ({placeholders})"
                for i, cid in enumerate(collection_ids):
                    params[f"cid_{i}"] = str(cid)
            
            # 排序和限制
            base_query += " ORDER BY score DESC LIMIT :limit"
            params["limit"] = top_k
            
            result = await db.execute(text(base_query), params)
            rows = result.fetchall()
            
            # 转换为 (chunk, score) 格式
            results = []
            for row in rows:
                # 重新查询完整的 DocumentChunk 对象
                chunk_result = await db.execute(
                    select(DocumentChunk).where(DocumentChunk.id == row.id)
                )
                chunk = chunk_result.scalar_one_or_none()
                if chunk:
                    results.append((chunk, float(row.score)))
            
            logger.info(f"BM25 搜索完成，找到 {len(results)} 个结果")
            return results
        else:
            logger.info("BM25 索引不存在，使用 LIKE 搜索")
            raise Exception("BM25 index not available")
        
    except Exception as e:
        logger.debug(f"BM25 搜索不可用，使用 LIKE 搜索: {e}")
        # 回退到简单的 LIKE 搜索
        # 使用 PostgreSQL 的 ts_rank 进行简单的文本相关性评分
        query_stmt = select(
            DocumentChunk,
            # 简单评分：匹配次数
            func.cast(
                func.length(DocumentChunk.content) - 
                func.length(func.replace(func.lower(DocumentChunk.content), func.lower(query), '')),
                Integer
            ).label('score')
        ).where(
            DocumentChunk.content.ilike(f"%{query}%")
        )
        
        if user_id:
            query_stmt = query_stmt.where(DocumentChunk.user_id == user_id)
        
        if collection_ids:
            query_stmt = query_stmt.where(DocumentChunk.collection_id.in_(collection_ids))
        
        # 按评分排序
        query_stmt = query_stmt.order_by(text('score DESC')).limit(top_k)
        
        result = await db.execute(query_stmt)
        return result.all()


async def hybrid_search(
    db: AsyncSession,
    query: str,
    user_id: Optional[UUID],
    collection_ids: Optional[List[UUID]],
    top_k: int,
    threshold: float,
    vector_weight: float,
    fulltext_weight: float
) -> List[tuple]:
    """
    混合搜索 (向量 + 全文)
    
    Returns:
        List[tuple]: [(chunk, combined_score), ...]
    """
    # 1. 执行向量搜索
    vector_results = await vector_search(
        db, query, user_id, collection_ids, top_k * 2, threshold
    )
    
    # 2. 执行全文搜索
    fulltext_results = await fulltext_search(
        db, query, user_id, collection_ids, top_k * 2
    )
    
    # 3. 合并结果
    # 使用字典存储每个 chunk 的分数
    chunk_scores = {}
    
    # 添加向量搜索结果
    for chunk, similarity in vector_results:
        chunk_scores[chunk.id] = {
            'chunk': chunk,
            'vector_score': float(similarity),
            'fulltext_score': 0.0
        }
    
    # 添加全文搜索结果
    for chunk, score in fulltext_results:
        if chunk.id in chunk_scores:
            chunk_scores[chunk.id]['fulltext_score'] = float(score)
        else:
            chunk_scores[chunk.id] = {
                'chunk': chunk,
                'vector_score': 0.0,
                'fulltext_score': float(score)
            }
    
    # 4. 计算综合分数并排序
    combined_results = []
    for chunk_id, scores in chunk_scores.items():
        # 归一化分数（如果需要）
        vector_score = scores['vector_score']
        fulltext_score = scores['fulltext_score']
        
        # 计算加权综合分数
        combined_score = (
            vector_weight * vector_score +
            fulltext_weight * fulltext_score
        )
        
        combined_results.append((scores['chunk'], combined_score))
    
    # 按综合分数排序
    combined_results.sort(key=lambda x: x[1], reverse=True)
    
    # 返回 top_k 结果
    return combined_results[:top_k]


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
    - 支持三种搜索模式：vector（向量）、fulltext（全文）、hybrid（混合）
    """
    import time
    start_time = time.time()
    
    try:
        logger.info(f"用户 {current_user.id} {req.mode.value} 搜索: {req.query}")
        
        # 根据搜索模式选择搜索方法
        if req.mode == SearchMode.VECTOR:
            rows = await vector_search(
                db, req.query, current_user.id, req.collection_ids, 
                req.top_k, req.threshold
            )
        elif req.mode == SearchMode.FULLTEXT:
            rows = await fulltext_search(
                db, req.query, current_user.id, req.collection_ids, req.top_k
            )
        elif req.mode == SearchMode.HYBRID:
            rows = await hybrid_search(
                db, req.query, current_user.id, req.collection_ids,
                req.top_k, req.threshold, req.vector_weight, req.fulltext_weight
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"不支持的搜索模式: {req.mode}"
            )
        
        # 构建响应
        results = []
        for chunk, score in rows:
            results.append(SearchResultItem(
                chunk_id=chunk.id,
                document_id=chunk.document_id,
                collection_id=chunk.collection_id,
                content=chunk.content,
                similarity=float(score),
                metadata=chunk.meta or {},
                chunk_index=chunk.chunk_index
            ))
        
        search_time_ms = int((time.time() - start_time) * 1000)
        
        logger.info(f"{req.mode.value} 搜索完成，找到 {len(results)} 个结果，耗时 {search_time_ms}ms")
        
        return SearchResponse(
            query=req.query,
            mode=req.mode.value,
            total=len(results),
            results=results,
            search_time_ms=search_time_ms,
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"搜索失败: {e}", exc_info=True)
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
        logger.info(f"分享链接 {share_token} {req.mode.value} 搜索: {req.query}")
        
        # 根据搜索模式选择搜索方法（限定到分享的知识库）
        collection_ids = [share.collection_id]
        
        if req.mode == SearchMode.VECTOR:
            rows = await vector_search(
                db, req.query, None, collection_ids, req.top_k, req.threshold
            )
        elif req.mode == SearchMode.FULLTEXT:
            rows = await fulltext_search(
                db, req.query, None, collection_ids, req.top_k
            )
        elif req.mode == SearchMode.HYBRID:
            rows = await hybrid_search(
                db, req.query, None, collection_ids,
                req.top_k, req.threshold, req.vector_weight, req.fulltext_weight
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"不支持的搜索模式: {req.mode}"
            )
        
        # 构建响应
        results = []
        for chunk, score in rows:
            results.append(SearchResultItem(
                chunk_id=chunk.id,
                document_id=chunk.document_id,
                collection_id=chunk.collection_id,
                content=chunk.content,
                similarity=float(score),
                metadata=chunk.meta or {},
                chunk_index=chunk.chunk_index
            ))
        
        search_time_ms = int((time.time() - start_time) * 1000)
        
        logger.info(f"分享链接 {req.mode.value} 搜索完成，找到 {len(results)} 个结果，耗时 {search_time_ms}ms")
        
        return SearchResponse(
            query=req.query,
            mode=req.mode.value,
            total=len(results),
            results=results,
            search_time_ms=search_time_ms,
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"分享链接搜索失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"搜索失败: {str(e)}"
        )

