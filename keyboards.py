"""Inline keyboard layouts."""
from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def main_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📷 Scan QR", callback_data="scan"),
         InlineKeyboardButton("⚡ Generate", callback_data="generate")],
        [InlineKeyboardButton("📚 History", callback_data="history"),
         InlineKeyboardButton("📊 Analytics", callback_data="analytics")],
        [InlineKeyboardButton("🎨 Custom QR", callback_data="gen:Custom"),
         InlineKeyboardButton("ℹ️ Help", callback_data="help")],
    ])


def generate_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔗 URL", callback_data="gen:URL"),
         InlineKeyboardButton("💬 Text", callback_data="gen:Text")],
        [InlineKeyboardButton("📶 WiFi", callback_data="gen:WiFi"),
         InlineKeyboardButton("👤 Contact", callback_data="gen:Contact")],
        [InlineKeyboardButton("💳 Payment", callback_data="gen:Payment"),
         InlineKeyboardButton("🎨 Custom", callback_data="gen:Custom")],
        [InlineKeyboardButton("🏠 Main Menu", callback_data="home")],
    ])


def home_only() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🏠 Main Menu", callback_data="home")],
    ])


def after_qr() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⚡ Generate Another", callback_data="generate"),
         InlineKeyboardButton("🏠 Main Menu", callback_data="home")],
    ])


def after_scan() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 Scan Another", callback_data="scan"),
         InlineKeyboardButton("🏠 Main Menu", callback_data="home")],
    ])
