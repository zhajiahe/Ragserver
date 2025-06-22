# RagBackend 第二阶段实现说明

## 🎯 实现功能概览

本次实现完成了RagBackend项目第二阶段的核心功能：

### ✅ 已实现功能

1. **文件上传API** - 支持多种文档格式上传到MinIO
2. **文档处理服务** - 解析、分块、向量化文档
3. **向量搜索功能** - 基于语义相似度的文档检索
4. **嵌入服务抽象层** - 支持Ollama、OpenAI、SiliconFlow

## 🏗️ 架构设计

### 数据流程
```
文件上传 → MinIO存储 → 文档解析 → 文本分块 → 向量化 → pgvector存储
                                                          ↓
查询文本 → 向量化 → pgvector搜索 → 结果排序 → 返回相关文档
```

### 核心组件

```
ragbackend/
├── api/
│   ├── files.py          # 文件上传API
│   └── documents.py      # 搜索API
├── services/
│   ├── embedding_service.py     # 嵌入服务抽象
│   └── document_processor.py    # 文档处理核心
└── database/
    └── vectors.py               # 向量操作
```

## 📋 API接口说明

### 文件管理

#### 1. 上传文件
```http
POST /collections/{collection_id}/files
Content-Type: multipart/form-data

file: 文件内容
```

**支持格式**：
- `text/plain` - 文本文件
- `application/pdf` - PDF文档
- `text/markdown` - Markdown文件
- `application/vnd.openxmlformats-officedocument.wordprocessingml.document` - Word文档
- `text/html` - HTML文件

**响应**：
```json
{
  "id": "file-uuid",
  "collection_id": "collection-uuid",
  "content": "文件 filename.txt 上传成功，正在处理中...",
  "metadata": {
    "filename": "filename.txt",
    "content_type": "text/plain",
    "size": 1024,
    "status": "processing"
  },
  "created_at": "2025-01-23T10:00:00Z",
  "updated_at": "2025-01-23T10:00:00Z"
}
```

#### 2. 获取集合文件列表
```http
GET /collections/{collection_id}/files
```

#### 3. 获取文件信息
```http
GET /files/{file_id}
```

#### 4. 删除文件
```http
DELETE /files/{file_id}
```

### 文档搜索

#### 1. 向量搜索
```http
POST /collections/{collection_id}/search
Content-Type: application/json

{
  "query": "搜索关键词",
  "limit": 10,
  "filter": {"key": "value"}  // 可选的元数据过滤
}
```

**响应**：
```json
[
  {
    "id": "vector-uuid",
    "page_content": "相关文档内容...",
    "metadata": {
      "filename": "source.txt",
      "chunk_index": 0
    },
    "score": 0.85
  }
]
```

#### 2. 获取集合统计
```http
GET /collections/{collection_id}/stats
```

**响应**：
```json
{
  "collection_id": "collection-uuid",
  "collection_name": "我的集合",
  "embedding_model": "bge-m3",
  "embedding_provider": "ollama",
  "total_vectors": 100,
  "unique_files": 5,
  "latest_created": "2025-01-23T10:00:00Z"
}
```

## 🔧 配置说明

### 环境变量

```bash
# 嵌入模型配置
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_EMBED_MODEL=bge-m3

SILICONFLOW_API_KEY=your_api_key
SILICONFLOW_MODEL=BAAI/bge-m3

OPENAI_API_KEY=your_api_key

# 文档处理配置
CHUNK_SIZE=1000
CHUNK_OVERLAP=200

# 默认嵌入模型
DEFAULT_EMBEDDING_MODEL=ollama  # ollama, openai, siliconflow
```

### 文档处理参数

- **CHUNK_SIZE**: 文档分块大小（默认1000字符）
- **CHUNK_OVERLAP**: 分块重叠大小（默认200字符）
- **MAX_FILE_SIZE**: 最大文件大小（10MB）

## 🚀 使用示例

### 1. 创建集合
```bash
curl -X POST "http://localhost:8080/collections/" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "我的文档集合",
    "description": "存储技术文档",
    "embedding_model": "bge-m3",
    "embedding_provider": "ollama"
  }'
```

### 2. 上传文件
```bash
curl -X POST "http://localhost:8080/collections/{collection_id}/files" \
  -F "file=@document.pdf"
```

### 3. 搜索文档
```bash
curl -X POST "http://localhost:8080/collections/{collection_id}/search" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "什么是RAG系统？",
    "limit": 5
  }'
```

## 🧪 测试指南

### 自动化测试

运行提供的测试脚本：

```bash
# 安装测试依赖
pip install aiohttp

# 确保RagBackend服务正在运行
python ragbackend/main.py

# 运行测试
python test_phase2_api.py
```

### 手动测试步骤

1. **启动服务**
   ```bash
   docker-compose up -d  # 启动数据库和MinIO
   python ragbackend/main.py  # 启动API服务
   ```

2. **创建集合**
   - 使用API或直接访问 http://localhost:8080/docs

3. **上传文档**
   - 支持PDF、Word、文本等多种格式
   - 文件会自动处理和向量化

4. **测试搜索**
   - 使用自然语言查询
   - 查看相似度分数和结果排序

## 🔍 技术特性

### 文档处理
- **多格式支持**：PDF、DOCX、TXT、MD、HTML
- **智能分块**：使用RecursiveCharacterTextSplitter
- **异步处理**：文件上传后后台处理
- **状态跟踪**：uploading → processing → completed/failed

### 向量化
- **多模型支持**：Ollama、OpenAI、SiliconFlow
- **批量处理**：提高处理效率
- **动态选择**：根据集合配置自动选择嵌入模型

### 搜索功能
- **语义搜索**：基于向量相似度
- **元数据过滤**：支持条件过滤
- **分数排序**：相似度从高到低排序
- **结果限制**：防止返回过多结果

### 数据库设计
- **动态表创建**：每个集合对应一个向量表
- **安全表名**：防止SQL注入
- **向量索引**：使用ivfflat索引优化搜索性能

## 🐛 常见问题

### 1. 文件上传失败
- 检查文件格式是否支持
- 确认文件大小未超过限制（10MB）
- 验证MinIO服务是否正常运行

### 2. 文档处理失败
- 查看服务日志获取详细错误信息
- 确认嵌入服务（Ollama等）可用
- 检查临时文件目录权限

### 3. 搜索无结果
- 确认文档已处理完成（status=completed）
- 检查查询文本是否为空
- 验证集合中是否有向量数据

### 4. 向量维度不匹配
- 确保集合使用的嵌入模型一致
- 重新创建集合或重新索引文档

## 📈 性能优化建议

1. **批量处理**：一次上传多个文件比单个文件更高效
2. **合理分块**：根据文档类型调整CHUNK_SIZE
3. **索引优化**：定期VACUUM和ANALYZE向量表
4. **缓存嵌入**：对于重复查询可以考虑缓存向量结果

## 🔮 下一步计划

- [ ] 实现重新索引功能
- [ ] 添加文档更新API
- [ ] 支持更多文档格式
- [ ] 实现用户认证和权限管理
- [ ] 添加搜索结果高亮
- [ ] 优化大文件处理性能

---

**开发完成时间**: 2025年1月23日  
**测试状态**: ✅ 已通过基本功能测试  
**部署状态**: 🟡 开发环境就绪，生产环境待优化 