#!/usr/bin/env python3
"""RAG流水线诊断脚本"""

import asyncio
import aiohttp
import json
import os
import sys
from pathlib import Path

# 添加项目路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from ragbackend.services.embedding_service import get_embedding_service
from ragbackend.services.minio_service import get_minio_service
from ragbackend.config import OLLAMA_BASE_URL

BASE_URL = "http://localhost:8080"


async def test_ollama_connection():
    """测试Ollama连接"""
    print("🔍 测试Ollama连接...")
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{OLLAMA_BASE_URL}/api/tags") as resp:
                if resp.status == 200:
                    models = await resp.json()
                    print(f"✅ Ollama连接成功，可用模型: {[m['name'] for m in models.get('models', [])]}")
                    
                    # 检查bge-m3模型是否存在
                    model_names = [m['name'] for m in models.get('models', [])]
                    # 支持带版本号的模型名检查
                    bge_models = [name for name in model_names if name.startswith('bge-m3')]
                    if not bge_models:
                        print(f"⚠️ 警告：bge-m3模型未找到。请运行: ollama pull bge-m3")
                        return False
                    else:
                        print(f"✅ 找到bge-m3模型: {bge_models[0]}")
                    return True
                else:
                    print(f"❌ Ollama连接失败: HTTP {resp.status}")
                    return False
    except Exception as e:
        print(f"❌ Ollama连接错误: {e}")
        print(f"   请确保Ollama服务正在运行: {OLLAMA_BASE_URL}")
        return False


async def test_embedding_service():
    """测试嵌入服务"""
    print("\n🧮 测试嵌入服务...")
    try:
        embedding_service = await get_embedding_service("ollama")
        test_text = "这是一个测试文本"
        
        embedding = await embedding_service.embed_query(test_text)
        print(f"✅ 嵌入服务正常，向量维度: {len(embedding)}")
        return True
    except Exception as e:
        print(f"❌ 嵌入服务错误: {e}")
        return False


async def test_minio_connection():
    """测试MinIO连接"""
    print("\n📦 测试MinIO连接...")
    try:
        minio_service = get_minio_service()
        # 尝试列出bucket
        if minio_service.client.bucket_exists(minio_service.bucket_name):
            print(f"✅ MinIO连接成功，bucket '{minio_service.bucket_name}' 存在")
            return True
        else:
            print(f"❌ MinIO bucket '{minio_service.bucket_name}' 不存在")
            return False
    except Exception as e:
        print(f"❌ MinIO连接错误: {e}")
        return False


async def test_api_endpoints():
    """测试API端点"""
    print("\n🌐 测试API端点...")
    
    async with aiohttp.ClientSession() as session:
        # 健康检查
        try:
            async with session.get(f"{BASE_URL}/health") as resp:
                if resp.status == 200:
                    print("✅ API健康检查通过")
                else:
                    print(f"❌ API健康检查失败: {resp.status}")
                    return False
        except Exception as e:
            print(f"❌ API连接错误: {e}")
            return False
        
        # 检查集合列表
        try:
            async with session.get(f"{BASE_URL}/collections/") as resp:
                if resp.status == 200:
                    collections = await resp.json()
                    print(f"✅ 集合API正常，当前有 {len(collections)} 个集合")
                    return True
                else:
                    print(f"❌ 集合API错误: {resp.status}")
                    return False
        except Exception as e:
            print(f"❌ 集合API连接错误: {e}")
            return False


