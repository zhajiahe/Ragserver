# RAG知识库管理平台 - 前端设计文档

## 一、项目概述

### 1.1 项目定位
企业级知识库管理平台的Web前端系统，提供文档管理、智能搜索和知识库分享功能。

### 1.2 核心功能
- 用户认证（登录/注册）
- 知识库管理（CRUD）
- 文档上传与处理
- 智能搜索（向量/全文/混合）
- 知识库分享

### 1.3 技术栈

| 类别 | 技术选型 | 说明 |
|------|---------|------|
| **模板** | [react-vite-shadcn-ui](https://github.com/dan5py/react-vite-shadcn-ui) | 官方推荐模板 |
| **核心框架** | React 18 + TypeScript | hooks + 类型安全 |
| **构建工具** | Vite | 快速构建 |
| **UI组件库** | shadcn/ui | Radix UI + TailwindCSS |
| **样式方案** | TailwindCSS v3 | 原子化CSS |
| **状态管理** | Zustand | 轻量级状态管理 |
| **数据请求** | TanStack Query | 数据获取和缓存 |
| **路由** | React Router v6 | 客户端路由 |
| **表单** | React Hook Form + Zod | 表单验证 |
| **HTTP客户端** | Axios | API调用 |
| **图标** | Lucide React | 图标库 |
| **文件上传** | react-dropzone | 拖拽上传 |
| **包管理** | pnpm | 推荐使用 |

---

## 二、快速开始

### 2.1 基于模板创建项目

```bash
# 1. 克隆模板
git clone https://github.com/dan5py/react-vite-shadcn-ui.git rag-frontend
cd rag-frontend

# 2. 安装依赖
pnpm install

# 3. 安装额外依赖
pnpm add zustand @tanstack/react-query axios react-router-dom react-hook-form @hookform/resolvers zod react-dropzone date-fns

# 4. 安装需要的 shadcn/ui 组件
npx shadcn-ui@latest add dialog
npx shadcn-ui@latest add dropdown-menu
npx shadcn-ui@latest add table
npx shadcn-ui@latest add tabs
npx shadcn-ui@latest add select
npx shadcn-ui@latest add toast
npx shadcn-ui@latest add progress
npx shadcn-ui@latest add form
npx shadcn-ui@latest add textarea
npx shadcn-ui@latest add checkbox
npx shadcn-ui@latest add radio-group
npx shadcn-ui@latest add switch
npx shadcn-ui@latest add slider
npx shadcn-ui@latest add separator
npx shadcn-ui@latest add alert
npx shadcn-ui@latest add avatar
npx shadcn-ui@latest add skeleton
npx shadcn-ui@latest add tooltip
npx shadcn-ui@latest add popover
npx shadcn-ui@latest add sheet

# 5. 启动开发服务器
pnpm dev
```

### 2.2 环境配置

```bash
# .env.development
VITE_API_BASE_URL=http://localhost:8000
VITE_APP_TITLE=RAG知识库管理平台
VITE_UPLOAD_MAX_SIZE=104857600

# .env.production
VITE_API_BASE_URL=https://api.yourdomain.com
VITE_APP_TITLE=RAG知识库管理平台
VITE_UPLOAD_MAX_SIZE=104857600
```

---

## 三、项目结构

```
rag-frontend/
├── src/
│   ├── components/
│   │   ├── ui/                    # shadcn/ui 组件（自动生成）
│   │   ├── layout/                # 布局组件
│   │   │   ├── header.tsx
│   │   │   ├── sidebar.tsx
│   │   │   └── page-layout.tsx
│   │   ├── collection/            # 知识库组件
│   │   │   ├── collection-card.tsx
│   │   │   ├── collection-form.tsx
│   │   │   └── collection-list.tsx
│   │   ├── document/              # 文档组件
│   │   │   ├── document-table.tsx
│   │   │   ├── document-upload.tsx
│   │   │   └── document-viewer.tsx
│   │   ├── search/                # 搜索组件
│   │   │   ├── search-bar.tsx
│   │   │   └── search-results.tsx
│   │   └── share/                 # 分享组件
│   │       └── share-link-form.tsx
│   ├── pages/                     # 页面
│   │   ├── auth/
│   │   │   ├── login.tsx
│   │   │   └── register.tsx
│   │   ├── dashboard.tsx
│   │   ├── collections.tsx
│   │   ├── search.tsx
│   │   └── shares.tsx
│   ├── api/                       # API接口
│   │   ├── client.ts
│   │   ├── auth.ts
│   │   ├── collections.ts
│   │   ├── documents.ts
│   │   ├── search.ts
│   │   └── shares.ts
│   ├── hooks/                     # 自定义Hooks
│   │   ├── use-auth.ts
│   │   ├── use-collections.ts
│   │   └── use-toast.ts
│   ├── store/                     # 状态管理
│   │   ├── auth-store.ts
│   │   └── ui-store.ts
│   ├── lib/                       # 工具函数
│   │   ├── utils.ts
│   │   └── validations.ts
│   ├── types/                     # 类型定义
│   │   ├── api.ts
│   │   ├── collection.ts
│   │   ├── document.ts
│   │   └── search.ts
│   ├── App.tsx
│   └── main.tsx
├── .env.example
├── .env.development
├── components.json                # shadcn/ui 配置
├── tailwind.config.ts
├── vite.config.ts
└── package.json
```

---

## 四、核心实现

### 4.1 API 客户端配置

```typescript
// src/api/client.ts
import axios from 'axios';

const client = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL,
  timeout: 30000,
});

// 请求拦截器
client.interceptors.request.use((config) => {
  const token = localStorage.getItem('token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// 响应拦截器
client.interceptors.response.use(
  (response) => response.data,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('token');
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

export default client;
```

### 4.2 路由配置

```typescript
// src/App.tsx
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Toaster } from '@/components/ui/toaster';
import { useAuthStore } from '@/store/auth-store';

// Pages
import Login from '@/pages/auth/login';
import Register from '@/pages/auth/register';
import Dashboard from '@/pages/dashboard';
import Collections from '@/pages/collections';
import Search from '@/pages/search';
import Shares from '@/pages/shares';

const queryClient = new QueryClient();

function PrivateRoute({ children }: { children: React.ReactNode }) {
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);
  return isAuthenticated ? children : <Navigate to="/login" />;
}

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Register />} />
          <Route path="/shares/:token" element={<PublicShare />} />
          
          <Route path="/" element={<PrivateRoute><Dashboard /></PrivateRoute>} />
          <Route path="/collections" element={<PrivateRoute><Collections /></PrivateRoute>} />
          <Route path="/collections/:id" element={<PrivateRoute><CollectionDetail /></PrivateRoute>} />
          <Route path="/search" element={<PrivateRoute><Search /></PrivateRoute>} />
          <Route path="/shares" element={<PrivateRoute><Shares /></PrivateRoute>} />
        </Routes>
        <Toaster />
      </BrowserRouter>
    </QueryClientProvider>
  );
}

export default App;
```

### 4.3 状态管理

```typescript
// src/store/auth-store.ts
import { create } from 'zustand';
import { persist } from 'zustand/middleware';

interface User {
  id: string;
  username: string;
  email: string;
}

interface AuthState {
  user: User | null;
  token: string | null;
  isAuthenticated: boolean;
  login: (token: string, user: User) => void;
  logout: () => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      user: null,
      token: null,
      isAuthenticated: false,
      login: (token, user) => {
        localStorage.setItem('token', token);
        set({ token, user, isAuthenticated: true });
      },
      logout: () => {
        localStorage.removeItem('token');
        set({ token: null, user: null, isAuthenticated: false });
      },
    }),
    { name: 'auth-storage' }
  )
);
```

### 4.4 类型定义

```typescript
// src/types/collection.ts
export interface Collection {
  id: string;
  name: string;
  description?: string;
  icon_url?: string;
  status: 'active' | 'archived';
  document_count: number;
  chunk_count: number;
  total_size: number;
  created_at: string;
  updated_at: string;
}

export interface CollectionCreate {
  name: string;
  description?: string;
  icon_url?: string;
  settings?: {
    chunking_strategy?: {
      strategy_type: 'fixed' | 'paragraph' | 'semantic';
      config: Record<string, any>;
    };
  };
}

// src/types/document.ts
export interface Document {
  id: string;
  collection_id: string;
  filename: string;
  file_type: string;
  file_size: number;
  status: 'pending' | 'processing' | 'completed' | 'failed';
  chunk_count: number;
  created_at: string;
}

// src/types/search.ts
export interface SearchRequest {
  query: string;
  collection_ids: string[];
  mode: 'vector' | 'fulltext' | 'hybrid';
  top_k?: number;
  threshold?: number;
}

export interface SearchResult {
  chunk_id: string;
  document_id: string;
  document_name: string;
  collection_name: string;
  content: string;
  score: number;
}
```

---

## 五、关键页面实现

### 5.1 登录页面

```typescript
// src/pages/auth/login.tsx
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import * as z from 'zod';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Label } from '@/components/ui/label';
import { useNavigate } from 'react-router-dom';
import { useAuthStore } from '@/store/auth-store';
import { authApi } from '@/api/auth';

const loginSchema = z.object({
  username: z.string().min(1, '请输入用户名'),
  password: z.string().min(8, '密码至少8位'),
});

type LoginForm = z.infer<typeof loginSchema>;

export default function Login() {
  const navigate = useNavigate();
  const login = useAuthStore((state) => state.login);
  
  const { register, handleSubmit, formState: { errors } } = useForm<LoginForm>({
    resolver: zodResolver(loginSchema),
  });

  const onSubmit = async (data: LoginForm) => {
    try {
      const result = await authApi.login(data);
      login(result.access_token, result.user);
      navigate('/');
    } catch (error) {
      console.error('Login failed:', error);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-muted/40">
      <Card className="w-[400px]">
        <CardHeader>
          <CardTitle>登录</CardTitle>
          <CardDescription>输入您的账号密码登录系统</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="username">用户名</Label>
              <Input id="username" {...register('username')} />
              {errors.username && (
                <p className="text-sm text-destructive">{errors.username.message}</p>
              )}
            </div>
            <div className="space-y-2">
              <Label htmlFor="password">密码</Label>
              <Input id="password" type="password" {...register('password')} />
              {errors.password && (
                <p className="text-sm text-destructive">{errors.password.message}</p>
              )}
            </div>
            <Button type="submit" className="w-full">登录</Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
```

### 5.2 知识库列表页面

```typescript
// src/pages/collections.tsx
import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Plus } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { collectionsApi } from '@/api/collections';
import CollectionCard from '@/components/collection/collection-card';
import CollectionForm from '@/components/collection/collection-form';
import PageLayout from '@/components/layout/page-layout';

export default function Collections() {
  const [createOpen, setCreateOpen] = useState(false);

  const { data: collections, isLoading } = useQuery({
    queryKey: ['collections'],
    queryFn: () => collectionsApi.list(),
  });

  return (
    <PageLayout
      title="知识库"
      action={
        <Button onClick={() => setCreateOpen(true)}>
          <Plus className="mr-2 h-4 w-4" />
          创建知识库
        </Button>
      }
    >
      {isLoading ? (
        <div>加载中...</div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {collections?.map((collection) => (
            <CollectionCard key={collection.id} collection={collection} />
          ))}
        </div>
      )}

      <CollectionForm open={createOpen} onOpenChange={setCreateOpen} />
    </PageLayout>
  );
}
```

### 5.3 搜索页面

```typescript
// src/pages/search.tsx
import { useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { Search as SearchIcon } from 'lucide-react';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { searchApi } from '@/api/search';
import SearchResults from '@/components/search/search-results';
import PageLayout from '@/components/layout/page-layout';
import type { SearchRequest } from '@/types/search';

export default function Search() {
  const [query, setQuery] = useState('');
  const [mode, setMode] = useState<'vector' | 'fulltext' | 'hybrid'>('vector');

  const { mutate: search, data: results, isLoading } = useMutation({
    mutationFn: (params: SearchRequest) => searchApi.search(params),
  });

  const handleSearch = () => {
    if (!query.trim()) return;
    
    search({
      query,
      collection_ids: [], // 从用户选择获取
      mode,
      top_k: 10,
    });
  };

  return (
    <PageLayout title="搜索">
      <div className="space-y-6">
        <div className="flex gap-2">
          <Input
            placeholder="输入搜索内容..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
            className="flex-1"
          />
          <Select value={mode} onValueChange={(v: any) => setMode(v)}>
            <SelectTrigger className="w-[180px]">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="vector">向量搜索</SelectItem>
              <SelectItem value="fulltext">全文搜索</SelectItem>
              <SelectItem value="hybrid">混合搜索</SelectItem>
            </SelectContent>
          </Select>
          <Button onClick={handleSearch} disabled={isLoading}>
            <SearchIcon className="mr-2 h-4 w-4" />
            搜索
          </Button>
        </div>

        <SearchResults results={results || []} />
      </div>
    </PageLayout>
  );
}
```

---

## 六、组件示例

### 6.1 知识库卡片

```typescript
// src/components/collection/collection-card.tsx
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from '@/components/ui/dropdown-menu';
import { MoreVertical, FileText, Database } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import type { Collection } from '@/types/collection';

interface CollectionCardProps {
  collection: Collection;
}

export default function CollectionCard({ collection }: CollectionCardProps) {
  const navigate = useNavigate();

  return (
    <Card className="hover:shadow-lg transition-shadow cursor-pointer">
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between">
          <div className="flex-1" onClick={() => navigate(`/collections/${collection.id}`)}>
            <CardTitle>{collection.name}</CardTitle>
            <CardDescription className="mt-1.5">
              {collection.description || '暂无描述'}
            </CardDescription>
          </div>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" size="icon">
                <MoreVertical className="h-4 w-4" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem>编辑</DropdownMenuItem>
              <DropdownMenuItem className="text-destructive">删除</DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </CardHeader>
      <CardContent className="pb-3">
        <div className="flex gap-4 text-sm text-muted-foreground">
          <div className="flex items-center gap-1">
            <FileText className="h-4 w-4" />
            <span>{collection.document_count} 文档</span>
          </div>
          <div className="flex items-center gap-1">
            <Database className="h-4 w-4" />
            <span>{(collection.total_size / 1024 / 1024).toFixed(2)} MB</span>
          </div>
        </div>
      </CardContent>
      <CardFooter>
        <Badge variant={collection.status === 'active' ? 'default' : 'secondary'}>
          {collection.status === 'active' ? '活跃' : '已归档'}
        </Badge>
      </CardFooter>
    </Card>
  );
}
```

### 6.2 文档上传

```typescript
// src/components/document/document-upload.tsx
import { useCallback } from 'react';
import { useDropzone } from 'react-dropzone';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Upload } from 'lucide-react';
import { cn } from '@/lib/utils';

interface DocumentUploadProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  collectionId: string;
}

export default function DocumentUpload({ open, onOpenChange, collectionId }: DocumentUploadProps) {
  const onDrop = useCallback((files: File[]) => {
    // 处理文件上传
    console.log(files);
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'application/pdf': ['.pdf'],
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'],
      'text/plain': ['.txt'],
      'text/markdown': ['.md'],
    },
    maxSize: 100 * 1024 * 1024,
  });

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>上传文档</DialogTitle>
        </DialogHeader>
        <div
          {...getRootProps()}
          className={cn(
            'border-2 border-dashed rounded-lg p-8 text-center cursor-pointer',
            isDragActive ? 'border-primary bg-primary/5' : 'border-border'
          )}
        >
          <input {...getInputProps()} />
          <Upload className="mx-auto h-12 w-12 text-muted-foreground mb-4" />
          <p>拖拽文件到这里，或点击选择文件</p>
        </div>
      </DialogContent>
    </Dialog>
  );
}
```

---

## 七、API 接口封装

```typescript
// src/api/collections.ts
import client from './client';
import type { Collection, CollectionCreate } from '@/types/collection';

export const collectionsApi = {
  list: () => client.get<Collection[]>('/api/v1/collections'),
  get: (id: string) => client.get<Collection>(`/api/v1/collections/${id}`),
  create: (data: CollectionCreate) => client.post<Collection>('/api/v1/collections', data),
  update: (id: string, data: Partial<Collection>) => client.put(`/api/v1/collections/${id}`, data),
  delete: (id: string) => client.delete(`/api/v1/collections/${id}`),
};

// src/api/documents.ts
import client from './client';

export const documentsApi = {
  list: (collectionId: string) => client.get(`/api/v1/collections/${collectionId}/documents`),
  upload: (collectionId: string, files: FormData) => 
    client.post(`/api/v1/collections/${collectionId}/documents/upload`, files, {
      headers: { 'Content-Type': 'multipart/form-data' },
    }),
  delete: (ids: string[]) => client.delete('/api/v1/documents', { data: { document_ids: ids } }),
};

// src/api/search.ts
import client from './client';
import type { SearchRequest, SearchResult } from '@/types/search';

export const searchApi = {
  search: (params: SearchRequest) => client.post<SearchResult[]>('/api/v1/search', params),
};

// src/api/shares.ts
import client from './client';

export const sharesApi = {
  create: (collectionId: string, config?: any) => 
    client.post(`/api/v1/collections/${collectionId}/share`, config),
  list: () => client.get('/api/v1/shares'),
  delete: (id: string) => client.delete(`/api/v1/shares/${id}`),
};
```

---

## 八、部署

### 8.1 构建

```bash
# 开发
pnpm dev

# 构建
pnpm build

# 预览
pnpm preview
```

### 8.2 Docker 部署

```dockerfile
# Dockerfile
FROM node:18-alpine as builder

WORKDIR /app
COPY package.json pnpm-lock.yaml ./
RUN npm install -g pnpm && pnpm install --frozen-lockfile
COPY . .
RUN pnpm build

FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
```

```nginx
# nginx.conf
server {
  listen 80;
  root /usr/share/nginx/html;
  index index.html;

  location / {
    try_files $uri $uri/ /index.html;
  }

  location /api {
    proxy_pass http://backend:8000;
  }
}
```

---

## 九、开发规范

### 9.1 命名规范
- 组件文件：kebab-case（如 `collection-card.tsx`）
- 组件名：PascalCase（如 `CollectionCard`）
- 函数/变量：camelCase（如 `handleSubmit`）
- 类型/接口：PascalCase（如 `Collection`）

### 9.2 代码风格
- 使用 ESLint 进行代码检查
- 使用 Prettier 进行代码格式化
- 遵循 React Hooks 规范
- 使用 TypeScript 严格模式

### 9.3 提交规范
```bash
feat: 新功能
fix: Bug修复
docs: 文档更新
style: 代码格式调整
refactor: 重构
test: 测试相关
chore: 构建/工具变动
```

---

## 十、API 接口快速参考

| 功能 | 方法 | 路径 |
|------|------|------|
| **认证** |
| 注册 | POST | `/api/v1/auth/register` |
| 登录 | POST | `/api/v1/auth/login` |
| 获取用户信息 | GET | `/api/v1/auth/me` |
| **知识库** |
| 列表 | GET | `/api/v1/collections` |
| 创建 | POST | `/api/v1/collections` |
| 详情 | GET | `/api/v1/collections/{id}` |
| 更新 | PUT | `/api/v1/collections/{id}` |
| 删除 | DELETE | `/api/v1/collections/{id}` |
| **文档** |
| 列表 | GET | `/api/v1/collections/{kb_id}/documents` |
| 上传 | POST | `/api/v1/collections/{kb_id}/documents/upload` |
| 删除 | DELETE | `/api/v1/documents` |
| **搜索** |
| 搜索 | POST | `/api/v1/search` |
| **分享** |
| 创建分享 | POST | `/api/v1/collections/{id}/share` |
| 分享列表 | GET | `/api/v1/shares` |
| 公开搜索 | POST | `/api/v1/shares/{token}/search` |

---

## 十一、常见问题

### Q1: 如何添加新的 shadcn/ui 组件？
```bash
npx shadcn-ui@latest add <component-name>
```

### Q2: 如何配置反向代理？
在 `vite.config.ts` 中配置：
```typescript
export default defineConfig({
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
});
```

### Q3: 如何处理大文件上传？
使用分片上传或调整后端文件大小限制。

---

## 参考资源

- [React 官方文档](https://react.dev)
- [Vite 文档](https://vitejs.dev)
- [shadcn/ui 文档](https://ui.shadcn.com)
- [TailwindCSS 文档](https://tailwindcss.com)
- [TanStack Query 文档](https://tanstack.com/query)
- [react-vite-shadcn-ui 模板](https://github.com/dan5py/react-vite-shadcn-ui)

---

**文档版本**: v2.0  
**最后更新**: 2025-11-13  
**维护者**: 后端团队
