"""
用户认证 API 集成测试
"""
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ragserver.main import app
from ragserver.app.dependencies import get_db
from ragserver.app.models import User, Base
from ragserver.app.dependencies.security import get_password_hash


@pytest.fixture
async def setup_db(db_session: AsyncSession):
    """设置数据库依赖注入"""
    # 覆盖依赖注入
    async def override_get_db():
        yield db_session
    
    app.dependency_overrides[get_db] = override_get_db
    yield
    
    # 清理
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


class TestRegister:
    """用户注册测试"""

    @pytest.mark.asyncio
    async def test_register_success(self, async_client: AsyncClient, db_session: AsyncSession, setup_db):
        """测试成功注册"""
        payload = {
            "username": "newuser",
            "email": "newuser@example.com",
            "password": "Password123!",
            "full_name": "New User",
        }
        
        # 1. 注册新用户
        res = await async_client.post("/api/v1/auth/register", json=payload)
        assert res.status_code == 201
        
        data = res.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert data["expires_in"] == 60 * 60 * 24
        
        # 2. 验证数据库写入
        result = await db_session.execute(
            select(User).where(User.username == "newuser")
        )
        user = result.scalar_one()
        assert user.email == "newuser@example.com"
        assert user.full_name == "New User"
        assert user.is_active is True

    @pytest.mark.asyncio
    async def test_register_duplicate_username(self, async_client: AsyncClient, db_session: AsyncSession, test_user: User):
        """测试用户名重复"""
        payload = {
            "username": "testuser",  # 已存在
            "email": "another@example.com",
            "password": "Password123!",
        }
        
        res = await async_client.post("/api/v1/auth/register", json=payload)
        
        assert res.status_code == 400
        assert "用户名或邮箱已存在" in res.json()["detail"]

    @pytest.mark.asyncio
    async def test_register_duplicate_email(self, async_client: AsyncClient, db_session: AsyncSession, test_user: User):
        """测试邮箱重复"""
        payload = {
            "username": "anotheruser",
            "email": "test@example.com",  # 已存在
            "password": "Password123!",
        }
        
        res = await async_client.post("/api/v1/auth/register", json=payload)
        
        assert res.status_code == 400
        assert "用户名或邮箱已存在" in res.json()["detail"]

    @pytest.mark.asyncio
    async def test_register_invalid_username(self, async_client: AsyncClient, setup_db):
        """测试无效用户名（太短）"""
        payload = {
            "username": "ab",  # 少于3个字符
            "email": "test@example.com",
            "password": "Password123!",
        }
        
        res = await async_client.post("/api/v1/auth/register", json=payload)
        
        assert res.status_code == 422  # Validation error

    @pytest.mark.asyncio
    async def test_register_invalid_password(self, async_client: AsyncClient, setup_db):
        """测试无效密码（太短）"""
        payload = {
            "username": "newuser",
            "email": "test@example.com",
            "password": "short",  # 少于8个字符
        }
        
        res = await async_client.post("/api/v1/auth/register", json=payload)
        
        assert res.status_code == 422

    @pytest.mark.asyncio
    async def test_register_invalid_email(self, async_client: AsyncClient, setup_db):
        """测试无效邮箱格式"""
        payload = {
            "username": "newuser",
            "email": "not-an-email",
            "password": "Password123!",
        }
        
        res = await async_client.post("/api/v1/auth/register", json=payload)
        
        assert res.status_code == 422


