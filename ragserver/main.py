"""
AI知识库管理平台 FastAPI 应用主入口
"""
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
import uvicorn

from ragserver.config import settings
from ragserver.app.dependencies.db import async_engine
from ragserver.app.models import Base

# 导入所有 API 路由
from ragserver.app.api import auth, collections, documents, search, parser
# TODO: 以下路由待实现
# from ragserver.app.api import files


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    """应用生命周期管理"""
    # 启动时
    print("🚀 应用启动中...")
    print(f"📦 环境: {'开发' if settings.debug else '生产'}")
    print(f"🗄️  数据库: {settings.postgres_host}:{settings.postgres_port}/{settings.postgres_db}")
    print(f"🔑 Redis: {settings.redis_host}:{settings.redis_port}")
    print(f"📦 MinIO: {settings.minio_host}:{settings.minio_port}")
    
    # 开发模式：自动创建数据库表
    if settings.debug:
        print("🔧 开发模式：自动创建数据库扩展和表...")
        try:
            # 创建必要的 PostgreSQL 扩展和表
            async with async_engine.begin() as conn:
                # 创建 pgvector 扩展（必需）
                await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
                print("  ✓ pgvector 扩展已启用")
                
                # 创建所有表
                await conn.run_sync(Base.metadata.create_all)
                print("  ✓ 数据库表创建完成")
            
            # 尝试创建 ParadeDB 扩展（可选，单独事务）
            paradedb_available = False
            try:
                async with async_engine.begin() as conn:
                    # ParadeDB 由多个扩展组成：pg_search（全文搜索）和 pg_analytics（分析）
                    await conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_search"))
                    print("  ✓ ParadeDB (pg_search) 扩展已启用")
                    paradedb_available = True
            except Exception as e:
                print(f"  ℹ️  ParadeDB 扩展不可用（全文搜索将使用 pg_trgm）")
            
            # 如果 ParadeDB 可用，创建 BM25 索引
            if paradedb_available:
                try:
                    async with async_engine.begin() as conn:
                        # 检查索引是否已存在
                        result = await conn.execute(text("""
                            SELECT indexname FROM pg_indexes 
                            WHERE tablename = 'document_chunks' 
                            AND indexname = 'document_chunks_bm25_idx'
                        """))
                        if not result.scalar():
                            # 使用 CREATE INDEX 创建 BM25 索引（ParadeDB v0.18+ 方式）
                            await conn.execute(text("""
                                CREATE INDEX document_chunks_bm25_idx 
                                ON document_chunks 
                                USING bm25 (id, content)
                                WITH (key_field='id')
                            """))
                            print("  ✓ BM25 索引已创建")
                        else:
                            print("  ✓ BM25 索引已存在")
                except Exception as e:
                    print(f"  ⚠️  BM25 索引创建失败: {str(e)[:100]}")
                    print("  提示：全文搜索仍可使用，但性能可能受影响")
                
        except Exception as e:
            print(f"  ⚠️  数据库初始化失败: {e}")
            print("  提示：请确保数据库已安装 pgvector 扩展")
            raise
    
    print("✅ 应用启动完成！")
    
    yield
    
    # 关闭时
    print("🛑 应用关闭中...")
    await async_engine.dispose()
    print("✅ 应用已关闭")


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
    
    # ==================== CORS 中间件 ====================
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
    
    # 知识库管理路由
    app.include_router(collections.router)
    
    # 文档管理路由
    app.include_router(documents.router)
    
    # 搜索路由
    app.include_router(search.router)
    
    # 文档解析路由
    app.include_router(parser.router)
    
    # 文件上传路由
    # app.include_router(files.router)
    
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
