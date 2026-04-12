"""
Account, subscription, and payment handlers.
"""

from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, LabeledPrice, Message, PreCheckoutQuery

from bot.keyboards.main_menu import account_keyboard, upgrade_keyboard
from config import settings
from database.engine import AsyncSessionLocal
from database import operations as ops

logger = logging.getLogger(__name__)
router = Router()


async def show_account(message: Message) -> None:
    async with AsyncSessionLocal() as session:
        user, _ = await ops.get_or_create_user(
            session, message.from_user.id,
            username=message.from_user.username,
            first_name=message.from_user.first_name,
        )
        usage = await ops.get_daily_usage(session, message.from_user.id)

    plan_label = "⭐ Premium" if user.is_premium else "🆓 Free"
    scans_left = (
        "Unlimited" if user.is_premium
        else f"{max(0, settings.FREE_DAILY_SCANS - (usage.scans or 0))} / {settings.FREE_DAILY_SCANS}"
    )
    gens_left = (
        "Unlimited" if user.is_premium
        else f"{max(0, settings.FREE_DAILY_GENERATIONS - (usage.generations or 0))} / {settings.FREE_DAILY_GENERATIONS}"
    )

    text = (
        f"👤 *Your Account*\n\n"
        f"Name: {message.from_user.first_name or 'N/A'}\n"
        f"Username: @{message.from_user.username or 'N/A'}\n"
        f"Plan: {plan_label}\n\n"
        f"*Today's Usage:*\n"
        f"📷 Scans: {scans_left}\n"
        f"⚡ Generations: {gens_left}\n\n"
        f"{'🌟 *Premium Benefits:* unlimited scans, unlimited dynamic QR codes, advanced analytics' if not user.is_premium else '✅ You have full Premium access!'}"
    )

    await message.answer(
        text,
        parse_mode="Markdown",
        reply_markup=account_keyboard(is_premium=user.is_premium),
    )


@router.message(Command("account"))
async def cmd_account(message: Message, state: FSMContext) -> None:
    await show_account(message)


@router.callback_query(F.data == "account:main")
async def cb_account_main(callback: CallbackQuery, state: FSMContext) -> None:
    await show_account(callback.message)
    await callback.answer()


@router.callback_query(F.data == "account:stats")
async def cb_account_stats(callback: CallbackQuery) -> None:
    async with AsyncSessionLocal() as session:
        usage = await ops.get_daily_usage(session, callback.from_user.id)
        scans = await ops.get_scan_history(session, callback.from_user.id, limit=1)
        total_scans_result = await ops.get_scan_history(session, callback.from_user.id, limit=9999)
        gens = await ops.get_generated_history(session, callback.from_user.id, limit=9999)

    text = (
        f"📊 *Usage Statistics*\n\n"
        f"*Today:*\n"
        f"  📷 Scans: {usage.scans or 0}\n"
        f"  ⚡ Generations: {usage.generations or 0}\n\n"
        f"*All Time:*\n"
        f"  📷 Total scans: {len(total_scans_result)}\n"
        f"  ⚡ Total generated: {len(gens)}"
    )

    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from aiogram.types import InlineKeyboardButton

    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="◀ Back", callback_data="account:main"))

    await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=builder.as_markup())
    await callback.answer()


# ---------------------------------------------------------------------------
# Subscription upgrade
# ---------------------------------------------------------------------------

@router.callback_query(F.data == "sub:upgrade")
async def cb_upgrade(callback: CallbackQuery) -> None:
    await callback.message.edit_text(
        f"⭐ *Upgrade to Premium*\n\n"
        f"Unlock unlimited scans, generations, and dynamic QR codes.\n\n"
        f"💰 Price: {settings.PREMIUM_PRICE_STARS} Telegram Stars / month\n"
        f"         OR ${settings.PREMIUM_PRICE_USD:.2f} via Stripe",
        parse_mode="Markdown",
        reply_markup=upgrade_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "pay:stars")
async def cb_pay_stars(callback: CallbackQuery) -> None:
    """Send a Telegram Stars invoice."""
    try:
        await callback.message.answer_invoice(
            title="Premium Plan",
            description="Unlimited scans, generations & dynamic QR codes",
            payload="premium_monthly",
            currency="XTR",  # Telegram Stars currency code
            prices=[LabeledPrice(label="Premium (1 month)", amount=settings.PREMIUM_PRICE_STARS)],
        )
    except Exception as exc:
        logger.error("Stars invoice error: %s", exc)
        await callback.answer("⚠️ Payments temporarily unavailable.", show_alert=True)
    await callback.answer()


@router.pre_checkout_query()
async def pre_checkout(pre_checkout_query: PreCheckoutQuery) -> None:
    await pre_checkout_query.answer(ok=True)


@router.message(F.successful_payment)
async def payment_success(message: Message) -> None:
    payload = message.successful_payment.invoice_payload
    if payload == "premium_monthly":
        async with AsyncSessionLocal() as session:
            await ops.set_user_premium(session, message.from_user.id, True)
            from datetime import datetime, timedelta, timezone
            from database.models import Subscription
            sub = Subscription(
                user_id=message.from_user.id,
                plan="premium",
                payment_provider="telegram_stars",
                amount=message.successful_payment.total_amount,
                currency=message.successful_payment.currency,
                expires_at=datetime.now(timezone.utc) + timedelta(days=30),
            )
            session.add(sub)
            await session.commit()

        await message.answer(
            "🎉 *Payment successful! You're now Premium!*\n\n"
            "Enjoy unlimited scans, generations, and dynamic QR codes.",
            parse_mode="Markdown",
        )


@router.callback_query(F.data == "pay:stripe")
async def cb_pay_stripe(callback: CallbackQuery) -> None:
    await callback.answer(
        "💳 Stripe payment link will be sent to you shortly.",
        show_alert=True,
    )
    # TODO: generate Stripe checkout session and send payment link
