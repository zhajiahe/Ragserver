"""
文档处理任务

实现文档解析、分块、向量化的异步任务
"""
import asyncio
import hashlib
from typing import List, Dict, Any, Optional
from uuid import UUID
import traceback
from io import BytesIO

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from langchain_text_splitters import (
    RecursiveCharacterTextSplitter,
    MarkdownHeaderTextSplitter,
)
from openai import AsyncOpenAI

from ragserver.tasks import broker
from ragserver.app.models import Document, DocumentChunk, Collection
from ragserver.app.dependencies.db import async_session_factory
from ragserver.app.utils.minio_client import minio_client
from ragserver.app.utils.date_util import get_current_time
from ragserver.config import settings

from ragserver.app.utils.embedding_service import EmbeddingService
from ragserver.app.utils.chunkers import chunk_text


# ==================== 文档解析服务 ====================

class DocumentParser:
    """文档解析服务"""
    
    @staticmethod
    async def parse_document(file_content: bytes, file_type: str, filename: str) -> str:
        """
        解析文档为 Markdown 格式文本
        
        Args:
            file_content: 文件内容（字节）
            file_type: 文件类型（pdf, docx, txt等）
            filename: 文件名
            
        Returns:
            str: Markdown 格式的文档内容
        """
        try:
            if file_type == "txt":
                return file_content.decode("utf-8")
            
            elif file_type == "md":
                return file_content.decode("utf-8")
            
            elif file_type == "pdf":
                return await DocumentParser._parse_pdf(file_content)
            
            elif file_type in ["docx", "doc"]:
                return await DocumentParser._parse_docx(file_content)
            
            elif file_type == "html" or file_type == "htm":
                return await DocumentParser._parse_html(file_content)
            
            elif file_type in ["xlsx", "xls", "csv"]:
                return await DocumentParser._parse_excel(file_content, file_type)
            
            else:
                raise ValueError(f"不支持的文件类型: {file_type}")
                
        except Exception as e:
            logger.error(f"解析文档失败 {filename}: {e}")
            raise
    
    @staticmethod
    async def _parse_pdf(file_content: bytes) -> str:
        """解析 PDF 文档"""
        try:
            from pdfminer.high_level import extract_text
            file_obj = BytesIO(file_content)
            text = extract_text(file_obj)
            return text
        except Exception as e:
            logger.error(f"PDF 解析失败: {e}")
            # 可以在这里集成 OCR 方案（如 PaddleOCR 或 MinerU）
            raise ValueError(f"PDF 解析失败: {e}")
    
    @staticmethod
    async def _parse_docx(file_content: bytes) -> str:
        """解析 DOCX 文档"""
        try:
            import docx
            file_obj = BytesIO(file_content)
            doc = docx.Document(file_obj)
            paragraphs = [para.text for para in doc.paragraphs if para.text.strip()]
            return "\n\n".join(paragraphs)
        except Exception as e:
            logger.error(f"DOCX 解析失败: {e}")
            raise ValueError(f"DOCX 解析失败: {e}")
    
    @staticmethod
    async def _parse_html(file_content: bytes) -> str:
        """解析 HTML 文档"""
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(file_content, "html.parser")
            # 移除 script 和 style 标签
            for script in soup(["script", "style"]):
                script.decompose()
            text = soup.get_text()
            # 清理多余空行
            lines = [line.strip() for line in text.splitlines() if line.strip()]
            return "\n\n".join(lines)
        except Exception as e:
            logger.error(f"HTML 解析失败: {e}")
            raise ValueError(f"HTML 解析失败: {e}")
    
    @staticmethod
    async def _parse_excel(file_content: bytes, file_type: str) -> str:
        """解析 Excel/CSV 文档"""
        try:
            import pandas as pd
            file_obj = BytesIO(file_content)
            
            if file_type == "csv":
                df = pd.read_csv(file_obj)
            else:
                df = pd.read_excel(file_obj, sheet_name=None)  # 读取所有 sheet
                # 将所有 sheet 合并为文本
                if isinstance(df, dict):
                    text_parts = []
                    for sheet_name, sheet_df in df.items():
                        text_parts.append(f"# Sheet: {sheet_name}\n\n")
                        text_parts.append(sheet_df.to_markdown(index=False))
                        text_parts.append("\n\n")
                    return "".join(text_parts)
                df = df
            
            # 转换为 Markdown 表格
            return df.to_markdown(index=False)
        except Exception as e:
            logger.error(f"Excel 解析失败: {e}")
            raise ValueError(f"Excel 解析失败: {e}")


# ==================== 文档分块服务 ====================

