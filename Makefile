.PHONY: help install dev docker-up docker-down migrate upgrade test clean
SHELL := /bin/bash
.DEFAULT_GOAL := help

# 环境变量
UV := uv
VENV := .venv
PM2 := pm2

# 颜色输出
BLUE := \033[0;34m
GREEN := \033[0;32m
YELLOW := \033[0;33m
NC := \033[0m

##@ 帮助

help: ## 显示帮助信息
	@echo "$(BLUE)RAG Collection Server - Makefile$(NC)"
	@echo ""
	@awk 'BEGIN {FS = ":.*##"; printf "Usage:\n  make $(YELLOW)<target>$(NC)\n"} /^[a-zA-Z_-]+:.*?##/ { printf "  $(BLUE)%-15s$(NC) %s\n", $$1, $$2 } /^##@/ { printf "\n$(GREEN)%s$(NC)\n", substr($$0, 5) } ' $(MAKEFILE_LIST)

##@ 环境设置

install: ## 安装项目依赖
	@echo "$(BLUE)Installing dependencies...$(NC)"
	@$(UV) sync
	@echo "$(GREEN)✓ Dependencies installed$(NC)"

##@ Docker 服务

docker-up: ## 启动 Docker 服务
	@echo "$(BLUE)Starting Docker services...$(NC)"
	@docker compose up -d
	@echo "$(GREEN)✓ Docker services started$(NC)"

docker-down: ## 停止 Docker 服务
	@echo "$(BLUE)Stopping Docker services...$(NC)"
	@docker compose down
	@echo "$(GREEN)✓ Docker services stopped$(NC)"

##@ 数据库迁移

migrate: ## 创建数据库迁移 (需要 msg="描述")
	@echo "$(BLUE)Creating migration...$(NC)"
	@source $(VENV)/bin/activate && alembic revision --autogenerate -m "$(msg)"
	@echo "$(GREEN)✓ Migration created$(NC)"

upgrade: ## 应用数据库迁移
	@echo "$(BLUE)Upgrading database...$(NC)"
	@source $(VENV)/bin/activate && alembic upgrade head
	@echo "$(GREEN)✓ Database upgraded$(NC)"

##@ 应用管理

dev: ## 启动开发服务器
	@echo "$(BLUE)Starting development server...$(NC)"
	@source $(VENV)/bin/activate && uvicorn ragserver.main:app

start: ## 启动生产服务 (PM2)
	@echo "$(BLUE)Starting services...$(NC)"
	@$(PM2) start ecosystem.config.js
	@$(PM2) list

stop: ## 停止 PM2 服务
	@$(PM2) stop ecosystem.config.js

restart: ## 重启 PM2 服务
	@$(PM2) restart ecosystem.config.js

status: ## 查看服务状态
	@$(PM2) list

##@ 测试

test: ## 运行测试
	@echo "$(BLUE)Running tests...$(NC)"
	@source $(VENV)/bin/activate && pytest tests/ -v

##@ 清理

clean: ## 清理临时文件
	@echo "$(BLUE)Cleaning...$(NC)"
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name "*.pyc" -delete 2>/dev/null || true
	@rm -rf htmlcov/ .coverage 2>/dev/null || true
	@echo "$(GREEN)✓ Cleaned$(NC)"

##@ 一键操作

setup: install docker-up upgrade ## 一键设置开发环境
	@echo "$(GREEN)✓ Development environment ready!$(NC)"
	@echo ""
	@echo "$(YELLOW)Next:$(NC) make dev"

up: docker-up start ## 启动所有服务
	@echo "$(GREEN)✓ All services running!$(NC)"
	@echo "API: http://localhost:8000/docs"

down: stop docker-down ## 停止所有服务
	@echo "$(GREEN)✓ All services stopped$(NC)"


##@lint

lint: ## 运行lint
	@echo "$(BLUE)Running lint...$(NC)"
	@source $(VENV)/bin/activate && ruff check . --fix
	@echo "$(GREEN)✓ Lint passed$(NC)"

format: ## 格式化代码
	@echo "$(BLUE)Formatting code...$(NC)"
	@source $(VENV)/bin/activate && ruff format .
	@echo "$(GREEN)✓ Code formatted$(NC)"