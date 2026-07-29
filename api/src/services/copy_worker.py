"""Durable copy-event worker and risk-based sizing helpers."""

from __future__ import annotations

import asyncio
import json
import os
from dataclasses import dataclass
from typing import Any
from urllib import error, request
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.db.session import session_scope
from src.models.copy import (
    CopyEventStatus,
    CopyExecution,
    CopyExecutionStatus,
    CopyMode,
    CopyOutboxEvent,
    CopyRiskPolicy,
    CopyRuntime,
    CopyRuntimeStatus,
    CopySubscription,
    CopySubscriptionStatus,
    CopyTicketMapping,
    CopyTradeAction,
    CopyTradeEvent,
    CopyVolumeMode,
)


@dataclass(frozen=True, slots=True)
class RiskSizingResult:
    volume: float | None
    blocked_reason: str | None


def evaluate_risk_limits(
    *,
    balance: float,
    daily_copy_pnl: float,
    current_open_risk_pct: float,
    next_trade_risk_pct: float,
    daily_loss_limit_pct: float,
    total_open_risk_pct: float,
) -> str | None:
    """Return a stable blocking reason when account-level copy limits are reached."""
    if balance <= 0:
        return "account_balance_unavailable"
    daily_loss_pct = max(0.0, -daily_copy_pnl) / balance * 100
    if daily_loss_pct >= daily_loss_limit_pct:
        return "daily_loss_limit_reached"
    if current_open_risk_pct + next_trade_risk_pct > total_open_risk_pct:
        return "combined_open_risk_limit_reached"
    return None


def evaluate_daily_loss_limit(
    *,
    daily_copy_pnl: float,
    daily_loss_limit_amount: float | None,
    balance: float,
    legacy_daily_loss_limit_pct: float,
) -> str | None:
    """Evaluate the dollar protection, with percentage fallback for old policies."""
    daily_copy_loss = max(0.0, -daily_copy_pnl)
    if daily_loss_limit_amount is not None:
        return "daily_loss_limit_reached" if daily_copy_loss >= daily_loss_limit_amount else None
    if balance <= 0:
        return "account_balance_unavailable"
    if daily_copy_loss / balance * 100 >= legacy_daily_loss_limit_pct:
        return "daily_loss_limit_reached"
    return None


def calculate_risk_volume(
    *,
    balance: float,
    risk_pct: float,
    entry_price: float | None,
    stop_loss: float | None,
    value_per_price_unit_per_lot: float | None,
    volume_min: float = 0.01,
    volume_max: float = 100.0,
    volume_step: float = 0.01,
) -> RiskSizingResult:
    """Size a position so its stop-loss outcome fits the selected balance percentage."""
    if stop_loss is None or entry_price is None:
        return RiskSizingResult(None, "stop_loss_required")
    if balance <= 0:
        return RiskSizingResult(None, "account_balance_unavailable")
    distance = abs(entry_price - stop_loss)
    if distance <= 0:
        return RiskSizingResult(None, "invalid_stop_loss")
    if not value_per_price_unit_per_lot or value_per_price_unit_per_lot <= 0:
        return RiskSizingResult(None, "symbol_spec_unavailable")
    risk_amount = balance * (risk_pct / 100.0)
    raw_volume = risk_amount / (distance * value_per_price_unit_per_lot)
    steps = int(raw_volume / volume_step)
    rounded = steps * volume_step
    if rounded < volume_min:
        return RiskSizingResult(None, "trade_too_small_for_broker")
    if rounded > volume_max:
        rounded = volume_max
    return RiskSizingResult(round(rounded, 8), None)


def select_copy_volume(
    *,
    volume_mode: CopyVolumeMode,
    fixed_volume: float,
    source_volume: float | None,
    volume_min: float = 0.01,
    volume_max: float = 100.0,
    volume_step: float = 0.01,
) -> RiskSizingResult:
    """Validate the user's explicit lot choice against receiving-broker constraints."""
    if volume_mode is CopyVolumeMode.SOURCE:
        if source_volume is None or source_volume <= 0:
            return RiskSizingResult(None, "source_volume_required")
        requested = source_volume
    else:
        if fixed_volume <= 0:
            return RiskSizingResult(None, "fixed_volume_required")
        requested = fixed_volume

    if requested < volume_min:
        return RiskSizingResult(None, "copy_volume_below_broker_minimum")
    if requested > volume_max:
        return RiskSizingResult(None, "copy_volume_above_broker_maximum")
    if volume_step <= 0:
        return RiskSizingResult(None, "broker_volume_step_unavailable")

    normalized = round(requested / volume_step) * volume_step
    if abs(normalized - requested) > max(1e-8, volume_step * 1e-6):
        return RiskSizingResult(None, "copy_volume_not_supported_by_broker")
    return RiskSizingResult(round(normalized, 8), None)


