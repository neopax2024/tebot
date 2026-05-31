"""
QRZenBot — a Telegram bot that scans and generates QR codes.

Run:  python bot.py
"""
import logging
import os

from telegram import Update, InputFile
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ConversationHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

import qr_utils
import storage
import keyboards

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
log = logging.getLogger("qrzenbot")

# Conversation states
ASK_INPUT, ASK_WIFI_PASS, ASK_CONTACT_PHONE, ASK_PAY_ADDR = range(4)

WELCOME = (
    "👋 *QRZenBot* — QR scanner & generator\\.\n\n"
    "Send me a photo of a QR code to decode it, or pick an option below\\."
)

HELP = (
    "*QRZenBot Commands*\n\n"
    "📷 *Scan QR* — Decode any QR from a photo\n"
    "⚡ *Generate* — Create new QR codes\n"
    "🎨 *Custom QR* — Styled with custom colors\n"
    "📚 *History* — Your recent QR codes\n"
    "📊 *Analytics* — Usage statistics\n\n"
    "Formats: URL · WiFi · vCard · UPI · Bitcoin · Text\n\n"
    "You can also just send a photo any time to scan it\\."
)


# ── Helpers ──────────────────────────────────────────────────────────────────

def md_escape(text: str) -> str:
    """Escape text for MarkdownV2."""
    for ch in r"_*[]()~`>#+-=|{}.!\\":
        text = text.replace(ch, "\\" + ch)
    return text


async def send_menu(update: Update, text: str = None):
    msg = update.effective_message
    await msg.reply_text(
        text or WELCOME,
        reply_markup=keyboards.main_menu(),
        parse_mode=ParseMode.MARKDOWN_V2,
    )


# ── Commands ─────────────────────────────────────────────────────────────────

async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await send_menu(update)


async def cmd_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_text(
        HELP, reply_markup=keyboards.home_only(), parse_mode=ParseMode.MARKDOWN_V2
    )


# ── Top-level callback router ────────────────────────────────────────────────

