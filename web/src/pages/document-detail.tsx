import { useParams, useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import { ArrowLeft, Database } from 'lucide-react';
import { documentsApi } from '@/api/documents';
import PageLayout from '@/components/layout/page-layout';
import { formatFileSize, formatDate } from '@/lib/utils';

const statusConfig = {
  pending: { label: '待处理', variant: 'secondary' as const },
  processing: { label: '处理中', variant: 'default' as const },
  completed: { label: '已完成', variant: 'outline' as const },
  failed: { label: '失败', variant: 'destructive' as const },
};

export default function DocumentDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();

  const { data: document, isLoading } = useQuery({
    queryKey: ['documents', id],
    queryFn: () => documentsApi.get(id!),
    enabled: !!id,
  });

  const { data: chunks } = useQuery({
    queryKey: ['documents', id, 'chunks'],
    queryFn: () => documentsApi.getChunks(id!),
    enabled: !!id,
  });

  if (isLoading) {
    return (
      <PageLayout>
        <div className="flex items-center justify-center py-12">
          <div className="text-muted-foreground">加载中...</div>
        </div>
      </PageLayout>
    );
  }

  if (!document) {
    return (
      <PageLayout>
        <div className="flex flex-col items-center justify-center py-12">
          <p className="text-muted-foreground mb-4">文档不存在</p>
          <Button onClick={() => navigate(-1)}>返回</Button>
        </div>
      </PageLayout>
    );
  }

  return (
    <PageLayout
      title={document.filename}
      action={
        <Button variant="outline" onClick={() => navigate(-1)}>
          <ArrowLeft className="mr-2 h-4 w-4" />
          返回
        </Button>
      }
    >
      <div className="space-y-6">
        {/* 文档信息 */}
        <Card>
          <CardHeader>
            <div className="flex items-start justify-between">
              <div>
                <CardTitle>文档信息</CardTitle>
                <CardDescription className="mt-1">
                  文档的详细信息和处理状态
                </CardDescription>
              </div>
              <Badge variant={statusConfig[document.status].variant}>
                {statusConfig[document.status].label}
              </Badge>
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div>
                <p className="text-sm text-muted-foreground mb-1">文件类型</p>
                <p className="font-medium uppercase">{document.file_type}</p>
              </div>
              <div>
                <p className="text-sm text-muted-foreground mb-1">文件大小</p>
                <p className="font-medium">{formatFileSize(document.file_size)}</p>
              </div>
              <div>
                <p className="text-sm text-muted-foreground mb-1">分块数量</p>
                <p className="font-medium">{document.chunk_count}</p>
              </div>
              <div>
                <p className="text-sm text-muted-foreground mb-1">上传时间</p>
                <p className="font-medium">{formatDate(document.created_at)}</p>
              </div>
            </div>

            {document.error_message && (
              <div className="rounded-md bg-destructive/10 p-3 text-sm text-destructive">
                <p className="font-medium mb-1">处理失败</p>
                <p>{document.error_message}</p>
              </div>
            )}
          </CardContent>
        </Card>

        {/* 分块列表 */}
        {chunks && chunks.length > 0 && (
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Database className="h-5 w-5" />
                文档分块 ({chunks.length})
              </CardTitle>
              <CardDescription>
                文档被分割成的文本块，用于向量检索
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {chunks.map((chunk: any, index: number) => (
                  <div key={chunk.id}>
                    {index > 0 && <Separator className="my-4" />}
                    <div className="space-y-2">
                      <div className="flex items-center gap-2">
                        <Badge variant="outline">块 {chunk.chunk_index + 1}</Badge>
                        <span className="text-xs text-muted-foreground">
                          {chunk.token_count} tokens
                        </span>
                      </div>
                      <p className="text-sm whitespace-pre-wrap">
                        {chunk.content.length > 500
                          ? `${chunk.content.slice(0, 500)}...`
                          : chunk.content}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        )}

        {/* 如果没有分块 */}
        {document.status === 'completed' && (!chunks || chunks.length === 0) && (
          <Card>
            <CardContent className="flex flex-col items-center justify-center py-12">
              <Database className="h-12 w-12 text-muted-foreground mb-4" />
              <p className="text-muted-foreground">此文档还没有生成分块</p>
            </CardContent>
          </Card>
        )}
      </div>
    </PageLayout>
  );
}

