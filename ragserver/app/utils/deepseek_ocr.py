import os
import fitz
import io
import re
import argparse
import asyncio
import base64
from tqdm.asyncio import tqdm_asyncio
from pathlib import Path
from PIL import Image, ImageOps
import math

from ragserver.app.utils.llm_service import LLMService

llm_service = LLMService(
        model='deepseek-ai/DeepSeek-OCR',
    )

# ============================================
# 配置常量
# ============================================

DPI = 144
BASE_SIZE = 1024  # 全局视图基础尺寸
IMAGE_SIZE = 640  # 图片尺寸
CROP_MODE = True  # 是否启用动态裁剪


class Colors:
    RED = '\033[31m'
    GREEN = '\033[32m'
    YELLOW = '\033[33m'
    BLUE = '\033[34m'
    RESET = '\033[0m'


# ============================================
# 命令行参数解析
# ============================================

def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description='PDF OCR处理工具（简化版）')
    parser.add_argument('-i', '--input', type=str, required=True, help='输入PDF文件路径')
    parser.add_argument('-o', '--output', type=str, required=True, help='输出目录路径')
    parser.add_argument('--max-concurrent', type=int, default=30, help='最大并发数（默认30）')
    parser.add_argument('--max-pages', type=int, default=10, help='最大处理页数（默认处理所有页）')
    
    args = parser.parse_args()
    
    if not os.path.exists(args.input):
        parser.error(f"输入文件不存在: {args.input}")
    
    if not args.input.lower().endswith('.pdf'):
        parser.error(f"输入文件必须是PDF格式: {args.input}")
    
    if args.max_pages is not None and args.max_pages <= 0:
        parser.error(f"--max-pages 必须大于 0")
    
    return args


# ============================================
# PDF 处理函数
# ============================================

def pdf_to_images(pdf_path, dpi=300, image_format="PNG"):
    """
    pdf2images
    """
    images = []
    
    pdf_document = fitz.open(pdf_path)
    
    zoom = dpi / 72.0
    matrix = fitz.Matrix(zoom, zoom)
    
    for page_num in range(pdf_document.page_count):
        page = pdf_document[page_num]

        pixmap = page.get_pixmap(matrix=matrix, alpha=False)
        Image.MAX_IMAGE_PIXELS = None

        if image_format.upper() == "PNG":
            img_data = pixmap.tobytes("png")
            img = Image.open(io.BytesIO(img_data))
        else:
            img_data = pixmap.tobytes("png")
            img = Image.open(io.BytesIO(img_data))
            if img.mode in ('RGBA', 'LA'):
                background = Image.new('RGB', img.size, (255, 255, 255))
                background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                img = background
        
        images.append(img)
    
    pdf_document.close()
    return images


# ============================================
# 图片编码函数
# ============================================

def image_to_base64(image: Image.Image, image_format="PNG") -> str:
    """
    将PIL图片转换为base64编码
    
    Args:
        image: PIL图片对象
        image_format: 图片格式（PNG或JPEG）
    
    Returns:
        base64编码的图片字符串（带data URI前缀）
    """
    buffered = io.BytesIO()
    
    # 确保是RGB模式
    if image.mode != 'RGB':
        image = image.convert('RGB')
    
    # 保存图片到内存
    image.save(buffered, format=image_format, quality=95)
    buffered.seek(0)
    
    # 编码为base64
    img_base64 = base64.b64encode(buffered.read()).decode('utf-8')
    
    # 返回data URI格式
    mime_type = f"image/{image_format.lower()}"
    return f"data:{mime_type};base64,{img_base64}"


# ============================================
# LLM 调用函数（带重试）
# ============================================

async def process_image_with_llm(
    page_idx: int,
    image: Image.Image,
    llm_service: LLMService,
) -> tuple[int, str]:
    """使用LLM处理单张图片，并返回处理结果"""
    try:
        # 将图片转换为base64
        image_base64 = image_to_base64(image, image_format="JPEG")
        
        messages = [
            {
                "role": "user",
                "content": [
                    
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": image_base64,
                        }
                    },
                    {
                        "type": "text",
                        "text": "<image>\n<|grounding|>Convert the document to markdown."
                    },
                ]
            }
        ]
        
        response = await llm_service.chat(messages=messages)
        return (page_idx, response)
    
    except Exception as e:
        print(f"{Colors.RED}处理第 {page_idx+1} 页时出错: {e}{Colors.RESET}")
        return (page_idx, "")


