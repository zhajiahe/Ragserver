"""
应用配置模块
使用 Pydantic Settings 管理环境变量配置
"""
from typing import Optional, List
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
import secrets


class Settings(BaseSettings):
    """应用配置类"""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
    
    # ==================== 应用基础配置 ====================
    app_name: str = Field(default="RAG Knowledge Base Server", description="应用名称")
    app_version: str = Field(default="1.0.0", description="应用版本")
    debug: bool = Field(default=True, description="调试模式")
    log_level: str = Field(default="INFO", description="日志级别")
    
    # ==================== 数据库配置 ====================
    # PostgreSQL 配置
    postgres_user: str = Field(default="ragserver", description="PostgreSQL 用户名")
    postgres_password: str = Field(default="ragserver_password", description="PostgreSQL 密码")
    postgres_host: str = Field(default="localhost", description="PostgreSQL 主机")
    postgres_port: int = Field(default=5432, description="PostgreSQL 端口")
    postgres_db: str = Field(default="ragserver", description="PostgreSQL 数据库名")
    
    # 数据库连接URL（自动生成）
    database_url: Optional[str] = Field(default=None, description="数据库连接URL")
    
    # 连接池配置
    db_pool_size: int = Field(default=20, description="数据库连接池大小")
    db_max_overflow: int = Field(default=10, description="连接池最大溢出数")
    db_pool_timeout: int = Field(default=30, description="连接池超时时间（秒）")
    db_pool_recycle: int = Field(default=3600, description="连接回收时间（秒）")
    db_echo: bool = Field(default=False, description="是否打印SQL语句")
    
    @property
    def async_database_url(self) -> str:
        """异步数据库连接URL"""
        if self.database_url:
            return self.database_url
        return f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
    
    @property
    def sync_database_url(self) -> str:
        """同步数据库连接URL（用于 Alembic）"""
        return f"postgresql://{self.postgres_user}:{self.postgres_password}@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
    
    # ==================== Redis 配置 ====================
    redis_host: str = Field(default="localhost", description="Redis 主机")
    redis_port: int = Field(default=6379, description="Redis 端口")
    redis_password: Optional[str] = Field(default="ragserver_redis_password", description="Redis 密码")
    redis_db: int = Field(default=0, description="Redis 数据库编号")
    redis_url: Optional[str] = Field(default=None, description="Redis 连接URL")
    
    # Taskiq 任务队列配置
    taskiq_broker_url: Optional[str] = Field(default=None, description="Taskiq Broker URL")
    taskiq_result_backend_url: Optional[str] = Field(default=None, description="Taskiq Result Backend URL")
    
    @property
    def get_redis_url(self) -> str:
        """获取 Redis 连接URL"""
        if self.redis_url:
            return self.redis_url
        if self.redis_password:
            return f"redis://:{self.redis_password}@{self.redis_host}:{self.redis_port}/{self.redis_db}"
        return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"
    
    @property
    def get_taskiq_broker_url(self) -> str:
        """获取 Taskiq Broker URL"""
        if self.taskiq_broker_url:
            return self.taskiq_broker_url
        if self.redis_password:
            return f"redis://:{self.redis_password}@{self.redis_host}:{self.redis_port}/1"
        return f"redis://{self.redis_host}:{self.redis_port}/1"
    
    @property
    def get_taskiq_result_backend_url(self) -> str:
        """获取 Taskiq Result Backend URL"""
        if self.taskiq_result_backend_url:
            return self.taskiq_result_backend_url
        if self.redis_password:
            return f"redis://:{self.redis_password}@{self.redis_host}:{self.redis_port}/2"
        return f"redis://{self.redis_host}:{self.redis_port}/2"
    
    # ==================== MinIO 对象存储配置 ====================
    minio_host: str = Field(default="localhost", description="MinIO 主机")
    minio_port: int = Field(default=9000, description="MinIO 端口")
    minio_console_port: int = Field(default=9001, description="MinIO 控制台端口")
    minio_access_key: str = Field(default="ragserver", description="MinIO Access Key")
    minio_secret_key: str = Field(default="ragserver_minio_password", description="MinIO Secret Key")
    minio_secure: bool = Field(default=False, description="是否使用 HTTPS")
    minio_bucket_documents: str = Field(default="documents", description="文档存储桶")
    minio_bucket_avatars: str = Field(default="avatars", description="头像存储桶")
    minio_bucket_temp: str = Field(default="temp", description="临时文件存储桶")
    
    # ==================== JWT 认证配置 ====================
    jwt_secret_key: str = Field(
        default_factory=lambda: secrets.token_urlsafe(32),
        description="JWT 密钥"
    )
    jwt_algorithm: str = Field(default="HS256", description="JWT 算法")
    jwt_access_token_expire_minutes: int = Field(default=1440, description="访问令牌过期时间（分钟）")
    jwt_refresh_token_expire_days: int = Field(default=30, description="刷新令牌过期时间（天）")
    
    # ==================== CORS 配置 ====================
    cors_origins: List[str] = Field(
        default=["*"],
        description="允许的跨域源"
    )
    cors_allow_credentials: bool = Field(default=True, description="是否允许携带凭证")
    cors_allow_methods: List[str] = Field(default=["*"], description="允许的HTTP方法")
    cors_allow_headers: List[str] = Field(default=["*"], description="允许的HTTP头")
    
    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v):
        """解析 CORS origins"""
        if isinstance(v, str):
            return [i.strip() for i in v.split(",")]
        return v
    
    # ==================== 文件上传配置 ====================
    max_file_size_mb: int = Field(default=100, description="最大文件大小（MB）")
    allowed_file_types: List[str] = Field(
        default=[
            "pdf", "docx", "doc", "txt", "md", 
            "html", "htm", "xlsx", "xls", "csv", 
            "pptx", "jpg", "png"
        ],
        description="允许的文件类型"
    )
    upload_chunk_size: int = Field(default=1024 * 1024, description="上传分块大小（字节）")
    
    @field_validator("allowed_file_types", mode="before")
    @classmethod
    def parse_allowed_file_types(cls, v):
        """解析允许的文件类型"""
        if isinstance(v, str):
            return [i.strip() for i in v.split(",")]
        return v
    
    @property
    def max_file_size_bytes(self) -> int:
        """最大文件大小（字节）"""
        return self.max_file_size_mb * 1024 * 1024
    
    # ==================== SiliconFlow API 配置 ====================
    siliconflow_api_key: str = Field(description="硅基流动 API Key")
    siliconflow_api_base: str = Field(
        default="https://api.siliconflow.cn/v1",
        description="硅基流动 API Base URL"
    )

    # ==================== Embedding 配置 ====================
    default_embedding_model: str = Field(default="BAAI/bge-m3", description="默认 Embedding 模型")
    embedding_dimension: int = Field(default=1024, description="Embedding 向量维度（bge-m3: 1024维）")
    
    # ==================== LLM 配置 ====================
    # 用于自然语言生成分块策略
    default_llm_provider: str = Field(default="siliconflow", description="默认 LLM 提供商")

    # SiliconFlow LLM
    siliconflow_llm_model: str = Field(default="Qwen/Qwen3-8B", description="硅基流动 LLM 模型")
    siliconflow_llm_temperature: float = Field(default=0.7, description="LLM 温度")
    siliconflow_llm_max_tokens: int = Field(default=2000, description="LLM 最大 Token 数")
    
    # ==================== 向量搜索配置 ====================
    # pgvector 索引配置
    vector_index_type: str = Field(default="hnsw", description="向量索引类型 (hnsw/ivfflat)")
    hnsw_m: int = Field(default=16, description="HNSW 索引参数 m")
    hnsw_ef_construction: int = Field(default=64, description="HNSW 索引参数 ef_construction")
    ivfflat_lists: int = Field(default=100, description="IVFFlat 索引参数 lists")
    
    # 搜索默认配置
    default_search_type: str = Field(default="hybrid", description="默认搜索类型 (vector/fulltext/hybrid)")
    default_top_k: int = Field(default=10, description="默认返回结果数")
    default_similarity_threshold: float = Field(default=0.7, description="默认相似度阈值")
    
    # 混合搜索权重
    hybrid_vector_weight: float = Field(default=0.7, description="混合搜索向量权重")
    hybrid_fulltext_weight: float = Field(default=0.3, description="混合搜索全文权重")
    
    # ==================== 缓存配置 ====================
    cache_enabled: bool = Field(default=True, description="是否启用缓存")
    cache_ttl_seconds: int = Field(default=300, description="缓存过期时间（秒）")
    query_vector_cache_ttl: int = Field(default=86400, description="查询向量缓存时间（秒）")
    search_result_cache_ttl: int = Field(default=300, description="搜索结果缓存时间（秒）")
    
    # ==================== 限流配置 ====================
    rate_limit_enabled: bool = Field(default=True, description="是否启用限流")
    rate_limit_requests_per_minute: int = Field(default=60, description="每分钟请求数限制")
    rate_limit_daily_quota: int = Field(default=10000, description="每日请求配额")
    
    # ==================== 任务队列配置 ====================
    taskiq_workers: int = Field(default=4, description="Taskiq Worker 数量")
    taskiq_max_retries: int = Field(default=3, description="任务最大重试次数")
    taskiq_retry_delay: int = Field(default=60, description="任务重试延迟（秒）")
    
    # 文档处理配置
    document_processing_timeout: int = Field(default=600, description="文档处理超时时间（秒）")
    embedding_batch_size: int = Field(default=50, description="Embedding 批量大小")
    embedding_max_concurrency: int = Field(default=3, description="Embedding 最大并发数")
    
    # ==================== 监控配置 ====================
    prometheus_enabled: bool = Field(default=True, description="是否启用 Prometheus")
    prometheus_port: int = Field(default=19090, description="Prometheus 端口")
    grafana_port: int = Field(default=13000, description="Grafana 端口")
    
    # ==================== 日志配置 ====================
    log_format: str = Field(
        default="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        description="日志格式"
    )
    log_file_enabled: bool = Field(default=True, description="是否启用日志文件")
    log_file_path: str = Field(default="logs/app.log", description="日志文件路径")
    log_file_max_size: int = Field(default=10 * 1024 * 1024, description="日志文件最大大小（字节）")
    log_file_backup_count: int = Field(default=10, description="日志文件备份数量")
    
    # ==================== 安全配置 ====================
    # 密码策略
    password_min_length: int = Field(default=8, description="密码最小长度")
    password_require_uppercase: bool = Field(default=True, description="密码是否需要大写字母")
    password_require_lowercase: bool = Field(default=True, description="密码是否需要小写字母")
    password_require_digit: bool = Field(default=True, description="密码是否需要数字")
    password_require_special: bool = Field(default=False, description="密码是否需要特殊字符")
    
    # API Key 配置
    api_key_prefix: str = Field(default="kb_", description="API Key 前缀")
    api_key_length: int = Field(default=32, description="API Key 长度")
    
    # ==================== 存储配额配置 ====================
    default_user_storage_quota_gb: int = Field(default=10, description="默认用户存储配额（GB）")
    max_knowledge_bases_per_user: int = Field(default=100, description="每个用户最多知识库数量")
    max_documents_per_knowledge_base: int = Field(default=10000, description="每个知识库最多文档数量")
    
    @property
    def default_user_storage_quota_bytes(self) -> int:
        """默认用户存储配额（字节）"""
        return self.default_user_storage_quota_gb * 1024 * 1024 * 1024
    
    # ==================== OCR 配置 ====================
    ocr_enabled: bool = Field(default=True, description="是否启用 OCR")
    ocr_auto_detect_threshold: int = Field(default=50, description="OCR 自动检测阈值（字符数/页）")
    ocr_languages: List[str] = Field(default=["zh", "en"], description="OCR 支持的语言")
    
    # ==================== Webhook 配置 ====================
    webhook_enabled: bool = Field(default=True, description="是否启用 Webhook")
    webhook_timeout: int = Field(default=10, description="Webhook 超时时间（秒）")
    webhook_max_retries: int = Field(default=3, description="Webhook 最大重试次数")
    
    # ==================== 开发模式配置 ====================
    reload: bool = Field(default=False, description="是否启用热重载")
    docs_url: Optional[str] = Field(default="/docs", description="API 文档路径")
    redoc_url: Optional[str] = Field(default="/redoc", description="ReDoc 文档路径")
    openapi_url: Optional[str] = Field(default="/openapi.json", description="OpenAPI Schema 路径")
    
    # 生产环境禁用文档
    @property
    def get_docs_url(self) -> Optional[str]:
        """获取文档URL（生产环境禁用）"""
        return self.docs_url if self.debug else None
    
    @property
    def get_redoc_url(self) -> Optional[str]:
        """获取 ReDoc URL（生产环境禁用）"""
        return self.redoc_url if self.debug else None
    
    @property
    def get_openapi_url(self) -> Optional[str]:
        """获取 OpenAPI URL（生产环境禁用）"""
        return self.openapi_url if self.debug else None


