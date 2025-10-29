# 数据模型测试文档

本文档说明如何运行和使用 RAG Server 数据模型的测试套件。

## 概述

数据模型测试套件包含以下内容：

1. **单元测试** - 测试模型的字段验证、默认值、关系和方法
2. **数据库集成测试** - 测试模型在数据库中的实际操作和关系
3. **数据隔离测试** - 测试按用户 ID 的数据隔离功能

## 测试结构

```
tests/
├── conftest.py                    # 测试配置和 fixtures
├── run_model_tests.py             # 测试运行脚本
└── units/
    ├── test_models.py             # 数据模型测试
    └── README.md                  # 本文档
```

## 运行测试

### 方式一：使用测试运行脚本（推荐）

```bash
# 运行所有测试
python tests/run_model_tests.py

# 运行单元测试
python tests/run_model_tests.py unit

# 运行集成测试
python tests/run_model_tests.py integration

# 查看帮助
python tests/run_model_tests.py help
```

### 方式二：直接使用 pytest

```bash
# 运行所有模型测试
pytest tests/units/test_models.py -v

# 运行特定测试类
pytest tests/units/test_models.py::TestUserModel -v

# 运行特定测试方法
pytest tests/units/test_models.py::TestUserModel::test_user_creation -v

# 运行集成测试
pytest tests/units/test_models.py::TestModelDatabaseIntegration -v
```

### 方式三：使用 Makefile（如果存在）

```bash
make test-models    # 运行模型测试
make test           # 运行所有测试
```

## 测试覆盖范围

### 单元测试

#### TimeMixin
- ✅ 时间戳字段的存在性验证

#### User 模型
- ✅ 模型创建和字段验证
- ✅ `__repr__` 方法测试
- ✅ 默认值验证
- ✅ 关系属性验证

#### Collection 模型
- ✅ 模型创建和字段验证
- ✅ `__repr__` 方法测试
- ✅ 默认值验证
- ✅ 关系属性验证

#### Document 模型
- ✅ 模型创建和字段验证
- ✅ `__repr__` 方法测试
- ✅ 默认值验证
- ✅ 关系属性验证

#### DocumentChunk 模型
- ✅ 模型创建和字段验证
- ✅ `__repr__` 方法测试
- ✅ 默认值验证
- ✅ 关系属性验证

#### APIKey 模型
- ✅ 模型创建和字段验证
- ✅ `__repr__` 方法测试
- ✅ 默认值验证
- ✅ 关系属性验证

#### APIUsageLog 模型
- ✅ 模型创建和字段验证
- ✅ `__repr__` 方法测试
- ✅ 默认值验证
- ✅ 关系属性验证

### 数据库集成测试

#### 数据持久化测试
- ✅ 用户模型的数据库持久化
- ✅ 知识库和用户的关联关系
- ✅ 文档的关联关系
- ✅ 文档分块的关联关系
- ✅ API 密钥的关联关系
- ✅ API 使用日志的关联关系

#### 数据隔离测试
- ✅ 按用户 ID 的数据隔离验证
- ✅ 跨用户查询的安全性验证

#### 索引测试
- ✅ 数据库索引的性能验证
- ✅ 复合索引的测试

## 测试配置

### 测试数据库

测试使用独立的测试数据库：

```python
# 测试数据库连接
TEST_DATABASE_URL = "postgresql+asyncpg://ragserver:ragserver_password@localhost:15432/ragserver_test"
```

**注意**: 确保测试数据库存在并且可以访问：

```bash
# 创建测试数据库
createdb ragserver_test

# 或者使用 Docker
docker run --name ragserver-test-postgres \
  -e POSTGRES_USER=ragserver \
  -e POSTGRES_PASSWORD=ragserver_password \
  -e POSTGRES_DB=ragserver_test \
  -p 15432:5432 \
  -d postgres:15
```

### 环境变量

测试需要以下环境变量：

```bash
# 复制示例环境文件
cp env.example .env

# 编辑测试数据库配置（如果需要）
vim .env
```

确保 `.env` 文件中的数据库配置指向测试数据库。

### 测试依赖

确保安装了所有测试依赖：

```bash
# 安装开发依赖（包含测试依赖）
uv sync --dev

# 或者直接安装测试依赖
uv add --dev pytest pytest-asyncio pytest-socket pytest-timeout
```

## 编写新测试

### 添加单元测试