async def on_button(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    data = q.data

    if data == "home":
        await q.message.reply_text(
            WELCOME, reply_markup=keyboards.main_menu(), parse_mode=ParseMode.MARKDOWN_V2
        )
    elif data == "help":
        await q.message.reply_text(
            HELP, reply_markup=keyboards.home_only(), parse_mode=ParseMode.MARKDOWN_V2
        )
    elif data == "scan":
        await q.message.reply_text("📸 Send me a photo containing a QR code.")
    elif data == "generate":
        await q.message.reply_text(
            "⚡ Choose a QR type:", reply_markup=keyboards.generate_menu()
        )
    elif data == "history":
        await show_history(update, ctx)
    elif data == "analytics":
        await show_analytics(update, ctx)


# ── History + analytics ──────────────────────────────────────────────────────

async def show_history(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    rows = storage.recent_history(user_id, limit=6)
    if not rows:
        await update.effective_message.reply_text(
            "📚 No history yet. Generate or scan a QR code to get started!",
            reply_markup=keyboards.home_only(),
        )
        return
    lines = ["📚 *Recent QR codes:*\n"]
    for r in rows:
        icon = "⚡" if r["kind"] == "generate" else "📷"
        lines.append(f"{icon} {md_escape(r['label'])} — _{md_escape(r['qr_type'] or '')}_")
    await update.effective_message.reply_text(
        "\n".join(lines),
        reply_markup=keyboards.home_only(),
        parse_mode=ParseMode.MARKDOWN_V2,
    )


async def show_analytics(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    a = storage.analytics(update.effective_user.id)
    lines = [
        "📊 *Your usage stats:*\n",
        f"⚡ Generated: *{a['generated']}*",
        f"📷 Scanned: *{a['scanned']}*",
        f"📅 Last 30 days: *{a['this_month']}*",
    ]
    if a["by_type"]:
        lines.append("\n*By type:*")
        total = sum(t["count"] for t in a["by_type"]) or 1
        for t in a["by_type"]:
            pct = round(100 * t["count"] / total)
            bar = "█" * max(1, pct // 10)
            lines.append(f"{md_escape(t['type'])}: {bar} {pct}%")
    await update.effective_message.reply_text(
        "\n".join(lines),
        reply_markup=keyboards.home_only(),
        parse_mode=ParseMode.MARKDOWN_V2,
    )


# ── Scanning (any photo) ─────────────────────────────────────────────────────

async def on_photo(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    notice = await msg.reply_text("🔍 Analyzing image…")
    try:
        photo = await msg.photo[-1].get_file()
        data = bytes(await photo.download_as_bytearray())
        decoded = qr_utils.decode_qr(data)
    except RuntimeError as e:
        await notice.edit_text(f"⚠️ {e}")
        return
    except Exception as e:
        log.exception("scan failed")
        await notice.edit_text(f"⚠️ Could not read the image. ({e})")
        return

    if not decoded:
        await notice.edit_text(
            "❌ No QR code found in that image. Try a clearer photo.",
            reply_markup=keyboards.after_scan(),
        )
        return

    storage.log_event(update.effective_user.id, "scan", "Scan", "Scanned code", decoded)
    await notice.edit_text(
        f"✅ *Decoded:*\n\n`{md_escape(decoded)}`",
        reply_markup=keyboards.after_scan(),
        parse_mode=ParseMode.MARKDOWN_V2,
    )


# ── Generation conversation ──────────────────────────────────────────────────

PROMPTS = {
    "URL": "🔗 Send me the URL (e.g. https://example.com):",
    "Text": "💬 Send me the text to encode:",
    "WiFi": "📶 Send the WiFi network name (SSID):",
    "Contact": "👤 Send the contact's full name:",
    "Payment": "💳 Send payment type and address, e.g.  `upi user@bank`  or  `btc bc1q...`:",
    "Custom": "🎨 Send the content (URL or text) for your custom-colored QR:",
}


async def on_gen_choice(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    qr_type = q.data.split(":", 1)[1]
    ctx.user_data["qr_type"] = qr_type
    ctx.user_data["step"] = {}
    await q.message.reply_text(
        PROMPTS.get(qr_type, "Send the content:"),
        parse_mode=ParseMode.MARKDOWN_V2 if qr_type == "Payment" else None,
    )
    if qr_type in ("WiFi", "Contact", "Payment"):
        return ASK_INPUT
    return ASK_INPUT


async def on_gen_input(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    qr_type = ctx.user_data.get("qr_type", "Text")
    text = update.effective_message.text.strip()
    step = ctx.user_data.setdefault("step", {})

    # Multi-field flows
    if qr_type == "WiFi":
        if "ssid" not in step:
            step["ssid"] = text
            await update.effective_message.reply_text("🔑 Now send the WiFi password (or '-' for open):")
            return ASK_INPUT
        password = "" if text == "-" else text
        payload = qr_utils.build_wifi(step["ssid"], password)
        label = step["ssid"]
        return await finish_generate(update, ctx, qr_type, payload, label)

    if qr_type == "Contact":
        if "name" not in step:
            step["name"] = text
            await update.effective_message.reply_text("📞 Send the phone number (or '-' to skip):")
            return ASK_INPUT
        if "phone" not in step:
            step["phone"] = "" if text == "-" else text
            await update.effective_message.reply_text("✉️ Send the email (or '-' to skip):")
            return ASK_INPUT
        email = "" if text == "-" else text
        payload = qr_utils.build_vcard(step["name"], step["phone"], email)
        return await finish_generate(update, ctx, qr_type, payload, step["name"])

    if qr_type == "Payment":
        parts = text.split()
        kind = parts[0].lower() if parts else "upi"
        addr = parts[1] if len(parts) > 1 else parts[0]
        amount = parts[2] if len(parts) > 2 else ""
        payload = qr_utils.build_payment(kind, addr, amount)
        return await finish_generate(update, ctx, qr_type, payload, f"{kind} payment")

    # Single-field flows: URL, Text, Custom
    payload = text
    label = text[:40]
    return await finish_generate(update, ctx, qr_type, payload, label)


async def finish_generate(update, ctx, qr_type, payload, label):
    fill, back = "#000000", "#FFFFFF"
    if qr_type == "Custom":
        fill, back = "#1A3A5C", "#E8F4FD"  # default Navy scheme
    buf = qr_utils.generate_qr(payload, fill=fill, back=back)
    storage.log_event(update.effective_user.id, "generate", qr_type, label, payload)
    await update.effective_message.reply_photo(
        photo=InputFile(buf, filename="qrcode.png"),
        caption=f"✅ Your *{md_escape(qr_type)}* QR code is ready.",
        reply_markup=keyboards.after_qr(),
        parse_mode=ParseMode.MARKDOWN_V2,
    )
    ctx.user_data.clear()
    return ConversationHandler.END


async def cancel_conv(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data.clear()
    await update.effective_message.reply_text(
        "❌ Cancelled.", reply_markup=keyboards.main_menu()
    )
    return ConversationHandler.END


# ── App bootstrap ────────────────────────────────────────────────────────────

def build_app() -> Application:
    token = os.environ.get("BOT_TOKEN")
    if not token:
        raise SystemExit("BOT_TOKEN environment variable is not set.")

    storage.init_db()
    app = Application.builder().token(token).build()

    gen_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(on_gen_choice, pattern=r"^gen:")],
        states={
            ASK_INPUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, on_gen_input)],
        },
        fallbacks=[CommandHandler("cancel", cancel_conv)],
        per_message=False,
    )

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(gen_conv)
    app.add_handler(CallbackQueryHandler(on_button))
    app.add_handler(MessageHandler(filters.PHOTO, on_photo))

    return app


def main():
    app = build_app()
    mode = os.environ.get("MODE", "polling").lower()
    if mode == "webhook":
        port = int(os.environ.get("PORT", "8443"))
        url = os.environ["WEBHOOK_URL"].rstrip("/")
        log.info("Starting in webhook mode on port %s", port)
        app.run_webhook(
            listen="0.0.0.0",
            port=port,
            url_path=os.environ.get("BOT_TOKEN"),
            webhook_url=f"{url}/{os.environ.get('BOT_TOKEN')}",
        )
    else:
        log.info("Starting in polling mode")
        app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
