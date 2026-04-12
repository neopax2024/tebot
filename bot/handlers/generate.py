"""
Code generation handlers — QR, barcode, and Data Matrix.

FSM flow:
  1. User picks code type (QR / barcode / datamatrix)
  2. User picks data type (URL, text, WiFi …) or barcode format
  3. Bot asks for the data string
  4. Bot asks for export format (PNG/SVG/PDF)
  5. Bot generates and sends the file
"""

from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import BufferedInputFile, CallbackQuery, Message

from bot.keyboards.main_menu import (
    barcode_format_keyboard,
    export_format_keyboard,
    generate_menu_keyboard,
    qr_data_type_keyboard,
)
from config import settings
from database.engine import AsyncSessionLocal
from database import operations as ops
from generator.qr_generator import QROptions, generate_qr
from generator.barcode_generator import BarcodeOptions, generate_barcode
from generator.datamatrix_generator import DataMatrixOptions, generate_datamatrix

logger = logging.getLogger(__name__)
router = Router()


class GenStates(StatesGroup):
    # QR
    picking_qr_data_type = State()
    entering_qr_data = State()
    picking_qr_export = State()
    # Barcode
    picking_barcode_format = State()
    entering_barcode_data = State()
    picking_barcode_export = State()
    # Data Matrix
    entering_dm_data = State()
    picking_dm_export = State()


# ---------------------------------------------------------------------------
# Entry points
# ---------------------------------------------------------------------------

