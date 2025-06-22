"""Document processing service."""

import logging
import io
from typing import List, Dict, Any, Optional
from pathlib import Path

from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import (
    TextLoader, 
    PyPDFLoader,
    Docx2txtLoader,
    UnstructuredHTMLLoader
)
from langchain.schema import Document

from ragbackend.config import CHUNK_SIZE, CHUNK_OVERLAP
from ragbackend.services.embedding_service import get_collection_embedding_service
from ragbackend.services.minio_service import get_minio_service
from ragbackend.database import files as db_files, collections as db_collections
from ragbackend.database.vectors import insert_vectors, VectorDocument

logger = logging.getLogger(__name__)


class DocumentProcessor:
    """文档处理器"""
    
    def __init__(self, chunk_size: int = CHUNK_SIZE, chunk_overlap: int = CHUNK_OVERLAP):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            length_function=len,
            separators=[]
        )
        self.minio_service = get_minio_service()
    
    async def process_file(self, file_id: str) -> bool:
        """
        处理文件：下载、解析、分块、向量化、存储
        
        Args:
            file_id: 文件ID
        
        Returns:
            bool: 处理是否成功
        """
        try:
            # 获取文件信息
            file_info = await db_files.get_file_by_id(file_id)
            if not file_info:
                logger.error(f"文件不存在: {file_id}")
                return False
            
            # 获取集合信息
            collection = await db_collections.get_collection_by_id(file_info['collection_id'])
            if not collection:
                logger.error(f"集合不存在: {file_info['collection_id']}")
                return False
            
            # 更新文件状态为处理中
            await db_files.update_file_status(file_id, "processing")
            
            # 从MinIO下载文件
            file_stream = await self.minio_service.download_file(file_info['object_path'])
            file_content = file_stream.read()
            
            # 解析文档
            documents = await self._parse_document(
                file_content, 
                file_info['filename'], 
                file_info['content_type']
            )
            
            if not documents:
                logger.warning(f"文档解析失败或无内容: {file_id}")
                await db_files.update_file_status(file_id, "failed")
                return False
            
            # 文档分块
            chunks = self._split_documents(documents)
            logger.info(f"文档分块完成: {len(chunks)} 个块")
            
            # 获取嵌入服务
            embedding_service = await get_collection_embedding_service(collection)
            
            # 批量向量化
            texts = [chunk.page_content for chunk in chunks]
            embeddings = await embedding_service.embed_texts(texts)
            
            # 准备向量文档
            vector_docs = []
            for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
                # 确保元数据只包含可序列化的基本类型
                clean_metadata = {
                    "chunk_index": i,
                    "filename": file_info['filename'],
                    "content_type": file_info['content_type']
                }
                
                # 添加chunk的元数据，但只保留基本类型
                if chunk.metadata:
                    for key, value in chunk.metadata.items():
                        if isinstance(value, (str, int, float, bool, type(None))):
                            clean_metadata[key] = value
                        else:
                            clean_metadata[key] = str(value)  # 转换为字符串
                
                vector_doc = VectorDocument(
                    file_id=file_id,
                    content=chunk.page_content,
                    metadata=clean_metadata,
                    embedding=embedding
                )
                vector_docs.append(vector_doc)
            
            # 存储到向量数据库
            logger.info(f"准备插入 {len(vector_docs)} 个向量到集合 {collection['id']}")
            insert_success = await insert_vectors(collection['id'], vector_docs)
            
            if not insert_success:
                logger.error(f"向量插入失败: {file_id}")
                await db_files.update_file_status(file_id, "failed")
                return False
            
            # 更新文件状态为完成
            await db_files.update_file_status(file_id, "completed")
            
            logger.info(f"文档处理完成: {file_id}, 生成 {len(vector_docs)} 个向量")
            return True
            
        except Exception as e:
            logger.error(f"文档处理失败 {file_id}: {e}")
            await db_files.update_file_status(file_id, "failed")
            return False
    
    async def _parse_document(self, file_content: bytes, filename: str, content_type: str) -> List[Document]:
        """
        解析文档内容
        
        Args:
            file_content: 文件内容
            filename: 文件名
            content_type: 文件类型
        
        Returns:
            List[Document]: 解析后的文档列表
        """
        try:
            # 创建临时文件
            temp_file = f"/tmp/{filename}"
            with open(temp_file, "wb") as f:
                f.write(file_content)
            
            documents = []
            
            if content_type == "text/plain":
                # 文本文件
                with open(temp_file, "r", encoding="utf-8") as f:
                    content = f.read()
                documents = [Document(page_content=content, metadata={"source": filename})]
                
            elif content_type == "application/pdf":
                # PDF文件
                loader = PyPDFLoader(temp_file)
                documents = await self._async_load(loader)
                
            elif content_type in ["application/vnd.openxmlformats-officedocument.wordprocessingml.document", "application/msword"]:
                # Word文档
                loader = Docx2txtLoader(temp_file)
                documents = await self._async_load(loader)
                
            elif content_type == "text/html":
                # HTML文件
                loader = UnstructuredHTMLLoader(temp_file)
                documents = await self._async_load(loader)
                
            elif content_type == "text/markdown":
                # Markdown文件
                with open(temp_file, "r", encoding="utf-8") as f:
                    content = f.read()
                documents = [Document(page_content=content, metadata={"source": filename})]
            
            else:
                logger.warning(f"不支持的文件类型: {content_type}")
                return []
            
            # 清理临时文件
            Path(temp_file).unlink(missing_ok=True)
            
            return documents
            
        except Exception as e:
            logger.error(f"文档解析失败: {e}")
            return []
    
    async def _async_load(self, loader) -> List[Document]:
        """异步加载文档"""
        # 由于langchain的loader是同步的，这里用线程池执行
        import asyncio
        return await asyncio.get_event_loop().run_in_executor(None, loader.load)
    
    def _split_documents(self, documents: List[Document]) -> List[Document]:
        """
        分割文档
        
        Args:
            documents: 原始文档列表
        
        Returns:
            List[Document]: 分割后的文档块列表
        """
        chunks = []
        for doc in documents:
            # 使用RecursiveCharacterTextSplitter分割
            doc_chunks = self.text_splitter.split_documents([doc])
            chunks.extend(doc_chunks)
        
        return chunks


# 全局文档处理器实例
_document_processor: Optional[DocumentProcessor] = None


def get_document_processor() -> DocumentProcessor:
    """获取文档处理器实例（单例模式）"""
    global _document_processor
    if _document_processor is None:
        _document_processor = DocumentProcessor()
    return _document_processor


async def process_document_async(file_id: str) -> bool:
    """异步处理文档（用于后台任务）"""
    processor = get_document_processor()
    return await processor.process_file(file_id)
