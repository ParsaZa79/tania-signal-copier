"""Request schemas for the beginner-first copy-trading API."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class TraderProfileRequest(BaseModel):
    account_id: UUID
    display_name: str = Field(min_length=2, max_length=120)
    description: str = Field(default="", max_length=600)
    is_copyable: bool = False


class TraderProfilePatch(BaseModel):
    display_name: str | None = Field(default=None, min_length=2, max_length=120)
    description: str | None = Field(default=None, max_length=600)
    is_copyable: bool | None = None


class RiskPolicyRequest(BaseModel):
    preset: Literal["conservative", "balanced", "custom"] = "conservative"
    risk_per_trade_pct: float | None = Field(default=None, gt=0, le=1)
    daily_loss_limit_pct: float | None = Field(default=None, gt=0, le=5)
    daily_loss_limit_amount: float | None = Field(default=None, gt=0, le=1_000_000)
    total_open_risk_pct: float | None = Field(default=None, gt=0, le=5)
    max_open_trades: int | None = Field(default=None, ge=1, le=10)
    require_stop_loss: bool = True
    allowed_symbols: list[str] = Field(default_factory=list, max_length=100)

    @field_validator("allowed_symbols")
    @classmethod
    def clean_symbols(cls, values: list[str]) -> list[str]:
        return list(dict.fromkeys(item.strip().upper() for item in values if item.strip()))


class SubscriptionRequest(BaseModel):
    trader_id: UUID
    follower_account_id: UUID
    mode: Literal["paper", "live"] = "paper"
    risk_preset: Literal["conservative", "balanced", "custom"] = "conservative"
    volume_mode: Literal["fixed", "source"] = "fixed"
    fixed_volume: float = Field(default=0.01, gt=0, le=100, multiple_of=0.01)
    overlap_acknowledged: bool = False
    country_code: str | None = Field(default=None, min_length=2, max_length=2)
    disclosure_version: str | None = Field(default=None, max_length=80)

    @field_validator("country_code")
    @classmethod
    def clean_country(cls, value: str | None) -> str | None:
        return value.upper() if value else None


class SubscriptionPatch(BaseModel):
    status: Literal["active", "paused", "stopping", "stopped"] | None = None
    risk_preset: Literal["conservative", "balanced", "custom"] | None = None
    volume_mode: Literal["fixed", "source"] | None = None
    fixed_volume: float | None = Field(default=None, gt=0, le=100, multiple_of=0.01)
    overlap_acknowledged: bool | None = None


class LiveActivationRequest(BaseModel):
    country_code: str = Field(min_length=2, max_length=2)
    disclosure_version: str = Field(min_length=1, max_length=80)
    checklist: dict[str, bool]

    @field_validator("country_code")
    @classmethod
    def clean_country(cls, value: str) -> str:
        return value.upper()


class RuntimeHeartbeatRequest(BaseModel):
    account_id: UUID
    runtime_ref: str = Field(min_length=1, max_length=160)
    status: Literal["starting", "healthy", "degraded", "offline"]
    broker_server: str | None = Field(default=None, max_length=160)
    trading_enabled: bool = False
    details: dict[str, Any] = Field(default_factory=dict)


class NormalizedTradeEventRequest(BaseModel):
    trader_id: UUID
    source_account_id: UUID
    external_id: str = Field(min_length=1, max_length=200)
    source_ticket: str | None = Field(default=None, max_length=100)
    action: Literal["open", "modify", "reduce", "close"]
    symbol: str = Field(min_length=1, max_length=40)
    side: Literal["buy", "sell"] | None = None
    entry_price: float | None = Field(default=None, gt=0)
    stop_loss: float | None = Field(default=None, gt=0)
    take_profits: list[float] = Field(default_factory=list, max_length=12)
    source_volume: float | None = Field(default=None, gt=0)
    occurred_at: datetime | None = None
    raw_payload: dict[str, Any] = Field(default_factory=dict)

    @field_validator("symbol")
    @classmethod
    def clean_symbol(cls, value: str) -> str:
        return value.strip().upper()


class EmergencyStopRequest(BaseModel):
    close_positions: bool = False
    confirmation: str | None = None
