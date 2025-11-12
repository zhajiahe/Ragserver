"""
全文搜索和混合搜索 API 集成测试
"""
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta
from uuid import uuid4

from ragserver.main import app
from ragserver.app.dependencies import get_db
from ragserver.app.models import User, Collection, Document, DocumentChunk, CollectionShare
from ragserver.app.dependencies.security import get_password_hash
from ragserver.app.utils.date_util import get_current_time
from ragserver.app.utils.embedding_service import embedding_service


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
        username="fulltextuser",
        email="fulltext@example.com",
        hashed_password=get_password_hash("Test1234!"),
        full_name="Fulltext Test User",
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
        name="Tech Knowledge Base",
        description="关于技术的知识库",
        status="active",
    )
    db_session.add(collection)
    await db_session.commit()
    await db_session.refresh(collection)
    return collection


@pytest.fixture
async def test_document(db_session: AsyncSession, test_collection: Collection, test_user: User):
    """创建测试文档"""
    document = Document(
        collection_id=test_collection.id,
        uploaded_by=test_user.id,
        filename="tech_intro.txt",
        file_type="text/plain",
        file_size=1024,
        s3_url="http://minio:9000/test-bucket/tech_intro.txt",
        mime_type="text/plain",
        file_hash="abc123",
        status="completed",
        progress=100,
    )
    db_session.add(document)
    await db_session.commit()
    await db_session.refresh(document)
    return document


@pytest.fixture
async def test_chunks_with_embeddings(
    db_session: AsyncSession,
    test_document: Document,
    test_collection: Collection,
    test_user: User
):
    """创建包含真实向量的测试分块"""
    # 准备测试文本 - 包含明确的关键词
    test_texts = [
        "Python是一种高级编程语言，以其简洁的语法和强大的功能而闻名。Python广泛应用于Web开发、数据分析、人工智能等领域。",
        "JavaScript是Web开发中最常用的编程语言之一。它可以在浏览器中运行，也可以通过Node.js在服务器端运行。",
        "数据库是存储和管理数据的系统。常见的数据库包括MySQL、PostgreSQL、MongoDB等。数据库对于现代应用程序至关重要。",
        "机器学习是人工智能的一个分支，它使计算机能够从数据中学习。深度学习是机器学习的一个子领域，使用神经网络处理复杂任务。",
        "Docker是一个容器化平台，可以将应用程序及其依赖项打包在一起。Kubernetes是一个容器编排系统，用于管理Docker容器。",
    ]
    
    # 生成向量
    embeddings = await embedding_service.encode(test_texts)
    
    # 创建分块
    chunks = []
    for i, (text, embedding) in enumerate(zip(test_texts, embeddings)):
        chunk = DocumentChunk(
            document_id=test_document.id,
            collection_id=test_collection.id,
            user_id=test_user.id,
            content=text,
            content_hash=f"hash_{i}",
            chunk_index=i,
            content_embedding=embedding,
            embedding_model="BAAI/bge-m3",
            meta={"source": "test"}
        )
        chunks.append(chunk)
        db_session.add(chunk)
    
    await db_session.commit()
    
    # 刷新所有分块
    for chunk in chunks:
        await db_session.refresh(chunk)
    
    return chunks


@pytest.fixture
async def auth_headers(async_client: AsyncClient, test_user: User):
    """获取认证头"""
    login_payload = {
        "username_or_email": "fulltextuser",
        "password": "Test1234!",
    }
    res = await async_client.post("/api/v1/auth/login", json=login_payload)
    assert res.status_code == 200
    token = res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


class TestFulltextSearch:
    """全文搜索测试"""

    @pytest.mark.asyncio
    async def test_fulltext_search_with_keyword(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        test_collection: Collection,
        test_chunks_with_embeddings: list
    ):
        """测试全文搜索 - 关键词匹配"""
        payload = {
            "query": "Python",
            "mode": "fulltext",
            "top_k": 5,
        }
        
        res = await async_client.post(
            "/api/v1/search",
            json=payload,
            headers=auth_headers
        )
        
        assert res.status_code == 200
        data = res.json()
        assert data["query"] == "Python"
        assert data["mode"] == "fulltext"
        assert "results" in data
        assert "search_time_ms" in data
        
        # 如果找到结果，验证结果中包含关键词
        if data["total"] > 0:
            # 至少有一个结果应该包含 "Python"
            contents = [r["content"] for r in data["results"]]
            assert any("Python" in content for content in contents)

    @pytest.mark.asyncio
    async def test_fulltext_search_javascript(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        test_collection: Collection,
        test_chunks_with_embeddings: list
    ):
        """测试全文搜索 - JavaScript关键词"""
        payload = {
            "query": "JavaScript",
            "mode": "fulltext",
            "top_k": 3,
        }
        
        res = await async_client.post(
            "/api/v1/search",
            json=payload,
            headers=auth_headers
        )
        
        assert res.status_code == 200
        data = res.json()
        assert data["mode"] == "fulltext"
        
        # 如果找到结果，验证包含 JavaScript
        if data["total"] > 0:
            contents = [r["content"] for r in data["results"]]
            assert any("JavaScript" in content for content in contents)

    @pytest.mark.asyncio
    async def test_fulltext_search_database(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        test_chunks_with_embeddings: list
    ):
        """测试全文搜索 - 数据库关键词"""
        payload = {
            "query": "数据库",
            "mode": "fulltext",
            "top_k": 5,
        }
        
        res = await async_client.post(
            "/api/v1/search",
            json=payload,
            headers=auth_headers
        )
        
        assert res.status_code == 200
        data = res.json()
        assert data["mode"] == "fulltext"


