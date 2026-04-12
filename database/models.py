"""
SQLAlchemy ORM models.

All tables use async-compatible types (asyncpg driver).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------

class User(Base):
    __tablename__ = "users"

    id = Column(BigInteger, primary_key=True)          # Telegram user id
    username = Column(String(64), nullable=True)
    first_name = Column(String(128), nullable=True)
    last_name = Column(String(128), nullable=True)
    language_code = Column(String(10), default="en")
    is_premium = Column(Boolean, default=False)
    is_banned = Column(Boolean, default=False)
    joined_at = Column(DateTime(timezone=True), server_default=func.now())
    last_active = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now())

    # relationships
    scans = relationship("ScanHistory", back_populates="user", cascade="all, delete-orphan")
    generated_codes = relationship("GeneratedCode", back_populates="user", cascade="all, delete-orphan")
    dynamic_codes = relationship("DynamicCode", back_populates="user", cascade="all, delete-orphan")
    subscriptions = relationship("Subscription", back_populates="user", cascade="all, delete-orphan")
    daily_stats = relationship("DailyUsage", back_populates="user", cascade="all, delete-orphan")


# ---------------------------------------------------------------------------
# Scan history
# ---------------------------------------------------------------------------

class ScanHistory(Base):
    __tablename__ = "scan_history"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    code_type = Column(String(32), nullable=False)      # qr, ean13, code128, datamatrix …
    raw_data = Column(Text, nullable=False)
    content_type = Column(String(32), nullable=True)    # url, product, wifi, contact …
    analysis_result = Column(JSONB, nullable=True)
    is_safe = Column(Boolean, nullable=True)
    source = Column(String(16), default="image")        # image | pdf | camera
    scanned_at = Column(DateTime(timezone=True), server_default=func.now())
    is_favorite = Column(Boolean, default=False)

    user = relationship("User", back_populates="scans")


# ---------------------------------------------------------------------------
# Generated codes
# ---------------------------------------------------------------------------

class GeneratedCode(Base):
    __tablename__ = "generated_codes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    code_type = Column(String(32), nullable=False)      # qr | barcode | datamatrix
    data = Column(Text, nullable=False)
    options = Column(JSONB, nullable=True)              # colors, logo, format …
    file_path = Column(String(512), nullable=True)
    export_format = Column(String(8), default="png")   # png | svg | pdf
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    is_favorite = Column(Boolean, default=False)

    user = relationship("User", back_populates="generated_codes")


# ---------------------------------------------------------------------------
# Dynamic QR codes
# ---------------------------------------------------------------------------

class DynamicCode(Base):
    __tablename__ = "dynamic_codes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    short_code = Column(String(12), unique=True, nullable=False)
    destination_url = Column(Text, nullable=False)
    title = Column(String(256), nullable=True)
    is_active = Column(Boolean, default=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now())
    scan_count = Column(Integer, default=0)
    options = Column(JSONB, nullable=True)              # QR visual options

    user = relationship("User", back_populates="dynamic_codes")
    scan_events = relationship("DynamicScanEvent", back_populates="code", cascade="all, delete-orphan")


class DynamicScanEvent(Base):
    __tablename__ = "dynamic_scan_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code_id = Column(UUID(as_uuid=True), ForeignKey("dynamic_codes.id", ondelete="CASCADE"), nullable=False)
    scanned_at = Column(DateTime(timezone=True), server_default=func.now())
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(Text, nullable=True)
    country = Column(String(64), nullable=True)
    device_type = Column(String(32), nullable=True)     # mobile | desktop | tablet

    code = relationship("DynamicCode", back_populates="scan_events")


# ---------------------------------------------------------------------------
# Subscriptions / payments
# ---------------------------------------------------------------------------

class Subscription(Base):
    __tablename__ = "subscriptions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    plan = Column(String(32), default="free")           # free | premium
    payment_provider = Column(String(32), nullable=True)  # stripe | telegram_stars
    payment_id = Column(String(256), nullable=True)
    amount = Column(Float, nullable=True)
    currency = Column(String(8), nullable=True)
    starts_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=True)
    is_active = Column(Boolean, default=True)

    user = relationship("User", back_populates="subscriptions")


# ---------------------------------------------------------------------------
# Daily usage counters (reset each UTC day)
# ---------------------------------------------------------------------------

class DailyUsage(Base):
    __tablename__ = "daily_usage"
    __table_args__ = (UniqueConstraint("user_id", "date", name="uq_daily_usage"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    date = Column(String(10), nullable=False)           # YYYY-MM-DD
    scans = Column(Integer, default=0)
    generations = Column(Integer, default=0)

    user = relationship("User", back_populates="daily_stats")
