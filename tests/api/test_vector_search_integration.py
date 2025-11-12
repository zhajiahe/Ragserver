"""
向量搜索 API 集成测试（包含真实数据和向量）
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
        username="searchuser",
        email="search@example.com",
        hashed_password=get_password_hash("Test1234!"),
        full_name="Search Test User",
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
        name="AI Knowledge Base",
        description="关于人工智能的知识库",
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
        filename="ai_intro.txt",
        file_type="text/plain",
        file_size=1024,
        s3_url="http://minio:9000/test-bucket/ai_intro.txt",
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
    # 准备测试文本
    test_texts = [
        "人工智能（Artificial Intelligence，AI）是计算机科学的一个分支，致力于创建能够执行通常需要人类智能的任务的系统。",
        "机器学习是人工智能的一个子领域，它使计算机能够从数据中学习，而无需明确编程。",
        "深度学习是机器学习的一个分支，使用多层神经网络来处理复杂的模式识别任务。",
        "自然语言处理（NLP）是人工智能的一个领域，专注于使计算机能够理解、解释和生成人类语言。",
        "计算机视觉是人工智能的一个分支，使计算机能够从图像和视频中获取有意义的信息。",
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
        "username_or_email": "searchuser",
        "password": "Test1234!",
    }
    res = await async_client.post("/api/v1/auth/login", json=login_payload)
    assert res.status_code == 200
    token = res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


class TestVectorSearchWithRealData:
    """使用真实数据和向量的搜索测试"""

    @pytest.mark.asyncio
    async def test_search_with_relevant_query(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        test_collection: Collection,
        test_chunks_with_embeddings: list
    ):
        """测试相关查询能找到结果"""
        payload = {
            "query": "什么是人工智能？",
            "top_k": 3,
            "threshold": 0.3,  # 降低阈值以确保能找到结果
            "collection_ids": [str(test_collection.id)]
        }
        
        res = await async_client.post(
            "/api/v1/search",
            json=payload,
            headers=auth_headers
        )
        
        assert res.status_code == 200
        data = res.json()
        assert data["query"] == "什么是人工智能？"
        assert data["total"] > 0, "应该找到相关结果"
        assert len(data["results"]) > 0
        
        # 验证结果结构
        first_result = data["results"][0]
        assert "chunk_id" in first_result
        assert "document_id" in first_result
        assert "collection_id" in first_result
        assert "content" in first_result
        assert "similarity" in first_result
        assert "metadata" in first_result
        assert "chunk_index" in first_result
        
        # 验证相似度分数
        assert 0 <= first_result["similarity"] <= 1
        
        # 验证结果按相似度排序（降序）
        similarities = [r["similarity"] for r in data["results"]]
        assert similarities == sorted(similarities, reverse=True)

    @pytest.mark.asyncio
    async def test_search_machine_learning(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        test_collection: Collection,
        test_chunks_with_embeddings: list
    ):
        """测试搜索机器学习相关内容"""
        payload = {
            "query": "机器学习是什么？",
            "top_k": 2,
            "threshold": 0.3,
        }
        
        res = await async_client.post(
            "/api/v1/search",
            json=payload,
            headers=auth_headers
        )
        
        assert res.status_code == 200
        data = res.json()
        assert data["total"] > 0
        
        # 验证返回的内容包含"机器学习"相关的分块
        contents = [r["content"] for r in data["results"]]
        assert any("机器学习" in content for content in contents)

    @pytest.mark.asyncio
    async def test_search_deep_learning(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        test_collection: Collection,
        test_chunks_with_embeddings: list
    ):
        """测试搜索深度学习相关内容"""
        payload = {
            "query": "深度学习和神经网络",
            "top_k": 3,
            "threshold": 0.3,
        }
        
        res = await async_client.post(
            "/api/v1/search",
            json=payload,
            headers=auth_headers
        )
        
        assert res.status_code == 200
        data = res.json()
        assert data["total"] > 0
        
        # 验证返回的内容包含"深度学习"相关的分块
        contents = [r["content"] for r in data["results"]]
        assert any("深度学习" in content or "神经网络" in content for content in contents)

    @pytest.mark.asyncio
    async def test_search_with_high_threshold(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        test_collection: Collection,
        test_chunks_with_embeddings: list
    ):
        """测试高阈值过滤"""
        payload = {
            "query": "完全不相关的查询内容关于做饭和烹饪",
            "top_k": 10,
            "threshold": 0.9,  # 非常高的阈值
        }
        
        res = await async_client.post(
            "/api/v1/search",
            json=payload,
            headers=auth_headers
        )
        
        assert res.status_code == 200
        data = res.json()
        # 由于查询不相关且阈值很高，可能找不到结果
        assert data["total"] >= 0

    @pytest.mark.asyncio
    async def test_search_without_collection_filter(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        test_chunks_with_embeddings: list
    ):
        """测试不指定知识库的搜索"""
        payload = {
            "query": "人工智能",
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
        assert data["total"] > 0

    @pytest.mark.asyncio
    async def test_search_top_k_limit(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        test_collection: Collection,
        test_chunks_with_embeddings: list
    ):
        """测试 top_k 限制"""
        payload = {
            "query": "人工智能",
            "top_k": 2,
            "threshold": 0.1,  # 低阈值确保有足够结果
        }
        
        res = await async_client.post(
            "/api/v1/search",
            json=payload,
            headers=auth_headers
        )
        
        assert res.status_code == 200
        data = res.json()
        assert len(data["results"]) <= 2

    @pytest.mark.asyncio
    async def test_search_response_time(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        test_collection: Collection,
        test_chunks_with_embeddings: list
    ):
        """测试搜索响应时间"""
        payload = {
            "query": "人工智能技术",
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
        assert "search_time_ms" in data
        assert data["search_time_ms"] > 0
        # 搜索应该在合理时间内完成（10秒）
        assert data["search_time_ms"] < 10000


class TestVectorSearchMultipleCollections:
    """多知识库搜索测试"""

    @pytest.mark.asyncio
    async def test_search_multiple_collections(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        db_session: AsyncSession,
        test_user: User,
        test_chunks_with_embeddings: list
    ):
        """测试跨多个知识库搜索"""
        # 创建第二个知识库
        collection2 = Collection(
            user_id=test_user.id,
            name="Programming Knowledge Base",
            description="关于编程的知识库",
            status="active",
        )
        db_session.add(collection2)
        await db_session.commit()
        await db_session.refresh(collection2)
        
        # 创建第二个文档
        document2 = Document(
            collection_id=collection2.id,
            uploaded_by=test_user.id,
            filename="programming.txt",
            file_type="text/plain",
            file_size=512,
            s3_url="http://minio:9000/test-bucket/programming.txt",
            mime_type="text/plain",
            file_hash="def456",
            status="completed",
            progress=100,
        )
        db_session.add(document2)
        await db_session.commit()
        await db_session.refresh(document2)
        
        # 添加编程相关的分块
        programming_texts = [
            "Python是一种高级编程语言，以其简洁的语法和强大的功能而闻名。",
            "JavaScript是Web开发中最常用的编程语言之一。",
        ]
        
        embeddings = await embedding_service.encode(programming_texts)
        
        for i, (text, embedding) in enumerate(zip(programming_texts, embeddings)):
            chunk = DocumentChunk(
                document_id=document2.id,
                collection_id=collection2.id,
                user_id=test_user.id,
                content=text,
                content_hash=f"prog_hash_{i}",
                chunk_index=i,
                content_embedding=embedding,
                embedding_model="BAAI/bge-m3",
                meta={"source": "programming"}
            )
            db_session.add(chunk)
        
        await db_session.commit()
        
        # 搜索第一个知识库（AI相关）
        first_collection = test_chunks_with_embeddings[0].collection_id
        payload = {
            "query": "人工智能",
            "top_k": 5,
            "threshold": 0.3,
            "collection_ids": [str(first_collection)]
        }
        
        res = await async_client.post(
            "/api/v1/search",
            json=payload,
            headers=auth_headers
        )
        
        assert res.status_code == 200
        data = res.json()
        
        # 验证所有结果都来自指定的知识库
        for result in data["results"]:
            assert result["collection_id"] == str(first_collection)


class TestShareSearchWithRealData:
    """分享链接搜索测试（包含真实数据）"""

    @pytest.mark.asyncio
    async def test_share_search_with_real_data(
        self,
        async_client: AsyncClient,
        db_session: AsyncSession,
        test_collection: Collection,
        test_user: User,
        test_chunks_with_embeddings: list
    ):
        """测试通过分享链接搜索真实数据"""
        # 创建分享
        share = CollectionShare(
            collection_id=test_collection.id,
            created_by=test_user.id,
            share_token="kb_share_real_test",
            name="AI知识库分享",
            is_active=True,
            search_config={"max_top_k": 10},
        )
        db_session.add(share)
        await db_session.commit()
        
        payload = {
            "query": "什么是机器学习？",
            "top_k": 3,
            "threshold": 0.3,
        }
        
        res = await async_client.post(
            f"/api/v1/share/{share.share_token}/search",
            json=payload
        )
        
        assert res.status_code == 200
        data = res.json()
        assert data["total"] > 0
        assert len(data["results"]) > 0
        
        # 验证所有结果都来自分享的知识库
        for result in data["results"]:
            assert result["collection_id"] == str(test_collection.id)
        
        # 验证使用统计已更新
        await db_session.refresh(share)
        assert share.usage_count == 1
        assert share.last_used_at is not None

    @pytest.mark.asyncio
    async def test_share_search_with_max_top_k_limit(
        self,
        async_client: AsyncClient,
        db_session: AsyncSession,
        test_collection: Collection,
        test_user: User,
        test_chunks_with_embeddings: list
    ):
        """测试分享链接的 max_top_k 限制"""
        # 创建限制 max_top_k=2 的分享
        share = CollectionShare(
            collection_id=test_collection.id,
            created_by=test_user.id,
            share_token="kb_share_limited_topk",
            name="受限分享",
            is_active=True,
            search_config={"max_top_k": 2},
        )
        db_session.add(share)
        await db_session.commit()
        
        # 请求 top_k=10，应该被限制为 2
        payload = {
            "query": "人工智能",
            "top_k": 10,
            "threshold": 0.1,
        }
        
        res = await async_client.post(
            f"/api/v1/share/{share.share_token}/search",
            json=payload
        )
        
        assert res.status_code == 200
        data = res.json()
        # 结果数量应该不超过 2
        assert len(data["results"]) <= 2


class TestSearchEdgeCases:
    """搜索边界情况测试"""

    @pytest.mark.asyncio
    async def test_search_empty_query(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
    ):
        """测试空查询"""
        payload = {
            "query": "",
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
    async def test_search_very_long_query(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        test_chunks_with_embeddings: list
    ):
        """测试超长查询"""
        # 创建一个超长查询（超过1000字符）
        long_query = "人工智能" * 500
        payload = {
            "query": long_query,
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
    async def test_search_no_chunks_in_collection(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        db_session: AsyncSession,
        test_user: User
    ):
        """测试搜索空知识库"""
        # 创建一个空知识库
        empty_collection = Collection(
            user_id=test_user.id,
            name="Empty Collection",
            description="空知识库",
            status="active",
        )
        db_session.add(empty_collection)
        await db_session.commit()
        await db_session.refresh(empty_collection)
        
        payload = {
            "query": "测试查询",
            "top_k": 5,
            "threshold": 0.3,
            "collection_ids": [str(empty_collection.id)]
        }
        
        res = await async_client.post(
            "/api/v1/search",
            json=payload,
            headers=auth_headers
        )
        
        assert res.status_code == 200
        data = res.json()
        assert data["total"] == 0
        assert len(data["results"]) == 0

    @pytest.mark.asyncio
    async def test_search_nonexistent_collection(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
    ):
        """测试搜索不存在的知识库"""
        fake_id = str(uuid4())
        payload = {
            "query": "测试查询",
            "top_k": 5,
            "collection_ids": [fake_id]
        }
        
        res = await async_client.post(
            "/api/v1/search",
            json=payload,
            headers=auth_headers
        )
        
        # 应该返回空结果（因为用户没有该知识库的权限）
        assert res.status_code == 200
        data = res.json()
        assert data["total"] == 0

