"""E2E测试：使用完整 example.txt 文件测试所有分块策略

测试完整的文档处理流程，包括：
1. 三种分块策略的对比
2. 实际大文件的处理性能
3. 块大小分布统计
"""

from pathlib import Path

import pytest

from ragserver.app.utils.chunkers import chunk_text

# 获取测试文件路径
TEST_FILE = Path(__file__).parent.parent / "example.txt"


class TestChunkersE2E:
    """End-to-End 分块器测试"""

    @pytest.mark.asyncio
    async def test_full_example_file(self):
        """测试完整的example.txt文件，对比三种分块策略"""
        # 读取完整文件
        with open(TEST_FILE, encoding="utf-8") as f:
            full_text = f.read()

        print(f"\n\n{'=' * 80}")
        print("E2E测试: 完整 example.txt 文件")
        print(f"{'=' * 80}")
        print(f"\n原始文件长度: {len(full_text):,} 字符")

        base_config = {"max_chunk_size": 800, "min_chunk_size": 100, "chunk_overlap": 200}

        # 测试三种策略
        strategies = [
            ("recursive", "递归字符分块", {}),
            ("bm25", "BM25语义分块", {"similarity_threshold": 0.3}),
            ("semantic", "向量语义分块", {"similarity_threshold": 0.7, "breakpoint_threshold_type": "percentile"}),
        ]

        all_results = {}

        for strategy_type, strategy_name, extra_config in strategies:
            print(f"\n{'-' * 80}")
            print(f"策略: {strategy_name} ({strategy_type})")
            print(f"{'-' * 80}")

            config = {"strategy_type": strategy_type, "config": {**base_config, **extra_config}}

            try:
                chunks = await chunk_text(full_text, config)

                # 统计信息
                chunk_sizes = [len(c["content"]) for c in chunks]
                total_chunks = len(chunks)
                avg_size = sum(chunk_sizes) / total_chunks if total_chunks > 0 else 0
                min_size = min(chunk_sizes) if chunk_sizes else 0
                max_size = max(chunk_sizes) if chunk_sizes else 0

                all_results[strategy_name] = {
                    "chunks": chunks,
                    "total": total_chunks,
                    "avg": avg_size,
                    "min": min_size,
                    "max": max_size,
                }

                print("\n📊 统计信息:")
                print(f"  总块数: {total_chunks}")
                print(f"  平均大小: {avg_size:.0f} 字符")
                print(f"  最小块: {min_size} 字符")
                print(f"  最大块: {max_size} 字符")

                # 验证最小块大小（除了最后一块）
                if strategy_type != "semantic":  # semantic chunker 可能因为 API 限制跳过
                    for i, chunk in enumerate(chunks[:-1]):  # 检查除最后一块外的所有块
                        content_len = len(chunk["content"].strip())
                        min_size = base_config["min_chunk_size"]
                        assert content_len >= min_size, (
                            f"{strategy_name}: 块 {i + 1} 小于最小大小 ({content_len} < {min_size})"
                        )

                # 打印前20个块
                print("\n📝 前20个块内容:")
                for i, chunk in enumerate(chunks[:20], 1):
                    content = chunk["content"]
                    preview = content[:100].replace("\n", " ").strip()
                    if len(content) > 100:
                        preview += "..."

                    print(f"\n  [{i:2d}] 大小: {len(content):4d} 字符")
                    print(f"       内容: {preview}")

                assert total_chunks > 0

            except Exception as e:
                print(f"\n❌ 错误: {str(e)}")
                if strategy_type != "semantic":
                    raise

        # 打印对比总结
        print(f"\n\n{'=' * 80}")
        print("分块策略对比总结")
        print(f"{'=' * 80}")
        print(f"\n原始文件: {len(full_text):,} 字符\n")

        for strategy_name, result in all_results.items():
            print(f"{strategy_name}:")
            print(f"  块数: {result['total']}")
            print(f"  平均: {result['avg']:.0f} 字符")
            print(f"  范围: {result['min']} ~ {result['max']} 字符")
            print()

    @pytest.mark.asyncio
    async def test_large_file_performance(self):
        """测试大文件处理性能"""
        with open(TEST_FILE, encoding="utf-8") as f:
            full_text = f.read()

        import time

        config = {
            "strategy_type": "recursive",
            "config": {"max_chunk_size": 800, "min_chunk_size": 100, "chunk_overlap": 200},
        }

        start_time = time.time()
        chunks = await chunk_text(full_text, config)
        elapsed = time.time() - start_time

        print("\n性能测试:")
        print(f"  文件大小: {len(full_text):,} 字符")
        print(f"  生成块数: {len(chunks)}")
        print(f"  耗时: {elapsed:.2f} 秒")
        print(f"  吞吐量: {len(full_text) / elapsed:.0f} 字符/秒")

        assert len(chunks) > 0
        assert elapsed < 5.0  # 应该在5秒内完成

    @pytest.mark.asyncio
    async def test_chunk_size_distribution(self):
        """测试块大小分布"""
        with open(TEST_FILE, encoding="utf-8") as f:
            full_text = f.read()

        config = {
            "strategy_type": "recursive",
            "config": {"max_chunk_size": 2000, "min_chunk_size": 400, "chunk_overlap": 400},
        }

        chunks = await chunk_text(full_text, config)
        chunk_sizes = [len(c["content"]) for c in chunks]

        # 计算分布
        min_size = min(chunk_sizes)
        max_size = max(chunk_sizes)
        avg_size = sum(chunk_sizes) / len(chunk_sizes)

        import statistics

        median_size = statistics.median(chunk_sizes)
        std_dev = statistics.stdev(chunk_sizes) if len(chunk_sizes) > 1 else 0

        print("\n块大小分布统计:")
        print(f"  总块数: {len(chunks)}")
        print(f"  最小块: {min_size} 字符")
        print(f"  最大块: {max_size} 字符")
        print(f"  平均值: {avg_size:.0f} 字符")
        print(f"  中位数: {median_size:.0f} 字符")
        print(f"  标准差: {std_dev:.0f} 字符")

        # 分桶统计
        bins = [0, 200, 400, 600, 800, 1000, 1500, float("inf")]
        bin_labels = ["0-200", "200-400", "400-600", "600-800", "800-1000", "1000-1500", "1500+"]
        bin_counts = [0] * len(bin_labels)

        for size in chunk_sizes:
            for i, (low, high) in enumerate(zip(bins[:-1], bins[1:])):
                if low <= size < high:
                    bin_counts[i] += 1
                    break

        print("\n块大小分布:")
        for label, count in zip(bin_labels, bin_counts):
            percentage = (count / len(chunks)) * 100
            bar = "█" * int(percentage / 2)
            print(f"  {label:12s}: {count:4d} ({percentage:5.1f}%) {bar}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
