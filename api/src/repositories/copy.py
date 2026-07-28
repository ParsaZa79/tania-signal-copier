"""PostgreSQL repository operations for the copy-trading marketplace."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid5

from sqlalchemy import String, func, or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.account_store import list_user_accounts
from src.models.account import AccountMembership, AccountStatus, MembershipRole, TradingAccount
from src.models.copy import (
    CopyExecution,
    CopyJurisdictionPolicy,
    CopyMode,
    CopyOutboxEvent,
    CopyRiskPolicy,
    CopyRiskPreset,
    CopyRuntime,
    CopyRuntimeStatus,
    CopySubscription,
    CopySubscriptionStatus,
    CopyTradeEvent,
    CopyTraderProfile,
)
from src.models.user import UserRole, UserStatus
from src.repositories.users import reconcile_verified_user_profile

RISK_PRESETS: dict[CopyRiskPreset, dict[str, float | int]] = {
    CopyRiskPreset.CONSERVATIVE: {
        "risk_per_trade_pct": 0.25,
        "daily_loss_limit_pct": 1.0,
        "total_open_risk_pct": 1.0,
        "max_open_trades": 3,
    },
    CopyRiskPreset.BALANCED: {
        "risk_per_trade_pct": 0.5,
        "daily_loss_limit_pct": 2.0,
        "total_open_risk_pct": 2.5,
        "max_open_trades": 5,
    },
    CopyRiskPreset.CUSTOM: {
        "risk_per_trade_pct": 0.25,
        "daily_loss_limit_pct": 1.0,
        "total_open_risk_pct": 1.0,
        "max_open_trades": 3,
    },
}


def copy_account_uuid(legacy_account_id: str) -> UUID:
    """Return the stable PostgreSQL id for one legacy account identifier."""
    return uuid5(NAMESPACE_URL, f"trading-signal-copier:account:{legacy_account_id}")


def _role(value: object) -> UserRole:
    try:
        return UserRole(str(value))
    except ValueError:
        return UserRole.TRADER


async def ensure_copy_identity(
    session: AsyncSession, current_user: dict[str, Any]
) -> list[dict[str, Any]]:
    """Idempotently bridge existing dashboard users/accounts into app-owned tables."""
    user_id = str(current_user["id"])
    email = str(current_user.get("email") or f"{user_id}@local.invalid").lower()
    await reconcile_verified_user_profile(
        session,
        auth_subject=user_id,
        email=email,
        role=_role(current_user.get("role")),
        status=UserStatus.ACTIVE,
    )

    bridged: list[dict[str, Any]] = []
    for legacy in list_user_accounts(user_id):
        account_id = copy_account_uuid(str(legacy["id"]))
        account = await session.get(TradingAccount, account_id)
        desired_status = (
            AccountStatus.ACTIVE if legacy.get("setup_complete") else AccountStatus.PENDING_SETUP
        )
        if account is None:
            account = TradingAccount(
                id=account_id,
                name=str(legacy.get("name") or "Trading Account"),
                status=desired_status,
            )
            session.add(account)
            await session.flush()
        else:
            account.name = str(legacy.get("name") or account.name)
            account.status = desired_status

        membership_statement = (
            pg_insert(AccountMembership)
            .values(account_id=account_id, user_id=user_id, role=MembershipRole.OWNER.value)
            .on_conflict_do_nothing(index_elements=["account_id", "user_id"])
        )
        await session.execute(membership_statement)
        bridged.append(
            {
                "id": account_id,
                "legacy_id": str(legacy["id"]),
                "name": account.name,
                "status": account.status.value,
                "setup_complete": bool(legacy.get("setup_complete")),
            }
        )
    await session.flush()
    return bridged


async def require_account_role(
    session: AsyncSession,
    *,
    user_id: str,
    account_id: UUID,
    write: bool = False,
) -> AccountMembership:
    membership = await session.get(AccountMembership, (account_id, user_id))
    if membership is None:
        raise PermissionError("Trading account access required")
    if write and membership.role is MembershipRole.VIEWER:
        raise PermissionError("Trading account operator access required")
    return membership


async def _flush_and_refresh(session: AsyncSession, record: Any) -> None:
    """Load server-managed timestamps before synchronous response serialization."""
    await session.flush()
    await session.refresh(record)


def serialize_trader(profile: CopyTraderProfile, follower_count: int = 0) -> dict[str, Any]:
    stats = profile.statistics or {}
    return {
        "id": str(profile.id),
        "account_id": str(profile.account_id),
        "owner_user_id": profile.owner_user_id,
        "display_name": profile.display_name,
        "description": profile.description,
        "is_copyable": profile.is_copyable,
        "markets": profile.markets or [],
        "statistics": {
            "return_90d_pct": stats.get("return_90d_pct"),
            "max_drawdown_pct": stats.get("max_drawdown_pct"),
            "track_record_days": stats.get("track_record_days", 0),
            "trade_count": stats.get("trade_count", 0),
            "follower_count": follower_count,
            "data_source": "connected_mt5",
        },
        "stats_updated_at": profile.stats_updated_at.isoformat()
        if profile.stats_updated_at
        else None,
        "created_at": profile.created_at.isoformat(),
        "updated_at": profile.updated_at.isoformat(),
    }


async def list_directory(
    session: AsyncSession,
    *,
    search: str = "",
    market: str | None = None,
) -> list[dict[str, Any]]:
    follower_count = (
        select(func.count(CopySubscription.id))
        .where(
            CopySubscription.trader_id == CopyTraderProfile.id,
            CopySubscription.status.in_(
                [CopySubscriptionStatus.ACTIVE, CopySubscriptionStatus.PAUSED]
            ),
        )
        .correlate(CopyTraderProfile)
        .scalar_subquery()
    )
    statement = select(CopyTraderProfile, follower_count).where(
        CopyTraderProfile.is_copyable.is_(True)
    )
    cleaned_search = search.strip()
    if cleaned_search:
        pattern = f"%{cleaned_search}%"
        statement = statement.where(
            or_(
                CopyTraderProfile.display_name.ilike(pattern),
                CopyTraderProfile.description.ilike(pattern),
                CopyTraderProfile.markets.cast(String).ilike(pattern),
            )
        )
    if market:
        statement = statement.where(CopyTraderProfile.markets.contains([market.strip().upper()]))
    rows = (await session.execute(statement.order_by(CopyTraderProfile.updated_at.desc()))).all()
    return [serialize_trader(profile, int(count or 0)) for profile, count in rows]


async def list_owned_traders(session: AsyncSession, user_id: str) -> list[dict[str, Any]]:
    profiles = (
        await session.scalars(
            select(CopyTraderProfile)
            .where(CopyTraderProfile.owner_user_id == user_id)
            .order_by(CopyTraderProfile.created_at)
        )
    ).all()
    return [serialize_trader(profile) for profile in profiles]


async def upsert_trader(
    session: AsyncSession,
    *,
    user_id: str,
    account_id: UUID,
    display_name: str,
    description: str,
    is_copyable: bool,
) -> CopyTraderProfile:
    await require_account_role(session, user_id=user_id, account_id=account_id, write=True)
    profile = await session.scalar(
        select(CopyTraderProfile).where(CopyTraderProfile.account_id == account_id)
    )
    was_copyable = profile.is_copyable if profile is not None else False
    if profile is None:
        profile = CopyTraderProfile(
            account_id=account_id,
            owner_user_id=user_id,
            display_name=display_name.strip(),
            description=description.strip(),
            is_copyable=is_copyable,
        )
        session.add(profile)
    else:
        if profile.owner_user_id != user_id:
            raise PermissionError("Trader profile owner access required")
        profile.display_name = display_name.strip()
        profile.description = description.strip()
        profile.is_copyable = is_copyable
    # Existing followers enter a drain-only state: opens stop immediately while
    # modify/reduce/close events continue until every copied ticket is flat.
    if was_copyable and not is_copyable:
        subscriptions = (
            await session.scalars(
                select(CopySubscription).where(
                    CopySubscription.trader_id == profile.id,
                    CopySubscription.status.in_(
                        [CopySubscriptionStatus.ACTIVE, CopySubscriptionStatus.PAUSED]
                    ),
                )
            )
        ).all()
        for subscription in subscriptions:
            subscription.status = CopySubscriptionStatus.STOPPING
    await _flush_and_refresh(session, profile)
    return profile


async def update_trader_statistics(
    session: AsyncSession,
    *,
    account_id: UUID,
    statistics: dict[str, Any],
    markets: list[str],
) -> CopyTraderProfile | None:
    """Store the runtime's broker-derived public statistics without user edits."""
    profile = await session.scalar(
        select(CopyTraderProfile).where(CopyTraderProfile.account_id == account_id)
    )
    if profile is None:
        return None
    allowed_statistics = {
        key: statistics[key]
        for key in (
            "return_90d_pct",
            "max_drawdown_pct",
            "track_record_days",
            "trade_count",
        )
        if key in statistics
    }
    profile.statistics = allowed_statistics
    profile.markets = list(
        dict.fromkeys(market.strip().upper() for market in markets if market.strip())
    )
    profile.stats_updated_at = datetime.now(UTC)
    await _flush_and_refresh(session, profile)
    return profile


