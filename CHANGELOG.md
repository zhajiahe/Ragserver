# 更新日志

所有的项目重要更改都会记录在此文件中。

此项目遵循 [语义化版本](https://semver.org/lang/zh-CN/) 和 [Keep a Changelog](https://keepachangelog.com/zh-CN/) 格式。

## [未发布]

## [0.0.2] - 2025-06-22

### 🔒 安全修复
- 修复SQL注入风险：在所有数据库操作中添加UUID格式验证
- 使用安全的表名生成函数，防止SQL注入攻击
- 实现输入验证和参数化查询

### 🐛 错误修复
- 修复数据库schema不一致问题：collections表添加embedding_provider字段
- 修复API响应不一致问题：统一所有接口返回字段
- 修复删除接口的204响应格式错误
- 修复路由注册中的重复前缀问题

### ♻️ 重构
- 将全局变量重构为DatabaseManager类，使用依赖注入模式
- 改进连接池管理的封装性和可测试性
- 保持向后兼容性

### 📝 文档
- 更新安全审计报告
- 完善代码注释和类型提示

## [0.0.1] - 2025-06-21

### ✨ 新增功能
- 实现基础FastAPI应用框架
- 完成数据库连接池管理（asyncpg）
- 实现集合管理完整CRUD操作
- 支持多种嵌入模型（Ollama、OpenAI、SiliconFlow）
- 集成MinIO文件存储服务
- 添加配置管理系统
- 实现健康检查API
- 支持Docker容器化部署

### 🏗️ 基础架构
- PostgreSQL + pgvector 数据库设计
- 异步架构设计
- 每个集合独立的向量表结构
- CORS中间件配置
- 应用生命周期管理
