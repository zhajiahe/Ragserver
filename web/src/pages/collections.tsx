import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Plus, FolderKanban } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { collectionsApi } from '@/api/collections';
import CollectionCard from '@/components/collection/collection-card';
import CollectionForm from '@/components/collection/collection-form';
import PageLayout from '@/components/layout/page-layout';
import type { Collection } from '@/types';

export default function CollectionsPage() {
  const [createOpen, setCreateOpen] = useState(false);
  const [editCollection, setEditCollection] = useState<Collection | undefined>();
  const queryClient = useQueryClient();

  const { data: collections, isLoading } = useQuery({
    queryKey: ['collections'],
    queryFn: () => collectionsApi.list(),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => collectionsApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['collections'] });
    },
  });

  const archiveMutation = useMutation({
    mutationFn: (id: string) => collectionsApi.archive(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['collections'] });
    },
  });

  const handleEdit = (collection: Collection) => {
    setEditCollection(collection);
  };

  const handleDelete = (collection: Collection) => {
    if (window.confirm(`确定要删除知识库「${collection.name}」吗？此操作无法撤销。`)) {
      deleteMutation.mutate(collection.id);
    }
  };

  const handleArchive = (collection: Collection) => {
    archiveMutation.mutate(collection.id);
  };

  return (
    <PageLayout
      title="知识库"
      description="管理您的所有知识库"
      action={
        <Button onClick={() => setCreateOpen(true)}>
          <Plus className="mr-2 h-4 w-4" />
          创建知识库
        </Button>
      }
    >
      {isLoading ? (
        <div className="flex items-center justify-center py-12">
          <div className="text-muted-foreground">加载中...</div>
        </div>
      ) : Array.isArray(collections) && collections.length > 0 ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {collections.map((collection) => (
            <CollectionCard
              key={collection.id}
              collection={collection}
              onEdit={() => handleEdit(collection)}
              onDelete={() => handleDelete(collection)}
              onArchive={() => handleArchive(collection)}
            />
          ))}
        </div>
      ) : (
        <div className="flex flex-col items-center justify-center py-12">
          <FolderKanban className="h-16 w-16 text-muted-foreground mb-4" />
          <h3 className="text-lg font-semibold mb-2">还没有知识库</h3>
          <p className="text-muted-foreground mb-4 text-center max-w-sm">
            创建您的第一个知识库来开始上传和管理文档
          </p>
          <Button onClick={() => setCreateOpen(true)}>
            <Plus className="mr-2 h-4 w-4" />
            创建知识库
          </Button>
        </div>
      )}

      {/* 创建对话框 */}
      <CollectionForm
        open={createOpen}
        onOpenChange={setCreateOpen}
      />

      {/* 编辑对话框 */}
      {editCollection && (
        <CollectionForm
          open={!!editCollection}
          onOpenChange={(open) => !open && setEditCollection(undefined)}
          collection={editCollection}
        />
      )}
    </PageLayout>
  );
}