class TestLogin:
    """用户登录测试"""

    @pytest.mark.asyncio
    async def test_login_with_username_success(self, async_client: AsyncClient, test_user: User):
        """测试使用用户名登录成功"""
        payload = {
            "username_or_email": "testuser",
            "password": "Test1234!",
        }
        
        res = await async_client.post("/api/v1/auth/login", json=payload)
        
        assert res.status_code == 200
        data = res.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert data["expires_in"] == 1440 * 60

    @pytest.mark.asyncio
    async def test_login_with_email_success(self, async_client: AsyncClient, test_user: User):
        """测试使用邮箱登录成功"""
        payload = {
            "username_or_email": "test@example.com",
            "password": "Test1234!",
        }
        
        res = await async_client.post("/api/v1/auth/login", json=payload)
        
        assert res.status_code == 200
        data = res.json()
        assert "access_token" in data

    @pytest.mark.asyncio
    async def test_login_wrong_password(self, async_client: AsyncClient, test_user: User):
        """测试密码错误"""
        payload = {
            "username_or_email": "testuser",
            "password": "WrongPassword!",
        }
        
        res = await async_client.post("/api/v1/auth/login", json=payload)
        
        assert res.status_code == 400
        assert "用户名或密码错误" in res.json()["detail"]

    @pytest.mark.asyncio
    async def test_login_nonexistent_user(self, async_client: AsyncClient, setup_db):
        """测试不存在的用户"""
        payload = {
            "username_or_email": "nonexistent",
            "password": "Password123!",
        }
        
        res = await async_client.post("/api/v1/auth/login", json=payload)
        
        assert res.status_code == 400
        assert "用户名或密码错误" in res.json()["detail"]

    @pytest.mark.asyncio
    async def test_login_inactive_user(self, async_client: AsyncClient, db_session: AsyncSession, setup_db):
        """测试未激活用户"""
        inactive_user = User(
            username="inactive",
            email="inactive@example.com",
            hashed_password=get_password_hash("Test1234!"),
            is_active=False,
        )
        db_session.add(inactive_user)
        await db_session.commit()
        
        payload = {
            "username_or_email": "inactive",
            "password": "Test1234!",
        }
        
        res = await async_client.post("/api/v1/auth/login", json=payload)
        
        assert res.status_code == 400
        assert "用户未激活" in res.json()["detail"]


class TestChangePassword:
    """修改密码测试"""

    @pytest.mark.asyncio
    async def test_change_password_success(self, async_client: AsyncClient, db_session: AsyncSession, test_user: User):
        """测试成功修改密码"""
        # 1. 先登录获取 token
        login_payload = {
            "username_or_email": "testuser",
            "password": "Test1234!",
        }
        login_res = await async_client.post("/api/v1/auth/login", json=login_payload)
        token = login_res.json()["access_token"]
        
        # 2. 修改密码
        change_payload = {
            "old_password": "Test1234!",
            "new_password": "NewPassword123!",
        }
        headers = {"Authorization": f"Bearer {token}"}
        res = await async_client.post(
            "/api/v1/auth/change-password",
            json=change_payload,
            headers=headers
        )
        
        assert res.status_code == 204
        
        # 3. 验证数据库中密码已更新
        await db_session.refresh(test_user)
        from ragserver.app.dependencies.security import verify_password
        assert verify_password("NewPassword123!", test_user.hashed_password)
        
        # 4. 验证新密码可以登录
        new_login_payload = {
            "username_or_email": "testuser",
            "password": "NewPassword123!",
        }
        new_login_res = await async_client.post("/api/v1/auth/login", json=new_login_payload)
        assert new_login_res.status_code == 200

    @pytest.mark.asyncio
    async def test_change_password_wrong_old_password(self, async_client: AsyncClient, test_user: User):
        """测试原密码错误"""
        # 1. 先登录
        login_payload = {
            "username_or_email": "testuser",
            "password": "Test1234!",
        }
        login_res = await async_client.post("/api/v1/auth/login", json=login_payload)
        token = login_res.json()["access_token"]
        
        # 2. 使用错误的原密码
        change_payload = {
            "old_password": "WrongOldPassword!",
            "new_password": "NewPassword123!",
        }
        headers = {"Authorization": f"Bearer {token}"}
        res = await async_client.post(
            "/api/v1/auth/change-password",
            json=change_payload,
            headers=headers
        )
        
        assert res.status_code == 400
        assert "原密码不正确" in res.json()["detail"]

    @pytest.mark.asyncio
    async def test_change_password_without_auth(self, async_client: AsyncClient, setup_db):
        """测试未认证修改密码"""
        change_payload = {
            "old_password": "Test1234!",
            "new_password": "NewPassword123!",
        }
        
        res = await async_client.post("/api/v1/auth/change-password", json=change_payload)
        
        assert res.status_code == 401  # Unauthorized

    @pytest.mark.asyncio
    async def test_change_password_invalid_new_password(self, async_client: AsyncClient, test_user: User):
        """测试新密码格式无效"""
        # 1. 先登录
        login_payload = {
            "username_or_email": "testuser",
            "password": "Test1234!",
        }
        login_res = await async_client.post("/api/v1/auth/login", json=login_payload)
        token = login_res.json()["access_token"]
        
        # 2. 新密码太短
        change_payload = {
            "old_password": "Test1234!",
            "new_password": "short",
        }
        headers = {"Authorization": f"Bearer {token}"}
        res = await async_client.post(
            "/api/v1/auth/change-password",
            json=change_payload,
            headers=headers
        )
        
        assert res.status_code == 422