@router.message(Command("generate"))
@router.message(F.text == "⚡ Generate Code")
async def cmd_generate(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(
        "⚡ *Code Generator*\n\nWhat type of code do you want to create?",
        parse_mode="Markdown",
        reply_markup=generate_menu_keyboard(),
    )


@router.callback_query(F.data == "gen:menu")
async def cb_gen_menu(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.edit_text(
        "⚡ *Code Generator*\n\nWhat type of code do you want to create?",
        parse_mode="Markdown",
        reply_markup=generate_menu_keyboard(),
    )
    await callback.answer()


# ---------------------------------------------------------------------------
# QR Code flow
# ---------------------------------------------------------------------------

@router.callback_query(F.data == "gen:qr")
async def cb_gen_qr(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(GenStates.picking_qr_data_type)
    await state.update_data(code_type="qr")
    await callback.message.edit_text(
        "🔲 *QR Code Generator*\n\nSelect the type of data to encode:",
        parse_mode="Markdown",
        reply_markup=qr_data_type_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("qrtype:"), GenStates.picking_qr_data_type)
async def cb_qr_data_type(callback: CallbackQuery, state: FSMContext) -> None:
    qr_data_type = callback.data.split(":", 1)[1]
    await state.update_data(qr_data_type=qr_data_type)
    await state.set_state(GenStates.entering_qr_data)

    prompts = {
        "url": "🔗 Enter the URL (e.g. https://example.com):",
        "text": "📝 Enter the text to encode:",
        "email": "📧 Enter the email address:",
        "phone": "📞 Enter the phone number (e.g. +1234567890):",
        "wifi": "📶 Enter WiFi credentials in format:\n`WIFI:T:WPA;S:YourSSID;P:YourPassword;;`",
        "contact": "👤 Enter vCard data or just a name/phone for a simple contact:",
    }
    await callback.message.edit_text(
        prompts.get(qr_data_type, "Enter the data to encode:"),
        parse_mode="Markdown",
    )
    await callback.answer()


@router.message(GenStates.entering_qr_data)
async def enter_qr_data(message: Message, state: FSMContext) -> None:
    raw = message.text or ""
    if not raw.strip():
        await message.answer("❌ Data cannot be empty. Please enter the data:")
        return

    data = await state.get_data()
    qr_type = data.get("qr_data_type", "text")

    # Auto-format for known types
    formatted = raw.strip()
    if qr_type == "email" and not formatted.startswith("mailto:"):
        formatted = f"mailto:{formatted}"
    elif qr_type == "phone" and not formatted.startswith("tel:"):
        formatted = f"tel:{formatted}"

    await state.update_data(qr_data=formatted)
    await state.set_state(GenStates.picking_qr_export)
    await message.answer(
        "📦 Select export format:",
        reply_markup=export_format_keyboard("qrexport"),
    )


@router.callback_query(F.data.startswith("qrexport:"), GenStates.picking_qr_export)
async def cb_qr_export(callback: CallbackQuery, state: FSMContext) -> None:
    export_fmt = callback.data.split(":", 1)[1]
    data = await state.get_data()
    await state.clear()

    # Check generation quota
    async with AsyncSessionLocal() as session:
        user, _ = await ops.get_or_create_user(
            session, callback.from_user.id,
            username=callback.from_user.username,
            first_name=callback.from_user.first_name,
        )
        if not await ops.check_gen_limit(session, user):
            await callback.message.edit_text(
                "⚠️ Daily generation limit reached. Upgrade to Premium for unlimited generations!"
            )
            await callback.answer()
            return

    status = await callback.message.edit_text("⚙️ Generating QR code…")

    try:
        opts = QROptions(
            data=data.get("qr_data", ""),
            export_format=export_fmt,
        )
        qr_bytes, file_path = generate_qr(opts)

        caption = f"✅ *QR Code ready!*\nData: `{opts.data[:100]}`\nFormat: {export_fmt.upper()}"

        await callback.message.answer_document(
            document=BufferedInputFile(qr_bytes, filename=f"qrcode.{export_fmt}"),
            caption=caption,
            parse_mode="Markdown",
        )
        await status.delete()

        # Save to DB
        async with AsyncSessionLocal() as session:
            await ops.save_generated_code(
                session=session,
                user_id=callback.from_user.id,
                code_type="qr",
                data=opts.data,
                options={"style": opts.style, "fg": opts.fg_color, "bg": opts.bg_color},
                file_path=file_path,
                export_format=export_fmt,
            )
            await ops.increment_gen_count(session, callback.from_user.id)

    except Exception as exc:
        logger.exception("QR generation failed: %s", exc)
        await status.edit_text(f"❌ Generation failed: {exc}")

    await callback.answer()


# ---------------------------------------------------------------------------
# Barcode flow
# ---------------------------------------------------------------------------

@router.callback_query(F.data == "gen:barcode")
async def cb_gen_barcode(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(GenStates.picking_barcode_format)
    await state.update_data(code_type="barcode")
    await callback.message.edit_text(
        "|||  *Barcode Generator*\n\nSelect the barcode format:",
        parse_mode="Markdown",
        reply_markup=barcode_format_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("bcfmt:"), GenStates.picking_barcode_format)
async def cb_barcode_format(callback: CallbackQuery, state: FSMContext) -> None:
    bc_format = callback.data.split(":", 1)[1]
    await state.update_data(barcode_format=bc_format)
    await state.set_state(GenStates.entering_barcode_data)

    hints = {
        "ean13": "Enter 12 or 13 digits (EAN-13):",
        "ean8": "Enter 7 or 8 digits (EAN-8):",
        "upca": "Enter 11 or 12 digits (UPC-A):",
        "code128": "Enter any alphanumeric string (Code 128):",
        "code39": "Enter uppercase letters, digits, or - . $ / + % space (Code 39):",
        "itf": "Enter an even number of digits (ITF):",
    }
    await callback.message.edit_text(
        hints.get(bc_format, "Enter the data to encode:"),
        parse_mode="Markdown",
    )
    await callback.answer()


@router.message(GenStates.entering_barcode_data)
async def enter_barcode_data(message: Message, state: FSMContext) -> None:
    raw = (message.text or "").strip()
    if not raw:
        await message.answer("❌ Please enter the data for the barcode:")
        return

    await state.update_data(barcode_data=raw)
    await state.set_state(GenStates.picking_barcode_export)
    await message.answer(
        "📦 Select export format:",
        reply_markup=export_format_keyboard("bcexport"),
    )


@router.callback_query(F.data.startswith("bcexport:"), GenStates.picking_barcode_export)
async def cb_barcode_export(callback: CallbackQuery, state: FSMContext) -> None:
    export_fmt = callback.data.split(":", 1)[1]
    data = await state.get_data()
    await state.clear()

    async with AsyncSessionLocal() as session:
        user, _ = await ops.get_or_create_user(
            session, callback.from_user.id,
            username=callback.from_user.username,
            first_name=callback.from_user.first_name,
        )
        if not await ops.check_gen_limit(session, user):
            await callback.message.edit_text("⚠️ Daily generation limit reached.")
            await callback.answer()
            return

    status = await callback.message.edit_text("⚙️ Generating barcode…")

    try:
        opts = BarcodeOptions(
            data=data.get("barcode_data", ""),
            barcode_format=data.get("barcode_format", "code128"),
            export_format=export_fmt,
        )
        bc_bytes, file_path = generate_barcode(opts)

        await callback.message.answer_document(
            document=BufferedInputFile(bc_bytes, filename=f"barcode.{export_fmt}"),
            caption=f"✅ *Barcode ready!*\nFormat: `{opts.barcode_format.upper()}`\nData: `{opts.data[:80]}`",
            parse_mode="Markdown",
        )
        await status.delete()

        async with AsyncSessionLocal() as session:
            await ops.save_generated_code(
                session=session,
                user_id=callback.from_user.id,
                code_type="barcode",
                data=opts.data,
                options={"format": opts.barcode_format},
                file_path=file_path,
                export_format=export_fmt,
            )
            await ops.increment_gen_count(session, callback.from_user.id)

    except Exception as exc:
        logger.exception("Barcode generation failed: %s", exc)
        await status.edit_text(f"❌ Generation failed: {exc}")

    await callback.answer()


# ---------------------------------------------------------------------------
# Data Matrix flow
# ---------------------------------------------------------------------------

@router.callback_query(F.data == "gen:datamatrix")
async def cb_gen_dm(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(GenStates.entering_dm_data)
    await state.update_data(code_type="datamatrix")
    await callback.message.edit_text(
        "▪▪ *Data Matrix Generator*\n\nEnter the data to encode:",
        parse_mode="Markdown",
    )
    await callback.answer()


@router.message(GenStates.entering_dm_data)
async def enter_dm_data(message: Message, state: FSMContext) -> None:
    raw = (message.text or "").strip()
    if not raw:
        await message.answer("❌ Please enter the data:")
        return

    await state.update_data(dm_data=raw)
    await state.set_state(GenStates.picking_dm_export)
    await message.answer(
        "📦 Select export format:",
        reply_markup=export_format_keyboard("dmexport"),
    )


@router.callback_query(F.data.startswith("dmexport:"), GenStates.picking_dm_export)
async def cb_dm_export(callback: CallbackQuery, state: FSMContext) -> None:
    export_fmt = callback.data.split(":", 1)[1]
    data = await state.get_data()
    await state.clear()

    async with AsyncSessionLocal() as session:
        user, _ = await ops.get_or_create_user(
            session, callback.from_user.id,
            username=callback.from_user.username,
            first_name=callback.from_user.first_name,
        )
        if not await ops.check_gen_limit(session, user):
            await callback.message.edit_text("⚠️ Daily generation limit reached.")
            await callback.answer()
            return

    status = await callback.message.edit_text("⚙️ Generating Data Matrix…")

    try:
        opts = DataMatrixOptions(
            data=data.get("dm_data", ""),
            export_format=export_fmt,
        )
        dm_bytes, file_path = generate_datamatrix(opts)

        await callback.message.answer_document(
            document=BufferedInputFile(dm_bytes, filename=f"datamatrix.{export_fmt}"),
            caption=f"✅ *Data Matrix ready!*\nData: `{opts.data[:80]}`",
            parse_mode="Markdown",
        )
        await status.delete()

        async with AsyncSessionLocal() as session:
            await ops.save_generated_code(
                session=session,
                user_id=callback.from_user.id,
                code_type="datamatrix",
                data=opts.data,
                options={},
                file_path=file_path,
                export_format=export_fmt,
            )
            await ops.increment_gen_count(session, callback.from_user.id)

    except Exception as exc:
        logger.exception("Data Matrix generation failed: %s", exc)
        await status.edit_text(f"❌ Generation failed: {exc}")

    await callback.answer()
