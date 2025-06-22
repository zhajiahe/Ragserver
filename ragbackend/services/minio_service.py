import logging
import io
from typing import BinaryIO, Optional, Dict, Any
from datetime import datetime, timedelta
from urllib.parse import urljoin

from minio import Minio
from minio.error import S3Error
from fastapi import UploadFile, HTTPException
from minio.deleteobjects import DeleteObject

from ragbackend.config import (
    MINIO_ENDPOINT,
    MINIO_ACCESS_KEY, 
    MINIO_SECRET_KEY,
    MINIO_SECURE,
    MINIO_BUCKET_NAME
)

logger = logging.getLogger(__name__)


class MinIOService:
    """MinIO service for handling file storage operations."""
    
    def __init__(self):
        """Initialize MinIO client."""
        self.client = Minio(
            MINIO_ENDPOINT,
            access_key=MINIO_ACCESS_KEY,
            secret_key=MINIO_SECRET_KEY,
            secure=MINIO_SECURE
        )
        self.bucket_name = MINIO_BUCKET_NAME
    
    async def initialize(self) -> bool:
        """Initialize MinIO service and create bucket if it doesn't exist."""
        try:
            # Check if bucket exists, if not create it
            if not self.client.bucket_exists(self.bucket_name):
                self.client.make_bucket(self.bucket_name)
                logger.info(f"Created MinIO bucket: {self.bucket_name}")
            else:
                logger.info(f"MinIO bucket already exists: {self.bucket_name}")
            return True
        except S3Error as e:
            logger.error(f"Failed to initialize MinIO service: {e}")
            return False
    
    def _generate_object_path(self, user_id: str, collection_id: str, file_id: str, filename: str) -> str:
        """Generate object path following the pattern: user_id/collection_id/file_id/filename"""
        # Ensure filename doesn't contain path separators
        safe_filename = filename.replace('/', '_').replace('\\', '_')
        return f"{user_id}/{collection_id}/{file_id}/{safe_filename}"
    
    async def upload_file(
        self, 
        file: UploadFile, 
        user_id: str, 
        collection_id: str, 
        file_id: str
    ) -> Dict[str, Any]:
        """
        Upload a file to MinIO.
        
        Args:
            file: FastAPI UploadFile object
            user_id: User ID
            collection_id: Collection ID
            file_id: Unique file ID
            
        Returns:
            Dict containing file metadata
        """
        try:
            # Ensure all IDs are strings
            user_id = str(user_id)
            collection_id = str(collection_id)
            file_id = str(file_id)
            
            # Generate object path
            object_path = self._generate_object_path(user_id, collection_id, file_id, file.filename)
            
            # Get file content
            file_content = await file.read()
            file_size = len(file_content)
            
            # Reset file pointer for potential reuse
            await file.seek(0)
            
            # Upload to MinIO
            result = self.client.put_object(
                self.bucket_name,
                object_path,
                io.BytesIO(file_content),
                file_size,
                content_type=file.content_type or 'application/octet-stream'
            )
            
            # Return file metadata
            metadata = {
                'object_path': object_path,
                'filename': file.filename,
                'content_type': file.content_type,
                'size': file_size,
                'bucket': self.bucket_name,
                'etag': result.etag,
                'user_id': user_id,
                'collection_id': collection_id,
                'file_id': file_id,
                'upload_time': datetime.utcnow().isoformat()
            }
            
            logger.info(f"Successfully uploaded file: {object_path}")
            return metadata
            
        except S3Error as e:
            logger.error(f"Failed to upload file {file.filename}: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to upload file: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error uploading file {file.filename}: {e}")
            raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")
    
    async def download_file(self, object_path: str) -> BinaryIO:
        """
        Download a file from MinIO.
        
        Args:
            object_path: Path to the object in MinIO
            
        Returns:
            Binary file stream
        """
        try:
            response = self.client.get_object(self.bucket_name, object_path)
            return response
        except S3Error as e:
            logger.error(f"Failed to download file {object_path}: {e}")
            raise HTTPException(status_code=404, detail=f"File not found: {object_path}")
        except Exception as e:
            logger.error(f"Unexpected error downloading file {object_path}: {e}")
            raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")
    
    async def delete_file(self, object_path: str) -> bool:
        """
        Delete a file from MinIO.
        
        Args:
            object_path: Path to the object in MinIO
            
        Returns:
            True if successful, False otherwise
        """
        try:
            self.client.remove_object(self.bucket_name, object_path)
            logger.info(f"Successfully deleted file: {object_path}")
            return True
        except S3Error as e:
            logger.error(f"Failed to delete file {object_path}: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error deleting file {object_path}: {e}")
            return False
    
    async def delete_files_by_prefix(self, prefix: str) -> int:
        """
        Delete all files with a given prefix (e.g., user_id/collection_id/).
        
        Args:
            prefix: Object prefix to match
            
        Returns:
            Number of files deleted
        """
        try:
            objects = self.client.list_objects(self.bucket_name, prefix=prefix, recursive=True)
            object_names = [obj.object_name for obj in objects]
            
            if not object_names:
                return 0
            
            # Use remove_objects for batch deletion - need to import DeleteObject
            delete_objects = [DeleteObject(name) for name in object_names]
            errors = self.client.remove_objects(
                self.bucket_name,
                delete_objects
            )
            
            # Check for errors
            error_count = 0
            for error in errors:
                logger.error(f"Failed to delete {error.object_name}: {error}")
                error_count += 1
            
            success_count = len(object_names) - error_count
            logger.info(f"Successfully deleted {success_count} files with prefix: {prefix}")
            
            return success_count
        except Exception as e:
            logger.error(f"Unexpected error deleting files with prefix {prefix}: {e}")
            return 0
    
    async def get_file_info(self, object_path: str) -> Optional[Dict[str, Any]]:
        """
        Get file information from MinIO.
        
        Args:
            object_path: Path to the object in MinIO
            
        Returns:
            Dict containing file information or None if not found
        """
        try:
            stat = self.client.stat_object(self.bucket_name, object_path)
            return {
                'object_path': object_path,
                'size': stat.size,
                'etag': stat.etag,
                'last_modified': stat.last_modified.isoformat(),
                'content_type': stat.content_type,
                'metadata': stat.metadata
            }
        except S3Error as e:
            if e.code == 'NoSuchKey':
                return None
            logger.error(f"Failed to get file info for {object_path}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error getting file info for {object_path}: {e}")
            return None
    
    async def generate_presigned_url(
        self, 
        object_path: str, 
        expires: timedelta = timedelta(hours=1)
    ) -> str:
        """
        Generate a presigned URL for file download.
        
        Args:
            object_path: Path to the object in MinIO
            expires: URL expiration time
            
        Returns:
            Presigned URL string
        """
        try:
            url = self.client.presigned_get_object(
                self.bucket_name,
                object_path,
                expires=expires
            )
            return url
        except S3Error as e:
            logger.error(f"Failed to generate presigned URL for {object_path}: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to generate download URL: {str(e)}")
    
    async def list_files_by_prefix(self, prefix: str) -> list[Dict[str, Any]]:
        """
        List all files with a given prefix.
        
        Args:
            prefix: Object prefix to match
            
        Returns:
            List of file information dictionaries
        """
        try:
            objects = self.client.list_objects(self.bucket_name, prefix=prefix, recursive=True)
            files = []
            
            for obj in objects:
                files.append({
                    'object_path': obj.object_name,
                    'size': obj.size,
                    'last_modified': obj.last_modified.isoformat(),
                    'etag': obj.etag,
                    'is_dir': obj.is_dir
                })
            
            return files
        except Exception as e:
            logger.error(f"Unexpected error listing files with prefix {prefix}: {e}")
            return []


# Global MinIO service instance
_minio_service: Optional[MinIOService] = None


def get_minio_service() -> MinIOService:
    """Get the global MinIO service instance."""
    global _minio_service
    if _minio_service is None:
        _minio_service = MinIOService()
    return _minio_service


async def initialize_minio_service() -> bool:
    """Initialize the global MinIO service."""
    service = get_minio_service()
    return await service.initialize() 