.PHONY: help install dev-install setup-env docker-up docker-down docker-restart docker-logs migrate upgrade downgrade db-init dev worker start stop restart status clean test lint format

# 默认目标
.DEFAULT_GOAL := help

# 环境变量
PYTHON := python3
UV := uv
VENV := .venv
ALEMBIC := alembic
PM2 := pm2

# 颜色输出
BLUE := \033[0;34m
GREEN := \033[0;32m
YELLOW := \033[0;33m
RED := \033[0;31m
NC := \033[0m # No Color

##@ 帮助

help: ## 显示帮助信息
	@echo "$(BLUE)RAG Knowledge Base Server - Makefile$(NC)"
	@echo ""
	@awk 'BEGIN {FS = ":.*##"; printf "Usage:\n  make $(YELLOW)<target>$(NC)\n"} /^[a-zA-Z_-]+:.*?##/ { printf "  $(BLUE)%-20s$(NC) %s\n", $$1, $$2 } /^##@/ { printf "\n$(GREEN)%s$(NC)\n", substr($$0, 5) } ' $(MAKEFILE_LIST)

##@ 环境设置

install: ## 安装项目依赖（使用 uv）
	@echo "$(BLUE)Installing dependencies with uv...$(NC)"
	@$(UV) sync
	@echo "$(GREEN)✓ Dependencies installed$(NC)"

dev-install: install ## 安装开发依赖
	@echo "$(BLUE)Installing development dependencies...$(NC)"
	@$(UV) add --dev pytest pytest-asyncio httpx black ruff mypy
	@echo "$(GREEN)✓ Development dependencies installed$(NC)"

##@ Docker 服务管理

docker-up: ## 启动 Docker 服务（PostgreSQL, Redis, MinIO, Prometheus, Grafana）
	@echo "$(BLUE)Starting Docker services...$(NC)"
	@docker compose up -d
	@echo "$(GREEN)✓ Docker services started$(NC)"
	@echo "$(YELLOW)Services:$(NC)"
	@echo "  - PostgreSQL:  localhost:5432"
	@echo "  - Redis:       localhost:6379"
	@echo "  - MinIO:       localhost:9000 (Console: 9001)"
	@echo "  - Prometheus:  localhost:9091"
	@echo "  - Grafana:     localhost:3000 (admin/admin)"

docker-down: ## 停止 Docker 服务
	@echo "$(BLUE)Stopping Docker services...$(NC)"
	@docker compose down
	@echo "$(GREEN)✓ Docker services stopped$(NC)"

docker-restart: docker-down docker-up ## 重启 Docker 服务

docker-logs: ## 查看 Docker 服务日志
	@docker compose logs -f

docker-clean: ## 清理 Docker 容器和数据卷（危险操作！）
	@echo "$(RED)WARNING: This will remove all containers and volumes!$(NC)"
	@read -p "Are you sure? [y/N] " -n 1 -r; \
	echo; \
	if [[ $$REPLY =~ ^[Yy]$$ ]]; then \
		docker compose down -v; \
		echo "$(GREEN)✓ Docker containers and volumes removed$(NC)"; \
	else \
		echo "$(YELLOW)Cancelled$(NC)"; \
	fi

##@ 数据库迁移

migrate: ## 创建新的数据库迁移
	@echo "$(BLUE)Creating new migration...$(NC)"
	@source $(VENV)/bin/activate && $(ALEMBIC) revision --autogenerate -m "$(msg)"
	@echo "$(GREEN)✓ Migration created$(NC)"

upgrade: ## 升级数据库到最新版本
	@echo "$(BLUE)Upgrading database...$(NC)"
	@source $(VENV)/bin/activate && $(ALEMBIC) upgrade head
	@echo "$(GREEN)✓ Database upgraded$(NC)"

downgrade: ## 降级数据库一个版本
	@echo "$(BLUE)Downgrading database...$(NC)"
	@source $(VENV)/bin/activate && $(ALEMBIC) downgrade -1
	@echo "$(GREEN)✓ Database downgraded$(NC)"

db-init: upgrade ## 初始化数据库（运行所有迁移）
	@echo "$(GREEN)✓ Database initialized$(NC)"

##@ 应用管理（PM2）

dev: ## 启动开发服务器（热重载）
	@echo "$(BLUE)Starting development server...$(NC)"
	@source $(VENV)/bin/activate && uvicorn ragserver.main:app --host 0.0.0.0 --port 8000 --reload

start: ## 使用 PM2 启动所有服务（API + Worker）
	@echo "$(BLUE)Starting services with PM2...$(NC)"
	@$(PM2) start ecosystem.config.js
	@echo "$(GREEN)✓ Services started$(NC)"
	@$(PM2) list

stop: ## 停止所有 PM2 服务
	@echo "$(BLUE)Stopping PM2 services...$(NC)"
	@$(PM2) stop ecosystem.config.js
	@echo "$(GREEN)✓ Services stopped$(NC)"

restart: ## 重启所有 PM2 服务
	@echo "$(BLUE)Restarting PM2 services...$(NC)"
	@$(PM2) restart ecosystem.config.js
	@echo "$(GREEN)✓ Services restarted$(NC)"

status: ## 查看 PM2 服务状态
	@$(PM2) list

worker: ## 单独启动 Taskiq Worker
	@echo "$(BLUE)Starting Taskiq Worker...$(NC)"
	@source $(VENV)/bin/activate && taskiq worker ragserver.tasks:broker --workers 4

pm2-logs: ## 查看 PM2 日志
	@$(PM2) logs

pm2-monit: ## 监控 PM2 服务
	@$(PM2) monit

pm2-delete: ## 删除所有 PM2 进程
	@echo "$(BLUE)Deleting PM2 processes...$(NC)"
	@$(PM2) delete ecosystem.config.js || true
	@echo "$(GREEN)✓ PM2 processes deleted$(NC)"

##@ 测试和质量检查

test: ## 运行测试
	@echo "$(BLUE)Running tests...$(NC)"
	@source $(VENV)/bin/activate && pytest tests/ -v

test-cov: ## 运行测试并生成覆盖率报告
	@echo "$(BLUE)Running tests with coverage...$(NC)"
	@source $(VENV)/bin/activate && pytest tests/ -v --cov=ragserver --cov-report=html --cov-report=term

lint: ## 代码检查（ruff）
	@echo "$(BLUE)Running linter...$(NC)"
	@source $(VENV)/bin/activate && ruff check ragserver/

format: ## 格式化代码（ruff）
	@echo "$(BLUE)Formatting code...$(NC)"
	@source $(VENV)/bin/activate && ruff format ragserver/

type-check: ## 类型检查（mypy）
	@echo "$(BLUE)Running type checker...$(NC)"
	@source $(VENV)/bin/activate && mypy ragserver/

##@ 清理

clean: ## 清理临时文件和缓存
	@echo "$(BLUE)Cleaning temporary files...$(NC)"
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name "*.pyc" -delete 2>/dev/null || true
	@find . -type f -name "*.pyo" -delete 2>/dev/null || true
	@rm -rf htmlcov/ .coverage 2>/dev/null || true
	@rm -rf logs/*.log 2>/dev/null || true
	@echo "$(GREEN)✓ Temporary files cleaned$(NC)"

clean-all: clean pm2-delete docker-clean ## 清理所有（包括 Docker 和 PM2）
	@echo "$(GREEN)✓ All cleaned$(NC)"

##@ 一键操作

setup: setup-env install docker-up db-init ## 一键设置开发环境
	@echo "$(GREEN)=====================================$(NC)"
	@echo "$(GREEN)✓ Development environment is ready!$(NC)"
	@echo "$(GREEN)=====================================$(NC)"
	@echo ""
	@echo "$(YELLOW)Next steps:$(NC)"
	@echo "  1. Update .env with your API keys"
	@echo "  2. Run 'make start' to start the application"
	@echo "  3. Visit http://localhost:8000/docs for API documentation"

up: docker-up start ## 一键启动所有服务（Docker + PM2）
	@echo "$(GREEN)=====================================$(NC)"
	@echo "$(GREEN)✓ All services are running!$(NC)"
	@echo "$(GREEN)=====================================$(NC)"
	@echo ""
	@echo "$(YELLOW)Services:$(NC)"
	@echo "  - API:         http://localhost:8000"
	@echo "  - API Docs:    http://localhost:8000/docs"
	@echo "  - MinIO:       http://localhost:9001"
	@echo "  - Grafana:     http://localhost:3000"
	@echo ""
	@echo "Run 'make status' to check PM2 services"

down: stop docker-down ## 一键停止所有服务（PM2 + Docker）
	@echo "$(GREEN)✓ All services stopped$(NC)"

logs: ## 查看所有日志（Docker + PM2）
	@echo "$(BLUE)Docker logs in one terminal, PM2 logs in another...$(NC)"
	@echo "Run 'make docker-logs' or 'make pm2-logs' separately"

##@ 其他

shell: ## 进入 Python Shell（IPython）
	@echo "$(BLUE)Starting Python shell...$(NC)"
	@source $(VENV)/bin/activate && ipython

db-shell: ## 进入数据库 Shell（psql）
	@echo "$(BLUE)Connecting to database...$(NC)"
	@docker compose exec postgres psql -U ragserver -d ragserver

redis-shell: ## 进入 Redis Shell
	@echo "$(BLUE)Connecting to Redis...$(NC)"
	@docker compose exec redis redis-cli -a ragserver_redis_password

minio-console: ## 打开 MinIO 控制台
	@echo "$(BLUE)Opening MinIO Console...$(NC)"
	@echo "URL: http://localhost:9001"
	@echo "Username: ragserver"
	@echo "Password: ragserver_minio_password"
	@open http://localhost:9001 || xdg-open http://localhost:9001 || echo "Please open http://localhost:9001 manually"

grafana-console: ## 打开 Grafana 控制台
	@echo "$(BLUE)Opening Grafana Console...$(NC)"
	@echo "URL: http://localhost:3000"
	@echo "Username: admin"
	@echo "Password: admin"
	@open http://localhost:3000 || xdg-open http://localhost:3000 || echo "Please open http://localhost:3000 manually"

version: ## 显示版本信息
	@echo "$(BLUE)RAG Knowledge Base Server$(NC)"
	@echo "Version: 1.0.0"
	@echo ""
	@echo "Python: $$($(PYTHON) --version)"
	@echo "Docker: $$(docker --version)"
	@echo "PM2: $$($(PM2) --version)"
	@echo "UV: $$($(UV) --version)"

