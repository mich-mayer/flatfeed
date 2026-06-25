from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Float,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from flatfeed.listing_status import UNPARSED_STATUS


class Base(DeclarativeBase):
    pass


class SourceCompany(Base):
    __tablename__ = "source_companies"

    company_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(80), unique=True, nullable=False, index=True)
    base_url: Mapped[str] = mapped_column(String(255), nullable=False)
    parser_status: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
        default="planned",
    )


class User(Base):
    __tablename__ = "users"

    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    raw_input: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    parsed_preferences: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    filter_updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )


class Listing(Base):
    __tablename__ = "listings"

    listing_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_company: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    url: Mapped[str] = mapped_column(String(1024), unique=True, nullable=False, index=True)
    title: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    image_url: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    address: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    postal_code: Mapped[Optional[str]] = mapped_column(String(5), nullable=True, index=True)
    district: Mapped[Optional[str]] = mapped_column(String(120), nullable=True, index=True)
    floor: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    rooms: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    rent_kalt: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    rent_warm: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    latitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    longitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    transport_walk: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    source_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        String(80),
        nullable=False,
        default=UNPARSED_STATUS,
        index=True,
    )
    parsed_constraints: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        index=True,
    )
    last_seen_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True,
        index=True,
    )
    last_checked_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )


class APILog(Base):
    __tablename__ = "api_logs"

    log_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    target_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    endpoint_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    prompt_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_cost_usd: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        index=True,
    )


class SentListingNotification(Base):
    __tablename__ = "sent_listing_notifications"
    __table_args__ = (
        UniqueConstraint("user_id", "listing_id", name="uq_sent_listing_user_listing"),
    )

    notification_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    listing_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    sent_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        index=True,
    )


class IngestionRun(Base):
    __tablename__ = "ingestion_runs"

    run_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_company: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    trigger_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    listings_found: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    saved_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    removed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    parsed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    transport_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_type: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    alert_sent: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        index=True,
    )
    finished_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True,
        index=True,
    )
    duration_seconds: Mapped[Optional[float]] = mapped_column(Float, nullable=True)


class AIQAReview(Base):
    __tablename__ = "ai_qa_reviews"
    __table_args__ = (
        UniqueConstraint(
            "listing_id",
            "qa_prompt_version",
            name="uq_ai_qa_reviews_listing_version",
        ),
    )

    review_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    listing_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    listing_url: Mapped[str] = mapped_column(String(1024), nullable=False)
    source_company: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    trigger_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    qa_prompt_version: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
        default="v1",
        index=True,
    )
    raw_text_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    parser_snapshot_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    parser_snapshot: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)
    ai_result: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)
    risk_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0, index=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    parser_result_correct: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    should_alert_admin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    alert_sent: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    feedback_status: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
        default="pending",
        index=True,
    )
    feedback_by: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    feedback_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    prompt_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_cost_usd: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        index=True,
    )