async def patch_trader(
    session: AsyncSession,
    *,
    user_id: str,
    trader_id: UUID,
    changes: dict[str, Any],
) -> CopyTraderProfile:
    profile = await session.get(CopyTraderProfile, trader_id)
    if profile is None:
        raise ValueError("Trader not found")
    await require_account_role(
        session, user_id=user_id, account_id=profile.account_id, write=True
    )
    if profile.owner_user_id != user_id:
        raise PermissionError("Trader profile owner access required")
    for field in ("display_name", "description", "is_copyable"):
        if field in changes and changes[field] is not None:
            next_value = (
                changes[field].strip() if isinstance(changes[field], str) else changes[field]
            )
            setattr(profile, field, next_value)
    if changes.get("is_copyable") is False:
        subscriptions = (
            await session.scalars(
                select(CopySubscription).where(
                    CopySubscription.trader_id == trader_id,
                    CopySubscription.status.in_(
                        [CopySubscriptionStatus.ACTIVE, CopySubscriptionStatus.PAUSED]
                    ),
                )
            )
        ).all()
        for subscription in subscriptions:
            subscription.status = CopySubscriptionStatus.STOPPING
    await _flush_and_refresh(session, profile)
    return profile


async def get_or_create_risk_policy(
    session: AsyncSession,
    *,
    user_id: str,
    account_id: UUID,
    preset: CopyRiskPreset = CopyRiskPreset.CONSERVATIVE,
) -> CopyRiskPolicy:
    await require_account_role(session, user_id=user_id, account_id=account_id)
    policy = await session.scalar(
        select(CopyRiskPolicy).where(CopyRiskPolicy.account_id == account_id)
    )
    if policy is None:
        defaults = RISK_PRESETS[preset]
        policy = CopyRiskPolicy(account_id=account_id, preset=preset, **defaults)
        session.add(policy)
        await session.flush()
    return policy


