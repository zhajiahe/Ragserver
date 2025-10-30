# Alembic 数据库迁移配置

## 使用方法

### 查看当前迁移状态

```bash
# 激活虚拟环境
source .venv/bin/activate

# 查看当前版本
alembic current

# 查看迁移历史
alembic history

# 查看详细历史
alembic history --verbose
```

### 创建新迁移

```bash
# 自动生成迁移（推荐）
alembic revision --autogenerate -m "描述信息"

# 手动创建空迁移
alembic revision -m "描述信息"
```

### 应用迁移

```bash
# 升级到最新版本
alembic upgrade head

# 升级到特定版本
alembic upgrade <revision_id>

# 升级一个版本
alembic upgrade +1
```

### 回滚迁移

```bash
# 回滚到基础状态
alembic downgrade base

# 回滚到特定版本
alembic downgrade <revision_id>

# 回滚一个版本
alembic downgrade -1
```

### 标记数据库状态

```bash
# 标记为最新版本（不执行迁移）
alembic stamp head

# 标记为特定版本
alembic stamp <revision_id>
```

---

## 常用场景

### 场景 1: 修改现有模型

1. 修改 `ragserver/app/models.py` 中的模型
2. 生成迁移文件:
   ```bash
   alembic revision --autogenerate -m "修改用户表添加字段"
   ```
3. 检查生成的迁移文件（`ragserver/alembic/versions/xxx.py`）
4. 应用迁移:
   ```bash
   alembic upgrade head
   ```

### 场景 2: 添加新表

1. 在 `ragserver/app/models.py` 中添加新模型类
2. 生成迁移:
   ```bash
   alembic revision --autogenerate -m "添加新表"
   ```
3. 应用迁移:
   ```bash
   alembic upgrade head
   ```

### 场景 3: 生产环境部署

```bash
# 1. 拉取最新代码
git pull

# 2. 激活虚拟环境
source .venv/bin/activate

# 3. 安装依赖
uv sync

# 4. 查看待应用的迁移
alembic current
alembic history

# 5. 应用迁移
alembic upgrade head

# 6. 重启应用
pm2 restart ragserver
```

### 场景 4: 回滚错误的迁移

```bash
# 1. 回滚到上一个版本
alembic downgrade -1

# 2. 删除错误的迁移文件
rm ragserver/alembic/versions/<错误的文件>.py

# 3. 重新创建迁移
alembic revision --autogenerate -m "正确的描述"

# 4. 应用新迁移
alembic upgrade head
```

---

## 注意事项

### ⚠️ 重要提醒

1. **生产环境备份**: 在生产环境应用迁移前，务必备份数据库
   ```bash
   pg_dump -U ragserver -d ragserver > backup_$(date +%Y%m%d_%H%M%S).sql
   ```

2. **检查自动生成的迁移**: `--autogenerate` 不是万能的，需要人工检查：
   - 检查是否正确检测到所有变更
   - 检查是否有遗漏的索引
   - 检查数据迁移逻辑（如字段重命名）

3. **向量字段特殊处理**: pgvector 的 `Vector` 类型需要手动导入：
   ```python
   from pgvector.sqlalchemy import Vector
   ```

4. **HNSW 索引**: 向量索引创建较慢，大表可能需要几分钟到几小时

5. **环境变量**: 确保 `.env` 文件中的数据库配置正确
