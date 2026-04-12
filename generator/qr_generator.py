"""
QR code generator with full customisation support.

Features
--------
* Foreground / background color
* Embedded logo / image
* Dot style: square (classic), rounded, dots
* Error correction: L / M / Q / H
* Export formats: PNG, SVG, PDF
* Optional border / quiet-zone control
"""

from __future__ import annotations

import io
import logging
import os
import uuid
from dataclasses import dataclass, field
from typing import Literal, Optional

from PIL import Image, ImageDraw

import qrcode
from qrcode.constants import ERROR_CORRECT_H, ERROR_CORRECT_L, ERROR_CORRECT_M, ERROR_CORRECT_Q
from qrcode.image.styledpil import StyledPilImage
from qrcode.image.styles.moduledrawers import (
    CircleModuleDrawer,
    GappedSquareModuleDrawer,
    RoundedModuleDrawer,
    SquareModuleDrawer,
)
from qrcode.image.styles.colormasks import SolidFillColorMask
from qrcode.image.svg import SvgFillImage

from config import settings

logger = logging.getLogger(__name__)

_EC_MAP = {
    "L": ERROR_CORRECT_L,
    "M": ERROR_CORRECT_M,
    "Q": ERROR_CORRECT_Q,
    "H": ERROR_CORRECT_H,
}

_DRAWER_MAP = {
    "square": SquareModuleDrawer,
    "rounded": RoundedModuleDrawer,
    "dots": CircleModuleDrawer,
    "gapped": GappedSquareModuleDrawer,
}


@dataclass
class QROptions:
    data: str
    error_correction: Literal["L", "M", "Q", "H"] = "H"
    box_size: int = 10
    border: int = 4
    fg_color: str = "#000000"
    bg_color: str = "#FFFFFF"
    style: Literal["square", "rounded", "dots", "gapped"] = "square"
    logo_path: Optional[str] = None        # path to overlay image
    logo_ratio: float = 0.25              # logo occupies this fraction of QR
    export_format: Literal["png", "svg", "pdf"] = "png"
    size_px: int = 400                     # final image dimension for png/pdf


def _hex_to_rgb(color: str) -> tuple[int, int, int]:
    color = color.lstrip("#")
    r, g, b = int(color[0:2], 16), int(color[2:4], 16), int(color[4:6], 16)
    return r, g, b


def _generate_png(opts: QROptions) -> bytes:
    ec = _EC_MAP.get(opts.error_correction, ERROR_CORRECT_H)
    drawer_cls = _DRAWER_MAP.get(opts.style, SquareModuleDrawer)

    fg_rgb = _hex_to_rgb(opts.fg_color)
    bg_rgb = _hex_to_rgb(opts.bg_color)

    qr = qrcode.QRCode(
        error_correction=ec,
        box_size=opts.box_size,
        border=opts.border,
    )
    qr.add_data(opts.data)
    qr.make(fit=True)

    img: Image.Image = qr.make_image(
        image_factory=StyledPilImage,
        module_drawer=drawer_cls(),
        color_mask=SolidFillColorMask(
            back_color=(*bg_rgb, 255),
            front_color=(*fg_rgb, 255),
        ),
    ).convert("RGBA")

    # Embed logo
    if opts.logo_path and os.path.exists(opts.logo_path):
        logo = Image.open(opts.logo_path).convert("RGBA")
        qr_w, qr_h = img.size
        max_logo = int(min(qr_w, qr_h) * opts.logo_ratio)
        logo.thumbnail((max_logo, max_logo), Image.LANCZOS)
        logo_w, logo_h = logo.size

        # White background padding behind logo
        pad = 6
        bg_layer = Image.new("RGBA", (logo_w + pad * 2, logo_h + pad * 2), (*bg_rgb, 255))
        bg_layer.paste(logo, (pad, pad), logo)

        pos_x = (qr_w - bg_layer.width) // 2
        pos_y = (qr_h - bg_layer.height) // 2
        img.paste(bg_layer, (pos_x, pos_y), bg_layer)

    # Resize to target dimension
    img = img.resize((opts.size_px, opts.size_px), Image.LANCZOS)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _generate_svg(opts: QROptions) -> bytes:
    ec = _EC_MAP.get(opts.error_correction, ERROR_CORRECT_H)

    qr = qrcode.QRCode(
        error_correction=ec,
        box_size=opts.box_size,
        border=opts.border,
        image_factory=SvgFillImage,
    )
    qr.add_data(opts.data)
    qr.make(fit=True)
    img = qr.make_image()

    buf = io.BytesIO()
    img.save(buf)
    return buf.getvalue()


def _generate_pdf(opts: QROptions) -> bytes:
    """Generate a PNG, then embed it inside a minimal PDF."""
    png_bytes = _generate_png(opts)

    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas as rl_canvas

        buf = io.BytesIO()
        c = rl_canvas.Canvas(buf, pagesize=A4)
        page_w, page_h = A4
        img_size = min(page_w, page_h) * 0.7
        x = (page_w - img_size) / 2
        y = (page_h - img_size) / 2

        img_buf = io.BytesIO(png_bytes)
        c.drawImage(img_buf, x, y, width=img_size, height=img_size)
        c.showPage()
        c.save()
        return buf.getvalue()
    except ImportError:
        logger.warning("reportlab not installed — returning PNG instead of PDF.")
        return png_bytes


def generate_qr(opts: QROptions, save: bool = True) -> tuple[bytes, str]:
    """
    Generate a QR code according to *opts*.

    Returns
    -------
    (file_bytes, file_path)
        file_path is empty string when save=False.
    """
    fmt = opts.export_format.lower()
    if fmt == "svg":
        data = _generate_svg(opts)
    elif fmt == "pdf":
        data = _generate_pdf(opts)
    else:
        data = _generate_png(opts)

    file_path = ""
    if save:
        filename = f"qr_{uuid.uuid4().hex}.{fmt}"
        file_path = os.path.join(settings.GENERATED_DIR, filename)
        with open(file_path, "wb") as fh:
            fh.write(data)

    return data, file_path
