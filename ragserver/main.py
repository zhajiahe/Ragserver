"""AI知识库管理平台 FastAPI 应用主入口"""

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi_radar import Radar

# 导入所有 API 路由
from ragserver.app.api import auth, chunks, collections, documents, parser, search, users
from ragserver.app.dependencies.db import async_engine

# 导入中间件
from ragserver.app.middleware import LoggingMiddleware, PerformanceLoggingMiddleware

# 导入日志配置
from ragserver.app.utils.logging_config import setup_logging
from ragserver.config import settings
from ragserver.lifespan import lifespan

# 初始化日志系统
setup_logging()


def create_app() -> FastAPI:
    """创建 FastAPI 应用实例"""
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="AI知识库管理平台后端 API",
        docs_url=settings.get_docs_url,
        redoc_url=settings.get_redoc_url,
        openapi_url=settings.get_openapi_url,
        lifespan=lifespan,
    )

    # ==================== 服务监控配置 ====================
    # 只在非开发环境启用 Radar（避免 DuckDB 文件锁冲突）
    if not settings.debug:
        radar = Radar(app, db_engine=async_engine)
        radar.create_tables()

    # ==================== 中间件配置 ====================
    # 日志中间件（最先添加，最后执行）
    app.add_middleware(LoggingMiddleware)
    app.add_middleware(PerformanceLoggingMiddleware)

    # CORS 中间件
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=settings.cors_allow_credentials,
        allow_methods=settings.cors_allow_methods,
        allow_headers=settings.cors_allow_headers,
    )

    # ==================== 注册路由 ====================
    # 认证路由
    app.include_router(auth.router)
    
    # 用户路由
    app.include_router(users.router)

    # 知识库管理路由
    app.include_router(collections.router)
    app.include_router(collections.shares_router)

    # 文档管理路由
    app.include_router(documents.router)

    # 搜索路由
    app.include_router(search.router)

    # 文档解析路由
    app.include_router(parser.router)

    # 文档分块查询路由
    app.include_router(chunks.router)

    # ==================== 健康检查端点 ====================
    @app.get("/health", tags=["健康检查"])
    async def health_check():
        """健康检查接口"""
        return JSONResponse(
            content={
                "status": "healthy",
                "app_name": settings.app_name,
                "version": settings.app_version,
                "debug": settings.debug,
            }
        )

    @app.get("/", tags=["根路径"])
    async def root():
        """根路径"""
        return JSONResponse(
            content={
                "message": "欢迎使用 AI知识库管理平台",
                "version": settings.app_version,
                "docs": settings.get_docs_url or "文档已在生产环境禁用",
            }
        )

    return app


# 创建全局应用实例
app = create_app()


# ==================== 开发服务器入口 ====================
if __name__ == "__main__":
    uvicorn.run(
        "ragserver.main:app",
        host="0.0.0.0",
        port=settings.api_port,
        reload=settings.reload or settings.debug,
        log_level=settings.log_level.lower(),
    )
