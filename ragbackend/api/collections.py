"""Collections API routes."""

import logging
import asyncio
from typing import List, Optional

from fastapi import APIRouter, HTTPException, UploadFile, File, Depends, status, Response
from fastapi.responses import JSONResponse

from ragbackend.schemas.collections import (
    CollectionCreate,
    CollectionUpdate,
    CollectionResponse,
    CollectionListResponse
)
from ragbackend.schemas.document import DocumentResponse, SearchQuery, SearchResult
from ragbackend.database import collections as db_collections, files as db_files
from ragbackend.services.minio_service import get_minio_service, MinIOService
from ragbackend.services.document_processor import process_document_async
from ragbackend.database.vectors import search_vectors, get_vector_stats
from ragbackend.services.embedding_service import get_collection_embedding_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/collections", tags=["collections"])


# 支持的文件格式
SUPPORTED_CONTENT_TYPES = {
    'application/pdf',
    'text/plain', 
    'text/markdown',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'application/msword',
    'text/html',
    'application/rtf'
}

# 文件大小限制 (10MB)
MAX_FILE_SIZE = 10 * 1024 * 1024


def validate_file(file: UploadFile) -> None:
    """验证上传的文件"""
    # 检查文件类型
    if file.content_type not in SUPPORTED_CONTENT_TYPES:
        raise HTTPException(
            status_code=400, 
            detail=f"不支持的文件格式: {file.content_type}. 支持的格式: {', '.join(SUPPORTED_CONTENT_TYPES)}"
        )
    
    # 检查文件大小（注意：这里只是初步检查，实际大小需要在读取后确认）
    if file.size and file.size > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"文件过大: {file.size} bytes. 最大支持: {MAX_FILE_SIZE} bytes"
        )


@router.post("/", response_model=CollectionResponse, status_code=status.HTTP_201_CREATED)
async def create_collection(collection: CollectionCreate):
    """Create a new collection."""
    try:
        result = await db_collections.create_collection(
            name=collection.name,
            description=collection.description,
            embedding_model=collection.embedding_model,
            embedding_provider=collection.embedding_provider
        )
        return CollectionResponse(**result)
    except Exception as e:
        logger.error(f"Failed to create collection: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/", response_model=List[CollectionResponse])
async def get_collections():
    """Get all collections."""
    try:
        collections = await db_collections.get_all_collections()
        return [CollectionResponse(**collection) for collection in collections]
    except Exception as e:
        logger.error(f"Failed to get collections: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{collection_id}", response_model=CollectionResponse)
async def get_collection(collection_id: str):
    """Get collection by ID."""
    try:
        collection = await db_collections.get_collection_by_id(collection_id)
        if not collection:
            raise HTTPException(status_code=404, detail="Collection not found")
        return CollectionResponse(**collection)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get collection {collection_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{collection_id}", response_model=CollectionResponse)
async def update_collection(collection_id: str, collection: CollectionUpdate):
    """Update collection."""
    try:
        result = await db_collections.update_collection(
            collection_id=collection_id,
            name=collection.name,
            description=collection.description
        )
        if not result:
            raise HTTPException(status_code=404, detail="Collection not found")
        return CollectionResponse(**result)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update collection {collection_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{collection_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_collection(collection_id: str):
    """Delete collection."""
    try:
        deleted = await db_collections.delete_collection(collection_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Collection not found")
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete collection {collection_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# 文件相关端点
@router.post("/{collection_id}/files", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_file(
    collection_id: str,
    file: UploadFile = File(...),
    minio_service: MinIOService = Depends(get_minio_service)
):
    """
    上传文件到指定集合
    
    Args:
        collection_id: 集合ID
        file: 上传的文件
        minio_service: MinIO服务依赖注入
    
    Returns:
        DocumentResponse: 文件信息
    """
    try:
        # 验证集合是否存在
        collection = await db_collections.get_collection_by_id(collection_id)
        if not collection:
            raise HTTPException(status_code=404, detail="集合不存在")
        
        # 验证文件
        validate_file(file)
        
        # 创建文件记录（状态为uploading）
        file_record = await db_files.create_file(
            collection_id=collection_id,
            filename=file.filename,
            content_type=file.content_type,
            size=0,  # 暂时设为0，上传后更新
            object_path=""  # 暂时为空，上传后更新
        )
        
        file_id = file_record['id']
        
        try:
            # 上传文件到MinIO
            upload_result = await minio_service.upload_file(
                file=file,
                user_id="default",  # TODO: 从认证中获取用户ID
                collection_id=collection_id,
                file_id=file_id
            )
            
            # 更新文件记录
            updated_file = await db_files.update_file_info(
                file_id=file_id,
                size=upload_result['size'],
                object_path=upload_result['object_path']
            )
            
            # 更新文件状态为处理中
            await db_files.update_file_status(file_id, "processing")
            
            logger.info(f"文件上传成功: {file.filename}, ID: {file_id}")
            
            # 触发异步文档处理任务
            asyncio.create_task(process_document_async(file_id))
            
            return DocumentResponse(
                id=file_id,
                collection_id=collection_id,
                content=f"文件 {file.filename} 上传成功，正在处理中...",
                metadata={
                    "filename": file.filename,
                    "content_type": file.content_type,
                    "size": upload_result['size'],
                    "status": "processing"
                },
                created_at=updated_file['created_at'],
                updated_at=updated_file['updated_at']
            )
            
        except Exception as upload_error:
            # 上传失败，删除文件记录
            await db_files.delete_file(file_id)
            logger.error(f"文件上传失败: {upload_error}")
            raise HTTPException(status_code=500, detail=f"文件上传失败: {str(upload_error)}")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"处理文件上传时发生错误: {e}")
        raise HTTPException(status_code=500, detail="文件上传失败")


@router.get("/{collection_id}/files", response_model=List[DocumentResponse])
async def get_collection_files(collection_id: str):
    """
    获取集合中的所有文件
    
    Args:
        collection_id: 集合ID
    
    Returns:
        List[DocumentResponse]: 文件列表
    """
    try:
        # 验证集合是否存在
        collection = await db_collections.get_collection_by_id(collection_id)
        if not collection:
            raise HTTPException(status_code=404, detail="集合不存在")
        
        # 获取文件列表
        files = await db_files.get_files_by_collection(collection_id)
        
        return [
            DocumentResponse(
                id=file['id'],
                collection_id=file['collection_id'],
                content=f"文件: {file['filename']}",
                metadata={
                    "filename": file['filename'],
                    "content_type": file['content_type'],
                    "size": file['size'],
                    "status": file['status']
                },
                created_at=file['created_at'],
                updated_at=file['updated_at']
            )
            for file in files
        ]
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取文件列表时发生错误: {e}")
        raise HTTPException(status_code=500, detail="获取文件列表失败")


# 搜索和统计端点
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
