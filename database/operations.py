"""
High-level async database operations used by bot handlers and the API.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from typing import Optional

from sqlalchemy import desc, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from database.models import (
    DailyUsage,
    DynamicCode,
    DynamicScanEvent,
    GeneratedCode,
    ScanHistory,
    Subscription,
    User,
)


# ---------------------------------------------------------------------------
# User helpers
# ---------------------------------------------------------------------------

async def get_or_create_user(
    session: AsyncSession,
    telegram_id: int,
    username: str | None = None,
    first_name: str | None = None,
    last_name: str | None = None,
    language_code: str = "en",
) -> tuple[User, bool]:
    """Return (user, created). Updates profile fields on every login."""
    result = await session.execute(select(User).where(User.id == telegram_id))
    user = result.scalar_one_or_none()
    created = False

    if user is None:
        user = User(
            id=telegram_id,
            username=username,
            first_name=first_name,
            last_name=last_name,
            language_code=language_code,
        )
        session.add(user)
        created = True
    else:
        user.username = username
        user.first_name = first_name
        user.last_name = last_name
        user.last_active = datetime.now(timezone.utc)

    await session.commit()
    await session.refresh(user)
    return user, created


async def get_user(session: AsyncSession, telegram_id: int) -> Optional[User]:
    result = await session.execute(select(User).where(User.id == telegram_id))
    return result.scalar_one_or_none()


async def set_user_premium(session: AsyncSession, telegram_id: int, is_premium: bool) -> None:
    await session.execute(update(User).where(User.id == telegram_id).values(is_premium=is_premium))
    await session.commit()


async def ban_user(session: AsyncSession, telegram_id: int, banned: bool = True) -> None:
    await session.execute(update(User).where(User.id == telegram_id).values(is_banned=banned))
    await session.commit()


# ---------------------------------------------------------------------------
# Daily usage / limits
# ---------------------------------------------------------------------------

async def _get_or_create_daily(session: AsyncSession, user_id: int) -> DailyUsage:
    today = date.today().isoformat()
    result = await session.execute(
        select(DailyUsage).where(DailyUsage.user_id == user_id, DailyUsage.date == today)
    )
    record = result.scalar_one_or_none()
    if record is None:
        record = DailyUsage(user_id=user_id, date=today)
        session.add(record)
        await session.commit()
        await session.refresh(record)
    return record


async def increment_scan_count(session: AsyncSession, user_id: int) -> int:
    """Increment today's scan counter; return new count."""
    record = await _get_or_create_daily(session, user_id)
    record.scans = (record.scans or 0) + 1
    await session.commit()
    return record.scans


async def increment_gen_count(session: AsyncSession, user_id: int) -> int:
    record = await _get_or_create_daily(session, user_id)
    record.generations = (record.generations or 0) + 1
    await session.commit()
    return record.generations


async def get_daily_usage(session: AsyncSession, user_id: int) -> DailyUsage:
    return await _get_or_create_daily(session, user_id)


async def check_scan_limit(session: AsyncSession, user: User) -> bool:
    """Return True if user can still scan today."""
    if user.is_premium:
        return True
    usage = await _get_or_create_daily(session, user.id)
    return (usage.scans or 0) < settings.FREE_DAILY_SCANS


async def check_gen_limit(session: AsyncSession, user: User) -> bool:
    if user.is_premium:
        return True
    usage = await _get_or_create_daily(session, user.id)
    return (usage.generations or 0) < settings.FREE_DAILY_GENERATIONS


# ---------------------------------------------------------------------------
# Scan history
# ---------------------------------------------------------------------------

async def save_scan(
    session: AsyncSession,
    user_id: int,
    code_type: str,
    raw_data: str,
    content_type: str | None = None,
    analysis_result: dict | None = None,
    is_safe: bool | None = None,
    source: str = "image",
) -> ScanHistory:
    record = ScanHistory(
        user_id=user_id,
        code_type=code_type,
        raw_data=raw_data,
        content_type=content_type,
        analysis_result=analysis_result,
        is_safe=is_safe,
        source=source,
    )
    session.add(record)
    await session.commit()
    await session.refresh(record)
    return record


async def get_scan_history(
    session: AsyncSession,
    user_id: int,
    limit: int = 20,
    offset: int = 0,
    favorites_only: bool = False,
) -> list[ScanHistory]:
    q = select(ScanHistory).where(ScanHistory.user_id == user_id)
    if favorites_only:
        q = q.where(ScanHistory.is_favorite == True)  # noqa: E712
    q = q.order_by(desc(ScanHistory.scanned_at)).limit(limit).offset(offset)
    result = await session.execute(q)
    return list(result.scalars().all())