```python
class TestNewModel:
    """测试新模型"""

    def test_model_creation(self):
        """测试模型创建"""
        model = NewModel(
            field1="value1",
            field2="value2"
        )

        assert model.field1 == "value1"
        assert model.field2 == "value2"

    def test_model_defaults(self):
        """测试模型默认值"""
        model = NewModel(field1="value1")

        assert model.default_field == "default_value"

    def test_model_relationships(self):
        """测试模型关系"""
        model = NewModel(field1="value1")

        # 验证关系属性的存在
        assert hasattr(model, 'related_model')
```

### 添加集成测试

```python
class TestModelIntegration:
    """测试模型集成"""

    @pytest.mark.asyncio
    async def test_model_persistence(self, test_db: AsyncSession):
        """测试模型持久化"""
        model = NewModel(field1="value1")

        test_db.add(model)
        await test_db.commit()
        await test_db.refresh(model)

        # 验证数据库操作
        assert model.id is not None

        # 验证查询
        result = await test_db.execute(
            select(NewModel).where(NewModel.field1 == "value1")
        )
        db_model = result.scalar_one()

        assert db_model.field1 == "value1"
```

### 添加数据隔离测试

```python
@pytest.mark.asyncio
async def test_data_isolation(self, test_db: AsyncSession):
    """测试数据隔离"""
    # 创建多个用户
    user1 = User(username="user1", email="user1@example.com", ...)
    user2 = User(username="user2", email="user2@example.com", ...)

    test_db.add_all([user1, user2])
    await test_db.commit()

    # 创建资源
    resource1 = Resource(user_id=user1.id, ...)
    resource2 = Resource(user_id=user2.id, ...)

    test_db.add_all([resource1, resource2])
    await test_db.commit()

    # 验证数据隔离
    result1 = await test_db.execute(
        select(Resource).where(Resource.user_id == user1.id)
    )
    resources1 = result1.scalars().all()

    assert len(resources1) == 1
    assert resources1[0].user_id == user1.id
```

## 故障排除

### 常见问题

#### 1. 数据库连接错误

**错误**: `Connection refused` 或 `database does not exist`

**解决方案**:
- 确保 PostgreSQL 服务正在运行
- 确保测试数据库存在
- 检查数据库连接配置

#### 2. 权限错误

**错误**: `Permission denied` 或 `authentication failed`

**解决方案**:
- 检查数据库用户权限
- 验证密码配置
- 确保数据库用户有创建表的权限

#### 3. 导入错误

**错误**: `Module not found` 或 `ImportError`

**解决方案**:
- 激活虚拟环境: `source .venv/bin/activate`
- 安装依赖: `uv sync`
- 检查 Python 路径

#### 4. 测试超时

**错误**: `Test timeout` 或 `Async test timeout`

**解决方案**:
- 增加测试超时时间
- 检查数据库连接是否正常
- 验证异步代码是否正确

### 调试技巧

#### 启用 SQL 调试

修改 `conftest.py` 中的测试引擎配置：

```python
test_engine = create_async_engine(
    TEST_DATABASE_URL,
    echo=True,  # 启用 SQL 调试输出
    pool_pre_ping=True,
    ...
)
```

#### 运行单个测试

```bash
# 运行单个测试方法
pytest tests/units/test_models.py::TestUserModel::test_user_creation -v -s

# 运行测试类
pytest tests/units/test_models.py::TestUserModel -v -s
```

#### 生成覆盖率报告

```bash
# 安装覆盖率工具
uv add --dev pytest-cov

# 生成覆盖率报告
pytest tests/units/test_models.py --cov=ragserver.app.models --cov-report=html
```

## 最佳实践

### 1. 测试命名

- 使用描述性的测试方法名: `test_user_creation` 而不是 `test_1`
- 每个测试方法只测试一个功能点
- 使用 `pytest.mark.asyncio` 标记异步测试

### 2. 测试数据

- 使用独立的测试数据，避免测试间相互影响
- 清理测试数据，使用 fixtures 管理生命周期
- 测试边界条件和异常情况

### 3. 断言

- 使用具体的断言，避免模糊的 `assert True`
- 验证所有相关属性和关系
- 测试默认值和约束

### 4. 文档

- 为复杂测试添加注释说明测试目的
- 记录测试的先决条件和期望结果
- 维护测试文档的更新

## 贡献

当添加新的数据模型时，请：

1. 在 `test_models.py` 中添加相应的测试类
2. 实现单元测试和集成测试
3. 更新测试文档
4. 运行测试确保通过

## 相关文档

- [项目开发指南](../README.md)
- [数据模型文档](../../ER_SIMPLE.md)
- [配置文档](../../CONFIG_README.md)
- [pytest 文档](https://docs.pytest.org/)
- [SQLAlchemy 文档](https://docs.sqlalchemy.org/)
