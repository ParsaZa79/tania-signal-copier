"""Durable account-scoped copy-trading marketplace models."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.db.base import Base
from src.models.common import TimestampMixin
from src.models.user import _enum_values


class CopyMode(StrEnum):
    PAPER = "paper"
    LIVE = "live"


class CopyRiskPreset(StrEnum):
    CONSERVATIVE = "conservative"
    BALANCED = "balanced"
    CUSTOM = "custom"


class CopyVolumeMode(StrEnum):
    FIXED = "fixed"
    SOURCE = "source"


class CopySubscriptionStatus(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    STOPPING = "stopping"
    STOPPED = "stopped"


class CopyTradeAction(StrEnum):
    OPEN = "open"
    MODIFY = "modify"
    REDUCE = "reduce"
    CLOSE = "close"


class CopyEventStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    PROCESSED = "processed"
    FAILED = "failed"


class CopyExecutionStatus(StrEnum):
    ACCEPTED = "accepted"
    BLOCKED = "blocked"
    PENDING = "pending"
    EXECUTED = "executed"
    FAILED = "failed"


class CopyRuntimeStatus(StrEnum):
    OFFLINE = "offline"
    STARTING = "starting"
    HEALTHY = "healthy"
    DEGRADED = "degraded"


class CopyLegacyArchive(Base):
    """Immutable paper-only snapshot imported from the retired JSON store."""

    __tablename__ = "copy_legacy_archive"
    __table_args__ = (
        UniqueConstraint("record_type", "legacy_id", name="uq_copy_legacy_archive_record"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    record_type: Mapped[str] = mapped_column(String(40), nullable=False)
    legacy_id: Mapped[str] = mapped_column(String(200), nullable=False)
    owner_user_id: Mapped[str | None] = mapped_column(String(128), index=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    imported_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    paper_only: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )


class CopyTraderProfile(TimestampMixin, Base):
    """Public opt-in profile backed by one connected MT5 account."""

    __tablename__ = "copy_trader_profiles"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    account_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("app.trading_accounts.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    owner_user_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey(
            "app.app_user_profiles.auth_subject",
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        nullable=False,
        index=True,
    )
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")
    is_copyable: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    markets: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb")
    )
    statistics: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )
    stats_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class CopyRiskPolicy(TimestampMixin, Base):
    """Account-level defaults and hard limits for copied trades."""

    __tablename__ = "copy_risk_policies"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    account_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("app.trading_accounts.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    preset: Mapped[CopyRiskPreset] = mapped_column(
        Enum(
            CopyRiskPreset,
            name="copy_risk_preset",
            native_enum=False,
            create_constraint=True,
            values_callable=_enum_values,
        ),
        nullable=False,
        default=CopyRiskPreset.CONSERVATIVE,
        server_default=CopyRiskPreset.CONSERVATIVE.value,
    )
    risk_per_trade_pct: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.25, server_default="0.25"
    )
    daily_loss_limit_pct: Mapped[float] = mapped_column(
        Float, nullable=False, default=1.0, server_default="1"
    )
    daily_loss_limit_amount: Mapped[float | None] = mapped_column(Float)
    total_open_risk_pct: Mapped[float] = mapped_column(
        Float, nullable=False, default=1.0, server_default="1"
    )
    max_open_trades: Mapped[int] = mapped_column(
        Integer, nullable=False, default=3, server_default="3"
    )
    require_stop_loss: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )
    allowed_symbols: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb")
    )


class CopySubscription(TimestampMixin, Base):
    """One trader copied into one explicit follower MT5 account."""

    __tablename__ = "copy_subscriptions"
    __table_args__ = (
        UniqueConstraint(
            "trader_id", "follower_account_id", name="uq_copy_subscription_trader_account"
        ),
        Index("ix_copy_subscriptions_follower_status", "follower_user_id", "status"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    trader_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("app.copy_trader_profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    follower_account_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("app.trading_accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    follower_user_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey(
            "app.app_user_profiles.auth_subject",
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        nullable=False,
        index=True,
    )
    mode: Mapped[CopyMode] = mapped_column(
        Enum(
            CopyMode,
            name="copy_mode",
            native_enum=False,
            create_constraint=True,
            values_callable=_enum_values,
        ),
        nullable=False,
        default=CopyMode.PAPER,
        server_default=CopyMode.PAPER.value,
    )
    status: Mapped[CopySubscriptionStatus] = mapped_column(
        Enum(
            CopySubscriptionStatus,
            name="copy_subscription_status",
            native_enum=False,
            create_constraint=True,
            values_callable=_enum_values,
        ),
        nullable=False,
        default=CopySubscriptionStatus.ACTIVE,
        server_default=CopySubscriptionStatus.ACTIVE.value,
    )
    risk_preset: Mapped[CopyRiskPreset] = mapped_column(
        Enum(
            CopyRiskPreset,
            name="copy_subscription_risk_preset",
            native_enum=False,
            create_constraint=True,
            values_callable=_enum_values,
        ),
        nullable=False,
        default=CopyRiskPreset.CONSERVATIVE,
        server_default=CopyRiskPreset.CONSERVATIVE.value,
    )
    volume_mode: Mapped[CopyVolumeMode] = mapped_column(
        Enum(
            CopyVolumeMode,
            name="copy_volume_mode",
            native_enum=False,
            create_constraint=True,
            values_callable=_enum_values,
        ),
        nullable=False,
        default=CopyVolumeMode.FIXED,
        server_default=CopyVolumeMode.FIXED.value,
    )
    fixed_volume: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.01, server_default="0.01"
    )
    overlap_acknowledged: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    disclosure_version: Mapped[str | None] = mapped_column(String(80))
    country_code: Mapped[str | None] = mapped_column(String(2))
    live_activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class CopyTradeEvent(TimestampMixin, Base):
    """Normalized, idempotent lifecycle event observed from a trader account."""

    __tablename__ = "copy_trade_events"
    __table_args__ = (
        UniqueConstraint("trader_id", "external_id", name="uq_copy_event_trader_external"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    trader_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("app.copy_trader_profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    external_id: Mapped[str] = mapped_column(String(200), nullable=False)
    source_ticket: Mapped[str | None] = mapped_column(String(100))
    action: Mapped[CopyTradeAction] = mapped_column(
        Enum(
            CopyTradeAction,
            name="copy_trade_action",
            native_enum=False,
            create_constraint=True,
            values_callable=_enum_values,
        ),
        nullable=False,
    )
    symbol: Mapped[str] = mapped_column(String(40), nullable=False)
    side: Mapped[str | None] = mapped_column(String(8))
    entry_price: Mapped[float | None] = mapped_column(Float)
    stop_loss: Mapped[float | None] = mapped_column(Float)
    take_profits: Mapped[list[float]] = mapped_column(
        JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb")
    )
    source_volume: Mapped[float | None] = mapped_column(Float)
    status: Mapped[CopyEventStatus] = mapped_column(
        Enum(
            CopyEventStatus,
            name="copy_event_status",
            native_enum=False,
            create_constraint=True,
            values_callable=_enum_values,
        ),
        nullable=False,
        default=CopyEventStatus.PENDING,
        server_default=CopyEventStatus.PENDING.value,
    )
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    raw_payload: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )


class CopyOutboxEvent(Base):
    """Durable work record for one normalized source event."""

    __tablename__ = "copy_outbox_events"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    trade_event_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("app.copy_trade_events.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    status: Mapped[str] = mapped_column(
        String(24), nullable=False, default="pending", server_default="pending"
    )
    attempts: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    next_attempt_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    last_error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class CopyExecution(TimestampMixin, Base):
    """Risk decision and broker result for one follower subscription."""

    __tablename__ = "copy_executions"
    __table_args__ = (
        UniqueConstraint("trade_event_id", "subscription_id", name="uq_copy_execution_event_sub"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    trade_event_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("app.copy_trade_events.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    subscription_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("app.copy_subscriptions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    follower_account_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("app.trading_accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    mode: Mapped[CopyMode] = mapped_column(
        Enum(
            CopyMode,
            name="copy_execution_mode",
            native_enum=False,
            create_constraint=True,
            values_callable=_enum_values,
        ),
        nullable=False,
    )
    status: Mapped[CopyExecutionStatus] = mapped_column(
        Enum(
            CopyExecutionStatus,
            name="copy_execution_status",
            native_enum=False,
            create_constraint=True,
            values_callable=_enum_values,
        ),
        nullable=False,
    )
    desired_volume: Mapped[float | None] = mapped_column(Float)
    actual_volume: Mapped[float | None] = mapped_column(Float)
    blocked_reason: Mapped[str | None] = mapped_column(String(120))
    target_ticket: Mapped[str | None] = mapped_column(String(100))
    realized_pnl: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0, server_default="0"
    )
    broker_result: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )


class CopyTicketMapping(TimestampMixin, Base):
    """Source-to-follower broker ticket map used for later lifecycle events."""

    __tablename__ = "copy_ticket_mappings"
    __table_args__ = (
        UniqueConstraint(
            "subscription_id", "source_ticket", name="uq_copy_ticket_subscription_source"
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    subscription_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("app.copy_subscriptions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_ticket: Mapped[str] = mapped_column(String(100), nullable=False)
    target_ticket: Mapped[str] = mapped_column(String(100), nullable=False)
    symbol: Mapped[str] = mapped_column(String(40), nullable=False)
    is_open: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )


class CopyRuntime(TimestampMixin, Base):
    """Secret-free health state for one isolated managed MT5 runtime."""

    __tablename__ = "copy_runtimes"

    account_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("app.trading_accounts.id", ondelete="CASCADE"),
        primary_key=True,
    )
    status: Mapped[CopyRuntimeStatus] = mapped_column(
        Enum(
            CopyRuntimeStatus,
            name="copy_runtime_status",
            native_enum=False,
            create_constraint=True,
            values_callable=_enum_values,
        ),
        nullable=False,
        default=CopyRuntimeStatus.OFFLINE,
        server_default=CopyRuntimeStatus.OFFLINE.value,
    )
    runtime_ref: Mapped[str | None] = mapped_column(String(160))
    broker_server: Mapped[str | None] = mapped_column(String(160))
    trading_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    last_heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    details: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )


class CopyJurisdictionPolicy(TimestampMixin, Base):
    """Country-by-country live eligibility configuration."""

    __tablename__ = "copy_jurisdiction_policies"

    country_code: Mapped[str] = mapped_column(String(2), primary_key=True)
    live_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    disclosure_version: Mapped[str | None] = mapped_column(String(80))
    requirements: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )
