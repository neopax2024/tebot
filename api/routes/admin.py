"""
Admin API endpoints — protected by API_SECRET_KEY header.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.schemas import AdminStatsResponse
from config import settings
from database.engine import get_session
from database import operations as ops

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin", tags=["Admin"])


def verify_admin_key(x_admin_key: str = Header(...)) -> str:
    if x_admin_key != settings.API_SECRET_KEY:
        raise HTTPException(status_code=403, detail="Forbidden.")
    return x_admin_key


@router.get("/stats", response_model=AdminStatsResponse)
async def admin_stats(
    _: str = Depends(verify_admin_key),
    session: AsyncSession = Depends(get_session),
) -> AdminStatsResponse:
    return AdminStatsResponse(
        total_users=await ops.get_total_users(session),
        premium_users=await ops.get_premium_users(session),
        total_scans=await ops.get_total_scans(session),
        total_generations=await ops.get_total_generations(session),
    )


@router.post("/users/{user_id}/ban")
async def ban_user_api(
    user_id: int,
    _: str = Depends(verify_admin_key),
    session: AsyncSession = Depends(get_session),
) -> dict:
    await ops.ban_user(session, user_id, banned=True)
    return {"status": "banned", "user_id": user_id}


@router.post("/users/{user_id}/unban")
async def unban_user_api(
    user_id: int,
    _: str = Depends(verify_admin_key),
    session: AsyncSession = Depends(get_session),
) -> dict:
    await ops.ban_user(session, user_id, banned=False)
    return {"status": "unbanned", "user_id": user_id}


@router.post("/users/{user_id}/premium")
async def set_premium_api(
    user_id: int,
    is_premium: bool = True,
    _: str = Depends(verify_admin_key),
    session: AsyncSession = Depends(get_session),
) -> dict:
    await ops.set_user_premium(session, user_id, is_premium)
    return {"status": "updated", "user_id": user_id, "is_premium": is_premium}
