# 测试最佳实践 (Testing Best Practices)

> 本文档为 AI 代码助手和开发者提供测试编写指南

## 目录

- [测试架构](#测试架构)
- [Fixtures 设计](#fixtures-设计)
- [异步测试](#异步测试)
- [数据库测试](#数据库测试)
- [API 测试](#api-测试)
- [常见问题](#常见问题)

---

## 测试架构

### 项目结构

```
tests/
├── conftest.py          # 全局 fixtures
├── AGENTS.md           # 本文档
└── api/
    ├── test_auth_integration.py  # 认证API集成测试
    └── ...
```

### 配置文件

测试配置位于 `pyproject.toml`:

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"  # 自动检测异步测试
asyncio_default_fixture_loop_scope = "function"  # 每个测试独立事件循环
```

---

## Fixtures 设计

### 核心原则

1. **隔离性**: 每个测试完全独立，互不影响
2. **独立性**: 每个测试使用独立的数据库连接
3. **清理**: 测试后自动清理资源

### 数据库 Fixture

```python
@pytest.fixture(scope="function")
async def db_session():
    """为每个测试创建独立的数据库会话
    
    特点:
    - 独立的 engine（避免连接冲突）
    - 使用 StaticPool（单连接池）
    - 每个测试前重建表
    - 测试后自动清理
    """
    test_engine = create_async_engine(
        TEST_DATABASE_URL,
        echo=False,
        poolclass=StaticPool,  # ← 关键：避免并发冲突
    )
    
    # 重建表
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    
    # 创建会话
    AsyncSessionLocal = async_sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    
    async with AsyncSessionLocal() as session:
        yield session
    
    await test_engine.dispose()
```

### HTTP 客户端 Fixture

```python
@pytest.fixture(scope="function")
async def async_client():
    """创建异步 HTTP 客户端
    
    注意:
    - 必须使用 AsyncClient（不是 TestClient）
    - 使用 ASGITransport
    """
    from httpx import ASGITransport
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as client:
        yield client
```

---

## 异步测试

### 基本规则

1. **必须使用 `async def`**
2. **所有 HTTP 调用加 `await`**
3. **fixture 参数必须包含 `async_client`**

### ✅ 正确示例

```python
@pytest.mark.asyncio
async def test_register_success(
    async_client: AsyncClient,  # ← 必须声明
    db_session: AsyncSession,
    setup_db
):
    """测试成功注册"""
    payload = {"username": "newuser", "email": "test@example.com", "password": "Pass123!"}
    
    # ← 使用 await
    res = await async_client.post("/api/v1/auth/register", json=payload)
    assert res.status_code == 201
    
    # 查询数据库也要 await
    result = await db_session.execute(
        select(User).where(User.username == "newuser")
    )
    user = result.scalar_one()
    assert user.email == "test@example.com"
```

### ❌ 错误示例

```python
# 错误 1: 使用同步 TestClient
from fastapi.testclient import TestClient
client = TestClient(app)
res = client.post("/api/v1/auth/register", json=payload)  # ← 不要这样

# 错误 2: 忘记 await
res = async_client.post("/api/v1/auth/register", json=payload)  # ← 缺少 await

# 错误 3: 混用同步和异步
async def test_example():
    res = client.post(...)  # 同步
    result = await db_session.execute(...)  # 异步
    # ← 会导致事件循环冲突
```

---

## 数据库测试

### 时区处理

**重要**: 所有 `DateTime` 字段必须使用时区感知的时间。

```python
# ✅ 正确：使用 timezone.utc
from datetime import datetime, timezone

created_at = datetime.now(timezone.utc)
user = User(
    username="test",
    created_at=created_at  # ← 带时区
)

# ❌ 错误：不要使用 naive datetime
created_at = datetime.now()  # ← 没有时区信息
```

### 数据模型定义

```python
# ✅ 正确：DateTime 加 timezone=True
class User(Base):
    created_at = Column(DateTime(timezone=True), default=get_current_time)
    updated_at = Column(DateTime(timezone=True), onupdate=get_current_time)

# ❌ 错误：不指定 timezone
created_at = Column(DateTime, default=datetime.now)  # ← 会导致时区错误
```

### 依赖注入覆盖

```python
@pytest.fixture
async def setup_db(db_session: AsyncSession):
    """设置数据库依赖注入"""
    async def override_get_db():
        yield db_session
    
    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.clear()
```

---

## API 测试

### 测试结构

```python
class TestRegister:
    """用户注册测试
    
    测试组织:
    - 成功场景（happy path）
    - 边界情况（edge cases）
    - 错误场景（error cases）
    """
    
    @pytest.mark.asyncio
    async def test_register_success(self, async_client, db_session, setup_db):
        """测试成功注册（happy path）"""
        # 1. 准备数据
        payload = {...}
        
        # 2. 调用 API
        res = await async_client.post("/api/v1/auth/register", json=payload)
        
        # 3. 验证响应
        assert res.status_code == 201
        data = res.json()
        assert "access_token" in data
        
        # 4. 验证数据库
        result = await db_session.execute(...)
        user = result.scalar_one()
        assert user.username == "newuser"
    
    @pytest.mark.asyncio
    async def test_register_duplicate_username(self, async_client, test_user):
        """测试用户名重复（error case）"""
        payload = {"username": "testuser", ...}  # 已存在
        res = await async_client.post("/api/v1/auth/register", json=payload)
        assert res.status_code == 400
```

### 认证测试

```python
@pytest.mark.asyncio
async def test_protected_endpoint(self, async_client, test_user):
    """测试需要认证的端点"""
    # 1. 登录获取 token
    login_payload = {"username": "testuser", "password": "Test1234!"}
    login_res = await async_client.post("/api/v1/auth/login", json=login_payload)
    token = login_res.json()["access_token"]
    
    # 2. 使用 token 访问受保护端点
    headers = {"Authorization": f"Bearer {token}"}
    res = await async_client.post(
        "/api/v1/protected",
        json={...},
        headers=headers
    )
    assert res.status_code == 200
```

---

## 常见问题

### 问题 1: 事件循环冲突

**症状**: `RuntimeError: Task got Future attached to a different loop`

**原因**: 混用同步和异步客户端

**解决**:
```python
# ❌ 不要
client = TestClient(app)

# ✅ 使用
async_client = AsyncClient(...)
res = await async_client.post(...)
```

### 问题 2: 数据库连接冲突

**症状**: `asyncpg.exceptions.InterfaceError: another operation is in progress`

**原因**: 多个测试共享同一个 engine

**解决**:
```python
# ✅ 每个测试创建独立 engine
@pytest.fixture(scope="function")
async def db_session():
    test_engine = create_async_engine(..., poolclass=StaticPool)
    ...
```

### 问题 3: 时区错误

**症状**: `can't subtract offset-naive and offset-aware datetimes`

**原因**: DateTime 列没有时区支持

**解决**:
```python
# ✅ 数据模型
class User(Base):
    created_at = Column(DateTime(timezone=True), ...)  # ← 加 timezone=True

# ✅ 工具函数
def get_current_time() -> datetime:
    return datetime.now(timezone.utc)  # ← 使用 UTC
```

### 问题 4: 测试数据污染

**症状**: 测试顺序影响结果

**原因**: 测试间共享数据

**解决**:
```python
# ✅ 每个测试重建表
@pytest.fixture(scope="function")
async def db_session():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    ...
```

---

## 性能优化

### 减少表重建次数

如果测试很多，每个测试重建表会很慢。可以考虑：

```python
# 选项 1: 使用事务回滚（推荐，但需要更复杂的设置）
@pytest.fixture(scope="function")
async def db_session():
    connection = await engine.connect()
    transaction = await connection.begin()
    session = AsyncSessionLocal(bind=connection)
    
    yield session
    
    await session.close()
    await transaction.rollback()  # ← 回滚而不是删表
    await connection.close()

# 选项 2: 模块级表创建（当前实现）
# 适合测试数量较少的情况
```

### 并行测试

```bash
# 使用 pytest-xdist 并行运行
pytest -n auto  # 自动检测 CPU 核心数

# 如果有并发问题，禁用并行
pytest -n 0
```

---

## 密码测试特别说明

### bcrypt 哈希

项目使用 `bcrypt` 进行密码哈希（已移除 passlib）:

```python
from ragserver.app.dependencies.security import get_password_hash, verify_password

# 生成哈希
hashed = get_password_hash("mypassword")
# $2b$12$...

# 验证密码
is_valid = verify_password("mypassword", hashed)  # True
```

### 兼容性

- ✅ 完全兼容旧的 passlib 生成的 bcrypt 哈希
- ✅ bcrypt 格式是标准化的（$2b$12$...）
- ✅ 无需迁移现有数据库密码

---

## 运行测试

### 基本命令

```bash
# 运行所有测试
pytest tests/

# 运行特定文件
pytest tests/api/test_auth_integration.py

# 运行特定类
pytest tests/api/test_auth_integration.py::TestRegister

# 运行特定测试
pytest tests/api/test_auth_integration.py::TestRegister::test_register_success

# 详细输出
pytest -v

# 显示打印输出
pytest -s

# 遇到第一个失败就停止
pytest -x

# 显示最慢的 10 个测试
pytest --durations=10
```

### 调试

```bash
# 显示详细错误信息
pytest --tb=long

# 只显示一行错误
pytest --tb=line

# 不显示错误堆栈
pytest --tb=no

# 进入 pdb 调试器
pytest --pdb

# 详细日志
pytest --log-cli-level=DEBUG
```

---

## 检查清单

在编写新测试时，检查以下项：

- [ ] 使用 `async def` 定义测试函数
- [ ] 添加 `@pytest.mark.asyncio` 装饰器
- [ ] 使用 `async_client` 而不是 `TestClient`
- [ ] 所有 HTTP 调用都加 `await`
- [ ] 所有数据库操作都加 `await`
- [ ] 测试函数包含必要的 fixtures（`async_client`, `db_session`, `setup_db`）
- [ ] 测试有清晰的文档字符串
- [ ] 验证响应状态码
- [ ] 验证响应数据结构
- [ ] 必要时验证数据库状态
- [ ] 测试覆盖成功和失败场景

---

## 更多资源

- [pytest 文档](https://docs.pytest.org/)
- [pytest-asyncio 文档](https://pytest-asyncio.readthedocs.io/)
- [FastAPI 测试文档](https://fastapi.tiangolo.com/tutorial/testing/)
- [SQLAlchemy 异步文档](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html)

---

**最后更新**: 2025-10-29  
**维护者**: AI 代码助手

