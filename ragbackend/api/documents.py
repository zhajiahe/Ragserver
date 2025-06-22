"""Documents API routes for search functionality."""

import logging
from typing import List

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import JSONResponse

from ragbackend.schemas.document import SearchQuery, SearchResult
from ragbackend.database import collections as db_collections
from ragbackend.database.vectors import search_vectors, get_vector_stats
from ragbackend.services.embedding_service import get_collection_embedding_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/collections", tags=["documents"])


@router.post("/{collection_id}/search", response_model=List[SearchResult])
async def search_documents(collection_id: str, query: SearchQuery):
    """
    在集合中搜索相关文档
    
    Args:
        collection_id: 集合ID
        query: 搜索查询参数
    
    Returns:
        List[SearchResult]: 搜索结果列表
    """
    try:
        # 验证集合是否存在
        collection = await db_collections.get_collection_by_id(collection_id)
        if not collection:
            raise HTTPException(status_code=404, detail="集合不存在")
        
        # 验证查询参数
        if not query.query or not query.query.strip():
            raise HTTPException(status_code=400, detail="查询文本不能为空")
        
        # 限制返回数量
        limit = min(query.limit or 10, 100)  # 最大100个结果
        
        # 获取嵌入服务
        embedding_service = await get_collection_embedding_service(collection)
        
        # 将查询文本向量化
        query_embedding = await embedding_service.embed_query(query.query)
        
        # 执行向量搜索
        search_results = await search_vectors(
            collection_id=collection_id,
            query_embedding=query_embedding,
            limit=limit,
            metadata_filter=query.filter
        )
        
        # 转换为API响应格式
        results = []
        for result in search_results:
            search_result = SearchResult(
                id=result.id,
                page_content=result.content,
                metadata=result.metadata,
                score=result.score
            )
            results.append(search_result)
        
        logger.info(f"搜索完成: 集合 {collection_id}, 查询 '{query.query}', 返回 {len(results)} 个结果")
        return results
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"搜索文档时发生错误: {e}")
        raise HTTPException(status_code=500, detail="搜索失败")


@router.get("/{collection_id}/stats")
async def get_collection_stats(collection_id: str):
    """
    获取集合统计信息
    
    Args:
        collection_id: 集合ID
    
    Returns:
        dict: 集合统计信息
    """
    try:
        # 验证集合是否存在
        collection = await db_collections.get_collection_by_id(collection_id)
        if not collection:
            raise HTTPException(status_code=404, detail="集合不存在")
        
        # 获取向量统计信息
        vector_stats = await get_vector_stats(collection_id)
        
        # 组合统计信息
        stats = {
            "collection_id": collection_id,
            "collection_name": collection['name'],
            "embedding_model": collection['embedding_model'],
            "embedding_provider": collection['embedding_provider'],
            "total_vectors": vector_stats['total_vectors'],
            "unique_files": vector_stats['unique_files'],
            "latest_created": vector_stats['latest_created'],
            "created_at": collection['created_at'],
            "updated_at": collection['updated_at']
        }
        
        return stats
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取集合统计信息时发生错误: {e}")
        raise HTTPException(status_code=500, detail="获取统计信息失败")


@router.post("/collections/{collection_id}/reindex")
async def reindex_collection(collection_id: str):
    """
    重新索引集合中的所有文档（重新处理和向量化）
    
    Args:
        collection_id: 集合ID
    
    Returns:
        dict: 重新索引任务信息
    """
    try:
        # 验证集合是否存在
        collection = await db_collections.get_collection_by_id(collection_id)
        if not collection:
            raise HTTPException(status_code=404, detail="集合不存在")
        
        # TODO: 实现重新索引逻辑
        # 1. 获取集合中所有文件
        # 2. 清空现有向量数据
        # 3. 重新处理所有文件
        # 4. 返回任务状态
        
        return {
            "message": "重新索引功能待实现",
            "collection_id": collection_id,
            "status": "pending"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"重新索引集合时发生错误: {e}")
        raise HTTPException(status_code=500, detail="重新索引失败")
