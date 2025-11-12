"""
文档解析 API 集成测试
"""
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from ragserver.main import app
from ragserver.app.dependencies import get_db
from ragserver.app.models import User, Collection, Document
from ragserver.app.dependencies.security import get_password_hash


@pytest.fixture
async def setup_db(db_session: AsyncSession):
    """设置数据库依赖注入"""
    async def override_get_db():
        yield db_session
    
    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.clear()


@pytest.fixture
async def test_user(db_session: AsyncSession, setup_db):
    """创建测试用户"""
    user = User(
        username="testuser",
        email="test@example.com",
        hashed_password=get_password_hash("Test1234!"),
        full_name="Test User",
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def test_collection(db_session: AsyncSession, test_user: User):
    """创建测试知识库"""
    collection = Collection(
        user_id=test_user.id,
        name="Test Collection",
        description="Test description",
        status="active",
    )
    db_session.add(collection)
    await db_session.commit()
    await db_session.refresh(collection)
    return collection


@pytest.fixture
async def test_documents(db_session: AsyncSession, test_collection: Collection, test_user: User) -> List[Document]:
    """创建测试文档"""
    from ragserver.app.utils.minio_client import minio_client
    from ragserver.config import settings
    from io import BytesIO
    
    documents = []
    for i in range(3):
        # 创建测试文件内容并上传到 MinIO
        test_content = f"This is test document {i} content.\n" * 10
        file_obj = BytesIO(test_content.encode('utf-8'))
        
        # 上传文件到 MinIO
        minio_info = await minio_client.upload_file(
            bucket_name=settings.minio_bucket_documents,
            file=file_obj,
            file_name=f"test{i}.txt",
        )
        
        # 创建文档记录
        doc = Document(
            collection_id=test_collection.id,
            uploaded_by=test_user.id,
            filename=minio_info['filename'],
            file_type=minio_info['file_type'],
            file_size=minio_info['file_size'],
            s3_url=minio_info['s3_url'],
            mime_type=minio_info['mime_type'],
            file_hash=minio_info['file_hash'],
            status="pending",
        )
        db_session.add(doc)
        documents.append(doc)
    
    await db_session.commit()
    for doc in documents:
        await db_session.refresh(doc)
    return documents


@pytest.fixture
async def auth_headers(async_client: AsyncClient, test_user: User):
    """获取认证头"""
    login_payload = {
        "username_or_email": "testuser",
        "password": "Test1234!",
    }
    res = await async_client.post("/api/v1/auth/login", json=login_payload)
    assert res.status_code == 200
    token = res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


class TestDocumentProcessing:
    """文档处理测试"""

    @pytest.mark.asyncio
    async def test_process_documents_success(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        test_documents: List[Document]
    ):
        """测试成功处理文档"""
        payload = {
            "document_ids": [str(doc.id) for doc in test_documents]
        }
        
        res = await async_client.post(
            "/api/v1/documents/process",
            json=payload,
            headers=auth_headers
        )
        
        assert res.status_code == 202
        data = res.json()
        assert data["message"].startswith("已提交")
        assert len(data["document_ids"]) == len(test_documents)

    @pytest.mark.asyncio
    async def test_process_documents_empty_list(
        self,
        async_client: AsyncClient,
        auth_headers: dict
    ):
        """测试空文档列表"""
        payload = {
            "document_ids": []
        }
        
        res = await async_client.post(
            "/api/v1/documents/process",
            json=payload,
            headers=auth_headers
        )
        
        assert res.status_code == 400
        assert "不能为空" in res.json()["detail"]

    @pytest.mark.asyncio
    async def test_reprocess_documents_success(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        test_documents: List[Document]
    ):
        """测试重新处理文档"""
        payload = {
            "document_ids": [str(doc.id) for doc in test_documents]
        }
        
        res = await async_client.post(
            "/api/v1/documents/reprocess",
            json=payload,
            headers=auth_headers
        )
        
        assert res.status_code == 202
        data = res.json()
        assert data["message"].startswith("已提交")
        assert len(data["document_ids"]) == len(test_documents)

    @pytest.mark.asyncio
    async def test_reprocess_documents_unauthorized(
        self,
        async_client: AsyncClient,
        test_documents: List[Document]
    ):
        """测试未认证重新处理"""
        payload = {
            "document_ids": [str(doc.id) for doc in test_documents]
        }
        
        res = await async_client.post(
            "/api/v1/documents/reprocess",
            json=payload
        )
        
        assert res.status_code == 401

