import { useState } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import { Search as SearchIcon, FileText } from 'lucide-react';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { searchApi } from '@/api/search';
import { collectionsApi } from '@/api/collections';
import PageLayout from '@/components/layout/page-layout';
import type { SearchRequest, SearchResult } from '@/types';

export default function SearchPage() {
  const [query, setQuery] = useState('');
  const [mode, setMode] = useState<'vector' | 'fulltext' | 'hybrid'>('vector');

  const { data: collections } = useQuery({
    queryKey: ['collections'],
    queryFn: () => collectionsApi.list(),
  });

  const {
    mutate: search,
    data: results,
    isPending,
  } = useMutation({
    mutationFn: (params: SearchRequest) => searchApi.search(params),
  });

  const handleSearch = () => {
    if (!query.trim()) return;

    search({
      query,
      collection_ids: collections?.map(c => c.id) || [],
      mode,
      top_k: 10,
      threshold: 0.7,
    });
  };

  return (
    <PageLayout title="搜索" description="在您的知识库中搜索内容">
      <div className="space-y-6">
        {/* 搜索栏 */}
        <div className="flex gap-2">
          <Input
            placeholder="输入搜索内容..."
            value={query}
            onChange={(e: React.ChangeEvent<HTMLInputElement>) => setQuery(e.target.value)}
            onKeyDown={(e: React.KeyboardEvent) => e.key === 'Enter' && handleSearch()}
            className="flex-1"
          />
          <Select value={mode} onValueChange={(v: any) => setMode(v)}>
            <SelectTrigger className="w-[150px]">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="vector">向量搜索</SelectItem>
              <SelectItem value="fulltext">全文搜索</SelectItem>
              <SelectItem value="hybrid">混合搜索</SelectItem>
            </SelectContent>
          </Select>
          <Button onClick={handleSearch} disabled={isPending || !query.trim()}>
            <SearchIcon className="mr-2 h-4 w-4" />
            {isPending ? '搜索中...' : '搜索'}
          </Button>
        </div>

        {/* 搜索模式说明 */}
        <div className="grid gap-4 md:grid-cols-3">
          <Card className={mode === 'vector' ? 'border-primary' : ''}>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm">向量搜索</CardTitle>
              <CardDescription className="text-xs">
                基于语义理解，适合自然语言查询
              </CardDescription>
            </CardHeader>
          </Card>
          <Card className={mode === 'fulltext' ? 'border-primary' : ''}>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm">全文搜索</CardTitle>
              <CardDescription className="text-xs">
                基于关键词匹配，适合精确查找
              </CardDescription>
            </CardHeader>
          </Card>
          <Card className={mode === 'hybrid' ? 'border-primary' : ''}>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm">混合搜索</CardTitle>
              <CardDescription className="text-xs">
                结合两者优势，综合检索
              </CardDescription>
            </CardHeader>
          </Card>
        </div>

        {/* 搜索结果 */}
        {results && (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-semibold">
                搜索结果 ({results.length})
              </h2>
            </div>

            {results.length > 0 ? (
              <div className="space-y-4">
                {results.map((result: SearchResult) => (
                  <Card
                    key={result.chunk_id}
                    className="hover:shadow-md transition-shadow cursor-pointer"
                  >
                    <CardHeader className="pb-3">
                      <div className="flex items-start justify-between">
                        <div className="flex-1">
                          <CardTitle className="text-base flex items-center gap-2">
                            <FileText className="h-4 w-4" />
                            {result.document_name}
                          </CardTitle>
                          <CardDescription className="mt-1">
                            {result.collection_name}
                          </CardDescription>
                        </div>
                        <Badge variant="secondary">
                          {(result.score * 100).toFixed(1)}%
                        </Badge>
                      </div>
                    </CardHeader>
                    <CardContent>
                      <p className="text-sm text-muted-foreground line-clamp-3">
                        {result.content}
                      </p>
                    </CardContent>
                  </Card>
                ))}
              </div>
            ) : (
              <div className="text-center py-12">
                <SearchIcon className="mx-auto h-12 w-12 text-muted-foreground mb-4" />
                <p className="text-muted-foreground">没有找到相关结果</p>
              </div>
            )}
          </div>
        )}

        {!results && !isPending && (
          <div className="text-center py-12">
            <SearchIcon className="mx-auto h-12 w-12 text-muted-foreground mb-4" />
            <p className="text-muted-foreground">输入关键词开始搜索</p>
          </div>
        )}
      </div>
    </PageLayout>
  );
}

