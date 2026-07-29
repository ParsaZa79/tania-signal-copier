"""FastAPI dependencies for dependency injection."""

import os
from collections.abc import Callable
from threading import RLock
from typing import Annotated, Any

from fastapi import Depends, HTTPException

from .account_store import get_active_account, load_account_config
from .runtime_pool import (
    RuntimePoolError,
    assigned_runtime_endpoint,
    resolve_runtime_endpoint,
)

# Executor objects are keyed by authenticated dashboard account. Production
# assigns every account a different private MT5 endpoint; account selection is
# therefore a UI concern and never transfers ownership of a shared terminal.
_executor_factory: Callable[..., Any] | None = None
_mt5_executors: dict[str, Any] = {}
_executors_lock = RLock()


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


def _runtime_endpoint(account_id: str, config_values: dict[str, str]) -> tuple[str, int]:
    endpoint = resolve_runtime_endpoint(
        account_id,
        fallback_host=_mt5_docker_host(config_values),
        fallback_port=_mt5_docker_port(config_values),
    )
    return endpoint.host, endpoint.port


def _new_executor(account_id: str) -> Any:
    if _executor_factory is None:
        raise RuntimeError("MT5 executor factory not initialized")

    config = load_account_config(account_id, reveal_secrets=True)
    docker_host, docker_port = _runtime_endpoint(account_id, config)
    return _executor_factory(
        login=_coerce_int(config.get("MT5_LOGIN"), 0),
        password=config.get("MT5_PASSWORD", ""),
        server=config.get("MT5_SERVER", ""),
        docker_host=docker_host,
        docker_port=docker_port,
        path=config.get("MT5_PATH") or None,
    )


def get_executor_for_account_id(account_id: str) -> Any:
    """Get or create the executor for an account."""
    with _executors_lock:
        executor = _mt5_executors.get(account_id)
        if executor is None:
            executor = _new_executor(account_id)
            _mt5_executors[account_id] = executor
        return executor


def is_account_runtime_active(account_id: str, executor: Any | None = None) -> bool:
    """Return whether this account's isolated MT5 runtime is connected."""
    if executor is None:
        executor = _mt5_executors.get(account_id)

    return bool(
        executor is not None
        and getattr(executor, "connected", False)
        and getattr(executor, "_mt5", None) is not None
    )


def is_account_runtime_owner(account_id: str, executor: Any | None = None) -> bool:
    """Return whether this account has its own executor/runtime assignment."""
    if executor is not None or account_id in _mt5_executors:
        return True
    try:
        return assigned_runtime_endpoint(account_id) is not None
    except RuntimePoolError:
        return False


def get_mt5_executor(
    account: Annotated[dict[str, Any], Depends(get_active_account)],
) -> Any:
    """Get the active account's MT5 executor."""
    try:
        executor = get_executor_for_account_id(account["id"])
    except RuntimePoolError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    if not is_account_runtime_active(account["id"], executor):
        raise HTTPException(status_code=503, detail="MT5 not connected for this account")
    return executor


def connect_account_executor(account_id: str, config_values: dict[str, str]) -> dict:
    """Connect one account to its dedicated MT5 runtime."""
    try:
        docker_host, docker_port = _runtime_endpoint(account_id, config_values)
        executor = get_executor_for_account_id(account_id)
    except RuntimePoolError as error:
        return {
            "success": False,
            "connected": False,
            "error": str(error),
            "health": {},
        }
    result = executor.reconfigure(
        login=_coerce_int(config_values.get("MT5_LOGIN"), 0),
        password=config_values.get("MT5_PASSWORD", ""),
        server=config_values.get("MT5_SERVER", ""),
        docker_host=docker_host,
        docker_port=docker_port,
        path=config_values.get("MT5_PATH") or None,
    )
    return result


def activate_account_runtime(account_id: str) -> dict:
    """Connect a configured account without affecting any other account."""
    config = load_account_config(account_id, reveal_secrets=True)
    if not all(config.get(key) for key in ("MT5_LOGIN", "MT5_PASSWORD", "MT5_SERVER")):
        return {
            "success": False,
            "connected": False,
            "error": "Saved MT5 configuration is incomplete",
        }

    try:
        executor = get_executor_for_account_id(account_id)
    except RuntimePoolError as error:
        return {
            "success": False,
            "connected": False,
            "error": str(error),
            "health": {},
        }
    if is_account_runtime_active(account_id, executor) and executor.is_alive():
        return {"success": True, "connected": True, "health": executor.health_check()}
    return connect_account_executor(account_id, config)


def restore_account_executor(account_id: str) -> dict:
    """Restore one saved runtime without touching other account runtimes."""
    return activate_account_runtime(account_id)


def active_runtime_account_id() -> str | None:
    """Compatibility helper for callers that only support a single connection."""
    connected = connected_executor_account_ids()
    return connected[0] if len(connected) == 1 else None


def connected_executor_account_ids() -> list[str]:
    with _executors_lock:
        return [
            account_id
            for account_id, executor in _mt5_executors.items()
            if getattr(executor, "connected", False)
        ]


def clear_mt5_executor(account_id: str | None = None) -> None:
    """Clear one account executor, or all executors during shutdown."""
    if account_id is not None:
        with _executors_lock:
            executor = _mt5_executors.pop(account_id, None)
        if executor is not None:
            executor.disconnect()
        return

    with _executors_lock:
        executors = list(_mt5_executors.values())
        _mt5_executors.clear()
    for executor in executors:
        executor.disconnect()
