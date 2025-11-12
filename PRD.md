## AI知识库管理平台 PRD

### 一、产品概述

#### 1.1 产品定位
企业级知识库管理平台后端系统，支持智能文档处理、灵活的权限控制和API服务能力。
总结来说，是一个支持多用户的知识库后端，支持知识库创建、文档上传解析、检索的能力，并支持知识库搜索接口分享，是一个RAG系统必不可少的一个部分。

#### 1.2 核心价值
- **智能文档处理**：支持多格式文档解析，包括OCR识别
- **灵活分块策略**：内置多种分块策略
- **高效检索**：基于向量的语义搜索
- **开放API**：支持针对知识库搜索的API服务
- **私有化部署**：基于Docker的完整部署方案

#### 1.3 技术栈

| 组件类别 | 技术选型 | 版本/说明 |
|---------|---------|----------|
| **后端框架** | FastAPI | 异步高性能框架 |
| **数据库** | PostgreSQL + pgvector | 关系型数据库 + 向量扩展（HNSW索引） |
| **对象存储** | MinIO | S3兼容的开源对象存储 |
| **Embedding** | SiliconFlow API | BGE-M3 (1024维) |
| **LLM** | SiliconFlow API | Qwen3-8B |
| **文档解析** | unstructured / pdfminer / python-docx / BeautifulSoup4 | 多格式文档解析 |
| **OCR解析** | DeepSeek OCR API | 高精度图片文字识别 |
| **日志监控** | fastapi-radar + loguru | 性能监控和日志管理 |
| **数据库迁移** | Alembic | 数据库版本控制 |
| **部署** | Docker | 容器化 |

---

### 数据模型和接口设计

#### 2.1 核心数据模型

基于业务需求，系统设计了以下核心数据实体：

##### 2.1.1 用户管理 (User)
- **用户身份**: 支持多用户系统，每个用户拥有独立的数据空间
- **基本信息**: 用户名、邮箱、密码、头像、全名
- **配置管理**: JSONB格式存储用户个性化设置
- **权限控制**: 超级用户标志、激活状态
- **统计信息**: 存储使用量、API调用次数
- **关联关系**: 用户拥有的知识库、上传的文档、API密钥等

##### 2.1.2 知识库管理 (Collection)
- **知识库概念**: 用户可创建多个知识库，每个知识库是独立的文档集合
- **基本信息**: 名称、描述、图标URL
- **状态管理**: 活跃/归档状态控制
- **统计信息**: 文档数量、总大小、分块数量、最后更新时间
- **灵活配置**: JSONB格式存储知识库级设置（如分块策略、Embedding配置等）
- **数据隔离**: 严格按用户ID隔离，确保数据安全

##### 2.1.3 文档管理 (Document)
- **多格式支持**: PDF、DOCX、TXT、HTML、XLSX等格式
- **文件存储**: 使用MinIO对象存储，支持大文件处理
- **处理流程**: 待处理→处理中→已完成→失败，支持进度跟踪
- **内容提取**: 自动提取文本内容并转换为Markdown格式
- **OCR集成**: 支持图片型PDF的OCR文字识别
- **分块配置**: 支持文档级自定义分块策略，覆盖知识库默认设置

##### 2.1.4 文档分块 (DocumentChunk)
- **智能分块**: 支持多种分块策略（段落、句子、固定长度等）
- **向量存储**: 1024维BGE-M3向量，支持语义搜索
- **内容优化**: 支持生成块摘要，提升检索效果
- **层级结构**: 支持父子块关系，实现层级分块
- **索引优化**: 支持HNSW


#### 2.2 接口设计原则

##### 2.2.1 RESTful API设计
- **版本控制**: 使用/api前缀进行版本管理
- **资源导向**: 以资源为中心设计URL结构
- **HTTP方法**: 严格遵循GET/POST/PUT/DELETE语义
- **状态码**: 使用标准HTTP状态码表示操作结果

##### 2.2.2 数据验证与序列化
- **Pydantic模型**: 使用Pydantic进行请求/响应数据验证
- **类型安全**: 全面使用Python类型提示
- **自动文档**: 基于OpenAPI自动生成API文档
- **错误处理**: 统一的错误响应格式

##### 2.2.3 安全设计
- **身份认证**: JWT Token认证机制
- **权限控制**: 基于角色的访问控制(RBAC)
- **数据隔离**: 所有查询必须包含用户ID过滤
- **输入验证**: 严格的输入数据验证和清理

##### 2.2.4 文档处理
- **异步API**: 所有API端点支持异步处理
- **流水线处理**: 使用简单的流水线处理文档解析、分块、向量生成
- **进度跟踪**: 支持文档处理的实时进度查询
- **错误处理**: 完善的错误处理和状态更新机制

#### 2.3 核心接口列表

