# RAG Collection Server - AI Assistant 开发指南

> 本文档为 AI 代码助手（如 Cursor、GitHub Copilot、Cline等）提供项目开发指南。

## 项目概述

**项目名称**: AI知识库管理平台后端系统  
**技术栈**: FastAPI + PostgreSQL + pgvector + Redis + MinIO  
**主要功能**: 文档智能处理、向量检索、知识库管理、API服务

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
├── tests/ 测试脚本
├── app/
│   ├── models.py           # SQLAlchemy 数据模型
│   ├── api/
│   │   ├── files.py    #文件上传接口
│   │   ├── users.py    # 用户管理接口
│   │   ├── kb.py       # 知识库管理接口
│   │   ├── documents.py # 文档管理接口
│   │   └── search.py   # 搜索接口
│   ├── services/
│   │   ├── document_pipeline.py # 文档处理流水线
│   │   ├── embedding.py    # Embedding服务
│   │   ├── parser.py       # 文档解析服务
│   │   ├── chunking.py     # 分块服务
│   │   └── search.py       # 搜索服务
│   └── utils/
│       ├── minio_client.py # MinIO工具
│       └── redis_client.py # Redis工具
├── config.py               # 配置管理
├── database.py             # 数据库连接
└── main.py                 # FastAPI应用入口

```

## 数据模型设计

### 核心实体

参考 `ER.md` 了解完整的数据模型。关键实体：

1. **User** - 用户表
2. **Collection** - 知识库表
3. **Document** - 文档表
4. **DocumentChunk** - 文档分块表（含向量）
5. **APIKey** - API密钥表
6. **APIUsageLog** - API使用日志表

### 重要规则
- pass

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
# ✅ 正确：使用本地 bge-m3 模型
from FlagEmbedding import BGEM3FlagModel

class EmbeddingService:
    def __init__(self):
        self.model = BGEM3FlagModel(
            'BAAI/bge-m3',
            use_fp16=True,
            device=settings.embedding_device
        )
    
    async def encode(self, texts: List[str]) -> List[List[float]]:
        """生成向量"""
        # 使用线程池避免阻塞事件循环
        embeddings = await asyncio.to_thread(
            self.model.encode,
            texts,
            batch_size=settings.embedding_batch_size,
            max_length=8192
        )
        return embeddings['dense_vecs'].tolist()
```

### 7. 分块配置

```python
# ✅ 正确：从 JSONB 字段读取配置
async def get_chunking_config(kb: Collection, doc: Optional[Document] = None):
    """获取分块配置（文档级优先，知识库级备选）"""
    if doc and doc.chunking_config:
        return doc.chunking_config
    
    if kb.settings and 'chunking_config' in kb.settings:
        return kb.settings['chunking_config']
    
    # 默认配置
    return {
        "strategy_type": "paragraph",
        "config": {
            "max_chunk_size": 800,
            "min_chunk_size": 100,
            "merge_short_paragraphs": True
        }
    }
```

### 8. 向量搜索

```python
# ✅ 正确：使用 pgvector 的余弦相似度
from pgvector.sqlalchemy import Vector

async def search_chunks(
    db: AsyncSession,
    query_embedding: List[float],
    kb_id: UUID,
    user_id: UUID,
    top_k: int = 10,
    threshold: float = 0.7
):
    """向量搜索"""
    result = await db.execute(
        select(
            DocumentChunk,
            (1 - DocumentChunk.content_embedding.cosine_distance(query_embedding)).label('similarity')
        )
        .where(
            DocumentChunk.collection_id == kb_id,
            DocumentChunk.user_id == user_id,
            (1 - DocumentChunk.content_embedding.cosine_distance(query_embedding)) > threshold
        )
        .order_by(DocumentChunk.content_embedding.cosine_distance(query_embedding))
        .limit(top_k)
    )
    return result.all()
```

## 错误处理

```python
# ✅ 正确：使用 HTTPException
from fastapi import HTTPException, status

@router.delete("/{kb_id}")
async def delete_kb(kb_id: UUID, current_user: User = Depends(get_current_user)):
    kb = await get_kb(db, kb_id, current_user.id)
    if not kb:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Collection not found"
        )
    
    if kb.status == "archived":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete archived Collection"
        )
    
    await db.delete(kb)
    await db.commit()
    return {"message": "Collection deleted successfully"}
```

## 性能优化建议

### 1. 数据库查询优化

```python
# ✅ 正确：使用 joinedload 预加载关联
from sqlalchemy.orm import joinedload

result = await db.execute(
    select(Document)
    .options(joinedload(Document.collection))
    .where(Document.id == doc_id)
)
```

### 2. 批量操作

```python
# ✅ 正确：批量插入
chunks = [DocumentChunk(...) for ... in ...]
db.add_all(chunks)
await db.commit()

# ❌ 错误：逐个插入
for chunk in chunks:
    db.add(chunk)
    await db.commit()  # 太慢！
```

### 3. 缓存

```python
# ✅ 正确：使用 Redis 缓存热数据
from app.utils.redis_client import redis_client

# 缓存查询向量
cache_key = f"query_embedding:{query_hash}"
cached = await redis_client.get(cache_key)
if cached:
    return json.loads(cached)

embedding = await embedding_service.encode([query])
await redis_client.setex(
    cache_key,
    settings.query_vector_cache_ttl,
    json.dumps(embedding)
)
```

## 环境设置

```bash
# 1. 复制配置
cp env.example .env

# 2. 编辑配置（填入API密钥等）
vim .env

# 3. 安装依赖
make install

# 4. 启动基础设施（Docker）
make docker-up

# 5. 运行数据库迁移
make upgrade

# 6. 启动应用
make dev  # 开发模式
# 或
make start  # 生产模式（PM2）
```

## 常用命令

```bash
# 开发
make dev              # 启动开发服务器（热重载）
make test             # 运行测试
make lint             # 代码检查
make format           # 格式化代码

# 部署
make up               # 启动所有服务（Docker + PM2）
make down             # 停止所有服务
make restart          # 重启服务
make status           # 查看状态

# 数据库
make migrate msg="..." # 创建迁移
make upgrade          # 应用迁移
make downgrade        # 回滚迁移

# 清理
make clean            # 清理临时文件
make docker-clean     # 清理 Docker 数据
```

## 文档参考

- `PRD.md` - 产品需求文档
- `ER.md` - 数据模型文档
- `Makefile` - 构建命令
- `ragserver/config.py` - 配置定义

## 获取帮助

1. 查看文档：上述参考文档
2. 查看代码注释：所有关键函数都有详细注释
3. 运行 `make help` 查看可用命令

