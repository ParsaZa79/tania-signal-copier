"""Filters for high-volume, low-signal HTTP access log entries."""

from __future__ import annotations

import logging
import re

_SYMBOL_PRICE_PATH = re.compile(r"^/api/symbols/[^/?]+/price$")


class SuppressSymbolPriceAccessLog(logging.Filter):
    """Keep symbol polling requests out of Uvicorn's access log."""

    def filter(self, record: logging.LogRecord) -> bool:
        args = record.args
        if not isinstance(args, tuple) or len(args) < 3:
            return True

        method = str(args[1])
        path = str(args[2]).partition("?")[0]
        return method != "GET" or _SYMBOL_PRICE_PATH.fullmatch(path) is None
