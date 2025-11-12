# RAG Collection Server - AI Assistant 开发指南

> 本文档为 AI 代码助手（如 Cursor、GitHub Copilot、Cline等）提供项目开发指南。

## 项目概述

**项目名称**: AI知识库管理平台后端系统  
**技术栈**: FastAPI + PostgreSQL + pgvector + MinIO + SiliconFlow API  
**主要功能**: 文档智能处理、向量检索、知识库管理、API服务、知识库分享

## 核心原则

1. **简洁优于复杂**: 优先使用简单直接的实现
2. **配置驱动**: 所有可配置项都通过 `.env` 文件管理
3. **异步优先**: 使用 FastAPI 的异步特性
4. **类型安全**: 使用 Pydantic 进行数据验证
5. **数据隔离**: 所有资源必须按 `user_id` 隔离

## uv
1. 安装环境或者运行python需要激活环境
2. source .venv/bin/activate

## 项目结构

```
ragserver/
├── ragserver/
│   ├── app/
│   │   ├── models.py              # 数据模型（User, Collection, Document, DocumentChunk, CollectionShare）
│   │   ├── api/                   # API 路由
│   │   │   ├── auth.py           # 认证接口
│   │   │   ├── collections.py   # 知识库接口
│   │   │   ├── documents.py     # 文档接口
│   │   │   ├── parser.py        # 解析接口
│   │   │   ├── chunks.py        # 分块接口
│   │   │   └── search.py        # 搜索接口
│   │   ├── dependencies/         # 依赖注入（db, security）
│   │   ├── services/
│   │   │   └── document_pipeline.py  # 文档处理流水线
│   │   └── utils/
│   │       ├── minio_client.py       # 对象存储
│   │       ├── embedding_service.py  # 向量服务
│   │       ├── parsers.py           # 文档解析
│   │       └── chunkers.py          # 文本分块
│   ├── config.py                 # 配置（settings对象）
│   └── main.py                   # 应用入口
├── tests/                        # 测试
├── Makefile                      # 常用命令
└── pyproject.toml                # 依赖管理
```

## 数据模型（详见 ER.md）

1. **User** - 用户（所有资源按 user_id 隔离）
2. **Collection** - 知识库（settings 字段存储 JSONB 配置）
3. **Document** - 文档（status: pending/processing/completed/failed）
4. **DocumentChunk** - 分块（含 1024维向量，pgvector）
5. **CollectionShare** - 分享链接（share_token 用于公开访问）

## 开发规范

### 1. 数据库操作

```python
# ✅ 正确：使用异步 Session
from sqlalchemy.ext.asyncio import AsyncSession

async def get_kb(db: AsyncSession, kb_id: UUID, user_id: UUID):
    result = await db.execute(
        select(Collection).where(
            Collection.id == kb_id,
            Collection.user_id == user_id  # 必须过滤 user_id
        )
    )
    return result.scalar_one_or_none()

# ❌ 错误：忘记数据隔离
async def get_kb_bad(db: AsyncSession, kb_id: UUID):
    result = await db.execute(
        select(Collection).where(Collection.id == kb_id)
    )
    return result.scalar_one_or_none()
```

### 2. API 路由设计

```python
# ✅ 正确：使用依赖注入
from fastapi import APIRouter, Depends
from app.dependencies import get_current_user, get_db

router = APIRouter(prefix="/api/v1/collections", tags=["collections"])

@router.get("/{kb_id}")
async def get_collection(
    kb_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    kb = await get_kb(db, kb_id, current_user.id)
    if not kb:
        raise HTTPException(status_code=404, detail="Collection not found")
    return kb
```

### 3. 数据验证

```python
# ✅ 正确：使用 Pydantic schemas
from pydantic import BaseModel, Field, field_validator

class CollectionCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    settings: Optional[Dict[str, Any]] = Field(default_factory=dict)
    
    @field_validator('name')
    @classmethod
    def name_must_not_be_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError('Name cannot be empty or whitespace')
        return v.strip()
```