class DocumentChunker:
    """文档分块服务"""
    
    @staticmethod
    def chunk_text(
        text: str,
        chunking_config: Dict[str, Any]
    ) -> List[str]:
        """
        对文本进行分块
        
        Args:
            text: 文档内容
            chunking_config: 分块配置
            
        Returns:
            List[str]: 分块列表
        """
        strategy_type = chunking_config.get("strategy_type", "recursive")
        config = chunking_config.get("config", {})
        
        if strategy_type == "recursive":
            return DocumentChunker._chunk_recursive(text, config)
        elif strategy_type == "markdown":
            return DocumentChunker._chunk_markdown(text, config)
        elif strategy_type == "paragraph":
            return DocumentChunker._chunk_paragraph(text, config)
        else:
            # 默认使用递归分块
            return DocumentChunker._chunk_recursive(text, config)
    
    @staticmethod
    def _chunk_recursive(text: str, config: Dict[str, Any]) -> List[str]:
        """递归字符分块"""
        chunk_size = config.get("max_chunk_size", 800)
        chunk_overlap = config.get("chunk_overlap", 200)
        separators = config.get("separators", ["\n\n", "\n", "。", "！", "？", ". ", "! ", "? ", " ", ""])
        
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=separators,
            length_function=len,
        )
        
        chunks = splitter.split_text(text)
        return [chunk for chunk in chunks if chunk.strip()]
    
    @staticmethod
    def _chunk_markdown(text: str, config: Dict[str, Any]) -> List[str]:
        """Markdown 标题分块"""
        headers_to_split_on = config.get("headers_to_split_on", [
            ("#", "Header 1"),
            ("##", "Header 2"),
            ("###", "Header 3"),
        ])
        
        markdown_splitter = MarkdownHeaderTextSplitter(
            headers_to_split_on=headers_to_split_on
        )
        
        splits = markdown_splitter.split_text(text)
        
        # 如果分块后仍然太大，进一步递归分块
        max_chunk_size = config.get("max_chunk_size", 800)
        final_chunks = []
        
        for split in splits:
            content = split.page_content
            if len(content) > max_chunk_size:
                # 使用递归分块进一步切分
                sub_chunks = DocumentChunker._chunk_recursive(
                    content, 
                    {"max_chunk_size": max_chunk_size, "chunk_overlap": 200}
                )
                final_chunks.extend(sub_chunks)
            else:
                final_chunks.append(content)
        
        return [chunk for chunk in final_chunks if chunk.strip()]
    
    @staticmethod
    def _chunk_paragraph(text: str, config: Dict[str, Any]) -> List[str]:
        """段落分块"""
        max_chunk_size = config.get("max_chunk_size", 800)
        min_chunk_size = config.get("min_chunk_size", 100)
        merge_short = config.get("merge_short_paragraphs", True)
        
        # 按段落分割
        paragraphs = text.split("\n\n")
        paragraphs = [p.strip() for p in paragraphs if p.strip()]
        
        chunks = []
        current_chunk = ""
        
        for para in paragraphs:
            # 如果段落本身就太长，递归分块
            if len(para) > max_chunk_size:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                    current_chunk = ""
                
                sub_chunks = DocumentChunker._chunk_recursive(
                    para,
                    {"max_chunk_size": max_chunk_size, "chunk_overlap": 100}
                )
                chunks.extend(sub_chunks)
            else:
                # 尝试合并到当前 chunk
                if len(current_chunk) + len(para) + 2 <= max_chunk_size:
                    current_chunk += para + "\n\n"
                else:
                    if current_chunk:
                        chunks.append(current_chunk.strip())
                    current_chunk = para + "\n\n"
        
        # 添加最后一个 chunk
        if current_chunk:
            chunks.append(current_chunk.strip())
        
        # 如果启用合并短段落，合并太短的 chunk
        if merge_short:
            final_chunks = []
            temp_chunk = ""
            
            for chunk in chunks:
                if len(temp_chunk) + len(chunk) <= max_chunk_size:
                    temp_chunk += chunk + "\n\n"
                else:
                    if temp_chunk:
                        final_chunks.append(temp_chunk.strip())
                    temp_chunk = chunk + "\n\n"
            
            if temp_chunk:
                final_chunks.append(temp_chunk.strip())
            
            return [c for c in final_chunks if len(c) >= min_chunk_size]
        
        return chunks



# ==================== 文档处理任务 ====================

