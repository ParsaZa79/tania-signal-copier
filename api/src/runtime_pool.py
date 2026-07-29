"""Persistent one-account-to-one-terminal MT5 runtime assignments."""

from __future__ import annotations

import json
import os
import re
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from threading import RLock
from typing import Any

from .runtime_data import DATA_DIR

try:
    import fcntl
except ImportError:  # pragma: no cover - the production API runs on Linux.
    fcntl = None  # type: ignore[assignment]


RUNTIME_ENDPOINTS_ENV = "MT5_RUNTIME_ENDPOINTS"
ASSIGNMENTS_PATH = DATA_DIR / "mt5_runtime_assignments.json"
ASSIGNMENTS_LOCK_PATH = DATA_DIR / ".mt5_runtime_assignments.lock"
_HOST_PATTERN = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9._-]{0,251}[A-Za-z0-9])?$")
_assignment_lock = RLock()


class RuntimePoolError(RuntimeError):
    """Base error for isolated MT5 runtime assignment failures."""


class RuntimePoolConfigurationError(RuntimePoolError):
    """Raised when the configured runtime pool is invalid."""


class RuntimePoolCapacityError(RuntimePoolError):
    """Raised when every isolated runtime is already assigned."""


@dataclass(frozen=True, slots=True)
class RuntimeEndpoint:
    """A private RPyC endpoint dedicated to one dashboard account."""

    host: str
    port: int

    @property
    def key(self) -> str:
        return f"{self.host}:{self.port}"


def _parse_endpoint(raw_endpoint: str) -> RuntimeEndpoint:
    raw_endpoint = raw_endpoint.strip()
    if not raw_endpoint:
        raise RuntimePoolConfigurationError("MT5 runtime endpoint cannot be blank")

    host = raw_endpoint
    port = 8001
    if ":" in raw_endpoint:
        host, raw_port = raw_endpoint.rsplit(":", 1)
        try:
            port = int(raw_port)
        except ValueError as error:
            raise RuntimePoolConfigurationError(
                f"Invalid MT5 runtime port in {raw_endpoint!r}"
            ) from error

    host = host.strip()
    if not _HOST_PATTERN.fullmatch(host):
        raise RuntimePoolConfigurationError(f"Invalid MT5 runtime host {host!r}")
    if not 1 <= port <= 65535:
        raise RuntimePoolConfigurationError(f"Invalid MT5 runtime port {port}")
    return RuntimeEndpoint(host=host, port=port)


def configured_runtime_endpoints() -> tuple[RuntimeEndpoint, ...]:
    """Return the ordered, validated private runtime pool from the environment."""
    raw = os.getenv(RUNTIME_ENDPOINTS_ENV, "").strip()
    if not raw:
        return ()

    endpoints = tuple(_parse_endpoint(item) for item in raw.split(","))
    keys = [endpoint.key for endpoint in endpoints]
    if len(keys) != len(set(keys)):
        raise RuntimePoolConfigurationError("MT5 runtime endpoints must be unique")
    return endpoints


def runtime_pool_enabled() -> bool:
    """Return whether isolated runtime assignment is enabled."""
    return bool(configured_runtime_endpoints())


def _load_assignments() -> dict[str, str]:
    if not ASSIGNMENTS_PATH.exists():
        return {}
    try:
        payload = json.loads(ASSIGNMENTS_PATH.read_text(encoding="utf-8"))
    except Exception as error:
        raise RuntimePoolConfigurationError(
            "MT5 runtime assignment registry is unreadable"
        ) from error

    raw_assignments = payload.get("assignments") if isinstance(payload, dict) else None
    if not isinstance(raw_assignments, dict):
        raise RuntimePoolConfigurationError("MT5 runtime assignment registry is invalid")
    return {
        str(account_id): str(endpoint_key)
        for account_id, endpoint_key in raw_assignments.items()
        if account_id and endpoint_key
    }


def _save_assignments(assignments: dict[str, str]) -> None:
    ASSIGNMENTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = ASSIGNMENTS_PATH.with_name(
        f".{ASSIGNMENTS_PATH.name}.{os.getpid()}.tmp"
    )
    payload: dict[str, Any] = {
        "version": 1,
        "assignments": dict(sorted(assignments.items())),
    }
    temporary_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    os.chmod(temporary_path, 0o600)
    os.replace(temporary_path, ASSIGNMENTS_PATH)


