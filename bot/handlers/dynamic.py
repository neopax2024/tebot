"""
Dynamic QR code management handlers.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import BufferedInputFile, CallbackQuery, Message

from bot.keyboards.main_menu import (
    confirm_keyboard,
    dynamic_code_actions_keyboard,
    dynamic_qr_menu_keyboard,
)
from database.engine import AsyncSessionLocal
from database import operations as ops
from dynamic.manager import create_dynamic_qr, update_destination, deactivate_code, get_user_codes
from dynamic.tracker import get_analytics

logger = logging.getLogger(__name__)
router = Router()


class DynStates(StatesGroup):
    entering_destination = State()
    entering_title = State()
    editing_url = State()
    editing_url_code_id = State()


# ---------------------------------------------------------------------------
# Entry
# ---------------------------------------------------------------------------

@router.message(Command("dynamic"))
@router.message(F.text == "🔁 Dynamic QR")
async def cmd_dynamic(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(
        "🔁 *Dynamic QR Codes*\n\n"
        "Dynamic QR codes let you change the destination URL at any time "
        "without reprinting. Track every scan with analytics.",
        parse_mode="Markdown",
        reply_markup=dynamic_qr_menu_keyboard(),
    )


@router.callback_query(F.data == "dyn:menu")
async def cb_dyn_menu(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.edit_text(
        "🔁 *Dynamic QR Codes*",
        parse_mode="Markdown",
        reply_markup=dynamic_qr_menu_keyboard(),
    )
    await callback.answer()


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------

@router.callback_query(F.data == "dyn:create")
async def cb_dyn_create(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(DynStates.entering_destination)
    await callback.message.edit_text(
        "➕ *Create Dynamic QR Code*\n\n"
        "Enter the destination URL (you can change this later):",
        parse_mode="Markdown",
    )
    await callback.answer()


@router.message(DynStates.entering_destination)
async def enter_destination(message: Message, state: FSMContext) -> None:
    url = (message.text or "").strip()
    if not url.startswith(("http://", "https://")):
        await message.answer("❌ Please enter a valid URL starting with http:// or https://")
        return

    await state.update_data(destination_url=url)
    await state.set_state(DynStates.entering_title)
    await message.answer(
        "📝 Enter a title for this dynamic code (or send /skip to skip):"
    )


@router.message(DynStates.entering_title)
async def enter_title(message: Message, state: FSMContext) -> None:
    title = None
    if message.text and message.text.strip() not in ("/skip", "skip"):
        title = message.text.strip()[:255]

    data = await state.get_data()
    await state.clear()

    status = await message.answer("⚙️ Creating your dynamic QR code…")

    async with AsyncSessionLocal() as session:
        try:
            user, _ = await ops.get_or_create_user(
                session, message.from_user.id,
                username=message.from_user.username,
                first_name=message.from_user.first_name,
            )
            record, qr_bytes = await create_dynamic_qr(
                session=session,
                user_id=message.from_user.id,
                destination_url=data["destination_url"],
                title=title,
                check_limit=True,
            )

            await status.delete()
            await message.answer_document(
                document=BufferedInputFile(qr_bytes, filename=f"dynamic_{record.short_code}.png"),
                caption=(
                    f"✅ *Dynamic QR Code Created!*\n\n"
                    f"🔗 Short link: `{record.short_code}`\n"
                    f"📍 Destination: {record.destination_url}\n"
                    f"📝 Title: {record.title or 'N/A'}\n\n"
                    f"You can edit the destination URL anytime without reprinting this QR code."
                ),
                parse_mode="Markdown",
                reply_markup=dynamic_code_actions_keyboard(str(record.id)),
            )

        except ValueError as exc:
            await status.edit_text(f"⚠️ {exc}")
        except Exception as exc:
            logger.exception("Dynamic QR creation failed: %s", exc)
            await status.edit_text(f"❌ Failed to create dynamic QR: {exc}")


# ---------------------------------------------------------------------------
# List
# ---------------------------------------------------------------------------

@router.callback_query(F.data == "dyn:list")
async def cb_dyn_list(callback: CallbackQuery, state: FSMContext) -> None:
    async with AsyncSessionLocal() as session:
        codes = await get_user_codes(session, callback.from_user.id, limit=10)

    if not codes:
        await callback.message.edit_text(
            "📋 You have no dynamic QR codes yet.\n\nCreate one to get started!",
            reply_markup=dynamic_qr_menu_keyboard(),
        )
        await callback.answer()
        return

    text = "📋 *Your Dynamic QR Codes*\n\n"
    for code in codes:
        status_icon = "🟢" if code.is_active else "🔴"
        text += (
            f"{status_icon} *{code.title or code.short_code}*\n"
            f"   🔗 `{code.short_code}` → {code.destination_url[:40]}…\n"
            f"   📊 {code.scan_count} scans\n\n"
        )

    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from aiogram.types import InlineKeyboardButton

    builder = InlineKeyboardBuilder()
    for code in codes:
        builder.row(
            InlineKeyboardButton(
                text=f"{'🟢' if code.is_active else '🔴'} {code.title or code.short_code}",
                callback_data=f"dyn_view:{code.id}",
            )
        )
    builder.row(InlineKeyboardButton(text="◀ Back", callback_data="dyn:menu"))

    await callback.message.edit_text(
        text, parse_mode="Markdown", reply_markup=builder.as_markup()
    )
    await callback.answer()


@router.callback_query(F.data.startswith("dyn_view:"))
async def cb_dyn_view(callback: CallbackQuery, state: FSMContext) -> None:
    code_id = callback.data.split(":", 1)[1]

    async with AsyncSessionLocal() as session:
        from sqlalchemy import select
        from database.models import DynamicCode
        import uuid

        result = await session.execute(
            select(DynamicCode).where(
                DynamicCode.id == uuid.UUID(code_id),
                DynamicCode.user_id == callback.from_user.id,
            )
        )
        code = result.scalar_one_or_none()

    if not code:
        await callback.answer("Code not found.", show_alert=True)
        return

    status_icon = "🟢 Active" if code.is_active else "🔴 Inactive"
    expiry = code.expires_at.strftime("%Y-%m-%d") if code.expires_at else "Never"

    await callback.message.edit_text(
        f"🔁 *Dynamic QR Code*\n\n"
        f"📝 Title: {code.title or 'N/A'}\n"
        f"🔗 Short code: `{code.short_code}`\n"
        f"📍 Destination: {code.destination_url}\n"
        f"📊 Total scans: {code.scan_count}\n"
        f"📅 Created: {code.created_at.strftime('%Y-%m-%d')}\n"
        f"⏰ Expires: {expiry}\n"
        f"Status: {status_icon}",
        parse_mode="Markdown",
        reply_markup=dynamic_code_actions_keyboard(code_id),
    )
    await callback.answer()


# ---------------------------------------------------------------------------
# Edit destination URL
# ---------------------------------------------------------------------------

@router.callback_query(F.data.startswith("dyn_edit:"))
async def cb_dyn_edit(callback: CallbackQuery, state: FSMContext) -> None:
    code_id = callback.data.split(":", 1)[1]
    await state.set_state(DynStates.editing_url)
    await state.update_data(editing_code_id=code_id)
    await callback.message.edit_text(
        "✏️ Enter the new destination URL:"
    )
    await callback.answer()


@router.message(DynStates.editing_url)
async def enter_new_url(message: Message, state: FSMContext) -> None:
    new_url = (message.text or "").strip()
    if not new_url.startswith(("http://", "https://")):
        await message.answer("❌ Please enter a valid URL starting with http:// or https://")
        return

    data = await state.get_data()
    code_id = data.get("editing_code_id")
    await state.clear()

    async with AsyncSessionLocal() as session:
        success = await update_destination(session, code_id, message.from_user.id, new_url)

    if success:
        await message.answer(
            f"✅ Destination updated!\n\nNew URL: {new_url}",
            reply_markup=dynamic_code_actions_keyboard(code_id),
        )
    else:
        await message.answer("❌ Could not update — code not found or not owned by you.")


# ---------------------------------------------------------------------------
# Analytics
# ---------------------------------------------------------------------------

@router.callback_query(F.data.startswith("dyn_stats:"))
async def cb_dyn_stats(callback: CallbackQuery, state: FSMContext) -> None:
    code_id = callback.data.split(":", 1)[1]

    async with AsyncSessionLocal() as session:
        analytics = await get_analytics(session, code_id, callback.from_user.id)

    if not analytics:
        await callback.answer("Analytics not found.", show_alert=True)
        return

    devices = analytics.get("device_breakdown", {})
    countries = analytics.get("top_countries", {})

    device_lines = "\n".join(
        f"  • {k.title()}: {v}" for k, v in devices.items()
    ) or "  No data yet"

    country_lines = "\n".join(
        f"  • {k}: {v}" for k, v in countries.items()
    ) or "  No data yet"

    text = (
        f"📊 *Analytics — {analytics.get('title') or analytics.get('short_code')}*\n\n"
        f"🔢 Total scans: *{analytics['total_scans']}*\n\n"
        f"📱 Device breakdown:\n{device_lines}\n\n"
        f"🌍 Top countries:\n{country_lines}\n\n"
        f"Status: {'🟢 Active' if analytics['is_active'] else '🔴 Inactive'}"
    )

    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from aiogram.types import InlineKeyboardButton

    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="◀ Back", callback_data=f"dyn_view:{code_id}"))

    await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=builder.as_markup())
    await callback.answer()


# ---------------------------------------------------------------------------
# Download QR
# ---------------------------------------------------------------------------

@router.callback_query(F.data.startswith("dyn_dl:"))
async def cb_dyn_download(callback: CallbackQuery, state: FSMContext) -> None:
    code_id = callback.data.split(":", 1)[1]

    async with AsyncSessionLocal() as session:
        import uuid
        from sqlalchemy import select
        from database.models import DynamicCode
        from config import settings as cfg

        result = await session.execute(
            select(DynamicCode).where(
                DynamicCode.id == uuid.UUID(code_id),
                DynamicCode.user_id == callback.from_user.id,
            )
        )
        code = result.scalar_one_or_none()

    if not code:
        await callback.answer("Code not found.", show_alert=True)
        return

    file_path = (code.options or {}).get("file_path")
    if file_path:
        import os

        if os.path.exists(file_path):
            with open(file_path, "rb") as fh:
                qr_bytes = fh.read()
        else:
            await callback.answer("File no longer available. Re-generate.", show_alert=True)
            return
    else:
        # Regenerate
        from generator.qr_generator import QROptions, generate_qr
        from config import settings as cfg

        redirect_url = f"{cfg.SHORT_URL_PREFIX}{code.short_code}"
        opts = QROptions(data=redirect_url)
        qr_bytes, _ = generate_qr(opts, save=False)

    await callback.message.answer_document(
        document=BufferedInputFile(qr_bytes, filename=f"dynamic_{code.short_code}.png"),
        caption=f"🔁 Dynamic QR — `{code.short_code}`\nDestination: {code.destination_url}",
        parse_mode="Markdown",
    )
    await callback.answer()


# ---------------------------------------------------------------------------
# Deactivate
# ---------------------------------------------------------------------------

@router.callback_query(F.data.startswith("dyn_del:"))
async def cb_dyn_deactivate(callback: CallbackQuery, state: FSMContext) -> None:
    code_id = callback.data.split(":", 1)[1]
    await callback.message.edit_text(
        "⚠️ Are you sure you want to deactivate this dynamic QR code?\n"
        "It will stop redirecting, but data is kept.",
        reply_markup=confirm_keyboard(
            confirm_cb=f"dyn_del_confirm:{code_id}",
            cancel_cb=f"dyn_view:{code_id}",
        ),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("dyn_del_confirm:"))
async def cb_dyn_deactivate_confirm(callback: CallbackQuery, state: FSMContext) -> None:
    code_id = callback.data.split(":", 1)[1]

    async with AsyncSessionLocal() as session:
        success = await deactivate_code(session, code_id, callback.from_user.id)

    if success:
        await callback.message.edit_text(
            "🔴 Dynamic QR code deactivated.",
            reply_markup=dynamic_qr_menu_keyboard(),
        )
    else:
        await callback.message.edit_text("❌ Could not deactivate — code not found.")

    await callback.answer()
