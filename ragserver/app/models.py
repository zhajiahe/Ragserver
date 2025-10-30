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
from sqlalchemy.orm import declarative_base, relationship
import uuid
from ragserver.config import settings
from ragserver.app.utils.date_util import get_current_time

Base = declarative_base()


class TimeMixin:
    """时间戳混入类，为所有模型提供创建和更新时间"""
    created_at = Column(DateTime(timezone=True), default=get_current_time, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=get_current_time, onupdate=get_current_time, nullable=False)


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
    last_login_at = Column(DateTime(timezone=True))

    # 统计信息
    storage_used = Column(BigInteger, default=0)  # bytes
    api_calls_count = Column(Integer, default=0)

    # 关联关系
    collections = relationship("Collection", back_populates="user")
    documents = relationship("Document", back_populates="uploader")
    document_chunks = relationship("DocumentChunk", back_populates="user")
    collection_shares = relationship("CollectionShare", back_populates="creator")

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
    last_updated_at = Column(DateTime(timezone=True), default=get_current_time)

    # 配置信息
    settings = Column(JSONB, default=dict)

    language = Column(String(20), default="zh", nullable=False)

    # 关联关系
    user = relationship("User", back_populates="collections")
    documents = relationship("Document", back_populates="collection", passive_deletes=True)
    chunks = relationship("DocumentChunk", back_populates="collection", passive_deletes=True)
    shares = relationship("CollectionShare", back_populates="collection", passive_deletes=True)

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
    s3_url = Column(String(500), nullable=False)  # MinIO路径
    mime_type = Column(String(100), nullable=False)
    file_hash = Column(String(64), nullable=False)  # SHA256


    content_text = Column(Text) # Markdown格式文本

    # 处理状态
    status = Column(String(20), default="pending", nullable=False)  # pending/processing/completed/failed
    progress = Column(Integer, default=0)  # 0-100
    error_message = Column(Text)

    # 时间信息
    processed_at = Column(DateTime(timezone=True))

    # 元数据
    meta = Column(JSONB, default=dict)

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
    meta = Column(JSONB, default=dict)

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


class CollectionShare(Base, TimeMixin):
    """知识库分享模型"""
    __tablename__ = "collection_shares"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    collection_id = Column(PGUUID(as_uuid=True), ForeignKey("collections.id", ondelete='CASCADE'), nullable=False)
    created_by = Column(PGUUID(as_uuid=True), ForeignKey("users.id"), nullable=False)

    # 分享信息
    share_token = Column(String(64), unique=True, nullable=False, index=True)  # 格式: kb_share_xxx
    name = Column(String(100), nullable=False)
    description = Column(String(500))

    # 状态信息
    is_active = Column(Boolean, default=True, nullable=False)
    expires_at = Column(DateTime(timezone=True))  # 可选过期时间

    # 使用统计
    usage_count = Column(Integer, default=0)
    last_used_at = Column(DateTime(timezone=True))

    # 搜索配置
    search_config = Column(JSONB, default=dict)  # top_k限制、过滤条件等

    # 关联关系
    collection = relationship("Collection", back_populates="shares")
    creator = relationship("User", back_populates="collection_shares")

    __table_args__ = (
        Index('idx_share_token', 'share_token'),
        Index('idx_share_kb', 'collection_id'),
        Index('idx_share_creator', 'created_by'),
        Index('idx_share_active', 'is_active'),
    )

    def __repr__(self):
        return f"<CollectionShare(id={self.id}, token={self.share_token}, collection_id={self.collection_id})>"
