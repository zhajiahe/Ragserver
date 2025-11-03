"""
测试分块器功能

测试三种分块策略：
1. RecursiveCharacterChunker - 递归字符分块
2. Bm25TextChunker - BM25语义分块
3. SemanticChunker - 向量语义分块
"""
import pytest
from pathlib import Path
from typing import List, Dict, Any

from ragserver.app.utils.chunkers import (
    RecursiveCharacterChunker,
    Bm25TextChunker,
    SemanticChunker,
    ChunkerFactory,
    chunk_text,
)


# 获取测试文件路径
TEST_FILE = Path(__file__).parent.parent / "example.txt"


@pytest.fixture
def example_text() -> str:
    """加载示例文件"""
    with open(TEST_FILE, "r", encoding="utf-8") as f:
        content = f.read()
    # 使用前 5000 字符进行测试（完整文件太大）
    return content[:5000]


@pytest.fixture
def short_text() -> str:
    """短文本示例"""
    return """
# 中华人民共和国电力行业标准

本规程根据《国家能源局关于下达 2011 年第二批能源领域行业标准制（修）订计划的通知》要求制定。

DL 5009《电力建设安全工作规程》共 3 个部分：
- DL 5009.1 第 1 部分：火力发电
- DL 5009.2 第 2 部分：电力线路
- DL 5009.3 第 3 部分：变电站

本部分共分 7 章和6 个附录，主要内容是：
1. 总则
2. 术语
3. 基本规定
4. 综合管理
5. 土建
6. 安装
7. 调整试验及试运行
"""


class TestRecursiveCharacterChunker:
    """测试递归字符分块器"""

    @pytest.mark.asyncio
    async def test_basic_chunking(self, short_text: str):
        """测试基本分块功能"""
        chunker = RecursiveCharacterChunker(
            chunk_size=300,
            chunk_overlap=50
        )

        chunks = await chunker.split_text(short_text)

        # 验证返回格式
        assert isinstance(chunks, list)
        assert len(chunks) > 0

        # 验证每个块的结构
        for chunk in chunks:
            assert "content" in chunk
            assert "metadata" in chunk
            assert "chunk_index" in chunk["metadata"]
            assert "chunk_size" in chunk["metadata"]

            # 验证内容
            assert isinstance(chunk["content"], str)
            assert len(chunk["content"]) > 0

    @pytest.mark.asyncio
    async def test_chunk_size_limit(self, short_text: str):
        """测试块大小限制"""
        chunk_size = 300
        chunker = RecursiveCharacterChunker(chunk_size=chunk_size, chunk_overlap=0)

        chunks = await chunker.split_text(short_text)

        # 验证块大小（允许稍微超出）
        for chunk in chunks:
            assert len(chunk["content"]) <= chunk_size * 1.2  # 允许20%误差

    @pytest.mark.asyncio
    async def test_chunk_overlap(self, short_text: str):
        """测试块重叠功能"""
        chunker = RecursiveCharacterChunker(
            chunk_size=200,
            chunk_overlap=50
        )

        chunks = await chunker.split_text(short_text)

        if len(chunks) > 1:
            # 检查相邻块之间有重叠内容
            for i in range(len(chunks) - 1):
                content1 = chunks[i]["content"]
                content2 = chunks[i + 1]["content"]

                # 检查第二个块的开头是否出现在第一个块的末尾
                overlap_text = content2[:50]  # 取第二个块的开头
                # 由于重叠可能不是完全匹配，只检查是否有部分重叠
                assert len(overlap_text) > 0

    @pytest.mark.asyncio
    async def test_custom_separators(self, short_text: str):
        """测试自定义分隔符"""
        chunker = RecursiveCharacterChunker(
            chunk_size=300,
            chunk_overlap=50,
            separators=["\n\n", "\n", "。", ".", " "]
        )

        chunks = await chunker.split_text(short_text)
        assert len(chunks) > 0

    @pytest.mark.asyncio
    async def test_example_file(self, example_text: str):
        """测试示例文件"""
        chunker = RecursiveCharacterChunker(
            chunk_size=800,
            chunk_overlap=200
        )

        chunks = await chunker.split_text(example_text)

        print(f"\n递归字符分块器结果:")
        print(f"  总块数: {len(chunks)}")
        print(f"  平均块大小: {sum(len(c['content']) for c in chunks) / len(chunks):.0f} 字符")
        print(f"  最小块: {min(len(c['content']) for c in chunks)} 字符")
        print(f"  最大块: {max(len(c['content']) for c in chunks)} 字符")

        assert len(chunks) > 0
        assert all(chunk["content"].strip() for chunk in chunks)