async def test_full_pipeline():
    """测试完整流水线"""
    print("\n🚀 测试完整RAG流水线...")
    
    async with aiohttp.ClientSession() as session:
        # 1. 创建测试集合
        print("   📁 创建测试集合...")
        collection_data = {
            "name": "诊断测试集合",
            "description": "用于诊断的测试集合",
            "embedding_model": "bge-m3",
            "embedding_provider": "ollama"
        }
        
        async with session.post(f"{BASE_URL}/collections/", json=collection_data) as resp:
            if resp.status == 201:
                collection = await resp.json()
                collection_id = collection["id"]
                print(f"   ✅ 集合创建成功: {collection_id}")
            else:
                error_text = await resp.text()
                print(f"   ❌ 集合创建失败: {resp.status}, {error_text}")
                return False
        
        # 2. 创建测试文档
        print("   📄 创建测试文档...")
        test_content = """
测试文档内容

这是一个用于测试RAG系统的简单文档。

主要内容：
1. 文档解析测试
2. 文本分块测试
3. 向量化测试
4. 搜索功能测试

这个文档应该能够被正确处理和索引。
        """
        
        test_file_path = "/tmp/debug_test_doc.txt"
        with open(test_file_path, "w", encoding="utf-8") as f:
            f.write(test_content)
        
        # 3. 上传文件
        print("   📤 上传测试文件...")
        data = aiohttp.FormData()
        data.add_field('file', open(test_file_path, 'rb'), 
                      filename='debug_test_doc.txt', content_type='text/plain')
        
        async with session.post(f"{BASE_URL}/collections/{collection_id}/files", data=data) as resp:
            if resp.status == 201:
                file_response = await resp.json()
                file_id = file_response["id"]
                print(f"   ✅ 文件上传成功: {file_id}")
            else:
                error_text = await resp.text()
                print(f"   ❌ 文件上传失败: {resp.status}, {error_text}")
                await cleanup_collection(session, collection_id)
                return False
        
        # 4. 等待文档处理
        print("   ⏳ 等待文档处理...")
        processing_success = False
        for i in range(60):  # 等待60秒
            await asyncio.sleep(1)
            
            async with session.get(f"{BASE_URL}/files/{file_id}") as resp:
                if resp.status == 200:
                    file_info = await resp.json()
                    status = file_info['metadata']['status']
                    
                    if i % 5 == 0:  # 每5秒打印一次状态
                        print(f"     状态: {status} ({i}s)")
                    
                    if status == "completed":
                        print("   ✅ 文档处理完成!")
                        processing_success = True
                        break
                    elif status == "failed":
                        print("   ❌ 文档处理失败!")
                        break
                else:
                    print(f"   ❌ 获取文件状态失败: {resp.status}")
                    break
        
        if not processing_success:
            print("   ⏰ 文档处理超时或失败")
            await cleanup_collection(session, collection_id)
            return False
        
        # 5. 检查向量数据
        print("   📊 检查向量数据...")
        async with session.get(f"{BASE_URL}/collections/{collection_id}/stats") as resp:
            if resp.status == 200:
                stats = await resp.json()
                total_vectors = stats['total_vectors']
                print(f"   ✅ 向量数据: {total_vectors} 个向量")
                
                if total_vectors == 0:
                    print("   ❌ 警告：没有向量数据生成")
                    await cleanup_collection(session, collection_id)
                    return False
            else:
                print(f"   ❌ 获取统计失败: {resp.status}")
                await cleanup_collection(session, collection_id)
                return False
        
        # 6. 测试搜索
        print("   🔍 测试搜索功能...")
        search_data = {
            "query": "测试文档",
            "limit": 5
        }
        
        async with session.post(f"{BASE_URL}/collections/{collection_id}/search", json=search_data) as resp:
            if resp.status == 200:
                results = await resp.json()
                print(f"   ✅ 搜索成功，找到 {len(results)} 个结果")
                
                if len(results) > 0:
                    print(f"     第一个结果相似度: {results[0]['score']:.3f}")
                    print(f"     内容片段: {results[0]['page_content'][:50]}...")
                else:
                    print("   ⚠️ 警告：搜索无结果")
            else:
                error_text = await resp.text()
                print(f"   ❌ 搜索失败: {resp.status}, {error_text}")
                await cleanup_collection(session, collection_id)
                return False
        
        # 7. 清理
        await cleanup_collection(session, collection_id)
        Path(test_file_path).unlink(missing_ok=True)
        
        return True


async def cleanup_collection(session, collection_id):
    """清理测试集合"""
    try:
        async with session.delete(f"{BASE_URL}/collections/{collection_id}") as resp:
            if resp.status == 204:
                print(f"   🧹 测试集合已清理: {collection_id}")
            else:
                print(f"   ⚠️ 清理集合失败: {resp.status}")
    except Exception as e:
        print(f"   ⚠️ 清理集合错误: {e}")


async def main():
    """主诊断流程"""
    print("🔧 RAG流水线诊断工具")
    print("=" * 50)
    
    # 检查各个组件
    components_ok = True
    
    # 1. Ollama连接
    if not await test_ollama_connection():
        components_ok = False
    
    # 2. 嵌入服务
    if components_ok and not await test_embedding_service():
        components_ok = False
    
    # 3. MinIO连接
    if not await test_minio_connection():
        components_ok = False
    
    # 4. API端点
    if not await test_api_endpoints():
        components_ok = False
    
    # 如果基础组件都正常，测试完整流水线
    if components_ok:
        print("\n✅ 基础组件检查通过，开始测试完整流水线...")
        if await test_full_pipeline():
            print("\n🎉 RAG流水线诊断完成，所有功能正常！")
        else:
            print("\n❌ RAG流水线存在问题，请检查日志")
    else:
        print("\n❌ 基础组件检查失败，请先解决这些问题：")
        print("   1. 确保Ollama服务运行: ollama serve")
        print("   2. 安装bge-m3模型: ollama pull bge-m3")
        print("   3. 确保MinIO服务运行: docker-compose up -d")
        print("   4. 确保RagBackend API运行: python ragbackend/main.py")


if __name__ == "__main__":
    asyncio.run(main()) 