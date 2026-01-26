"""Health check router."""

from fastapi import APIRouter, Depends

from ..dependencies import get_mt5_executor

router = APIRouter()


@router.get("/")
async def health_check(executor=Depends(get_mt5_executor)) -> dict:
    """Check MT5 connection health.

    Returns:
        dict: Health status including connection state and account info.
    """
    try:
        health = executor.health_check()
        return {
            "status": "healthy" if health.get("connected") else "unhealthy",
            "mt5": health,
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "mt5": {
                "connected": False,
                "error": str(e),
            },
        }