class RuntimeManagerError(RuntimeError):
    pass


class RuntimeManagerClient:
    """Restricted client for the isolated runtime control plane."""

    def __init__(self) -> None:
        self.base_url = os.getenv("COPY_RUNTIME_MANAGER_URL", "").strip().rstrip("/")
        self.token = os.getenv("COPY_RUNTIME_MANAGER_TOKEN", "").strip()

    @property
    def configured(self) -> bool:
        return self.base_url.startswith(("https://", "http://copy-runtime-manager")) and bool(
            self.token
        )

    async def execute(
        self, *, account_id: UUID, payload: dict[str, Any], idempotency_key: str
    ) -> dict[str, Any]:
        if not self.configured:
            raise RuntimeManagerError("runtime_manager_unavailable")

        def send() -> dict[str, Any]:
            body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
            outbound = request.Request(
                f"{self.base_url}/v1/accounts/{account_id}/orders",
                data=body,
                method="POST",
                headers={
                    "Authorization": f"Bearer {self.token}",
                    "Content-Type": "application/json",
                    "Idempotency-Key": idempotency_key,
                },
            )
            try:
                with request.urlopen(outbound, timeout=10) as response:
                    result = json.loads(response.read().decode("utf-8"))
            except (error.URLError, TimeoutError, json.JSONDecodeError) as exc:
                raise RuntimeManagerError("runtime_execution_failed") from exc
            if not isinstance(result, dict) or not result.get("success"):
                raise RuntimeManagerError("runtime_execution_rejected")
            return result

        return await asyncio.to_thread(send)

    async def close_all_copied_positions(
        self, *, account_id: UUID, idempotency_key: str
    ) -> dict[str, Any]:
        """Ask the isolated runtime to close only copy-created positions."""
        if not self.configured:
            raise RuntimeManagerError("runtime_manager_unavailable")

        def send() -> dict[str, Any]:
            outbound = request.Request(
                f"{self.base_url}/v1/accounts/{account_id}/emergency-close",
                data=b"{}",
                method="POST",
                headers={
                    "Authorization": f"Bearer {self.token}",
                    "Content-Type": "application/json",
                    "Idempotency-Key": idempotency_key,
                },
            )
            try:
                with request.urlopen(outbound, timeout=20) as response:
                    result = json.loads(response.read().decode("utf-8"))
            except (error.URLError, TimeoutError, json.JSONDecodeError) as exc:
                raise RuntimeManagerError("runtime_emergency_close_failed") from exc
            if not isinstance(result, dict) or not result.get("success"):
                raise RuntimeManagerError("runtime_emergency_close_rejected")
            return result

        return await asyncio.to_thread(send)


async def _account_open_ticket_count(session: AsyncSession, account_id: UUID) -> int:
    value = await session.scalar(
        select(func.count())
        .select_from(CopyTicketMapping)
        .join(
            CopySubscription,
            CopySubscription.id == CopyTicketMapping.subscription_id,
        )
        .where(
            CopySubscription.follower_account_id == account_id,
            CopyTicketMapping.is_open.is_(True),
        )
    )
    return int(value or 0)


async def _subscription_open_ticket_count(session: AsyncSession, subscription_id: UUID) -> int:
    value = await session.scalar(
        select(func.count())
        .select_from(CopyTicketMapping)
        .where(
            CopyTicketMapping.subscription_id == subscription_id,
            CopyTicketMapping.is_open.is_(True),
        )
    )
    return int(value or 0)


