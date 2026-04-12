"""
Barcode generator — supports all common 1-D formats via python-barcode.

Supported symbologies
---------------------
EAN-13, EAN-8, UPC-A, Code 128, Code 39, ITF, ISBN-10, ISBN-13, PZN

Export formats: PNG, SVG, PDF
"""

from __future__ import annotations

import io
import logging
import os
import uuid
from dataclasses import dataclass
from typing import Literal, Optional

from config import settings

logger = logging.getLogger(__name__)

BARCODE_FORMATS = {
    "ean13": "ean13",
    "ean8": "ean8",
    "upca": "upca",
    "code128": "code128",
    "code39": "code39",
    "itf": "itf",
    "isbn10": "isbn10",
    "isbn13": "isbn13",
    "pzn": "pzn",
}


@dataclass
class BarcodeOptions:
    data: str
    barcode_format: str = "code128"          # see BARCODE_FORMATS keys
    export_format: Literal["png", "svg", "pdf"] = "png"
    fg_color: str = "#000000"
    bg_color: str = "#FFFFFF"
    width_mm: int = 80                        # approx rendered width
    height_mm: int = 30
    show_text: bool = True
    text_distance: float = 5.0
    quiet_zone: float = 6.5


def _generate_svg_bytes(opts: BarcodeOptions) -> bytes:
    import barcode
    from barcode.writer import SVGWriter

    fmt_key = opts.barcode_format.lower().replace("-", "")
    bc_cls = barcode.get_barcode_class(BARCODE_FORMATS.get(fmt_key, "code128"))

    writer = SVGWriter()
    buf = io.BytesIO()
    bc_cls(
        opts.data,
        writer=writer,
    ).write(
        buf,
        options={
            "foreground": opts.fg_color,
            "background": opts.bg_color,
            "write_text": opts.show_text,
            "text_distance": opts.text_distance,
            "quiet_zone": opts.quiet_zone,
        },
    )
    buf.seek(0)
    return buf.read()


def _generate_png_bytes(opts: BarcodeOptions) -> bytes:
    import barcode
    from barcode.writer import ImageWriter

    fmt_key = opts.barcode_format.lower().replace("-", "")
    bc_cls = barcode.get_barcode_class(BARCODE_FORMATS.get(fmt_key, "code128"))

    writer = ImageWriter()
    buf = io.BytesIO()
    bc_cls(
        opts.data,
        writer=writer,
    ).write(
        buf,
        options={
            "foreground": opts.fg_color,
            "background": opts.bg_color,
            "write_text": opts.show_text,
            "text_distance": opts.text_distance,
            "quiet_zone": opts.quiet_zone,
            "module_width": 10,
            "module_height": 10,
        },
    )
    buf.seek(0)
    return buf.read()


def _generate_pdf_bytes(opts: BarcodeOptions) -> bytes:
    png_bytes = _generate_png_bytes(opts)
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas as rl_canvas

        buf = io.BytesIO()
        c = rl_canvas.Canvas(buf, pagesize=A4)
        page_w, _ = A4
        img_w = page_w * 0.6
        img_h = img_w * 0.3

        x = (page_w - img_w) / 2
        y = 500

        c.drawImage(io.BytesIO(png_bytes), x, y, width=img_w, height=img_h)
        c.showPage()
        c.save()
        return buf.getvalue()
    except ImportError:
        return png_bytes


def generate_barcode(opts: BarcodeOptions, save: bool = True) -> tuple[bytes, str]:
    """
    Returns (file_bytes, file_path).
    """
    fmt = opts.export_format.lower()
    try:
        if fmt == "svg":
            data = _generate_svg_bytes(opts)
        elif fmt == "pdf":
            data = _generate_pdf_bytes(opts)
        else:
            data = _generate_png_bytes(opts)
    except Exception as exc:
        logger.error("Barcode generation failed: %s", exc)
        raise

    file_path = ""
    if save:
        filename = f"barcode_{uuid.uuid4().hex}.{fmt}"
        file_path = os.path.join(settings.GENERATED_DIR, filename)
        with open(file_path, "wb") as fh:
            fh.write(data)

    return data, file_path
