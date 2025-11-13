"""知识库分享管理 API 集成测试"""

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ragserver.app.dependencies import get_db
from ragserver.app.dependencies.security import get_password_hash
from ragserver.app.models import Collection, CollectionShare, User
from ragserver.main import app


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
async def test_user2(db_session: AsyncSession, setup_db):
    """创建第二个测试用户"""
    user = User(
        username="testuser2",
        email="test2@example.com",
        hashed_password=get_password_hash("Test1234!"),
        full_name="Test User 2",
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


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


@pytest.fixture
async def auth_headers2(async_client: AsyncClient, test_user2: User):
    """获取第二个用户的认证头"""
    login_payload = {
        "username_or_email": "testuser2",
        "password": "Test1234!",
    }
    res = await async_client.post("/api/v1/auth/login", json=login_payload)
    assert res.status_code == 200
    token = res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


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


class TestCreateShare:
    """测试创建分享"""

    @pytest.mark.asyncio
    async def test_create_share_success(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        db_session: AsyncSession,
        test_collection: Collection,
    ):
        """测试成功创建分享"""
        payload = {
            "name": "Public Share",
            "description": "Share for testing",
            "expires_in_days": 7,
            "search_config": {"top_k": 5},
        }

        res = await async_client.post(
            f"/api/v1/collections/{test_collection.id}/share", json=payload, headers=auth_headers
        )

        assert res.status_code == 201
        data = res.json()
        assert data["name"] == "Public Share"
        assert data["description"] == "Share for testing"
        assert data["is_active"] is True
        assert data["usage_count"] == 0
        assert data["search_config"] == {"top_k": 5}
        assert "share_token" in data
        assert data["share_token"].startswith("kb_share_")
        assert "share_url" in data

        # 验证数据库
        result = await db_session.execute(select(CollectionShare).where(CollectionShare.id == data["id"]))
        share = result.scalar_one()
        assert share.collection_id == test_collection.id
        assert share.name == "Public Share"

    @pytest.mark.asyncio
    async def test_create_share_without_expiry(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        test_collection: Collection,
    ):
        """测试创建永久有效的分享"""
        payload = {
            "name": "Permanent Share",
            "description": "Never expires",
        }

        res = await async_client.post(
            f"/api/v1/collections/{test_collection.id}/share", json=payload, headers=auth_headers
        )

        assert res.status_code == 201
        data = res.json()
        assert data["expires_at"] is None

    @pytest.mark.asyncio
    async def test_create_share_collection_not_found(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
    ):
        """测试创建分享时知识库不存在"""
        from uuid import uuid4

        fake_id = uuid4()

        payload = {
            "name": "Test Share",
        }

        res = await async_client.post(f"/api/v1/collections/{fake_id}/share", json=payload, headers=auth_headers)

        assert res.status_code == 404
        assert "知识库不存在" in res.json()["detail"]

    @pytest.mark.asyncio
    async def test_create_share_unauthorized(
        self,
        async_client: AsyncClient,
        test_collection: Collection,
    ):
        """测试未认证创建分享"""
        payload = {
            "name": "Test Share",
        }

        res = await async_client.post(f"/api/v1/collections/{test_collection.id}/share", json=payload)

        assert res.status_code == 401


class TestListShares:
    """测试获取分享列表"""

    @pytest.mark.asyncio
    async def test_list_shares_success(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        db_session: AsyncSession,
        test_collection: Collection,
        test_user: User,
    ):
        """测试成功获取分享列表"""
        # 创建多个分享
        shares = []
        for i in range(3):
            share = CollectionShare(
                collection_id=test_collection.id,
                created_by=test_user.id,
                share_token=f"kb_share_test_{i}",
                name=f"Share {i}",
                is_active=True,
            )
            shares.append(share)
            db_session.add(share)

        await db_session.commit()

        res = await async_client.get(f"/api/v1/collections/{test_collection.id}/shares", headers=auth_headers)

        assert res.status_code == 200
        data = res.json()
        assert data["total"] == 3
        assert len(data["items"]) == 3
        assert all(item["collection_id"] == str(test_collection.id) for item in data["items"])

    @pytest.mark.asyncio
    async def test_list_shares_pagination(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        db_session: AsyncSession,
        test_collection: Collection,
        test_user: User,
    ):
        """测试分页"""
        # 创建5个分享
        for i in range(5):
            share = CollectionShare(
                collection_id=test_collection.id,
                created_by=test_user.id,
                share_token=f"kb_share_test_{i}",
                name=f"Share {i}",
                is_active=True,
            )
            db_session.add(share)

        await db_session.commit()

        # 第一页
        res = await async_client.get(
            f"/api/v1/collections/{test_collection.id}/shares?skip=0&limit=2", headers=auth_headers
        )

        assert res.status_code == 200
        data = res.json()
        assert data["total"] == 5
        assert len(data["items"]) == 2

        # 第二页
        res = await async_client.get(
            f"/api/v1/collections/{test_collection.id}/shares?skip=2&limit=2", headers=auth_headers
        )

        assert res.status_code == 200
        data = res.json()
        assert data["total"] == 5
        assert len(data["items"]) == 2

    @pytest.mark.asyncio
    async def test_list_shares_empty(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        test_collection: Collection,
    ):
        """测试空列表"""
        res = await async_client.get(f"/api/v1/collections/{test_collection.id}/shares", headers=auth_headers)

        assert res.status_code == 200
        data = res.json()
        assert data["total"] == 0
        assert len(data["items"]) == 0

    @pytest.mark.asyncio
    async def test_list_shares_collection_not_found(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
    ):
        """测试知识库不存在"""
        from uuid import uuid4

        fake_id = uuid4()

        res = await async_client.get(f"/api/v1/collections/{fake_id}/shares", headers=auth_headers)

        assert res.status_code == 404

    @pytest.mark.asyncio
    async def test_list_shares_unauthorized(
        self,
        async_client: AsyncClient,
        test_collection: Collection,
    ):
        """测试未认证"""
        res = await async_client.get(f"/api/v1/collections/{test_collection.id}/shares")

        assert res.status_code == 401


class TestGetShare:
    """测试获取分享详情"""

    @pytest.mark.asyncio
    async def test_get_share_success(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        db_session: AsyncSession,
        test_collection: Collection,
        test_user: User,
    ):
        """测试成功获取分享详情"""
        share = CollectionShare(
            collection_id=test_collection.id,
            created_by=test_user.id,
            share_token="kb_share_test_123",
            name="Test Share",
            description="Test description",
            is_active=True,
            search_config={"top_k": 10},
        )
        db_session.add(share)
        await db_session.commit()
        await db_session.refresh(share)

        res = await async_client.get(f"/api/v1/shares/{share.id}", headers=auth_headers)

        assert res.status_code == 200
        data = res.json()
        assert data["id"] == str(share.id)
        assert data["name"] == "Test Share"
        assert data["description"] == "Test description"
        assert data["is_active"] is True
        assert data["search_config"] == {"top_k": 10}

    @pytest.mark.asyncio
    async def test_get_share_not_found(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
    ):
        """测试分享不存在"""
        from uuid import uuid4

        fake_id = uuid4()

        res = await async_client.get(f"/api/v1/shares/{fake_id}", headers=auth_headers)

        assert res.status_code == 404

    @pytest.mark.asyncio
    async def test_get_share_not_owner(
        self,
        async_client: AsyncClient,
        auth_headers2: dict,
        db_session: AsyncSession,
        test_collection: Collection,
        test_user: User,
    ):
        """测试获取其他用户的分享"""
        share = CollectionShare(
            collection_id=test_collection.id,
            created_by=test_user.id,
            share_token="kb_share_test_123",
            name="Test Share",
            is_active=True,
        )
        db_session.add(share)
        await db_session.commit()
        await db_session.refresh(share)

        # 使用第二个用户的认证头
        res = await async_client.get(f"/api/v1/shares/{share.id}", headers=auth_headers2)

        assert res.status_code == 404  # 权限不足，返回404

    @pytest.mark.asyncio
    async def test_get_share_unauthorized(
        self,
        async_client: AsyncClient,
        db_session: AsyncSession,
        test_collection: Collection,
        test_user: User,
    ):
        """测试未认证"""
        share = CollectionShare(
            collection_id=test_collection.id,
            created_by=test_user.id,
            share_token="kb_share_test_123",
            name="Test Share",
            is_active=True,
        )
        db_session.add(share)
        await db_session.commit()
        await db_session.refresh(share)

        res = await async_client.get(f"/api/v1/shares/{share.id}")

        assert res.status_code == 401


class TestUpdateShare:
    """测试更新分享"""

    @pytest.mark.asyncio
    async def test_update_share_name(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        db_session: AsyncSession,
        test_collection: Collection,
        test_user: User,
    ):
        """测试更新分享名称"""
        share = CollectionShare(
            collection_id=test_collection.id,
            created_by=test_user.id,
            share_token="kb_share_test_123",
            name="Old Name",
            is_active=True,
        )
        db_session.add(share)
        await db_session.commit()
        await db_session.refresh(share)

        payload = {
            "name": "New Name",
        }

        res = await async_client.put(f"/api/v1/shares/{share.id}", json=payload, headers=auth_headers)

        assert res.status_code == 200
        data = res.json()
        assert data["name"] == "New Name"

        # 验证数据库
        await db_session.refresh(share)
        assert share.name == "New Name"

    @pytest.mark.asyncio
    async def test_update_share_deactivate(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        db_session: AsyncSession,
        test_collection: Collection,
        test_user: User,
    ):
        """测试停用分享"""
        share = CollectionShare(
            collection_id=test_collection.id,
            created_by=test_user.id,
            share_token="kb_share_test_123",
            name="Test Share",
            is_active=True,
        )
        db_session.add(share)
        await db_session.commit()
        await db_session.refresh(share)

        payload = {
            "is_active": False,
        }

        res = await async_client.put(f"/api/v1/shares/{share.id}", json=payload, headers=auth_headers)

        assert res.status_code == 200
        data = res.json()
        assert data["is_active"] is False

        # 验证数据库
        await db_session.refresh(share)
        assert share.is_active is False

    @pytest.mark.asyncio
    async def test_update_share_expiry(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        db_session: AsyncSession,
        test_collection: Collection,
        test_user: User,
    ):
        """测试更新过期时间"""
        share = CollectionShare(
            collection_id=test_collection.id,
            created_by=test_user.id,
            share_token="kb_share_test_123",
            name="Test Share",
            is_active=True,
        )
        db_session.add(share)
        await db_session.commit()
        await db_session.refresh(share)

        payload = {
            "expires_in_days": 30,
        }

        res = await async_client.put(f"/api/v1/shares/{share.id}", json=payload, headers=auth_headers)

        assert res.status_code == 200
        data = res.json()
        assert data["expires_at"] is not None

        # 验证数据库
        await db_session.refresh(share)
        assert share.expires_at is not None

    @pytest.mark.asyncio
    async def test_update_share_search_config(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        db_session: AsyncSession,
        test_collection: Collection,
        test_user: User,
    ):
        """测试更新搜索配置"""
        share = CollectionShare(
            collection_id=test_collection.id,
            created_by=test_user.id,
            share_token="kb_share_test_123",
            name="Test Share",
            is_active=True,
            search_config={"top_k": 5},
        )
        db_session.add(share)
        await db_session.commit()
        await db_session.refresh(share)

        payload = {
            "search_config": {"top_k": 20, "threshold": 0.8},
        }

        res = await async_client.put(f"/api/v1/shares/{share.id}", json=payload, headers=auth_headers)

        assert res.status_code == 200
        data = res.json()
        assert data["search_config"] == {"top_k": 20, "threshold": 0.8}

        # 验证数据库
        await db_session.refresh(share)
        assert share.search_config == {"top_k": 20, "threshold": 0.8}

    @pytest.mark.asyncio
    async def test_update_share_multiple_fields(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        db_session: AsyncSession,
        test_collection: Collection,
        test_user: User,
    ):
        """测试同时更新多个字段"""
        share = CollectionShare(
            collection_id=test_collection.id,
            created_by=test_user.id,
            share_token="kb_share_test_123",
            name="Old Name",
            description="Old description",
            is_active=True,
        )
        db_session.add(share)
        await db_session.commit()
        await db_session.refresh(share)

        payload = {
            "name": "New Name",
            "description": "New description",
            "is_active": False,
            "search_config": {"top_k": 15},
        }

        res = await async_client.put(f"/api/v1/shares/{share.id}", json=payload, headers=auth_headers)

        assert res.status_code == 200
        data = res.json()
        assert data["name"] == "New Name"
        assert data["description"] == "New description"
        assert data["is_active"] is False
        assert data["search_config"] == {"top_k": 15}

    @pytest.mark.asyncio
    async def test_update_share_not_found(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
    ):
        """测试更新不存在的分享"""
        from uuid import uuid4

        fake_id = uuid4()

        payload = {
            "name": "New Name",
        }

        res = await async_client.put(f"/api/v1/shares/{fake_id}", json=payload, headers=auth_headers)

        assert res.status_code == 404

    @pytest.mark.asyncio
    async def test_update_share_not_owner(
        self,
        async_client: AsyncClient,
        auth_headers2: dict,
        db_session: AsyncSession,
        test_collection: Collection,
        test_user: User,
    ):
        """测试更新其他用户的分享"""
        share = CollectionShare(
            collection_id=test_collection.id,
            created_by=test_user.id,
            share_token="kb_share_test_123",
            name="Test Share",
            is_active=True,
        )
        db_session.add(share)
        await db_session.commit()
        await db_session.refresh(share)

        payload = {
            "name": "New Name",
        }

        # 使用第二个用户的认证头
        res = await async_client.put(f"/api/v1/shares/{share.id}", json=payload, headers=auth_headers2)

        assert res.status_code == 404  # 权限不足，返回404

    @pytest.mark.asyncio
    async def test_update_share_unauthorized(
        self,
        async_client: AsyncClient,
        db_session: AsyncSession,
        test_collection: Collection,
        test_user: User,
    ):
        """测试未认证"""
        share = CollectionShare(
            collection_id=test_collection.id,
            created_by=test_user.id,
            share_token="kb_share_test_123",
            name="Test Share",
            is_active=True,
        )
        db_session.add(share)
        await db_session.commit()
        await db_session.refresh(share)

        payload = {
            "name": "New Name",
        }

        res = await async_client.put(f"/api/v1/shares/{share.id}", json=payload)

        assert res.status_code == 401


class TestDeleteShare:
    """测试删除分享"""

    @pytest.mark.asyncio
    async def test_delete_share_success(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        db_session: AsyncSession,
        test_collection: Collection,
        test_user: User,
    ):
        """测试成功删除分享"""
        share = CollectionShare(
            collection_id=test_collection.id,
            created_by=test_user.id,
            share_token="kb_share_test_123",
            name="Test Share",
            is_active=True,
        )
        db_session.add(share)
        await db_session.commit()
        await db_session.refresh(share)
        share_id = share.id

        res = await async_client.delete(f"/api/v1/shares/{share.id}", headers=auth_headers)

        assert res.status_code == 204

        # 验证数据库
        result = await db_session.execute(select(CollectionShare).where(CollectionShare.id == share_id))
        deleted_share = result.scalar_one_or_none()
        assert deleted_share is None

    @pytest.mark.asyncio
    async def test_delete_share_not_found(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
    ):
        """测试删除不存在的分享"""
        from uuid import uuid4

        fake_id = uuid4()

        res = await async_client.delete(f"/api/v1/shares/{fake_id}", headers=auth_headers)

        assert res.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_share_not_owner(
        self,
        async_client: AsyncClient,
        auth_headers2: dict,
        db_session: AsyncSession,
        test_collection: Collection,
        test_user: User,
    ):
        """测试删除其他用户的分享"""
        share = CollectionShare(
            collection_id=test_collection.id,
            created_by=test_user.id,
            share_token="kb_share_test_123",
            name="Test Share",
            is_active=True,
        )
        db_session.add(share)
        await db_session.commit()
        await db_session.refresh(share)

        # 使用第二个用户的认证头
        res = await async_client.delete(f"/api/v1/shares/{share.id}", headers=auth_headers2)

        assert res.status_code == 404  # 权限不足，返回404

        # 验证分享仍然存在
        result = await db_session.execute(select(CollectionShare).where(CollectionShare.id == share.id))
        existing_share = result.scalar_one_or_none()
        assert existing_share is not None

    @pytest.mark.asyncio
    async def test_delete_share_unauthorized(
        self,
        async_client: AsyncClient,
        db_session: AsyncSession,
        test_collection: Collection,
        test_user: User,
    ):
        """测试未认证"""
        share = CollectionShare(
            collection_id=test_collection.id,
            created_by=test_user.id,
            share_token="kb_share_test_123",
            name="Test Share",
            is_active=True,
        )
        db_session.add(share)
        await db_session.commit()
        await db_session.refresh(share)

        res = await async_client.delete(f"/api/v1/shares/{share.id}")

        assert res.status_code == 401


class TestShareIntegration:
    """集成测试：完整的分享生命周期"""

    @pytest.mark.asyncio
    async def test_share_lifecycle(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        db_session: AsyncSession,
        test_collection: Collection,
    ):
        """测试完整的分享生命周期"""
        # 1. 创建分享
        create_payload = {
            "name": "Integration Test Share",
            "description": "Testing full lifecycle",
            "expires_in_days": 7,
            "search_config": {"top_k": 5},
        }

        create_res = await async_client.post(
            f"/api/v1/collections/{test_collection.id}/share", json=create_payload, headers=auth_headers
        )

        assert create_res.status_code == 201
        share_data = create_res.json()
        share_id = share_data["id"]

        # 2. 获取分享列表
        list_res = await async_client.get(f"/api/v1/collections/{test_collection.id}/shares", headers=auth_headers)

        assert list_res.status_code == 200
        list_data = list_res.json()
        assert list_data["total"] == 1
        assert list_data["items"][0]["id"] == share_id

        # 3. 获取分享详情
        get_res = await async_client.get(f"/api/v1/shares/{share_id}", headers=auth_headers)

        assert get_res.status_code == 200
        get_data = get_res.json()
        assert get_data["name"] == "Integration Test Share"

        # 4. 更新分享
        update_payload = {
            "name": "Updated Share Name",
            "is_active": False,
        }

        update_res = await async_client.put(f"/api/v1/shares/{share_id}", json=update_payload, headers=auth_headers)

        assert update_res.status_code == 200
        update_data = update_res.json()
        assert update_data["name"] == "Updated Share Name"
        assert update_data["is_active"] is False

        # 5. 删除分享
        delete_res = await async_client.delete(f"/api/v1/shares/{share_id}", headers=auth_headers)

        assert delete_res.status_code == 204

        # 6. 验证删除
        verify_res = await async_client.get(f"/api/v1/shares/{share_id}", headers=auth_headers)

        assert verify_res.status_code == 404

    @pytest.mark.asyncio
    async def test_multiple_shares_per_collection(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        test_collection: Collection,
    ):
        """测试一个知识库可以有多个分享"""
        # 创建3个分享
        for i in range(3):
            payload = {
                "name": f"Share {i}",
                "description": f"Description {i}",
            }

            res = await async_client.post(
                f"/api/v1/collections/{test_collection.id}/share", json=payload, headers=auth_headers
            )

            assert res.status_code == 201

        # 获取列表
        list_res = await async_client.get(f"/api/v1/collections/{test_collection.id}/shares", headers=auth_headers)

        assert list_res.status_code == 200
        list_data = list_res.json()
        assert list_data["total"] == 3
        assert len(list_data["items"]) == 3


