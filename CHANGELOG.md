# 更新日志

所有的项目重要更改都会记录在此文件中。

此项目遵循 [语义化版本](https://semver.org/lang/zh-CN/) 和 [Keep a Changelog](https://keepachangelog.com/zh-CN/) 格式。

## [0.0.1] - 2025-06-22

### 新增
- **配置管理模块** - 实现了从环境变量读取配置的完整系统
  - 数据库配置（PostgreSQL + pgvector）
  - MinIO 对象存储配置
  - 多种嵌入模型支持（Ollama、OpenAI、SiliconFlow）
  - CORS 和应用基础配置
- **数据库基础设施** - 基于 asyncpg 的原生 SQL 实现
  - 异步连接池管理
  - collections 表和 files 表结构
  - 自动创建向量表（每个集合独立）
  - 完整的 CRUD 操作函数
  - 性能优化索引
- **FastAPI 应用框架** - 完整的 Web 服务基础
  - 应用生命周期管理
  - 自动初始化数据库和 MinIO 服务
  - CORS 中间件配置
  - 模块化路由结构
- **健康检查 API** - 服务状态监控端点
  - 返回服务名称、版本和状态信息
- **集合管理 API** - 完整的集合 CRUD 操作
  - POST /collections - 创建集合（自动创建向量表）
  - GET /collections - 列出所有集合
  - GET /collections/{id} - 获取集合详情
  - PUT /collections/{id} - 更新集合信息
  - DELETE /collections/{id} - 删除集合（同时清理向量表）

### 技术决策
- 使用原生 SQL 而非 ORM，提供更好的性能和控制
- 每个集合独立创建向量表，支持更好的数据隔离
- 异步架构设计，支持高并发处理
- 完整的错误处理和日志记录

### 测试验证
- ✅ 所有 API 端点功能正常
- ✅ 数据库连接和表创建成功
- ✅ 服务启动和关闭流程正常
- ✅ 集合的完整生命周期管理
