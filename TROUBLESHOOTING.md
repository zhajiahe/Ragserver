# RAG系统故障排除指南

## 🔧 快速诊断

如果你遇到搜索结果为0的问题，请按以下步骤排查：

### 1. 运行诊断脚本

```bash
python debug_rag_pipeline.py
```

这个脚本会自动检查所有组件的状态。

### 2. 常见问题及解决方案

#### 问题1: Ollama服务未运行

**症状**: 嵌入服务错误，连接失败
**解决方案**:
```bash
# 启动Ollama服务
ollama serve

# 在另一个终端安装bge-m3模型
ollama pull bge-m3
```

#### 问题2: MinIO服务未运行

**症状**: 文件上传失败，MinIO连接错误
**解决方案**:
```bash
# 启动Docker服务
docker-compose up -d

# 检查服务状态
docker-compose ps
```

#### 问题3: 文档处理卡在"processing"状态

**症状**: 文件状态一直是"processing"，从不变为"completed"
**原因**: 
- Ollama模型未安装
- 嵌入服务API调用失败
- 异步任务异常退出

**解决方案**:
```bash
# 1. 检查Ollama模型
ollama list

# 2. 如果没有bge-m3，安装它
ollama pull bge-m3

# 3. 重启API服务
# 停止当前服务（Ctrl+C）然后重新启动
python ragbackend/main.py
```

#### 问题4: 向量表为空

**症状**: 统计信息显示0个向量
**检查方法**:
```sql
-- 连接到PostgreSQL检查
SELECT COUNT(*) FROM collection_xxx_vectors;
```

**解决方案**:
- 确保文档处理完成（状态为"completed"）
- 检查文档内容是否过短（少于chunk_size）
- 重新上传文件

#### 问题5: 搜索无结果但有向量数据

**症状**: 向量表有数据，但搜索返回空结果
**可能原因**:
- 查询向量化失败
- 相似度阈值过高
- 元数据过滤条件过严

**调试步骤**:
```bash
# 1. 测试简单查询
curl -X POST "http://localhost:8080/collections/{collection_id}/search" \
  -H "Content-Type: application/json" \
  -d '{"query": "测试", "limit": 10}'

# 2. 检查集合统计
curl "http://localhost:8080/collections/{collection_id}/stats"
```

### 3. 手动验证步骤

#### 步骤1: 检查基础服务

```bash
# 检查Ollama
curl http://localhost:11434/api/tags

# 检查API服务
curl http://localhost:8080/health

# 检查MinIO (可选，通过web界面)
# 访问 http://localhost:9001
```

#### 步骤2: 检查数据库状态

```bash
# 连接PostgreSQL
docker exec -it ragbackend-db-1 psql -U postgres -d postgres

# 检查表
\dt

# 检查集合
SELECT id, name, embedding_provider FROM collections;

# 检查文件
SELECT id, filename, status FROM files;

# 检查向量数据（替换collection_id）
SELECT COUNT(*) FROM collection_xxx_vectors;
```

#### 步骤3: 查看日志

```bash
# API服务日志（如果用docker运行）
docker-compose logs ragbackend

# 或者直接运行时的控制台输出
```

### 4. 重置和重试

如果问题仍然存在，可以重置环境：

```bash
# 1. 停止所有服务
docker-compose down

# 2. 清理数据（可选，会删除所有数据）
docker-compose down -v

# 3. 重新启动
docker-compose up -d

# 4. 重启API服务
python ragbackend/main.py
```

### 5. 环境变量检查

确保以下环境变量正确设置：

```bash
# .env文件内容示例
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_EMBED_MODEL=bge-m3
DEFAULT_EMBEDDING_MODEL=ollama

POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER=postgres
POSTGRES_PASSWORD=password
POSTGRES_DB=postgres

MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin123
MINIO_BUCKET_NAME=ragbackend-documents

CHUNK_SIZE=1000
CHUNK_OVERLAP=200
```

### 6. 性能调优

如果系统运行缓慢：

1. **调整分块大小**:
   ```bash
   CHUNK_SIZE=500  # 减少分块大小
   CHUNK_OVERLAP=100
   ```

2. **检查系统资源**:
   ```bash
   # 检查内存使用
   docker stats
   
   # 检查磁盘空间
   df -h
   ```

3. **优化数据库**:
   ```sql
   -- 手动创建向量索引（如果需要）
   CREATE INDEX IF NOT EXISTS idx_collection_xxx_vectors_embedding 
   ON collection_xxx_vectors USING ivfflat (embedding vector_cosine_ops);
   ```

## 🆘 寻求帮助

如果以上步骤都无法解决问题，请：

1. 运行诊断脚本并保存输出
2. 收集API服务日志
3. 记录具体的错误信息和复现步骤
4. 提供系统环境信息（OS、Python版本、Docker版本等）

## 📝 调试技巧

### 启用详细日志

在代码中添加更多日志：

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### 测试单个组件

```python
# 测试嵌入服务
from ragbackend.services.embedding_service import get_embedding_service
import asyncio

async def test():
    service = await get_embedding_service("ollama")
    result = await service.embed_query("测试文本")
    print(f"向量维度: {len(result)}")

asyncio.run(test())
```

### 手动处理文档

```python
# 手动测试文档处理
from ragbackend.services.document_processor import get_document_processor
import asyncio

async def test():
    processor = get_document_processor()
    success = await processor.process_file("your-file-id")
    print(f"处理结果: {success}")

asyncio.run(test())
``` 