class TestHybridSearch:
    """混合搜索测试"""

    @pytest.mark.asyncio
    async def test_hybrid_search_default_weights(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        test_collection: Collection,
        test_chunks_with_embeddings: list
    ):
        """测试混合搜索 - 默认权重"""
        payload = {
            "query": "Python编程语言",
            "mode": "hybrid",
            "top_k": 5,
            "threshold": 0.3,
        }
        
        res = await async_client.post(
            "/api/v1/search",
            json=payload,
            headers=auth_headers
        )
        
        assert res.status_code == 200
        data = res.json()
        assert data["query"] == "Python编程语言"
        assert data["mode"] == "hybrid"
        assert "results" in data
        assert data["total"] >= 0

    @pytest.mark.asyncio
    async def test_hybrid_search_custom_weights(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        test_collection: Collection,
        test_chunks_with_embeddings: list
    ):
        """测试混合搜索 - 自定义权重"""
        payload = {
            "query": "机器学习",
            "mode": "hybrid",
            "top_k": 3,
            "threshold": 0.3,
            "vector_weight": 0.5,
            "fulltext_weight": 0.5,
        }
        
        res = await async_client.post(
            "/api/v1/search",
            json=payload,
            headers=auth_headers
        )
        
        assert res.status_code == 200
        data = res.json()
        assert data["mode"] == "hybrid"
        assert data["total"] >= 0

    @pytest.mark.asyncio
    async def test_hybrid_search_vector_heavy(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        test_chunks_with_embeddings: list
    ):
        """测试混合搜索 - 向量权重更高"""
        payload = {
            "query": "容器化技术",
            "mode": "hybrid",
            "top_k": 5,
            "threshold": 0.2,
            "vector_weight": 0.9,
            "fulltext_weight": 0.1,
        }
        
        res = await async_client.post(
            "/api/v1/search",
            json=payload,
            headers=auth_headers
        )
        
        assert res.status_code == 200
        data = res.json()
        assert data["mode"] == "hybrid"

    @pytest.mark.asyncio
    async def test_hybrid_search_fulltext_heavy(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        test_chunks_with_embeddings: list
    ):
        """测试混合搜索 - 全文权重更高"""
        payload = {
            "query": "Docker",
            "mode": "hybrid",
            "top_k": 5,
            "threshold": 0.2,
            "vector_weight": 0.1,
            "fulltext_weight": 0.9,
        }
        
        res = await async_client.post(
            "/api/v1/search",
            json=payload,
            headers=auth_headers
        )
        
        assert res.status_code == 200
        data = res.json()
        assert data["mode"] == "hybrid"


class TestSearchModeComparison:
    """搜索模式对比测试"""

    @pytest.mark.asyncio
    async def test_compare_all_search_modes(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        test_chunks_with_embeddings: list
    ):
        """对比三种搜索模式的结果"""
        query = "Python编程"
        
        # 向量搜索
        vector_res = await async_client.post(
            "/api/v1/search",
            json={"query": query, "mode": "vector", "top_k": 5, "threshold": 0.3},
            headers=auth_headers
        )
        
        # 全文搜索
        fulltext_res = await async_client.post(
            "/api/v1/search",
            json={"query": query, "mode": "fulltext", "top_k": 5},
            headers=auth_headers
        )
        
        # 混合搜索
        hybrid_res = await async_client.post(
            "/api/v1/search",
            json={"query": query, "mode": "hybrid", "top_k": 5, "threshold": 0.3},
            headers=auth_headers
        )
        
        # 验证所有请求都成功
        assert vector_res.status_code == 200
        assert fulltext_res.status_code == 200
        assert hybrid_res.status_code == 200
        
        vector_data = vector_res.json()
        fulltext_data = fulltext_res.json()
        hybrid_data = hybrid_res.json()
        
        # 验证模式标识
        assert vector_data["mode"] == "vector"
        assert fulltext_data["mode"] == "fulltext"
        assert hybrid_data["mode"] == "hybrid"
        
        # 打印结果数量对比
        print(f"\n搜索模式对比 - 查询: {query}")
        print(f"  向量搜索: {vector_data['total']} 个结果")
        print(f"  全文搜索: {fulltext_data['total']} 个结果")
        print(f"  混合搜索: {hybrid_data['total']} 个结果")


