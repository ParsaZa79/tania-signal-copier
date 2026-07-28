import json

import pytest
from fastapi import HTTPException
from starlette.datastructures import Headers

from src import access_store, account_store, dependencies, runtime_data, security
from src.routers import access as access_router
from src.routers import accounts as accounts_router


def _isolate_storage(monkeypatch, tmp_path):
    monkeypatch.delenv("WORKOS_CLIENT_ID", raising=False)
    monkeypatch.setenv("ACCESS_BOOTSTRAP_EMAILS", "owner@example.com")
    monkeypatch.setattr(security, "USERS_PATH", tmp_path / "users.json")
    monkeypatch.setattr(security, "DEV_SECRET_PATH", tmp_path / ".dev_app_secret")
    monkeypatch.setattr(account_store, "ACCOUNTS_PATH", tmp_path / "accounts.json")
    monkeypatch.setattr(access_store, "ACCESS_PATH", tmp_path / "access.json")
    monkeypatch.setattr(access_store, "LEGACY_USERS_PATH", tmp_path / "users.json")
    monkeypatch.setattr(access_store, "ACCOUNTS_PATH", tmp_path / "accounts.json")
    monkeypatch.setattr(runtime_data, "DATA_DIR", tmp_path)
    monkeypatch.setattr(runtime_data, "ACCOUNTS_DIR", tmp_path / "accounts")
    monkeypatch.setattr(runtime_data, "CACHE_PATH", tmp_path / "bot_config_cache.json")
    monkeypatch.setattr(runtime_data, "ENV_PATH", tmp_path / ".env")


def test_auth_token_round_trip(monkeypatch, tmp_path):
    _isolate_storage(monkeypatch, tmp_path)

    user = security.create_user("owner@example.com", "correct horse battery")
    raw_user = security.get_user(user["id"])
    assert raw_user is not None

    token = security.create_token(user["id"])
    payload = security.decode_token(token)

    assert payload is not None
    assert payload["sub"] == user["id"]
    assert security.authenticate_credentials("owner@example.com", "correct horse battery")
    assert security.authenticate_credentials("owner@example.com", "wrong password") is None


def test_dashboard_proxy_headers_authenticate_workos_user(monkeypatch, tmp_path):
    _isolate_storage(monkeypatch, tmp_path)
    monkeypatch.setenv("DASHBOARD_PROXY_SECRET", "shared-secret")
    monkeypatch.setenv("ACCESS_BOOTSTRAP_EMAILS", "proxy-user@example.com")

    user = security._workos_user_from_proxy_headers(
        Headers(
            {
                "x-dashboard-proxy-auth": "shared-secret",
                "x-workos-user-id": "user_workos_proxy",
                "x-workos-user-email": "proxy-user@example.com",
                "x-workos-session-id": "sess_proxy",
            }
        ),
        provision=True,
    )

    assert user is not None
    assert user["id"] == "user_workos_proxy"
    assert user["email"] == "proxy-user@example.com"
    assert user["role"] == "owner"
    assert user["auth_provider"] == "workos"
    assert user["session_id"] == "sess_proxy"


def test_account_config_encrypts_and_masks_secrets(monkeypatch, tmp_path):
    _isolate_storage(monkeypatch, tmp_path)

    user = security.create_user("owner@example.com", "correct horse battery")
    account = account_store.create_account(user["id"], "Primary Account")

    account_store.save_account_config(
        account["id"],
        {
            "MT5_LOGIN": "123456",
            "MT5_PASSWORD": "broker-password",
            "MT5_SERVER": "Broker-Real",
            "DEFAULT_LOT_SIZE": "0.01",
        },
    )

    raw = runtime_data.account_config_path(account["id"]).read_text(encoding="utf-8")
    assert "broker-password" not in raw
    assert json.loads(raw)["secrets"]["MT5_PASSWORD"].startswith("fernet:")

    revealed = account_store.load_account_config(account["id"], reveal_secrets=True)
    assert revealed["MT5_PASSWORD"] == "broker-password"

    sanitized, configured = account_store.sanitize_config(revealed)
    assert sanitized["MT5_PASSWORD"] == ""
    assert "MT5_PASSWORD" in configured


def test_blank_secret_save_preserves_existing_value(monkeypatch, tmp_path):
    _isolate_storage(monkeypatch, tmp_path)

    user = security.create_user("owner@example.com", "correct horse battery")
    account = account_store.create_account(user["id"], "Primary Account")
    account_store.save_account_config(account["id"], {"MT5_PASSWORD": "first-password"})
    account_store.save_account_config(
        account["id"],
        {"MT5_PASSWORD": "", "MT5_SERVER": "Updated-Server"},
    )

    revealed = account_store.load_account_config(account["id"], reveal_secrets=True)
    assert revealed["MT5_PASSWORD"] == "first-password"
    assert revealed["MT5_SERVER"] == "Updated-Server"


