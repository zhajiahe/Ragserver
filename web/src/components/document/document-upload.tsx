import { useState, useCallback } from 'react';
import { useDropzone } from 'react-dropzone';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Progress } from '@/components/ui/progress';
import { Upload, File, X } from 'lucide-react';
import { cn } from '@/lib/utils';
import { documentsApi } from '@/api/documents';
import { formatFileSize } from '@/lib/utils';

interface DocumentUploadProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  collectionId: string;
  onSuccess?: () => void;
}

export default function DocumentUpload({
  open,
  onOpenChange,
  collectionId,
  onSuccess,
}: DocumentUploadProps) {
  const [files, setFiles] = useState<File[]>([]);
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState(0);

  const onDrop = useCallback((acceptedFiles: File[]) => {
    setFiles((prev) => [...prev, ...acceptedFiles]);
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'application/pdf': ['.pdf'],
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'],
      'application/msword': ['.doc'],
      'text/plain': ['.txt'],
      'text/markdown': ['.md'],
      'text/html': ['.html'],
      'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': ['.xlsx'],
      'application/vnd.ms-excel': ['.xls'],
      'text/csv': ['.csv'],
    },
    maxSize: 100 * 1024 * 1024, // 100MB
  });

  const removeFile = (index: number) => {
    setFiles(files.filter((_, i) => i !== index));
  };

  const handleUpload = async () => {
    if (files.length === 0) return;

    try {
      setUploading(true);
      setProgress(0);

      const formData = new FormData();
      files.forEach((file) => {
        formData.append('files', file);
      });

      // 模拟进度（真实场景可用 axios onUploadProgress）
      const progressInterval = setInterval(() => {
        setProgress((prev) => {
          if (prev >= 90) {
            clearInterval(progressInterval);
            return 90;
          }
          return prev + 10;
        });
      }, 200);

      await documentsApi.upload(collectionId, formData);

      clearInterval(progressInterval);
      setProgress(100);

      // 等待一下让用户看到100%
      setTimeout(() => {
        setFiles([]);
        setProgress(0);
        onOpenChange(false);
        onSuccess?.();
      }, 500);
    } catch (error) {
      console.error('Upload failed:', error);
      alert('上传失败，请重试');
    } finally {
      setUploading(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[600px]">
        <DialogHeader>
          <DialogTitle>上传文档</DialogTitle>
          <DialogDescription>
            支持 PDF、DOCX、TXT、MD、HTML、XLSX 格式，单文件最大 100MB
          </DialogDescription>
        </DialogHeader>

        <div
          {...getRootProps()}
          className={cn(
            'border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-colors',
            isDragActive
              ? 'border-primary bg-primary/5'
              : 'border-border hover:border-primary/50',
            uploading && 'pointer-events-none opacity-50'
          )}
        >
          <input {...getInputProps()} />
          <Upload className="mx-auto h-12 w-12 text-muted-foreground mb-4" />
          {isDragActive ? (
            <p>释放文件到这里...</p>
          ) : (
            <div>
              <p className="text-sm text-muted-foreground">
                拖拽文件到这里，或点击选择文件
              </p>
              <p className="text-xs text-muted-foreground mt-2">
                支持批量上传
              </p>
            </div>
          )}
        </div>

        {files.length > 0 && (
          <div className="space-y-2 max-h-[200px] overflow-y-auto">
            {files.map((file, index) => (
              <div
                key={index}
                className="flex items-center gap-2 p-2 border rounded hover:bg-muted/50"
              >
                <File className="h-4 w-4 text-muted-foreground flex-shrink-0" />
                <span className="text-sm flex-1 truncate">{file.name}</span>
                <span className="text-xs text-muted-foreground">
                  {formatFileSize(file.size)}
                </span>
                {!uploading && (
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-6 w-6"
                    onClick={() => removeFile(index)}
                  >
                    <X className="h-4 w-4" />
                  </Button>
                )}
              </div>
            ))}
          </div>
        )}

        {uploading && (
          <div className="space-y-2">
            <Progress value={progress} />
            <p className="text-sm text-center text-muted-foreground">
              上传中... {progress}%
            </p>
          </div>
        )}

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={uploading}>
            取消
          </Button>
          <Button onClick={handleUpload} disabled={files.length === 0 || uploading}>
            {uploading ? '上传中...' : `上传 ${files.length > 0 ? `(${files.length})` : ''}`}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}