async def toggle_scan_favorite(session: AsyncSession, scan_id: str, user_id: int) -> bool:
    result = await session.execute(
        select(ScanHistory).where(ScanHistory.id == uuid.UUID(scan_id), ScanHistory.user_id == user_id)
    )
    record = result.scalar_one_or_none()
    if record:
        record.is_favorite = not record.is_favorite
        await session.commit()
        return record.is_favorite
    return False


# ---------------------------------------------------------------------------
# Generated codes
# ---------------------------------------------------------------------------

async def save_generated_code(
    session: AsyncSession,
    user_id: int,
    code_type: str,
    data: str,
    options: dict | None = None,
    file_path: str | None = None,
    export_format: str = "png",
) -> GeneratedCode:
    record = GeneratedCode(
        user_id=user_id,
        code_type=code_type,
        data=data,
        options=options,
        file_path=file_path,
        export_format=export_format,
    )
    session.add(record)
    await session.commit()
    await session.refresh(record)
    return record


async def get_generated_history(
    session: AsyncSession,
    user_id: int,
    limit: int = 20,
    offset: int = 0,
) -> list[GeneratedCode]:
    q = (
        select(GeneratedCode)
        .where(GeneratedCode.user_id == user_id)
        .order_by(desc(GeneratedCode.created_at))
        .limit(limit)
        .offset(offset)
    )
    result = await session.execute(q)
    return list(result.scalars().all())


# ---------------------------------------------------------------------------
# Dynamic codes
# ---------------------------------------------------------------------------

async def create_dynamic_code(
    session: AsyncSession,
    user_id: int,
    short_code: str,
    destination_url: str,
    title: str | None = None,
    expires_at: datetime | None = None,
    options: dict | None = None,
) -> DynamicCode:
    record = DynamicCode(
        user_id=user_id,
        short_code=short_code,
        destination_url=destination_url,
        title=title,
        expires_at=expires_at,
        options=options,
    )
    session.add(record)
    await session.commit()
    await session.refresh(record)
    return record


async def get_dynamic_code_by_short(session: AsyncSession, short_code: str) -> Optional[DynamicCode]:
    result = await session.execute(
        select(DynamicCode).where(DynamicCode.short_code == short_code)
    )
    return result.scalar_one_or_none()


async def get_user_dynamic_codes(
    session: AsyncSession, user_id: int, limit: int = 50
) -> list[DynamicCode]:
    result = await session.execute(
        select(DynamicCode)
        .where(DynamicCode.user_id == user_id)
        .order_by(desc(DynamicCode.created_at))
        .limit(limit)
    )
    return list(result.scalars().all())


async def update_dynamic_destination(
    session: AsyncSession, code_id: str, user_id: int, new_url: str
) -> bool:
    result = await session.execute(
        update(DynamicCode)
        .where(DynamicCode.id == uuid.UUID(code_id), DynamicCode.user_id == user_id)
        .values(destination_url=new_url, updated_at=datetime.now(timezone.utc))
        .returning(DynamicCode.id)
    )
    await session.commit()
    return result.scalar_one_or_none() is not None


async def record_dynamic_scan(
    session: AsyncSession,
    code_id: uuid.UUID,
    ip_address: str | None = None,
    user_agent: str | None = None,
    country: str | None = None,
    device_type: str | None = None,
) -> None:
    event = DynamicScanEvent(
        code_id=code_id,
        ip_address=ip_address,
        user_agent=user_agent,
        country=country,
        device_type=device_type,
    )
    session.add(event)
    await session.execute(
        update(DynamicCode).where(DynamicCode.id == code_id).values(
            scan_count=DynamicCode.scan_count + 1
        )
    )
    await session.commit()


# ---------------------------------------------------------------------------
# Admin / analytics
# ---------------------------------------------------------------------------

async def get_total_users(session: AsyncSession) -> int:
    result = await session.execute(select(func.count()).select_from(User))
    return result.scalar() or 0


async def get_premium_users(session: AsyncSession) -> int:
    result = await session.execute(
        select(func.count()).select_from(User).where(User.is_premium == True)  # noqa: E712
    )
    return result.scalar() or 0


async def get_total_scans(session: AsyncSession) -> int:
    result = await session.execute(select(func.count()).select_from(ScanHistory))
    return result.scalar() or 0


async def get_total_generations(session: AsyncSession) -> int:
    result = await session.execute(select(func.count()).select_from(GeneratedCode))
    return result.scalar() or 0


async def get_all_users(session: AsyncSession, limit: int = 100, offset: int = 0) -> list[User]:
    result = await session.execute(
        select(User).order_by(desc(User.joined_at)).limit(limit).offset(offset)
    )
    return list(result.scalars().all())
