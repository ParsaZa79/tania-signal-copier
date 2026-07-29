from __future__ import annotations

from src.trading.mt5_adapter import LinuxMT5Adapter


class _RemoteConnection:
    def __init__(self, *, account_login: int = 123456) -> None:
        self.closed = False
        self.evaluations: list[str] = []
        self.account_login = account_login

    def eval(self, code: str):
        self.evaluations.append(code)
        if code == "getattr(mt5.account_info(), 'login', None)":
            return self.account_login
        return True

    def close(self) -> None:
        self.closed = True


def test_linux_adapter_disconnect_never_shuts_down_the_remote_terminal() -> None:
    connection = _RemoteConnection()
    adapter = LinuxMT5Adapter(host="mt5-2", port=8001)
    adapter._conn = connection

    adapter.shutdown()

    assert connection.closed is True
    assert connection.evaluations == []
    assert adapter._conn is None


def test_linux_adapter_login_requires_the_requested_account_identity() -> None:
    matching = LinuxMT5Adapter(host="mt5-2", port=8001)
    matching._conn = _RemoteConnection(account_login=123456)

    mismatched = LinuxMT5Adapter(host="mt5-3", port=8001)
    mismatched._conn = _RemoteConnection(account_login=654321)

    assert matching.login(123456, password="secret", server="Broker-Live") is True
    assert mismatched.login(123456, password="secret", server="Broker-Live") is False
    assert mismatched.last_error() == (-1, "MT5 account identity mismatch")