def test_accounts_are_isolated(monkeypatch, tmp_path):
    _isolate_storage(monkeypatch, tmp_path)

    user = security.create_user("owner@example.com", "correct horse battery")
    first = account_store.create_account(user["id"], "Primary Account")
    second = account_store.create_account(user["id"], "Second")

    account_store.save_account_config(first["id"], {"MT5_LOGIN": "111", "MT5_PASSWORD": "one"})
    account_store.save_account_config(second["id"], {"MT5_LOGIN": "222", "MT5_PASSWORD": "two"})

    first_config = account_store.load_account_config(first["id"], reveal_secrets=True)
    second_config = account_store.load_account_config(second["id"], reveal_secrets=True)

    assert first_config["MT5_LOGIN"] == "111"
    assert first_config["MT5_PASSWORD"] == "one"
    assert second_config["MT5_LOGIN"] == "222"
    assert second_config["MT5_PASSWORD"] == "two"


def test_workos_owner_bootstrap_migrates_legacy_accounts(monkeypatch, tmp_path):
    _isolate_storage(monkeypatch, tmp_path)

    legacy_user = security.create_user("owner@example.com", "correct horse battery")
    legacy_account = account_store.create_account(legacy_user["id"], "Primary Account")

    member = access_store.resolve_workos_member("user_workos_owner", "owner@example.com")

    assert member["id"] == "user_workos_owner"
    assert member["role"] == "owner"
    assert member["status"] == "active"
    assert member["active_account_id"] == legacy_account["id"]
    assert account_store.get_account(legacy_account["id"], "user_workos_owner") is not None
    assert account_store.get_account(legacy_account["id"], legacy_user["id"]) is None


def test_workos_email_rebind_preserves_existing_dashboard_accounts(monkeypatch, tmp_path):
    _isolate_storage(monkeypatch, tmp_path)

    previous = access_store.resolve_workos_member("previous_identity", "owner@example.com")
    account = account_store.create_account(previous["id"], "Live Account")
    access_store.set_member_active_account_id(previous["id"], account["id"])

    rebound = access_store.resolve_workos_member("user_workos_owner", "OWNER@example.com")

    assert rebound["id"] == "user_workos_owner"
    assert rebound["role"] == "owner"
    assert rebound["active_account_id"] == account["id"]
    assert account_store.get_account(account["id"], "user_workos_owner") is not None
    assert account_store.get_account(account["id"], "previous_identity") is None


def test_uninvited_workos_users_are_self_service_traders(monkeypatch, tmp_path):
    _isolate_storage(monkeypatch, tmp_path)

    owner = access_store.resolve_workos_member("user_workos_owner", "owner@example.com")
    trader = access_store.resolve_workos_member("user_workos_trader", "trader@example.com")

    assert owner["role"] == "owner"
    assert trader["role"] == "trader"
    assert trader["status"] == "active"
    assert trader["active_account_id"] is None


def test_legacy_invite_only_settings_cannot_block_or_promote_self_service_users(
    monkeypatch,
    tmp_path,
):
    _isolate_storage(monkeypatch, tmp_path)
    monkeypatch.setenv("ACCESS_REQUIRE_INVITE", "true")
    monkeypatch.setenv("ACCESS_SELF_SIGNUP_ROLE", "admin")

    access_store.resolve_workos_member("user_workos_owner", "owner@example.com")
    trader = access_store.resolve_workos_member(
        "user_workos_trader",
        "trader@example.com",
    )

    assert trader["role"] == "trader"
    assert trader["status"] == "active"


def test_self_service_user_can_register_before_reserved_owner(monkeypatch, tmp_path):
    _isolate_storage(monkeypatch, tmp_path)

    trader = access_store.resolve_workos_member(
        "user_workos_trader",
        "trader@example.com",
    )
    owner = access_store.resolve_workos_member(
        "user_workos_owner",
        "owner@example.com",
    )

    assert trader["role"] == "trader"
    assert owner["role"] == "owner"


def test_accounts_are_not_created_until_requested(monkeypatch, tmp_path):
    _isolate_storage(monkeypatch, tmp_path)

    user = security.create_user("owner@example.com", "correct horse battery")

    assert account_store.list_user_accounts(user["id"]) == []
    assert account_store.get_preferred_account(user) is None
    assert account_store.get_user_setup_status(user)["needs_account"] is True

    with pytest.raises(HTTPException) as exc_info:
        account_store.ensure_default_account(user)

    assert exc_info.value.status_code == 404