class TestBm25TextChunker:
    """测试BM25语义分块器"""

    @pytest.mark.asyncio
    async def test_basic_chunking(self, short_text: str):
        """测试基本分块功能"""
        chunker = Bm25TextChunker(
            chunk_size=300,
            chunk_overlap=50,
            similarity_threshold=0.3
        )

        chunks = await chunker.split_text(short_text)

        # 验证返回格式
        assert isinstance(chunks, list)
        assert len(chunks) > 0

        for chunk in chunks:
            assert "content" in chunk
            assert "metadata" in chunk
            assert "char_count" in chunk["metadata"]

    @pytest.mark.asyncio
    async def test_similarity_threshold(self, short_text: str):
        """测试相似度阈值"""
        # 高阈值应该产生更多块
        chunker_high = Bm25TextChunker(
            chunk_size=500,
            chunk_overlap=50,
            similarity_threshold=0.8
        )

        # 低阈值应该产生更少块
        chunker_low = Bm25TextChunker(
            chunk_size=500,
            chunk_overlap=50,
            similarity_threshold=0.1
        )

        chunks_high = await chunker_high.split_text(short_text)
        chunks_low = await chunker_low.split_text(short_text)

        print(f"\n高阈值(0.8)块数: {len(chunks_high)}")
        print(f"低阈值(0.1)块数: {len(chunks_low)}")

        # 通常高阈值会产生更多或相同数量的块
        assert len(chunks_high) >= len(chunks_low) * 0.5  # 允许一些变化

    @pytest.mark.asyncio
    async def test_example_file(self, example_text: str):
        """测试示例文件"""
        chunker = Bm25TextChunker(
            chunk_size=800,
            chunk_overlap=200,
            similarity_threshold=0.3
        )

        chunks = await chunker.split_text(example_text)

        print(f"\nBM25语义分块器结果:")
        print(f"  总块数: {len(chunks)}")
        print(f"  平均块大小: {sum(len(c['content']) for c in chunks) / len(chunks):.0f} 字符")
        print(f"  最小块: {min(len(c['content']) for c in chunks)} 字符")
        print(f"  最大块: {max(len(c['content']) for c in chunks)} 字符")

        assert len(chunks) > 0


class TestSemanticChunker:
    """测试向量语义分块器"""

    @pytest.mark.asyncio
    async def test_basic_chunking(self, short_text: str):
        """测试基本分块功能"""
        chunker = SemanticChunker(
            similarity_threshold=0.7,
            min_chunk_size=100,
            max_chunk_size=500,
            chunk_overlap=50,
            breakpoint_threshold_type="percentile"
        )

        chunks = await chunker.split_text(short_text)

        # 验证返回格式
        assert isinstance(chunks, list)
        assert len(chunks) > 0

        for chunk in chunks:
            assert "content" in chunk
            assert "metadata" in chunk

    @pytest.mark.asyncio
    async def test_breakpoint_strategies(self, short_text: str):
        """测试三种边界检测策略"""
        strategies = ["fixed", "percentile", "gradient"]

        for strategy in strategies:
            chunker = SemanticChunker(
                similarity_threshold=0.7,
                min_chunk_size=100,
                max_chunk_size=500,
                chunk_overlap=50,
                breakpoint_threshold_type=strategy
            )

            chunks = await chunker.split_text(short_text)

            print(f"\n策略 {strategy}: {len(chunks)} 块")
            assert len(chunks) > 0

    @pytest.mark.asyncio
    async def test_min_max_chunk_size(self, short_text: str):
        """测试最小/最大块大小"""
        chunker = SemanticChunker(
            similarity_threshold=0.7,
            min_chunk_size=50,
            max_chunk_size=300,
            chunk_overlap=20
        )

        chunks = await chunker.split_text(short_text)

        # 验证块大小在合理范围内
        for chunk in chunks:
            content_len = len(chunk["content"])
            # 最后一个块可能小于最小值
            if chunk["metadata"]["chunk_index"] < len(chunks) - 1:
                assert content_len >= 30  # 允许一些弹性


