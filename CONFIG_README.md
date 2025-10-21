# 配置管理说明

## 统一配置管理

本项目使用 `.env` 文件统一管理所有配置，包括：
- Docker Compose 服务配置
- PM2 应用配置
- Python 应用配置（通过 `ragserver/config.py`）

## 配置文件结构

```
.
├── .env                    # 实际配置文件（不纳入版本控制）
├── .env.template           # 配置模板文件
├── ragserver/config.py     # Python 配置管理类
├── docker-compose.yml      # Docker服务配置（使用env_file）
└── ecosystem.config.js     # PM2配置（使用dotenv）
```

## 首次设置

1. 复制模板文件创建配置：
   ```bash
   cp .env.template .env
   ```

2. 编辑 `.env` 文件，填入您的配置：
   ```bash
   vi .env  # 或使用其他编辑器
   ```

3. 关键配置项：
   - `QWEN_API_KEY`: 通义千问API密钥（必需）
   - `POSTGRES_PASSWORD`: 数据库密码
   - `REDIS_PASSWORD`: Redis密码
   - `MINIO_SECRET_KEY`: MinIO密钥
   - `JWT_SECRET_KEY`: JWT密钥（建议使用`openssl rand -hex 32`生成）

## 配置加载顺序

### Docker Compose
```yaml
services:
  postgres:
    env_file:
      - .env  # 加载 .env 文件
    environment:
      # 使用环境变量，提供默认值
      POSTGRES_USER: ${POSTGRES_USER:-ragserver}
```

### PM2
```javascript
// ecosystem.config.js 自动加载 .env
require('dotenv').config();

module.exports = {
  apps: [{
    env_file: '.env',  // 显式指定env文件
    // ...
  }]
};
```

### Python 应用
```python
# ragserver/config.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",  # 自动加载 .env
        # ...
    )
```

## 配置优先级

1. 环境变量（最高）
2. `.env` 文件
3. 代码中的默认值（最低）

示例：
```bash
# 临时覆盖配置
DEBUG=true make dev

# 或在 .env 中设置
DEBUG=true
```

## 核心配置项

### 数据库
- `POSTGRES_USER`: 数据库用户名
- `POSTGRES_PASSWORD`: 数据库密码
- `POSTGRES_HOST`: 数据库主机
- `POSTGRES_PORT`: 数据库端口
- `POSTGRES_DB`: 数据库名

### Redis
- `REDIS_HOST`: Redis主机
- `REDIS_PORT`: Redis端口
- `REDIS_PASSWORD`: Redis密码

### MinIO
- `MINIO_ENDPOINT`: MinIO端点
- `MINIO_ACCESS_KEY`: AccessKey
- `MINIO_SECRET_KEY`: SecretKey

### API密钥
- `QWEN_API_KEY`: 通义千问API密钥（必需）
- `OPENAI_API_KEY`: OpenAI API密钥（可选）
- `ANTHROPIC_API_KEY`: Anthropic API密钥（可选）

### 应用配置
- `DEBUG`: 调试模式（true/false）
- `LOG_LEVEL`: 日志级别（DEBUG/INFO/WARNING/ERROR）
- `API_PORT`: API服务端口（默认8000）

### 任务队列
- `TASKIQ_WORKERS`: Worker总数（默认4）
- `TASKIQ_WORKERS_DOCUMENT`: 文档处理Worker数（默认2）
- `TASKIQ_WORKERS_EMBEDDING`: Embedding Worker数（默认2）

## 环境隔离

### 开发环境
```bash
# .env.development
DEBUG=true
LOG_LEVEL=DEBUG
```

### 生产环境
```bash
# .env.production
DEBUG=false
LOG_LEVEL=INFO
JWT_SECRET_KEY=<strong-secret-key>
```

使用时：
```bash
# 开发环境
cp .env.development .env
make up

# 生产环境
cp .env.production .env
make up
```

## 安全建议

1. **绝对不要**将 `.env` 文件提交到版本控制
2. 在 `.gitignore` 中添加：
   ```
   .env
   .env.local
   .env.*.local
   ```

3. 生产环境使用强密码：
   ```bash
   # 生成JWT密钥
   openssl rand -hex 32
   
   # 生成数据库密码
   openssl rand -base64 32
   ```

4. 定期轮换敏感密钥

## 配置验证

应用启动时会自动验证配置：

```python
# ragserver/config.py
def validate_settings() -> None:
    """验证配置的有效性"""
    if not settings.qwen_api_key:
        warnings.warn("QWEN_API_KEY 未设置")
    # ...
```

## 常见问题

### Q: 修改配置后需要重启吗？
A: 是的，配置在应用启动时加载，修改后需要重启：
```bash
make restart  # 重启所有服务
```

### Q: 如何查看当前配置？
A: 可以通过以下方式：
```bash
# 查看环境变量
printenv | grep POSTGRES

# 或在Python中
python -c "from ragserver.config import settings; print(settings.postgres_host)"
```

### Q: Docker和PM2使用不同的端口？
A: 确保 `.env` 中的端口配置一致，或者：
```bash
# Docker使用宿主机端口
POSTGRES_PORT=5432

# Python应用连接
POSTGRES_HOST=localhost
```

## 配置模板更新

当添加新的配置项时：

1. 更新 `.env.template`
2. 更新 `ragserver/config.py`
3. 更新此文档
4. 通知团队成员更新其本地 `.env` 文件

