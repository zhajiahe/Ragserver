"""
AI知识库管理平台数据模型

SQLAlchemy模型，包含用户管理、知识库管理、文档处理等核心实体。
"""

from datetime import datetime
from sqlalchemy import (
    Column, String, Text, Integer, Boolean, DateTime, BigInteger, text, event,
    Index, ForeignKey, UUID as PGUUID
)
from sqlalchemy.dialects.postgresql import JSONB
from pgvector.sqlalchemy import Vector
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
import uuid
from ragserver.config import settings

Base = declarative_base()


class TimeMixin:
    """时间戳混入类，为所有模型提供创建和更新时间"""
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class User(Base, TimeMixin):
    """用户模型"""
    __tablename__ = "users"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(100))
    avatar_url = Column(String(500))

    # 配置信息
    settings = Column(JSONB, default=dict)

    # 状态信息
    is_active = Column(Boolean, default=True, nullable=False)
    is_superuser = Column(Boolean, default=False, nullable=False)

    # 时间信息
    last_login_at = Column(DateTime)

    # 统计信息
    storage_used = Column(BigInteger, default=0)  # bytes
    api_calls_count = Column(Integer, default=0)

    # 关联关系
    collections = relationship("Collection", back_populates="user")
    documents = relationship("Document", back_populates="uploader")
    api_keys = relationship("APIKey", back_populates="user")
    document_chunks = relationship("DocumentChunk", back_populates="user")
    api_usage_logs = relationship("APIUsageLog", back_populates="user")

    def __repr__(self):
        return f"<User(id={self.id}, username={self.username}, email={self.email})>"


class Collection(Base, TimeMixin):
    """知识库模型"""
    __tablename__ = "collections"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(PGUUID(as_uuid=True), ForeignKey("users.id"), nullable=False)

    # 基本信息
    name = Column(String(100), nullable=False)
    description = Column(String(500))
    icon_url = Column(String(500))

    # 状态信息
    status = Column(String(20), default="active", nullable=False)  # active/archived

    # 统计信息
    document_count = Column(Integer, default=0)
    total_size_bytes = Column(BigInteger, default=0)
    chunk_count = Column(Integer, default=0)
    last_updated_at = Column(DateTime, default=datetime.utcnow)

    # 配置信息
    settings = Column(JSONB, default=dict)

    language = Column(String(20), default="zh", nullable=False)

    # 关联关系
    user = relationship("User", back_populates="collections")
    documents = relationship("Document", back_populates="collection", passive_deletes=True)
    chunks = relationship("DocumentChunk", back_populates="collection", passive_deletes=True)

    __table_args__ = (
        Index('idx_kb_user', 'user_id'),
        Index('idx_kb_status', 'status'),
    )

    def __repr__(self):
        return f"<Collection(id={self.id}, name={self.name}, user_id={self.user_id})>"


class Document(Base, TimeMixin):
    """文档模型"""
    __tablename__ = "documents"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    collection_id = Column(PGUUID(as_uuid=True), ForeignKey("collections.id", ondelete='CASCADE'), nullable=False)
    uploaded_by = Column(PGUUID(as_uuid=True), ForeignKey("users.id"), nullable=False)

    # 文件信息
    filename = Column(String(255), nullable=False)
    file_type = Column(String(20), nullable=False)  # pdf, docx, txt, html, xlsx, etc.
    file_size = Column(BigInteger, nullable=False)  # bytes
    file_path = Column(String(500), nullable=False)  # MinIO路径
    mime_type = Column(String(100), nullable=False)
    file_hash = Column(String(64), nullable=False)  # SHA256

    # 语言（用于 OCR、分词、分块等策略）
    language = Column(String(20), default="zh", nullable=False)

    content_text = Column(Text) # Markdown格式文本

    # 处理状态
    status = Column(String(20), default="pending", nullable=False)  # pending/processing/completed/failed
    progress = Column(Integer, default=0)  # 0-100
    error_message = Column(Text)

    # 时间信息
    processed_at = Column(DateTime)

    # 元数据
    metadata = Column(JSONB, default=dict)

    # 分块配置（可选，默认使用知识库配置）
    chunking_config = Column(JSONB)
    chunk_count = Column(Integer, default=0)

    # 关联关系
    collection = relationship("Collection", back_populates="documents")
    uploader = relationship("User", back_populates="documents")
    chunks = relationship("DocumentChunk", back_populates="document", passive_deletes=True)

    __table_args__ = (
        Index('idx_doc_kb', 'collection_id'),
        Index('idx_doc_uploader', 'uploaded_by'),
        Index('idx_doc_status', 'status'),
        Index('idx_doc_hash', 'file_hash'),
    )

    def __repr__(self):
        return f"<Document(id={self.id}, filename={self.filename}, status={self.status})>"


