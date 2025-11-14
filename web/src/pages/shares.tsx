import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { Plus, MoreVertical, Copy, ExternalLink } from 'lucide-react';
import { sharesApi } from '@/api/shares';
import PageLayout from '@/components/layout/page-layout';
import { formatDate } from '@/lib/utils';

export default function SharesPage() {
  const queryClient = useQueryClient();

  const { data: shares, isLoading } = useQuery({
    queryKey: ['shares'],
    queryFn: () => sharesApi.list(),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => sharesApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['shares'] });
    },
  });

  const copyShareLink = (token: string) => {
    const url = `${window.location.origin}/shares/${token}`;
    navigator.clipboard.writeText(url);
    // TODO: 显示复制成功提示
    alert('分享链接已复制到剪贴板');
  };

  const handleDelete = (id: string, name?: string) => {
    if (window.confirm(`确定要删除分享链接${name ? `「${name}」` : ''}吗？`)) {
      deleteMutation.mutate(id);
    }
  };

  return (
    <PageLayout
      title="分享管理"
      description="管理您的知识库分享链接"
      action={
        <Button>
          <Plus className="mr-2 h-4 w-4" />
          创建分享链接
        </Button>
      }
    >
      {isLoading ? (
        <div className="flex items-center justify-center py-12">
          <div className="text-muted-foreground">加载中...</div>
        </div>
      ) : shares && shares.length > 0 ? (
        <div className="grid gap-4">
          {shares.map((share) => (
            <Card key={share.id}>
              <CardHeader>
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <CardTitle className="flex items-center gap-2">
                      {share.collection_name || '未命名知识库'}
                      <Badge variant={share.is_enabled ? 'default' : 'secondary'}>
                        {share.is_enabled ? '已启用' : '已禁用'}
                      </Badge>
                    </CardTitle>
                    <CardDescription className="mt-1">
                      分享令牌: {share.share_token}
                    </CardDescription>
                  </div>
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button variant="ghost" size="icon">
                        <MoreVertical className="h-4 w-4" />
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end">
                      <DropdownMenuItem onClick={() => copyShareLink(share.share_token)}>
                        <Copy className="mr-2 h-4 w-4" />
                        复制链接
                      </DropdownMenuItem>
                      <DropdownMenuItem
                        onClick={() => window.open(`/shares/${share.share_token}`, '_blank')}
                      >
                        <ExternalLink className="mr-2 h-4 w-4" />
                        打开链接
                      </DropdownMenuItem>
                      <DropdownMenuItem
                        onClick={() => handleDelete(share.id, share.collection_name)}
                        className="text-destructive"
                      >
                        删除
                      </DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
                </div>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                  <div>
                    <p className="text-muted-foreground">使用次数</p>
                    <p className="font-medium">{share.usage_count}</p>
                  </div>
                  <div>
                    <p className="text-muted-foreground">创建时间</p>
                    <p className="font-medium">{formatDate(share.created_at)}</p>
                  </div>
                  {share.expires_at && (
                    <div>
                      <p className="text-muted-foreground">过期时间</p>
                      <p className="font-medium">{formatDate(share.expires_at)}</p>
                    </div>
                  )}
                  {share.last_used_at && (
                    <div>
                      <p className="text-muted-foreground">最后使用</p>
                      <p className="font-medium">{formatDate(share.last_used_at)}</p>
                    </div>
                  )}
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      ) : (
        <div className="flex flex-col items-center justify-center py-12">
          <ExternalLink className="h-16 w-16 text-muted-foreground mb-4" />
          <h3 className="text-lg font-semibold mb-2">还没有分享链接</h3>
          <p className="text-muted-foreground mb-4 text-center max-w-sm">
            创建分享链接来让他人无需登录即可搜索您的知识库
          </p>
          <Button>
            <Plus className="mr-2 h-4 w-4" />
            创建分享链接
          </Button>
        </div>
      )}
    </PageLayout>
  );
}

