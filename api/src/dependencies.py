"""FastAPI dependencies for dependency injection."""

import os
from collections.abc import Callable
from typing import Annotated, Any

from fastapi import Depends, HTTPException

from .account_store import get_active_account, load_account_config

# Executor objects are keyed by authenticated dashboard account. The current
# Dokploy MT5 bridge is still one shared terminal, so only one account can be
# active against the bridge at a time.
_executor_factory: Callable[..., Any] | None = None
_mt5_executors: dict[str, Any] = {}
_active_runtime_account_id: str | None = None


def set_mt5_executor_factory(factory: Callable[..., Any]) -> None:
    """Set the concrete MT5 executor factory for account-scoped runtimes."""
    global _executor_factory
    _executor_factory = factory


def _coerce_int(value: str | None, default: int) -> int:
    try:
        return int(value or default)
    except (TypeError, ValueError):
        return default


def _mt5_docker_host(config_values: dict[str, str]) -> str | None:
    return config_values.get("MT5_DOCKER_HOST") or os.getenv("MT5_DOCKER_HOST") or None


def _mt5_docker_port(config_values: dict[str, str]) -> int:
    return _coerce_int(config_values.get("MT5_DOCKER_PORT") or os.getenv("MT5_DOCKER_PORT"), 8001)


def _new_executor(account_id: str) -> Any:
    if _executor_factory is None:
        raise RuntimeError("MT5 executor factory not initialized")

    config = load_account_config(account_id, reveal_secrets=True)
    return _executor_factory(
        login=_coerce_int(config.get("MT5_LOGIN"), 0),
        password=config.get("MT5_PASSWORD", ""),
        server=config.get("MT5_SERVER", ""),
        docker_host=_mt5_docker_host(config),
        docker_port=_mt5_docker_port(config),
        path=config.get("MT5_PATH") or None,
    )


def get_executor_for_account_id(account_id: str) -> Any:
    """Get or create the executor for an account."""
    executor = _mt5_executors.get(account_id)
    if executor is None:
        executor = _new_executor(account_id)
        _mt5_executors[account_id] = executor
    return executor


def is_account_runtime_active(account_id: str, executor: Any | None = None) -> bool:
    """Return whether this account currently owns the shared MT5 runtime."""
    if _active_runtime_account_id != account_id:
        return False

    if executor is None:
        executor = _mt5_executors.get(account_id)

    return bool(
        executor is not None
        and getattr(executor, "connected", False)
        and getattr(executor, "_mt5", None) is not None
    )


def is_account_runtime_owner(account_id: str, executor: Any | None = None) -> bool:
    """Return whether this account owns the shared terminal, even while recovering."""
    del executor
    return _active_runtime_account_id == account_id


def get_mt5_executor(
    account: Annotated[dict[str, Any], Depends(get_active_account)],
) -> Any:
    """Get the active account's MT5 executor."""
    executor = get_executor_for_account_id(account["id"])
    if not is_account_runtime_active(account["id"], executor):
        if getattr(executor, "connected", False):
            executor.disconnect()
        raise HTTPException(status_code=503, detail="MT5 not connected for this account")
    return executor


def connect_account_executor(account_id: str, config_values: dict[str, str]) -> dict:
    """Connect one account to the shared MT5 bridge and mark it runtime-active."""
    global _active_runtime_account_id

    executor = get_executor_for_account_id(account_id)
    result = executor.reconfigure(
        login=_coerce_int(config_values.get("MT5_LOGIN"), 0),
        password=config_values.get("MT5_PASSWORD", ""),
        server=config_values.get("MT5_SERVER", ""),
        docker_host=_mt5_docker_host(config_values),
        docker_port=_mt5_docker_port(config_values),
        path=config_values.get("MT5_PATH") or None,
    )

    if result.get("success"):
        for other_account_id, other_executor in list(_mt5_executors.items()):
            if other_account_id != account_id and getattr(other_executor, "connected", False):
                other_executor.disconnect()
        _active_runtime_account_id = account_id

    return result


def activate_account_runtime(account_id: str) -> dict:
    """Make a configured account own the shared MT5 runtime.

    Account credentials remain isolated on disk. Because the current deployment
    has one MT5 terminal, switching accounts must explicitly re-authenticate that
    terminal instead of leaving it bound to the previously selected account.
    """
    executor = get_executor_for_account_id(account_id)
    if is_account_runtime_active(account_id, executor) and executor.is_alive():
        return {"success": True, "connected": True, "health": executor.health_check()}

    config = load_account_config(account_id, reveal_secrets=True)
    if not all(config.get(key) for key in ("MT5_LOGIN", "MT5_PASSWORD", "MT5_SERVER")):
        return {
            "success": False,
            "connected": False,
            "error": "Saved MT5 configuration is incomplete",
        }
    return connect_account_executor(account_id, config)


def restore_account_executor(account_id: str) -> dict:
    """Restore the saved account runtime without displacing another account.

    This is used when a dashboard WebSocket reconnects after an API restart or
    a dropped MT5 bridge. It deliberately refuses to take over a terminal that
    currently belongs to a different dashboard account.
    """
    if _active_runtime_account_id not in (None, account_id):
        return {
            "success": False,
            "connected": False,
            "error": "MT5 runtime is active for another account",
        }

    return activate_account_runtime(account_id)


def active_runtime_account_id() -> str | None:
    return _active_runtime_account_id


def connected_executor_account_ids() -> list[str]:
    return [
        account_id
        for account_id, executor in _mt5_executors.items()
        if getattr(executor, "connected", False)
    ]


def clear_mt5_executor(account_id: str | None = None) -> None:
    """Clear one account executor, or all executors during shutdown."""
    global _active_runtime_account_id

    if account_id is not None:
        executor = _mt5_executors.pop(account_id, None)
        if executor is not None:
            executor.disconnect()
        if _active_runtime_account_id == account_id:
            _active_runtime_account_id = None
        return

    for executor in _mt5_executors.values():
        executor.disconnect()
    _mt5_executors.clear()
    _active_runtime_account_id = None