def test_account_setup_requires_broker_and_completion_marker(monkeypatch, tmp_path):
    _isolate_storage(monkeypatch, tmp_path)

    user = security.create_user("owner@example.com", "correct horse battery")
    account = account_store.create_account(user["id"], "Live Account")

    account_store.save_account_config(
        account["id"],
        {
            "MT5_LOGIN": "123456",
            "MT5_PASSWORD": "broker-password",
            "MT5_SERVER": "Broker-Real",
        },
    )

    setup = account_store.get_user_setup_status(user)
    assert setup["setup_complete"] is False
    assert account_store.list_user_accounts(user["id"])[0]["setup_complete"] is False

    completed = account_store.mark_account_setup_complete(account["id"])
    refreshed = account_store.get_user_setup_status(user)

    assert completed["setup_complete"] is True
    assert refreshed["setup_complete"] is True
    assert account_store.list_user_accounts(user["id"])[0]["setup_complete"] is True


def test_account_config_strips_telegram_overrides(monkeypatch, tmp_path):
    _isolate_storage(monkeypatch, tmp_path)

    user = security.create_user("owner@example.com", "correct horse battery")
    account = account_store.create_account(user["id"], "Live Account")

    account_store.save_account_config(
        account["id"],
        {
            "MT5_LOGIN": "123456",
            "TELEGRAM_API_ID": "999",
            "TELEGRAM_API_HASH": "user-hash",
            "TELEGRAM_CHANNEL": "user-channel",
            "TELEGRAM_SESSION_NAME": "user-session",
        },
    )

    config = account_store.load_account_config(account["id"], reveal_secrets=True)

    assert config["MT5_LOGIN"] == "123456"
    assert "TELEGRAM_API_ID" not in config
    assert "TELEGRAM_API_HASH" not in config
    assert "TELEGRAM_CHANNEL" not in config
    assert "TELEGRAM_SESSION_NAME" not in config


def test_invited_workos_user_links_pending_access(monkeypatch, tmp_path):
    _isolate_storage(monkeypatch, tmp_path)

    pending = access_store.invite_member(
        email="trader@example.com",
        role="trader",
        invited_by="user_workos_owner",
        invitation_id="inv_123",
        invitation_status="pending",
    )

    member = access_store.resolve_workos_member("user_workos_trader", "trader@example.com")
    members = access_store.list_members()

    assert pending["status"] == "pending"
    assert member["id"] == "user_workos_trader"
    assert member["workos_user_id"] == "user_workos_trader"
    assert member["status"] == "active"
    assert member["invitation_status"] == "accepted"
    assert len(members) == 1


def test_disabled_workos_member_stays_blocked(monkeypatch, tmp_path):
    _isolate_storage(monkeypatch, tmp_path)

    access_store.resolve_workos_member("user_workos_owner", "owner@example.com")
    pending = access_store.invite_member(
        email="disabled@example.com",
        role="trader",
        invited_by="user_workos_owner",
    )
    access_store.update_member(pending["id"], status_value="disabled")

    with pytest.raises(HTTPException) as exc_info:
        access_store.resolve_workos_member("user_workos_disabled", "disabled@example.com")

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == {
        "code": "access_disabled",
        "message": "This dashboard account has been disabled.",
    }


def test_access_store_keeps_at_least_one_active_owner(monkeypatch, tmp_path):
    _isolate_storage(monkeypatch, tmp_path)

    owner = access_store.resolve_workos_member("user_workos_owner", "owner@example.com")

    with pytest.raises(ValueError, match="At least one active owner"):
        access_store.update_member(owner["id"], status_value="disabled")

    with pytest.raises(ValueError, match="At least one active owner"):
        access_store.remove_member(owner["id"])


async def test_access_route_validates_last_owner_before_deleting_workos_user(monkeypatch, tmp_path):
    _isolate_storage(monkeypatch, tmp_path)
    owner = access_store.resolve_workos_member("user_workos_owner", "owner@example.com")
    remote_deletions: list[str] = []
    monkeypatch.setattr(access_router, "workos_management_enabled", lambda: True)
    monkeypatch.setattr(access_router, "delete_workos_user", remote_deletions.append)

    with pytest.raises(HTTPException) as exc_info:
        await access_router.delete_access_member(owner["id"], current_user=owner)

    assert exc_info.value.status_code == 400
    assert remote_deletions == []


class _RuntimeExecutor:
    def __init__(self, connected: bool = True) -> None:
        self.connected = connected
        self._mt5 = object() if connected else None
        self.disconnect_called = False
        self.reconfigure_calls: list[dict] = []

    def disconnect(self) -> None:
        self.disconnect_called = True
        self.connected = False
        self._mt5 = None

    def is_alive(self) -> bool:
        return self.connected

    def health_check(self) -> dict:
        return {"connected": self.connected}

    def reconfigure(self, **config) -> dict:
        self.reconfigure_calls.append(config)
        self.connected = True
        self._mt5 = object()
        return {"success": True, "connected": True, "health": self.health_check()}


