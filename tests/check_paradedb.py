#!/usr/bin/env python3
"""
检查 ParadeDB BM25 索引状态
"""
import asyncio
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import text
from ragserver.app.dependencies.db import async_engine
from ragserver.config import settings


async def check_paradedb_status():
    """检查 ParadeDB 扩展和 BM25 索引状态"""
    
    print("\n" + "=" * 80)
    print("ParadeDB BM25 索引状态检查")
    print("=" * 80)
    print(f"\n数据库: {settings.postgres_db}")
    print(f"主机: {settings.postgres_host}:{settings.postgres_port}")
    
    try:
        async with async_engine.connect() as conn:
            # 1. 检查 ParadeDB 扩展
            print("\n" + "-" * 80)
            print("1. ParadeDB 扩展检查")
            print("-" * 80)
            
            result = await conn.execute(text("""
                SELECT 
                    extname,
                    extversion,
                    extrelocatable,
                    extnamespace::regnamespace AS schema
                FROM pg_extension
                WHERE extname IN ('pg_search', 'pg_analytics', 'paradedb')
                ORDER BY extname;
            """))
            
            extensions = result.fetchall()
            
            if not extensions:
                print("❌ ParadeDB 扩展未安装")
                print("\n安装方法:")
                print("  1. 使用 ParadeDB Docker 镜像:")
                print("     docker run -d --name paradedb -p 5432:5432 paradedb/paradedb:latest")
                print("\n  2. 或在 PostgreSQL 中手动安装:")
                print("     CREATE EXTENSION pg_search;")
            else:
                print("✅ ParadeDB 扩展已安装:\n")
                for ext_name, ext_version, relocatable, schema in extensions:
                    print(f"  • {ext_name}")
                    print(f"    版本: {ext_version}")
                    print(f"    Schema: {schema}")
                    print(f"    可重定位: {'是' if relocatable else '否'}")
                    print()
            
            # 2. 检查 BM25 索引
            print("-" * 80)
            print("2. BM25 索引检查")
            print("-" * 80)
            
            result = await conn.execute(text("""
                SELECT 
                    schemaname,
                    tablename,
                    indexname,
                    indexdef
                FROM pg_indexes
                WHERE tablename = 'document_chunks'
                    AND indexname = 'document_chunks_bm25_idx'
            """))
            
            bm25_index = result.fetchone()
            
            if not bm25_index:
                print("❌ BM25 索引不存在")
                print("\n创建方法:")
                print("  1. 启动应用（会自动创建）:")
                print("     python -m ragserver.main")
                print("\n  2. 或手动创建:")
                print("     CREATE INDEX document_chunks_bm25_idx")
                print("     ON document_chunks")
                print("     USING bm25 (id, content)")
                print("     WITH (key_field='id');")
            else:
                schema, table, index_name, index_def = bm25_index
                print(f"✅ BM25 索引已创建:\n")
                print(f"  索引名: {index_name}")
                print(f"  表名: {table}")
                print(f"  定义: {index_def}")
            
            # 3. 检查索引详细信息
            if bm25_index:
                print("\n" + "-" * 80)
                print("3. BM25 索引详细信息")
                print("-" * 80)
                
                result = await conn.execute(text("""
                    SELECT 
                        indexrelid::regclass AS index_name,
                        relname AS table_name,
                        pg_size_pretty(pg_relation_size(indexrelid)) AS index_size,
                        idx_scan AS scans,
                        idx_tup_read AS tuples_read,
                        idx_tup_fetch AS tuples_fetched
                    FROM pg_stat_user_indexes
                    WHERE indexrelname = 'document_chunks_bm25_idx';
                """))
                
                index_stats = result.fetchone()
                
                if index_stats:
                    index_name, table_name, size, scans, tuples_read, tuples_fetched = index_stats
                    print(f"\n  索引大小: {size}")
                    print(f"  扫描次数: {scans}")
                    print(f"  读取元组: {tuples_read}")
                    print(f"  获取元组: {tuples_fetched}")
            
            # 4. 测试 BM25 搜索功能
            if bm25_index and extensions:
                print("\n" + "-" * 80)
                print("4. BM25 搜索功能测试")
                print("-" * 80)
                
                # 检查是否有数据
                result = await conn.execute(text("""
                    SELECT COUNT(*) FROM document_chunks;
                """))
                chunk_count = result.scalar()
                
                print(f"\n  文档分块数量: {chunk_count}")
                
                if chunk_count > 0:
                    # 测试 BM25 搜索
                    try:
                        result = await conn.execute(text("""
                            SELECT 
                                id,
                                LEFT(content, 50) as content_preview,
                                paradedb.score(id) as score
                            FROM document_chunks
                            WHERE id @@@ paradedb.parse('test')
                            LIMIT 3;
                        """))
                        
                        search_results = result.fetchall()
                        
                        if search_results:
                            print("\n  ✅ BM25 搜索功能正常")
                            print("\n  测试搜索结果（查询: 'test'）:")
                            for doc_id, preview, score in search_results:
                                print(f"    • ID: {doc_id}")
                                print(f"      内容: {preview}...")
                                print(f"      分数: {score:.4f}")
                        else:
                            print("\n  ℹ️  BM25 搜索功能正常（无匹配结果）")
                    
                    except Exception as e:
                        print(f"\n  ❌ BM25 搜索测试失败: {e}")
                        print("  提示: 请检查 ParadeDB 扩展是否正确安装")
                else:
                    print("\n  ℹ️  数据库中没有文档分块，无法测试搜索")
            
            # 5. 检查 ParadeDB 函数
            print("\n" + "-" * 80)
            print("5. ParadeDB 函数检查")
            print("-" * 80)
            
            result = await conn.execute(text("""
                SELECT 
                    proname AS function_name,
                    pronargs AS arg_count,
                    pg_get_function_result(oid) AS return_type
                FROM pg_proc
                WHERE pronamespace = 'paradedb'::regnamespace
                    AND proname IN ('parse', 'score', 'rank', 'snippet')
                ORDER BY proname;
            """))
            
            functions = result.fetchall()
            
            if not functions:
                print("❌ ParadeDB 函数不可用")
            else:
                print("✅ ParadeDB 函数可用:\n")
                for func_name, arg_count, return_type in functions:
                    print(f"  • paradedb.{func_name}()")
                    print(f"    参数数量: {arg_count}")
                    print(f"    返回类型: {return_type}")
                    print()
            
            # 6. 推荐操作
            print("-" * 80)
            print("6. 状态总结")
            print("-" * 80)
            
            has_extension = len(extensions) > 0
            has_index = bm25_index is not None
            has_data = chunk_count > 0 if bm25_index and extensions else False
            
            if has_extension and has_index:
                print("\n✅ ParadeDB BM25 配置完整")
                if has_data:
                    print("✅ 已有数据，可以进行全文搜索")
                else:
                    print("ℹ️  数据库为空，上传文档后即可使用全文搜索")
            elif has_extension and not has_index:
                print("\n⚠️  ParadeDB 扩展已安装，但 BM25 索引未创建")
                print("\n推荐操作:")
                print("  1. 启动应用（会自动创建索引）:")
                print("     python -m ragserver.main")
            elif not has_extension:
                print("\n❌ ParadeDB 扩展未安装")
                print("\n推荐操作:")
                print("  1. 使用 ParadeDB Docker 镜像:")
                print("     docker-compose up -d postgres")
                print("\n  2. 或手动安装扩展:")
                print("     psql -U ragserver -d ragserver -c 'CREATE EXTENSION pg_search;'")
            
            print("\n" + "=" * 80)
            
    except Exception as e:
        print(f"\n❌ 检查失败: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        await async_engine.dispose()


if __name__ == "__main__":
    asyncio.run(check_paradedb_status())