# 创建全局配置实例
settings = Settings()


# 配置验证函数
def validate_settings() -> None:
    """验证配置的有效性"""
    errors = []

    # 验证硅基流动 API Key
    if not settings.siliconflow_api_key:
        errors.append("SILICONFLOW_API_KEY 未设置，Embedding 和 LLM 功能将无法使用")

    # 验证数据库配置
    if not settings.postgres_host:
        errors.append("POSTGRES_HOST 未设置")

    # 验证 Redis 配置
    if not settings.redis_host:
        errors.append("REDIS_HOST 未设置")

    # 验证 MinIO 配置
    if not settings.minio_host:
        errors.append("MINIO_HOST 未设置")

    # 验证向量索引类型
    if settings.vector_index_type not in ["hnsw", "ivfflat"]:
        errors.append(f"VECTOR_INDEX_TYPE 必须是 'hnsw' 或 'ivfflat'，当前值: {settings.vector_index_type}")

    # 验证搜索类型
    if settings.default_search_type not in ["vector", "fulltext", "hybrid"]:
        errors.append(f"DEFAULT_SEARCH_TYPE 必须是 'vector'、'fulltext' 或 'hybrid'，当前值: {settings.default_search_type}")

    # 验证 LLM 提供商
    if settings.default_llm_provider not in ["siliconflow"]:
        errors.append(f"DEFAULT_LLM_PROVIDER 必须是 'siliconflow'，当前值: {settings.default_llm_provider}")

    # 打印警告
    if errors:
        import warnings
        for error in errors:
            warnings.warn(f"配置警告: {error}")


# 启动时验证配置
if __name__ != "__main__":
    validate_settings()