async def save_risk_policy(
    session: AsyncSession,
    *,
    user_id: str,
    account_id: UUID,
    values: dict[str, Any],
) -> CopyRiskPolicy:
    await require_account_role(session, user_id=user_id, account_id=account_id, write=True)
    preset = CopyRiskPreset(values.get("preset", CopyRiskPreset.CONSERVATIVE.value))
    policy = await get_or_create_risk_policy(
        session, user_id=user_id, account_id=account_id, preset=preset
    )
    defaults = RISK_PRESETS[preset]
    policy.preset = preset
    for field, default_value in defaults.items():
        next_value = values.get(field) if values.get(field) is not None else default_value
        setattr(policy, field, next_value)
    policy.require_stop_loss = bool(values.get("require_stop_loss", True))
    policy.allowed_symbols = values.get("allowed_symbols") or []
    await _flush_and_refresh(session, policy)
    return policy


def serialize_risk_policy(policy: CopyRiskPolicy) -> dict[str, Any]:
    return {
        "id": str(policy.id),
        "account_id": str(policy.account_id),
        "preset": policy.preset.value,
        "risk_per_trade_pct": policy.risk_per_trade_pct,
        "daily_loss_limit_pct": policy.daily_loss_limit_pct,
        "total_open_risk_pct": policy.total_open_risk_pct,
        "max_open_trades": policy.max_open_trades,
        "require_stop_loss": policy.require_stop_loss,
        "allowed_symbols": policy.allowed_symbols or [],
        "updated_at": policy.updated_at.isoformat(),
    }


