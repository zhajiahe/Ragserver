from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Optional, Set, Callable
from ragserver.app.utils.date_util import get_current_time

from fastapi import Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ragserver.app.models import APIKey
from .db import get_db


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

        if api_key.expires_at and api_key.expires_at < get_current_time():
            raise HTTPException(status_code=401, detail="API Key 已过期")

        if required_scopes:
            key_scopes = set(api_key.scopes or [])
            missing = required_scopes - key_scopes
            if missing:
                raise HTTPException(status_code=403, detail=f"缺少权限: {sorted(missing)}")

        return api_key

    return _dep