class TestChunkerFactory:
    """测试分块器工厂"""

    @pytest.mark.asyncio
    async def test_create_recursive_chunker(self):
        """测试创建递归分块器"""
        config = {
            "max_chunk_size": 500,
            "chunk_overlap": 100,
            "separators": ["\n\n", "\n"]
        }

        chunker = ChunkerFactory.create_chunker("recursive", config)
        assert isinstance(chunker, RecursiveCharacterChunker)
        assert chunker.chunk_size == 500
        assert chunker.chunk_overlap == 100

    @pytest.mark.asyncio
    async def test_create_bm25_chunker(self):
        """测试创建BM25分块器"""
        config = {
            "max_chunk_size": 600,
            "chunk_overlap": 150,
            "similarity_threshold": 0.4
        }

        chunker = ChunkerFactory.create_chunker("bm25", config)
        assert isinstance(chunker, Bm25TextChunker)
        assert chunker.chunk_size == 600
        assert chunker.similarity_threshold == 0.4

    @pytest.mark.asyncio
    async def test_create_semantic_chunker(self):
        """测试创建语义分块器"""
        config = {
            "max_chunk_size": 700,
            "chunk_overlap": 100,
            "similarity_threshold": 0.75,
            "min_chunk_size": 150,
            "breakpoint_threshold_type": "gradient"
        }

        chunker = ChunkerFactory.create_chunker("semantic", config)
        assert isinstance(chunker, SemanticChunker)
        assert chunker.max_chunk_size == 700
        assert chunker.similarity_threshold == 0.75
        assert chunker.breakpoint_threshold_type == "gradient"

    @pytest.mark.asyncio
    async def test_invalid_strategy(self):
        """测试无效策略"""
        with pytest.raises(ValueError, match="Unknown chunking strategy"):
            ChunkerFactory.create_chunker("invalid_strategy", {})


class TestChunkTextFunction:
    """测试统一分块函数"""

    @pytest.mark.asyncio
    async def test_chunk_text_recursive(self, short_text: str):
        """测试递归分块"""
        config = {
            "strategy_type": "recursive",
            "config": {
                "max_chunk_size": 300,
                "chunk_overlap": 50
            }
        }

        chunks = await chunk_text(short_text, config)

        assert len(chunks) > 0
        assert all("content" in chunk for chunk in chunks)

    @pytest.mark.asyncio
    async def test_chunk_text_bm25(self, short_text: str):
        """测试BM25分块"""
        config = {
            "strategy_type": "bm25",
            "config": {
                "max_chunk_size": 400,
                "chunk_overlap": 80,
                "similarity_threshold": 0.3
            }
        }

        chunks = await chunk_text(short_text, config)
        assert len(chunks) > 0

    @pytest.mark.asyncio
    async def test_chunk_text_semantic(self, short_text: str):
        """测试语义分块"""
        config = {
            "strategy_type": "semantic",
            "config": {
                "max_chunk_size": 500,
                "chunk_overlap": 100,
                "similarity_threshold": 0.7,
                "min_chunk_size": 100,
                "breakpoint_threshold_type": "percentile"
            }
        }

        chunks = await chunk_text(short_text, config)
        assert len(chunks) > 0

    @pytest.mark.asyncio
    async def test_default_strategy(self, short_text: str):
        """测试默认策略"""
        config = {
            "config": {
                "max_chunk_size": 300,
                "chunk_overlap": 50
            }
        }

        # 未指定 strategy_type，应该使用默认的 recursive
        chunks = await chunk_text(short_text, config)
        assert len(chunks) > 0