async def create_subscription(
    session: AsyncSession,
    *,
    user_id: str,
    trader_id: UUID,
    follower_account_id: UUID,
    mode: CopyMode,
    risk_preset: CopyRiskPreset,
    overlap_acknowledged: bool,
    country_code: str | None,
    disclosure_version: str | None,
) -> CopySubscription:
    await require_account_role(
        session, user_id=user_id, account_id=follower_account_id, write=True
    )
    trader = await session.get(CopyTraderProfile, trader_id)
    if trader is None or not trader.is_copyable:
        raise ValueError("Trader is not available to copy")
    if trader.account_id == follower_account_id:
        raise ValueError("An account cannot copy itself")
    if not overlap_acknowledged and trader.markets:
        existing_markets = (
            await session.scalars(
                select(CopyTraderProfile.markets)
                .join(CopySubscription, CopySubscription.trader_id == CopyTraderProfile.id)
                .where(
                    CopySubscription.follower_account_id == follower_account_id,
                    CopySubscription.status.in_(
                        [CopySubscriptionStatus.ACTIVE, CopySubscriptionStatus.PAUSED]
                    ),
                )
            )
        ).all()
        overlap = sorted(
            set(trader.markets).intersection(
                market for markets in existing_markets for market in (markets or [])
            )
        )
        if overlap:
            raise ValueError(
                "Acknowledge overlapping markets before continuing: " + ", ".join(overlap)
            )
    await get_or_create_risk_policy(
        session, user_id=user_id, account_id=follower_account_id, preset=risk_preset
    )
    subscription = await session.scalar(
        select(CopySubscription).where(
            CopySubscription.trader_id == trader_id,
            CopySubscription.follower_account_id == follower_account_id,
        )
    )
    if subscription is None:
        subscription = CopySubscription(
            trader_id=trader_id,
            follower_account_id=follower_account_id,
            follower_user_id=user_id,
        )
        session.add(subscription)
    subscription.mode = CopyMode.PAPER if mode is CopyMode.LIVE else mode
    subscription.status = CopySubscriptionStatus.ACTIVE
    subscription.risk_preset = risk_preset
    subscription.overlap_acknowledged = overlap_acknowledged
    subscription.country_code = country_code
    subscription.disclosure_version = disclosure_version
    await _flush_and_refresh(session, subscription)
    return subscription


def serialize_subscription(
    subscription: CopySubscription, trader: CopyTraderProfile | None = None
) -> dict[str, Any]:
    return {
        "id": str(subscription.id),
        "trader_id": str(subscription.trader_id),
        "trader_name": trader.display_name if trader else None,
        "trader_markets": trader.markets if trader else [],
        "follower_account_id": str(subscription.follower_account_id),
        "follower_user_id": subscription.follower_user_id,
        "mode": subscription.mode.value,
        "status": subscription.status.value,
        "risk_preset": subscription.risk_preset.value,
        "overlap_acknowledged": subscription.overlap_acknowledged,
        "country_code": subscription.country_code,
        "disclosure_version": subscription.disclosure_version,
        "live_activated_at": subscription.live_activated_at.isoformat()
        if subscription.live_activated_at
        else None,
        "created_at": subscription.created_at.isoformat(),
        "updated_at": subscription.updated_at.isoformat(),
    }


async def list_subscriptions(session: AsyncSession, user_id: str) -> list[dict[str, Any]]:
    rows = (
        await session.execute(
            select(CopySubscription, CopyTraderProfile)
            .join(CopyTraderProfile, CopyTraderProfile.id == CopySubscription.trader_id)
            .where(CopySubscription.follower_user_id == user_id)
            .order_by(CopySubscription.created_at.desc())
        )
    ).all()
    return [serialize_subscription(subscription, trader) for subscription, trader in rows]


async def patch_subscription(
    session: AsyncSession,
    *,
    user_id: str,
    subscription_id: UUID,
    values: dict[str, Any],
) -> CopySubscription:
    subscription = await session.get(CopySubscription, subscription_id)
    if subscription is None or subscription.follower_user_id != user_id:
        raise ValueError("Copy relationship not found")
    await require_account_role(
        session,
        user_id=user_id,
        account_id=subscription.follower_account_id,
        write=True,
    )
    if values.get("status"):
        subscription.status = CopySubscriptionStatus(values["status"])
    if values.get("risk_preset"):
        subscription.risk_preset = CopyRiskPreset(values["risk_preset"])
    if values.get("overlap_acknowledged") is not None:
        subscription.overlap_acknowledged = bool(values["overlap_acknowledged"])
    await _flush_and_refresh(session, subscription)
    return subscription


async def runtime_for_account(session: AsyncSession, account_id: UUID) -> CopyRuntime | None:
    return await session.get(CopyRuntime, account_id)


