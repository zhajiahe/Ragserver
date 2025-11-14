import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { MoreVertical, Eye, Trash2, RefreshCw } from 'lucide-react';
import { formatFileSize, formatDate } from '@/lib/utils';
import type { Document } from '@/types';
import { useNavigate } from 'react-router-dom';

interface DocumentTableProps {
  documents: Document[];
  selectedIds: string[];
  onSelectChange: (ids: string[]) => void;
  onDelete?: (id: string) => void;
  onReprocess?: (id: string) => void;
}

const statusConfig = {
  pending: { label: '待处理', variant: 'secondary' as const },
  processing: { label: '处理中', variant: 'default' as const },
  completed: { label: '已完成', variant: 'outline' as const },
  failed: { label: '失败', variant: 'destructive' as const },
};

export default function DocumentTable({
  documents,
  selectedIds,
  onSelectChange,
  onDelete,
  onReprocess,
}: DocumentTableProps) {
  const navigate = useNavigate();
  const isAllSelected = documents.length > 0 && selectedIds.length === documents.length;

  const toggleAll = () => {
    if (isAllSelected) {
      onSelectChange([]);
    } else {
      onSelectChange(documents.map((d) => d.id));
    }
  };

  const toggleOne = (id: string) => {
    if (selectedIds.includes(id)) {
      onSelectChange(selectedIds.filter((i) => i !== id));
    } else {
      onSelectChange([...selectedIds, id]);
    }
  };

  return (
    <div className="border rounded-lg">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="w-[50px]">
              <Checkbox
                checked={isAllSelected}
                onCheckedChange={toggleAll}
                aria-label="全选"
              />
            </TableHead>
            <TableHead>文件名</TableHead>
            <TableHead>类型</TableHead>
            <TableHead>大小</TableHead>
            <TableHead>状态</TableHead>
            <TableHead>分块数</TableHead>
            <TableHead>上传时间</TableHead>
            <TableHead className="w-[50px]"></TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {documents.length === 0 ? (
            <TableRow>
              <TableCell colSpan={8} className="text-center py-8 text-muted-foreground">
                暂无文档
              </TableCell>
            </TableRow>
          ) : (
            documents.map((doc) => (
              <TableRow key={doc.id}>
                <TableCell>
                  <Checkbox
                    checked={selectedIds.includes(doc.id)}
                    onCheckedChange={() => toggleOne(doc.id)}
                    aria-label={`选择 ${doc.filename}`}
                  />
                </TableCell>
                <TableCell className="font-medium max-w-[300px] truncate">
                  {doc.filename}
                </TableCell>
                <TableCell>
                  <span className="text-xs uppercase">{doc.file_type}</span>
                </TableCell>
                <TableCell>{formatFileSize(doc.file_size)}</TableCell>
                <TableCell>
                  <Badge variant={statusConfig[doc.status].variant}>
                    {statusConfig[doc.status].label}
                  </Badge>
                </TableCell>
                <TableCell>{doc.chunk_count}</TableCell>
                <TableCell className="text-sm text-muted-foreground">
                  {formatDate(doc.created_at)}
                </TableCell>
                <TableCell>
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button variant="ghost" size="icon">
                        <MoreVertical className="h-4 w-4" />
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end">
                      <DropdownMenuItem onClick={() => navigate(`/documents/${doc.id}`)}>
                        <Eye className="mr-2 h-4 w-4" />
                        查看详情
                      </DropdownMenuItem>
                      {onReprocess && doc.status === 'failed' && (
                        <DropdownMenuItem onClick={() => onReprocess(doc.id)}>
                          <RefreshCw className="mr-2 h-4 w-4" />
                          重新处理
                        </DropdownMenuItem>
                      )}
                      {onDelete && (
                        <DropdownMenuItem
                          onClick={() => onDelete(doc.id)}
                          className="text-destructive"
                        >
                          <Trash2 className="mr-2 h-4 w-4" />
                          删除
                        </DropdownMenuItem>
                      )}
                    </DropdownMenuContent>
                  </DropdownMenu>
                </TableCell>
              </TableRow>
            ))
          )}
        </TableBody>
      </Table>
    </div>
  );
}


