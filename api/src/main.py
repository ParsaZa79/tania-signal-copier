"""FastAPI main application."""

import asyncio
import importlib.util
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

# Load executor module directly to avoid importing telethon from bot's __init__.py
bot_src_path = Path(__file__).parent.parent.parent / "bot" / "src"

# Load the executor module directly without triggering package __init__.py
def _load_module_directly(module_name: str, file_path: Path):
    """Load a module directly from file path."""
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load module from {file_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module

# First load dependencies that executor needs
_load_module_directly(
    "tania_signal_copier.models",
    bot_src_path / "tania_signal_copier" / "models.py"
)
_load_module_directly(
    "tania_signal_copier.mt5_adapter",
    bot_src_path / "tania_signal_copier" / "mt5_adapter.py"
)
executor_module = _load_module_directly(
    "tania_signal_copier.executor",
    bot_src_path / "tania_signal_copier" / "executor.py"
)
MT5Executor = executor_module.MT5Executor

from .config import config
from .dependencies import clear_mt5_executor, set_mt5_executor
from .routers import account, health, orders, positions, symbols
from .services.history_service import init_database
from .websocket.broadcaster import start_broadcaster
from .websocket.manager import manager

# Background task reference
_broadcaster_task: asyncio.Task | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler for startup and shutdown."""
    global _broadcaster_task

    print("Starting Trading Dashboard API...")

    # Initialize database
    await init_database()

    # Initialize MT5 executor
    executor = MT5Executor(
        login=config.mt5.login,
        password=config.mt5.password,
        server=config.mt5.server,
    )

    # Connect to MT5
    connected = executor.connect()
    if connected:
        print("MT5 connected successfully")
        set_mt5_executor(executor)

        # Start WebSocket broadcaster
        _broadcaster_task = asyncio.create_task(start_broadcaster(executor, manager))
    else:
        print("Warning: MT5 connection failed. API will start but trading won't work.")
        set_mt5_executor(executor)  # Set anyway for health checks

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

    # Disconnect MT5
    executor.disconnect()
    clear_mt5_executor()

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
app.include_router(health.router, prefix="/api/health", tags=["Health"])
app.include_router(positions.router, prefix="/api/positions", tags=["Positions"])
app.include_router(orders.router, prefix="/api/orders", tags=["Orders"])
app.include_router(account.router, prefix="/api/account", tags=["Account"])
app.include_router(symbols.router, prefix="/api/symbols", tags=["Symbols"])


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
    await manager.connect(websocket)
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