async def activate_live_subscription(
    session: AsyncSession,
    *,
    user_id: str,
    subscription_id: UUID,
    country_code: str,
    disclosure_version: str,
) -> CopySubscription:
    subscription = await session.get(CopySubscription, subscription_id)
    if subscription is None or subscription.follower_user_id != user_id:
        raise ValueError("Copy relationship not found")
    await require_account_role(
        session,
        user_id=user_id,
        account_id=subscription.follower_account_id,
        write=True,
    )
    trader = await session.get(CopyTraderProfile, subscription.trader_id)
    if trader is None or not trader.is_copyable:
        raise ValueError("The trader is no longer available to copy")
    if not subscription.overlap_acknowledged and trader.markets:
        other_markets = (
            await session.scalars(
                select(CopyTraderProfile.markets)
                .join(CopySubscription, CopySubscription.trader_id == CopyTraderProfile.id)
                .where(
                    CopySubscription.follower_account_id
                    == subscription.follower_account_id,
                    CopySubscription.id != subscription.id,
                    CopySubscription.status.in_(
                        [CopySubscriptionStatus.ACTIVE, CopySubscriptionStatus.PAUSED]
                    ),
                )
            )
        ).all()
        if set(trader.markets).intersection(
            market for markets in other_markets for market in (markets or [])
        ):
            raise ValueError("Acknowledge overlapping markets before live activation")
    jurisdiction = await session.get(CopyJurisdictionPolicy, country_code)
    if jurisdiction is None or not jurisdiction.live_enabled:
        raise PermissionError("Live copying is not available in this country")
    if not jurisdiction.disclosure_version or jurisdiction.disclosure_version != disclosure_version:
        raise ValueError("The current live-risk disclosure must be accepted")
    runtime = await runtime_for_account(session, subscription.follower_account_id)
    if (
        runtime is None
        or runtime.status is not CopyRuntimeStatus.HEALTHY
        or not runtime.trading_enabled
    ):
        raise ValueError("The receiving MT5 account is not ready for live copying")
    subscription.mode = CopyMode.LIVE
    subscription.status = CopySubscriptionStatus.ACTIVE
    subscription.country_code = country_code
    subscription.disclosure_version = disclosure_version
    subscription.live_activated_at = datetime.now(UTC)
    await _flush_and_refresh(session, subscription)
    return subscription


async def upsert_runtime(
    session: AsyncSession,
    *,
    account_id: UUID,
    runtime_ref: str,
    status: CopyRuntimeStatus,
    broker_server: str | None,
    trading_enabled: bool,
    details: dict[str, Any],
) -> CopyRuntime:
    runtime = await session.get(CopyRuntime, account_id)
    if runtime is None:
        runtime = CopyRuntime(account_id=account_id)
        session.add(runtime)
    runtime.runtime_ref = runtime_ref
    runtime.status = status
    runtime.broker_server = broker_server
    runtime.trading_enabled = trading_enabled
    runtime.details = details
    runtime.last_heartbeat_at = datetime.now(UTC)
    await session.flush()
    return runtime


async def create_trade_event(
    session: AsyncSession,
    *,
    trader_id: UUID,
    values: dict[str, Any],
) -> tuple[CopyTradeEvent, bool]:
    existing = await session.scalar(
        select(CopyTradeEvent).where(
            CopyTradeEvent.trader_id == trader_id,
            CopyTradeEvent.external_id == values["external_id"],
        )
    )
    if existing is not None:
        return existing, False
    event = CopyTradeEvent(trader_id=trader_id, **values)
    session.add(event)
    await session.flush()
    session.add(CopyOutboxEvent(trade_event_id=event.id))
    await session.flush()
    return event, True


async def list_executions(session: AsyncSession, user_id: str) -> list[dict[str, Any]]:
    rows = (
        await session.execute(
            select(CopyExecution, CopyTradeEvent, CopyTraderProfile)
            .join(CopySubscription, CopySubscription.id == CopyExecution.subscription_id)
            .join(CopyTradeEvent, CopyTradeEvent.id == CopyExecution.trade_event_id)
            .join(CopyTraderProfile, CopyTraderProfile.id == CopyTradeEvent.trader_id)
            .where(CopySubscription.follower_user_id == user_id)
            .order_by(CopyExecution.created_at.desc())
            .limit(100)
        )
    ).all()
    return [
        {
            "id": str(execution.id),
            "trader_name": trader.display_name,
            "symbol": event.symbol,
            "action": event.action.value,
            "mode": execution.mode.value,
            "status": execution.status.value,
            "desired_volume": execution.desired_volume,
            "actual_volume": execution.actual_volume,
            "blocked_reason": execution.blocked_reason,
            "target_ticket": execution.target_ticket,
            "created_at": execution.created_at.isoformat(),
        }
        for execution, event, trader in rows
    ]


async def emergency_stop(
    session: AsyncSession, *, user_id: str, account_id: UUID
) -> list[CopySubscription]:
    await require_account_role(session, user_id=user_id, account_id=account_id, write=True)
    subscriptions = (
        await session.scalars(
            select(CopySubscription).where(
                CopySubscription.follower_user_id == user_id,
                CopySubscription.follower_account_id == account_id,
                CopySubscription.status == CopySubscriptionStatus.ACTIVE,
            )
        )
    ).all()
    for subscription in subscriptions:
        subscription.status = CopySubscriptionStatus.PAUSED
    await session.flush()
    return list(subscriptions)
