"""文档解析器使用示例

演示如何使用 ragserver.app.utils.parsers 模块解析各种类型的文档
"""

import asyncio
from pathlib import Path

from loguru import logger

from ragserver.app.utils.parsers import (
    DocumentParserFactory,
    get_supported_file_types,
    is_supported_file_type,
    parse_document,
)

# ==================== 基础示例 ====================


async def example_1_basic_usage():
    """示例1：基本用法"""
    logger.info("=" * 50)
    logger.info("示例1：基本用法")
    logger.info("=" * 50)

    # 创建一个简单的文本文件
    text_content = b"Hello World!\n\nThis is a test document."

    # 解析文本文件
    result = await parse_document(file_content=text_content, file_type="txt", filename="test.txt")

    logger.info(f"解析结果:\n{result}")
    return result


async def example_2_check_supported_types():
    """示例2：检查支持的文件类型"""
    logger.info("=" * 50)
    logger.info("示例2：检查支持的文件类型")
    logger.info("=" * 50)

    # 获取所有支持的文件类型
    supported_types = get_supported_file_types()
    logger.info(f"支持的文件类型: {', '.join(supported_types)}")

    # 检查特定类型是否支持
    test_types = ["pdf", "docx", "xyz", "txt"]
    for file_type in test_types:
        is_supported = is_supported_file_type(file_type)
        status = "✓" if is_supported else "✗"
        logger.info(f"{status} {file_type}: {is_supported}")


async def example_3_parse_markdown():
    """示例3：解析 Markdown 文件"""
    logger.info("=" * 50)
    logger.info("示例3：解析 Markdown 文件")
    logger.info("=" * 50)

    markdown_content = """# 标题

## 二级标题

这是一段文本，包含 **粗体** 和 *斜体*。

### 三级标题

- 列表项 1
- 列表项 2
- 列表项 3

```python
def hello():
    print("Hello World")
```
""".encode()

    result = await parse_document(file_content=markdown_content, file_type="md", filename="example.md")

    logger.info(f"Markdown 解析结果:\n{result}")
    return result


async def example_4_parse_html():
    """示例4：解析 HTML 文件"""
    logger.info("=" * 50)
    logger.info("示例4：解析 HTML 文件")
    logger.info("=" * 50)

    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>测试页面</title>
        <script>console.log('这段不应该被解析');</script>
    </head>
    <body>
        <h1>主标题</h1>
        <h2>副标题</h2>
        <p>这是一段正文。</p>
        <a href="https://example.com">链接文本</a>
        <ul>
            <li>列表项 1</li>
            <li>列表项 2</li>
        </ul>
    </body>
    </html>
    """.encode()

    result = await parse_document(
        file_content=html_content, file_type="html", filename="example.html", preserve_links=True
    )

    logger.info(f"HTML 解析结果:\n{result}")
    return result


async def example_5_parse_csv():
    """示例5：解析 CSV 文件"""
    logger.info("=" * 50)
    logger.info("示例5：解析 CSV 文件")
    logger.info("=" * 50)

    csv_content = b"""Name,Age,City,Salary
