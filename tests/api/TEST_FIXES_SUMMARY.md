# 文档集成测试修复总结

## 修复日期
2025-10-30

## 修复内容

### 1. MinIO 客户端修复 (`ragserver/app/utils/minio_client.py`)

**问题**: 缺少 `_calculate_sha256` 方法，导致文件上传时报错。

**修复**: 添加了 SHA256 哈希计算方法：

```python
def _calculate_sha256(self, file_content: bytes) -> str:
    """计算文件内容的 SHA256 值"""
    return hashlib.sha256(file_content).hexdigest()
```

### 2. 测试文件修复 (`tests/api/test_documents_integration.py`)

#### 2.1 文件上传格式修正

**问题**: 文件上传使用了错误的格式（字典格式），与 FastAPI 的 `List[UploadFile]` 不匹配。

**修复前**:
```python
files = {
    "files": ("test.txt", BytesIO(b"Hello World"), "text/plain")
}
```

**修复后**:
```python
files = [
    ("files", ("test.txt", BytesIO(b"Hello World"), "text/plain"))
]
```

#### 2.2 Document 模型字段修正

**问题**: 测试代码使用了不存在的 `file_path` 字段，实际模型使用的是 `s3_url`。

**修复**: 将所有 `file_path` 替换为 `s3_url`：

```python
# 修复前
doc = Document(
    file_path="path/test.txt",
    ...
)

# 修复后
doc = Document(
    s3_url="http://minio:9000/documents/path/test.txt",
    ...
)
```

#### 2.3 文档更新测试修正

**问题**: Document 模型没有 `language` 字段，该字段应该存储在 `meta` 中。

**修复前**:
```python
update_data = {
    "chunking_config": {"max_chunk_size": 500},
    "language": "en",
}
assert result["language"] == "en"
```

**修复后**:
```python
update_data = {
    "chunking_config": {"max_chunk_size": 500},
    "meta": {"language": "en"},
}
assert result["meta"]["language"] == "en"
```

#### 2.4 未认证测试修正

**问题**: 缺少 `setup_db` fixture，导致数据库依赖注入未正确设置。

**修复**: 添加 `setup_db` 参数：

```python
async def test_upload_without_auth(
    self, 
    async_client: AsyncClient, 
    db_session: AsyncSession, 
    setup_db  # 添加此参数
):
```

## 测试结果

✅ **所有 18 个测试全部通过**

```
tests/api/test_documents_integration.py::TestDocumentUpload::test_upload_single_document PASSED
tests/api/test_documents_integration.py::TestDocumentUpload::test_upload_multiple_documents PASSED
tests/api/test_documents_integration.py::TestDocumentUpload::test_upload_without_auth PASSED
tests/api/test_documents_integration.py::TestDocumentUpload::test_upload_to_nonexistent_kb PASSED
tests/api/test_documents_integration.py::TestDocumentList::test_get_document_list PASSED
tests/api/test_documents_integration.py::TestDocumentList::test_get_document_list_with_status_filter PASSED
tests/api/test_documents_integration.py::TestDocumentList::test_get_document_list_with_pagination PASSED
tests/api/test_documents_integration.py::TestDocumentDetail::test_get_document_detail PASSED
tests/api/test_documents_integration.py::TestDocumentDetail::test_get_document_detail_not_found PASSED
tests/api/test_documents_integration.py::TestDocumentUpdate::test_update_document_config PASSED
tests/api/test_documents_integration.py::TestDocumentDelete::test_delete_documents PASSED
tests/api/test_documents_integration.py::TestDocumentDelete::test_delete_empty_list PASSED
tests/api/test_documents_integration.py::TestDocumentProcess::test_process_documents PASSED
tests/api/test_documents_integration.py::TestDocumentProcess::test_reprocess_documents PASSED
tests/api/test_documents_integration.py::TestDocumentStatus::test_get_document_status PASSED
tests/api/test_documents_integration.py::TestDocumentChunks::test_get_document_chunks PASSED
tests/api/test_documents_integration.py::TestDocumentChunks::test_get_document_chunks_pagination PASSED
tests/api/test_documents_integration.py::TestDocumentPermissions::test_cannot_access_other_user_document PASSED

============================== 18 passed in 6.64s ==============================
```

## 测试覆盖范围

### 文档上传 (TestDocumentUpload)
- ✅ 单文件上传
- ✅ 批量文件上传
- ✅ 未认证用户上传（401）
- ✅ 上传到不存在的知识库（404）

### 文档列表 (TestDocumentList)
- ✅ 获取文档列表
- ✅ 按状态过滤
- ✅ 分页功能

### 文档详情 (TestDocumentDetail)
- ✅ 获取文档详情
- ✅ 获取不存在的文档（404）

### 文档更新 (TestDocumentUpdate)
- ✅ 更新文档配置（chunking_config 和 meta）

### 文档删除 (TestDocumentDelete)
- ✅ 批量删除文档
- ✅ 删除空列表（400）

### 文档处理 (TestDocumentProcess)
- ✅ 批量处理文档（Mock）
- ✅ 重新处理文档（Mock）

### 文档状态 (TestDocumentStatus)
- ✅ 查询文档处理状态

### 文档分块 (TestDocumentChunks)
- ✅ 获取文档分块列表
- ✅ 分块分页

### 权限控制 (TestDocumentPermissions)
- ✅ 用户无法访问其他用户的文档

## 关键修复点总结

1. **MinIO 客户端**: 添加缺失的 SHA256 哈希计算方法
2. **文件上传格式**: 从字典格式改为列表格式，符合 FastAPI 规范
3. **数据模型字段**: 统一使用 `s3_url` 而非 `file_path`
4. **元数据存储**: `language` 等自定义字段存储在 `meta` JSONB 字段中
5. **测试隔离**: 确保所有测试都正确使用 `setup_db` fixture

## 后续建议

1. 考虑添加文件上传大小限制测试
2. 添加不支持的文件类型测试
3. 添加并发上传测试
4. 实现真实的文档处理任务（目前是 Mock）
5. 实现 MinIO 文件删除功能（目前标记为 TODO）

