"""Files API routes."""

import logging
from typing import List

from fastapi import APIRouter, HTTPException, Depends, status

from ragbackend.schemas.document import DocumentResponse
from ragbackend.database import files as db_files
from ragbackend.services.minio_service import get_minio_service, MinIOService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/files", tags=["files"])


@router.delete("/{file_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_file(
    file_id: str,
    minio_service: MinIOService = Depends(get_minio_service)
):
    """
    删除文件
    
    Args:
        file_id: 文件ID
        minio_service: MinIO服务依赖注入
    """
    try:
        # 获取文件信息
        file_info = await db_files.get_file_by_id(file_id)
        if not file_info:
            raise HTTPException(status_code=404, detail="文件不存在")
        
        # 从MinIO删除文件
        if file_info['object_path']:
            await minio_service.delete_file(file_info['object_path'])
        
        # 从数据库删除文件记录
        deleted = await db_files.delete_file(file_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="文件不存在")
        
        logger.info(f"文件删除成功: {file_id}")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除文件时发生错误: {e}")
        raise HTTPException(status_code=500, detail="删除文件失败")


@router.get("/{file_id}", response_model=DocumentResponse)
async def get_file(file_id: str):
    """
    获取文件信息
    
    Args:
        file_id: 文件ID
    
    Returns:
        DocumentResponse: 文件信息
    """
    try:
        file_info = await db_files.get_file_by_id(file_id)
        if not file_info:
            raise HTTPException(status_code=404, detail="文件不存在")
        
        return DocumentResponse(
            id=file_info['id'],
            collection_id=file_info['collection_id'],
            content=f"文件: {file_info['filename']}",
            metadata={
                "filename": file_info['filename'],
                "content_type": file_info['content_type'],
                "size": file_info['size'],
                "status": file_info['status']
            },
            created_at=file_info['created_at'],
            updated_at=file_info['updated_at']
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取文件信息时发生错误: {e}")
        raise HTTPException(status_code=500, detail="获取文件信息失败") 