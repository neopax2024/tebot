"""
Scan & generation history handlers.
"""

from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton

from database.engine import AsyncSessionLocal
from database import operations as ops

logger = logging.getLogger(__name__)
router = Router()

PAGE_SIZE = 5


# ---------------------------------------------------------------------------
# Entry points
# ---------------------------------------------------------------------------

@router.message(Command("history"))
@router.message(F.text == "📜 My History")
async def cmd_history(message: Message, state: FSMContext) -> None:
    await state.clear()
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="📷 Scan History", callback_data="hist:scan:0"),
        InlineKeyboardButton(text="⚡ Generated Codes", callback_data="hist:gen:0"),
    )
    builder.row(InlineKeyboardButton(text="◀ Back", callback_data="menu:main"))
    await message.answer(
        "📜 *History*\n\nView your past scans and generated codes:",
        parse_mode="Markdown",
        reply_markup=builder.as_markup(),
    )


@router.message(F.text == "⭐ Favorites")
async def cmd_favorites(message: Message, state: FSMContext) -> None:
    await _show_scan_history(message, favorites_only=True, offset=0, edit=False)


# ---------------------------------------------------------------------------
# Scan history
# ---------------------------------------------------------------------------

@router.callback_query(F.data.startswith("hist:scan:"))
async def cb_scan_history(callback: CallbackQuery, state: FSMContext) -> None:
    offset = int(callback.data.split(":")[-1])
    await _show_scan_history(callback.message, favorites_only=False, offset=offset, edit=True)
    await callback.answer()


async def _show_scan_history(
    message: Message,
    favorites_only: bool,
    offset: int,
    edit: bool,
) -> None:
    async with AsyncSessionLocal() as session:
        scans = await ops.get_scan_history(
            session,
            user_id=message.chat.id,
            limit=PAGE_SIZE,
            offset=offset,
            favorites_only=favorites_only,
        )

    if not scans and offset == 0:
        text = "⭐ No favorites yet." if favorites_only else "📷 No scan history yet."
        builder = InlineKeyboardBuilder()
        builder.row(InlineKeyboardButton(text="◀ Back", callback_data="menu:main"))
        if edit:
            await message.edit_text(text, reply_markup=builder.as_markup())
        else:
            await message.answer(text, reply_markup=builder.as_markup())
        return

    header = "⭐ *Favorites*" if favorites_only else "📷 *Scan History*"
    text = f"{header}\n\n"
    for scan in scans:
        fav = "⭐" if scan.is_favorite else ""
        safe = {"safe": "✅", "dangerous": "🚨", "suspicious": "⚠️"}.get(
            (scan.analysis_result or {}).get("risk_level", ""), "❓"
        )
        text += (
            f"{fav} `{scan.code_type}` — {scan.content_type or 'unknown'} {safe}\n"
            f"  `{scan.raw_data[:50]}{'…' if len(scan.raw_data) > 50 else ''}`\n"
            f"  📅 {scan.scanned_at.strftime('%Y-%m-%d %H:%M')}\n\n"
        )

    builder = InlineKeyboardBuilder()
    if offset > 0:
        builder.add(
            InlineKeyboardButton(
                text="⬅️ Prev",
                callback_data=f"hist:scan:{max(0, offset - PAGE_SIZE)}",
            )
        )
    if len(scans) == PAGE_SIZE:
        builder.add(
            InlineKeyboardButton(
                text="Next ➡️",
                callback_data=f"hist:scan:{offset + PAGE_SIZE}",
            )
        )
    builder.adjust(2)
    builder.row(InlineKeyboardButton(text="◀ Back", callback_data="menu:main"))

    if edit:
        await message.edit_text(text, parse_mode="Markdown", reply_markup=builder.as_markup())
    else:
        await message.answer(text, parse_mode="Markdown", reply_markup=builder.as_markup())


# ---------------------------------------------------------------------------
# Generated code history
# ---------------------------------------------------------------------------

@router.callback_query(F.data.startswith("hist:gen:"))
async def cb_gen_history(callback: CallbackQuery, state: FSMContext) -> None:
    offset = int(callback.data.split(":")[-1])

    async with AsyncSessionLocal() as session:
        codes = await ops.get_generated_history(
            session,
            user_id=callback.from_user.id,
            limit=PAGE_SIZE,
            offset=offset,
        )

    if not codes and offset == 0:
        await callback.message.edit_text(
            "⚡ No generated codes yet.",
            reply_markup=InlineKeyboardBuilder()
            .row(InlineKeyboardButton(text="◀ Back", callback_data="menu:main"))
            .as_markup(),
        )
        await callback.answer()
        return

    text = "⚡ *Generated Codes*\n\n"
    for code in codes:
        text += (
            f"• `{code.code_type.upper()}` — {code.export_format.upper()}\n"
            f"  `{code.data[:50]}{'…' if len(code.data) > 50 else ''}`\n"
            f"  📅 {code.created_at.strftime('%Y-%m-%d %H:%M')}\n\n"
        )

    builder = InlineKeyboardBuilder()
    if offset > 0:
        builder.add(
            InlineKeyboardButton(
                text="⬅️ Prev",
                callback_data=f"hist:gen:{max(0, offset - PAGE_SIZE)}",
            )
        )
    if len(codes) == PAGE_SIZE:
        builder.add(
            InlineKeyboardButton(
                text="Next ➡️",
                callback_data=f"hist:gen:{offset + PAGE_SIZE}",
            )
        )
    builder.adjust(2)
    builder.row(InlineKeyboardButton(text="◀ Back", callback_data="menu:main"))

    await callback.message.edit_text(
        text, parse_mode="Markdown", reply_markup=builder.as_markup()
    )
    await callback.answer()
