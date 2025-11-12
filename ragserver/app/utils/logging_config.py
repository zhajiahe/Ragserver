"""
日志配置模块
使用 loguru 进行日志管理
"""
import sys
from pathlib import Path
from loguru import logger

from ragserver.config import settings


def setup_logging():
    """配置 loguru 日志系统"""
    
    # 移除默认的 handler
    logger.remove()
    
    # 添加控制台输出
    logger.add(
        sys.stdout,
        format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        level=settings.log_level,
        colorize=True,
    )
    
    # 如果启用文件日志
    if settings.log_file_enabled:
        # 确保日志目录存在
        log_path = Path(settings.log_file_path)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        # 添加文件输出（带轮转）
        logger.add(
            settings.log_file_path,
            format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} - {message}",
            level=settings.log_level,
            rotation=settings.log_file_max_size,  # 文件大小轮转
            retention=settings.log_file_backup_count,  # 保留的备份数量
            compression="zip",  # 压缩旧日志
            encoding="utf-8",
        )
        
        # 添加错误日志单独文件
        error_log_path = log_path.parent / f"{log_path.stem}_error{log_path.suffix}"
        logger.add(
            str(error_log_path),
            format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} - {message}",
            level="ERROR",
            rotation=settings.log_file_max_size,
            retention=settings.log_file_backup_count,
            compression="zip",
            encoding="utf-8",
        )
    
    logger.info("日志系统初始化完成")
    logger.info(f"日志级别: {settings.log_level}")
    logger.info(f"文件日志: {'启用' if settings.log_file_enabled else '禁用'}")
    if settings.log_file_enabled:
        logger.info(f"日志文件路径: {settings.log_file_path}")


# 导出 logger 供其他模块使用
__all__ = ["setup_logging", "logger"]

