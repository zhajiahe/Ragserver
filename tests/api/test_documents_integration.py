"""
文档管理集成测试

测试文档上传、删除、更新、查询、处理等接口
"""
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import uuid4

from ragserver.app.models import User, Collection, Document, DocumentChunk
from ragserver.app.dependencies.security import create_access_token, get_password_hash
from datetime import timedelta
from io import BytesIO


@pytest.fixture(scope="function")
async def setup_db(db_session: AsyncSession):
    """设置数据库依赖注入覆盖"""
    from ragserver.main import app
    from ragserver.app.dependencies import get_db
    
    async def override_get_db():
        yield db_session
    
    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.clear()


@pytest.fixture(scope="function")
async def authenticated_user_with_kb(async_client: AsyncClient, db_session: AsyncSession, setup_db):
    """创建一个已认证的用户和知识库"""
    user = User(
        username="docuser",
        email="docuser@example.com",
        hashed_password=get_password_hash("DocPass123!"),
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    # 创建知识库
    collection = Collection(
        user_id=user.id,
        name="Test KB",
        description="A test knowledge base",
        language="zh",
        status="active",
    )
    db_session.add(collection)
    await db_session.commit()
    await db_session.refresh(collection)

    access_token = create_access_token(str(user.id), expires_delta=timedelta(minutes=60))
    async_client.headers = {"Authorization": f"Bearer {access_token}"}
    
    return user, collection, async_client


class TestDocumentUpload:
    """文档上传测试"""

    @pytest.mark.asyncio
    async def test_upload_single_document(
        self, authenticated_user_with_kb, db_session: AsyncSession
    ):
        """测试上传单个文档"""
        user, collection, client = authenticated_user_with_kb

        # 模拟文件上传
        files = [
            ("files", ("test.txt", BytesIO(b"Hello World"), "text/plain"))
        ]

        res = await client.post(
            f"/api/v1/collections/{collection.id}/upload",
            files=files,
        )

        assert res.status_code == 201
        result = res.json()
        assert len(result) == 1
        assert result[0]["filename"] == "test.txt"
        assert result[0]["status"] == "pending"
        assert result[0]["collection_id"] == str(collection.id)
        assert result[0]["uploaded_by"] == str(user.id)

        # 验证数据库
        doc = await db_session.execute(
            select(Document).filter_by(id=result[0]["id"])
        )
        assert doc.scalar_one().filename == "test.txt"

    @pytest.mark.asyncio
    async def test_upload_multiple_documents(
        self, authenticated_user_with_kb, db_session: AsyncSession
    ):
        """测试批量上传文档"""
        user, collection, client = authenticated_user_with_kb

        files = [
            ("files", ("doc1.txt", BytesIO(b"Content 1"), "text/plain")),
            ("files", ("doc2.pdf", BytesIO(b"Content 2"), "application/pdf")),
        ]

        res = await client.post(
            f"/api/v1/collections/{collection.id}/upload",
            files=files,
        )

        assert res.status_code == 201
        result = res.json()
        assert len(result) == 2
        assert {doc["filename"] for doc in result} == {"doc1.txt", "doc2.pdf"}

    @pytest.mark.asyncio
    async def test_upload_without_auth(self, async_client: AsyncClient, db_session: AsyncSession, setup_db):
        """测试未认证用户上传文档"""
        fake_kb_id = uuid4()
        files = [
            ("files", ("test.txt", BytesIO(b"Hello"), "text/plain"))
        ]
        
        res = await async_client.post(
            f"/api/v1/collections/{fake_kb_id}/upload",
            files=files,
        )
        
        assert res.status_code == 401

    @pytest.mark.asyncio
    async def test_upload_to_nonexistent_kb(
        self, authenticated_user_with_kb, db_session: AsyncSession
    ):
        """测试上传到不存在的知识库"""
        user, collection, client = authenticated_user_with_kb

        fake_kb_id = uuid4()
        files = [
            ("files", ("test.txt", BytesIO(b"Hello"), "text/plain"))
        ]

        res = await client.post(
            f"/api/v1/collections/{fake_kb_id}/upload",
            files=files,
        )

        assert res.status_code == 404


class TestDocumentList:
    """文档列表测试"""

    @pytest.mark.asyncio
    async def test_get_document_list(
        self, authenticated_user_with_kb, db_session: AsyncSession
    ):
        """测试获取文档列表"""
        user, collection, client = authenticated_user_with_kb

        # 创建几个文档
        for i in range(3):
            doc = Document(
                collection_id=collection.id,
                uploaded_by=user.id,
                filename=f"test{i}.txt",
                file_type="txt",
                file_size=1000,
                s3_url=f"http://minio:9000/documents/path/test{i}.txt",
                mime_type="text/plain",
                file_hash=f"hash{i}",
                status="pending",
            )
            db_session.add(doc)
        await db_session.commit()

        res = await client.get(f"/api/v1/collections/{collection.id}/documents")

        assert res.status_code == 200
        result = res.json()
        assert result["total"] == 3
        assert len(result["items"]) == 3

    @pytest.mark.asyncio
    async def test_get_document_list_with_status_filter(
        self, authenticated_user_with_kb, db_session: AsyncSession
    ):
        """测试按状态过滤文档列表"""
        user, collection, client = authenticated_user_with_kb

        # 创建不同状态的文档
        statuses = ["pending", "processing", "completed"]
        for status in statuses:
            doc = Document(
                collection_id=collection.id,
                uploaded_by=user.id,
                filename=f"test_{status}.txt",
                file_type="txt",
                file_size=1000,
                s3_url=f"http://minio:9000/documents/path/test_{status}.txt",
                mime_type="text/plain",
                file_hash=f"hash_{status}",
                status=status,
            )
            db_session.add(doc)
        await db_session.commit()

        # 过滤 completed
        res = await client.get(
            f"/api/v1/collections/{collection.id}/documents?status_filter=completed"
        )

        assert res.status_code == 200
        result = res.json()
        assert result["total"] == 1
        assert result["items"][0]["status"] == "completed"

    @pytest.mark.asyncio
    async def test_get_document_list_with_pagination(
        self, authenticated_user_with_kb, db_session: AsyncSession
    ):
        """测试分页"""
        user, collection, client = authenticated_user_with_kb

        # 创建10个文档
        for i in range(10):
            doc = Document(
                collection_id=collection.id,
                uploaded_by=user.id,
                filename=f"test{i}.txt",
                file_type="txt",
                file_size=1000,
                s3_url=f"http://minio:9000/documents/path/test{i}.txt",
                mime_type="text/plain",
                file_hash=f"hash{i}",
                status="pending",
            )
            db_session.add(doc)
        await db_session.commit()

        # 第一页
        res = await client.get(
            f"/api/v1/collections/{collection.id}/documents?limit=5&offset=0"
        )
        assert res.status_code == 200
        result = res.json()
        assert result["total"] == 10
        assert len(result["items"]) == 5

        # 第二页
        res = await client.get(
            f"/api/v1/collections/{collection.id}/documents?limit=5&offset=5"
        )
        assert res.status_code == 200
        result = res.json()
        assert result["total"] == 10
        assert len(result["items"]) == 5


class TestDocumentDetail:
    """文档详情测试"""

    @pytest.mark.asyncio
    async def test_get_document_detail(
        self, authenticated_user_with_kb, db_session: AsyncSession
    ):
        """测试获取文档详情"""
        user, collection, client = authenticated_user_with_kb

        doc = Document(
            collection_id=collection.id,
            uploaded_by=user.id,
            filename="detail_test.txt",
            file_type="txt",
            file_size=2048,
            s3_url="http://minio:9000/documents/path/detail_test.txt",
            mime_type="text/plain",
            file_hash="detailhash",
            status="completed",
            chunk_count=5,
        )
        db_session.add(doc)
        await db_session.commit()
        await db_session.refresh(doc)

        res = await client.get(f"/api/v1/documents/{doc.id}")

        assert res.status_code == 200
        result = res.json()
        assert result["filename"] == "detail_test.txt"
        assert result["status"] == "completed"
        assert result["chunk_count"] == 5

    @pytest.mark.asyncio
    async def test_get_document_detail_not_found(
        self, authenticated_user_with_kb, db_session: AsyncSession
    ):
        """测试获取不存在的文档"""
        user, collection, client = authenticated_user_with_kb

        fake_id = uuid4()
        res = await client.get(f"/api/v1/documents/{fake_id}")

        assert res.status_code == 404


class TestDocumentUpdate:
    """文档更新测试"""

    @pytest.mark.asyncio
    async def test_update_document_config(
        self, authenticated_user_with_kb, db_session: AsyncSession
    ):
        """测试更新文档配置"""
        user, collection, client = authenticated_user_with_kb

        doc = Document(
            collection_id=collection.id,
            uploaded_by=user.id,
            filename="update_test.txt",
            file_type="txt",
            file_size=1000,
            s3_url="http://minio:9000/documents/path/update_test.txt",
            mime_type="text/plain",
            file_hash="updatehash",
            status="pending",
        )
        db_session.add(doc)
        await db_session.commit()
        await db_session.refresh(doc)

        update_data = {
            "chunking_config": {"max_chunk_size": 500},
            "meta": {"language": "en"},
        }

        res = await client.put(f"/api/v1/documents/{doc.id}", json=update_data)

        assert res.status_code == 200
        result = res.json()
        assert result["chunking_config"] == {"max_chunk_size": 500}
        assert result["meta"]["language"] == "en"


class TestDocumentDelete:
    """文档删除测试"""

    @pytest.mark.asyncio
    async def test_delete_documents(
        self, authenticated_user_with_kb, db_session: AsyncSession
    ):
        """测试批量删除文档"""
        user, collection, client = authenticated_user_with_kb

        # 创建2个文档
        docs = []
        for i in range(2):
            doc = Document(
                collection_id=collection.id,
                uploaded_by=user.id,
                filename=f"delete{i}.txt",
                file_type="txt",
                file_size=1000,
                s3_url=f"http://minio:9000/documents/path/delete{i}.txt",
                mime_type="text/plain",
                file_hash=f"deletehash{i}",
                status="pending",
            )
            db_session.add(doc)
            docs.append(doc)
        await db_session.commit()
        for doc in docs:
            await db_session.refresh(doc)

        doc_ids = [str(doc.id) for doc in docs]

        res = await client.request(
            "DELETE",
            "/api/v1/documents",
            json={"document_ids": doc_ids}
        )

        assert res.status_code == 204

        # 验证已删除
        for doc_id in doc_ids:
            result = await db_session.execute(
                select(Document).filter_by(id=doc_id)
            )
            assert result.scalar_one_or_none() is None

    @pytest.mark.asyncio
    async def test_delete_empty_list(
        self, authenticated_user_with_kb, db_session: AsyncSession
    ):
        """测试删除空列表"""
        user, collection, client = authenticated_user_with_kb

        res = await client.request(
            "DELETE",
            "/api/v1/documents",
            json={"document_ids": []}
        )

        assert res.status_code == 400


class TestDocumentProcess:
    """文档处理测试 (Mock)"""

    @pytest.mark.asyncio
    async def test_process_documents(
        self, authenticated_user_with_kb, db_session: AsyncSession
    ):
        """测试批量处理文档 (Mock)"""
        user, collection, client = authenticated_user_with_kb

        # 创建文档
        doc = Document(
            collection_id=collection.id,
            uploaded_by=user.id,
            filename="process.txt",
            file_type="txt",
            file_size=1000,
            s3_url="http://minio:9000/documents/path/process.txt",
            mime_type="text/plain",
            file_hash="processhash",
            status="pending",
        )
        db_session.add(doc)
        await db_session.commit()
        await db_session.refresh(doc)

        res = await client.post(
            "/api/v1/documents/process",
            json={"document_ids": [str(doc.id)]}
        )

        assert res.status_code == 202
        result = res.json()
        assert "已提交" in result["message"]
        assert len(result["document_ids"]) == 1

        # 验证状态已更新
        await db_session.refresh(doc)
        assert doc.status == "processing"

    @pytest.mark.asyncio
    async def test_reprocess_documents(
        self, authenticated_user_with_kb, db_session: AsyncSession
    ):
        """测试重新处理文档 (Mock)"""
        user, collection, client = authenticated_user_with_kb

        # 创建已完成的文档
        doc = Document(
            collection_id=collection.id,
            uploaded_by=user.id,
            filename="reprocess.txt",
            file_type="txt",
            file_size=1000,
            s3_url="http://minio:9000/documents/path/reprocess.txt",
            mime_type="text/plain",
            file_hash="reprocesshash",
            status="completed",
            chunk_count=3,
        )
        db_session.add(doc)
        await db_session.commit()
        await db_session.refresh(doc)

        res = await client.post(
            "/api/v1/documents/reprocess",
            json={"document_ids": [str(doc.id)]}
        )

        assert res.status_code == 202
        result = res.json()
        assert "重新处理" in result["message"]

        # 验证状态已重置
        await db_session.refresh(doc)
        assert doc.status == "processing"
        assert doc.chunk_count == 0


class TestDocumentStatus:
    """文档状态查询测试"""

    @pytest.mark.asyncio
    async def test_get_document_status(
        self, authenticated_user_with_kb, db_session: AsyncSession
    ):
        """测试查询文档状态"""
        user, collection, client = authenticated_user_with_kb

        doc = Document(
            collection_id=collection.id,
            uploaded_by=user.id,
            filename="status.txt",
            file_type="txt",
            file_size=1000,
            s3_url="http://minio:9000/documents/path/status.txt",
            mime_type="text/plain",
            file_hash="statushash",
            status="processing",
            progress=50,
            chunk_count=2,
        )
        db_session.add(doc)
        await db_session.commit()
        await db_session.refresh(doc)

        res = await client.get(f"/api/v1/documents/{doc.id}/status")

        assert res.status_code == 200
        result = res.json()
        assert result["status"] == "processing"
        assert result["progress"] == 50
        assert result["chunk_count"] == 2


class TestDocumentChunks:
    """文档分块测试"""

    @pytest.mark.asyncio
    async def test_get_document_chunks(
        self, authenticated_user_with_kb, db_session: AsyncSession
    ):
        """测试获取文档分块列表"""
        user, collection, client = authenticated_user_with_kb

        # 创建文档
        doc = Document(
            collection_id=collection.id,
            uploaded_by=user.id,
            filename="chunks.txt",
            file_type="txt",
            file_size=1000,
            s3_url="http://minio:9000/documents/path/chunks.txt",
            mime_type="text/plain",
            file_hash="chunkshash",
            status="completed",
        )
        db_session.add(doc)
        await db_session.commit()
        await db_session.refresh(doc)

        # 创建分块
        for i in range(3):
            chunk = DocumentChunk(
                document_id=doc.id,
                collection_id=collection.id,
                user_id=user.id,
                content=f"Chunk {i} content",
                content_hash=f"chunkhash{i}",
                chunk_index=i,
            )
            db_session.add(chunk)
        await db_session.commit()

        res = await client.get(f"/api/v1/documents-chunks/{doc.id}")

        assert res.status_code == 200
        result = res.json()
        assert len(result) == 3
        assert result[0]["chunk_index"] == 0
        assert result[1]["chunk_index"] == 1
        assert result[2]["chunk_index"] == 2

    @pytest.mark.asyncio
    async def test_get_document_chunks_pagination(
        self, authenticated_user_with_kb, db_session: AsyncSession
    ):
        """测试文档分块分页"""
        user, collection, client = authenticated_user_with_kb

        # 创建文档
        doc = Document(
            collection_id=collection.id,
            uploaded_by=user.id,
            filename="chunks_page.txt",
            file_type="txt",
            file_size=1000,
            s3_url="http://minio:9000/documents/path/chunks_page.txt",
            mime_type="text/plain",
            file_hash="chunkshashpage",
            status="completed",
        )
        db_session.add(doc)
        await db_session.commit()
        await db_session.refresh(doc)

        # 创建10个分块
        for i in range(10):
            chunk = DocumentChunk(
                document_id=doc.id,
                collection_id=collection.id,
                user_id=user.id,
                content=f"Chunk {i}",
                content_hash=f"chunkhash{i}",
                chunk_index=i,
            )
            db_session.add(chunk)
        await db_session.commit()

        # 获取前5个
        res = await client.get(f"/api/v1/documents-chunks/{doc.id}?limit=5&offset=0")
        assert res.status_code == 200
        result = res.json()
        assert len(result) == 5


class TestDocumentPermissions:
    """文档权限测试"""

    @pytest.mark.asyncio
    async def test_cannot_access_other_user_document(
        self, authenticated_user_with_kb, async_client: AsyncClient, db_session: AsyncSession
    ):
        """测试用户无法访问其他用户的文档"""
        user1, collection1, client1 = authenticated_user_with_kb

        # 创建第二个用户和文档
        user2 = User(
            username="docuser2",
            email="docuser2@example.com",
            hashed_password=get_password_hash("Pass123!"),
            is_active=True,
        )
        db_session.add(user2)
        await db_session.commit()
        await db_session.refresh(user2)

        collection2 = Collection(
            user_id=user2.id,
            name="User2 KB",
            language="zh",
            status="active",
        )
        db_session.add(collection2)
        await db_session.commit()
        await db_session.refresh(collection2)

        doc2 = Document(
            collection_id=collection2.id,
            uploaded_by=user2.id,
            filename="user2doc.txt",
            file_type="txt",
            file_size=1000,
            s3_url="http://minio:9000/documents/path/user2doc.txt",
            mime_type="text/plain",
            file_hash="user2hash",
            status="pending",
        )
        db_session.add(doc2)
        await db_session.commit()
        await db_session.refresh(doc2)

        # user1 尝试访问 user2 的文档
        res = await client1.get(f"/api/v1/documents/{doc2.id}")
        assert res.status_code == 404

