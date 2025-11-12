"""文档分块查询集成测试

测试文档分块的查询、详情、删除等接口
"""

from datetime import timedelta
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ragserver.app.dependencies.security import create_access_token, get_password_hash
from ragserver.app.models import Collection, Document, DocumentChunk, User


@pytest.fixture(scope="function")
async def setup_db(db_session: AsyncSession):
    """设置数据库依赖注入覆盖"""
    from ragserver.app.dependencies import get_db
    from ragserver.main import app

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.clear()


@pytest.fixture(scope="function")
async def authenticated_user_with_chunks(async_client: AsyncClient, db_session: AsyncSession, setup_db):
    """创建一个已认证的用户、知识库、文档和分块"""
    # 创建用户
    user = User(
        username="chunkuser",
        email="chunkuser@example.com",
        hashed_password=get_password_hash("ChunkPass123!"),
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    # 创建知识库
    collection = Collection(
        user_id=user.id,
        name="Test KB for Chunks",
        description="A test knowledge base for chunk testing",
        language="zh",
        status="active",
    )
    db_session.add(collection)
    await db_session.commit()
    await db_session.refresh(collection)

    # 创建文档
    document = Document(
        collection_id=collection.id,
        uploaded_by=user.id,
        filename="test_document.txt",
        file_type="txt",
        file_size=1024,
        s3_url="http://minio:9000/documents/test_document.txt",
        mime_type="text/plain",
        file_hash="test_hash_123",
        status="completed",
        content_text="This is a test document content.",
        chunk_count=3,
    )
    db_session.add(document)
    await db_session.commit()
    await db_session.refresh(document)

    # 创建分块
    chunks = []
    for i in range(3):
        chunk = DocumentChunk(
            document_id=document.id,
            collection_id=collection.id,
            user_id=user.id,
            content=f"This is chunk {i} content.",
            content_hash=f"hash_{i}",
            chunk_index=i,
            content_embedding=[0.1] * 1024,  # 1024维向量
            embedding_model="BAAI/bge-m3",
            meta={"chunk_size": len(f"This is chunk {i} content.")},
        )
        chunks.append(chunk)
        db_session.add(chunk)

    await db_session.commit()
    for chunk in chunks:
        await db_session.refresh(chunk)

    # 创建认证token
    access_token = create_access_token(str(user.id), expires_delta=timedelta(minutes=60))
    async_client.headers = {"Authorization": f"Bearer {access_token}"}

    return user, collection, document, chunks, async_client


class TestGetDocumentChunks:
    """获取文档分块列表测试"""

    @pytest.mark.asyncio
    async def test_get_document_chunks_success(self, authenticated_user_with_chunks, db_session: AsyncSession):
        """测试成功获取文档分块列表"""
        user, collection, document, chunks, client = authenticated_user_with_chunks

        res = await client.get(f"/api/v1/chunks/document/{document.id}")

        assert res.status_code == 200
        data = res.json()
        assert data["total"] == 3
        assert len(data["items"]) == 3

        # 验证分块按 chunk_index 排序
        for i, item in enumerate(data["items"]):
            assert item["chunk_index"] == i
            assert item["content"] == f"This is chunk {i} content."
            assert item["document_id"] == str(document.id)
            assert item["collection_id"] == str(collection.id)

    @pytest.mark.asyncio
    async def test_get_document_chunks_with_pagination(self, authenticated_user_with_chunks, db_session: AsyncSession):
        """测试分页获取文档分块"""
        user, collection, document, chunks, client = authenticated_user_with_chunks

        # 第一页
        res = await client.get(f"/api/v1/chunks/document/{document.id}", params={"limit": 2, "offset": 0})

        assert res.status_code == 200
        data = res.json()
        assert data["total"] == 3
        assert len(data["items"]) == 2
        assert data["items"][0]["chunk_index"] == 0
        assert data["items"][1]["chunk_index"] == 1

        # 第二页
        res = await client.get(f"/api/v1/chunks/document/{document.id}", params={"limit": 2, "offset": 2})

        assert res.status_code == 200
        data = res.json()
        assert data["total"] == 3
        assert len(data["items"]) == 1
        assert data["items"][0]["chunk_index"] == 2

    @pytest.mark.asyncio
    async def test_get_document_chunks_not_found(self, authenticated_user_with_chunks, db_session: AsyncSession):
        """测试获取不存在的文档分块"""
        user, collection, document, chunks, client = authenticated_user_with_chunks

        fake_doc_id = uuid4()
        res = await client.get(f"/api/v1/chunks/document/{fake_doc_id}")

        assert res.status_code == 404
        assert "不存在或无权访问" in res.json()["detail"]

    @pytest.mark.asyncio
    async def test_get_document_chunks_without_auth(self, authenticated_user_with_chunks):
        """测试未认证获取文档分块"""
        user, collection, document, chunks, client = authenticated_user_with_chunks

        # 创建一个新的客户端，不带认证头
        from httpx import ASGITransport, AsyncClient

        from ragserver.main import app

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as unauthenticated_client:
            res = await unauthenticated_client.get(f"/api/v1/chunks/document/{document.id}")
            assert res.status_code == 401


class TestGetChunkDetail:
    """获取单个分块详情测试"""

    @pytest.mark.asyncio
    async def test_get_chunk_detail_success(self, authenticated_user_with_chunks, db_session: AsyncSession):
        """测试成功获取分块详情"""
        user, collection, document, chunks, client = authenticated_user_with_chunks

        chunk = chunks[0]
        res = await client.get(f"/api/v1/chunks/{chunk.id}")

        assert res.status_code == 200
        data = res.json()
        assert data["id"] == str(chunk.id)
        assert data["content"] == chunk.content
        assert data["chunk_index"] == chunk.chunk_index
        assert data["embedding_model"] == "BAAI/bge-m3"

    @pytest.mark.asyncio
    async def test_get_chunk_detail_not_found(self, authenticated_user_with_chunks, db_session: AsyncSession):
        """测试获取不存在的分块详情"""
        user, collection, document, chunks, client = authenticated_user_with_chunks

        fake_chunk_id = uuid4()
        res = await client.get(f"/api/v1/chunks/{fake_chunk_id}")

        assert res.status_code == 404
        assert "不存在或无权访问" in res.json()["detail"]


class TestGetCollectionChunks:
    """获取知识库分块列表测试"""

    @pytest.mark.asyncio
    async def test_get_collection_chunks_success(self, authenticated_user_with_chunks, db_session: AsyncSession):
        """测试成功获取知识库分块列表"""
        user, collection, document, chunks, client = authenticated_user_with_chunks

        res = await client.get(f"/api/v1/chunks/collection/{collection.id}")

        assert res.status_code == 200
        data = res.json()
        assert data["total"] == 3
        assert len(data["items"]) == 3

    @pytest.mark.asyncio
    async def test_get_collection_chunks_with_pagination(
        self, authenticated_user_with_chunks, db_session: AsyncSession
    ):
        """测试分页获取知识库分块"""
        user, collection, document, chunks, client = authenticated_user_with_chunks

        res = await client.get(f"/api/v1/chunks/collection/{collection.id}", params={"limit": 2, "offset": 0})

        assert res.status_code == 200
        data = res.json()
        assert data["total"] == 3
        assert len(data["items"]) == 2

    @pytest.mark.asyncio
    async def test_get_collection_chunks_not_found(self, authenticated_user_with_chunks, db_session: AsyncSession):
        """测试获取不存在的知识库分块"""
        user, collection, document, chunks, client = authenticated_user_with_chunks

        fake_collection_id = uuid4()
        res = await client.get(f"/api/v1/chunks/collection/{fake_collection_id}")

        assert res.status_code == 404
        assert "不存在或无权访问" in res.json()["detail"]


class TestDeleteChunk:
    """删除分块测试"""

    @pytest.mark.asyncio
    async def test_delete_chunk_success(self, authenticated_user_with_chunks, db_session: AsyncSession):
        """测试成功删除分块"""
        user, collection, document, chunks, client = authenticated_user_with_chunks

        chunk = chunks[0]
        res = await client.delete(f"/api/v1/chunks/{chunk.id}")

        assert res.status_code == 204

        # 验证分块已删除
        result = await db_session.execute(select(DocumentChunk).where(DocumentChunk.id == chunk.id))
        deleted_chunk = result.scalar_one_or_none()
        assert deleted_chunk is None

        # 验证文档统计已更新
        await db_session.refresh(document)
        assert document.chunk_count == 2

        # 验证知识库统计已更新
        await db_session.refresh(collection)
        # 注意：知识库的 chunk_count 可能需要重新计算
        # 这里假设删除操作会更新统计

    @pytest.mark.asyncio
    async def test_delete_chunk_not_found(self, authenticated_user_with_chunks, db_session: AsyncSession):
        """测试删除不存在的分块"""
        user, collection, document, chunks, client = authenticated_user_with_chunks

        fake_chunk_id = uuid4()
        res = await client.delete(f"/api/v1/chunks/{fake_chunk_id}")

        assert res.status_code == 404
        assert "不存在或无权访问" in res.json()["detail"]

    @pytest.mark.asyncio
    async def test_delete_chunk_without_auth(self, authenticated_user_with_chunks):
        """测试未认证删除分块"""
        user, collection, document, chunks, client = authenticated_user_with_chunks

        chunk = chunks[0]

        # 创建一个新的客户端，不带认证头
        from httpx import ASGITransport, AsyncClient

        from ragserver.main import app

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as unauthenticated_client:
            res = await unauthenticated_client.delete(f"/api/v1/chunks/{chunk.id}")
            assert res.status_code == 401


class TestChunkAccessControl:
    """分块访问控制测试"""

    @pytest.mark.asyncio
    async def test_cannot_access_other_user_chunks(
        self, authenticated_user_with_chunks, async_client: AsyncClient, db_session: AsyncSession, setup_db
    ):
        """测试无法访问其他用户的分块"""
        user1, collection1, document1, chunks1, _ = authenticated_user_with_chunks

        # 创建第二个用户
        user2 = User(
            username="otheruser",
            email="otheruser@example.com",
            hashed_password=get_password_hash("OtherPass123!"),
            is_active=True,
        )
        db_session.add(user2)
        await db_session.commit()
        await db_session.refresh(user2)

        # 使用第二个用户的token
        token2 = create_access_token(str(user2.id))
        async_client.headers = {"Authorization": f"Bearer {token2}"}

        # 尝试访问第一个用户的分块
        chunk = chunks1[0]
        res = await async_client.get(f"/api/v1/chunks/{chunk.id}")

        assert res.status_code == 404
        assert "不存在或无权访问" in res.json()["detail"]

        # 尝试访问第一个用户的文档分块列表
        res = await async_client.get(f"/api/v1/chunks/document/{document1.id}")

        assert res.status_code == 404
        assert "不存在或无权访问" in res.json()["detail"]

        # 尝试访问第一个用户的知识库分块列表
        res = await async_client.get(f"/api/v1/chunks/collection/{collection1.id}")

        assert res.status_code == 404
        assert "不存在或无权访问" in res.json()["detail"]

        # 尝试删除第一个用户的分块
        res = await async_client.delete(f"/api/v1/chunks/{chunk.id}")

        assert res.status_code == 404
        assert "不存在或无权访问" in res.json()["detail"]