Alice,30,New York,75000
Bob,25,Los Angeles,65000
Charlie,35,Chicago,80000
Diana,28,Houston,70000"""

    result = await parse_document(file_content=csv_content, file_type="csv", filename="employees.csv")

    logger.info(f"CSV 解析结果:\n{result}")
    return result


# ==================== 高级示例 ====================


async def example_6_batch_parsing():
    """示例6：批量解析多个文档"""
    logger.info("=" * 50)
    logger.info("示例6：批量解析多个文档")
    logger.info("=" * 50)

    # 模拟多个文档
    documents = [
        (b"Text document 1", "txt", "doc1.txt"),
        (b"# Markdown document", "md", "doc2.md"),
        (b"<html><body>HTML doc</body></html>", "html", "doc3.html"),
    ]

    # 并行解析
    tasks = [parse_document(content, file_type, filename) for content, file_type, filename in documents]

    results = await asyncio.gather(*tasks)

    for (_, _, filename), result in zip(documents, results):
        logger.info(f"✓ {filename}: {len(result)} 字符")

    return results


async def example_7_error_handling():
    """示例7：错误处理"""
    logger.info("=" * 50)
    logger.info("示例7：错误处理")
    logger.info("=" * 50)

    # 测试不支持的文件类型
    try:
        await parse_document(file_content=b"content", file_type="unsupported", filename="test.unsupported")
    except ValueError as e:
        logger.error(f"预期的错误: {e}")

    # 测试空内容
    try:
        await parse_document(file_content=b"", file_type="txt", filename="empty.txt")
    except ValueError as e:
        logger.error(f"预期的错误: {e}")

    logger.info("错误处理测试完成")


async def example_8_using_factory():
    """示例8：使用解析器工厂"""
    logger.info("=" * 50)
    logger.info("示例8：使用解析器工厂")
    logger.info("=" * 50)

    # 直接获取解析器
    parser = DocumentParserFactory.get_parser("txt")
    logger.info(f"获取到的解析器: {parser.__class__.__name__}")

    # 使用解析器
    content = b"Using parser factory"
    result = await parser.parse(content, "example.txt")
    logger.info(f"解析结果: {result}")

    # 查看所有解析器映射
    logger.info("\n所有注册的解析器:")
    for file_type, parser_class in DocumentParserFactory.PARSER_MAP.items():
        logger.info(f"  {file_type:10s} -> {parser_class.__name__}")


async def example_9_encoding_detection():
    """示例9：编码自动检测"""
    logger.info("=" * 50)
    logger.info("示例9：编码自动检测")
    logger.info("=" * 50)

    # UTF-8 编码
    utf8_content = "你好，世界！".encode()
    result1 = await parse_document(utf8_content, "txt", "utf8.txt")
    logger.info(f"UTF-8 解析: {result1}")

    # GBK 编码
    gbk_content = "你好，世界！".encode("gbk")
    result2 = await parse_document(gbk_content, "txt", "gbk.txt")
    logger.info(f"GBK 解析: {result2}")

    # 验证结果一致
    assert result1 == result2
    logger.info("✓ 编码自动检测成功！")


async def example_10_performance_test():
    """示例10：性能测试"""
    logger.info("=" * 50)
    logger.info("示例10：性能测试")
    logger.info("=" * 50)

    import time

    # 生成大文本（约 1MB）
    large_text = ("This is a test line with some content.\n" * 10000).encode("utf-8")
    logger.info(f"测试文本大小: {len(large_text) / 1024 / 1024:.2f} MB")

    # 串行解析（5次）
    start_time = time.time()
    for i in range(5):
        await parse_document(large_text, "txt", f"large_{i}.txt")
    serial_time = time.time() - start_time
    logger.info(f"串行解析 5 次耗时: {serial_time:.4f} 秒")

    # 并行解析（5次）
    start_time = time.time()
    tasks = [parse_document(large_text, "txt", f"large_{i}.txt") for i in range(5)]
    await asyncio.gather(*tasks)
    parallel_time = time.time() - start_time
    logger.info(f"并行解析 5 次耗时: {parallel_time:.4f} 秒")

    speedup = serial_time / parallel_time
    logger.info(f"加速比: {speedup:.2f}x")


# ==================== PDF 相关示例（需要实际文件）====================


async def example_11_pdf_text_extraction():
    """示例11：PDF 文本提取（需要实际 PDF 文件）"""
    logger.info("=" * 50)
    logger.info("示例11：PDF 文本提取")
    logger.info("=" * 50)

    logger.info("此示例需要实际的 PDF 文件")
    logger.info("使用方法:")
    logger.info("""
    with open("example.pdf", "rb") as f:
        content = f.read()
    
    # 标准文本提取
    result = await parse_document(content, "pdf", "example.pdf")
    
    # 使用 OCR（扫描版）
    result = await parse_document(
        content, 
        "pdf", 
        "scanned.pdf",
        use_ocr=True,
        ocr_config={
            'dpi': 144,
            'max_concurrent': 30
        }
    )
    """)


async def example_12_image_ocr():
    """示例12：图片 OCR 解析（需要实际图片）"""
    logger.info("=" * 50)
    logger.info("示例12：图片 OCR 解析")
    logger.info("=" * 50)

    logger.info("此示例需要实际的图片文件")
    logger.info("使用方法:")
    logger.info("""
    with open("screenshot.png", "rb") as f:
        content = f.read()
    
    result = await parse_document(
        content, 
        "png", 
        "screenshot.png",
        ocr_config={
            'model': 'deepseek-ai/DeepSeek-OCR',
            'max_concurrent': 30
        }
    )
    print(result)
    """)


# ==================== 实用工具函数 ====================


async def parse_file_from_path(file_path: str, **kwargs):
    """从文件路径解析文档的便捷函数"""
    path = Path(file_path)

    # 检查文件是否存在
    if not path.exists():
        raise FileNotFoundError(f"文件不存在: {file_path}")

    # 获取文件类型
    file_type = path.suffix.lstrip(".").lower()

    # 检查是否支持
    if not is_supported_file_type(file_type):
        raise ValueError(f"不支持的文件类型: {file_type}")

    # 读取文件
    with open(file_path, "rb") as f:
        content = f.read()

    # 解析
    return await parse_document(file_content=content, file_type=file_type, filename=path.name, **kwargs)


async def example_13_utility_function():
    """示例13：使用便捷函数"""
    logger.info("=" * 50)
    logger.info("示例13：使用便捷函数解析文件")
    logger.info("=" * 50)

    logger.info("便捷函数 parse_file_from_path 使用示例:")
    logger.info("""
    # 直接从文件路径解析
    result = await parse_file_from_path("path/to/document.pdf")
    
    # 带 OCR 参数
    result = await parse_file_from_path(
        "path/to/scanned.pdf",
        use_ocr=True,
        ocr_config={'dpi': 144}
    )
    """)


# ==================== 主函数 ====================


async def run_all_examples():
    """运行所有示例"""
    logger.info("\n" + "=" * 60)
    logger.info("文档解析器使用示例演示")
    logger.info("=" * 60 + "\n")

    examples = [
        example_1_basic_usage,
        example_2_check_supported_types,
        example_3_parse_markdown,
        example_4_parse_html,
        example_5_parse_csv,
        example_6_batch_parsing,
        example_7_error_handling,
        example_8_using_factory,
        example_9_encoding_detection,
        example_10_performance_test,
        example_11_pdf_text_extraction,
        example_12_image_ocr,
        example_13_utility_function,
    ]

    for example in examples:
        try:
            await example()
            logger.info("")  # 空行分隔
        except Exception as e:
            logger.error(f"示例 {example.__name__} 执行失败: {e}")
            logger.exception(e)

    logger.info("\n" + "=" * 60)
    logger.info("所有示例演示完成！")
    logger.info("=" * 60)


if __name__ == "__main__":
    # 配置日志
    logger.remove()
    logger.add(
        lambda msg: print(msg, end=""),
        format="<green>{time:HH:mm:ss}</green> | <level>{level:8}</level> | {message}",
        level="INFO",
    )

    # 运行示例
    asyncio.run(run_all_examples())

    # 或者运行单个示例
    # asyncio.run(example_1_basic_usage())
