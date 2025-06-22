"""Vector database operations."""

import logging
from typing import List, Dict, Any, Optional, NamedTuple
from uuid import UUID
import asyncpg
import json

from ragbackend.database.connection import get_db_connection
from ragbackend.utils.validators import validate_uuid, validate_and_sanitize_table_name

logger = logging.getLogger(__name__)


class VectorDocument(NamedTuple):
    """向量文档数据结构"""
    file_id: str
    content: str
    metadata: Dict[str, Any]
    embedding: List[float]


class SearchResult(NamedTuple):
    """搜索结果数据结构"""
    id: str
    content: str
    metadata: Dict[str, Any]
    score: float


async def insert_vectors(collection_id: str, vector_docs: List[VectorDocument]) -> bool:
    """
    批量插入向量文档
    
    Args:
        collection_id: 集合ID
        vector_docs: 向量文档列表
    
    Returns:
        bool: 插入是否成功
    """
    if not vector_docs:
        return True
    
    try:
        # 验证集合ID并生成表名
        uuid_obj = validate_uuid(collection_id)
        table_name = validate_and_sanitize_table_name(str(uuid_obj))
        
        logger.info(f"开始向量插入: 集合 {collection_id}, 表名 {table_name}, 向量数量 {len(vector_docs)}")
        
        async with get_db_connection() as conn:
            # 准备批量插入数据
            records = []
            for doc in vector_docs:
                file_uuid = validate_uuid(doc.file_id)
                # 将元数据转换为JSON字符串以兼容asyncpg
                metadata_json = json.dumps(doc.metadata) if doc.metadata else json.dumps({})
                # 现在可以直接使用Python列表，因为已经注册了vector类型
                records.append((
                    file_uuid,
                    doc.content,
                    metadata_json,
                    doc.embedding  # 直接使用Python列表
                ))
            
            logger.info(f"准备插入数据: {len(records)} 条记录")
            
            # 批量插入
            await conn.executemany(f"""
                INSERT INTO {table_name} (file_id, content, metadata, embedding)
                VALUES ($1, $2, $3, $4)
            """, records)
            
            logger.info(f"成功插入 {len(vector_docs)} 个向量到表 {table_name}")
            return True
            
    except Exception as e:
        logger.error(f"向量插入失败: {e}")
        logger.error(f"集合ID: {collection_id}, 向量数量: {len(vector_docs) if vector_docs else 0}")
        import traceback
        logger.error(f"堆栈跟踪: {traceback.format_exc()}")
        return False


async def search_vectors(
    collection_id: str, 
    query_embedding: List[float], 
    limit: int = 10,
    metadata_filter: Optional[Dict[str, Any]] = None
) -> List[SearchResult]:
    """
    向量相似度搜索
    
    Args:
        collection_id: 集合ID
        query_embedding: 查询向量
        limit: 返回结果数量限制
        metadata_filter: 元数据过滤条件
    
    Returns:
        List[SearchResult]: 搜索结果列表
    """
    try:
        # 验证集合ID并生成表名
        uuid_obj = validate_uuid(collection_id)
        table_name = validate_and_sanitize_table_name(str(uuid_obj))
        
        # 现在可以直接使用Python列表，因为已经注册了vector类型
        # 构建查询SQL
        base_sql = f"""
            SELECT id, content, metadata, 
                   1 - (embedding <=> $1) as score
            FROM {table_name}
        """
        
        params = [query_embedding]  # 直接使用Python列表
        
        where_conditions = []
        
        # 添加元数据过滤条件
        if metadata_filter:
            for key, value in metadata_filter.items():
                where_conditions.append(f"metadata ->> ${len(params) + 1} = ${len(params) + 2}")
                params.extend([key, str(value)])
        
        if where_conditions:
            base_sql += " WHERE " + " AND ".join(where_conditions)
        
        base_sql += f" ORDER BY embedding <=> $1 LIMIT ${len(params) + 1}"
        params.append(limit)
        
        async with get_db_connection() as conn:
            rows = await conn.fetch(base_sql, *params)
            
            results = []
            for row in rows:
                # 解析JSON格式的metadata
                metadata = {}
                if row['metadata']:
                    try:
                        metadata = json.loads(row['metadata']) if isinstance(row['metadata'], str) else row['metadata']
                    except (json.JSONDecodeError, TypeError):
                        metadata = {}
                
                result = SearchResult(
                    id=str(row['id']),
                    content=row['content'],
                    metadata=metadata,
                    score=float(row['score'])
                )
                results.append(result)
            
            logger.info(f"向量搜索完成: 查询表 {table_name}, 返回 {len(results)} 个结果")
            return results
            
    except Exception as e:
        logger.error(f"向量搜索失败: {e}")
        return []


async def delete_vectors_by_file(collection_id: str, file_id: str) -> bool:
    """
    删除指定文件的所有向量
    
    Args:
        collection_id: 集合ID
        file_id: 文件ID
    
    Returns:
        bool: 删除是否成功
    """
    try:
        # 验证ID并生成表名
        collection_uuid = validate_uuid(collection_id)
        file_uuid = validate_uuid(file_id)
        table_name = validate_and_sanitize_table_name(str(collection_uuid))
        
        async with get_db_connection() as conn:
            result = await conn.execute(f"""
                DELETE FROM {table_name} WHERE file_id = $1
            """, file_uuid)
            
            deleted_count = int(result.split()[-1])
            logger.info(f"删除文件 {file_id} 的 {deleted_count} 个向量")
            return True
            
    except Exception as e:
        logger.error(f"删除文件向量失败: {e}")
        return False


async def get_vector_stats(collection_id: str) -> Dict[str, Any]:
    """
    获取集合向量统计信息
    
    Args:
        collection_id: 集合ID
    
    Returns:
        Dict[str, Any]: 统计信息
    """
    try:
        # 验证集合ID并生成表名
        uuid_obj = validate_uuid(collection_id)
        table_name = validate_and_sanitize_table_name(str(uuid_obj))
        
        async with get_db_connection() as conn:
            # 获取向量总数
            total_vectors = await conn.fetchval(f"SELECT COUNT(*) FROM {table_name}")
            
            # 获取文件数
            unique_files = await conn.fetchval(f"SELECT COUNT(DISTINCT file_id) FROM {table_name}")
            
            # 获取最近创建时间
            latest_created = await conn.fetchval(f"SELECT MAX(created_at) FROM {table_name}")
            
            return {
                "total_vectors": total_vectors,
                "unique_files": unique_files,
                "latest_created": latest_created.isoformat() if latest_created else None
            }
            
    except Exception as e:
        logger.error(f"获取向量统计失败: {e}")
        return {
            "total_vectors": 0,
            "unique_files": 0,
            "latest_created": None
        }


async def check_table_exists(collection_id: str) -> bool:
    """
    检查集合对应的向量表是否存在
    
    Args:
        collection_id: 集合ID
    
    Returns:
        bool: 表是否存在
    """
    try:
        # 验证集合ID并生成表名
        uuid_obj = validate_uuid(collection_id)
        table_name = validate_and_sanitize_table_name(str(uuid_obj))
        
        async with get_db_connection() as conn:
            result = await conn.fetchval("""
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.tables 
                    WHERE table_name = $1
                )
            """, table_name)
            
            return bool(result)
            
    except Exception as e:
        logger.error(f"检查表存在性失败: {e}")
        return False 