"""
请求日志中间件
记录所有 HTTP 请求和响应
"""
import time
from typing import Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from loguru import logger


class LoggingMiddleware(BaseHTTPMiddleware):
    """请求日志中间件"""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """处理请求并记录日志"""
        # 记录请求开始时间
        start_time = time.time()
        
        # 获取请求信息
        method = request.method
        url = str(request.url)
        client_host = request.client.host if request.client else "unknown"
        
        # 记录请求
        logger.info(f"→ {method} {url} from {client_host}")
        
        # 处理请求
        try:
            response = await call_next(request)
            
            # 计算处理时间
            process_time = time.time() - start_time
            
            # 记录响应
            status_code = response.status_code
            log_level = "info" if status_code < 400 else "warning" if status_code < 500 else "error"
            
            logger.log(
                log_level.upper(),
                f"← {method} {url} - {status_code} - {process_time:.3f}s"
            )
            
            # 添加处理时间到响应头
            response.headers["X-Process-Time"] = f"{process_time:.3f}"
            
            return response
            
        except Exception as e:
            # 记录异常
            process_time = time.time() - start_time
            logger.error(
                f"✗ {method} {url} - ERROR - {process_time:.3f}s - {str(e)}"
            )
            raise


class PerformanceLoggingMiddleware(BaseHTTPMiddleware):
    """性能监控中间件"""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """监控慢请求"""
        start_time = time.time()
        
        response = await call_next(request)
        
        process_time = time.time() - start_time
        
        # 记录慢请求（超过 1 秒）
        if process_time > 1.0:
            logger.warning(
                f"⚠️  慢请求: {request.method} {request.url.path} - {process_time:.3f}s"
            )
        
        return response

