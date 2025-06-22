[English](./README.md)

# RagBackend (中文)

RagBackend 是一个基于 FastAPI 构建的 RAG (Retrieval-Augmented Generation) 服务, 提供了一个用于管理集合和文档的 REST API，并使用 PostgreSQL 和 pgvector 进行向量存储。

## TODO


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
- Python 3.11 或更高版本

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