async def _risk_decision(
    session: AsyncSession,
    *,
    event: CopyTradeEvent,
    subscription: CopySubscription,
    policy: CopyRiskPolicy,
    runtime: CopyRuntime | None,
) -> RiskSizingResult:
    if event.action is not CopyTradeAction.OPEN:
        return RiskSizingResult(None, None)
    if subscription.status is not CopySubscriptionStatus.ACTIVE:
        return RiskSizingResult(None, "new_trades_paused")
    if policy.require_stop_loss and event.stop_loss is None:
        return RiskSizingResult(None, "stop_loss_required")
    if policy.allowed_symbols and event.symbol not in policy.allowed_symbols:
        return RiskSizingResult(None, "symbol_not_allowed")
    if (
        await _account_open_ticket_count(session, subscription.follower_account_id)
        >= policy.max_open_trades
    ):
        return RiskSizingResult(None, "open_trade_limit_reached")
    details = runtime.details if runtime else {}
    daily_limit_reason = evaluate_daily_loss_limit(
        daily_copy_pnl=float(details.get("daily_copy_pnl") or 0),
        daily_loss_limit_amount=policy.daily_loss_limit_amount,
        balance=float(details.get("balance") or 0),
        legacy_daily_loss_limit_pct=policy.daily_loss_limit_pct,
    )
    if daily_limit_reason:
        return RiskSizingResult(None, daily_limit_reason)

    specs = details.get("symbol_specs") if isinstance(details, dict) else {}
    symbol_spec = specs.get(event.symbol, {}) if isinstance(specs, dict) else {}
    return select_copy_volume(
        volume_mode=subscription.volume_mode,
        fixed_volume=subscription.fixed_volume,
        source_volume=event.source_volume,
        volume_min=float(symbol_spec.get("volume_min") or 0.01),
        volume_max=float(symbol_spec.get("volume_max") or 100),
        volume_step=float(symbol_spec.get("volume_step") or 0.01),
    )


async def _existing_mapping(
    session: AsyncSession, subscription_id: UUID, source_ticket: str | None
) -> CopyTicketMapping | None:
    if not source_ticket:
        return None
    return await session.scalar(
        select(CopyTicketMapping).where(
            CopyTicketMapping.subscription_id == subscription_id,
            CopyTicketMapping.source_ticket == source_ticket,
        )
    )