@contextmanager
def _locked_registry() -> Iterator[None]:
    """Serialize assignments across API threads and worker processes."""
    with _assignment_lock:
        ASSIGNMENTS_LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
        with ASSIGNMENTS_LOCK_PATH.open("a+", encoding="utf-8") as lock_file:
            if fcntl is not None:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                if fcntl is not None:
                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def _validate_unique_assignments(
    assignments: dict[str, str],
    endpoint_keys: set[str],
) -> None:
    owners_by_endpoint: dict[str, str] = {}
    for account_id, endpoint_key in assignments.items():
        if endpoint_key not in endpoint_keys:
            continue
        existing_owner = owners_by_endpoint.get(endpoint_key)
        if existing_owner is not None and existing_owner != account_id:
            raise RuntimePoolConfigurationError(
                f"MT5 runtime {endpoint_key} is assigned to multiple accounts"
            )
        owners_by_endpoint[endpoint_key] = account_id


def assign_runtime_endpoint(account_id: str) -> RuntimeEndpoint:
    """Return the account's stable endpoint, allocating a free one if needed."""
    if not account_id:
        raise RuntimePoolConfigurationError("Account id is required for runtime assignment")

    endpoints = configured_runtime_endpoints()
    if not endpoints:
        raise RuntimePoolConfigurationError("The isolated MT5 runtime pool is not configured")

    endpoints_by_key = {endpoint.key: endpoint for endpoint in endpoints}
    endpoint_keys = set(endpoints_by_key)
    with _locked_registry():
        assignments = _load_assignments()
        _validate_unique_assignments(assignments, endpoint_keys)

        assigned_key = assignments.get(account_id)
        if assigned_key in endpoints_by_key:
            return endpoints_by_key[assigned_key]

        # Remove an assignment to a retired slot before selecting a replacement.
        assignments.pop(account_id, None)
        occupied = {
            endpoint_key
            for owner_id, endpoint_key in assignments.items()
            if owner_id != account_id and endpoint_key in endpoint_keys
        }
        endpoint = next(
            (candidate for candidate in endpoints if candidate.key not in occupied),
            None,
        )
        if endpoint is None:
            raise RuntimePoolCapacityError(
                f"No isolated MT5 runtime is available ({len(endpoints)} configured)"
            )

        assignments[account_id] = endpoint.key
        _save_assignments(assignments)
        return endpoint


def assigned_runtime_endpoint(account_id: str) -> RuntimeEndpoint | None:
    """Return an existing valid assignment without consuming pool capacity."""
    endpoints = configured_runtime_endpoints()
    if not endpoints:
        return None
    endpoints_by_key = {endpoint.key: endpoint for endpoint in endpoints}
    with _locked_registry():
        assignments = _load_assignments()
        _validate_unique_assignments(assignments, set(endpoints_by_key))
        return endpoints_by_key.get(assignments.get(account_id, ""))


def release_runtime_endpoint(account_id: str) -> None:
    """Release an account assignment after that account has been deleted."""
    if not configured_runtime_endpoints():
        return
    with _locked_registry():
        assignments = _load_assignments()
        if assignments.pop(account_id, None) is not None:
            _save_assignments(assignments)


def resolve_runtime_endpoint(
    account_id: str,
    *,
    fallback_host: str | None,
    fallback_port: int,
) -> RuntimeEndpoint:
    """Resolve a pooled production endpoint or the legacy local endpoint."""
    if configured_runtime_endpoints():
        return assign_runtime_endpoint(account_id)
    return RuntimeEndpoint(host=fallback_host or "localhost", port=fallback_port)


def validate_runtime_pool() -> None:
    """Fail fast on malformed endpoints or colliding persisted assignments."""
    endpoints = configured_runtime_endpoints()
    if not endpoints:
        return
    endpoints_by_key = {endpoint.key: endpoint for endpoint in endpoints}
    with _locked_registry():
        _validate_unique_assignments(_load_assignments(), set(endpoints_by_key))