def test_mt5_executor_requires_account_to_own_runtime(monkeypatch):
    primary = _RuntimeExecutor()
    secondary = _RuntimeExecutor()
    monkeypatch.setattr(
        dependencies,
        "_mt5_executors",
        {"primary": primary, "secondary": secondary},
    )
    monkeypatch.setattr(dependencies, "_active_runtime_account_id", "primary")

    assert dependencies.get_mt5_executor({"id": "primary"}) is primary
    assert dependencies.is_account_runtime_active("primary", primary) is True
    assert dependencies.is_account_runtime_active("secondary", secondary) is False

    with pytest.raises(HTTPException) as exc_info:
        dependencies.get_mt5_executor({"id": "secondary"})

    assert exc_info.value.status_code == 503
    assert secondary.disconnect_called is True


def test_activate_account_runtime_reconnects_saved_account_after_demo_takes_over(monkeypatch):
    live = _RuntimeExecutor(connected=False)
    demo = _RuntimeExecutor(connected=True)
    monkeypatch.setattr(
        dependencies,
        "_mt5_executors",
        {"live": live, "demo": demo},
    )
    monkeypatch.setattr(dependencies, "_active_runtime_account_id", "demo")
    monkeypatch.setattr(
        dependencies,
        "load_account_config",
        lambda account_id, reveal_secrets: {
            "MT5_LOGIN": "111111",
            "MT5_PASSWORD": "live-password",
            "MT5_SERVER": "Broker-Live",
        },
    )

    result = dependencies.activate_account_runtime("live")

    assert result["connected"] is True
    assert dependencies.active_runtime_account_id() == "live"
    assert live.reconfigure_calls[0]["login"] == 111111
    assert live.reconfigure_calls[0]["server"] == "Broker-Live"
    assert demo.disconnect_called is True


def test_activate_unconfigured_account_does_not_disconnect_existing_runtime(monkeypatch):
    live = _RuntimeExecutor(connected=True)
    unconfigured = _RuntimeExecutor(connected=False)
    monkeypatch.setattr(
        dependencies,
        "_mt5_executors",
        {"live": live, "new-demo": unconfigured},
    )
    monkeypatch.setattr(dependencies, "_active_runtime_account_id", "live")
    monkeypatch.setattr(
        dependencies,
        "load_account_config",
        lambda account_id, reveal_secrets: {},
    )

    result = dependencies.activate_account_runtime("new-demo")

    assert result["connected"] is False
    assert dependencies.active_runtime_account_id() == "live"
    assert live.disconnect_called is False
    assert unconfigured.reconfigure_calls == []


async def test_active_account_route_reconnects_the_selected_runtime(monkeypatch, tmp_path):
    _isolate_storage(monkeypatch, tmp_path)
    user = security.create_user("owner@example.com", "correct horse battery")
    live = account_store.create_account(user["id"], "Live Account")
    demo = account_store.create_account(user["id"], "Demo Account")
    account_store.set_user_active_account(user["id"], demo["id"])
    runtime_calls: list[str] = []

    def activate_runtime(account_id: str) -> dict:
        runtime_calls.append(account_id)
        return {"success": True, "connected": True, "health": {}}

    monkeypatch.setattr(accounts_router, "activate_account_runtime", activate_runtime)

    result = await accounts_router.set_active_account(live["id"], current_user=user)

    assert result["active_account_id"] == live["id"]
    assert result["runtime"] == {"success": True, "connected": True, "error": None}
    assert runtime_calls == [live["id"]]


def test_restore_account_executor_reconnects_saved_runtime_without_displacing_another(
    monkeypatch,
):
    executor = _RuntimeExecutor(connected=False)
    monkeypatch.setattr(dependencies, "_mt5_executors", {"primary": executor})
    monkeypatch.setattr(dependencies, "_active_runtime_account_id", None)
    monkeypatch.setattr(
        dependencies,
        "load_account_config",
        lambda account_id, reveal_secrets: {
            "MT5_LOGIN": "123456",
            "MT5_PASSWORD": "saved-password",
            "MT5_SERVER": "Broker-Real",
        },
    )
    calls = []

    def connect(account_id, config):
        calls.append((account_id, config["MT5_SERVER"]))
        return {"success": True, "connected": True, "health": {}}

    monkeypatch.setattr(dependencies, "connect_account_executor", connect)

    result = dependencies.restore_account_executor("primary")

    assert result["connected"] is True
    assert calls == [("primary", "Broker-Real")]

    monkeypatch.setattr(dependencies, "_active_runtime_account_id", "other")
    refused = dependencies.restore_account_executor("primary")
    assert refused["connected"] is False
    assert calls == [("primary", "Broker-Real")]