# ============================================
# 内容清理函数（参考DeepSeek-OCR处理方式）
# ============================================

def re_match(text):
    """
    提取文本中的各种标记
    返回: (图片引用列表, 图片标记列表, 其他标记列表)
    """
    # 提取图片引用 <|ref|>image<|/ref|><|det|>...<|/det|>
    pattern_ref = r'<\|ref\|>image<\|/ref\|><\|det\|>(.*?)<\|/det\|>'
    matches_ref = re.findall(pattern_ref, text, re.DOTALL)
    
    # 提取完整的图片标记（用于替换）
    pattern_images = r'<\|ref\|>image<\|/ref\|><\|det\|>.*?<\|/det\|>'
    matches_images = re.findall(pattern_images, text, re.DOTALL)
    
    # 提取其他标记
    pattern_other = r'<\|ref\|>.*?<\|/ref\|><\|det\|>.*?<\|/det\|>'
    matches_other = re.findall(pattern_other, text, re.DOTALL)
    
    return matches_ref, matches_images, matches_other


def save_page_image(image: Image.Image, page_idx: int, output_path: str):
    """保存PDF页面图片"""
    images_dir = os.path.join(output_path, 'images')
    os.makedirs(images_dir, exist_ok=True)
    
    # 保存为JPG格式
    image_path = os.path.join(images_dir, f'page_{page_idx}.jpg')
    
    # 确保是RGB模式（JPG不支持透明度）
    if image.mode != 'RGB':
        image = image.convert('RGB')
    
    image.save(image_path, format='JPEG', quality=95)
    return image_path


def clean_content(content, page_idx, output_path):
    """
    清理内容并保存图片（参考DeepSeek-OCR的处理方式）
    """
    # 提取各种标记
    matches_ref, matches_images, matches_other = re_match(content)
    
    # 替换图片引用为markdown格式
    for idx, a_match_image in enumerate(matches_images):
        content = content.replace(a_match_image, f'![](images/page_{page_idx}_extracted_{idx}.jpg)\n')
    
    # 清理其他标记
    for a_match_other in matches_other:
        content = content.replace(a_match_other, '')
    
    # 清理特殊字符（参考原代码）
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


# ============================================
# 主程序
# ============================================

