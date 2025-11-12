import os
import io
import re
import asyncio
import base64
from pathlib import Path
from typing import Union, List, Optional
from urllib.parse import urlparse
import tempfile

import fitz
from PIL import Image
import httpx

from ragserver.app.utils.llm_service import LLMService


class DocumentOCRParser:
    """文档 OCR 解析器，支持 PDF、图片和 S3 URL"""
    
    def __init__(
        self,
        model: str = 'deepseek-ai/DeepSeek-OCR',
        dpi: int = 144,
        max_concurrent: int = 30,
        timeout: int = 300
    ):
        """
        初始化解析器
        
        Args:
            model: LLM 模型名称
            dpi: PDF 转图片的 DPI（默认 144）
            max_concurrent: 最大并发数（默认 30）
            timeout: HTTP 请求超时时间（秒）
        """
        self.llm_service = LLMService(model=model)
        self.dpi = dpi
        self.max_concurrent = max_concurrent
        self.timeout = timeout
        self.semaphore = asyncio.Semaphore(max_concurrent)
    
    async def parse_document(
        self,
        file_path: str,
        extract_images: bool = False,
        output_dir: Optional[str] = None
    ) -> str:
        """
        解析文档（支持 PDF、图片、S3 URL）
        
        Args:
            file_path: 文件路径或 S3 URL
            extract_images: 是否提取文档中的图片（默认 False）
            output_dir: 输出目录（提取图片时需要，默认使用临时目录）
        
        Returns:
            解析后的 Markdown 文本
        
        Raises:
            ValueError: 不支持的文件格式
            FileNotFoundError: 文件不存在
            Exception: 其他处理错误
        """
        # 1. 下载文件（如果是 URL）
        local_path = await self._download_if_url(file_path)
        
        try:
            # 2. 判断文件类型并转换为图片列表
            images = await self._load_document(local_path)
            
            # 3. 使用 LLM 处理所有图片
            results = await self._process_images_with_llm(images)
            
            # 4. 后处理并生成 Markdown
            markdown = await self._post_process(
                results,
                extract_images=extract_images,
                output_dir=output_dir
            )
            
            return markdown
            
        finally:
            # 清理临时文件
            if local_path != file_path and os.path.exists(local_path):
                os.unlink(local_path)
    
    async def _download_if_url(self, file_path: str) -> str:
        """如果是 URL，下载到临时文件；否则返回原路径"""
        parsed = urlparse(file_path)
        
        # 判断是否为 URL（http/https/s3）
        if parsed.scheme in ('http', 'https', 's3'):
            # 处理 S3 URL
            if parsed.scheme == 's3':
                # 转换 s3://bucket/key 为 https URL
                # 这里假设使用标准的 S3 endpoint，实际使用时可能需要配置
                bucket = parsed.netloc
                key = parsed.path.lstrip('/')
                # 可以根据实际情况配置 region
                url = f'https://{bucket}.s3.amazonaws.com/{key}'
            else:
                url = file_path
            
            # 下载文件
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url)
                response.raise_for_status()
                
                # 从 URL 或 Content-Type 推断文件扩展名
                ext = self._get_file_extension(url, response.headers.get('content-type'))
                
                # 保存到临时文件
                with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp_file:
                    tmp_file.write(response.content)
                    return tmp_file.name
        else:
            # 本地文件，检查是否存在
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"文件不存在: {file_path}")
            return file_path
    
    def _get_file_extension(self, url: str, content_type: Optional[str] = None) -> str:
        """从 URL 或 Content-Type 获取文件扩展名"""
        # 首先尝试从 URL 获取
        path = urlparse(url).path
        ext = os.path.splitext(path)[1].lower()
        if ext in ('.pdf', '.png', '.jpg', '.jpeg', '.webp', '.bmp', '.tiff'):
            return ext
        
        # 从 Content-Type 推断
        if content_type:
            type_map = {
                'application/pdf': '.pdf',
                'image/png': '.png',
                'image/jpeg': '.jpg',
                'image/webp': '.webp',
                'image/bmp': '.bmp',
                'image/tiff': '.tiff'
            }
            return type_map.get(content_type.lower(), '.bin')
        
        return '.bin'
    
    async def _load_document(self, file_path: str) -> List[Image.Image]:
        """加载文档并转换为图片列表"""
        ext = os.path.splitext(file_path)[1].lower()
        
        # PDF 文件
        if ext == '.pdf':
            return await asyncio.to_thread(self._pdf_to_images, file_path)
        
        # 图片文件
        elif ext in ('.png', '.jpg', '.jpeg', '.webp', '.bmp', '.tiff'):
            image = await asyncio.to_thread(Image.open, file_path)
            return [image]
        
        else:
            raise ValueError(f"不支持的文件格式: {ext}")
    
    def _pdf_to_images(self, pdf_path: str) -> List[Image.Image]:
        """将 PDF 转换为图片列表"""
        images = []
        pdf_document = fitz.open(pdf_path)
        
        zoom = self.dpi / 72.0
        matrix = fitz.Matrix(zoom, zoom)
        
        for page_num in range(pdf_document.page_count):
            page = pdf_document[page_num]
            pixmap = page.get_pixmap(matrix=matrix, alpha=False)
            
            Image.MAX_IMAGE_PIXELS = None
            img_data = pixmap.tobytes("png")
            img = Image.open(io.BytesIO(img_data))
            
            # 确保是 RGB 模式
            if img.mode in ('RGBA', 'LA'):
                background = Image.new('RGB', img.size, (255, 255, 255))
                background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                img = background
            
            images.append(img)
        
        pdf_document.close()
        return images
    
    def _image_to_base64(self, image: Image.Image, image_format: str = "PNG") -> str:
        """将 PIL 图片转换为 base64 编码"""
        buffered = io.BytesIO()
        
        # 确保是 RGB 模式
        if image.mode != 'RGB':
            image = image.convert('RGB')
        
        image.save(buffered, format=image_format, quality=95)
        buffered.seek(0)
        
        img_base64 = base64.b64encode(buffered.read()).decode('utf-8')
        mime_type = f"image/{image_format.lower()}"
        return f"data:{mime_type};base64,{img_base64}"
    
    async def _process_single_image(
        self,
        page_idx: int,
        image: Image.Image
    ) -> tuple[int, str]:
        """使用 LLM 处理单张图片"""
        async with self.semaphore:
            try:
                image_base64 = await asyncio.to_thread(
                    self._image_to_base64, image, "PNG"
                )
                
                messages = [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image_url",
                                "image_url": {"url": image_base64}
                            },
                            {
                                "type": "text",
                                "text": "<image>\nConvert the document to markdown."
                            }
                        ]
                    }
                ]
                
                response = await self.llm_service.chat(messages=messages)
                return (page_idx, response)
            
            except Exception as e:
                print(f"处理第 {page_idx+1} 页时出错: {e}")
                return (page_idx, "")
    
    async def _process_images_with_llm(
        self,
        images: List[Image.Image]
    ) -> List[tuple[int, str]]:
        """并发处理所有图片"""
        tasks = [
            self._process_single_image(idx, image)
            for idx, image in enumerate(images)
        ]
        
        results = await asyncio.gather(*tasks)
        
        # 按页码排序
        return sorted(results, key=lambda x: x[0])
    
    def _extract_image_markers(self, text: str) -> tuple[List[str], List[str], List[str]]:
        """提取文本中的图片标记"""
        # 提取图片引用内容
        pattern_ref = r'<\|ref\|>image<\|/ref\|><\|det\|>(.*?)<\|/det\|>'
        matches_ref = re.findall(pattern_ref, text, re.DOTALL)
        
        # 提取完整的图片标记
        pattern_images = r'<\|ref\|>image<\|/ref\|><\|det\|>.*?<\|/det\|>'
        matches_images = re.findall(pattern_images, text, re.DOTALL)
        
        # 提取其他标记
        pattern_other = r'<\|ref\|>.*?<\|/ref\|><\|det\|>.*?<\|/det\|>'
        matches_other = re.findall(pattern_other, text, re.DOTALL)
        
        return matches_ref, matches_images, matches_other
    
    def _clean_content(
        self,
        content: str,
        page_idx: int,
        extract_images: bool = False,
        output_dir: Optional[str] = None
    ) -> str:
        """清理内容"""
        # 提取图片标记
        matches_ref, matches_images, matches_other = self._extract_image_markers(content)
        
        # 处理图片引用
        if extract_images and output_dir:
            # 替换为 markdown 图片引用
            for idx, a_match_image in enumerate(matches_images):
                content = content.replace(
                    a_match_image,
                    f'![](images/page_{page_idx}_extracted_{idx}.jpg)\n'
                )
        else:
            # 直接移除图片标记
            for a_match_image in matches_images:
                content = content.replace(a_match_image, '')
        
        # 清理其他标记
        for a_match_other in matches_other:
            content = content.replace(a_match_other, '')
        
        # 清理特殊字符
        content = (content
                   .replace('\\coloneqq', ':=')
                   .replace('\\eqqcolon', '=:')
                   .replace('\n\n\n\n', '\n\n')
                   .replace('\n\n\n', '\n\n'))
        
        # 去除结束标记
        stop_str = '<｜end▁of▁sentence｜>'
        if content.endswith(stop_str):
            content = content[:-len(stop_str)]
        
        return content.strip()
    
    async def _post_process(
        self,
        results: List[tuple[int, str]],
        extract_images: bool = False,
        output_dir: Optional[str] = None
    ) -> str:
        """后处理：清理内容并生成最终 Markdown"""
        contents = []
        page_separator = '\n\n---\n\n'  # 页面分隔符
        
        for page_idx, content in results:
            if not content:
                continue
            
            # 清理内容
            cleaned_content = self._clean_content(
                content,
                page_idx,
                extract_images=extract_images,
                output_dir=output_dir
            )
            
            # 如果是多页文档，添加页码标题
            if len(results) > 1:
                contents.append(f"## 第 {page_idx + 1} 页\n\n{cleaned_content}")
            else:
                contents.append(cleaned_content)
        
        # 合并所有内容
        return page_separator.join(contents)


