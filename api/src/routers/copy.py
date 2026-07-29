"""Beginner-first account-scoped copy-trading marketplace routes."""

from __future__ import annotations

import asyncio
import hmac
import os
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status

from src.config import config
from src.db.runtime import DatabaseSession
from src.dependencies import get_executor_for_account_id, is_account_runtime_active
from src.models.account import TradingAccount
from src.models.audit import AuditEvent
from src.models.copy import (
    CopyMode,
    CopyRiskPreset,
    CopyRuntimeStatus,
    CopyTraderProfile,
    CopyVolumeMode,
)
from src.repositories import copy as repository
from src.schemas.copy import (
    EmergencyStopRequest,
    LiveActivationRequest,
    NormalizedTradeEventRequest,
    RiskPolicyRequest,
    RuntimeHeartbeatRequest,
    SubscriptionPatch,
    SubscriptionRequest,
    TraderProfilePatch,
    TraderProfileRequest,
)
from src.security import get_current_user
from src.services.copy_worker import RuntimeManagerClient, RuntimeManagerError
from src.symbol_utils import to_base_symbol

router = APIRouter()
internal_router = APIRouter()
CurrentUser = Annotated[dict[str, Any], Depends(get_current_user)]


def _domain_error(error: Exception) -> HTTPException:
    if isinstance(error, PermissionError):
        return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(error))
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error))


async def _prepare(session: DatabaseSession, current_user: dict[str, Any]) -> list[dict[str, Any]]:
    return await repository.ensure_copy_identity(session, current_user)


def _audit(
    session: DatabaseSession,
    *,
    actor_user_id: str | None,
    action: str,
    target_type: str,
    target_id: str,
    details: dict[str, Any] | None = None,
) -> None:
    session.add(
        AuditEvent(
            actor_user_id=actor_user_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            details=details or {},
        )
    )


def _runtime_payload(runtime: Any | None) -> dict[str, Any] | None:
    if runtime is None:
        return None
    return {
        "account_id": str(runtime.account_id),
        "status": runtime.status.value,
        "broker_server": runtime.broker_server,
        "trading_enabled": runtime.trading_enabled,
        "last_heartbeat_at": runtime.last_heartbeat_at.isoformat()
        if runtime.last_heartbeat_at
        else None,
    }


