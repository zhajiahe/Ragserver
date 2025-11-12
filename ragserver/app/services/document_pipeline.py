"""
文档处理流水线服务

实现简单的同步文档处理流程：解析 -> 分块 -> 向量化 -> 存储
"""
import hashlib
from typing import List, Dict, Any, Optional
from uuid import UUID

from loguru import logger
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from ragserver.app.models import Document, DocumentChunk, Collection
from ragserver.app.utils.minio_client import minio_client
from ragserver.app.utils.date_util import get_current_time
from ragserver.app.utils.embedding_service import EmbeddingService
from ragserver.app.utils.parsers import parse_document as parse_document_content
from ragserver.app.utils.chunkers import chunk_text
from ragserver.config import settings


class DocumentProcessingPipeline:
    """文档处理流水线"""
    
    def __init__(self, db: AsyncSession):
        """
        初始化文档处理流水线
        
        Args:
            db: 数据库会话
        """
        self.db = db
        self.embedding_service = EmbeddingService()
    
    async def process_document(self, document_id: UUID) -> Dict[str, Any]:
        """
        处理文档（解析、分块、向量化）
        
        Args:
            document_id: 文档 ID
            
        Returns:
            Dict: 处理结果
            
        Raises:
            ValueError: 文档不存在或处理失败
        """
        logger.info(f"开始处理文档: {document_id}")
        
        try:
            # 1. 获取文档信息
            result = await self.db.execute(
                select(Document).where(Document.id == document_id)
            )
            document = result.scalar_one_or_none()
            
            if not document:
                raise ValueError(f"文档不存在: {document_id}")
            
            # 2. 获取知识库信息
            result = await self.db.execute(
                select(Collection).where(Collection.id == document.collection_id)
            )
            collection = result.scalar_one_or_none()
            
            if not collection:
                raise ValueError(f"知识库不存在: {document.collection_id}")
            
            # 更新状态为处理中
            document.status = "processing"
            document.progress = 10
            document.updated_at = get_current_time()
            await self.db.commit()
            
            # 3. 从 MinIO 下载文件
            logger.info(f"从 MinIO 下载文件: {document.s3_url}")
            object_key = document.s3_url.split(f"{settings.minio_bucket_documents}/")[-1]
            response = await minio_client.download_file(
                settings.minio_bucket_documents,
                object_key
            )
            
            file_content = await response['Body'].read()
            logger.info(f"文件下载完成，大小: {len(file_content)} bytes")
            
            # 更新进度
            document.progress = 20
            await self.db.commit()
            
            # 4. 解析文档
            logger.info(f"开始解析文档: {document.filename}")
            content_text = await parse_document_content(
                file_content,
                document.file_type,
                document.filename
            )
            
            # 保存解析后的文本
            document.content_text = content_text
            document.progress = 40
            await self.db.commit()
            logger.info(f"文档解析完成，内容长度: {len(content_text)} 字符")
            
            # 5. 获取分块配置
            chunking_config = self._get_chunking_config(collection, document)
            logger.info(f"分块配置: {chunking_config}")
            
            # 6. 分块
            logger.info("开始分块...")
            chunks_data = await chunk_text(content_text, chunking_config)
            chunks = [chunk['content'] for chunk in chunks_data]
            logger.info(f"分块完成，共 {len(chunks)} 块")
            
            document.progress = 60
            await self.db.commit()
            
            # 7. 生成向量
            logger.info("开始生成向量...")
            all_embeddings = await self._generate_embeddings(chunks, document)
            logger.info(f"向量生成完成，共 {len(all_embeddings)} 个向量")
            
            # 8. 保存分块到数据库
            logger.info("保存分块到数据库...")
            await self._save_chunks(
                chunks=chunks,
                embeddings=all_embeddings,
                document=document,
                chunking_config=chunking_config
            )
            
            # 9. 更新文档状态
            document.status = "completed"
            document.progress = 100
            document.chunk_count = len(chunks)
            document.processed_at = get_current_time()
            document.updated_at = get_current_time()
            document.error_message = None
            
            # 10. 更新知识库统计
            collection.chunk_count = (collection.chunk_count or 0) + len(chunks)
            collection.last_updated_at = get_current_time()
            
            await self.db.commit()
            
            logger.info(f"文档处理完成: {document_id}, 生成 {len(chunks)} 个分块")
            
            return {
                "document_id": str(document.id),
                "status": "completed",
                "chunk_count": len(chunks),
                "content_length": len(content_text),
            }
            
        except Exception as e:
            # 错误处理
            logger.error(f"文档处理失败: {document_id}, 错误: {e}")
            
            try:
                # 更新文档状态为失败
                result = await self.db.execute(
                    select(Document).where(Document.id == document_id)
                )
                document = result.scalar_one_or_none()
                
                if document:
                    document.status = "failed"
                    document.progress = 0
                    document.error_message = str(e)[:1000]  # 限制错误消息长度
                    document.updated_at = get_current_time()
                    await self.db.commit()
            except Exception as update_error:
                logger.error(f"更新文档状态失败: {update_error}")
            
            raise
    
    async def reprocess_document(self, document_id: UUID) -> Dict[str, Any]:
        """
        重新处理文档（删除旧分块，重新处理）
        
        Args:
            document_id: 文档 ID
            
        Returns:
            Dict: 处理结果
        """
        logger.info(f"开始重新处理文档: {document_id}")
        
        try:
            # 1. 删除旧的分块
            await self.db.execute(
                delete(DocumentChunk).where(DocumentChunk.document_id == document_id)
            )
            await self.db.commit()
            logger.info(f"已删除文档 {document_id} 的旧分块")
            
            # 2. 重置文档状态
            result = await self.db.execute(
                select(Document).where(Document.id == document_id)
            )
            document = result.scalar_one_or_none()
            
            if document:
                document.status = "pending"
                document.progress = 0
                document.chunk_count = 0
                document.error_message = None
                document.updated_at = get_current_time()
                await self.db.commit()
            
            # 3. 调用正常的处理流程
            return await self.process_document(document_id)
            
        except Exception as e:
            logger.error(f"重新处理文档失败: {document_id}, 错误: {e}")
            raise
    
    async def _generate_embeddings(
        self, 
        chunks: List[str], 
        document: Document
    ) -> List[List[float]]:
        """
        生成向量（批量处理）
        
        Args:
            chunks: 文本块列表
            document: 文档对象（用于更新进度）
            
        Returns:
            List[List[float]]: 向量列表
        """
        batch_size = settings.embedding_batch_size
        all_embeddings = []
        
        for i in range(0, len(chunks), batch_size):
            batch_chunks = chunks[i:i + batch_size]
            batch_embeddings = await self.embedding_service.encode(batch_chunks)
            all_embeddings.extend(batch_embeddings)
            
            # 更新进度
            progress = 60 + int((i / len(chunks)) * 30)
            document.progress = min(progress, 90)
            await self.db.commit()
            
            logger.info(f"向量生成进度: {i + len(batch_chunks)}/{len(chunks)}")
        
        return all_embeddings
    
    async def _save_chunks(
        self,
        chunks: List[str],
        embeddings: List[List[float]],
        document: Document,
        chunking_config: Dict[str, Any]
    ) -> None:
        """
        保存分块到数据库
        
        Args:
            chunks: 文本块列表
            embeddings: 向量列表
            document: 文档对象
            chunking_config: 分块配置
        """
        chunk_objects = []
        
        for idx, (chunk_text, embedding) in enumerate(zip(chunks, embeddings)):
            # 计算 chunk hash
            chunk_hash = hashlib.sha256(chunk_text.encode()).hexdigest()
            
            chunk_obj = DocumentChunk(
                document_id=document.id,
                collection_id=document.collection_id,
                user_id=document.uploaded_by,
                content=chunk_text,
                content_hash=chunk_hash,
                chunk_index=idx,
                content_embedding=embedding,
                embedding_model=settings.default_embedding_model,
                meta={
                    "chunk_size": len(chunk_text),
                    "chunking_strategy": chunking_config.get("strategy_type"),
                }
            )
            chunk_objects.append(chunk_obj)
        
        # 批量插入
        self.db.add_all(chunk_objects)
        await self.db.commit()
    
    def _get_chunking_config(
        self, 
        collection: Collection, 
        document: Optional[Document] = None
    ) -> Dict[str, Any]:
        """
        获取分块配置（文档级优先，知识库级备选）
        
        Args:
            collection: 知识库对象
            document: 文档对象（可选）
            
        Returns:
            Dict: 分块配置
        """
        # 文档级配置优先
        if document and document.chunking_config:
            return document.chunking_config
        
        # 知识库级配置
        if collection.settings and 'chunking_config' in collection.settings:
            return collection.settings['chunking_config']
        
        # 默认配置
        return {
            "strategy_type": "recursive",
            "config": {
                "max_chunk_size": 800,
                "chunk_overlap": 200,
                "separators": ["\n\n", "\n", "。", "！", "？", ". ", "! ", "? ", " ", ""]
            }
        }


# ==================== 便捷函数 ====================

async def process_document(db: AsyncSession, document_id: UUID) -> Dict[str, Any]:
    """
    处理文档的便捷函数
    
    Args:
        db: 数据库会话
        document_id: 文档 ID
        
    Returns:
        Dict: 处理结果
    """
    pipeline = DocumentProcessingPipeline(db)
    return await pipeline.process_document(document_id)


async def reprocess_document(db: AsyncSession, document_id: UUID) -> Dict[str, Any]:
    """
    重新处理文档的便捷函数
    
    Args:
        db: 数据库会话
        document_id: 文档 ID
        
    Returns:
        Dict: 处理结果
    """
    pipeline = DocumentProcessingPipeline(db)
    return await pipeline.reprocess_document(document_id)

