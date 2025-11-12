#!/usr/bin/env python3
"""
数据库重置脚本

警告: 此脚本会删除所有数据库表并重新创建！
仅用于开发和测试环境，请勿在生产环境使用！
"""
import asyncio
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import text
from ragserver.app.dependencies.db import async_engine
from ragserver.app.models import Base
from ragserver.config import settings
from ragserver.app.utils.logging_config import logger


async def reset_database():
    """重置数据库（删除所有表并重新创建）"""
    
    # 显示数据库信息
    print("\n" + "=" * 60)
    print("数据库重置脚本")
    print("=" * 60)
    print(f"\n数据库连接: {settings.async_database_url.replace(settings.postgres_password, '***')}")
    print(f"数据库名称: {settings.postgres_db}")
    print(f"主机地址: {settings.postgres_host}:{settings.postgres_port}")
    print("\n⚠️  警告: 此操作将删除所有数据库表和数据！")
    print("⚠️  此操作不可逆，请确保已备份重要数据！")
    print("=" * 60)
    
    # 确认操作
    confirmation = input("\n是否继续？请输入数据库名称以确认 (输入 'cancel' 取消): ").strip()
    
    if confirmation.lower() == 'cancel':
        print("\n✅ 操作已取消")
        return
    
    if confirmation != settings.postgres_db:
        print(f"\n❌ 输入的数据库名称不匹配！期望: {settings.postgres_db}, 实际: {confirmation}")
        print("操作已取消")
        return
    
    # 二次确认
    final_confirmation = input("\n⚠️  最后确认：确定要删除所有数据吗？(yes/no): ").strip().lower()
    
    if final_confirmation != 'yes':
        print("\n✅ 操作已取消")
        return
    
    print("\n开始重置数据库...")
    
    try:
        async with async_engine.begin() as conn:
            # 1. 删除所有表
            print("\n[1/4] 删除所有表...")
            await conn.run_sync(Base.metadata.drop_all)
            logger.info("✅ 所有表已删除")
            
            # 2. 删除 pgvector 扩展（如果存在）
            print("[2/4] 重置 pgvector 扩展...")
            try:
                await conn.execute(text("DROP EXTENSION IF EXISTS vector CASCADE"))
                logger.info("✅ pgvector 扩展已删除")
            except Exception as e:
                logger.warning(f"删除 pgvector 扩展失败（可能不存在）: {e}")
            
            # 3. 创建 pgvector 扩展
            try:
                await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
                logger.info("✅ pgvector 扩展已创建")
            except Exception as e:
                logger.error(f"创建 pgvector 扩展失败: {e}")
                raise
            
            # 4. 重新创建所有表
            print("[3/4] 创建所有表...")
            await conn.run_sync(Base.metadata.create_all)
            logger.info("✅ 所有表已创建")
            
            # 5. 验证表创建
            print("[4/4] 验证表结构...")
            result = await conn.execute(text("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public' 
                ORDER BY table_name
            """))
            tables = [row[0] for row in result]
            
            print("\n创建的表:")
            for table in tables:
                print(f"  ✓ {table}")
            
            print(f"\n总计: {len(tables)} 个表")
        
        print("\n" + "=" * 60)
        print("✅ 数据库重置成功！")
        print("=" * 60)
        
    except Exception as e:
        logger.error(f"数据库重置失败: {e}")
        print("\n" + "=" * 60)
        print(f"❌ 数据库重置失败: {e}")
        print("=" * 60)
        raise
    
    finally:
        # 关闭数据库连接
        await async_engine.dispose()


async def show_database_info():
    """显示数据库信息（不执行重置）"""
    print("\n" + "=" * 60)
    print("数据库信息")
    print("=" * 60)
    print(f"\n数据库连接: {settings.async_database_url.replace(settings.postgres_password, '***')}")
    print(f"数据库名称: {settings.postgres_db}")
    print(f"主机地址: {settings.postgres_host}:{settings.postgres_port}")
    
    try:
        async with async_engine.connect() as conn:
            # 获取表列表
            result = await conn.execute(text("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public' 
                ORDER BY table_name
            """))
            tables = [row[0] for row in result]
            
            print(f"\n当前表数量: {len(tables)}")
            if tables:
                print("\n表列表:")
                for table in tables:
                    # 获取表的行数
                    count_result = await conn.execute(text(f"SELECT COUNT(*) FROM {table}"))
                    count = count_result.scalar()
                    print(f"  • {table}: {count} 行")
            else:
                print("\n数据库中没有表")
            
            # 检查 pgvector 扩展
            ext_result = await conn.execute(text("""
                SELECT extname, extversion 
                FROM pg_extension 
                WHERE extname = 'vector'
            """))
            ext = ext_result.fetchone()
            
            if ext:
                print(f"\npgvector 扩展: 已安装 (版本 {ext[1]})")
            else:
                print("\npgvector 扩展: 未安装")
        
        print("=" * 60)
        
    except Exception as e:
        logger.error(f"获取数据库信息失败: {e}")
        print(f"\n❌ 获取数据库信息失败: {e}")
    
    finally:
        await async_engine.dispose()


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="数据库重置脚本（仅用于开发和测试环境）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 显示数据库信息
  python tests/reset_db.py --info
  
  # 重置数据库（需要确认）
  python tests/reset_db.py --reset
  
  # 强制重置（跳过确认，危险！）
  python tests/reset_db.py --reset --force
        """
    )
    
    parser.add_argument(
        '--info',
        action='store_true',
        help='显示数据库信息（不执行重置）'
    )
    
    parser.add_argument(
        '--reset',
        action='store_true',
        help='重置数据库（删除所有表并重新创建）'
    )
    
    parser.add_argument(
        '--force',
        action='store_true',
        help='强制重置（跳过确认，危险！仅用于自动化脚本）'
    )
    
    args = parser.parse_args()
    
    # 检查是否在生产环境
    if not settings.debug and not args.force:
        print("\n❌ 错误: 检测到生产环境（DEBUG=False）")
        print("为了安全，此脚本仅能在开发环境运行")
        print("如果确实需要在生产环境重置数据库，请使用 --force 参数")
        sys.exit(1)
    
    if args.info:
        # 显示数据库信息
        asyncio.run(show_database_info())
    elif args.reset:
        # 重置数据库
        if args.force:
            print("\n⚠️  警告: 使用 --force 参数，跳过确认！")
            # 直接执行重置
            asyncio.run(reset_database_force())
        else:
            # 需要用户确认
            asyncio.run(reset_database())
    else:
        # 默认显示帮助信息
        parser.print_help()


async def reset_database_force():
    """强制重置数据库（跳过确认）"""
    print("\n开始强制重置数据库...")
    
    try:
        async with async_engine.begin() as conn:
            # 删除所有表
            print("[1/3] 删除所有表...")
            await conn.run_sync(Base.metadata.drop_all)
            
            # 重置 pgvector 扩展
            print("[2/3] 重置 pgvector 扩展...")
            await conn.execute(text("DROP EXTENSION IF EXISTS vector CASCADE"))
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            
            # 重新创建所有表
            print("[3/3] 创建所有表...")
            await conn.run_sync(Base.metadata.create_all)
        
        print("\n✅ 数据库强制重置成功！")
        
    except Exception as e:
        logger.error(f"数据库强制重置失败: {e}")
        print(f"\n❌ 数据库强制重置失败: {e}")
        raise
    
    finally:
        await async_engine.dispose()


if __name__ == "__main__":
    main()

