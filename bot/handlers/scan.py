"""
Scan handlers — image, PDF, and inline camera results.
"""

from __future__ import annotations

import io
import logging

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    BufferedInputFile,
    CallbackQuery,
    ContentType,
    Message,
)

from bot.keyboards.main_menu import scan_menu_keyboard, scan_result_keyboard
from database.engine import AsyncSessionLocal
from database import operations as ops
from scanner import detector, analyzer

logger = logging.getLogger(__name__)
router = Router()


class ScanStates(StatesGroup):
    waiting_for_image = State()
    waiting_for_pdf = State()


# ---------------------------------------------------------------------------
# Entry points
# ---------------------------------------------------------------------------

@router.message(Command("scan"))
@router.message(F.text == "📷 Scan Code")
async def cmd_scan(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(
        "📷 *Scan a Code*\n\nHow would you like to scan?",
        parse_mode="Markdown",
        reply_markup=scan_menu_keyboard(),
    )


@router.callback_query(F.data == "scan:image")
async def cb_scan_image(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(ScanStates.waiting_for_image)
    await callback.message.edit_text(
        "🖼 Please send an image (JPEG, PNG, WEBP) containing the code you want to scan."
    )
    await callback.answer()


@router.callback_query(F.data == "scan:pdf")
async def cb_scan_pdf(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(ScanStates.waiting_for_pdf)
    await callback.message.edit_text(
        "📄 Please send a PDF document. I'll scan all pages for codes."
    )
    await callback.answer()


# ---------------------------------------------------------------------------
# Auto-detect: any photo sent without explicit state also gets scanned
# ---------------------------------------------------------------------------

@router.message(F.content_type.in_({ContentType.PHOTO, ContentType.DOCUMENT}))
async def handle_file(message: Message, state: FSMContext) -> None:
    current_state = await state.get_state()

    # Determine if file is PDF
    is_pdf = False
    if message.document:
        mime = (message.document.mime_type or "").lower()
        is_pdf = "pdf" in mime

    if current_state == ScanStates.waiting_for_pdf.state or is_pdf:
        await _process_pdf(message, state)
    else:
        await _process_image(message, state)


# ---------------------------------------------------------------------------
# Image processing
# ---------------------------------------------------------------------------

async def _process_image(message: Message, state: FSMContext) -> None:
    await state.clear()
    status_msg = await message.answer("🔍 Scanning image…")

    try:
        image_bytes = await _download_file(message)
        if image_bytes is None:
            await status_msg.edit_text("❌ Could not download the file. Please try again.")
            return

        # Check quota
        async with AsyncSessionLocal() as session:
            user = await ops.get_or_create_user(
                session, message.from_user.id,
                username=message.from_user.username,
                first_name=message.from_user.first_name,
            )
            user_obj = user[0]
            if not await ops.check_scan_limit(session, user_obj):
                await status_msg.edit_text(
                    "⚠️ You've reached your daily free scan limit.\n"
                    "Upgrade to Premium for unlimited scans!"
                )
                return

        results = detector.scan_image_bytes(image_bytes)

        if not results:
            await status_msg.edit_text(
                "❌ No codes detected in this image.\n\n"
                "Tips:\n"
                "• Make sure the code is clearly visible\n"
                "• Try a higher-resolution image\n"
                "• Use the Mini App for live camera scanning"
            )
            return

        await status_msg.edit_text(
            f"✅ Found {len(results)} code(s)! Analysing…"
        )

        for idx, result in enumerate(results, start=1):
            await _handle_scan_result(
                message=message,
                result=result,
                index=idx,
                total=len(results),
                source="image",
            )

    except Exception as exc:
        logger.exception("Image scan error: %s", exc)
        await status_msg.edit_text(f"❌ Scan failed: {exc}")


# ---------------------------------------------------------------------------
# PDF processing
# ---------------------------------------------------------------------------

async def _process_pdf(message: Message, state: FSMContext) -> None:
    await state.clear()
    status_msg = await message.answer("📄 Processing PDF — this may take a moment…")

    try:
        pdf_bytes = await _download_file(message)
        if pdf_bytes is None:
            await status_msg.edit_text("❌ Could not download the PDF.")
            return

        async with AsyncSessionLocal() as session:
            user, _ = await ops.get_or_create_user(
                session, message.from_user.id,
                username=message.from_user.username,
                first_name=message.from_user.first_name,
            )
            if not await ops.check_scan_limit(session, user):
                await status_msg.edit_text(
                    "⚠️ Daily scan limit reached. Upgrade to Premium!"
                )
                return

        results = detector.scan_pdf_bytes(pdf_bytes)

        if not results:
            await status_msg.edit_text("❌ No codes found in the PDF.")
            return

        await status_msg.edit_text(
            f"✅ Found {len(results)} code(s) in PDF! Analysing…"
        )

        for idx, result in enumerate(results, start=1):
            await _handle_scan_result(
                message=message,
                result=result,
                index=idx,
                total=len(results),
                source="pdf",
            )

    except Exception as exc:
        logger.exception("PDF scan error: %s", exc)
        await status_msg.edit_text(f"❌ PDF scan failed: {exc}")


# ---------------------------------------------------------------------------
# Shared result handler
# ---------------------------------------------------------------------------

async def _handle_scan_result(
    message: Message,
    result: detector.DetectionResult,
    index: int,
    total: int,
    source: str,
) -> None:
    report = await analyzer.analyse(result.raw_data, result.code_type)

    prefix = f"*Code {index}/{total}* — `{result.code_type}`\n\n"
    text = prefix + report.summary

    risk_emoji = {"safe": "✅", "suspicious": "⚠️", "dangerous": "🚨"}.get(
        report.risk_level, "❓"
    )
    if report.risk_level != "safe":
        text += f"\n\n{risk_emoji} *Risk: {report.risk_level.upper()}*"

    # Save to DB
    async with AsyncSessionLocal() as session:
        await ops.save_scan(
            session=session,
            user_id=message.from_user.id,
            code_type=result.code_type,
            raw_data=result.raw_data,
            content_type=report.content_type,
            analysis_result=report.extra,
            is_safe=report.is_safe,
            source=source,
        )
        await ops.increment_scan_count(session, message.from_user.id)

    has_url = report.content_type == "url"
    has_product = report.content_type == "product"

    await message.answer(
        text,
        parse_mode="Markdown",
        reply_markup=scan_result_keyboard(has_url=has_url, has_product=has_product),
        disable_web_page_preview=True,
    )


# ---------------------------------------------------------------------------
# File download helper
# ---------------------------------------------------------------------------

async def _download_file(message: Message) -> bytes | None:
    bot = message.bot
    if message.photo:
        file_id = message.photo[-1].file_id
    elif message.document:
        file_id = message.document.file_id
    else:
        return None

    file = await bot.get_file(file_id)
    buf = io.BytesIO()
    await bot.download_file(file.file_path, destination=buf)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Scan result action callbacks
# ---------------------------------------------------------------------------

@router.callback_query(F.data.startswith("scan_action:"))
async def cb_scan_action(callback: CallbackQuery, state: FSMContext) -> None:
    action = callback.data.split(":", 1)[1]

    if action == "favorite":
        await callback.answer("⭐ Saved to favorites!", show_alert=False)
    elif action == "share":
        await callback.answer("📤 Forward this message to share!", show_alert=True)
    elif action == "open_url":
        await callback.answer("🔗 Use the link above to open the URL.", show_alert=True)
    elif action == "view_product":
        await callback.answer("🛒 See the product info above.", show_alert=True)
    elif action == "regen":
        await callback.answer("⚡ Use /generate to create a new code.", show_alert=True)
    else:
        await callback.answer()
