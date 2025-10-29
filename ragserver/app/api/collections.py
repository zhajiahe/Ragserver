"""
知识库管理 API
"""
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from ragserver.app.dependencies import get_db, get_current_active_user
from ragserver.app.models import Collection, User
from ragserver.config import settings

router = APIRouter(prefix="/api/v1/collections", tags=["知识库管理"])


# ==================== Pydantic Schemas ====================

class CollectionBase(BaseModel):
    """知识库基础模型"""
    name: str = Field(..., min_length=1, max_length=100, description="知识库名称")
    description: Optional[str] = Field(None, max_length=500, description="知识库描述")
    icon_url: Optional[str] = Field(None, max_length=500, description="图标URL")
    language: str = Field(default="zh", max_length=20, description="语言")
    settings: Optional[dict] = Field(default_factory=dict, description="知识库配置")


class CollectionCreate(CollectionBase):
    """创建知识库请求"""
    pass


class CollectionUpdate(BaseModel):
    """更新知识库请求"""
    name: Optional[str] = Field(None, min_length=1, max_length=100, description="知识库名称")
    description: Optional[str] = Field(None, max_length=500, description="知识库描述")
    icon_url: Optional[str] = Field(None, max_length=500, description="图标URL")
    language: Optional[str] = Field(None, max_length=20, description="语言")
    settings: Optional[dict] = Field(None, description="知识库配置")


class CollectionResponse(CollectionBase):
    """知识库响应模型"""
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    user_id: UUID
    status: str
    document_count: int
    total_size_bytes: int
    chunk_count: int
    created_at: str
    updated_at: str
    last_updated_at: Optional[str]


class CollectionListResponse(BaseModel):
    """知识库列表响应"""
    total: int
    items: List[CollectionResponse]


# ==================== API Endpoints ====================

@router.get("", response_model=CollectionListResponse)
async def list_collections(
    status: Optional[str] = Query(None, description="状态筛选: active/archived"),
    skip: int = Query(0, ge=0, description="跳过记录数"),
    limit: int = Query(50, ge=1, le=100, description="返回记录数"),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """获取知识库列表
    
    - 支持分页
    - 支持按状态筛选
    - 只返回当前用户的知识库
    """
    # 构建查询
    query = select(Collection).where(Collection.user_id == current_user.id)
    
    # 状态筛选
    if status:
        query = query.where(Collection.status == status)
    
    # 获取总数
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar()
    
    # 分页查询
    query = query.order_by(Collection.created_at.desc()).offset(skip).limit(limit)
    result = await db.execute(query)
    collections = result.scalars().all()
    
    # 转换为响应格式
    items = [
        CollectionResponse(
            id=c.id,
            user_id=c.user_id,
            name=c.name,
            description=c.description,
            icon_url=c.icon_url,
            language=c.language,
            settings=c.settings,
            status=c.status,
            document_count=c.document_count,
            total_size_bytes=c.total_size_bytes,
            chunk_count=c.chunk_count,
            created_at=c.created_at.isoformat(),
            updated_at=c.updated_at.isoformat(),
            last_updated_at=c.last_updated_at.isoformat() if c.last_updated_at else None,
        )
        for c in collections
    ]
    
    return CollectionListResponse(total=total, items=items)


@router.post("", response_model=CollectionResponse, status_code=status.HTTP_201_CREATED)
async def create_collection(
    req: CollectionCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """创建知识库
    
    - 检查知识库数量限制
    - 自动设置为 active 状态
    """
    # 检查用户知识库数量限制
    count_query = select(func.count()).select_from(Collection).where(
        Collection.user_id == current_user.id
    )
    count_result = await db.execute(count_query)
    collection_count = count_result.scalar()
    
    if collection_count >= settings.max_collections_per_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"已达到知识库数量上限 ({settings.max_collections_per_user})"
        )
    
    # 检查知识库名称是否重复（同一用户下）
    existing_query = select(Collection).where(
        Collection.user_id == current_user.id,
        Collection.name == req.name
    )
    existing_result = await db.execute(existing_query)
    if existing_result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="知识库名称已存在"
        )
    
    # 创建知识库
    collection = Collection(
        user_id=current_user.id,
        name=req.name,
        description=req.description,
        icon_url=req.icon_url,
        language=req.language,
        settings=req.settings or {},
        status="active",
    )
    
    db.add(collection)
    await db.commit()
    await db.refresh(collection)
    
    return CollectionResponse(
        id=collection.id,
        user_id=collection.user_id,
        name=collection.name,
        description=collection.description,
        icon_url=collection.icon_url,
        language=collection.language,
        settings=collection.settings,
        status=collection.status,
        document_count=collection.document_count,
        total_size_bytes=collection.total_size_bytes,
        chunk_count=collection.chunk_count,
        created_at=collection.created_at.isoformat(),
        updated_at=collection.updated_at.isoformat(),
        last_updated_at=collection.last_updated_at.isoformat() if collection.last_updated_at else None,
    )


