# RAG 知识库管理平台 - 前端项目

基于 [react-vite-shadcn-ui](https://github.com/dan5py/react-vite-shadcn-ui) 模板开发的知识库管理系统前端。

## 技术栈

- **React 19** + **TypeScript**
- **Vite** - 构建工具
- **shadcn/ui** - UI 组件库
- **TailwindCSS** - 样式方案
- **Zustand** - 状态管理
- **TanStack Query** - 数据获取
- **React Router** - 路由管理
- **React Hook Form** + **Zod** - 表单验证

## 快速开始

### 安装依赖

```bash
pnpm install
```

### 开发模式

```bash
pnpm dev
```

### 构建生产版本

```bash
pnpm build
```

### 预览生产版本

```bash
pnpm preview
```

## 项目结构

```
src/
├── components/       # 组件
│   ├── ui/          # shadcn/ui 组件
│   ├── layout/      # 布局组件
│   ├── collection/  # 知识库组件
│   ├── document/    # 文档组件
│   ├── search/      # 搜索组件
│   └── share/       # 分享组件
├── pages/           # 页面
├── api/             # API 接口
├── hooks/           # 自定义 Hooks
├── store/           # 状态管理
├── lib/             # 工具函数
└── types/           # 类型定义
```

## 环境配置

复制 `.env.example` 为 `.env.development`:

```bash
cp .env.example .env.development
```

配置项：

```env
VITE_API_BASE_URL=http://localhost:8000
VITE_APP_TITLE=RAG知识库管理平台
VITE_UPLOAD_MAX_SIZE=104857600
```

## 添加 shadcn/ui 组件

```bash
npx shadcn@latest add <component-name>
```

## 开发指南

详见项目根目录的 `FRONTEND_DESIGN.md` 文档。

## License

MIT
