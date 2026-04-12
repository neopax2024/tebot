"""
Dynamic QR code manager.

A dynamic QR code encodes a short URL like:
    https://yourdomain.com/r/<short_code>

The FastAPI redirect endpoint resolves <short_code> → destination_url.
The destination can be updated at any time without re-generating the QR image.
"""

from __future__ import annotations

import random
import string
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from database import operations as ops
from database.models import DynamicCode
from generator.qr_generator import QROptions, generate_qr


_ALPHABET = string.ascii_letters + string.digits


def _make_short_code(length: int = 8) -> str:
    return "".join(random.choices(_ALPHABET, k=length))


async def create_dynamic_qr(
    session: AsyncSession,
    user_id: int,
    destination_url: str,
    title: Optional[str] = None,
    expires_at: Optional[datetime] = None,
    qr_options: Optional[dict] = None,
    check_limit: bool = True,
) -> tuple[DynamicCode, bytes]:
    """
    Create a new dynamic QR code.

    Returns (DynamicCode record, QR image PNG bytes).
    Raises ValueError if the free-tier limit is exceeded.
    """
    if check_limit:
        existing = await ops.get_user_dynamic_codes(session, user_id)
        user = await ops.get_user(session, user_id)
        if user and not user.is_premium:
            active = [c for c in existing if c.is_active]
            if len(active) >= settings.FREE_DYNAMIC_QR_LIMIT:
                raise ValueError(
                    f"Free tier allows up to {settings.FREE_DYNAMIC_QR_LIMIT} active dynamic codes. "
                    "Upgrade to Premium for unlimited dynamic QR codes."
                )

    # Ensure short code is unique (retry a few times)
    short_code = ""
    for _ in range(10):
        candidate = _make_short_code()
        existing_code = await ops.get_dynamic_code_by_short(session, candidate)
        if existing_code is None:
            short_code = candidate
            break
    if not short_code:
        raise RuntimeError("Failed to generate a unique short code.")

    redirect_url = f"{settings.SHORT_URL_PREFIX}{short_code}"

    # Parse user customisation options
    opts_dict = qr_options or {}
    qr_opts = QROptions(
        data=redirect_url,
        error_correction=opts_dict.get("error_correction", "H"),
        box_size=opts_dict.get("box_size", 10),
        border=opts_dict.get("border", 4),
        fg_color=opts_dict.get("fg_color", "#000000"),
        bg_color=opts_dict.get("bg_color", "#FFFFFF"),
        style=opts_dict.get("style", "square"),
        logo_path=opts_dict.get("logo_path"),
        export_format="png",
        size_px=opts_dict.get("size_px", 400),
    )

    qr_bytes, file_path = generate_qr(qr_opts, save=True)

    record = await ops.create_dynamic_code(
        session=session,
        user_id=user_id,
        short_code=short_code,
        destination_url=destination_url,
        title=title,
        expires_at=expires_at,
        options={**opts_dict, "file_path": file_path},
    )

    return record, qr_bytes


async def update_destination(
    session: AsyncSession,
    code_id: str,
    user_id: int,
    new_url: str,
) -> bool:
    """Update the destination URL of an existing dynamic code."""
    return await ops.update_dynamic_destination(session, code_id, user_id, new_url)


async def deactivate_code(
    session: AsyncSession,
    code_id: str,
    user_id: int,
) -> bool:
    from sqlalchemy import update
    from database.models import DynamicCode
    import uuid

    async with session:
        result = await session.execute(
            update(DynamicCode)
            .where(
                DynamicCode.id == uuid.UUID(code_id),
                DynamicCode.user_id == user_id,
            )
            .values(is_active=False)
            .returning(DynamicCode.id)
        )
        await session.commit()
        return result.scalar_one_or_none() is not None


async def get_user_codes(
    session: AsyncSession,
    user_id: int,
    limit: int = 50,
) -> list[DynamicCode]:
    return await ops.get_user_dynamic_codes(session, user_id, limit=limit)