class DocumentChunk(Base, TimeMixin):
    """文档分块模型"""
    __tablename__ = "document_chunks"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(PGUUID(as_uuid=True), ForeignKey("documents.id", ondelete='CASCADE'), nullable=False)
    collection_id = Column(PGUUID(as_uuid=True), ForeignKey("collections.id", ondelete='CASCADE'), nullable=False)
    user_id = Column(PGUUID(as_uuid=True), ForeignKey("users.id"), nullable=False)

    # 分块内容
    content = Column(Text, nullable=False)
    content_hash = Column(String(64), nullable=False)  # SHA256 for deduplication
    chunk_index = Column(Integer, nullable=False)  # 0-based index in document
    summary = Column(Text) # 块的摘要
    # 向量数据（需 PostgreSQL + pgvector 扩展）
    content_embedding = Column(Vector(settings.embedding_dimension))  # bge-m3: 默认 1024 维（可配置）
    summary_embedding = Column(Vector(settings.embedding_dimension))
    embedding_model = Column(String(50), default="BAAI/bge-m3")

    # 元数据
    metadata = Column(JSONB, default=dict)

    # 关联信息
    parent_chunk_id = Column(PGUUID(as_uuid=True), ForeignKey("document_chunks.id"))  # for hierarchical chunking

    # 关联关系
    document = relationship("Document", back_populates="chunks")
    collection = relationship("Collection", back_populates="chunks")
    parent_chunk = relationship("DocumentChunk", remote_side=[id])
    user = relationship("User", back_populates="document_chunks")

    __table_args__ = (
        Index('idx_chunk_doc', 'document_id'),
        Index('idx_chunk_kb', 'collection_id'),
        Index('idx_chunk_user', 'user_id'),
        Index('idx_chunk_hash', 'content_hash'),
        Index(
            'idx_chunk_content_embedding_hnsw',
            content_embedding,
            postgresql_using='hnsw',
            postgresql_ops={'content_embedding': 'vector_cosine_ops'},
            postgresql_with={'m': settings.hnsw_m, 'ef_construction': settings.hnsw_ef_construction},
        ),
        Index('idx_chunk_kb_user', 'collection_id', 'user_id'),
    )

    def __repr__(self):
        return f"<DocumentChunk(id={self.id}, document_id={self.document_id}, index={self.chunk_index})>"

# 创建 BM25 索引
@event.listens_for(DocumentChunk.__table__, 'after_create')
def create_bm25_index(target, connection, **kw):
    connection.execute(text("""
        CALL paradedb.create_bm25(
            index_name => 'document_chunks_bm25_idx',
            table_name => 'document_chunks',
            key_field => 'id',
            text_fields => paradedb.field('content'))
        )
    """))
    connection.commit()

class APIKey(Base, TimeMixin):
    """API密钥模型"""
    __tablename__ = "api_keys"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(PGUUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    collection_id = Column(PGUUID(as_uuid=True), ForeignKey("collections.id"))  # optional, for KB-specific keys

    # 基本信息
    name = Column(String(100), nullable=False)
    description = Column(String(500))

    # 密钥信息（不存储明文）
    key_hash = Column(String(64), nullable=False)  # SHA256 hash of the full key
    key_prefix = Column(String(10), nullable=False)  # for display, e.g., "kb_1a2b..."
    key_suffix = Column(String(10), nullable=False)  # for display, last 4 chars

    # 权限配置
    scopes = Column(JSONB, default=list)  # ["search", "upload", "read", "delete"]

    # 配额限制
    rate_limit = Column(Integer, default=60)  # requests per minute
    daily_quota = Column(Integer, default=10000)  # requests per day
    monthly_quota = Column(Integer, default=100000)  # requests per month
    usage_count_today = Column(Integer, default=0)
    usage_count_month = Column(Integer, default=0)

    # 状态信息
    is_active = Column(Boolean, default=True, nullable=False)
    expires_at = Column(DateTime)  # optional expiration
    last_used_at = Column(DateTime)
    last_used_ip = Column(String(45))  # IPv4 or IPv6

    # 安全配置
    security = Column(JSONB, default=dict)

    # 关联关系
    user = relationship("User", back_populates="api_keys")
    collection = relationship("Collection")
    usage_logs = relationship("APIUsageLog", back_populates="api_key")

    __table_args__ = (
        Index('idx_ak_user', 'user_id'),
        Index('idx_ak_kb', 'collection_id'),
        Index('idx_ak_active', 'is_active'),
        Index('idx_ak_hash', 'key_hash'),
    )

    def __repr__(self):
        return f"<APIKey(id={self.id}, name={self.name}, user_id={self.user_id})>"


class APIUsageLog(Base):
    """API使用日志模型"""
    __tablename__ = "api_usage_logs"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    api_key_id = Column(PGUUID(as_uuid=True), ForeignKey("api_keys.id"), nullable=False)
    user_id = Column(PGUUID(as_uuid=True), ForeignKey("users.id"), nullable=False)

    # 请求信息
    endpoint = Column(String(200), nullable=False)
    method = Column(String(10), nullable=False)  # GET, POST, etc.

    # 响应信息
    status_code = Column(Integer, nullable=False)
    response_time_ms = Column(Integer, nullable=False)
    error_message = Column(Text)

    # 请求上下文
    request_body = Column(JSONB)  # optional, for debugging
    ip_address = Column(String(45), nullable=False)
    user_agent = Column(String(500))

    # 时间信息
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # 关联关系
    api_key = relationship("APIKey", back_populates="usage_logs")
    user = relationship("User", back_populates="api_usage_logs")

    __table_args__ = (
        Index('idx_aul_api_key', 'api_key_id'),
        Index('idx_aul_user', 'user_id'),
        Index('idx_aul_endpoint', 'endpoint'),
        Index('idx_aul_created_at', 'created_at'),
        Index('idx_aul_status', 'status_code'),
    )

    def __repr__(self):
        return f"<APIUsageLog(id={self.id}, endpoint={self.endpoint}, status={self.status_code})>"
