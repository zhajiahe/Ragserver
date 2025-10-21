/**
 * PM2 配置文件
 * RAG Knowledge Base Server
 * 
 * 使用说明:
 * - 启动所有服务: pm2 start ecosystem.config.js
 * - 停止所有服务: pm2 stop ecosystem.config.js
 * - 重启所有服务: pm2 restart ecosystem.config.js
 * - 查看状态: pm2 list
 * - 查看日志: pm2 logs
 * - 监控: pm2 monit
 * 
 * 注意: PM2 会自动加载 .env 文件中的环境变量
 */

require('dotenv').config();

module.exports = {
  apps: [
    // FastAPI 应用服务
    {
      name: 'ragserver-api',
      script: '.venv/bin/uvicorn',
      args: `ragserver.main:app --host 0.0.0.0 --port ${process.env.API_PORT || 8000}`,
      instances: 1,
      exec_mode: 'fork',
      autorestart: true,
      watch: false,
      max_memory_restart: '1G',
      env_file: '.env',
      error_file: './logs/pm2/api-error.log',
      out_file: './logs/pm2/api-out.log',
      log_file: './logs/pm2/api-combined.log',
      time: true,
      merge_logs: true,
      log_date_format: 'YYYY-MM-DD HH:mm:ss Z',
    },

    // Taskiq Worker - 文档处理队列
    {
      name: 'ragserver-worker-document',
      script: '.venv/bin/taskiq',
      args: `worker ragserver.tasks:broker --workers ${process.env.TASKIQ_WORKERS_DOCUMENT || 2}`,
      instances: 1,
      exec_mode: 'fork',
      autorestart: true,
      watch: false,
      max_memory_restart: '2G',
      env_file: '.env',
      error_file: './logs/pm2/worker-doc-error.log',
      out_file: './logs/pm2/worker-doc-out.log',
      log_file: './logs/pm2/worker-doc-combined.log',
      time: true,
      merge_logs: true,
      log_date_format: 'YYYY-MM-DD HH:mm:ss Z',
    },

    // Taskiq Worker - Embedding 生成队列
    {
      name: 'ragserver-worker-embedding',
      script: '.venv/bin/taskiq',
      args: `worker ragserver.tasks:broker --workers ${process.env.TASKIQ_WORKERS_EMBEDDING || 2}`,
      instances: 1,
      exec_mode: 'fork',
      autorestart: true,
      watch: false,
      max_memory_restart: '1G',
      env_file: '.env',
      error_file: './logs/pm2/worker-emb-error.log',
      out_file: './logs/pm2/worker-emb-out.log',
      log_file: './logs/pm2/worker-emb-combined.log',
      time: true,
      merge_logs: true,
      log_date_format: 'YYYY-MM-DD HH:mm:ss Z',
    },
  ],

  /**
   * 部署配置（可选）
   * 使用 pm2 deploy 命令部署到远程服务器
   */
  deploy: {
    production: {
      user: 'deploy',
      host: 'your-production-server.com',
      ref: 'origin/main',
      repo: 'git@github.com:your-username/ragserver.git',
      path: '/var/www/ragserver',
      'post-deploy': 
        'uv sync && ' +
        'source .venv/bin/activate && ' +
        'alembic upgrade head && ' +
        'pm2 reload ecosystem.config.js --env production',
      env: {
        NODE_ENV: 'production',
      },
    },
    
    staging: {
      user: 'deploy',
      host: 'your-staging-server.com',
      ref: 'origin/develop',
      repo: 'git@github.com:your-username/ragserver.git',
      path: '/var/www/ragserver-staging',
      'post-deploy': 
        'uv sync && ' +
        'source .venv/bin/activate && ' +
        'alembic upgrade head && ' +
        'pm2 reload ecosystem.config.js --env staging',
      env: {
        NODE_ENV: 'staging',
      },
    },
  },
};

