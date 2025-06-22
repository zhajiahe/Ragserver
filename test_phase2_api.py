#!/usr/bin/env python3
"""Test script for Phase 2 API functionality."""

import asyncio
import aiohttp
import json
import os
from pathlib import Path

# API配置
BASE_URL = "http://localhost:8080"
HEADERS = {"Content-Type": "application/json"}


async def test_phase2_functionality():
    """测试第二阶段功能"""
    
    async with aiohttp.ClientSession() as session:
        print("🚀 开始测试第二阶段功能...")
        
        # 1. 创建测试集合
        print("\n📁 创建测试集合...")
        collection_data = {
            "name": "Phase2测试集合",
            "description": "用于测试第二阶段功能的集合",
            "embedding_model": "bge-m3",
            "embedding_provider": "ollama"
        }
        
        async with session.post(f"{BASE_URL}/collections/", json=collection_data) as resp:
            if resp.status == 201:
                collection = await resp.json()
                collection_id = collection["id"]
                print(f"✅ 集合创建成功: {collection_id}")
            else:
                print(f"❌ 集合创建失败: {resp.status}")
                return
        
        # 2. 使用langgraph.txt作为测试文档
        print("\n📄 使用langgraph.txt作为测试文档...")
        
        test_file_path = "/Users/zhanghuaao/projects/RagBackend/datas/test.txt"
        
        # 3. 上传文件
        print("\n📤 上传测试文件...")
        data = aiohttp.FormData()
        data.add_field('file', open(test_file_path, 'rb'), filename='langgraph.txt', content_type='text/plain')
        
        async with session.post(f"{BASE_URL}/collections/{collection_id}/files", data=data) as resp:
            if resp.status == 201:
                file_response = await resp.json()
                file_id = file_response["id"]
                print(f"✅ 文件上传成功: {file_id}")
                print(f"   状态: {file_response['metadata']['status']}")
            else:
                error_text = await resp.text()
                print(f"❌ 文件上传失败: {resp.status}, {error_text}")
                return
        
        # 4. 等待文档处理完成
        print("\n⏳ 等待文档处理完成...")
        for i in range(30):  # 最多等待30秒
            await asyncio.sleep(1)
            
            async with session.get(f"{BASE_URL}/files/{file_id}") as resp:
                if resp.status == 200:
                    file_info = await resp.json()
                    status = file_info['metadata']['status']
                    print(f"   处理状态: {status}")
                    
                    if status == "completed":
                        print("✅ 文档处理完成!")
                        break
                    elif status == "failed":
                        print("❌ 文档处理失败!")
                        return
                else:
                    print(f"❌ 获取文件状态失败: {resp.status}")
                    return
        else:
            print("⏰ 文档处理超时")
            # 继续测试搜索功能
        
        # 5. 测试搜索功能
        print("\n🔍 测试搜索功能...")
        
        search_queries = [
            "什么是RAG系统？",
            "RAG的主要特点是什么？",
            "RAG有哪些应用场景？",
            "检索和生成"
        ]
        
        for query in search_queries:
            print(f"\n   查询: {query}")
            search_data = {
                "query": query,
                "limit": 5
            }
            
            async with session.post(f"{BASE_URL}/collections/{collection_id}/search", json=search_data) as resp:
                if resp.status == 200:
                    results = await resp.json()
                    print(f"   ✅ 找到 {len(results)} 个结果:")
                    
                    for i, result in enumerate(results[:3]):  # 只显示前3个结果
                        print(f"      {i+1}. 相似度: {result['score']:.3f}")
                        print(f"         内容: {result['page_content'][:100]}...")
                        print()
                else:
                    error_text = await resp.text()
                    print(f"   ❌ 搜索失败: {resp.status}, {error_text}")
        
        # 6. 获取集合统计信息
        print("\n📊 获取集合统计信息...")
        async with session.get(f"{BASE_URL}/collections/{collection_id}/stats") as resp:
            if resp.status == 200:
                stats = await resp.json()
                print("✅ 统计信息:")
                print(f"   总向量数: {stats['total_vectors']}")
                print(f"   文件数: {stats['unique_files']}")
                print(f"   嵌入模型: {stats['embedding_model']}")
                print(f"   提供商: {stats['embedding_provider']}")
            else:
                print(f"❌ 获取统计信息失败: {resp.status}")
        
        # 7. 获取集合文件列表
        print("\n📋 获取集合文件列表...")
        async with session.get(f"{BASE_URL}/collections/{collection_id}/files") as resp:
            if resp.status == 200:
                files = await resp.json()
                print(f"✅ 集合中有 {len(files)} 个文件:")
                for file in files:
                    print(f"   - {file['metadata']['filename']} ({file['metadata']['status']})")
            else:
                print(f"❌ 获取文件列表失败: {resp.status}")
        
        # 清理
        print("\n🧹 清理测试数据...")
        
        # 删除文件
        async with session.delete(f"{BASE_URL}/files/{file_id}") as resp:
            if resp.status == 204:
                print("✅ 测试文件删除成功")
            else:
                print(f"❌ 删除文件失败: {resp.status}")
        
        # 删除集合
        async with session.delete(f"{BASE_URL}/collections/{collection_id}") as resp:
            if resp.status == 204:
                print("✅ 测试集合删除成功")
            else:
                print(f"❌ 删除集合失败: {resp.status}")
        
        print("\n🎉 第二阶段功能测试完成!")


async def test_health_check():
    """测试健康检查"""
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{BASE_URL}/health") as resp:
            if resp.status == 200:
                health = await resp.json()
                print(f"✅ 服务健康状态: {health['status']}")
                return True
            else:
                print(f"❌ 健康检查失败: {resp.status}")
                return False


async def main():
    """主函数"""
    print("🔧 RagBackend Phase 2 API 测试工具")
    print("=" * 50)
    
    # 检查服务状态
    if not await test_health_check():
        print("❌ 服务不可用，请确保RagBackend正在运行")
        return
    
    # 运行功能测试
    await test_phase2_functionality()


if __name__ == "__main__":
    asyncio.run(main()) 