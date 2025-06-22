#!/usr/bin/env python3
"""直接测试嵌入服务"""

import asyncio
import sys
import os

# 添加项目路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from ragbackend.services.embedding_service import get_embedding_service


async def test_embedding():
    """测试嵌入服务"""
    print("🧮 测试Ollama嵌入服务...")
    
    try:
        # 获取嵌入服务
        embedding_service = await get_embedding_service("ollama")
        
        # 测试文本
        test_texts = [
            "这是一个测试文档",
            "RAG系统测试",
            "向量化测试内容"
        ]
        
        print(f"模型名称: {embedding_service.model}")
        print(f"API地址: {embedding_service.base_url}")
        
        # 测试单个查询
        print("\n测试单个查询...")
        query_embedding = await embedding_service.embed_query(test_texts[0])
        print(f"✅ 单个查询成功，向量维度: {len(query_embedding)}")
        print(f"向量前5个值: {query_embedding[:5]}")
        
        # 测试批量处理
        print("\n测试批量处理...")
        batch_embeddings = await embedding_service.embed_texts(test_texts)
        print(f"✅ 批量处理成功，处理了 {len(batch_embeddings)} 个文本")
        
        for i, embedding in enumerate(batch_embeddings):
            print(f"   文本 {i+1}: 维度 {len(embedding)}, 前3个值: {embedding[:3]}")
        
        return True
        
    except Exception as e:
        print(f"❌ 嵌入服务测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """主函数"""
    print("🔧 嵌入服务直接测试")
    print("=" * 40)
    
    success = await test_embedding()
    
    if success:
        print("\n🎉 嵌入服务测试成功！")
    else:
        print("\n❌ 嵌入服务测试失败，请检查：")
        print("1. Ollama服务是否运行: ollama serve")
        print("2. bge-m3模型是否可用: ollama list")
        print("3. 网络连接是否正常")


if __name__ == "__main__":
    asyncio.run(main()) 