import aioboto3
import hashlib
from typing import BinaryIO, Optional, Dict
from loguru import logger
from ragserver.config import settings
from botocore.exceptions import ClientError
from contextlib import asynccontextmanager
from io import BytesIO
from datetime import datetime
import magic


class AsyncMinioClient:
    def __init__(self):
        self.session = aioboto3.Session()
        self.endpoint_url = f'http://{settings.minio_host}:{settings.minio_port}'
        self.access_key = settings.minio_access_key
        self.secret_key = settings.minio_secret_key
        self._initialized = False
    
    @asynccontextmanager
    async def _get_client(self):
        """获取异步 S3 客户端"""
        async with self.session.client(
            's3',
            endpoint_url=self.endpoint_url,
            aws_access_key_id=self.access_key,
            aws_secret_access_key=self.secret_key,
            region_name=None,
        ) as client:
            yield client
    
    async def _ensure_bucket(self, client, bucket_name: str):
        """确保单个桶存在"""
        try:
            await client.head_bucket(Bucket=bucket_name)
            logger.info(f"Bucket {bucket_name} already exists")
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code')
            if error_code == '404':
                await client.create_bucket(Bucket=bucket_name)
                logger.info(f"Created bucket {bucket_name}")
            else:
                logger.error(f"Error with bucket {bucket_name}: {e}")
                raise
    
    async def _initialize_once(self):
        """首次调用时初始化桶"""
        if not self._initialized:
            async with self._get_client() as client:
                await self._ensure_bucket(client, settings.minio_bucket_documents)
                await self._ensure_bucket(client, settings.minio_bucket_avatars)
                await self._ensure_bucket(client, settings.minio_bucket_temp)
            self._initialized = True
            logger.info("Async MinIO client initialized")
    
    def _calculate_md5(self, file_content: bytes) -> str:
        """计算文件内容的 MD5 值"""
        return hashlib.md5(file_content).hexdigest()
    
    def _calculate_sha256(self, file_content: bytes) -> str:
        """计算文件内容的 SHA256 值"""
        return hashlib.sha256(file_content).hexdigest()
    
    def _get_file_extension(self, file_name: str) -> str:
        """获取文件扩展名"""
        if '.' in file_name:
            return file_name.rsplit('.', 1)[1].lower()
        return ''
    
    def _get_mime_type(self, file_content: bytes) -> str:
        mime = magic.Magic(mime=True)
        return mime.from_buffer(file_content)

    def _generate_object_key(self, md5_hash: str, extension: str = '') -> str:
        """
        生成对象存储的 key
        格式: md5[:2]/md5[2:4]/md5.extension
        使用前缀分层可以提高性能
        """
        prefix = f"{md5_hash[:2]}/{md5_hash[2:4]}"
        if extension:
            return f"{prefix}/{md5_hash}.{extension}"
        return f"{prefix}/{md5_hash}"
    
    async def _check_file_exists(self, client, bucket_name: str, object_key: str) -> bool:
        """检查文件是否已存在"""
        try:
            await client.head_object(Bucket=bucket_name, Key=object_key)
            return True
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code')
            if error_code == '404':
                return False
            raise
    
    async def upload_file(
        self, 
        bucket_name: str, 
        file: BinaryIO, 
        file_name: str, 
        public: bool = False,
    ) -> Dict[str, any]:
        """
        上传文件并返回完整信息
        
        Args:
            bucket_name: 桶名称
            file: 文件对象
            file_name: 原始文件名
            public: 是否公开访问
        Returns:
            dict: {
                'filename': '原始文件名',
                'file_type': 'MIME类型',
                'file_size': 文件大小（字节）,
                'file_path': '对象存储路径',
                's3_url': 'S3访问URL',
                'file_hash': 'SHA256哈希值',
                'md5': 'MD5哈希值',
                'extension': '文件扩展名',
                'existed': True/False,  # 文件是否已存在（秒传）
                'upload_time': '上传时间'
            }
        """
        await self._initialize_once()
        
        # 读取文件内容
        file_content = file.read()
        file.seek(0)  # 重置文件指针
        
        # 计算哈希值
        md5_hash = self._calculate_md5(file_content)
        sha256_hash = self._calculate_sha256(file_content)
        
        # 获取文件信息
        file_size = len(file_content)
        file_type = self._get_file_extension(file_name)
        mime_type = self._get_mime_type(file_content)
        
        # 生成对象 key
        object_key = self._generate_object_key(md5_hash, mime_type)
        
        # 生成 S3 URL (必须在 object_key 生成之后)
        if public:
            s3_url = f"{settings.minio_public_host}:{settings.minio_port}/{bucket_name}/{object_key}"
        else:
            s3_url = f"{self.endpoint_url}/{bucket_name}/{object_key}"
        
        # 当前时间
        upload_time = datetime.now().isoformat()
        
        async with self._get_client() as client:
            # 检查文件是否已存在（实现秒传）
            file_existed = await self._check_file_exists(client, bucket_name, object_key)
            
            if file_existed:
                logger.info(f"File {file_name} (MD5: {md5_hash}) already exists in {bucket_name}, skipping upload")
            else:
                # 上传文件
                file_obj = BytesIO(file_content)
                await client.upload_fileobj(
                    file_obj, 
                    bucket_name, 
                    object_key, 
                    ExtraArgs={
                        'ContentType': mime_type,
                        'Metadata': {
                            'original-filename': file_name,
                            'md5': md5_hash,
                            'sha256': sha256_hash,
                            'file-size': str(file_size),
                            'upload-time': upload_time,
                            'ACL': 'public-read' if public else None
                        }
                    }
                )
                logger.info(f"Uploaded {file_name} (MD5: {md5_hash}, SHA256: {sha256_hash}) to {bucket_name}/{object_key}")
        
        # 生成 S3 URL
        
        
        return {
            'filename': file_name,
            'mime_type': mime_type,
            'file_size': file_size,
            'file_path': object_key,
            's3_url': s3_url,
            'file_hash': sha256_hash,
            'md5': md5_hash,
            'file_type': file_type,
            'existed': file_existed,
            'upload_time': upload_time
        }
    
    async def get_file_by_md5(
        self, 
        bucket_name: str, 
        md5_hash: str, 
        extension: str = ''
    ) -> Optional[Dict[str, any]]:
        """
        通过 MD5 获取文件信息和下载路径
        
        Args:
            bucket_name: 桶名称
            md5_hash: 文件的 MD5 值
            extension: 文件扩展名（可选）
            
        Returns:
            dict: {
                'object_key': 'xx/xx/xxx.ext',
                'url': 'download_url',
                'metadata': {...}
            } 或 None（文件不存在）
        """
        await self._initialize_once()
        
        object_key = self._generate_object_key(md5_hash, extension)
        
        async with self._get_client() as client:
            try:
                response = await client.head_object(Bucket=bucket_name, Key=object_key)
                
                download_url = f"{self.endpoint_url}/{bucket_name}/{object_key}"
                
                return {
                    'object_key': object_key,
                    'url': download_url,
                    'metadata': response.get('Metadata', {}),
                    'content_type': response.get('ContentType'),
                    'size': response.get('ContentLength'),
                    'last_modified': response.get('LastModified')
                }
            except ClientError as e:
                error_code = e.response.get('Error', {}).get('Code')
                if error_code == '404':
                    logger.warning(f"File with MD5 {md5_hash} not found in {bucket_name}")
                    return None
                raise
    
    async def download_file_by_md5(
        self, 
        bucket_name: str, 
        md5_hash: str, 
        extension: str = ''
    ):
        """通过 MD5 下载文件"""
        await self._initialize_once()
        
        object_key = self._generate_object_key(md5_hash, extension)
        
        async with self._get_client() as client:
            return await client.get_object(Bucket=bucket_name, Key=object_key)
    
    async def download_file(self, bucket_name: str, file_name: str):
        """通过完整路径下载文件（保留原方法）"""
        await self._initialize_once()
        async with self._get_client() as client:
            return await client.get_object(Bucket=bucket_name, Key=file_name)
    
    async def delete_file_by_md5(
        self, 
        bucket_name: str, 
        md5_hash: str, 
        extension: str = ''
    ):
        """通过 MD5 删除文件"""
        await self._initialize_once()
        
        object_key = self._generate_object_key(md5_hash, extension)
        
        async with self._get_client() as client:
            await client.delete_object(Bucket=bucket_name, Key=object_key)
            logger.info(f"Deleted file with MD5 {md5_hash} from {bucket_name}")
    
    async def delete_file(self, bucket_name: str, file_name: str):
        """通过完整路径删除文件（保留原方法）"""
        await self._initialize_once()
        async with self._get_client() as client:
            await client.delete_object(Bucket=bucket_name, Key=file_name)
            logger.info(f"Deleted {file_name} from {bucket_name}")
    
    async def list_files(self, bucket_name: str, prefix: str = ''):
        """列出文件"""
        await self._initialize_once()
        async with self._get_client() as client:
            params = {'Bucket': bucket_name}
            if prefix:
                params['Prefix'] = prefix
            return await client.list_objects_v2(**params)
    
    async def generate_presigned_url(
        self,
        bucket_name: str,
        md5_hash: str,
        extension: str = '',
        expiration: int = 3600
    ) -> str:
        """
        生成预签名 URL（用于临时访问）
        
        Args:
            bucket_name: 桶名称
            md5_hash: 文件 MD5
            extension: 文件扩展名
            expiration: 过期时间（秒），默认 1 小时
            
        Returns:
            预签名 URL
        """
        await self._initialize_once()
        
        object_key = self._generate_object_key(md5_hash, extension)
        
        async with self._get_client() as client:
            url = await client.generate_presigned_url(
                'get_object',
                Params={'Bucket': bucket_name, 'Key': object_key},
                ExpiresIn=expiration
            )
            return url


minio_client = AsyncMinioClient()
