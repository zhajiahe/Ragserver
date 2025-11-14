import { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import {
  Upload,
  Trash2,
  ArrowLeft,
  FolderKanban,
  FileText,
  Database,
  RefreshCw,
} from 'lucide-react';
import { collectionsApi } from '@/api/collections';
import { documentsApi } from '@/api/documents';
import DocumentTable from '@/components/document/document-table';
import DocumentUpload from '@/components/document/document-upload';
import PageLayout from '@/components/layout/page-layout';
import { formatFileSize } from '@/lib/utils';

export default function CollectionDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [uploadOpen, setUploadOpen] = useState(false);
  const [selectedIds, setSelectedIds] = useState<string[]>([]);

  const { data: collection, isLoading: collectionLoading } = useQuery({
    queryKey: ['collections', id],
    queryFn: () => collectionsApi.get(id!),
    enabled: !!id,
  });

  const { data: documents, isLoading: documentsLoading } = useQuery({
    queryKey: ['documents', id],
    queryFn: () => documentsApi.list(id!),
    enabled: !!id,
  });

  const deleteMutation = useMutation({
    mutationFn: (documentIds: string[]) => documentsApi.delete(documentIds),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['documents', id] });
      queryClient.invalidateQueries({ queryKey: ['collections', id] });
      setSelectedIds([]);
    },
  });

  const processMutation = useMutation({
    mutationFn: (documentIds: string[]) => documentsApi.process(documentIds),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['documents', id] });
    },
  });

  const reprocessMutation = useMutation({
    mutationFn: (documentId: string) => documentsApi.reprocess(documentId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['documents', id] });
    },
  });

  const handleDeleteSelected = () => {
    if (selectedIds.length === 0) return;
    if (window.confirm(`确定要删除选中的 ${selectedIds.length} 个文档吗？`)) {
      deleteMutation.mutate(selectedIds);
    }
  };

  const handleProcessSelected = () => {
    if (selectedIds.length === 0) return;
    processMutation.mutate(selectedIds);
  };

  const handleDelete = (documentId: string) => {
    if (window.confirm('确定要删除此文档吗？')) {
      deleteMutation.mutate([documentId]);
    }
  };

  const handleReprocess = (documentId: string) => {
    reprocessMutation.mutate(documentId);
  };

  if (collectionLoading) {
    return (
      <PageLayout>
        <div className="flex items-center justify-center py-12">
          <div className="text-muted-foreground">加载中...</div>
        </div>
      </PageLayout>
    );
  }

  if (!collection) {
    return (
      <PageLayout>
        <div className="flex flex-col items-center justify-center py-12">
          <p className="text-muted-foreground mb-4">知识库不存在</p>
          <Button onClick={() => navigate('/collections')}>返回列表</Button>
        </div>
      </PageLayout>
    );
  }

  return (
    <PageLayout
      title={collection.name}
      description={collection.description}
      action={
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => navigate('/collections')}>
            <ArrowLeft className="mr-2 h-4 w-4" />
            返回
          </Button>
          <Button onClick={() => setUploadOpen(true)}>
            <Upload className="mr-2 h-4 w-4" />
            上传文档
          </Button>
        </div>
      }
    >
      <div className="space-y-6">
        {/* 统计卡片 */}
        <div className="grid gap-4 md:grid-cols-3">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">文档总数</CardTitle>
              <FileText className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{collection.document_count}</div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">分块总数</CardTitle>
              <Database className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{collection.chunk_count}</div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">总大小</CardTitle>
              <FolderKanban className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">
                {formatFileSize(collection.total_size_bytes)}
              </div>
            </CardContent>
          </Card>
        </div>

        {/* 文档列表 */}
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle>文档列表</CardTitle>
                <CardDescription>管理此知识库中的所有文档</CardDescription>
              </div>
              {selectedIds.length > 0 && (
                <div className="flex gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={handleProcessSelected}
                    disabled={processMutation.isPending}
                  >
                    <RefreshCw className="mr-2 h-4 w-4" />
                    处理选中 ({selectedIds.length})
                  </Button>
                  <Button
                    variant="destructive"
                    size="sm"
                    onClick={handleDeleteSelected}
                    disabled={deleteMutation.isPending}
                  >
                    <Trash2 className="mr-2 h-4 w-4" />
                    删除选中
                  </Button>
                </div>
              )}
            </div>
          </CardHeader>
          <CardContent>
            {documentsLoading ? (
              <div className="text-center py-8 text-muted-foreground">加载中...</div>
            ) : (
              <DocumentTable
                documents={documents || []}
                selectedIds={selectedIds}
                onSelectChange={setSelectedIds}
                onDelete={handleDelete}
                onReprocess={handleReprocess}
              />
            )}
          </CardContent>
        </Card>
      </div>

      {/* 上传对话框 */}
      <DocumentUpload
        open={uploadOpen}
        onOpenChange={setUploadOpen}
        collectionId={id!}
        onSuccess={() => {
          queryClient.invalidateQueries({ queryKey: ['documents', id] });
          queryClient.invalidateQueries({ queryKey: ['collections', id] });
        }}
      />
    </PageLayout>
  );
}

