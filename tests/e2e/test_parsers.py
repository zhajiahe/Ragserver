"""
测试文档解析器

测试不同文件类型的解析功能
"""
import asyncio
from pathlib import Path

import pytest

from ragserver.app.utils.parsers import (
    DocumentParserFactory,
    parse_document,
    get_supported_file_types,
    is_supported_file_type,
    TextParser,
    PDFParser,
    DocxParser,
    HTMLParser,
    ExcelParser,
    PPTXParser,
    ImageParser,
)


def test_get_supported_file_types():
    """测试获取支持的文件类型"""
    types = get_supported_file_types()
    assert isinstance(types, list)
    assert len(types) > 0
    assert 'pdf' in types
    assert 'docx' in types
    assert 'txt' in types


def test_is_supported_file_type():
    """测试检查文件类型是否支持"""
    assert is_supported_file_type('pdf') is True
    assert is_supported_file_type('.pdf') is True
    assert is_supported_file_type('PDF') is True
    assert is_supported_file_type('unknown') is False


@pytest.mark.asyncio
async def test_parse_text_file():
    """测试解析纯文本文件"""
    content = b"Hello World\n\nThis is a test file."
    result = await parse_document(content, 'txt', 'test.txt')
    assert result == "Hello World\n\nThis is a test file."


@pytest.mark.asyncio
async def test_parse_text_file_with_encoding():
    """测试解析不同编码的文本文件"""
    # UTF-8
    content = "你好世界".encode('utf-8')
    result = await parse_document(content, 'txt', 'test_utf8.txt')
    assert "你好世界" in result
    
    # GBK
    content = "你好世界".encode('gbk')
    result = await parse_document(content, 'txt', 'test_gbk.txt')
    assert "你好世界" in result


@pytest.mark.asyncio
async def test_parse_markdown_file():
    """测试解析 Markdown 文件"""
    content = b"# Title\n\nThis is **bold** text."
    result = await parse_document(content, 'md', 'test.md')
    assert "# Title" in result
    assert "**bold**" in result


@pytest.mark.asyncio
async def test_html_parser():
    """测试 HTML 解析器"""
    html_content = b"""
    <html>
        <head><title>Test</title></head>
        <body>
            <h1>Main Title</h1>
            <p>This is a paragraph.</p>
            <a href="https://example.com">Link</a>
            <script>console.log('remove me');</script>
        </body>
    </html>
    """
    result = await parse_document(html_content, 'html', 'test.html')
    assert "Main Title" in result
    assert "paragraph" in result
    assert "[Link](https://example.com)" in result
    assert "console.log" not in result


@pytest.mark.asyncio
async def test_get_parser_by_type():
    """测试根据文件类型获取解析器"""
    parser = DocumentParserFactory.get_parser('txt')
    assert isinstance(parser, TextParser)
    
    parser = DocumentParserFactory.get_parser('pdf')
    assert isinstance(parser, PDFParser)
    
    parser = DocumentParserFactory.get_parser('docx')
    assert isinstance(parser, DocxParser)
    
    parser = DocumentParserFactory.get_parser('html')
    assert isinstance(parser, HTMLParser)
    
    parser = DocumentParserFactory.get_parser('xlsx')
    assert isinstance(parser, ExcelParser)
    
    parser = DocumentParserFactory.get_parser('pptx')
    assert isinstance(parser, PPTXParser)
    
    parser = DocumentParserFactory.get_parser('jpg')
    assert isinstance(parser, ImageParser)


@pytest.mark.asyncio
async def test_unsupported_file_type():
    """测试不支持的文件类型"""
    with pytest.raises(ValueError) as exc_info:
        await parse_document(b"content", 'unsupported', 'test.unsupported')
    
    assert "不支持的文件类型" in str(exc_info.value)


@pytest.mark.asyncio
async def test_empty_content():
    """测试空内容"""
    with pytest.raises(ValueError) as exc_info:
        await parse_document(b"", 'txt', 'empty.txt')
    
    assert "解析结果为空" in str(exc_info.value)


@pytest.mark.asyncio
async def test_excel_csv_parser():
    """测试 CSV 解析器（简单模拟）"""
    csv_content = b"Name,Age,City\nAlice,30,New York\nBob,25,Los Angeles"
    result = await parse_document(csv_content, 'csv', 'test.csv')
    assert "Name" in result
    assert "Alice" in result
    assert "Bob" in result


def test_file_type_with_dot():
    """测试带点号的文件类型"""
    assert is_supported_file_type('.pdf') is True
    assert is_supported_file_type('.txt') is True
    
    parser = DocumentParserFactory.get_parser('.pdf')
    assert isinstance(parser, PDFParser)


# ==================== 集成测试示例 ====================

@pytest.mark.asyncio
async def test_parse_multiple_formats():
    """测试解析多种格式（示例）"""
    test_cases = [
        (b"Plain text content", "txt", "test.txt"),
        (b"# Markdown Header", "md", "test.md"),
        (b"<html><body>HTML content</body></html>", "html", "test.html"),
    ]
    
    for content, file_type, filename in test_cases:
        try:
            result = await parse_document(content, file_type, filename)
            assert result is not None
            assert len(result) > 0
            print(f"✓ 成功解析: {filename}")
        except Exception as e:
            pytest.fail(f"解析失败 {filename}: {e}")


# ==================== 性能测试示例 ====================

@pytest.mark.asyncio
async def test_parser_performance():
    """测试解析器性能"""
    import time
    
    # 生成大文本
    large_text = ("This is a test line.\n" * 1000).encode('utf-8')
    
    start_time = time.time()
    result = await parse_document(large_text, 'txt', 'large.txt')
    end_time = time.time()
    
    elapsed = end_time - start_time
    print(f"解析 {len(large_text)} 字节耗时: {elapsed:.4f} 秒")
    
    assert len(result) > 0
    # 性能要求：1MB 文本应在 1 秒内完成
    assert elapsed < 1.0


if __name__ == "__main__":
    # 运行测试
    pytest.main([__file__, "-v", "-s"])


