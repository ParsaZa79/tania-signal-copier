"""FastAPI main application."""

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from .account_store import get_websocket_account
from .config import config
from .db.runtime import (
    database_session_factory,
    start_database_runtime,
    stop_database_runtime,
)
from .dependencies import (
    clear_mt5_executor,
    get_executor_for_account_id,
    is_account_runtime_owner,
    restore_account_executor,
    set_mt5_executor_factory,
)
from .logging_filters import SuppressSymbolPriceAccessLog
from .routers import (
    access,
    account,
    accounts,
    copy,
    deprecated,
    health,
    mt5,
    orders,
    positions,
    symbols,
)
from .routers import (
    config as config_router,
)
from .security import bootstrap_admin_from_env, current_user_for_websocket, get_current_user
from .services.copy_legacy_migration import archive_legacy_copy_store
from .services.copy_worker import run_copy_worker
from .services.history_service import init_database
from .trading.executor import MT5Executor
from .websocket.broadcaster import start_broadcaster
from .websocket.manager import manager

# Background task reference
_broadcaster_task: asyncio.Task | None = None
_copy_worker_task: asyncio.Task | None = None

# Price polling is intentionally frequent and drowns out actionable API access
# entries. Keep the requests working while omitting only those access-log lines.
logging.getLogger("uvicorn.access").addFilter(SuppressSymbolPriceAccessLog())


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler for startup and shutdown."""
    global _broadcaster_task, _copy_worker_task

    print("Starting Trading Dashboard API...")

    # Initialize database
    await init_database()

    if await start_database_runtime():
        session_factory = database_session_factory()
        if session_factory is not None:
            await archive_legacy_copy_store(session_factory)
            _copy_worker_task = asyncio.create_task(run_copy_worker(session_factory))

    set_mt5_executor_factory(MT5Executor)
    bootstrap_admin_from_env()

    # Start account-aware WebSocket broadcaster.
    _broadcaster_task = asyncio.create_task(
        start_broadcaster(get_executor_for_account_id, manager, is_account_runtime_owner)
    )

    yield

    # Shutdown
    print("Shutting down...")

    # Cancel broadcaster
    if _broadcaster_task:
        _broadcaster_task.cancel()
        try:
            await _broadcaster_task
        except asyncio.CancelledError:
            pass

    if _copy_worker_task:
        _copy_worker_task.cancel()
        try:
            await _copy_worker_task
        except asyncio.CancelledError:
            pass

    clear_mt5_executor()
    await stop_database_runtime()

    print("Shutdown complete")


# Create FastAPI app
app = FastAPI(
    title="Trading Dashboard API",
    description="API for managing MT5 trading positions and orders",
    version="0.1.0",
    lifespan=lifespan,
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.api.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
protected = [Depends(get_current_user)]
app.include_router(access.router, prefix="/api/access", tags=["Access"])
app.include_router(
    accounts.router,
    prefix="/api/accounts",
    tags=["Accounts"],
    dependencies=protected,
)
app.include_router(health.router, prefix="/api/health", tags=["Health"])
app.include_router(mt5.router, prefix="/api/mt5", tags=["MT5"], dependencies=protected)
app.include_router(
    positions.router,
    prefix="/api/positions",
    tags=["Positions"],
    dependencies=protected,
)
app.include_router(orders.router, prefix="/api/orders", tags=["Orders"], dependencies=protected)
app.include_router(account.router, prefix="/api/account", tags=["Account"], dependencies=protected)
app.include_router(symbols.router, prefix="/api/symbols", tags=["Symbols"], dependencies=protected)
app.include_router(
    config_router.router,
    prefix="/api/config",
    tags=["Config"],
    dependencies=protected,
)
app.include_router(copy.router, prefix="/api/copy", tags=["Copy Trading"], dependencies=protected)
app.include_router(deprecated.router, prefix="/api", tags=["Deprecated"], dependencies=protected)
app.include_router(
    copy.internal_router,
    prefix="/api/internal/copy",
    tags=["Copy Runtime"],
)


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": "Trading Dashboard API",
        "version": "0.1.0",
        "docs": "/docs",
    }


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time updates.

    Clients connect here to receive position and account updates.
    """
    user = current_user_for_websocket(websocket)
    account = (
        get_websocket_account(user, websocket.query_params.get("account_id")) if user else None
    )
    if not user or not account:
        await websocket.close(code=1008)
        return

    # Restore saved credentials after an API/bridge restart before exposing the
    # live feed. The blocking RPyC handshake runs outside the event loop.
    await asyncio.to_thread(restore_account_executor, account["id"])
    await manager.connect(websocket, account["id"])
    try:
        while True:
            # Keep connection alive, handle any client messages
            data = await websocket.receive_text()
            # Could handle subscription requests or pings here
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        print(f"WebSocket error: {e}")
        manager.disconnect(websocket)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "src.main:app",
        host=config.api.host,
        port=config.api.port,
        reload=config.api.debug,
    )