# ============================================
# 便捷函数
# ============================================

async def parse_document_to_markdown(
    file_path: str,
    model: str = 'deepseek-ai/DeepSeek-OCR',
    dpi: int = 144,
    max_concurrent: int = 30,
    extract_images: bool = False,
    output_dir: Optional[str] = None,
    timeout: int = 300
) -> str:
    """
    解析文档为 Markdown（便捷函数）
    
    Args:
        file_path: 文件路径、S3 URL 或 HTTP URL
                  支持格式：PDF、PNG、JPG、JPEG、WEBP、BMP、TIFF
                  示例：
                    - 本地文件: '/path/to/document.pdf'
                    - S3 URL: 's3://bucket-name/path/to/document.pdf'
                    - HTTP URL: 'https://example.com/document.pdf'
        model: LLM 模型名称（默认 'deepseek-ai/DeepSeek-OCR'）
        dpi: PDF 转图片的 DPI（默认 144）
        max_concurrent: 最大并发数（默认 30）
        extract_images: 是否提取文档中的图片（默认 False）
        output_dir: 输出目录（提取图片时需要）
        timeout: HTTP 请求超时时间（秒，默认 300）
    
    Returns:
        解析后的 Markdown 文本
    
    Example:
        ```python
        # 解析本地 PDF
        markdown = await parse_document_to_markdown('/path/to/document.pdf')
        
        # 解析 S3 上的图片
        markdown = await parse_document_to_markdown('s3://my-bucket/image.png')
        
        # 解析 HTTP URL 的 PDF，并提取图片
        markdown = await parse_document_to_markdown(
            'https://example.com/document.pdf',
            extract_images=True,
            output_dir='/path/to/output'
        )
        ```
    """
    parser = DocumentOCRParser(
        model=model,
        dpi=dpi,
        max_concurrent=max_concurrent,
        timeout=timeout
    )
    
    return await parser.parse_document(
        file_path=file_path,
        extract_images=extract_images,
        output_dir=output_dir
    )

if __name__ == "__main__":
    import asyncio
    result = asyncio.run(parse_document_to_markdown("/data2/zhanghuaao/project/mineru/datas/NBT/images/page_6.jpg"))
    print(result)