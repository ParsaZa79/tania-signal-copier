"""Background broadcaster for stable real-time MT5 dashboard updates."""

import asyncio
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, cast

from .manager import ConnectionManager


@dataclass
class _CachedSnapshot:
    positions: list[dict[str, Any]]
    account: dict[str, Any]
    last_success_at: str
    last_success_monotonic: float
    consecutive_failures: int = 0


class RuntimeSnapshotCache:
    """Apply hysteresis to the MT5 feed and retain the last valid snapshot."""

    def __init__(
        self,
        *,
        grace_seconds: float = 12.0,
        recovery_after_failures: int = 3,
        recovery_cooldown_seconds: float = 15.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.grace_seconds = grace_seconds
        self.recovery_after_failures = recovery_after_failures
        self.recovery_cooldown_seconds = recovery_cooldown_seconds
        self.clock = clock
        self._snapshots: dict[str, _CachedSnapshot] = {}
        self._failure_counts: dict[str, int] = {}
        self._last_recovery_monotonic: dict[str, float] = {}

    async def build_update(self, executor: Any, account_id: str) -> dict[str, Any]:
        """Build a live update without turning one missed read into a disconnect."""
        try:
            positions, account = await asyncio.to_thread(_read_dashboard_snapshot, executor)
        except Exception:
            return await self._handle_failure(executor, account_id)
        return self._remember_success(account_id, positions, account)

    def runtime_unavailable(self, account_id: str) -> dict[str, Any]:
        """Return a cached degraded state while the owned runtime is recovering."""
        return self._failure_message(account_id, increment=True)

    async def _handle_failure(self, executor: Any, account_id: str) -> dict[str, Any]:
        cached = self._snapshots.get(account_id)
        now = self.clock()
        failure_count = self._failure_counts.get(account_id, 0) + 1
        self._failure_counts[account_id] = failure_count
        if cached:
            cached.consecutive_failures = failure_count

        recover = getattr(executor, "recover_connection", None)
        can_recover = callable(recover) and failure_count >= self.recovery_after_failures
        last_recovery = self._last_recovery_monotonic.get(account_id)
        cooldown_elapsed = (
            last_recovery is None or now - last_recovery >= self.recovery_cooldown_seconds
        )
        if can_recover and cooldown_elapsed:
            self._last_recovery_monotonic[account_id] = now
            try:
                recover_connection = cast(Callable[[], bool], recover)
                recovered = await asyncio.to_thread(recover_connection)
                if recovered:
                    positions, account = await asyncio.to_thread(
                        _read_dashboard_snapshot, executor
                    )
                    return self._remember_success(account_id, positions, account)
            except Exception:
                pass

        return self._failure_message(account_id, increment=False)

    def _remember_success(
        self,
        account_id: str,
        positions: list[dict[str, Any]],
        account: dict[str, Any],
    ) -> dict[str, Any]:
        last_success_at = datetime.now(UTC).isoformat()
        self._snapshots[account_id] = _CachedSnapshot(
            positions=positions,
            account=account,
            last_success_at=last_success_at,
            last_success_monotonic=self.clock(),
        )
        self._failure_counts[account_id] = 0
        return _update_message(
            account_id,
            positions,
            account,
            status="connected",
            stale=False,
            last_success_at=last_success_at,
        )

    def _failure_message(self, account_id: str, *, increment: bool) -> dict[str, Any]:
        cached = self._snapshots.get(account_id)
        if increment:
            count = self._failure_counts.get(account_id, 0) + 1
            self._failure_counts[account_id] = count
            if cached:
                cached.consecutive_failures = count

        if cached and self.clock() - cached.last_success_monotonic <= self.grace_seconds:
            return _update_message(
                account_id,
                cached.positions,
                cached.account,
                status="degraded",
                stale=True,
                last_success_at=cached.last_success_at,
            )
        return _empty_update_message(account_id)


async def start_broadcaster(
    get_executor: Callable[[str], Any],
    manager: ConnectionManager,
    is_runtime_owner: Callable[[str, Any | None], bool] | None = None,
    interval: float = 1.0,
) -> None:
    """Broadcast account-scoped snapshots while smoothing transient MT5 misses."""
    print(f"Starting WebSocket broadcaster with {interval}s interval")
    snapshots = RuntimeSnapshotCache()

    while True:
        try:
            if manager.connection_count == 0:
                await asyncio.sleep(interval)
                continue

            for account_id in manager.account_ids:
                try:
                    executor = get_executor(account_id)
                    if is_runtime_owner is not None and not is_runtime_owner(
                        account_id, executor
                    ):
                        message = snapshots.runtime_unavailable(account_id)
                    else:
                        message = await snapshots.build_update(executor, account_id)
                except Exception:
                    # Endpoint capacity or one unhealthy terminal must never
                    # prevent healthy accounts from receiving their updates.
                    message = snapshots.runtime_unavailable(account_id)
                await manager.broadcast(account_id, message)

        except asyncio.CancelledError:
            print("Broadcaster task cancelled")
            raise
        except Exception as error:
            print(f"Broadcaster error: {error}")

        await asyncio.sleep(interval)


def _read_dashboard_snapshot(
    executor: Any,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Read and serialize RPyC-backed values inside one worker thread."""
    reader = getattr(executor, "get_dashboard_snapshot", None)
    if callable(reader):
        snapshot_reader = cast(Callable[[], tuple[list[Any], Any]], reader)
        positions, account = snapshot_reader()
    else:
        adapter = getattr(executor, "_mt5", None)
        if adapter is None:
            raise RuntimeError("MT5 adapter is unavailable")
        positions = adapter.positions_get()
        account = adapter.account_info()

    if account is None:
        raise RuntimeError("MT5 account information is unavailable")

    positions_data = [
        {
            "ticket": position.ticket,
            "symbol": position.symbol,
            "type": "buy" if position.type == 0 else "sell",
            "volume": position.volume,
            "price_open": position.price_open,
            "price_current": getattr(position, "price_current", None),
            "sl": position.sl,
            "tp": position.tp,
            "profit": position.profit,
            "swap": getattr(position, "swap", 0.0),
            "time": position.time if hasattr(position, "time") else None,
        }
        for position in positions or []
    ]
    account_data = {
        "balance": account.balance,
        "equity": account.equity,
        "margin": account.margin,
        "free_margin": account.margin_free,
        "profit": account.profit,
    }
    return positions_data, account_data


def _update_message(
    account_id: str,
    positions: list[dict[str, Any]],
    account: dict[str, Any],
    *,
    status: str,
    stale: bool,
    last_success_at: str,
) -> dict[str, Any]:
    return {
        "type": "update",
        "account_id": account_id,
        "timestamp": datetime.now(UTC).isoformat(),
        "positions": positions,
        "account": account,
        "connection": {
            "status": status,
            "stale": stale,
            "last_success_at": last_success_at,
        },
    }


def _empty_update_message(account_id: str) -> dict[str, Any]:
    return {
        "type": "update",
        "account_id": account_id,
        "timestamp": datetime.now(UTC).isoformat(),
        "positions": [],
        "account": None,
        "connection": {
            "status": "disconnected",
            "stale": False,
            "last_success_at": None,
        },
    }


async def _build_update_message(executor: Any, account_id: str) -> dict[str, Any]:
    """Compatibility helper for focused tests and one-off callers."""
    return await RuntimeSnapshotCache().build_update(executor, account_id)
