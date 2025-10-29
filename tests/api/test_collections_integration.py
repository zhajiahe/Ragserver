"""
知识库管理 API 集成测试
"""
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ragserver.main import app
from ragserver.app.dependencies import get_db
from ragserver.app.models import User, Collection
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


class TestCollectionsCRUD:
    """知识库 CRUD 测试"""

    @pytest.mark.asyncio
    async def test_create_collection_success(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        db_session: AsyncSession,
        test_user: User
    ):
        """测试成功创建知识库"""
        payload = {
            "name": "My First KB",
            "description": "Test knowledge base",
            "language": "zh",
            "settings": {"chunking": {"max_size": 500}}
        }
        
        res = await async_client.post(
            "/api/v1/collections",
            json=payload,
            headers=auth_headers
        )
        
        assert res.status_code == 201
        data = res.json()
        assert data["name"] == "My First KB"
        assert data["description"] == "Test knowledge base"
        assert data["status"] == "active"
        assert data["user_id"] == str(test_user.id)
        assert data["document_count"] == 0
        
        # 验证数据库
        result = await db_session.execute(
            select(Collection).where(Collection.name == "My First KB")
        )
        collection = result.scalar_one()
        assert collection.user_id == test_user.id

    @pytest.mark.asyncio
    async def test_create_collection_duplicate_name(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        db_session: AsyncSession,
        test_user: User
    ):
        """测试创建重复名称的知识库"""
        # 创建第一个
        payload1 = {"name": "Duplicate KB", "description": "First"}
        res1 = await async_client.post(
            "/api/v1/collections",
            json=payload1,
            headers=auth_headers
        )
        assert res1.status_code == 201
        
        # 尝试创建重复的
        payload2 = {"name": "Duplicate KB", "description": "Second"}
        res2 = await async_client.post(
            "/api/v1/collections",
            json=payload2,
            headers=auth_headers
        )
        assert res2.status_code == 400
        assert "已存在" in res2.json()["detail"]

    @pytest.mark.asyncio
    async def test_create_collection_without_auth(
        self,
        async_client: AsyncClient
    ):
        """测试未认证创建知识库"""
        payload = {"name": "Unauthorized KB"}
        res = await async_client.post("/api/v1/collections", json=payload)
        assert res.status_code == 401

    @pytest.mark.asyncio
    async def test_list_collections(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        db_session: AsyncSession,
        test_user: User
    ):
        """测试获取知识库列表"""
        # 创建多个知识库
        for i in range(3):
            collection = Collection(
                user_id=test_user.id,
                name=f"KB {i}",
                description=f"Description {i}",
                status="active"
            )
            db_session.add(collection)
        await db_session.commit()
        
        # 获取列表
        res = await async_client.get("/api/v1/collections", headers=auth_headers)
        assert res.status_code == 200
        data = res.json()
        assert data["total"] == 3
        assert len(data["items"]) == 3
        assert all(item["user_id"] == str(test_user.id) for item in data["items"])

    @pytest.mark.asyncio
    async def test_list_collections_with_status_filter(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        db_session: AsyncSession,
        test_user: User
    ):
        """测试按状态筛选知识库列表"""
        # 创建不同状态的知识库
        active_kb = Collection(
            user_id=test_user.id,
            name="Active KB",
            status="active"
        )
        archived_kb = Collection(
            user_id=test_user.id,
            name="Archived KB",
            status="archived"
        )
        db_session.add_all([active_kb, archived_kb])
        await db_session.commit()
        
        # 筛选 active
        res = await async_client.get(
            "/api/v1/collections?status=active",
            headers=auth_headers
        )
        assert res.status_code == 200
        data = res.json()
        assert data["total"] == 1
        assert data["items"][0]["status"] == "active"

    @pytest.mark.asyncio
    async def test_get_collection_by_id(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        db_session: AsyncSession,
        test_user: User
    ):
        """测试获取知识库详情"""
        # 创建知识库
        collection = Collection(
            user_id=test_user.id,
            name="Test KB",
            description="Test description",
            status="active"
        )
        db_session.add(collection)
        await db_session.commit()
        await db_session.refresh(collection)
        
        # 获取详情
        res = await async_client.get(
            f"/api/v1/collections/{collection.id}",
            headers=auth_headers
        )
        assert res.status_code == 200
        data = res.json()
        assert data["id"] == str(collection.id)
        assert data["name"] == "Test KB"

    @pytest.mark.asyncio
    async def test_get_collection_not_found(
        self,
        async_client: AsyncClient,
        auth_headers: dict
    ):
        """测试获取不存在的知识库"""
        import uuid
        fake_id = uuid.uuid4()
        res = await async_client.get(
            f"/api/v1/collections/{fake_id}",
            headers=auth_headers
        )
        assert res.status_code == 404

    @pytest.mark.asyncio
    async def test_update_collection(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        db_session: AsyncSession,
        test_user: User
    ):
        """测试更新知识库"""
        # 创建知识库
        collection = Collection(
            user_id=test_user.id,
            name="Original Name",
            description="Original description",
            status="active"
        )
        db_session.add(collection)
        await db_session.commit()
        await db_session.refresh(collection)
        
        # 更新
        update_payload = {
            "name": "Updated Name",
            "description": "Updated description"
        }
        res = await async_client.put(
            f"/api/v1/collections/{collection.id}",
            json=update_payload,
            headers=auth_headers
        )
        assert res.status_code == 200
        data = res.json()
        assert data["name"] == "Updated Name"
        assert data["description"] == "Updated description"
        
        # 验证数据库
        await db_session.refresh(collection)
        assert collection.name == "Updated Name"

    @pytest.mark.asyncio
    async def test_update_archived_collection(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        db_session: AsyncSession,
        test_user: User
    ):
        """测试更新已归档的知识库（应失败）"""
        # 创建归档知识库
        collection = Collection(
            user_id=test_user.id,
            name="Archived KB",
            status="archived"
        )
        db_session.add(collection)
        await db_session.commit()
        await db_session.refresh(collection)
        
        # 尝试更新
        update_payload = {"name": "New Name"}
        res = await async_client.put(
            f"/api/v1/collections/{collection.id}",
            json=update_payload,
            headers=auth_headers
        )
        assert res.status_code == 400
        assert "归档" in res.json()["detail"]

    @pytest.mark.asyncio
    async def test_delete_collection(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        db_session: AsyncSession,
        test_user: User
    ):
        """测试删除知识库"""
        # 创建知识库
        collection = Collection(
            user_id=test_user.id,
            name="To Delete",
            status="active"
        )
        db_session.add(collection)
        await db_session.commit()
        await db_session.refresh(collection)
        collection_id = collection.id
        
        # 删除
        res = await async_client.delete(
            f"/api/v1/collections/{collection_id}",
            headers=auth_headers
        )
        assert res.status_code == 204
        
        # 验证数据库
        result = await db_session.execute(
            select(Collection).where(Collection.id == collection_id)
        )
        assert result.scalar_one_or_none() is None

    @pytest.mark.asyncio
    async def test_delete_archived_collection(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        db_session: AsyncSession,
        test_user: User
    ):
        """测试删除已归档的知识库（应失败）"""
        # 创建归档知识库
        collection = Collection(
            user_id=test_user.id,
            name="Archived KB",
            status="archived"
        )
        db_session.add(collection)
        await db_session.commit()
        await db_session.refresh(collection)
        
        # 尝试删除
        res = await async_client.delete(
            f"/api/v1/collections/{collection.id}",
            headers=auth_headers
        )
        assert res.status_code == 400
        assert "归档" in res.json()["detail"]

    @pytest.mark.asyncio
    async def test_archive_collection(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        db_session: AsyncSession,
        test_user: User
    ):
        """测试归档知识库"""
        # 创建知识库
        collection = Collection(
            user_id=test_user.id,
            name="To Archive",
            status="active"
        )
        db_session.add(collection)
        await db_session.commit()
        await db_session.refresh(collection)
        
        # 归档
        res = await async_client.post(
            f"/api/v1/collections/{collection.id}/archive",
            headers=auth_headers
        )
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "archived"
        
        # 验证数据库
        await db_session.refresh(collection)
        assert collection.status == "archived"

    @pytest.mark.asyncio
    async def test_archive_already_archived_collection(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        db_session: AsyncSession,
        test_user: User
    ):
        """测试归档已归档的知识库（应失败）"""
        # 创建归档知识库
        collection = Collection(
            user_id=test_user.id,
            name="Already Archived",
            status="archived"
        )
        db_session.add(collection)
        await db_session.commit()
        await db_session.refresh(collection)
        
        # 尝试再次归档
        res = await async_client.post(
            f"/api/v1/collections/{collection.id}/archive",
            headers=auth_headers
        )
        assert res.status_code == 400
        assert "已经是归档状态" in res.json()["detail"]


