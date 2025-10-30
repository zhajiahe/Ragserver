# 知识库分享功能更新日志

## 更新时间
2025-10-30

## 变更概述
移除了复杂的 API Key 管理系统，改用更简单的知识库分享链接方式。

## 数据库变更

### 删除的表
- `api_keys` - API密钥表
- `api_usage_logs` - API使用日志表

### 新增的表
- `collection_shares` - 知识库分享表

#### collection_shares 表结构
```sql
CREATE TABLE collection_shares (
    id UUID PRIMARY KEY,
    collection_id UUID NOT NULL REFERENCES collections(id) ON DELETE CASCADE,
    created_by UUID NOT NULL REFERENCES users(id),
    share_token VARCHAR(64) UNIQUE NOT NULL,
    name VARCHAR(100) NOT NULL,
    description VARCHAR(500),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    expires_at TIMESTAMPTZ,
    usage_count INTEGER DEFAULT 0,
    last_used_at TIMESTAMPTZ,
    search_config JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL
);

-- 索引
CREATE INDEX idx_share_token ON collection_shares(share_token);
CREATE INDEX idx_share_kb ON collection_shares(collection_id);
CREATE INDEX idx_share_creator ON collection_shares(created_by);
CREATE INDEX idx_share_active ON collection_shares(is_active);
```

## 代码变更

### 1. 模型变更 (`ragserver/app/models.py`)

**删除的模型:**
- `APIKey`
- `APIUsageLog`

**新增的模型:**
- `CollectionShare`

**修改的关系:**
- `User.api_keys` → 删除
- `User.api_usage_logs` → 删除
- `User.collection_shares` → 新增
- `Collection.shares` → 新增

### 2. API 接口变更 (`ragserver/app/api/collections.py`)

**新增接口:**

#### 创建分享链接
```
POST /api/v1/collections/{collection_id}/share
```
**请求体:**
```json
{
  "name": "分享名称",
  "description": "分享描述（可选）",
  "expires_in_days": 30,  // 可选，不设置则永久有效
  "search_config": {
    "max_top_k": 20
  }
}
```
**响应:**
```json
{
  "id": "uuid",
  "collection_id": "uuid",
  "share_token": "kb_share_xxx",
  "share_url": "http://localhost:8000/api/v1/share/kb_share_xxx/search",
  "name": "分享名称",
  "description": "描述",
  "is_active": true,
  "expires_at": "2025-11-30T00:00:00Z",
  "usage_count": 0,
  "last_used_at": null,
  "search_config": {},
  "created_at": "2025-10-30T10:00:00Z",
  "updated_at": "2025-10-30T10:00:00Z"
}
```

#### 获取分享列表
```
GET /api/v1/collections/{collection_id}/shares?skip=0&limit=50
```

#### 删除分享链接
```
DELETE /api/v1/collections/{collection_id}/shares/{share_id}
```

#### 切换分享状态
```
PUT /api/v1/collections/{collection_id}/shares/{share_id}/toggle
```

### 3. 搜索接口 (`ragserver/app/api/search.py`)

**新增接口:**

#### 认证搜索（需要登录）
```
POST /api/v1/search
Authorization: Bearer <jwt_token>

{
  "query": "搜索内容",
  "top_k": 10,
  "threshold": 0.7,
  "collection_ids": ["uuid1", "uuid2"]  // 可选
}
```

#### 分享链接搜索（无需登录）
```
POST /api/v1/share/{share_token}/search

{
  "query": "搜索内容",
  "top_k": 10,
  "threshold": 0.7
}
```

**说明:**
- 无需 JWT 认证
- 自动应用分享配置的限制（如 max_top_k）
- 检查分享链接是否激活和过期
- 自动更新使用统计

## 数据迁移

### 迁移文件
```
ragserver/alembic/versions/e841d98e7989_移除api_key和api_usage_log_添加collection_.py
```

### 执行迁移
```bash
# 激活环境
source .venv/bin/activate

# 执行迁移
alembic upgrade head
```

## 配置项

需要确保在 `.env` 或配置文件中设置：
```bash
API_BASE_URL=http://localhost:8000
```

## 使用示例

### 1. 创建分享链接
```python
import httpx

# 登录获取 token
response = httpx.post("http://localhost:8000/api/v1/auth/login", json={
    "username": "user@example.com",
    "password": "password"
})
token = response.json()["access_token"]

# 创建分享
response = httpx.post(
    "http://localhost:8000/api/v1/collections/{collection_id}/share",
    headers={"Authorization": f"Bearer {token}"},
    json={
        "name": "公开分享",
        "description": "这是一个公开的知识库",
        "expires_in_days": 30,
        "search_config": {
            "max_top_k": 20
        }
    }
)
share_data = response.json()
share_url = share_data["share_url"]
print(f"分享链接: {share_url}")
```

### 2. 使用分享链接搜索
```python
# 无需登录，直接搜索
response = httpx.post(share_url, json={
    "query": "如何使用 FastAPI？",
    "top_k": 5
})
results = response.json()
```

## 优势对比

### 旧方案（API Key）
- ❌ 需要管理 API Key 的生成、存储、验证
- ❌ 需要处理配额、速率限制
- ❌ 需要记录详细的使用日志
- ❌ 复杂的权限控制（scopes）
- ❌ 用户体验不友好（需要配置 API Key）

### 新方案（分享链接）
- ✅ 一键生成分享链接
- ✅ 简单的启用/停用控制
- ✅ 可选的过期时间
- ✅ 基础的使用统计
- ✅ 用户体验友好（点击链接即可使用）
- ✅ 适合快速分享和协作

## 注意事项

1. **安全性**: 分享链接是公开的，任何获得链接的人都可以搜索。建议：
   - 设置合理的过期时间
   - 使用 `is_active` 控制临时禁用
   - 通过 `search_config` 限制查询范围

2. **性能**: 分享链接会自动更新使用统计，频繁使用时注意数据库写入压力

3. **向后兼容**: 此更新删除了 API Key 功能，如果现有系统依赖 API Key，需要迁移到分享链接

## TODO

- [ ] 实现向量搜索的具体逻辑（目前返回空结果）
- [ ] 添加分享链接的访问日志（可选）
- [ ] 添加分享链接的访问频率限制（可选）
- [ ] 前端界面实现