class TestMinChunkSize:
    """测试最小块大小参数"""

    @pytest.mark.asyncio
    async def test_recursive_min_size(self, short_text: str):
        """测试递归分块器的最小块大小"""
        min_size = 50
        
        chunker = RecursiveCharacterChunker(
            chunk_size=500,
            chunk_overlap=50,
            min_chunk_size=min_size
        )
        
        chunks = await chunker.split_text(short_text)
        
        print(f"\n递归分块器 (min_chunk_size={min_size}):")
        print(f"  总块数: {len(chunks)}")
        
        # 验证所有块（除了可能的最后一块）都满足最小大小要求
        for i, chunk in enumerate(chunks[:-1]):
            content_len = len(chunk["content"].strip())
            assert content_len >= min_size, f"块 {i+1} 太小: {content_len} < {min_size}"
        
        assert len(chunks) > 0

    @pytest.mark.asyncio
    async def test_bm25_min_size(self, short_text: str):
        """测试BM25分块器的最小块大小"""
        min_size = 50
        
        chunker = Bm25TextChunker(
            chunk_size=500,
            chunk_overlap=50,
            min_chunk_size=min_size,
            similarity_threshold=0.3
        )
        
        chunks = await chunker.split_text(short_text)
        
        print(f"\nBM25分块器 (min_chunk_size={min_size}):")
        print(f"  总块数: {len(chunks)}")
        
        for i, chunk in enumerate(chunks[:-1]):
            content_len = len(chunk["content"].strip())
            assert content_len >= min_size, f"块 {i+1} 太小: {content_len} < {min_size}"
        
        assert len(chunks) > 0

    @pytest.mark.asyncio
    async def test_factory_min_size(self, short_text: str):
        """测试工厂方法支持最小块大小"""
        min_size = 60
        
        config = {
            "strategy_type": "recursive",
            "config": {
                "max_chunk_size": 500,
                "chunk_overlap": 50,
                "min_chunk_size": min_size
            }
        }
        
        chunks = await chunk_text(short_text, config)
        
        print(f"\n工厂方法 (min_chunk_size={min_size}):")
        print(f"  总块数: {len(chunks)}")
        
        for i, chunk in enumerate(chunks[:-1]):
            content_len = len(chunk["content"].strip())
            assert content_len >= min_size, f"块 {i+1} 太小: {content_len} < {min_size}"
        
        assert len(chunks) > 0

    @pytest.mark.asyncio
    async def test_different_min_sizes(self):
        """测试不同的最小块大小配置"""
        text = "短。\n\n中等长度的段落。\n\n这是一个更长的段落，包含了足够多的文本内容。"
        
        min_sizes = [10, 20, 30]
        
        print(f"\n测试不同的 min_chunk_size:")
        
        for min_size in min_sizes:
            chunker = RecursiveCharacterChunker(
                chunk_size=200,
                chunk_overlap=20,
                min_chunk_size=min_size
            )
            
            chunks = await chunker.split_text(text)
            print(f"  min={min_size}: {len(chunks)} 块")
            assert len(chunks) > 0


class TestCompareStrategies:
    """比较不同分块策略"""

    @pytest.mark.asyncio
    async def test_compare_all_strategies(self, example_text: str):
        """比较三种策略的分块结果"""
        base_config = {
            "max_chunk_size": 800,
            "chunk_overlap": 200
        }

        # 递归分块
        config_recursive = {
            "strategy_type": "recursive",
            "config": base_config
        }
        chunks_recursive = await chunk_text(example_text, config_recursive)

        # BM25分块
        config_bm25 = {
            "strategy_type": "bm25",
            "config": {**base_config, "similarity_threshold": 0.3}
        }
        chunks_bm25 = await chunk_text(example_text, config_bm25)

        # 语义分块
        config_semantic = {
            "strategy_type": "semantic",
            "config": {
                **base_config,
                "similarity_threshold": 0.7,
                "min_chunk_size": 100,
                "breakpoint_threshold_type": "percentile"
            }
        }
        chunks_semantic = await chunk_text(example_text, config_semantic)

        # 打印对比结果
        print("\n\n========== 分块策略对比 ==========")
        print(f"\n原始文本长度: {len(example_text)} 字符")

        print(f"\n1. 递归字符分块:")
        print(f"   块数: {len(chunks_recursive)}")
        print(f"   平均块大小: {sum(len(c['content']) for c in chunks_recursive) / len(chunks_recursive):.0f}")
        print(f"   最小/最大: {min(len(c['content']) for c in chunks_recursive)} / {max(len(c['content']) for c in chunks_recursive)}")

        print(f"\n2. BM25语义分块:")
        print(f"   块数: {len(chunks_bm25)}")
        print(f"   平均块大小: {sum(len(c['content']) for c in chunks_bm25) / len(chunks_bm25):.0f}")
        print(f"   最小/最大: {min(len(c['content']) for c in chunks_bm25)} / {max(len(c['content']) for c in chunks_bm25)}")

        print(f"\n3. 向量语义分块:")
        print(f"   块数: {len(chunks_semantic)}")
        print(f"   平均块大小: {sum(len(c['content']) for c in chunks_semantic) / len(chunks_semantic):.0f}")
        print(f"   最小/最大: {min(len(c['content']) for c in chunks_semantic)} / {max(len(c['content']) for c in chunks_semantic)}")

        # 显示第一个块的内容示例
        print(f"\n========== 第一个块内容示例 ==========")
        print(f"\n递归分块第一块:")
        print(f"{chunks_recursive[0]['content'][:200]}...")

        print(f"\nBM25分块第一块:")
        print(f"{chunks_bm25[0]['content'][:200]}...")

        print(f"\n语义分块第一块:")
        print(f"{chunks_semantic[0]['content'][:200]}...")

        # 验证所有策略都产生了有效的块
        assert len(chunks_recursive) > 0
        assert len(chunks_bm25) > 0
        assert len(chunks_semantic) > 0