class TestCollectionPermissions:
    """知识库权限测试"""

    @pytest.mark.asyncio
    async def test_cannot_access_other_user_collection(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        db_session: AsyncSession
    ):
        """测试无法访问其他用户的知识库"""
        # 创建另一个用户
        other_user = User(
            username="otheruser",
            email="other@example.com",
            hashed_password=get_password_hash("Other1234!"),
            is_active=True,
        )
        db_session.add(other_user)
        await db_session.commit()
        await db_session.refresh(other_user)
        
        # 创建其他用户的知识库
        other_collection = Collection(
            user_id=other_user.id,
            name="Other User KB",
            status="active"
        )
        db_session.add(other_collection)
        await db_session.commit()
        await db_session.refresh(other_collection)
        
        # 尝试访问（使用 testuser 的 token）
        res = await async_client.get(
            f"/api/v1/collections/{other_collection.id}",
            headers=auth_headers
        )
        assert res.status_code == 404  # 应该返回 404 而不是 403，避免泄露信息


class TestCollectionPagination:
    """知识库分页测试"""

    @pytest.mark.asyncio
    async def test_pagination(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        db_session: AsyncSession,
        test_user: User
    ):
        """测试分页功能"""
        # 创建 10 个知识库
        for i in range(10):
            collection = Collection(
                user_id=test_user.id,
                name=f"KB {i:02d}",
                status="active"
            )
            db_session.add(collection)
        await db_session.commit()
        
        # 第一页
        res1 = await async_client.get(
            "/api/v1/collections?skip=0&limit=5",
            headers=auth_headers
        )
        assert res1.status_code == 200
        data1 = res1.json()
        assert data1["total"] == 10
        assert len(data1["items"]) == 5
        
        # 第二页
        res2 = await async_client.get(
            "/api/v1/collections?skip=5&limit=5",
            headers=auth_headers
        )
        assert res2.status_code == 200
        data2 = res2.json()
        assert data2["total"] == 10
        assert len(data2["items"]) == 5
        
        # 确保不重复
        ids1 = {item["id"] for item in data1["items"]}
        ids2 = {item["id"] for item in data2["items"]}
        assert len(ids1 & ids2) == 0  # 没有交集

