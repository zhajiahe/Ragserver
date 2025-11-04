import os
import pymupdf as fitz
import io
import re
import argparse
import asyncio
from tqdm.asyncio import tqdm_asyncio
import base64
from pathlib import Path
from PIL import Image

from ragserver.app.utils.llm_service import LLMService


# ============================================
# 配置常量
# ============================================

DPI = 144


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
    parser.add_argument('--max-concurrent', type=int, default=30, help='最大并发数（默认3）')
    
    args = parser.parse_args()
    
    if not os.path.exists(args.input):
        parser.error(f"输入文件不存在: {args.input}")
    
    if not args.input.lower().endswith('.pdf'):
        parser.error(f"输入文件必须是PDF格式: {args.input}")
    
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

def encode_image_to_base64(image: Image.Image, image_format="PNG") -> str:
    """将PIL图片编码为base64字符串"""
    buffered = io.BytesIO()
    
    if image.mode != 'RGB':
        image = image.convert('RGB')
    
    image.save(buffered, format=image_format, quality=95)
    return f"data:image/{image_format};base64,{base64.b64encode(buffered.getvalue()).decode('utf-8')}"


# ============================================
# LLM 调用函数（带重试）
# ============================================

async def process_image(
    page_idx: int, 
    image: Image.Image, 
    llm_service: LLMService,
    semaphore: asyncio.Semaphore
) -> tuple[int, str]:
    """使用LLM处理单张图片（带并发控制）"""
    async with semaphore:
        try:
            base64_image = encode_image_to_base64(image, image_format="PNG")
            
            messages = [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "<image>\n<|grounding|>Convert the document to markdown."
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": base64_image,
                            }
                        }
                    ]
                }
            ]
            
            response = await llm_service.chat(messages=messages)
            return (page_idx, response)
        
        except Exception as e:
            print(f"{Colors.RED}处理第 {page_idx+1} 页时出错: {e}{Colors.RESET}")
            return (page_idx, "")


# ============================================
# 内容清理函数（简化版）
# ============================================

def extract_image_refs(text):
    """提取图片引用"""
    pattern = r'(<\|ref\|>image<\|/ref\|><\|det\|>(.*?)<\|/det\|>)'
    return re.findall(pattern, text, re.DOTALL)


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
    """清理内容并保存图片"""
    # 提取图片引用
    image_refs = extract_image_refs(content)
    
    # 替换图片引用为markdown格式
    for idx, img_ref in enumerate(image_refs):
        content = content.replace(img_ref[0], f'![](images/{page_idx}_{idx}.jpg)\n')
    
    # 清理所有其他标记
    content = re.sub(r'<\|ref\|>.*?<\|/ref\|><\|det\|>.*?<\|/det\|>', '', content, flags=re.DOTALL)
    
    # 清理特殊字符
    content = (content
               .replace('\\coloneqq', ':=')
               .replace('\\eqqcolon', '=:')
               .replace('\n\n\n\n', '\n\n')
               .replace('\n\n\n', '\n\n'))
    
    return content


# ============================================
# 主程序
# ============================================

async def process_pdf(args):
    """处理PDF的主函数"""
    # 初始化LLM服务
    print(f'{Colors.BLUE}初始化 LLM 服务...{Colors.RESET}')
    llm_service = LLMService(
        model='deepseek-ai/DeepSeek-OCR',
    )
    
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
    print(f'{Colors.BLUE}{"="*60}{Colors.RESET}\n')
    
    # 加载PDF
    print(f'{Colors.BLUE}PDF加载中...{Colors.RESET}')
    images = pdf_to_images(args.input, dpi=DPI)

    print(f'{Colors.GREEN}✓ 成功加载 {len(images)} 页{Colors.RESET}\n')

    # 创建并发控制信号量
    semaphore = asyncio.Semaphore(args.max_concurrent)
    
    # 并发处理所有图片（带进度条）
    print(f'{Colors.GREEN}开始处理 {len(images)} 张图片...{Colors.RESET}')
    tasks = [
        process_image(idx, image, llm_service, semaphore) 
        for idx, image in enumerate(images)
    ]
    
    # 使用 tqdm 显示进度
    results = []
    for coro in tqdm_asyncio.as_completed(tasks, total=len(tasks), desc="OCR处理", unit="页"):
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
    
    for page_idx, content in results:
        if not content:
            print(f"{Colors.YELLOW}⚠ 第 {page_idx+1} 页内容为空，跳过{Colors.RESET}")
            continue
        
        # 清理内容
        cleaned_content = clean_content(content, page_idx, args.output)
        contents.append(f"## 第 {page_idx + 1} 页\n\n{cleaned_content}")
    
    # 合并所有内容
    final_content = page_separator.join(contents)
    
    # 保存结果
    print(f'\n{Colors.GREEN}保存结果...{Colors.RESET}')
    
    with open(mmd_path, 'w', encoding='utf-8') as f:
        f.write(final_content)
    
    
    # 打印结果
    print(f'\n{Colors.BLUE}{"="*60}{Colors.RESET}')
    print(f'{Colors.GREEN}✓ 处理完成！{Colors.RESET}')
    print(f'{Colors.BLUE}{"="*60}{Colors.RESET}')
    print(f'清理后Markdown: {Colors.YELLOW}{mmd_path}{Colors.RESET}')
    print(f'原始输出文本: {Colors.YELLOW}{raw_path}{Colors.RESET}')
    print(f'页面图片: {Colors.YELLOW}{args.output}/images/page_*.jpg{Colors.RESET}')
    print(f'提取图片: {Colors.YELLOW}{args.output}/images/{Colors.RESET}')
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