@router.get("/{collection_id}", response_model=CollectionResponse)
async def get_collection(
    collection_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """获取知识库详情
    
    - 只能查看自己的知识库
    """
    query = select(Collection).where(
        Collection.id == collection_id,
        Collection.user_id == current_user.id
    )
    result = await db.execute(query)
    collection = result.scalar_one_or_none()
    
    if not collection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="知识库不存在"
        )
    
    return CollectionResponse(
        id=collection.id,
        user_id=collection.user_id,
        name=collection.name,
        description=collection.description,
        icon_url=collection.icon_url,
        language=collection.language,
        settings=collection.settings,
        status=collection.status,
        document_count=collection.document_count,
        total_size_bytes=collection.total_size_bytes,
        chunk_count=collection.chunk_count,
        created_at=collection.created_at.isoformat(),
        updated_at=collection.updated_at.isoformat(),
        last_updated_at=collection.last_updated_at.isoformat() if collection.last_updated_at else None,
    )


@router.put("/{collection_id}", response_model=CollectionResponse)
async def update_collection(
    collection_id: UUID,
    req: CollectionUpdate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """更新知识库
    
    - 只能更新自己的知识库
    - 只更新提供的字段
    """
    # 查询知识库
    query = select(Collection).where(
        Collection.id == collection_id,
        Collection.user_id == current_user.id
    )
    result = await db.execute(query)
    collection = result.scalar_one_or_none()
    
    if not collection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="知识库不存在"
        )
    
    # 检查状态
    if collection.status == "archived":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="无法更新已归档的知识库"
        )
    
    # 如果更新名称，检查是否重复
    if req.name and req.name != collection.name:
        existing_query = select(Collection).where(
            Collection.user_id == current_user.id,
            Collection.name == req.name,
            Collection.id != collection_id
        )
        existing_result = await db.execute(existing_query)
        if existing_result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="知识库名称已存在"
            )
    
    # 更新字段
    update_data = req.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(collection, field, value)
    
    await db.commit()
    await db.refresh(collection)
    
    return CollectionResponse(
        id=collection.id,
        user_id=collection.user_id,
        name=collection.name,
        description=collection.description,
        icon_url=collection.icon_url,
        language=collection.language,
        settings=collection.settings,
        status=collection.status,
        document_count=collection.document_count,
        total_size_bytes=collection.total_size_bytes,
        chunk_count=collection.chunk_count,
        created_at=collection.created_at.isoformat(),
        updated_at=collection.updated_at.isoformat(),
        last_updated_at=collection.last_updated_at.isoformat() if collection.last_updated_at else None,
    )


@router.delete("/{collection_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_collection(
    collection_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """删除知识库
    
    - 只能删除自己的知识库
    - 不能删除已归档的知识库
    - 会级联删除所有文档和分块
    """
    # 查询知识库
    query = select(Collection).where(
        Collection.id == collection_id,
        Collection.user_id == current_user.id
    )
    result = await db.execute(query)
    collection = result.scalar_one_or_none()
    
    if not collection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="知识库不存在"
        )
    
    # 检查状态
    if collection.status == "archived":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="无法删除已归档的知识库，请先取消归档"
        )
    
    # 删除知识库（会级联删除相关数据）
    await db.delete(collection)
    await db.commit()
    
    return None


@router.post("/{collection_id}/archive", response_model=CollectionResponse)
async def archive_collection(
    collection_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """归档知识库
    
    - 只能归档自己的知识库
    - 归档后无法更新和删除，但可以查看
    """
    # 查询知识库
    query = select(Collection).where(
        Collection.id == collection_id,
        Collection.user_id == current_user.id
    )
    result = await db.execute(query)
    collection = result.scalar_one_or_none()
    
    if not collection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="知识库不存在"
        )
    
    # 检查状态
    if collection.status == "archived":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="知识库已经是归档状态"
        )
    
    # 归档
    collection.status = "archived"
    await db.commit()
    await db.refresh(collection)
    
    return CollectionResponse(
        id=collection.id,
        user_id=collection.user_id,
        name=collection.name,
        description=collection.description,
        icon_url=collection.icon_url,
        language=collection.language,
        settings=collection.settings,
        status=collection.status,
        document_count=collection.document_count,
        total_size_bytes=collection.total_size_bytes,
        chunk_count=collection.chunk_count,
        created_at=collection.created_at.isoformat(),
        updated_at=collection.updated_at.isoformat(),
        last_updated_at=collection.last_updated_at.isoformat() if collection.last_updated_at else None,
    )

