import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { MoreVertical, FileText, Database, Calendar } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import type { Collection } from '@/types';
import { formatDate, formatFileSize } from '@/lib/utils';

interface CollectionCardProps {
  collection: Collection;
  onEdit?: () => void;
  onDelete?: () => void;
  onArchive?: () => void;
}

export default function CollectionCard({
  collection,
  onEdit,
  onDelete,
  onArchive,
}: CollectionCardProps) {
  const navigate = useNavigate();

  return (
    <Card className="hover:shadow-lg transition-shadow cursor-pointer group">
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between">
          <div
            className="flex-1"
            onClick={() => navigate(`/collections/${collection.id}`)}
          >
            <CardTitle className="flex items-center gap-2">
              {collection.icon_url && (
                <img src={collection.icon_url} alt="" className="w-6 h-6" />
              )}
              {collection.name}
            </CardTitle>
            <CardDescription className="mt-1.5 line-clamp-2">
              {collection.description || '暂无描述'}
            </CardDescription>
          </div>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" size="icon" className="opacity-0 group-hover:opacity-100">
                <MoreVertical className="h-4 w-4" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem onClick={() => navigate(`/collections/${collection.id}`)}>
                查看详情
              </DropdownMenuItem>
              {onEdit && <DropdownMenuItem onClick={onEdit}>编辑</DropdownMenuItem>}
              {onArchive && (
                <DropdownMenuItem onClick={onArchive}>
                  {collection.status === 'active' ? '归档' : '激活'}
                </DropdownMenuItem>
              )}
              {onDelete && (
                <DropdownMenuItem onClick={onDelete} className="text-destructive">
                  删除
                </DropdownMenuItem>
              )}
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
            <span>{formatFileSize(collection.total_size_bytes)}</span>
          </div>
        </div>
      </CardContent>
      <CardFooter className="pt-0 flex items-center justify-between">
        <Badge variant={collection.status === 'active' ? 'default' : 'secondary'}>
          {collection.status === 'active' ? '活跃' : '已归档'}
        </Badge>
        <div className="flex items-center gap-1 text-xs text-muted-foreground">
          <Calendar className="h-3 w-3" />
          {formatDate(collection.updated_at)}
        </div>
      </CardFooter>
    </Card>
  );
}