##### 2.3.1 用户认证接口 (`/api/v1/auth`)
- `POST /auth/register` - 用户注册
- `POST /auth/login` - 用户登录
- `GET /auth/me` - 获取当前用户信息

##### 2.3.2 知识库管理接口 (`/api/v1/collections`)
- `GET /collections` - 获取知识库列表（分页、筛选）
- `POST /collections` - 创建知识库
- `GET /collections/{id}` - 获取知识库详情
- `PUT /collections/{id}` - 更新知识库信息
- `DELETE /collections/{id}` - 删除知识库
- `POST /collections/{id}/archive` - 归档知识库
- `GET /collections/{id}/statistics` - 获取知识库统计信息

##### 2.3.3 文档管理接口 (`/api/v1/collections/{kb_id}/documents`)
- `GET /collections/{kb_id}/documents` - 获取文档列表（分页、筛选）
- `POST /collections/{kb_id}/documents/upload` - 上传文档（支持批量）
- `GET /documents/{id}` - 获取文档详情
- `PUT /documents/{id}` - 更新文档配置（分块配置、元数据）
- `DELETE /documents` - 批量删除文档
- `GET /documents/{id}/chunks` - 获取文档分块列表

##### 2.3.4 文档解析接口 (`/api/v1/documents`)
- `POST /documents/process` - 批量处理文档（解析、分块、向量化）
- `POST /documents/{id}/reprocess` - 重新处理单个文档
- `GET /documents/{id}/status` - 查询文档处理状态

##### 2.3.5 分块查询接口 (`/api/v1/chunks`)
- `GET /chunks` - 查询分块列表（支持按知识库、文档筛选）
- `GET /chunks/{id}` - 获取分块详情
- `GET /collections/{kb_id}/chunks` - 获取知识库所有分块
- `GET /documents/{doc_id}/chunks` - 获取文档所有分块

##### 2.3.6 搜索接口 (`/api/v1/search`)
- `POST /search` - 知识库搜索
  - 支持向量搜索 (Vector)
  - 支持全文搜索 (Fulltext/BM25)
  - 支持混合搜索 (Hybrid)
  - 支持多知识库搜索
  - 支持相似度阈值和Top-K配置

##### 2.3.7 知识库分享接口 (`/api/v1/shares`)
- `POST /collections/{collection_id}/share` - 创建知识库分享链接
- `GET /shares` - 获取用户的所有分享链接
- `GET /shares/{share_token}` - 获取分享链接详情
- `PUT /shares/{share_id}` - 更新分享链接配置
- `DELETE /shares/{share_id}` - 删除分享链接
- `POST /shares/{share_token}/search` - 通过分享链接搜索（无需认证）

---

### 三、核心功能详解

#### 3.1 文档解析支持

系统支持多种文档格式的智能解析：

| 文档类型 | 支持格式 | 解析器 | 说明 |
|---------|---------|--------|------|
| **文本文档** | txt, md | TextParser | 自动检测编码（UTF-8/GBK/GB2312） |
| **PDF文档** | pdf | PDFParser | 基于pdfminer.six，支持文字型PDF |
| **Word文档** | docx, doc | DocxParser | 基于python-docx，保留格式 |
| **HTML网页** | html, htm | HTMLParser | 基于BeautifulSoup4，提取纯文本 |
| **Excel表格** | xlsx, xls, csv | ExcelParser | 基于pandas，表格转Markdown |
| **PPT演示** | pptx | PPTParser | 基于python-pptx，提取文本内容 |
| **图片文档** | jpg, png | ImageParser | 集成DeepSeek OCR API识别文字 |

#### 3.2 文本分块策略

支持三种分块策略，适应不同场景需求：

##### 3.2.1 固定大小分块 (Fixed)
- **适用场景**: 通用文档、长文本
- **特点**: 固定chunk_size，支持overlap重叠
- **配置参数**:
  ```json
  {
    "strategy_type": "fixed",
    "config": {
      "chunk_size": 1000,
      "chunk_overlap": 200,
      "min_chunk_size": 100
    }
  }
  ```

##### 3.2.2 段落分块 (Paragraph)
- **适用场景**: 结构化文档、文章、论文
- **特点**: 按段落分割，智能合并短段落
- **配置参数**:
  ```json
  {
    "strategy_type": "paragraph",
    "config": {
      "chunk_size": 1000,
      "chunk_overlap": 0,
      "min_chunk_size": 100
    }
  }
  ```

##### 3.2.3 语义分块 (Semantic)
- **适用场景**: 需要高精度语义完整性的场景
- **特点**: 基于向量相似度聚合，保证语义连贯
- **配置参数**:
  ```json
  {
    "strategy_type": "semantic",
    "config": {
      "chunk_size": 1000,
      "similarity_threshold": 0.75,
      "min_chunk_size": 100
    }
  }
  ```

#### 3.3 向量检索技术

