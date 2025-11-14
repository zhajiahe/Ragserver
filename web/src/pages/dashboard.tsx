import { useQuery } from '@tanstack/react-query';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { collectionsApi } from '@/api/collections';
import { FolderKanban, FileText, Database, Plus } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import PageLayout from '@/components/layout/page-layout';
import { formatRelativeTime } from '@/lib/utils';

export default function DashboardPage() {
  const navigate = useNavigate();

  const { data: collections, isLoading } = useQuery({
    queryKey: ['collections', 'recent'],
    queryFn: () => collectionsApi.list({ skip: 0, limit: 5 }),
  });

  const totalDocuments = Array.isArray(collections) 
    ? collections.reduce((sum, c) => sum + c.document_count, 0) 
    : 0;
  const totalChunks = Array.isArray(collections) 
    ? collections.reduce((sum, c) => sum + c.chunk_count, 0) 
    : 0;

  return (
    <PageLayout
      title="仪表盘"
      description="欢迎回来，这是您的知识库概览"
    >
      <div className="space-y-6">
        {/* 统计卡片 */}
        <div className="grid gap-4 md:grid-cols-3">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">知识库总数</CardTitle>
              <FolderKanban className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">
                {Array.isArray(collections) ? collections.length : 0}
              </div>
              <p className="text-xs text-muted-foreground mt-1">
                活跃知识库
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">文档总数</CardTitle>
              <FileText className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{totalDocuments}</div>
              <p className="text-xs text-muted-foreground mt-1">
                已上传文档
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">分块总数</CardTitle>
              <Database className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{totalChunks}</div>
              <p className="text-xs text-muted-foreground mt-1">
                可检索分块
              </p>
            </CardContent>
          </Card>
        </div>

        {/* 最近使用的知识库 */}
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle>最近使用</CardTitle>
                <CardDescription>您最近访问的知识库</CardDescription>
              </div>
              <Button onClick={() => navigate('/collections')}>
                <Plus className="mr-2 h-4 w-4" />
                创建知识库
              </Button>
            </div>
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <div className="text-center py-8 text-muted-foreground">加载中...</div>
            ) : Array.isArray(collections) && collections.length > 0 ? (
              <div className="space-y-4">
                {collections.map((collection) => (
                  <div
                    key={collection.id}
                    className="flex items-center justify-between p-4 border rounded-lg hover:bg-muted/50 cursor-pointer transition-colors"
                    onClick={() => navigate(`/collections/${collection.id}`)}
                  >
                    <div className="flex-1">
                      <h3 className="font-semibold">{collection.name}</h3>
                      <p className="text-sm text-muted-foreground mt-1">
                        {collection.description || '暂无描述'}
                      </p>
                      <div className="flex items-center gap-4 mt-2 text-xs text-muted-foreground">
                        <span>{collection.document_count} 文档</span>
                        <span>{collection.chunk_count} 分块</span>
                        <span>更新于 {formatRelativeTime(collection.updated_at)}</span>
                      </div>
                    </div>
                    <Button variant="ghost" size="sm">
                      查看
                    </Button>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-center py-12">
                <FolderKanban className="mx-auto h-12 w-12 text-muted-foreground mb-4" />
                <p className="text-muted-foreground mb-4">还没有知识库</p>
                <Button onClick={() => navigate('/collections')}>
                  <Plus className="mr-2 h-4 w-4" />
                  创建第一个知识库
                </Button>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </PageLayout>
  );
}

