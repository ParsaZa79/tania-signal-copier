from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor

import pytest

from src import runtime_pool


def _isolate_registry(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(
        runtime_pool,
        "ASSIGNMENTS_PATH",
        tmp_path / "mt5_runtime_assignments.json",
    )
    monkeypatch.setattr(
        runtime_pool,
        "ASSIGNMENTS_LOCK_PATH",
        tmp_path / ".mt5_runtime_assignments.lock",
    )


def test_runtime_assignments_are_unique_and_persisted(monkeypatch, tmp_path) -> None:
    _isolate_registry(monkeypatch, tmp_path)
    monkeypatch.setenv(
        "MT5_RUNTIME_ENDPOINTS",
        "mt5:8001, mt5-2:8001,mt5-3:8001",
    )

    first = runtime_pool.assign_runtime_endpoint("account-a")
    second = runtime_pool.assign_runtime_endpoint("account-b")

    assert first.key == "mt5:8001"
    assert second.key == "mt5-2:8001"
    assert runtime_pool.assign_runtime_endpoint("account-a") == first
    payload = json.loads(runtime_pool.ASSIGNMENTS_PATH.read_text(encoding="utf-8"))
    assert payload["assignments"] == {
        "account-a": "mt5:8001",
        "account-b": "mt5-2:8001",
    }
    assert runtime_pool.ASSIGNMENTS_PATH.stat().st_mode & 0o777 == 0o600


def test_concurrent_account_assignments_never_share_a_runtime(monkeypatch, tmp_path) -> None:
    _isolate_registry(monkeypatch, tmp_path)
    monkeypatch.setenv(
        "MT5_RUNTIME_ENDPOINTS",
        ",".join(f"mt5-{index}:8001" for index in range(1, 9)),
    )

    account_ids = [f"account-{index}" for index in range(8)]
    with ThreadPoolExecutor(max_workers=8) as executor:
        endpoints = list(executor.map(runtime_pool.assign_runtime_endpoint, account_ids))

    assert len({endpoint.key for endpoint in endpoints}) == len(account_ids)


def test_runtime_pool_fails_closed_when_capacity_is_exhausted(monkeypatch, tmp_path) -> None:
    _isolate_registry(monkeypatch, tmp_path)
    monkeypatch.setenv("MT5_RUNTIME_ENDPOINTS", "mt5:8001")
    runtime_pool.assign_runtime_endpoint("account-a")

    with pytest.raises(runtime_pool.RuntimePoolCapacityError, match="1 configured"):
        runtime_pool.assign_runtime_endpoint("account-b")

    assert runtime_pool.assigned_runtime_endpoint("account-a") is not None
    assert runtime_pool.assigned_runtime_endpoint("account-b") is None


def test_duplicate_persisted_assignment_fails_closed(monkeypatch, tmp_path) -> None:
    _isolate_registry(monkeypatch, tmp_path)
    monkeypatch.setenv("MT5_RUNTIME_ENDPOINTS", "mt5:8001,mt5-2:8001")
    runtime_pool.ASSIGNMENTS_PATH.write_text(
        json.dumps(
            {
                "version": 1,
                "assignments": {
                    "account-a": "mt5:8001",
                    "account-b": "mt5:8001",
                },
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(runtime_pool.RuntimePoolConfigurationError, match="multiple"):
        runtime_pool.validate_runtime_pool()


def test_local_runtime_falls_back_without_consuming_a_pool_slot(monkeypatch, tmp_path) -> None:
    _isolate_registry(monkeypatch, tmp_path)
    monkeypatch.delenv("MT5_RUNTIME_ENDPOINTS", raising=False)

    endpoint = runtime_pool.resolve_runtime_endpoint(
        "account-a",
        fallback_host="localhost",
        fallback_port=9001,
    )

    assert endpoint == runtime_pool.RuntimeEndpoint(host="localhost", port=9001)
    assert not runtime_pool.ASSIGNMENTS_PATH.exists()