### 4. 配置管理

```python
# ✅ 正确：使用统一配置
from ragserver.config import settings

# 获取配置
embedding_model = settings.default_embedding_model
db_url = settings.async_database_url

# ❌ 错误：硬编码配置
EMBEDDING_MODEL = "BAAI/bge-m3"  # 不要这样做
```

### 5. 文档处理流水线

```python
# ✅ 正确：使用简单的流水线处理
from ragserver.app.services.document_pipeline import process_document

async def handle_document_upload(document_id: UUID, db: AsyncSession):
    """处理上传的文档"""
    # 直接调用处理流水线
    result = await process_document(db, document_id)
    # 流水线会自动完成：
    # 1. 解析文档
    # 2. 分块
    # 3. 生成向量
    # 4. 存储到数据库
    return result
```

### 6. Embedding 生成

```python
# ✅ 正确：使用 SiliconFlow API 生成向量
from ragserver.app.utils.embedding_service import embedding_service

# 生成单个文本向量
embedding = await embedding_service.encode_single("查询文本")

# 批量生成向量
texts = ["文本1", "文本2", "文本3"]
embeddings = await embedding_service.encode(texts)

# 自动分批处理大量文本
embeddings = await embedding_service.encode_batch(
    texts,
    batch_size=settings.embedding_batch_size
)
```

### 7. 文本分块

```python
# 使用分块服务
from ragserver.app.utils.chunkers import chunk_text

chunking_config = {
    "strategy_type": "fixed",  # fixed/paragraph/semantic
    "config": {
        "chunk_size": 1000,
        "chunk_overlap": 200,
        "min_chunk_size": 100
    }
}

chunks = await chunk_text(content_text, chunking_config)
```

### 8. 搜索（三种模式）

```python
# 1. 向量搜索（语义）
SearchRequest(query="查询", mode="vector", top_k=10, threshold=0.7)

# 2. 全文搜索（关键词）
SearchRequest(query="关键词", mode="fulltext", top_k=10)

# 3. 混合搜索（向量+全文）
SearchRequest(
    query="查询",
    mode="hybrid",
    vector_weight=0.7,
    fulltext_weight=0.3
)
```

## 关键注意事项

### 1. 错误处理
```python
from fastapi import HTTPException, status

raise HTTPException(status_code=404, detail="Resource not found")
```

### 2. MinIO 对象存储
```python
from ragserver.app.utils.minio_client import minio_client

# 上传
await minio_client.upload_file(bucket, key, file_bytes, content_type)

# 下载
response = await minio_client.download_file(bucket, key)
content = await response["Body"].read()
```

### 3. 批量操作
```python
# ✅ 正确
db.add_all(chunks)
await db.commit()

# ❌ 错误（太慢）
for chunk in chunks:
    db.add(chunk)
    await db.commit()
```

## 快速开始

```bash
# 1. 环境准备
source .venv/bin/activate  # 激活 uv 虚拟环境
cp env.example .env        # 配置环境变量

# 2. 启动服务
make install      # 安装依赖
make docker-up    # 启动 PostgreSQL + MinIO
make upgrade      # 数据库迁移
make dev          # 启动开发服务器

# 3. 常用命令
make test         # 运行测试
make lint         # 代码检查
make format       # 格式化
```

## 重要配置（.env）

```bash
# 数据库
POSTGRES_HOST=localhost
POSTGRES_DB=ragserver

# 对象存储
MINIO_HOST=localhost

# API 密钥（必须配置）
SILICONFLOW_API_KEY=sk-xxx

# JWT
JWT_SECRET_KEY=xxx
```

## 参考文档

- `PRD.md` - 产品需求和完整功能说明
- `ER.md` - 数据模型详细定义
- `Makefile` - 所有可用命令

