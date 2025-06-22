# 更新日志

所有的项目重要更改都会记录在此文件中。

此项目遵循 [语义化版本](https://semver.org/lang/zh-CN/) 和 [Keep a Changelog](https://keepachangelog.com/zh-CN/) 格式。

## [未发布]

## [0.1.0] - 2025-01-23

### ✨ 新增功能
- 实现文件上传API：支持PDF、Word、文本、Markdown、HTML等多种格式
- 完成文档处理服务：文档解析、智能分块、向量化处理
- 实现向量搜索功能：基于语义相似度的文档检索
- 支持异步文档处理：上传后后台自动处理和索引
- 添加文件状态跟踪：uploading → processing → completed/failed
- 实现集合统计信息API：向量数量、文件数量等统计

### 🔧 技术改进
- 创建嵌入服务抽象层：支持动态切换Ollama、OpenAI、SiliconFlow
- 实现智能文档分块：使用RecursiveCharacterTextSplitter
- 添加向量数据库操作：批量插入、相似度搜索、元数据过滤
- 实现文档格式识别和解析：基于langchain的多格式支持
- 添加文件验证和大小限制：防止无效文件上传

### 📋 API扩展
- POST /collections/{id}/files - 文件上传
- GET /collections/{id}/files - 文件列表
- POST /collections/{id}/search - 向量搜索
- GET /collections/{id}/stats - 集合统计
- GET /files/{id} - 文件详情
- DELETE /files/{id} - 文件删除

### 🧪 测试
- 添加端到端测试脚本：完整的RAG流程测试
- 实现自动化功能验证：上传、处理、搜索全流程

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
