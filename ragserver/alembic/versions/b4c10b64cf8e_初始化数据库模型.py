"""初始化数据库模型

Revision ID: b4c10b64cf8e
Revises:
Create Date: 2025-10-30 09:57:16.137420

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "b4c10b64cf8e"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # 创建 pgvector 扩展
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # 创建 users 表
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("username", sa.String(50), nullable=False, unique=True, index=True),
        sa.Column("email", sa.String(255), nullable=False, unique=True, index=True),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(100)),
        sa.Column("avatar_url", sa.String(500)),
        sa.Column("settings", postgresql.JSONB, default=dict),
        sa.Column("is_active", sa.Boolean, default=True, nullable=False),
        sa.Column("is_superuser", sa.Boolean, default=False, nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True)),
        sa.Column("storage_used", sa.BigInteger, default=0),
        sa.Column("api_calls_count", sa.Integer, default=0),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    # 创建 collections 表
    op.create_table(
        "collections",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.String(500)),
        sa.Column("icon_url", sa.String(500)),
        sa.Column("status", sa.String(20), default="active", nullable=False),
        sa.Column("document_count", sa.Integer, default=0),
        sa.Column("total_size_bytes", sa.BigInteger, default=0),
        sa.Column("chunk_count", sa.Integer, default=0),
        sa.Column("last_updated_at", sa.DateTime(timezone=True)),
        sa.Column("settings", postgresql.JSONB, default=dict),
        sa.Column("language", sa.String(20), default="zh", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("idx_kb_user", "collections", ["user_id"])
    op.create_index("idx_kb_status", "collections", ["status"])

    # 创建 documents 表
    op.create_table(
        "documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "collection_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("collections.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("uploaded_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("file_type", sa.String(20), nullable=False),
        sa.Column("file_size", sa.BigInteger, nullable=False),
        sa.Column("s3_url", sa.String(500), nullable=False),
        sa.Column("mime_type", sa.String(100), nullable=False),
        sa.Column("file_hash", sa.String(64), nullable=False),
        sa.Column("content_text", sa.Text),
        sa.Column("status", sa.String(20), default="pending", nullable=False),
        sa.Column("progress", sa.Integer, default=0),
        sa.Column("error_message", sa.Text),
        sa.Column("processed_at", sa.DateTime(timezone=True)),
        sa.Column("meta", postgresql.JSONB, default=dict),
        sa.Column("chunking_config", postgresql.JSONB),
        sa.Column("chunk_count", sa.Integer, default=0),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("idx_doc_kb", "documents", ["collection_id"])
    op.create_index("idx_doc_uploader", "documents", ["uploaded_by"])
    op.create_index("idx_doc_status", "documents", ["status"])
    op.create_index("idx_doc_hash", "documents", ["file_hash"])

    # 创建 document_chunks 表
    op.create_table(
        "document_chunks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "document_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "collection_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("collections.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("chunk_index", sa.Integer, nullable=False),
        sa.Column("summary", sa.Text),
        sa.Column("content_embedding", Vector(1024)),
        sa.Column("summary_embedding", Vector(1024)),
        sa.Column("embedding_model", sa.String(50), default="BAAI/bge-m3"),
        sa.Column("meta", postgresql.JSONB, default=dict),
        sa.Column("parent_chunk_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("document_chunks.id")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("idx_chunk_doc", "document_chunks", ["document_id"])
    op.create_index("idx_chunk_kb", "document_chunks", ["collection_id"])
    op.create_index("idx_chunk_user", "document_chunks", ["user_id"])
    op.create_index("idx_chunk_hash", "document_chunks", ["content_hash"])
    op.create_index("idx_chunk_kb_user", "document_chunks", ["collection_id", "user_id"])

    # 创建 HNSW 向量索引
    op.execute("""
        CREATE INDEX idx_chunk_content_embedding_hnsw 
        ON document_chunks 
        USING hnsw (content_embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64)
    """)

    # 创建 api_keys 表
    op.create_table(
        "api_keys",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("collection_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("collections.id")),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.String(500)),
        sa.Column("key_hash", sa.String(64), nullable=False),
        sa.Column("key_prefix", sa.String(10), nullable=False),
        sa.Column("key_suffix", sa.String(10), nullable=False),
        sa.Column("scopes", postgresql.JSONB, default=list),
        sa.Column("rate_limit", sa.Integer, default=60),
        sa.Column("daily_quota", sa.Integer, default=10000),
        sa.Column("monthly_quota", sa.Integer, default=100000),
        sa.Column("usage_count_today", sa.Integer, default=0),
        sa.Column("usage_count_month", sa.Integer, default=0),
        sa.Column("is_active", sa.Boolean, default=True, nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("last_used_at", sa.DateTime(timezone=True)),
        sa.Column("last_used_ip", sa.String(45)),
        sa.Column("security", postgresql.JSONB, default=dict),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("idx_ak_user", "api_keys", ["user_id"])
    op.create_index("idx_ak_kb", "api_keys", ["collection_id"])
    op.create_index("idx_ak_active", "api_keys", ["is_active"])
    op.create_index("idx_ak_hash", "api_keys", ["key_hash"])

    # 创建 api_usage_logs 表
    op.create_table(
        "api_usage_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("api_key_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("api_keys.id"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("endpoint", sa.String(200), nullable=False),
        sa.Column("method", sa.String(10), nullable=False),
        sa.Column("status_code", sa.Integer, nullable=False),
        sa.Column("response_time_ms", sa.Integer, nullable=False),
        sa.Column("error_message", sa.Text),
        sa.Column("request_body", postgresql.JSONB),
        sa.Column("ip_address", sa.String(45), nullable=False),
        sa.Column("user_agent", sa.String(500)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("idx_aul_api_key", "api_usage_logs", ["api_key_id"])
    op.create_index("idx_aul_user", "api_usage_logs", ["user_id"])
    op.create_index("idx_aul_endpoint", "api_usage_logs", ["endpoint"])
    op.create_index("idx_aul_created_at", "api_usage_logs", ["created_at"])
    op.create_index("idx_aul_status", "api_usage_logs", ["status_code"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("api_usage_logs")
    op.drop_table("api_keys")
    op.drop_table("document_chunks")
    op.drop_table("documents")
    op.drop_table("collections")
    op.drop_table("users")
    op.execute("DROP EXTENSION IF EXISTS vector")
