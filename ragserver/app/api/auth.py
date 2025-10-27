from __future__ import annotations

from datetime import timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ragserver.app.dependencies import get_db
from ragserver.app.dependencies.security import (
    get_password_hash,
    verify_password,
    create_access_token,
    get_current_active_user,
)
from ragserver.app.models import User


router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: Optional[str] = Field(default=None, max_length=100)
    avatar_url: Optional[str] = Field(default=None, max_length=500)


@router.post("/register", response_model=TokenResponse, status_code=201)
async def register(req: RegisterRequest, db: AsyncSession = Depends(get_db)):
    # 唯一性检查
    result = await db.execute(
        select(User).where((User.username == req.username) | (User.email == req.email))
    )
    exists = result.scalar_one_or_none()
    if exists:
        raise HTTPException(status_code=400, detail="用户名或邮箱已存在")

    user = User(
        username=req.username,
        email=req.email,
        hashed_password=get_password_hash(req.password),
        full_name=req.full_name,
        avatar_url=req.avatar_url,
        is_active=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    access_token = create_access_token(str(user.id))
    return TokenResponse(access_token=access_token, expires_in=60 * 60 * 24)


class LoginRequest(BaseModel):
    username_or_email: str
    password: str


@router.post("/login", response_model=TokenResponse)
async def login(req: LoginRequest, db: AsyncSession = Depends(get_db)):
    q = select(User).where((User.username == req.username_or_email) | (User.email == req.username_or_email))
    result = await db.execute(q)
    user = result.scalar_one_or_none()
    if not user or not verify_password(req.password, user.hashed_password):
        raise HTTPException(status_code=400, detail="用户名或密码错误")
    if not user.is_active:
        raise HTTPException(status_code=400, detail="用户未激活")

    expires = timedelta(minutes=1440)
    access_token = create_access_token(str(user.id), expires)
    return TokenResponse(access_token=access_token, expires_in=int(expires.total_seconds()))


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str = Field(min_length=8, max_length=128)


@router.post("/change-password", status_code=204)
async def change_password(
    req: ChangePasswordRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    if not verify_password(req.old_password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="原密码不正确")
    current_user.hashed_password = get_password_hash(req.new_password)
    await db.commit()
    return None