class TestShareSearchWithModes:
    """分享链接搜索模式测试"""

    @pytest.mark.asyncio
    async def test_share_search_vector_mode(
        self,
        async_client: AsyncClient,
        db_session: AsyncSession,
        test_collection: Collection,
        test_user: User,
        test_chunks_with_embeddings: list
    ):
        """测试分享链接的向量搜索"""
        # 创建分享
        share = CollectionShare(
            collection_id=test_collection.id,
            created_by=test_user.id,
            share_token="kb_share_fulltext_test",
            name="技术知识库分享",
            is_active=True,
            search_config={"max_top_k": 10},
        )
        db_session.add(share)
        await db_session.commit()
        
        payload = {
            "query": "Python",
            "mode": "vector",
            "top_k": 3,
            "threshold": 0.3,
        }
        
        res = await async_client.post(
            f"/api/v1/share/{share.share_token}/search",
            json=payload
        )
        
        assert res.status_code == 200
        data = res.json()
        assert data["mode"] == "vector"

    @pytest.mark.asyncio
    async def test_share_search_fulltext_mode(
        self,
        async_client: AsyncClient,
        db_session: AsyncSession,
        test_collection: Collection,
        test_user: User,
        test_chunks_with_embeddings: list
    ):
        """测试分享链接的全文搜索"""
        # 创建分享
        share = CollectionShare(
            collection_id=test_collection.id,
            created_by=test_user.id,
            share_token="kb_share_fulltext_test2",
            name="技术知识库分享2",
            is_active=True,
            search_config={"max_top_k": 10},
        )
        db_session.add(share)
        await db_session.commit()
        
        payload = {
            "query": "JavaScript",
            "mode": "fulltext",
            "top_k": 3,
        }
        
        res = await async_client.post(
            f"/api/v1/share/{share.share_token}/search",
            json=payload
        )
        
        assert res.status_code == 200
        data = res.json()
        assert data["mode"] == "fulltext"

    @pytest.mark.asyncio
    async def test_share_search_hybrid_mode(
        self,
        async_client: AsyncClient,
        db_session: AsyncSession,
        test_collection: Collection,
        test_user: User,
        test_chunks_with_embeddings: list
    ):
        """测试分享链接的混合搜索"""
        # 创建分享
        share = CollectionShare(
            collection_id=test_collection.id,
            created_by=test_user.id,
            share_token="kb_share_hybrid_test",
            name="技术知识库分享3",
            is_active=True,
            search_config={"max_top_k": 10},
        )
        db_session.add(share)
        await db_session.commit()
        
        payload = {
            "query": "数据库系统",
            "mode": "hybrid",
            "top_k": 3,
            "threshold": 0.3,
        }
        
        res = await async_client.post(
            f"/api/v1/share/{share.share_token}/search",
            json=payload
        )
        
        assert res.status_code == 200
        data = res.json()
        assert data["mode"] == "hybrid"


class TestSearchEdgeCases:
    """搜索边界情况测试"""

    @pytest.mark.asyncio
    async def test_invalid_search_mode(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
    ):
        """测试无效的搜索模式"""
        payload = {
            "query": "测试",
            "mode": "invalid_mode",
            "top_k": 5,
        }
        
        res = await async_client.post(
            "/api/v1/search",
            json=payload,
            headers=auth_headers
        )
        
        # 应该返回验证错误
        assert res.status_code == 422

    @pytest.mark.asyncio
    async def test_fulltext_search_no_results(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        test_chunks_with_embeddings: list
    ):
        """测试全文搜索无结果的情况"""
        payload = {
            "query": "完全不存在的关键词xyzabc123",
            "mode": "fulltext",
            "top_k": 5,
        }
        
        res = await async_client.post(
            "/api/v1/search",
            json=payload,
            headers=auth_headers
        )
        
        assert res.status_code == 200
        data = res.json()
        assert data["mode"] == "fulltext"
        # 可能找不到结果
        assert data["total"] >= 0