@broker.task(
    task_name="process_document",
    max_retries=settings.taskiq_max_retries,
    retry_on_error=True,
)
async def process_document_task(document_id: str) -> Dict[str, Any]:
    """
    处理文档任务（解析、分块、向量化）
    
    Args:
        document_id: 文档 ID
        
    Returns:
        Dict: 处理结果
    """
    doc_uuid = UUID(document_id)
    logger.info(f"开始处理文档: {document_id}")
    
    async with async_session_factory() as db:
        try:
            # 1. 获取文档信息
            result = await db.execute(
                select(Document).where(Document.id == doc_uuid)
            )
            document = result.scalar_one_or_none()
            
            if not document:
                raise ValueError(f"文档不存在: {document_id}")
            
            # 2. 获取知识库信息
            result = await db.execute(
                select(Collection).where(Collection.id == document.collection_id)
            )
            collection = result.scalar_one_or_none()
            
            if not collection:
                raise ValueError(f"知识库不存在: {document.collection_id}")
            
            # 更新状态为处理中
            document.status = "processing"
            document.progress = 10
            document.updated_at = get_current_time()
            await db.commit()
            
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
            await db.commit()
            
            # 4. 解析文档
            logger.info(f"开始解析文档: {document.filename}")
            parser = DocumentParser()
            content_text = await parser.parse_document(
                file_content,
                document.file_type,
                document.filename
            )
            
            # 保存解析后的文本
            document.content_text = content_text
            document.progress = 40
            await db.commit()
            logger.info(f"文档解析完成，内容长度: {len(content_text)} 字符")
            
            # 5. 获取分块配置
            chunking_config = await get_chunking_config(collection, document)
            logger.info(f"分块配置: {chunking_config}")
            
            # 6. 分块
            logger.info("开始分块...")
            chunker = DocumentChunker()
            chunks = chunker.chunk_text(content_text, chunking_config)
            logger.info(f"分块完成，共 {len(chunks)} 块")
            
            document.progress = 60
            await db.commit()
            
            # 7. 生成向量
            logger.info("开始生成向量...")
            embedding_service = EmbeddingService()
            
            # 批量生成向量（避免一次性提交太多）
            batch_size = settings.embedding_batch_size
            all_embeddings = []
            
            for i in range(0, len(chunks), batch_size):
                batch_chunks = chunks[i:i + batch_size]
                batch_embeddings = await embedding_service.encode(batch_chunks)
                all_embeddings.extend(batch_embeddings)
                
                # 更新进度
                progress = 60 + int((i / len(chunks)) * 30)
                document.progress = min(progress, 90)
                await db.commit()
                
                logger.info(f"向量生成进度: {i + len(batch_chunks)}/{len(chunks)}")
            
            logger.info(f"向量生成完成，共 {len(all_embeddings)} 个向量")
            
            # 8. 保存分块到数据库
            logger.info("保存分块到数据库...")
            chunk_objects = []
            
            for idx, (chunk_text, embedding) in enumerate(zip(chunks, all_embeddings)):
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
            db.add_all(chunk_objects)
            
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
            
            await db.commit()
            
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
            logger.error(traceback.format_exc())
            
            try:
                # 更新文档状态为失败
                result = await db.execute(
                    select(Document).where(Document.id == doc_uuid)
                )
                document = result.scalar_one_or_none()
                
                if document:
                    document.status = "failed"
                    document.progress = 0
                    document.error_message = str(e)[:1000]  # 限制错误消息长度
                    document.updated_at = get_current_time()
                    await db.commit()
            except Exception as update_error:
                logger.error(f"更新文档状态失败: {update_error}")
            
            raise


@broker.task(
    task_name="reprocess_document",
    max_retries=settings.taskiq_max_retries,
    retry_on_error=True,
)
async def reprocess_document_task(document_id: str) -> Dict[str, Any]:
    """
    重新处理文档任务（删除旧分块，重新处理）
    
    Args:
        document_id: 文档 ID
        
    Returns:
        Dict: 处理结果
    """
    doc_uuid = UUID(document_id)
    logger.info(f"开始重新处理文档: {document_id}")
    
    async with async_session_factory() as db:
        try:
            # 1. 删除旧的分块
            from sqlalchemy import delete
            await db.execute(
                delete(DocumentChunk).where(DocumentChunk.document_id == doc_uuid)
            )
            await db.commit()
            logger.info(f"已删除文档 {document_id} 的旧分块")
            
            # 2. 重置文档状态
            result = await db.execute(
                select(Document).where(Document.id == doc_uuid)
            )
            document = result.scalar_one_or_none()
            
            if document:
                document.status = "pending"
                document.progress = 0
                document.chunk_count = 0
                document.error_message = None
                document.updated_at = get_current_time()
                await db.commit()
            
            # 3. 调用正常的处理任务
            return await process_document_task(document_id)
            
        except Exception as e:
            logger.error(f"重新处理文档失败: {document_id}, 错误: {e}")
            raise


# ==================== 辅助函数 ====================

async def get_chunking_config(
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

