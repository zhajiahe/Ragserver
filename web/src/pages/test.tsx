import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';

export default function TestPage() {
  return (
    <div className="container mx-auto p-8">
      <Card className="max-w-2xl mx-auto">
        <CardHeader>
          <CardTitle>RAG 知识库管理平台</CardTitle>
          <CardDescription>前端项目初始化成功！</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-muted-foreground">
            项目已成功初始化，包含以下特性：
          </p>
          <ul className="list-disc list-inside space-y-2 text-sm">
            <li>✅ React 19 + TypeScript</li>
            <li>✅ Vite 构建工具</li>
            <li>✅ shadcn/ui 组件库</li>
            <li>✅ TailwindCSS 样式</li>
            <li>✅ Zustand 状态管理</li>
            <li>✅ TanStack Query 数据获取</li>
            <li>✅ React Router 路由</li>
            <li>✅ React Hook Form + Zod 表单验证</li>
          </ul>
          <div className="flex gap-2 pt-4">
            <Button>Primary Button</Button>
            <Button variant="outline">Outline Button</Button>
            <Button variant="ghost">Ghost Button</Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}


