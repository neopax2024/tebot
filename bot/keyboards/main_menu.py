"""
Main reply & inline keyboard layouts.
"""

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    WebAppInfo,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder

from config import settings


# ---------------------------------------------------------------------------
# Reply keyboard (persistent bottom menu)
# ---------------------------------------------------------------------------

def main_reply_keyboard() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.row(
        KeyboardButton(text="📷 Scan Code"),
        KeyboardButton(text="⚡ Generate Code"),
    )
    builder.row(
        KeyboardButton(text="🔁 Dynamic QR"),
        KeyboardButton(text="📜 My History"),
    )
    builder.row(
        KeyboardButton(text="⭐ Favorites"),
        KeyboardButton(text="👤 My Account"),
    )
    builder.row(
        KeyboardButton(
            text="🌐 Open Mini App",
            web_app=WebAppInfo(url=settings.WEBAPP_URL),
        )
    )
    return builder.as_markup(resize_keyboard=True)


# ---------------------------------------------------------------------------
# Scan menu
# ---------------------------------------------------------------------------

def scan_menu_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🖼 Send an Image", callback_data="scan:image"),
        InlineKeyboardButton(text="📄 Send a PDF", callback_data="scan:pdf"),
    )
    builder.row(
        InlineKeyboardButton(
            text="📷 Use Camera (Mini App)",
            web_app=WebAppInfo(url=f"{settings.WEBAPP_URL}?mode=scan"),
        )
    )
    builder.row(InlineKeyboardButton(text="◀ Back", callback_data="menu:main"))
    return builder.as_markup()


# ---------------------------------------------------------------------------
# Generate menu
# ---------------------------------------------------------------------------

def generate_menu_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🔲 QR Code", callback_data="gen:qr"),
        InlineKeyboardButton(text="|||  Barcode", callback_data="gen:barcode"),
    )
    builder.row(
        InlineKeyboardButton(text="▪▪ Data Matrix", callback_data="gen:datamatrix"),
    )
    builder.row(InlineKeyboardButton(text="◀ Back", callback_data="menu:main"))
    return builder.as_markup()


# ---------------------------------------------------------------------------
# QR data type selection
# ---------------------------------------------------------------------------

def qr_data_type_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    types = [
        ("🔗 URL", "qrtype:url"),
        ("📝 Text", "qrtype:text"),
        ("📧 Email", "qrtype:email"),
        ("📞 Phone", "qrtype:phone"),
        ("📶 WiFi", "qrtype:wifi"),
        ("👤 Contact", "qrtype:contact"),
    ]
    for label, cb in types:
        builder.add(InlineKeyboardButton(text=label, callback_data=cb))
    builder.adjust(2)
    builder.row(
        InlineKeyboardButton(
            text="🎨 Open Advanced Editor",
            web_app=WebAppInfo(url=f"{settings.WEBAPP_URL}?mode=generate"),
        )
    )
    builder.row(InlineKeyboardButton(text="◀ Back", callback_data="gen:menu"))
    return builder.as_markup()


# ---------------------------------------------------------------------------
# Barcode format selection
# ---------------------------------------------------------------------------

def barcode_format_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    formats = [
        ("EAN-13", "bcfmt:ean13"),
        ("EAN-8", "bcfmt:ean8"),
        ("Code 128", "bcfmt:code128"),
        ("Code 39", "bcfmt:code39"),
        ("UPC-A", "bcfmt:upca"),
        ("ITF", "bcfmt:itf"),
    ]
    for label, cb in formats:
        builder.add(InlineKeyboardButton(text=label, callback_data=cb))
    builder.adjust(2)
    builder.row(InlineKeyboardButton(text="◀ Back", callback_data="gen:menu"))
    return builder.as_markup()


# ---------------------------------------------------------------------------
# Export format selection
# ---------------------------------------------------------------------------

def export_format_keyboard(prefix: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🖼 PNG", callback_data=f"{prefix}:png"),
        InlineKeyboardButton(text="📐 SVG", callback_data=f"{prefix}:svg"),
        InlineKeyboardButton(text="📄 PDF", callback_data=f"{prefix}:pdf"),
    )
    builder.row(InlineKeyboardButton(text="◀ Back", callback_data="gen:menu"))
    return builder.as_markup()


# ---------------------------------------------------------------------------
# Scan result actions
# ---------------------------------------------------------------------------

def scan_result_keyboard(has_url: bool = False, has_product: bool = False) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if has_url:
        builder.row(InlineKeyboardButton(text="🔗 Open URL", callback_data="scan_action:open_url"))
    if has_product:
        builder.row(InlineKeyboardButton(text="🛒 View Product", callback_data="scan_action:view_product"))
    builder.row(
        InlineKeyboardButton(text="⭐ Save to Favorites", callback_data="scan_action:favorite"),
        InlineKeyboardButton(text="🔁 Generate from this", callback_data="scan_action:regen"),
    )
    builder.row(InlineKeyboardButton(text="📤 Share", callback_data="scan_action:share"))
    return builder.as_markup()


# ---------------------------------------------------------------------------
# Dynamic QR menu
# ---------------------------------------------------------------------------

def dynamic_qr_menu_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="➕ Create Dynamic QR", callback_data="dyn:create"),
    )
    builder.row(
        InlineKeyboardButton(text="📋 My Dynamic Codes", callback_data="dyn:list"),
    )
    builder.row(InlineKeyboardButton(text="◀ Back", callback_data="menu:main"))
    return builder.as_markup()


def dynamic_code_actions_keyboard(code_id: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✏️ Edit URL", callback_data=f"dyn_edit:{code_id}"),
        InlineKeyboardButton(text="📊 Analytics", callback_data=f"dyn_stats:{code_id}"),
    )
    builder.row(
        InlineKeyboardButton(text="🖼 Download QR", callback_data=f"dyn_dl:{code_id}"),
        InlineKeyboardButton(text="🗑 Deactivate", callback_data=f"dyn_del:{code_id}"),
    )
    builder.row(InlineKeyboardButton(text="◀ Back", callback_data="dyn:list"))
    return builder.as_markup()


# ---------------------------------------------------------------------------
# Account / subscription
# ---------------------------------------------------------------------------

def account_keyboard(is_premium: bool) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if not is_premium:
        builder.row(
            InlineKeyboardButton(text="⭐ Upgrade to Premium", callback_data="sub:upgrade"),
        )
    builder.row(
        InlineKeyboardButton(text="📊 Usage Stats", callback_data="account:stats"),
        InlineKeyboardButton(text="🌍 Language", callback_data="account:lang"),
    )
    builder.row(InlineKeyboardButton(text="◀ Back", callback_data="menu:main"))
    return builder.as_markup()


def upgrade_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text=f"⭐ Pay with Telegram Stars",
            callback_data="pay:stars",
        )
    )
    builder.row(
        InlineKeyboardButton(text="💳 Pay with Stripe", callback_data="pay:stripe"),
    )
    builder.row(InlineKeyboardButton(text="◀ Back", callback_data="account:main"))
    return builder.as_markup()


# ---------------------------------------------------------------------------
# Confirmation
# ---------------------------------------------------------------------------

def confirm_keyboard(confirm_cb: str, cancel_cb: str = "menu:main") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Confirm", callback_data=confirm_cb),
        InlineKeyboardButton(text="❌ Cancel", callback_data=cancel_cb),
    )
    return builder.as_markup()