class TestAuthIntegration:
    """完整认证流程集成测试"""

    @pytest.mark.asyncio
    async def test_full_auth_flow(self, async_client: AsyncClient, db_session: AsyncSession, setup_db):
        """测试完整的注册-登录-修改密码流程"""
        # 1. 注册新用户
        register_payload = {
            "username": "flowuser",
            "email": "flow@example.com",
            "password": "InitialPass123!",
            "full_name": "Flow User",
        }
        register_res = await async_client.post("/api/v1/auth/register", json=register_payload)
        assert register_res.status_code == 201
        register_token = register_res.json()["access_token"]
        
        # 2. 验证用户已创建
        result = await db_session.execute(
            select(User).where(User.username == "flowuser")
        )
        user = result.scalar_one()
        assert user.email == "flow@example.com"
        assert user.full_name == "Flow User"
        
        # 3. 使用注册返回的 token 修改密码
        change_payload = {
            "old_password": "InitialPass123!",
            "new_password": "NewPass456!",
        }
        headers = {"Authorization": f"Bearer {register_token}"}
        change_res = await async_client.post(
            "/api/v1/auth/change-password",
            json=change_payload,
            headers=headers
        )
        assert change_res.status_code == 204
        
        # 4. 验证密码已更新
        await db_session.refresh(user)
        from ragserver.app.dependencies.security import verify_password
        assert verify_password("NewPass456!", user.hashed_password)
        
        # 5. 使用新密码登录
        login_payload = {
            "username_or_email": "flowuser",
            "password": "NewPass456!",
        }
        login_res = await async_client.post("/api/v1/auth/login", json=login_payload)
        assert login_res.status_code == 200
        assert "access_token" in login_res.json()
        
        # 6. 验证旧密码不能登录
        old_login_payload = {
            "username_or_email": "flowuser",
            "password": "InitialPass123!",
        }
        old_login_res = await async_client.post("/api/v1/auth/login", json=old_login_payload)
        assert old_login_res.status_code == 400

    @pytest.mark.asyncio
    async def test_register_and_immediate_login(self, async_client: AsyncClient, db_session: AsyncSession, setup_db):
        """测试注册后立即登录"""
        # 1. 注册
        register_payload = {
            "username": "quickuser",
            "email": "quick@example.com",
            "password": "QuickPass123!",
        }
        register_res = await async_client.post("/api/v1/auth/register", json=register_payload)
        assert register_res.status_code == 201
        
        # 2. 验证数据库中用户存在
        result = await db_session.execute(
            select(User).where(User.username == "quickuser")
        )
        user = result.scalar_one()
        assert user is not None
        
        # 3. 立即使用相同凭证登录
        login_payload = {
            "username_or_email": "quickuser",
            "password": "QuickPass123!",
        }
        login_res = await async_client.post("/api/v1/auth/login", json=login_payload)
        assert login_res.status_code == 200
        
        # 4. 验证两个 token 都有效（都能用来修改密码）
        register_token = register_res.json()["access_token"]
        login_token = login_res.json()["access_token"]
        
        change_payload = {
            "old_password": "QuickPass123!",
            "new_password": "NewQuickPass456!",
        }
        
        # 使用注册 token
        headers = {"Authorization": f"Bearer {register_token}"}
        res = await async_client.post(
            "/api/v1/auth/change-password",
            json=change_payload,
            headers=headers
        )
        assert res.status_code == 204