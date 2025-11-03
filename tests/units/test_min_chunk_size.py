"""
测试 min_chunk_size 参数功能

验证所有分块器都正确支持最小块大小限制
"""
import pytest
from ragserver.app.utils.chunkers import (
    RecursiveCharacterChunker,
    Bm25TextChunker,
    ChunkerFactory,
    chunk_text,
)


@pytest.fixture
def test_text() -> str:
    """测试文本，包含一些短段落"""
    return """
第一段：这是一个很短的段落。

第二段：这是第二个段落，稍微长一点，但还是比较短。

第三段：这是第三个段落。

第四段：这个段落包含了更多的内容，用来测试分块器是否能够正确处理不同大小的文本块。我们希望这个段落能够被保留，因为它足够长。

第五段：短。

第六段：这是最后一个段落，用来测试边界情况。
"""


class TestMinChunkSize:
    """测试最小块大小参数"""

    @pytest.mark.asyncio
    async def test_recursive_chunker_min_size(self, test_text: str):
        """测试递归分块器的最小块大小"""
        min_size = 50
        
        chunker = RecursiveCharacterChunker(
            chunk_size=500,
            chunk_overlap=50,
            min_chunk_size=min_size
        )
        
        chunks = await chunker.split_text(test_text)
        
        print(f"\n递归分块器 (min_chunk_size={min_size}):")
        print(f"  总块数: {len(chunks)}")
        
        # 验证所有块（除了可能的最后一块）都满足最小大小要求
        for i, chunk in enumerate(chunks):
            content_len = len(chunk["content"].strip())
            print(f"  块 {i+1}: {content_len} 字符")
            
            # 最后一块可以小于最小大小
            if i < len(chunks) - 1:
                assert content_len >= min_size, f"块 {i+1} 太小: {content_len} < {min_size}"
        
        assert len(chunks) > 0

    @pytest.mark.asyncio
    async def test_bm25_chunker_min_size(self, test_text: str):
        """测试BM25分块器的最小块大小"""
        min_size = 50
        
        chunker = Bm25TextChunker(
            chunk_size=500,
            chunk_overlap=50,
            min_chunk_size=min_size,
            similarity_threshold=0.3
        )
        
        chunks = await chunker.split_text(test_text)
        
        print(f"\nBM25分块器 (min_chunk_size={min_size}):")
        print(f"  总块数: {len(chunks)}")
        
        for i, chunk in enumerate(chunks):
            content_len = len(chunk["content"].strip())
            print(f"  块 {i+1}: {content_len} 字符")
            
            # 最后一块可以小于最小大小
            if i < len(chunks) - 1:
                assert content_len >= min_size, f"块 {i+1} 太小: {content_len} < {min_size}"
        
        assert len(chunks) > 0

    @pytest.mark.asyncio
    async def test_factory_min_size(self, test_text: str):
        """测试工厂方法创建的分块器支持最小块大小"""
        min_size = 60
        
        config = {
            "strategy_type": "recursive",
            "config": {
                "max_chunk_size": 500,
                "chunk_overlap": 50,
                "min_chunk_size": min_size
            }
        }
        
        chunks = await chunk_text(test_text, config)
        
        print(f"\n工厂方法 - 递归分块 (min_chunk_size={min_size}):")
        print(f"  总块数: {len(chunks)}")
        
        for i, chunk in enumerate(chunks):
            content_len = len(chunk["content"].strip())
            print(f"  块 {i+1}: {content_len} 字符 - {chunk['content'].strip()[:50]}...")
            
            # 最后一块可以小于最小大小
            if i < len(chunks) - 1:
                assert content_len >= min_size, f"块 {i+1} 太小: {content_len} < {min_size}"
        
        assert len(chunks) > 0

    @pytest.mark.asyncio
    async def test_different_min_sizes(self):
        """测试不同的最小块大小配置"""
        text = "短。\n\n中等长度的段落。\n\n这是一个更长的段落，包含了足够多的文本内容。"
        
        min_sizes = [10, 20, 30, 50]
        
        print(f"\n测试不同的 min_chunk_size 配置:")
        print(f"原始文本长度: {len(text)} 字符\n")
        
        for min_size in min_sizes:
            chunker = RecursiveCharacterChunker(
                chunk_size=200,
                chunk_overlap=20,
                min_chunk_size=min_size
            )
            
            chunks = await chunker.split_text(text)
            
            print(f"min_chunk_size={min_size}:")
            print(f"  块数: {len(chunks)}")
            
            for i, chunk in enumerate(chunks):
                content_len = len(chunk["content"].strip())
                print(f"    块 {i+1}: {content_len} 字符")
            print()
            
            assert len(chunks) > 0

    @pytest.mark.asyncio
    async def test_min_size_with_very_small_text(self):
        """测试当文本本身小于最小块大小时的行为"""
        small_text = "很小的文本"
        min_size = 100
        
        chunker = RecursiveCharacterChunker(
            chunk_size=500,
            chunk_overlap=50,
            min_chunk_size=min_size
        )
        
        chunks = await chunker.split_text(small_text)
        
        print(f"\n极小文本测试 (文本: {len(small_text)} 字符, min_size: {min_size}):")
        print(f"  块数: {len(chunks)}")
        print(f"  块内容: '{chunks[0]['content']}'")
        
        # 即使小于最小大小，也应该返回至少一个块
        assert len(chunks) == 1
        assert chunks[0]["content"] == small_text

    @pytest.mark.asyncio
    async def test_all_strategies_support_min_size(self):
        """测试所有策略都支持 min_chunk_size"""
        text = """
段落1：短文本。

段落2：这是一个中等长度的段落，用于测试。

段落3：这是一个更长的段落，包含了更多的文本内容，确保它不会被过滤掉。

段落4：短。

段落5：最后一个测试段落。
"""
        
        strategies = [
            ("recursive", "递归字符分块", {}),
            ("bm25", "BM25语义分块", {"similarity_threshold": 0.3}),
        ]
        
        min_size = 40
        
        print(f"\n测试所有策略支持 min_chunk_size={min_size}:")
        
        for strategy_type, strategy_name, extra_config in strategies:
            config = {
                "strategy_type": strategy_type,
                "config": {
                    "max_chunk_size": 500,
                    "chunk_overlap": 50,
                    "min_chunk_size": min_size,
                    **extra_config
                }
            }
            
            chunks = await chunk_text(text, config)
            
            print(f"\n{strategy_name}:")
            print(f"  块数: {len(chunks)}")
            
            for i, chunk in enumerate(chunks):
                content_len = len(chunk["content"].strip())
                print(f"    块 {i+1}: {content_len} 字符")
                
                # 验证（除了最后一块）都满足最小大小
                if i < len(chunks) - 1:
                    assert content_len >= min_size, \
                        f"{strategy_name} - 块 {i+1} 太小: {content_len} < {min_size}"
            
            assert len(chunks) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])

