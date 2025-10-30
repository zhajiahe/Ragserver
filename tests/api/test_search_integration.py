"""
搜索 API 集成测试
"""
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta

from ragserver.main import app
from ragserver.app.dependencies import get_db
from ragserver.app.models import User, Collection, CollectionShare
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


class TestSearchAuthenticated:
    """认证搜索测试"""

    @pytest.mark.asyncio
    async def test_search_authenticated(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        test_collection: Collection
    ):
        """测试认证用户搜索"""
        payload = {
            "query": "测试查询",
            "top_k": 5,
            "threshold": 0.7,
            "collection_ids": [str(test_collection.id)]
        }
        
        res = await async_client.post(
            "/api/v1/search",
            json=payload,
            headers=auth_headers
        )
        
        assert res.status_code == 200
        data = res.json()
        assert data["query"] == "测试查询"
        assert data["total"] >= 0
        assert "results" in data
        assert "search_time_ms" in data

    @pytest.mark.asyncio
    async def test_search_without_auth(
        self,
        async_client: AsyncClient,
    ):
        """测试未认证用户无法访问"""
        payload = {
            "query": "测试查询",
            "top_k": 5
        }
        
        res = await async_client.post(
            "/api/v1/search",
            json=payload
        )
        
        assert res.status_code == 401

    @pytest.mark.asyncio
    async def test_search_with_invalid_top_k(
        self,
        async_client: AsyncClient,
        auth_headers: dict
    ):
        """测试无效的 top_k 参数"""
        payload = {
            "query": "测试查询",
            "top_k": 200,  # 超过最大值 100
        }
        
        res = await async_client.post(
            "/api/v1/search",
            json=payload,
            headers=auth_headers
        )
        
        assert res.status_code == 422  # Validation error


class TestCollectionShare:
    """知识库分享测试"""

    @pytest.mark.asyncio
    async def test_create_share_success(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        test_collection: Collection,
        db_session: AsyncSession
    ):
        """测试成功创建分享链接"""
        payload = {
            "name": "公开分享",
            "description": "这是一个公开分享",
            "expires_in_days": 30,
            "search_config": {"max_top_k": 20}
        }
        
        res = await async_client.post(
            f"/api/v1/collections/{test_collection.id}/share",
            json=payload,
            headers=auth_headers
        )
        
        assert res.status_code == 201
        data = res.json()
        assert data["name"] == "公开分享"
        assert data["collection_id"] == str(test_collection.id)
        assert data["is_active"] is True
        assert "share_token" in data
        assert data["share_token"].startswith("kb_share_")
        assert "share_url" in data
        assert data["usage_count"] == 0
        
        # 验证数据库
        result = await db_session.execute(
            select(CollectionShare).where(
                CollectionShare.share_token == data["share_token"]
            )
        )
        share = result.scalar_one()
        assert share.collection_id == test_collection.id
        assert share.is_active is True

    @pytest.mark.asyncio
    async def test_create_share_nonexistent_collection(
        self,
        async_client: AsyncClient,
        auth_headers: dict
    ):
        """测试为不存在的知识库创建分享"""
        import uuid
        fake_id = uuid.uuid4()
        
        payload = {
            "name": "测试分享",
        }
        
        res = await async_client.post(
            f"/api/v1/collections/{fake_id}/share",
            json=payload,
            headers=auth_headers
        )
        
        assert res.status_code == 404

    @pytest.mark.asyncio
    async def test_list_shares(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        test_collection: Collection,
        db_session: AsyncSession,
        test_user: User
    ):
        """测试获取分享列表"""
        # 创建几个分享
        shares = []
        for i in range(3):
            share = CollectionShare(
                collection_id=test_collection.id,
                created_by=test_user.id,
                share_token=f"kb_share_test_{i}",
                name=f"分享{i}",
                is_active=True,
            )
            db_session.add(share)
            shares.append(share)
        
        await db_session.commit()
        
        res = await async_client.get(
            f"/api/v1/collections/{test_collection.id}/shares",
            headers=auth_headers
        )
        
        assert res.status_code == 200
        data = res.json()
        assert data["total"] == 3
        assert len(data["items"]) == 3

    @pytest.mark.asyncio
    async def test_delete_share(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        test_collection: Collection,
        db_session: AsyncSession,
        test_user: User
    ):
        """测试删除分享链接"""
        # 创建分享
        share = CollectionShare(
            collection_id=test_collection.id,
            created_by=test_user.id,
            share_token="kb_share_to_delete",
            name="待删除分享",
            is_active=True,
        )
        db_session.add(share)
        await db_session.commit()
        await db_session.refresh(share)
        
        res = await async_client.delete(
            f"/api/v1/collections/{test_collection.id}/shares/{share.id}",
            headers=auth_headers
        )
        
        assert res.status_code == 204
        
        # 验证数据库已删除
        result = await db_session.execute(
            select(CollectionShare).where(CollectionShare.id == share.id)
        )
        assert result.scalar_one_or_none() is None

    @pytest.mark.asyncio
    async def test_toggle_share_status(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        test_collection: Collection,
        db_session: AsyncSession,
        test_user: User
    ):
        """测试切换分享状态"""
        # 创建分享
        share = CollectionShare(
            collection_id=test_collection.id,
            created_by=test_user.id,
            share_token="kb_share_to_toggle",
            name="待切换分享",
            is_active=True,
        )
        db_session.add(share)
        await db_session.commit()
        await db_session.refresh(share)
        
        # 第一次切换（True -> False）
        res = await async_client.put(
            f"/api/v1/collections/{test_collection.id}/shares/{share.id}/toggle",
            headers=auth_headers
        )
        
        assert res.status_code == 200
        data = res.json()
        assert data["is_active"] is False
        
        # 第二次切换（False -> True）
        res = await async_client.put(
            f"/api/v1/collections/{test_collection.id}/shares/{share.id}/toggle",
            headers=auth_headers
        )
        
        assert res.status_code == 200
        data = res.json()
        assert data["is_active"] is True


