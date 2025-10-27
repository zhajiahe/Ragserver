"""
FastAPI 依赖：数据库会话、配置、用户认证与 API Key 校验。
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timedelta, timezone
from typing import AsyncGenerator, Optional, Set, Callable

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ragserver.config import settings
from ragserver.database import async_session_factory
from ragserver.app.models import User, APIKey


# ==================== 通用依赖 ====================


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        yield session


def get_settings():  # noqa: ANN201 - 简单返回配置对象
    return settings


# ==================== 密码哈希 ====================


password_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def get_password_hash(password: str) -> str:
    return password_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return password_context.verify(plain_password, hashed_password)


# ==================== JWT 认证 ====================


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


def create_access_token(subject: str, expires_delta: Optional[timedelta] = None) -> str:
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.jwt_access_token_expire_minutes)
    )
    to_encode = {"sub": subject, "exp": expire}
    encoded_jwt = jwt.encode(to_encode, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    return encoded_jwt


async def get_current_user(
    db: AsyncSession = Depends(get_db), token: str = Depends(oauth2_scheme)
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="无法验证凭证",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        subject: str | None = payload.get("sub")
        if subject is None:
            raise credentials_exception
        try:
            user_id = uuid.UUID(subject)
        except Exception:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise credentials_exception
    return user


async def get_current_active_user(current_user: User = Depends(get_current_user)) -> User:
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="用户未激活")
    return current_user


async def get_current_superuser(current_user: User = Depends(get_current_active_user)) -> User:
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="需要管理员权限")
    return current_user


# ==================== API Key 校验 ====================


def api_key_dependency(required_scopes: Optional[Set[str]] = None) -> Callable:
    required_scopes = required_scopes or set()

    async def _dep(
        x_api_key: Optional[str] = Header(default=None, alias="X-API-Key"),
        db: AsyncSession = Depends(get_db),
    ) -> APIKey:
        if not x_api_key:
            raise HTTPException(status_code=401, detail="缺少 API Key")

        key_hash = hashlib.sha256(x_api_key.encode("utf-8")).hexdigest()
        result = await db.execute(
            select(APIKey).where(
                APIKey.key_hash == key_hash,
                APIKey.is_active == True,  # noqa: E712
            )
        )
        api_key = result.scalar_one_or_none()
        if api_key is None:
            raise HTTPException(status_code=401, detail="无效的 API Key")

        if api_key.expires_at and api_key.expires_at < datetime.utcnow():
            raise HTTPException(status_code=401, detail="API Key 已过期")

        if required_scopes:
            key_scopes = set(api_key.scopes or [])
            missing = required_scopes - key_scopes
            if missing:
                raise HTTPException(status_code=403, detail=f"缺少权限: {sorted(missing)}")

        return api_key

    return _dep


