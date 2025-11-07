#!/usr/bin/env python3
"""
测试 upload_image_to_minio 函数
"""
import asyncio
import sys
from pathlib import Path
from PIL import Image

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from ragserver.app.utils.deepseek_ocr import upload_image_to_minio
from ragserver.config import settings


async def test_upload_image():
    """测试上传图片到MinIO"""
    
    print("=" * 60)
    print("测试 upload_image_to_minio 函数")
    print("=" * 60)
    
    # 1. 创建一个测试图片（蓝色渐变背景，带圆形和文字）
    print("\n1. 创建测试图片...")
    width, height = 1024, 768
    image = Image.new('RGB', (width, height), color='white')
    
    # 可以添加一些文字（需要PIL的ImageDraw）
    from PIL import ImageDraw, ImageFont
    import random
    draw = ImageDraw.Draw(image)
    
    # 绘制渐变背景
    for y in range(height):
        color_value = int(255 * (y / height))
        draw.rectangle([(0, y), (width, y+1)], fill=(30, 144, color_value))
    
    # 绘制一些随机圆形
    for _ in range(10):
        x = random.randint(0, width)
        y = random.randint(0, height)
        r = random.randint(20, 80)
        color = (random.randint(100, 255), random.randint(100, 255), random.randint(100, 255))
        draw.ellipse([x-r, y-r, x+r, y+r], fill=color, outline='white', width=3)
    
    # 绘制一些文字
    text = f"MinIO Upload Test - {width}x{height}"
    try:
        # 尝试使用系统字体
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 50)
    except:
        # 如果找不到字体，使用默认字体
        font = ImageFont.load_default()
    
    # 计算文字位置（居中）
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    position = ((width - text_width) // 2, (height - text_height) // 2)
    
    # 绘制文字阴影
    draw.text((position[0]+3, position[1]+3), text, fill='black', font=font)
    # 绘制文字
    draw.text(position, text, fill='yellow', font=font)
    
    print(f"   ✓ 创建了 {width}x{height} 的渐变背景测试图片（带圆形和文字）")
    
    # 2. 显示配置信息
    print("\n2. MinIO配置信息:")
    print(f"   - Host: {settings.minio_host}")
    print(f"   - Port: {settings.minio_port}")
    print(f"   - Temp Bucket: {settings.minio_bucket_temp}")
    print(f"   - Public URL: {settings.minio_public_host}:{settings.minio_port}")
    
    # 3. 上传图片
    print("\n3. 上传图片到MinIO...")
    try:
        page_idx = 0
        url = await upload_image_to_minio(image, page_idx, image_format="PNG")
        
        print(f"   ✓ 上传成功!")
        print(f"   - 图片URL: {url}")
        
        # 4. 测试不同格式 - 创建条纹图案
        print("\n4. 测试JPEG格式上传（条纹图案）...")
        jpeg_image = Image.new('RGB', (640, 480), color='white')
        jpeg_draw = ImageDraw.Draw(jpeg_image)
        
        # 绘制彩色条纹
        stripe_height = 480 // 7
        colors = [
            (255, 0, 0),    # 红
            (255, 127, 0),  # 橙
            (255, 255, 0),  # 黄
            (0, 255, 0),    # 绿
            (0, 0, 255),    # 蓝
            (75, 0, 130),   # 靛
            (148, 0, 211),  # 紫
        ]
        for i, color in enumerate(colors):
            y_start = i * stripe_height
            y_end = (i + 1) * stripe_height
            jpeg_draw.rectangle([(0, y_start), (640, y_end)], fill=color)
        
        url_jpeg = await upload_image_to_minio(jpeg_image, page_idx + 1, image_format="JPEG")
        print(f"   ✓ JPEG上传成功!")
        print(f"   - 图片URL: {url_jpeg}")
        
        # 5. 测试RGBA模式转换 - 创建半透明网格
        print("\n5. 测试RGBA模式图片（半透明网格）...")
        rgba_image = Image.new('RGBA', (512, 512), color=(255, 255, 255, 0))
        rgba_draw = ImageDraw.Draw(rgba_image)
        
        # 绘制网格背景
        grid_size = 32
        for x in range(0, 512, grid_size * 2):
            for y in range(0, 512, grid_size * 2):
                rgba_draw.rectangle(
                    [(x, y), (x + grid_size, y + grid_size)],
                    fill=(200, 200, 200, 255)
                )
                rgba_draw.rectangle(
                    [(x + grid_size, y + grid_size), (x + grid_size * 2, y + grid_size * 2)],
                    fill=(200, 200, 200, 255)
                )
        
        # 绘制半透明圆形
        for i in range(5):
            x = random.randint(50, 462)
            y = random.randint(50, 462)
            r = random.randint(30, 60)
            color = (
                random.randint(0, 255),
                random.randint(0, 255),
                random.randint(0, 255),
                180  # 半透明
            )
            rgba_draw.ellipse([x-r, y-r, x+r, y+r], fill=color)
        
        url_rgba = await upload_image_to_minio(rgba_image, page_idx + 2, image_format="PNG")
        print(f"   ✓ RGBA图片上传成功!")
        print(f"   - 图片URL: {url_rgba}")
        
        print("\n" + "=" * 60)
        print("✓ 所有测试通过!")
        print("=" * 60)
        
        return True
        
    except Exception as e:
        print(f"\n   ✗ 上传失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_with_real_image(image_path: str):
    """使用真实图片测试"""
    
    print("=" * 60)
    print("使用真实图片测试 upload_image_to_minio")
    print("=" * 60)
    
    # 1. 加载图片
    print(f"\n1. 加载图片: {image_path}")
    try:
        image = Image.open(image_path)
        print(f"   ✓ 图片加载成功")
        print(f"   - 尺寸: {image.size}")
        print(f"   - 模式: {image.mode}")
        print(f"   - 格式: {image.format}")
    except Exception as e:
        print(f"   ✗ 图片加载失败: {e}")
        return False
    
    # 2. 上传图片
    print("\n2. 上传图片到MinIO...")
    try:
        page_idx = 99  # 使用特殊页码标识测试
        url = await upload_image_to_minio(image, page_idx, image_format="PNG")
        
        print(f"   ✓ 上传成功!")
        print(f"   - 图片URL: {url}")
        
        print("\n" + "=" * 60)
        print("✓ 测试通过!")
        print("=" * 60)
        
        return True
        
    except Exception as e:
        print(f"\n   ✗ 上传失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='测试图片上传到MinIO')
    parser.add_argument('--image', '-i', type=str, help='图片路径（可选，不提供则使用生成的测试图片）')
    
    args = parser.parse_args()
    
    if args.image:
        # 使用真实图片测试
        success = await test_with_real_image(args.image)
    else:
        # 使用生成的测试图片
        success = await test_upload_image()
    
    return 0 if success else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)

