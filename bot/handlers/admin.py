"""
Admin panel handlers — only accessible by ADMIN_IDS.
"""

from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton

from config import settings
from database.engine import AsyncSessionLocal
from database import operations as ops

logger = logging.getLogger(__name__)
router = Router()


def is_admin(user_id: int) -> bool:
    return user_id in settings.ADMIN_IDS


# ---------------------------------------------------------------------------
# Admin guard filter
# ---------------------------------------------------------------------------

from aiogram.filters import BaseFilter


class AdminFilter(BaseFilter):
    async def __call__(self, message: Message) -> bool:
        return is_admin(message.from_user.id)


# ---------------------------------------------------------------------------
# Admin dashboard
# ---------------------------------------------------------------------------

@router.message(Command("admin"), AdminFilter())
async def cmd_admin(message: Message) -> None:
    async with AsyncSessionLocal() as session:
        total_users = await ops.get_total_users(session)
        premium_users = await ops.get_premium_users(session)
        total_scans = await ops.get_total_scans(session)
        total_gens = await ops.get_total_generations(session)

    text = (
        "🛠 *Admin Dashboard*\n\n"
        f"👥 Total users: *{total_users}*\n"
        f"⭐ Premium users: *{premium_users}*\n"
        f"📷 Total scans: *{total_scans}*\n"
        f"⚡ Total generations: *{total_gens}*\n"
    )

    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="👥 User List", callback_data="admin:users:0"),
        InlineKeyboardButton(text="🔍 Find User", callback_data="admin:find"),
    )
    builder.row(
        InlineKeyboardButton(text="📢 Broadcast", callback_data="admin:broadcast"),
    )

    await message.answer(text, parse_mode="Markdown", reply_markup=builder.as_markup())


@router.message(Command("admin"))
async def cmd_admin_denied(message: Message) -> None:
    await message.answer("⛔ You don't have admin access.")


# ---------------------------------------------------------------------------
# User list
# ---------------------------------------------------------------------------

@router.callback_query(F.data.startswith("admin:users:"))
async def cb_admin_users(callback: CallbackQuery) -> None:
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Denied", show_alert=True)
        return

    offset = int(callback.data.split(":")[-1])
    page_size = 10

    async with AsyncSessionLocal() as session:
        users = await ops.get_all_users(session, limit=page_size, offset=offset)

    if not users:
        await callback.message.edit_text("No users found.")
        await callback.answer()
        return

    text = f"👥 *Users* (page {offset // page_size + 1})\n\n"
    for u in users:
        plan = "⭐" if u.is_premium else "🆓"
        banned = "🚫" if u.is_banned else ""
        text += (
            f"{plan}{banned} `{u.id}` — @{u.username or 'N/A'} "
            f"({u.first_name or ''} {u.last_name or ''})\n"
            f"   Joined: {u.joined_at.strftime('%Y-%m-%d')}\n"
        )

    builder = InlineKeyboardBuilder()
    if offset > 0:
        builder.add(InlineKeyboardButton(
            text="⬅️ Prev", callback_data=f"admin:users:{offset - page_size}"
        ))
    if len(users) == page_size:
        builder.add(InlineKeyboardButton(
            text="Next ➡️", callback_data=f"admin:users:{offset + page_size}"
        ))
    builder.adjust(2)
    builder.row(InlineKeyboardButton(text="◀ Back", callback_data="admin:main"))

    await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=builder.as_markup())
    await callback.answer()


# ---------------------------------------------------------------------------
# Ban / unban (inline lookup)
# ---------------------------------------------------------------------------

@router.callback_query(F.data.startswith("admin:ban:"))
async def cb_admin_ban(callback: CallbackQuery) -> None:
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Denied", show_alert=True)
        return

    parts = callback.data.split(":")
    action, target_id = parts[2], int(parts[3])

    async with AsyncSessionLocal() as session:
        banned = action == "ban"
        await ops.ban_user(session, target_id, banned)

    label = "banned" if action == "ban" else "unbanned"
    await callback.answer(f"User {target_id} {label}.", show_alert=True)


# ---------------------------------------------------------------------------
# Admin main callback
# ---------------------------------------------------------------------------

@router.callback_query(F.data == "admin:main")
async def cb_admin_main(callback: CallbackQuery) -> None:
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Denied", show_alert=True)
        return
    # Re-send full dashboard
    async with AsyncSessionLocal() as session:
        total_users = await ops.get_total_users(session)
        premium_users = await ops.get_premium_users(session)
        total_scans = await ops.get_total_scans(session)
        total_gens = await ops.get_total_generations(session)

    text = (
        "🛠 *Admin Dashboard*\n\n"
        f"👥 Total users: *{total_users}*\n"
        f"⭐ Premium users: *{premium_users}*\n"
        f"📷 Total scans: *{total_scans}*\n"
        f"⚡ Total generations: *{total_gens}*\n"
    )

    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="👥 User List", callback_data="admin:users:0"),
    )
    await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=builder.as_markup())
    await callback.answer()