async def _process_subscription(
    session: AsyncSession,
    *,
    event: CopyTradeEvent,
    subscription: CopySubscription,
    runtime_client: RuntimeManagerClient,
) -> None:
    existing = await session.scalar(
        select(CopyExecution).where(
            CopyExecution.trade_event_id == event.id,
            CopyExecution.subscription_id == subscription.id,
        )
    )
    if existing is not None:
        return
    if (
        event.action is CopyTradeAction.OPEN
        and subscription.status is not CopySubscriptionStatus.ACTIVE
    ):
        return
    if (
        event.action is not CopyTradeAction.OPEN
        and subscription.status is CopySubscriptionStatus.STOPPED
    ):
        return

    policy = await session.scalar(
        select(CopyRiskPolicy).where(CopyRiskPolicy.account_id == subscription.follower_account_id)
    )
    if policy is None:
        execution = CopyExecution(
            trade_event_id=event.id,
            subscription_id=subscription.id,
            follower_account_id=subscription.follower_account_id,
            mode=subscription.mode,
            status=CopyExecutionStatus.BLOCKED,
            blocked_reason="risk_policy_required",
        )
        session.add(execution)
        return

    runtime = await session.get(CopyRuntime, subscription.follower_account_id)
    sizing = await _risk_decision(
        session,
        event=event,
        subscription=subscription,
        policy=policy,
        runtime=runtime,
    )
    mapping = await _existing_mapping(session, subscription.id, event.source_ticket)
    if event.action is not CopyTradeAction.OPEN and mapping is None:
        sizing = RiskSizingResult(None, "copied_position_not_found")

    execution = CopyExecution(
        trade_event_id=event.id,
        subscription_id=subscription.id,
        follower_account_id=subscription.follower_account_id,
        mode=subscription.mode,
        status=CopyExecutionStatus.BLOCKED
        if sizing.blocked_reason
        else CopyExecutionStatus.ACCEPTED,
        desired_volume=sizing.volume,
        blocked_reason=sizing.blocked_reason,
    )
    session.add(execution)
    await session.flush()
    if sizing.blocked_reason:
        return

    target_ticket = mapping.target_ticket if mapping else None
    if subscription.mode is CopyMode.PAPER:
        target_ticket = target_ticket or f"paper:{execution.id}"
        execution.status = CopyExecutionStatus.EXECUTED
        execution.actual_volume = sizing.volume
        execution.target_ticket = target_ticket
        execution.broker_result = {"volume_mode": subscription.volume_mode.value}
    else:
        if (
            runtime is None
            or runtime.status is not CopyRuntimeStatus.HEALTHY
            or not runtime.trading_enabled
        ):
            execution.status = CopyExecutionStatus.FAILED
            execution.blocked_reason = "runtime_unavailable"
            return
        payload = {
            "action": event.action.value,
            "symbol": event.symbol,
            "side": event.side,
            "volume": sizing.volume,
            "entry_price": event.entry_price,
            "stop_loss": event.stop_loss,
            "take_profits": event.take_profits,
            "target_ticket": target_ticket,
        }
        try:
            result = await runtime_client.execute(
                account_id=subscription.follower_account_id,
                payload=payload,
                idempotency_key=str(execution.id),
            )
        except RuntimeManagerError as exc:
            execution.status = CopyExecutionStatus.FAILED
            execution.blocked_reason = str(exc)
            return
        execution.status = CopyExecutionStatus.EXECUTED
        execution.actual_volume = result.get("volume") or sizing.volume
        execution.target_ticket = str(result.get("ticket") or target_ticket or "") or None
        execution.broker_result = {
            key: result.get(key) for key in ("retcode", "message") if key in result
        }
        execution.broker_result["volume_mode"] = subscription.volume_mode.value
        target_ticket = execution.target_ticket

    if event.action is CopyTradeAction.OPEN and event.source_ticket and target_ticket:
        session.add(
            CopyTicketMapping(
                subscription_id=subscription.id,
                source_ticket=event.source_ticket,
                target_ticket=target_ticket,
                symbol=event.symbol,
            )
        )
    elif event.action is CopyTradeAction.CLOSE and mapping is not None:
        mapping.is_open = False
        await session.flush()
        if (
            subscription.status is CopySubscriptionStatus.STOPPING
            and await _subscription_open_ticket_count(session, subscription.id) == 0
        ):
            subscription.status = CopySubscriptionStatus.STOPPED


async def process_pending_once(
    session: AsyncSession, runtime_client: RuntimeManagerClient | None = None
) -> int:
    """Claim and process one outbox item, returning the number claimed."""
    outbox = await session.scalar(
        select(CopyOutboxEvent)
        .where(CopyOutboxEvent.status == "pending")
        .order_by(CopyOutboxEvent.created_at)
        .with_for_update(skip_locked=True)
        .limit(1)
    )
    if outbox is None:
        return 0
    outbox.status = "processing"
    outbox.attempts += 1
    event = await session.get(CopyTradeEvent, outbox.trade_event_id)
    if event is None:
        outbox.status = "failed"
        outbox.last_error = "trade_event_missing"
        return 1
    event.status = CopyEventStatus.PROCESSING
    subscriptions = (
        await session.scalars(
            select(CopySubscription).where(
                CopySubscription.trader_id == event.trader_id,
                CopySubscription.status.in_(
                    [
                        CopySubscriptionStatus.ACTIVE,
                        CopySubscriptionStatus.PAUSED,
                        CopySubscriptionStatus.STOPPING,
                    ]
                ),
            )
        )
    ).all()
    client = runtime_client or RuntimeManagerClient()
    for subscription in subscriptions:
        await _process_subscription(
            session, event=event, subscription=subscription, runtime_client=client
        )
    event.status = CopyEventStatus.PROCESSED
    outbox.status = "processed"
    return 1


async def run_copy_worker(
    session_factory: async_sessionmaker[AsyncSession], *, poll_seconds: float = 1.0
) -> None:
    """Continuously drain durable events until the application shuts down."""
    while True:
        claimed = 0
        try:
            async with session_scope(session_factory) as session:
                claimed = await process_pending_once(session)
        except asyncio.CancelledError:
            raise
        except Exception:
            await asyncio.sleep(max(poll_seconds, 1.0))
        if not claimed:
            await asyncio.sleep(poll_seconds)
