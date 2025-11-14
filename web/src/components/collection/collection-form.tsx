import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import * as z from 'zod';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Label } from '@/components/ui/label';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { collectionsApi } from '@/api/collections';
import type { Collection, CollectionCreate } from '@/types';
import { useEffect } from 'react';

const collectionSchema = z.object({
  name: z.string().min(1, '请输入知识库名称').max(100, '名称最多100个字符'),
  description: z.string().max(500, '描述最多500个字符').optional(),
  icon_url: z.string().url('请输入有效的URL').optional().or(z.literal('')),
});

type CollectionFormData = z.infer<typeof collectionSchema>;

interface CollectionFormProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  collection?: Collection;
}

export default function CollectionForm({
  open,
  onOpenChange,
  collection,
}: CollectionFormProps) {
  const queryClient = useQueryClient();
  const isEdit = !!collection;

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<CollectionFormData>({
    resolver: zodResolver(collectionSchema),
    defaultValues: collection
      ? {
          name: collection.name,
          description: collection.description || '',
          icon_url: collection.icon_url || '',
        }
      : undefined,
  });

  useEffect(() => {
    if (collection) {
      reset({
        name: collection.name,
        description: collection.description || '',
        icon_url: collection.icon_url || '',
      });
    } else {
      reset({ name: '', description: '', icon_url: '' });
    }
  }, [collection, reset]);

  const createMutation = useMutation({
    mutationFn: (data: CollectionCreate) => collectionsApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['collections'] });
      onOpenChange(false);
      reset();
    },
  });

  const updateMutation = useMutation({
    mutationFn: (data: Partial<Collection>) =>
      collectionsApi.update(collection!.id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['collections'] });
      onOpenChange(false);
    },
  });

  const onSubmit = (data: CollectionFormData) => {
    if (isEdit) {
      updateMutation.mutate(data);
    } else {
      createMutation.mutate(data);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{isEdit ? '编辑知识库' : '创建知识库'}</DialogTitle>
          <DialogDescription>
            {isEdit ? '修改知识库信息' : '创建一个新的知识库来管理您的文档'}
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="name">名称 *</Label>
            <Input id="name" {...register('name')} placeholder="输入知识库名称" />
            {errors.name && (
              <p className="text-sm text-destructive">{errors.name.message}</p>
            )}
          </div>

          <div className="space-y-2">
            <Label htmlFor="description">描述</Label>
            <Textarea
              id="description"
              {...register('description')}
              placeholder="简要描述这个知识库的用途"
              rows={3}
            />
            {errors.description && (
              <p className="text-sm text-destructive">{errors.description.message}</p>
            )}
          </div>

          <div className="space-y-2">
            <Label htmlFor="icon_url">图标 URL</Label>
            <Input
              id="icon_url"
              {...register('icon_url')}
              placeholder="https://example.com/icon.png"
            />
            {errors.icon_url && (
              <p className="text-sm text-destructive">{errors.icon_url.message}</p>
            )}
          </div>

          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
            >
              取消
            </Button>
            <Button
              type="submit"
              disabled={createMutation.isPending || updateMutation.isPending}
            >
              {createMutation.isPending || updateMutation.isPending
                ? '保存中...'
                : isEdit
                ? '保存'
                : '创建'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}


