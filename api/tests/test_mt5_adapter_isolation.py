from __future__ import annotations

from src.trading.mt5_adapter import LinuxMT5Adapter


class _RemoteConnection:
    def __init__(self) -> None:
        self.closed = False
        self.evaluations: list[str] = []

    def eval(self, code: str):
        self.evaluations.append(code)
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
