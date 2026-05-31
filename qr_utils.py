"""QR generation and decoding utilities."""
import io
import qrcode
from qrcode.constants import ERROR_CORRECT_M
from PIL import Image

try:
    from pyzbar.pyzbar import decode as _zbar_decode
    _HAS_ZBAR = True
except Exception:  # pragma: no cover - pyzbar needs the native zbar lib
    _HAS_ZBAR = False


def generate_qr(data: str, fill: str = "#000000", back: str = "#FFFFFF") -> io.BytesIO:
    """Render `data` to a PNG QR code and return an in-memory file."""
    qr = qrcode.QRCode(
        version=None,
        error_correction=ERROR_CORRECT_M,
        box_size=10,
        border=3,
    )
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color=fill, back_color=back).convert("RGB")

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    buf.name = "qrcode.png"
    return buf


def decode_qr(image_bytes: bytes) -> str | None:
    """Decode the first QR code found in an image. Returns text or None."""
    if not _HAS_ZBAR:
        raise RuntimeError(
            "pyzbar/zbar is not installed. See README for the system dependency."
        )
    img = Image.open(io.BytesIO(image_bytes))
    results = _zbar_decode(img)
    if not results:
        return None
    return results[0].data.decode("utf-8", errors="replace")


# ── Payload builders ─────────────────────────────────────────────────────────

def build_wifi(ssid: str, password: str, security: str = "WPA") -> str:
    security = (security or "WPA").upper()
    if security == "NONE":
        return f"WIFI:T:nopass;S:{ssid};;"
    return f"WIFI:T:{security};S:{ssid};P:{password};;"


def build_vcard(name: str, phone: str = "", email: str = "") -> str:
    lines = ["BEGIN:VCARD", "VERSION:3.0", f"FN:{name}"]
    if phone:
        lines.append(f"TEL:{phone}")
    if email:
        lines.append(f"EMAIL:{email}")
    lines.append("END:VCARD")
    return "\n".join(lines)


def build_payment(kind: str, address: str, amount: str = "") -> str:
    kind = (kind or "upi").lower()
    if kind == "btc":
        return f"bitcoin:{address}" + (f"?amount={amount}" if amount else "")
    if kind == "eth":
        return f"ethereum:{address}" + (f"?value={amount}" if amount else "")
    if kind == "paypal":
        return f"https://paypal.me/{address}" + (f"/{amount}" if amount else "")
    # default UPI
    return f"upi://pay?pa={address}" + (f"&am={amount}" if amount else "")
