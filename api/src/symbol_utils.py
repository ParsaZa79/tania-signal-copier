"""Symbol normalization helpers for broker-specific naming."""

BROKER_SUFFIX = "b"


def to_broker_symbol(symbol: str, suffix: str = BROKER_SUFFIX) -> str:
    """Convert a base symbol to broker form without changing suffix casing."""
    normalized = symbol.strip().upper()
    if not normalized:
        return normalized
    if not suffix:
        return normalized

    base = (
        normalized[: -len(suffix)]
        if normalized.lower().endswith(suffix.lower())
        else normalized
    )
    return f"{base}{suffix}"


def to_base_symbol(symbol: str, suffix: str = BROKER_SUFFIX) -> str:
    """Convert a broker symbol to base form by removing suffix when present."""
    normalized = symbol.strip().upper()
    if not normalized:
        return normalized
    if normalized.lower().endswith(suffix.lower()):
        return normalized[: -len(suffix)]
    return normalized


def symbols_match(left: str, right: str, suffix: str = BROKER_SUFFIX) -> bool:
    """Check symbol equality ignoring broker suffix differences."""
    return to_base_symbol(left, suffix=suffix) == to_base_symbol(right, suffix=suffix)
