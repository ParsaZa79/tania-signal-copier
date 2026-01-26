"""FastAPI dependencies for dependency injection."""

from typing import Any

# Global executor instance (initialized in lifespan)
# Using Any type to avoid importing from bot package which requires telethon
_mt5_executor: Any = None


def get_mt5_executor() -> Any:
    """Get the MT5 executor instance.

    Returns:
        MT5Executor: The executor instance.

    Raises:
        RuntimeError: If executor is not initialized.
    """
    if _mt5_executor is None:
        raise RuntimeError("MT5 executor not initialized")
    return _mt5_executor


def set_mt5_executor(executor: Any) -> None:
    """Set the global MT5 executor instance.

    Args:
        executor: The MT5Executor instance to set.
    """
    global _mt5_executor
    _mt5_executor = executor


def clear_mt5_executor() -> None:
    """Clear the global MT5 executor instance."""
    global _mt5_executor
    _mt5_executor = None
