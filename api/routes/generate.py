"""
Code generation endpoints (used by the Mini App).

POST /api/generate/qr          — generate QR code
POST /api/generate/barcode     — generate barcode
POST /api/generate/datamatrix  — generate Data Matrix
POST /api/scan                 — scan an uploaded image
"""

from __future__ import annotations

import io
import logging

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse

from api.models.schemas import (
    GenerateBarcodeRequest,
    GenerateDataMatrixRequest,
    GenerateQRRequest,
    ScanResultSchema,
)
from generator.qr_generator import QROptions, generate_qr
from generator.barcode_generator import BarcodeOptions, generate_barcode
from generator.datamatrix_generator import DataMatrixOptions, generate_datamatrix
from scanner.detector import scan_image_bytes
from scanner.analyzer import analyse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["Generation"])


@router.post("/generate/qr")
async def api_generate_qr(body: GenerateQRRequest) -> StreamingResponse:
    try:
        opts = QROptions(
            data=body.data,
            error_correction=body.error_correction,
            fg_color=body.fg_color,
            bg_color=body.bg_color,
            style=body.style,
            export_format=body.export_format,
            size_px=body.size_px,
        )
        data_bytes, _ = generate_qr(opts, save=False)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    media_type = {
        "png": "image/png",
        "svg": "image/svg+xml",
        "pdf": "application/pdf",
    }.get(body.export_format, "application/octet-stream")

    return StreamingResponse(
        io.BytesIO(data_bytes),
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="qrcode.{body.export_format}"'},
    )


@router.post("/generate/barcode")
async def api_generate_barcode(body: GenerateBarcodeRequest) -> StreamingResponse:
    try:
        opts = BarcodeOptions(
            data=body.data,
            barcode_format=body.barcode_format,
            export_format=body.export_format,
            fg_color=body.fg_color,
            bg_color=body.bg_color,
        )
        data_bytes, _ = generate_barcode(opts, save=False)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    media_type = "image/png" if body.export_format == "png" else "image/svg+xml"
    return StreamingResponse(
        io.BytesIO(data_bytes),
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="barcode.{body.export_format}"'},
    )


@router.post("/generate/datamatrix")
async def api_generate_datamatrix(body: GenerateDataMatrixRequest) -> StreamingResponse:
    try:
        opts = DataMatrixOptions(
            data=body.data,
            export_format=body.export_format,
            fg_color=body.fg_color,
            bg_color=body.bg_color,
            size_px=body.size_px,
        )
        data_bytes, _ = generate_datamatrix(opts, save=False)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    return StreamingResponse(
        io.BytesIO(data_bytes),
        media_type="image/png",
        headers={"Content-Disposition": f'attachment; filename="datamatrix.{body.export_format}"'},
    )


@router.post("/scan", response_model=list[ScanResultSchema])
async def api_scan(file: UploadFile = File(...)) -> list[ScanResultSchema]:
    """Scan an uploaded image for codes and return enriched analysis."""
    image_bytes = await file.read()
    if not image_bytes:
        raise HTTPException(status_code=400, detail="Empty file.")

    detected = scan_image_bytes(image_bytes)
    if not detected:
        return []

    results: list[ScanResultSchema] = []
    for item in detected:
        report = await analyse(item.raw_data, item.code_type)
        results.append(
            ScanResultSchema(
                code_type=item.code_type,
                raw_data=item.raw_data,
                content_type=report.content_type,
                is_safe=report.is_safe,
                summary=report.summary,
                links=report.links,
                extra=report.extra,
            )
        )
    return results
