# 测试最佳实践

> 本文档为 AI 代码助手和开发者提供测试编写指南

## 快速开始

### 测试配置 (`pyproject.toml`)

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
asyncio_default_fixture_loop_scope = "function"
```

### 核心 Fixtures (`tests/conftest.py`)

```python
@pytest.fixture(scope="function")
async def db_session():
    """独立数据库会话（每个测试重建表）"""
    test_engine = create_async_engine(
        TEST_DATABASE_URL,
        poolclass=StaticPool,  # 避免并发冲突
    )
    
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    
    AsyncSessionLocal = async_sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    
    async with AsyncSessionLocal() as session:
        yield session
    
    await test_engine.dispose()


@pytest.fixture(scope="function")
async def async_client():
    """异步 HTTP 客户端"""
    from httpx import ASGITransport
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as client:
        yield client


@pytest.fixture
async def setup_db(db_session: AsyncSession):
    """依赖注入覆盖"""
    async def override_get_db():
        yield db_session
    
    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.clear()
```

---

## 编写测试

### ✅ 标准测试模板

```python
@pytest.mark.asyncio
async def test_example(
    async_client: AsyncClient,
    db_session: AsyncSession,
    setup_db
):
    """测试描述"""
    # 1. 准备数据
    payload = {"key": "value"}
    
    # 2. 调用 API
    res = await async_client.post("/api/v1/endpoint", json=payload)
    
    # 3. 验证响应
    assert res.status_code == 201
    data = res.json()
    assert data["key"] == "value"
    
    # 4. 验证数据库（可选）
    result = await db_session.execute(select(Model).where(...))
    obj = result.scalar_one()
    assert obj.field == "expected"
```

### 文件上传测试

```python
# ✅ 正确格式（列表）
files = [
    ("files", ("test.txt", BytesIO(b"content"), "text/plain"))
]
res = await async_client.post("/api/v1/upload", files=files)

# ❌ 错误格式（字典）
files = {"files": ("test.txt", BytesIO(b"content"), "text/plain")}
```

### 认证测试

```python
# 1. 创建用户
user = User(
    username="testuser",
    hashed_password=get_password_hash("Pass123!"),
    is_active=True,
)
db_session.add(user)
await db_session.commit()

# 2. 获取 token
token = create_access_token(str(user.id))
async_client.headers = {"Authorization": f"Bearer {token}"}

# 3. 访问受保护端点
res = await async_client.get("/api/v1/protected")
```

---

## 常见错误

### ❌ 错误 1: 使用同步客户端

```python
# 错误
from fastapi.testclient import TestClient
client = TestClient(app)

# 正确
async_client = AsyncClient(...)
res = await async_client.post(...)
```

### ❌ 错误 2: 忘记 await

```python
# 错误
res = async_client.post("/api/v1/endpoint", json=payload)

# 正确
res = await async_client.post("/api/v1/endpoint", json=payload)
```

### ❌ 错误 3: 数据模型字段错误

```python
# 错误（Document 模型没有 file_path 字段）
doc = Document(file_path="path/file.txt", ...)

# 正确（使用 s3_url）
doc = Document(s3_url="http://minio:9000/bucket/path/file.txt", ...)
```

### ❌ 错误 4: 时区问题

```python
# 错误（naive datetime）
created_at = datetime.now()

# 正确（timezone-aware）
from datetime import datetime, timezone
created_at = datetime.now(timezone.utc)
```

### ❌ 错误 5: 缺少 setup_db fixture

```python
# 错误（未认证测试缺少 setup_db）
async def test_upload_without_auth(async_client, db_session):
    ...

# 正确
async def test_upload_without_auth(async_client, db_session, setup_db):
    ...
```

---

## 常见问题排查

| 错误症状 | 原因 | 解决方案 |
|---------|------|---------|
| `RuntimeError: Task got Future attached to a different loop` | 混用同步/异步客户端 | 只使用 `AsyncClient` |
| `asyncpg.exceptions.InterfaceError: another operation is in progress` | 共享 engine | 每个测试独立 engine + `StaticPool` |
| `can't subtract offset-naive and offset-aware datetimes` | 时区不一致 | 使用 `datetime.now(timezone.utc)` |
| 测试顺序影响结果 | 数据污染 | 每个测试重建表 |

---

## 运行测试

```bash
# 运行所有测试
pytest tests/

# 运行特定文件
pytest tests/api/test_documents_integration.py

# 详细输出
pytest -v

# 显示打印
pytest -s

# 失败时停止
pytest -x

# 显示最慢的测试
pytest --durations=10

# 并行运行
pytest -n auto
```

---

## 检查清单

编写新测试时，确保：

- [ ] 使用 `async def` + `@pytest.mark.asyncio`
- [ ] 使用 `async_client`（不是 `TestClient`）
- [ ] 所有异步调用都加 `await`
- [ ] 包含必要的 fixtures: `async_client`, `db_session`, `setup_db`
- [ ] 验证响应状态码和数据结构
- [ ] 测试覆盖成功和失败场景
- [ ] 使用正确的数据模型字段名
- [ ] 时区感知的 datetime

---

## 密码哈希

```python
from ragserver.app.dependencies.security import get_password_hash, verify_password

# 生成哈希
hashed = get_password_hash("mypassword")  # $2b$12$...

# 验证密码
is_valid = verify_password("mypassword", hashed)  # True
```

---

## 参考资源

- [pytest 文档](https://docs.pytest.org/)
- [pytest-asyncio 文档](https://pytest-asyncio.readthedocs.io/)
- [FastAPI 测试文档](https://fastapi.tiangolo.com/tutorial/testing/)
- [SQLAlchemy 异步文档](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html)


