"""
Dynamic code scan event tracker.

Records every redirect hit and provides analytics summaries.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import DynamicCode, DynamicScanEvent
from database import operations as ops


# Simple user-agent → device heuristic
_MOBILE_RE = re.compile(
    r"(android|iphone|ipad|ipod|blackberry|windows phone|mobile)", re.IGNORECASE
)
_TABLET_RE = re.compile(r"(ipad|tablet)", re.IGNORECASE)


def _detect_device(user_agent: Optional[str]) -> str:
    if not user_agent:
        return "unknown"
    if _TABLET_RE.search(user_agent):
        return "tablet"
    if _MOBILE_RE.search(user_agent):
        return "mobile"
    return "desktop"


async def record_hit(
    session: AsyncSession,
    short_code: str,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    country: Optional[str] = None,
) -> Optional[str]:
    """
    Record a redirect hit.

    Returns the destination URL (or None if the code is expired / inactive).
    """
    record = await ops.get_dynamic_code_by_short(session, short_code)
    if record is None or not record.is_active:
        return None

    # Check expiry
    if record.expires_at and record.expires_at < datetime.now(timezone.utc):
        return None

    device_type = _detect_device(user_agent)

    await ops.record_dynamic_scan(
        session=session,
        code_id=record.id,
        ip_address=ip_address,
        user_agent=user_agent,
        country=country,
        device_type=device_type,
    )

    return record.destination_url


async def get_analytics(
    session: AsyncSession,
    code_id: str,
    user_id: int,
) -> Optional[dict]:
    """
    Return a summary analytics dict for a dynamic code owned by user_id.
    """
    import uuid as _uuid

    result = await session.execute(
        select(DynamicCode).where(
            DynamicCode.id == _uuid.UUID(code_id),
            DynamicCode.user_id == user_id,
        )
    )
    code = result.scalar_one_or_none()
    if not code:
        return None

    # All events
    events_result = await session.execute(
        select(DynamicScanEvent).where(DynamicScanEvent.code_id == code.id)
    )
    events = list(events_result.scalars().all())

    # Device breakdown
    device_counts: dict[str, int] = {}
    for ev in events:
        dt = ev.device_type or "unknown"
        device_counts[dt] = device_counts.get(dt, 0) + 1

    # Country breakdown (top 5)
    country_counts: dict[str, int] = {}
    for ev in events:
        c = ev.country or "Unknown"
        country_counts[c] = country_counts.get(c, 0) + 1
    top_countries = sorted(country_counts.items(), key=lambda x: x[1], reverse=True)[:5]

    # Recent events (last 5)
    recent = sorted(events, key=lambda e: e.scanned_at, reverse=True)[:5]

    return {
        "code_id": str(code.id),
        "short_code": code.short_code,
        "title": code.title,
        "destination_url": code.destination_url,
        "is_active": code.is_active,
        "expires_at": code.expires_at.isoformat() if code.expires_at else None,
        "created_at": code.created_at.isoformat(),
        "total_scans": code.scan_count,
        "device_breakdown": device_counts,
        "top_countries": dict(top_countries),
        "recent_scans": [
            {
                "scanned_at": e.scanned_at.isoformat(),
                "device_type": e.device_type,
                "country": e.country,
            }
            for e in recent
        ],
    }
