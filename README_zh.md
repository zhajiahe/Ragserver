[English](./README.md)

# RagBackend (中文)

RagBackend 是一个基于 FastAPI 构建的 RAG (Retrieval-Augmented Generation) 服务, 提供了一个用于管理集合和文档的 REST API，并使用 PostgreSQL 和 pgvector 进行向量存储。

## TODO

### 第一阶段：基础设施 ✅
- [x] 实现配置管理 (`config.py`)
- [x] 实现数据库连接和模型定义
- [x] 实现基础 FastAPI 应用和服务器配置 (`server.py`)
- [x] 实现健康检查 API

### 第二阶段：核心功能
- [x] 实现集合管理 API 和数据库操作
- [ ] 实现文件上传 API，集成 MinIO 服务
- [ ] 实现文档处理服务（解析、分块、向量化）
- [ ] 实现向量搜索功能

### 第三阶段：功能完善
- [ ] 错误处理和日志记录
- [ ] 文档处理异步任务处理
- [ ] API 文档完善和测试
- [ ] 性能优化

### 支持特性
- [x] 多种文档格式支持 (TXT, PDF, MD, DOCX 等)
- [x] 多种嵌入模型支持：
  - [x] Ollama（本地部署）
  - [x] OpenAI API
  - [x] 硅基流动（免费 API）
- [x] 每个集合动态创建向量表
- [ ] 异步文档处理
- [x] Docker Compose 容器化部署

## 特性
- 基于 FastAPI 的 REST API
- 使用 PostgreSQL 和 pgvector 进行文档存储和向量嵌入
- 支持 Docker，方便部署
- 与 MinIO 集成的文件存储
- 多格式文档处理（TXT, PDF, MD, DOCX 等）
- 向量相似度语义搜索
- 实时文档索引和检索
- 多种嵌入选项：Ollama（本地）、硅基流动（免费API）、OpenAI

## 快速开始

### 环境要求

- Docker 和 Docker Compose
- Python 3.12 或更高版本

### 使用 Docker 运行

1. 克隆仓库:
   ```bash
   # 替换为你的仓库 URL
   git clone https://github.com/zhajiahe/RagBackend.git
   cd RagBackend
   ```

2. 启动服务:
   ```bash
   docker-compose up -d
   ```

   这将：
   - 启动一个带有 pgvector 扩展的 PostgreSQL 数据库
   - 构建并启动 RagBackend API 服务

3. 访问 API:
   - API 文档: http://localhost:8080/docs
   - 健康检查: http://localhost:8080/health
   - MinIO 管理控制台（文件管理）: http://localhost:9001 (minioadmin/minioadmin123)

### 开发模式

要在开发模式下运行服务并启用实时重新加载：

```bash
docker-compose up
```

## 开始使用
新建集合(自动新建vectorstore表) -> 上传文件(存入minio、解析、分块、存入vectorstore) -> 向量查询

## API 接口

### 集合管理
- `POST /collections` - 创建新集合
- `GET /collections` - 列出所有集合
- `GET /collections/{id}` - 获取集合详情
- `DELETE /collections/{id}` - 删除集合

### 文件管理
- `POST /collections/{id}/files` - 上传文件到集合
- `GET /collections/{id}/files` - 列出集合中的文件
- `DELETE /files/{id}` - 删除文件

### 搜索
- `POST /collections/{id}/search` - 执行向量相似度搜索

### 系统
- `GET /health` - 健康检查接口

## 配置说明

复制 `.env.example` 到 `.env` 并配置：

```bash
# 嵌入模型配置
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_EMBED_MODEL=bge-m3
SILICONFLOW_API_KEY=your_api_key
OPENAI_API_KEY=your_api_key

# 数据库配置
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER=postgres
POSTGRES_PASSWORD=password
POSTGRES_DB=postgres

# MinIO 配置
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin123
MINIO_BUCKET_NAME=ragbackend-documents
```

## 系统架构

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   FastAPI App   │    │   PostgreSQL    │    │     MinIO       │
│                 │    │   + pgvector    │    │   文件存储      │
│  - REST API     │◄──►│  - 集合表       │    │  - 文档         │
│  - 文档处理     │    │  - 文件表       │    │  - 元数据       │
│                 │    │  - 向量表       │    │                 │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```
