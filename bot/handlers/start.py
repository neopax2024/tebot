"""
/start, /help, and main-menu navigation handlers.
"""

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.keyboards.main_menu import main_reply_keyboard
from database.engine import AsyncSessionLocal
from database import operations as ops

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    tg_user = message.from_user

    async with AsyncSessionLocal() as session:
        user, created = await ops.get_or_create_user(
            session=session,
            telegram_id=tg_user.id,
            username=tg_user.username,
            first_name=tg_user.first_name,
            last_name=tg_user.last_name,
            language_code=tg_user.language_code or "en",
        )

    greeting = "Welcome back" if not created else "Welcome"
    name = tg_user.first_name or "there"

    await message.answer(
        f"👋 {greeting}, *{name}*!\n\n"
        "I'm your all-in-one **Code Scanner & Generator** bot.\n\n"
        "📷 *Scan* QR codes, barcodes, Data Matrix from images or PDFs\n"
        "⚡ *Generate* QR codes, barcodes, Data Matrix in multiple formats\n"
        "🔁 *Dynamic QR* — edit destination URLs anytime\n"
        "🧠 *Smart Analysis* — automatic internet lookup after scanning\n\n"
        "Choose an option below to get started:",
        parse_mode="Markdown",
        reply_markup=main_reply_keyboard(),
    )


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(
        "🛠 *Available Commands*\n\n"
        "/start — Main menu\n"
        "/scan — Scan a code from image or PDF\n"
        "/generate — Generate a new code\n"
        "/dynamic — Manage dynamic QR codes\n"
        "/history — View scan & generation history\n"
        "/account — Account info & Premium upgrade\n"
        "/admin — Admin panel (admins only)\n"
        "/help — Show this help message\n\n"
        "💡 *Tips*\n"
        "• Send any image directly — I'll try to detect codes automatically\n"
        "• Send a PDF — I'll scan every page\n"
        "• Use the Mini App for advanced editing and live camera scanning",
        parse_mode="Markdown",
        reply_markup=main_reply_keyboard(),
    )


@router.callback_query(F.data == "menu:main")
async def cb_main_menu(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.edit_text(
        "🏠 *Main Menu*\n\nChoose an option:",
        parse_mode="Markdown",
    )
    # Send fresh reply keyboard
    await callback.message.answer(
        "Use the buttons below to navigate:",
        reply_markup=main_reply_keyboard(),
    )
    await callback.answer()


@router.message(F.text == "👤 My Account")
async def menu_account(message: Message) -> None:
    from bot.handlers.account import show_account  # local import avoids circular
    await show_account(message)
