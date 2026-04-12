"""
Pydantic request / response schemas for the FastAPI layer.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field, HttpUrl


# ---------------------------------------------------------------------------
# Dynamic QR
# ---------------------------------------------------------------------------

class CreateDynamicQRRequest(BaseModel):
    user_id: int
    destination_url: str
    title: Optional[str] = None
    expires_in_days: Optional[int] = None
    options: dict[str, Any] = Field(default_factory=dict)


class UpdateDynamicQRRequest(BaseModel):
    new_url: str


class DynamicQRResponse(BaseModel):
    id: UUID
    short_code: str
    redirect_url: str
    destination_url: str
    title: Optional[str]
    is_active: bool
    scan_count: int
    expires_at: Optional[datetime]
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Scan
# ---------------------------------------------------------------------------

class ScanResultSchema(BaseModel):
    code_type: str
    raw_data: str
    content_type: Optional[str]
    is_safe: Optional[bool]
    summary: str
    links: list[str] = []
    extra: dict[str, Any] = {}


# ---------------------------------------------------------------------------
# Code generation
# ---------------------------------------------------------------------------

class GenerateQRRequest(BaseModel):
    data: str
    error_correction: str = "H"
    fg_color: str = "#000000"
    bg_color: str = "#FFFFFF"
    style: str = "square"
    export_format: str = "png"
    size_px: int = 400


class GenerateBarcodeRequest(BaseModel):
    data: str
    barcode_format: str = "code128"
    export_format: str = "png"
    fg_color: str = "#000000"
    bg_color: str = "#FFFFFF"


class GenerateDataMatrixRequest(BaseModel):
    data: str
    export_format: str = "png"
    fg_color: str = "#000000"
    bg_color: str = "#FFFFFF"
    size_px: int = 300


# ---------------------------------------------------------------------------
# Analytics
# ---------------------------------------------------------------------------

class AnalyticsResponse(BaseModel):
    code_id: str
    short_code: str
    title: Optional[str]
    destination_url: str
    is_active: bool
    expires_at: Optional[str]
    created_at: str
    total_scans: int
    device_breakdown: dict[str, int]
    top_countries: dict[str, int]
    recent_scans: list[dict[str, Any]]


# ---------------------------------------------------------------------------
# Admin
# ---------------------------------------------------------------------------

class AdminStatsResponse(BaseModel):
    total_users: int
    premium_users: int
    total_scans: int
    total_generations: int
