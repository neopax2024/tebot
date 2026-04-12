"""
Multi-format code detector.

Supported formats:
  QR Code, EAN-8/13, UPC-A/E, Code 39/93/128, ITF, PDF417,
  Aztec, Data Matrix, Codabar

Input sources:
  • Image bytes (JPEG, PNG, WEBP, BMP)
  • PDF (converted per-page via pdf2image)
  • Live frame (bytes from Mini App camera)
"""

from __future__ import annotations

import io
import logging
from dataclasses import dataclass
from typing import Optional

import cv2
import numpy as np
from PIL import Image
from pyzbar import pyzbar

logger = logging.getLogger(__name__)


@dataclass
class DetectionResult:
    code_type: str          # e.g. "QRCODE", "EAN13", "DATAMATRIX"
    raw_data: str
    bounding_box: Optional[tuple[int, int, int, int]] = None   # x, y, w, h
    confidence: float = 1.0


def _pil_to_cv(image: Image.Image) -> np.ndarray:
    """Convert a PIL RGBA/RGB image to a BGR numpy array for OpenCV."""
    img = image.convert("RGB")
    return cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)


def _try_pyzbar(img_cv: np.ndarray) -> list[DetectionResult]:
    """Decode codes using pyzbar (fast, handles most 1-D and QR)."""
    results: list[DetectionResult] = []
    decoded = pyzbar.decode(img_cv)
    for obj in decoded:
        try:
            data = obj.data.decode("utf-8", errors="replace")
        except Exception:
            data = repr(obj.data)
        rect = obj.rect
        results.append(
            DetectionResult(
                code_type=obj.type,        # pyzbar returns e.g. "QRCODE"
                raw_data=data,
                bounding_box=(rect.left, rect.top, rect.width, rect.height),
            )
        )
    return results


def _try_opencv_qr(img_cv: np.ndarray) -> list[DetectionResult]:
    """Secondary QR scan using OpenCV's built-in QRCodeDetector."""
    results: list[DetectionResult] = []
    detector = cv2.QRCodeDetector()
    data, points, _ = detector.detectAndDecode(img_cv)
    if data:
        results.append(DetectionResult(code_type="QRCODE", raw_data=data))
    return results


def _try_wechat_qr(img_cv: np.ndarray) -> list[DetectionResult]:
    """Use OpenCV WeChatQRCode detector if available (handles rotated/distorted)."""
    results: list[DetectionResult] = []
    try:
        detector = cv2.wechat_qrcode_WeChatQRCode()
        texts, _ = detector.detectAndDecode(img_cv)
        for text in texts:
            if text:
                results.append(DetectionResult(code_type="QRCODE", raw_data=text))
    except Exception:
        pass  # wechat_qrcode extension not installed
    return results


def _try_datamatrix(img_cv: np.ndarray) -> list[DetectionResult]:
    """Decode Data Matrix codes using pylibdmtx."""
    results: list[DetectionResult] = []
    try:
        from pylibdmtx.pylibdmtx import decode as dm_decode

        gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)
        pil_gray = Image.fromarray(gray)
        decoded = dm_decode(pil_gray, timeout=2000)
        for obj in decoded:
            try:
                data = obj.data.decode("utf-8", errors="replace")
            except Exception:
                data = repr(obj.data)
            results.append(DetectionResult(code_type="DATAMATRIX", raw_data=data))
    except ImportError:
        logger.debug("pylibdmtx not installed — Data Matrix scanning disabled.")
    except Exception as exc:
        logger.debug("pylibdmtx error: %s", exc)
    return results


def _preprocess_variants(img_cv: np.ndarray) -> list[np.ndarray]:
    """Return several pre-processed versions to improve detection rate."""
    variants = [img_cv]

    # Grayscale
    gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)
    variants.append(gray)

    # Otsu threshold
    _, otsu = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    variants.append(otsu)

    # Adaptive threshold
    adaptive = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2
    )
    variants.append(adaptive)

    # Sharpened
    kernel = np.array([[-1, -1, -1], [-1, 9, -1], [-1, -1, -1]])
    sharpened = cv2.filter2D(gray, -1, kernel)
    variants.append(sharpened)

    return variants


def _deduplicate(results: list[DetectionResult]) -> list[DetectionResult]:
    seen: set[tuple[str, str]] = set()
    unique: list[DetectionResult] = []
    for r in results:
        key = (r.code_type, r.raw_data)
        if key not in seen:
            seen.add(key)
            unique.append(r)
    return unique


def scan_image_bytes(image_bytes: bytes) -> list[DetectionResult]:
    """
    Main entry point — detect all codes in raw image bytes.

    Returns a (possibly empty) list of DetectionResult objects.
    """
    try:
        pil_image = Image.open(io.BytesIO(image_bytes))
    except Exception as exc:
        logger.warning("Failed to open image: %s", exc)
        return []

    img_cv = _pil_to_cv(pil_image)
    all_results: list[DetectionResult] = []

    for variant in _preprocess_variants(img_cv):
        if variant.ndim == 2:
            # Convert grayscale back to BGR for pyzbar if needed
            variant_bgr = cv2.cvtColor(variant, cv2.COLOR_GRAY2BGR)
        else:
            variant_bgr = variant

        all_results.extend(_try_pyzbar(variant_bgr))
        if not all_results:
            all_results.extend(_try_opencv_qr(variant_bgr))
        if not all_results:
            all_results.extend(_try_wechat_qr(variant_bgr))

        if all_results:
            break  # Found something — no need to try more variants

    # Always try Data Matrix (independent pipeline)
    all_results.extend(_try_datamatrix(img_cv))

    return _deduplicate(all_results)


def scan_pdf_bytes(pdf_bytes: bytes) -> list[DetectionResult]:
    """
    Scan every page of a PDF for codes.

    Requires pdf2image + poppler-utils installed.
    """
    try:
        from pdf2image import convert_from_bytes  # type: ignore
    except ImportError:
        logger.warning("pdf2image not installed — PDF scanning disabled.")
        return []

    results: list[DetectionResult] = []
    try:
        pages = convert_from_bytes(pdf_bytes, dpi=200)
        for page_num, page_img in enumerate(pages, start=1):
            img_bytes = io.BytesIO()
            page_img.save(img_bytes, format="PNG")
            page_results = scan_image_bytes(img_bytes.getvalue())
            for r in page_results:
                r.code_type = f"{r.code_type} (PDF p.{page_num})"
            results.extend(page_results)
    except Exception as exc:
        logger.error("PDF scan error: %s", exc)

    return _deduplicate(results)