class TestShareSearch:
    """分享链接搜索测试"""

    @pytest.mark.asyncio
    async def test_search_by_share_token_success(
        self,
        async_client: AsyncClient,
        test_collection: Collection,
        db_session: AsyncSession,
        test_user: User
    ):
        """测试通过分享链接搜索"""
        # 创建分享
        share = CollectionShare(
            collection_id=test_collection.id,
            created_by=test_user.id,
            share_token="kb_share_test_search",
            name="测试搜索",
            is_active=True,
            search_config={"max_top_k": 20},
        )
        db_session.add(share)
        await db_session.commit()
        
        payload = {
            "query": "测试查询",
            "top_k": 5
        }
        
        res = await async_client.post(
            f"/api/v1/share/{share.share_token}/search",
            json=payload
        )
        
        assert res.status_code == 200
        data = res.json()
        assert data["query"] == "测试查询"
        assert data["total"] >= 0
        
        # 验证使用统计已更新
        await db_session.refresh(share)
        assert share.usage_count == 1
        assert share.last_used_at is not None

    @pytest.mark.asyncio
    async def test_search_by_inactive_share(
        self,
        async_client: AsyncClient,
        test_collection: Collection,
        db_session: AsyncSession,
        test_user: User
    ):
        """测试使用已停用的分享链接"""
        # 创建已停用的分享
        share = CollectionShare(
            collection_id=test_collection.id,
            created_by=test_user.id,
            share_token="kb_share_inactive",
            name="已停用",
            is_active=False,
        )
        db_session.add(share)
        await db_session.commit()
        
        payload = {
            "query": "测试查询",
            "top_k": 5
        }
        
        res = await async_client.post(
            f"/api/v1/share/{share.share_token}/search",
            json=payload
        )
        
        assert res.status_code == 403
        assert "已停用" in res.json()["detail"]

    @pytest.mark.asyncio
    async def test_search_by_expired_share(
        self,
        async_client: AsyncClient,
        test_collection: Collection,
        db_session: AsyncSession,
        test_user: User
    ):
        """测试使用已过期的分享链接"""
        from datetime import timezone
        
        # 创建已过期的分享
        share = CollectionShare(
            collection_id=test_collection.id,
            created_by=test_user.id,
            share_token="kb_share_expired",
            name="已过期",
            is_active=True,
            expires_at=datetime.now(timezone.utc) - timedelta(days=1),  # 昨天过期
        )
        db_session.add(share)
        await db_session.commit()
        
        payload = {
            "query": "测试查询",
            "top_k": 5
        }
        
        res = await async_client.post(
            f"/api/v1/share/{share.share_token}/search",
            json=payload
        )
        
        assert res.status_code == 403
        assert "已过期" in res.json()["detail"]

    @pytest.mark.asyncio
    async def test_search_by_nonexistent_share(
        self,
        async_client: AsyncClient
    ):
        """测试使用不存在的分享链接"""
        payload = {
            "query": "测试查询",
            "top_k": 5
        }
        
        res = await async_client.post(
            "/api/v1/share/kb_share_nonexistent/search",
            json=payload
        )
        
        assert res.status_code == 404

    @pytest.mark.asyncio
    async def test_search_with_top_k_limit(
        self,
        async_client: AsyncClient,
        test_collection: Collection,
        db_session: AsyncSession,
        test_user: User
    ):
        """测试 top_k 受分享配置限制"""
        # 创建限制 max_top_k=5 的分享
        share = CollectionShare(
            collection_id=test_collection.id,
            created_by=test_user.id,
            share_token="kb_share_limited",
            name="受限分享",
            is_active=True,
            search_config={"max_top_k": 5},
        )
        db_session.add(share)
        await db_session.commit()
        
        # 请求 top_k=10，应该被限制为 5
        payload = {
            "query": "测试查询",
            "top_k": 10
        }
        
        res = await async_client.post(
            f"/api/v1/share/{share.share_token}/search",
            json=payload
        )
        
        assert res.status_code == 200
        # 注意：实际搜索逻辑需要实现后，结果数量才会受到限制
        # 这里只测试接口能正常响应

