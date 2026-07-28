import logging

from src.logging_filters import SuppressSymbolPriceAccessLog


def _access_record(method: str, path: str) -> logging.LogRecord:
    return logging.LogRecord(
        "uvicorn.access",
        logging.INFO,
        __file__,
        1,
        '%s - "%s %s HTTP/%s" %d',
        ("127.0.0.1:1234", method, path, "1.1", 200),
        None,
    )


def test_symbol_price_polling_is_omitted_from_access_logs() -> None:
    access_filter = SuppressSymbolPriceAccessLog()

    assert access_filter.filter(_access_record("GET", "/api/symbols/XAUUSDb/price")) is False
    assert (
        access_filter.filter(_access_record("GET", "/api/symbols/EURUSDb/price?source=header"))
        is False
    )


def test_other_requests_remain_in_access_logs() -> None:
    access_filter = SuppressSymbolPriceAccessLog()

    assert access_filter.filter(_access_record("POST", "/api/copy/traders")) is True
    assert access_filter.filter(_access_record("GET", "/api/symbols")) is True