def merge_live_pending_orders(
    traders: list[dict[str, Any]],
    *,
    account_id: str,
    orders: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Attach sanitized live pending instructions to one public trader profile."""
    pending_orders = repository.sanitize_pending_orders(orders)
    for trader in traders:
        if trader.get("account_id") != account_id:
            continue
        trader["pending_orders"] = pending_orders
        trader.setdefault("statistics", {})["pending_order_count"] = len(pending_orders)
        trader["markets"] = list(
            dict.fromkeys(
                [
                    *(str(market).upper() for market in trader.get("markets", [])),
                    *(order["symbol"] for order in pending_orders),
                ]
            )
        )
    return traders


async def _with_active_pending_orders(
    traders: list[dict[str, Any]],
    current_user: dict[str, Any],
) -> list[dict[str, Any]]:
    """Enrich the active account without switching or taking over the MT5 runtime."""
    legacy_account_id = str(current_user.get("active_account_id") or "").strip()
    if not legacy_account_id or not is_account_runtime_active(legacy_account_id):
        return traders

    executor = get_executor_for_account_id(legacy_account_id)
    try:
        orders = await asyncio.to_thread(executor.get_pending_orders)
    except Exception:
        return traders
    return merge_live_pending_orders(
        traders,
        account_id=str(repository.copy_account_uuid(legacy_account_id)),
        orders=orders,
    )


@router.get("/directory")
async def directory(
    session: DatabaseSession,
    current_user: CurrentUser,
    search: str = Query(default="", max_length=120),
    market: str | None = Query(default=None, max_length=40),
) -> dict[str, Any]:
    await _prepare(session, current_user)
    # Apply discovery filters after live enrichment so an account whose only
    # activity is a pending order remains discoverable by that order's market.
    traders = await repository.list_directory(session)
    traders = await _with_active_pending_orders(traders, current_user)
    normalized_search = search.strip().lower()
    if normalized_search:
        traders = [
            trader
            for trader in traders
            if normalized_search
            in " ".join(
                [
                    str(trader.get("display_name") or ""),
                    str(trader.get("description") or ""),
                    *trader.get("markets", []),
                ]
            ).lower()
        ]
    if market:
        normalized_market = to_base_symbol(market.strip())
        traders = [trader for trader in traders if normalized_market in trader.get("markets", [])]
    return {
        "success": True,
        "traders": traders,
        "ranking": "neutral",
    }


@router.get("/overview")
async def overview(session: DatabaseSession, current_user: CurrentUser) -> dict[str, Any]:
    accounts = await _prepare(session, current_user)
    owned = await repository.list_owned_traders(session, current_user["id"])
    owned = await _with_active_pending_orders(owned, current_user)
    subscriptions = await repository.list_subscriptions(session, current_user["id"])
    executions = await repository.list_executions(session, current_user["id"])
    runtimes = []
    for account in accounts:
        runtime = await repository.runtime_for_account(session, account["id"])
        runtimes.append(
            _runtime_payload(runtime) or {"account_id": str(account["id"]), "status": "offline"}
        )
    return {
        "success": True,
        "accounts": [{**item, "id": str(item["id"])} for item in accounts],
        "owned_traders": owned,
        "subscriptions": subscriptions,
        "recent_executions": executions[:20],
        "runtimes": runtimes,
        "live": {
            "feature_enabled": config.features.paper_live_enabled,
            "requires_country_eligibility": True,
        },
    }


@router.get("/traders")
async def owned_traders(session: DatabaseSession, current_user: CurrentUser) -> dict[str, Any]:
    await _prepare(session, current_user)
    traders = await repository.list_owned_traders(session, current_user["id"])
    return {
        "success": True,
        "traders": await _with_active_pending_orders(traders, current_user),
    }


@router.post("/traders")
async def create_trader(
    request: TraderProfileRequest,
    session: DatabaseSession,
    current_user: CurrentUser,
) -> dict[str, Any]:
    await _prepare(session, current_user)
    try:
        profile = await repository.upsert_trader(
            session,
            user_id=current_user["id"],
            account_id=request.account_id,
            display_name=request.display_name,
            description=request.description,
            is_copyable=request.is_copyable,
        )
    except (ValueError, PermissionError) as error:
        raise _domain_error(error) from error
    _audit(
        session,
        actor_user_id=current_user["id"],
        action="copy.trader.updated",
        target_type="copy_trader",
        target_id=str(profile.id),
        details={"is_copyable": profile.is_copyable},
    )
    return {"success": True, "trader": repository.serialize_trader(profile)}


@router.patch("/traders/{trader_id}")
async def update_trader(
    trader_id: UUID,
    request: TraderProfilePatch,
    session: DatabaseSession,
    current_user: CurrentUser,
) -> dict[str, Any]:
    await _prepare(session, current_user)
    try:
        profile = await repository.patch_trader(
            session,
            user_id=current_user["id"],
            trader_id=trader_id,
            changes=request.model_dump(exclude_unset=True),
        )
    except (ValueError, PermissionError) as error:
        raise _domain_error(error) from error
    _audit(
        session,
        actor_user_id=current_user["id"],
        action="copy.trader.updated",
        target_type="copy_trader",
        target_id=str(profile.id),
        details={"is_copyable": profile.is_copyable},
    )
    return {"success": True, "trader": repository.serialize_trader(profile)}


@router.get("/accounts/{account_id}/risk-policy")
async def get_risk_policy(
    account_id: UUID,
    session: DatabaseSession,
    current_user: CurrentUser,
) -> dict[str, Any]:
    await _prepare(session, current_user)
    try:
        policy = await repository.get_or_create_risk_policy(
            session, user_id=current_user["id"], account_id=account_id
        )
    except (ValueError, PermissionError) as error:
        raise _domain_error(error) from error
    return {"success": True, "risk_policy": repository.serialize_risk_policy(policy)}


@router.put("/accounts/{account_id}/risk-policy")
async def put_risk_policy(
    account_id: UUID,
    request: RiskPolicyRequest,
    session: DatabaseSession,
    current_user: CurrentUser,
) -> dict[str, Any]:
    await _prepare(session, current_user)
    try:
        policy = await repository.save_risk_policy(
            session,
            user_id=current_user["id"],
            account_id=account_id,
            values=request.model_dump(),
        )
    except (ValueError, PermissionError) as error:
        raise _domain_error(error) from error
    _audit(
        session,
        actor_user_id=current_user["id"],
        action="copy.risk.updated",
        target_type="trading_account",
        target_id=str(account_id),
        details={
            "daily_loss_limit_amount": policy.daily_loss_limit_amount,
            "max_open_trades": policy.max_open_trades,
            "require_stop_loss": policy.require_stop_loss,
        },
    )
    return {"success": True, "risk_policy": repository.serialize_risk_policy(policy)}


@router.get("/subscriptions")
async def subscriptions(session: DatabaseSession, current_user: CurrentUser) -> dict[str, Any]:
    await _prepare(session, current_user)
    return {
        "success": True,
        "subscriptions": await repository.list_subscriptions(session, current_user["id"]),
    }


@router.post("/subscriptions")
async def create_subscription(
    request: SubscriptionRequest,
    session: DatabaseSession,
    current_user: CurrentUser,
) -> dict[str, Any]:
    await _prepare(session, current_user)
    try:
        subscription = await repository.create_subscription(
            session,
            user_id=current_user["id"],
            trader_id=request.trader_id,
            follower_account_id=request.follower_account_id,
            mode=CopyMode(request.mode),
            risk_preset=CopyRiskPreset(request.risk_preset),
            volume_mode=CopyVolumeMode(request.volume_mode),
            fixed_volume=request.fixed_volume,
            overlap_acknowledged=request.overlap_acknowledged,
            country_code=request.country_code,
            disclosure_version=request.disclosure_version,
        )
    except (ValueError, PermissionError) as error:
        raise _domain_error(error) from error
    _audit(
        session,
        actor_user_id=current_user["id"],
        action="copy.subscription.created",
        target_type="copy_subscription",
        target_id=str(subscription.id),
        details={
            "requested_mode": request.mode,
            "effective_mode": subscription.mode.value,
            "volume_mode": subscription.volume_mode.value,
            "fixed_volume": subscription.fixed_volume,
        },
    )
    return {"success": True, "subscription": repository.serialize_subscription(subscription)}


@router.patch("/subscriptions/{subscription_id}")
async def update_subscription(
    subscription_id: UUID,
    request: SubscriptionPatch,
    session: DatabaseSession,
    current_user: CurrentUser,
) -> dict[str, Any]:
    await _prepare(session, current_user)
    try:
        subscription = await repository.patch_subscription(
            session,
            user_id=current_user["id"],
            subscription_id=subscription_id,
            values=request.model_dump(exclude_unset=True),
        )
    except (ValueError, PermissionError) as error:
        raise _domain_error(error) from error
    _audit(
        session,
        actor_user_id=current_user["id"],
        action="copy.subscription.updated",
        target_type="copy_subscription",
        target_id=str(subscription.id),
        details={"status": subscription.status.value},
    )
    return {"success": True, "subscription": repository.serialize_subscription(subscription)}


@router.post("/subscriptions/{subscription_id}/activate-live")
async def activate_live(
    subscription_id: UUID,
    request: LiveActivationRequest,
    session: DatabaseSession,
    current_user: CurrentUser,
) -> dict[str, Any]:
    await _prepare(session, current_user)
    required_checks = {
        "account_connected",
        "risk_reviewed",
        "trader_available",
        "losses_understood",
    }
    if not config.features.paper_live_enabled:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Live copying is not enabled on this deployment",
        )
    if any(request.checklist.get(item) is not True for item in required_checks):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Complete every live-copying safety check",
        )
    try:
        subscription = await repository.activate_live_subscription(
            session,
            user_id=current_user["id"],
            subscription_id=subscription_id,
            country_code=request.country_code,
            disclosure_version=request.disclosure_version,
        )
    except (ValueError, PermissionError) as error:
        raise _domain_error(error) from error
    _audit(
        session,
        actor_user_id=current_user["id"],
        action="copy.subscription.live_activated",
        target_type="copy_subscription",
        target_id=str(subscription.id),
        details={
            "country_code": request.country_code,
            "disclosure_version": request.disclosure_version,
            "checklist": sorted(required_checks),
        },
    )
    return {"success": True, "subscription": repository.serialize_subscription(subscription)}


@router.get("/executions")
async def executions(session: DatabaseSession, current_user: CurrentUser) -> dict[str, Any]:
    await _prepare(session, current_user)
    return {
        "success": True,
        "executions": await repository.list_executions(session, current_user["id"]),
    }


@router.post("/accounts/{account_id}/emergency-stop")
async def stop_account_copying(
    account_id: UUID,
    request: EmergencyStopRequest,
    session: DatabaseSession,
    current_user: CurrentUser,
) -> dict[str, Any]:
    await _prepare(session, current_user)
    if request.close_positions and request.confirmation != "CLOSE ALL COPIED POSITIONS":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Type the full confirmation before closing copied positions",
        )
    runtime_result: dict[str, Any] | None = None
    try:
        paused = await repository.emergency_stop(
            session, user_id=current_user["id"], account_id=account_id
        )
    except (ValueError, PermissionError) as error:
        raise _domain_error(error) from error
    if request.close_positions:
        try:
            runtime_result = await RuntimeManagerClient().close_all_copied_positions(
                account_id=account_id,
                idempotency_key=f"emergency-close:{account_id}",
            )
        except RuntimeManagerError as error:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=(
                    "No positions were closed. The isolated account runtime is unavailable; "
                    "try again or close positions directly in MT5."
                ),
            ) from error
    _audit(
        session,
        actor_user_id=current_user["id"],
        action=(
            "copy.account.emergency_closed" if request.close_positions else "copy.account.paused"
        ),
        target_type="trading_account",
        target_id=str(account_id),
        details={"subscriptions_paused": len(paused), "runtime_result": runtime_result or {}},
    )
    return {
        "success": True,
        "paused": len(paused),
        "positions_close_requested": request.close_positions,
        "runtime_result": runtime_result,
    }


def _require_runtime_token(authorization: str | None) -> None:
    expected = os.getenv("COPY_RUNTIME_INGEST_TOKEN", "").strip()
    received = (authorization or "").removeprefix("Bearer ").strip()
    if not expected or not received or not hmac.compare_digest(expected, received):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid runtime token"
        )


@internal_router.post("/runtime/heartbeat")
async def runtime_heartbeat(
    request: RuntimeHeartbeatRequest,
    session: DatabaseSession,
    authorization: Annotated[str | None, Header()] = None,
) -> dict[str, Any]:
    _require_runtime_token(authorization)
    if await session.get(TradingAccount, request.account_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Trading account not found"
        )
    try:
        runtime = await repository.upsert_runtime(
            session,
            account_id=request.account_id,
            runtime_ref=request.runtime_ref,
            status=CopyRuntimeStatus(request.status),
            broker_server=request.broker_server,
            trading_enabled=request.trading_enabled,
            details=request.details,
        )
        verified_statistics = request.details.get("verified_statistics")
        markets = request.details.get("markets")
        if isinstance(verified_statistics, dict) and isinstance(markets, list):
            await repository.update_trader_statistics(
                session,
                account_id=request.account_id,
                statistics=verified_statistics,
                markets=[market for market in markets if isinstance(market, str)],
            )
    except (ValueError, PermissionError) as error:
        raise _domain_error(error) from error
    return {"success": True, "runtime": _runtime_payload(runtime)}


@internal_router.post("/events")
async def ingest_event(
    request: NormalizedTradeEventRequest,
    session: DatabaseSession,
    authorization: Annotated[str | None, Header()] = None,
) -> dict[str, Any]:
    _require_runtime_token(authorization)
    trader = await session.get(CopyTraderProfile, request.trader_id)
    if trader is None or trader.account_id != request.source_account_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Trader account not found"
        )
    if not trader.is_copyable and request.action == "open":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Sharing is off, so new copied positions are not accepted",
        )
    values = request.model_dump(exclude={"trader_id", "source_account_id"})
    if values.get("occurred_at") is None:
        values.pop("occurred_at", None)
    event, created = await repository.create_trade_event(
        session, trader_id=request.trader_id, values=values
    )
    return {"success": True, "created": created, "event_id": str(event.id)}
