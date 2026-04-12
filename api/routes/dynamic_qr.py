"""
Dynamic QR redirect + CRUD endpoints.

GET  /r/{short_code}           — redirect (public, records analytics)
POST /api/dynamic              — create a new dynamic QR
PUT  /api/dynamic/{id}         — update destination URL
GET  /api/dynamic/user/{uid}   — list user's codes
GET  /api/dynamic/{id}/stats   — analytics for a code
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.schemas import (
    CreateDynamicQRRequest,
    DynamicQRResponse,
    UpdateDynamicQRRequest,
    AnalyticsResponse,
)
from config import settings
from database.engine import get_session
from database import operations as ops
from dynamic.manager import create_dynamic_qr
from dynamic.tracker import get_analytics, record_hit

logger = logging.getLogger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# Public redirect
# ---------------------------------------------------------------------------

@router.get("/r/{short_code}", include_in_schema=False)
async def redirect_short(
    short_code: str,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> Response:
    ip = request.client.host if request.client else None
    user_agent = request.headers.get("User-Agent")

    destination = await record_hit(
        session=session,
        short_code=short_code,
        ip_address=ip,
        user_agent=user_agent,
    )

    if destination is None:
        raise HTTPException(status_code=404, detail="QR code not found or expired.")

    return RedirectResponse(url=destination, status_code=302)


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------

@router.post("/api/dynamic", response_model=DynamicQRResponse, tags=["Dynamic QR"])
async def create_dynamic(
    body: CreateDynamicQRRequest,
    session: AsyncSession = Depends(get_session),
) -> DynamicQRResponse:
    expires_at = None
    if body.expires_in_days:
        expires_at = datetime.now(timezone.utc) + timedelta(days=body.expires_in_days)

    record, _ = await create_dynamic_qr(
        session=session,
        user_id=body.user_id,
        destination_url=body.destination_url,
        title=body.title,
        expires_at=expires_at,
        qr_options=body.options,
        check_limit=False,
    )

    return DynamicQRResponse(
        id=record.id,
        short_code=record.short_code,
        redirect_url=f"{settings.SHORT_URL_PREFIX}{record.short_code}",
        destination_url=record.destination_url,
        title=record.title,
        is_active=record.is_active,
        scan_count=record.scan_count,
        expires_at=record.expires_at,
        created_at=record.created_at,
    )


@router.put("/api/dynamic/{code_id}", tags=["Dynamic QR"])
async def update_dynamic(
    code_id: str,
    body: UpdateDynamicQRRequest,
    user_id: int,
    session: AsyncSession = Depends(get_session),
) -> dict:
    from dynamic.manager import update_destination

    success = await update_destination(session, code_id, user_id, body.new_url)
    if not success:
        raise HTTPException(status_code=404, detail="Code not found.")
    return {"status": "updated", "new_url": body.new_url}


@router.get("/api/dynamic/user/{user_id}", tags=["Dynamic QR"])
async def list_user_codes(
    user_id: int,
    session: AsyncSession = Depends(get_session),
) -> list[DynamicQRResponse]:
    codes = await ops.get_user_dynamic_codes(session, user_id)
    return [
        DynamicQRResponse(
            id=c.id,
            short_code=c.short_code,
            redirect_url=f"{settings.SHORT_URL_PREFIX}{c.short_code}",
            destination_url=c.destination_url,
            title=c.title,
            is_active=c.is_active,
            scan_count=c.scan_count,
            expires_at=c.expires_at,
            created_at=c.created_at,
        )
        for c in codes
    ]


@router.get("/api/dynamic/{code_id}/stats", response_model=AnalyticsResponse, tags=["Dynamic QR"])
async def code_stats(
    code_id: str,
    user_id: int,
    session: AsyncSession = Depends(get_session),
) -> AnalyticsResponse:
    analytics = await get_analytics(session, code_id, user_id)
    if analytics is None:
        raise HTTPException(status_code=404, detail="Code not found.")
    return AnalyticsResponse(**analytics)