async def process_pdf(args):
    """处理PDF的主函数"""
    # 初始化LLM服务
    print(f'{Colors.BLUE}初始化 LLM 服务...{Colors.RESET}')
    
    
    # 创建输出目录
    os.makedirs(args.output, exist_ok=True)
    os.makedirs(f'{args.output}/images', exist_ok=True)
    
    # 打印配置信息
    print(f'{Colors.BLUE}{"="*60}{Colors.RESET}')
    print(f'{Colors.GREEN}PDF OCR 处理工具（简化版）{Colors.RESET}')
    print(f'{Colors.BLUE}{"="*60}{Colors.RESET}')
    print(f'输入文件: {Colors.YELLOW}{args.input}{Colors.RESET}')
    print(f'输出目录: {Colors.YELLOW}{args.output}{Colors.RESET}')
    print(f'最大并发: {Colors.YELLOW}{args.max_concurrent}{Colors.RESET}')
    if args.max_pages:
        print(f'最大页数: {Colors.YELLOW}{args.max_pages}{Colors.RESET}')
    print(f'{Colors.BLUE}{"="*60}{Colors.RESET}\n')
    
    # 加载PDF
    print(f'{Colors.BLUE}PDF加载中...{Colors.RESET}')
    images = pdf_to_images(args.input, dpi=DPI)
    
    # 应用max_pages限制
    total_pages = len(images)
    if args.max_pages and args.max_pages < total_pages:
        images = images[:args.max_pages]
        print(f'{Colors.GREEN}✓ 成功加载 {total_pages} 页，将处理前 {len(images)} 页{Colors.RESET}\n')
    else:
        print(f'{Colors.GREEN}✓ 成功加载 {len(images)} 页{Colors.RESET}\n')

    
    # 使用LLM处理所有图片（直接使用base64编码）
    print(f'{Colors.GREEN}使用LLM处理 {len(images)} 张图片...{Colors.RESET}')
    llm_tasks = [
        process_image_with_llm(idx, image, llm_service)
        for idx, image in enumerate(images)
    ]
    
    results = []
    for coro in tqdm_asyncio.as_completed(llm_tasks, total=len(llm_tasks), desc="OCR处理", unit="页"):
        result = await coro
        results.append(result)
    
    # 按页码排序
    results.sort(key=lambda x: x[0])
    
    print(f'{Colors.GREEN}✓ 图片处理完成{Colors.RESET}\n')

    # 生成输出文件路径
    input_filename = Path(args.input).stem
    mmd_path = os.path.join(args.output, f'{input_filename}.mmd')
    raw_path = os.path.join(args.output, f'{input_filename}_raw.txt')
    
    # 保存PDF页面图片
    print(f'{Colors.BLUE}保存PDF页面图片...{Colors.RESET}')
    for idx, image in enumerate(images):
        save_page_image(image, idx, args.output)
    print(f'{Colors.GREEN}✓ 已保存 {len(images)} 张页面图片{Colors.RESET}\n')
    
    # 保存原始输出
    print(f'{Colors.BLUE}保存原始输出...{Colors.RESET}')
    raw_contents = []
    for page_idx, content in results:
        if not content:
            raw_contents.append(f"## 第 {page_idx + 1} 页\n\n[空白页]\n\n")
        else:
            raw_contents.append(f"## 第 {page_idx + 1} 页\n\n{content}\n\n")
    
    with open(raw_path, 'w', encoding='utf-8') as f:
        f.write('=' * 60 + '\n')
        f.write('大模型原始输出（未处理）\n')
        f.write('=' * 60 + '\n\n')
        f.write('\n'.join(raw_contents))
    
    print(f'{Colors.GREEN}✓ 已保存原始输出{Colors.RESET}\n')
    
    # 后处理
    print(f'{Colors.BLUE}后处理中...{Colors.RESET}')
    
    contents = []
    page_separator = '\n\n<--- Page Split --->\n\n'
    total_extracted_images = 0
    
    for page_idx, content in results:
        if not content:
            print(f"{Colors.YELLOW}⚠ 第 {page_idx+1} 页内容为空，跳过{Colors.RESET}")
            continue
        
        # 统计提取的图片数量
        _, matches_images, _ = re_match(content)
        if matches_images:
            total_extracted_images += len(matches_images)
            print(f"{Colors.GREEN}  第 {page_idx+1} 页: 提取 {len(matches_images)} 张图片{Colors.RESET}")
        
        # 清理内容
        cleaned_content = clean_content(content, page_idx, args.output)
        contents.append(f"## 第 {page_idx + 1} 页\n\n{cleaned_content}")
    
    # 合并所有内容
    final_content = page_separator.join(contents)
    
    # 保存结果
    print(f'\n{Colors.GREEN}保存清理后的Markdown...{Colors.RESET}')
    
    with open(mmd_path, 'w', encoding='utf-8') as f:
        f.write(final_content)
    
    
    # 打印结果
    print(f'\n{Colors.BLUE}{"="*60}{Colors.RESET}')
    print(f'{Colors.GREEN}✓ 处理完成！{Colors.RESET}')
    print(f'{Colors.BLUE}{"="*60}{Colors.RESET}')
    print(f'清理后Markdown: {Colors.YELLOW}{mmd_path}{Colors.RESET}')
    print(f'原始输出文本: {Colors.YELLOW}{raw_path}{Colors.RESET}')
    print(f'PDF页面图片: {Colors.YELLOW}{args.output}/images/page_*.jpg ({len(images)} 张){Colors.RESET}')
    if total_extracted_images > 0:
        print(f'提取的图片: {Colors.YELLOW}{args.output}/images/page_*_extracted_*.jpg ({total_extracted_images} 张){Colors.RESET}')
    print(f'处理页数: {Colors.YELLOW}{len([c for _, c in results if c])}/{len(images)}{Colors.RESET}')
    print(f'{Colors.BLUE}{"="*60}{Colors.RESET}\n')


def main():
    """主入口函数"""
    args = parse_args()
    
    try:
        asyncio.run(process_pdf(args))
    except KeyboardInterrupt:
        print(f'\n{Colors.RED}用户中断处理{Colors.RESET}')
    except Exception as e:
        print(f'\n{Colors.RED}处理失败: {e}{Colors.RESET}')
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()