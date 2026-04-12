"""
Data Matrix code generator using pylibdmtx.

Export formats: PNG, SVG (approximate), PDF
"""

from __future__ import annotations

import io
import logging
import os
import uuid
from dataclasses import dataclass
from typing import Literal, Optional

from PIL import Image, ImageDraw

from config import settings

logger = logging.getLogger(__name__)


@dataclass
class DataMatrixOptions:
    data: str
    export_format: Literal["png", "svg", "pdf"] = "png"
    fg_color: str = "#000000"
    bg_color: str = "#FFFFFF"
    size_px: int = 300
    border_px: int = 10


def _generate_png_bytes(opts: DataMatrixOptions) -> bytes:
    try:
        from pylibdmtx.pylibdmtx import encode as dm_encode

        encoded = dm_encode(opts.data.encode("utf-8"))
        img = Image.frombytes("RGB", (encoded.width, encoded.height), encoded.pixels)

        # Apply colors (lib always returns black on white)
        if opts.fg_color != "#000000" or opts.bg_color != "#FFFFFF":
            img = img.convert("L")
            img_array = img.point(lambda p: 0 if p < 128 else 255, "L")
            fg = tuple(int(opts.fg_color.lstrip("#")[i : i + 2], 16) for i in (0, 2, 4))
            bg = tuple(int(opts.bg_color.lstrip("#")[i : i + 2], 16) for i in (0, 2, 4))
            colored = Image.new("RGB", img.size, bg)
            mask = img_array.point(lambda p: 255 if p == 0 else 0, "L")
            colored.paste(Image.new("RGB", img.size, fg), mask=mask)
            img = colored

        # Add border
        bordered_size = (
            img.width + 2 * opts.border_px,
            img.height + 2 * opts.border_px,
        )
        bg_color_tuple = tuple(int(opts.bg_color.lstrip("#")[i : i + 2], 16) for i in (0, 2, 4))
        bordered = Image.new("RGB", bordered_size, bg_color_tuple)
        bordered.paste(img, (opts.border_px, opts.border_px))

        # Resize
        bordered = bordered.resize((opts.size_px, opts.size_px), Image.NEAREST)

        buf = io.BytesIO()
        bordered.save(buf, format="PNG")
        return buf.getvalue()

    except ImportError:
        logger.error("pylibdmtx not installed — cannot generate Data Matrix.")
        raise RuntimeError("pylibdmtx is required for Data Matrix generation. Install it first.")


def _generate_svg_bytes(opts: DataMatrixOptions) -> bytes:
    """
    Fallback SVG using raster PNG embedded in an SVG wrapper.
    (True SVG Data Matrix is not supported by pylibdmtx.)
    """
    import base64

    png_data = _generate_png_bytes(opts)
    b64 = base64.b64encode(png_data).decode()
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{opts.size_px}" height="{opts.size_px}">'
        f'<image href="data:image/png;base64,{b64}" width="{opts.size_px}" height="{opts.size_px}"/>'
        f"</svg>"
    )
    return svg.encode()


def _generate_pdf_bytes(opts: DataMatrixOptions) -> bytes:
    png_bytes = _generate_png_bytes(opts)
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas as rl_canvas

        buf = io.BytesIO()
        c = rl_canvas.Canvas(buf, pagesize=A4)
        page_w, page_h = A4
        img_size = min(page_w, page_h) * 0.5
        x = (page_w - img_size) / 2
        y = (page_h - img_size) / 2
        c.drawImage(io.BytesIO(png_bytes), x, y, width=img_size, height=img_size)
        c.showPage()
        c.save()
        return buf.getvalue()
    except ImportError:
        return png_bytes


def generate_datamatrix(opts: DataMatrixOptions, save: bool = True) -> tuple[bytes, str]:
    fmt = opts.export_format.lower()
    if fmt == "svg":
        data = _generate_svg_bytes(opts)
    elif fmt == "pdf":
        data = _generate_pdf_bytes(opts)
    else:
        data = _generate_png_bytes(opts)

    file_path = ""
    if save:
        filename = f"dm_{uuid.uuid4().hex}.{fmt}"
        file_path = os.path.join(settings.GENERATED_DIR, filename)
        with open(file_path, "wb") as fh:
            fh.write(data)

    return data, file_path