##### 3.3.1 Embedding 模型
- **模型**: BAAI/bge-m3 (1024维)
- **提供商**: SiliconFlow API
- **特点**: 
  - 支持中英文双语
  - 高精度语义理解
  - 批量处理优化

##### 3.3.2 向量索引
- **数据库**: PostgreSQL + pgvector扩展
- **索引类型**: HNSW (Hierarchical Navigable Small World)
- **索引参数**:
  - `m = 16`: 每个节点的连接数
  - `ef_construction = 64`: 构建时的搜索深度
- **距离度量**: 余弦相似度 (cosine distance)

##### 3.3.3 搜索模式

**1. 向量搜索 (Vector Search)**
- 基于语义相似度的检索
- 支持相似度阈值过滤
- 适合语义理解场景

**2. 全文搜索 (Fulltext Search)**
- 基于BM25算法的关键词匹配
- 支持SQL LIKE和正则表达式
- 适合精确关键词查找

**3. 混合搜索 (Hybrid Search)**
- 结合向量搜索和全文搜索
- 支持权重配置 (vector_weight + fulltext_weight)
- 适合综合检索场景
- 评分公式: `score = vector_weight × vector_score + fulltext_weight × fulltext_score`

#### 3.4 知识库分享机制

##### 3.4.1 分享链接特性
- **唯一令牌**: 生成格式为 `kb_share_xxxxx` 的分享令牌
- **无需认证**: 通过分享链接可直接访问搜索接口
- **可配置性**: 
  - 设置过期时间
  - 限制搜索配置（top_k、threshold）
  - 启用/禁用控制
- **使用统计**: 记录访问次数和最后使用时间

##### 3.4.2 使用流程
```
1. 用户创建分享链接 → 生成 share_token
2. 分享 token 给第三方 → https://api.example.com/shares/{token}
3. 第三方通过 token 搜索 → POST /shares/{token}/search
4. 系统记录使用统计 → usage_count++, last_used_at更新
```

---

### 四、部署架构

#### 4.1 服务组件

| 组件 | 说明 | 端口 | 备注 |
|------|------|------|------|
| **FastAPI 应用** | 主应用服务 | 8000 | Uvicorn ASGI服务器 |
| **PostgreSQL** | 主数据库 | 5432 | Docker容器 |
| **MinIO** | 对象存储 | 9000/9001 | Docker容器 |
| **Nginx** | 反向代理（可选） | 80/443 | 生产环境推荐 |

#### 4.2 环境要求

- Python >= 3.12
- PostgreSQL >= 15 (需安装pgvector扩展)
- Docker & Docker Compose
- 系统: Linux/macOS/Windows

#### 4.3 核心配置项

```bash
# 数据库配置
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER=ragserver
POSTGRES_PASSWORD=***
POSTGRES_DB=ragserver

# MinIO配置
MINIO_HOST=localhost
MINIO_PORT=9000
MINIO_ACCESS_KEY=ragserver
MINIO_SECRET_KEY=***

# SiliconFlow API
SILICONFLOW_API_KEY=***
SILICONFLOW_API_BASE=https://api.siliconflow.cn/v1

# JWT认证
JWT_SECRET_KEY=***
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=1440

# 向量配置
DEFAULT_EMBEDDING_MODEL=BAAI/bge-m3
EMBEDDING_DIMENSION=1024
EMBEDDING_BATCH_SIZE=50
```

---

### 五、开发与测试

#### 5.1 快速开始

```bash
# 1. 克隆项目
git clone <repository>
cd Ragserver

# 2. 环境配置
cp env.example .env
# 编辑 .env 填入配置

# 3. 安装依赖（使用uv）
make install

# 4. 启动基础设施
make docker-up

# 5. 数据库迁移
make upgrade

# 6. 启动开发服务器
make dev
```

#### 5.2 API 文档

启动服务后访问：
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
- OpenAPI JSON: http://localhost:8000/openapi.json

#### 5.3 测试

```bash
# 运行所有测试
make test

# 运行特定测试文件
pytest tests/api/test_collections.py -v

# 运行带覆盖率的测试
pytest --cov=ragserver tests/
```

---

### 六、性能与扩展

#### 6.1 性能指标

- 文档上传: 支持单次最大100MB
- 分块处理: 约1000字符/秒
- 向量生成: 批量50条/次（可配置）
- 向量搜索: <100ms (HNSW索引)
- 并发支持: 依赖硬件和配置

#### 6.2 扩展能力

- 支持水平扩展（多实例 + 负载均衡）
- PostgreSQL 主从复制
- MinIO 分布式部署
- 向量索引优化（调整HNSW参数）

#### 6.3 监控告警

- **fastapi-radar**: 实时性能监控Dashboard
- **loguru**: 结构化日志记录
- **数据库慢查询**: 可配置日志级别
- **MinIO监控**: 内置管理控制台