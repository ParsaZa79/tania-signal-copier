"""Bot control router."""

import asyncio
import os
import shutil
import signal
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()

# Paths
BOT_DIR = Path(__file__).parent.parent.parent.parent / "bot"
PID_FILE = BOT_DIR / ".bot.pid"
ENV_PATH = BOT_DIR / ".env"
CACHE_PATH = BOT_DIR / ".env.gui_cache.json"
STATE_PATH = BOT_DIR / "bot_state.json"

# Global state
_bot_process: subprocess.Popen | None = None
_bot_status: Literal["stopped", "starting", "running", "stopping", "error"] = "stopped"
_bot_error: str | None = None
_started_at: str | None = None

# Log manager will be injected from main.py
_log_manager = None


def set_log_manager(manager):
    """Set the log manager for streaming bot output."""
    global _log_manager
    _log_manager = manager


def _parse_env_value(raw: str) -> str:
    """Parse a value from .env file, removing quotes."""
    value = raw.strip()
    if len(value) >= 2 and (
        (value[0] == value[-1] == '"') or (value[0] == value[-1] == "'")
    ):
        return value[1:-1]
    return value


def _format_env_value(value: str) -> str:
    """Format a value for .env file, adding quotes if needed."""
    if value == "":
        return ""
    if any(ch.isspace() for ch in value) or "#" in value:
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    return value


async def _load_env_for_bot() -> dict[str, str]:
    """Load environment variables from .env and cache files."""
    import json

    env: dict[str, str] = {}

    # Load from .env file
    if ENV_PATH.exists():
        try:
            content = ENV_PATH.read_text(encoding="utf-8")
            for line in content.splitlines():
                stripped = line.strip()
                if not stripped or stripped.startswith("#") or "=" not in line:
                    continue
                key, raw_value = line.split("=", 1)
                env[key.strip()] = _parse_env_value(raw_value)
        except Exception:
            pass

    # Override with cache values
    if CACHE_PATH.exists():
        try:
            cache = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
            env.update(cache)
        except Exception:
            pass

    return env


async def _check_bot_running() -> tuple[bool, int | None]:
    """Check if bot process is running.

    Returns (is_running, pid).
    """
    if not PID_FILE.exists():
        return False, None

    try:
        pid = int(PID_FILE.read_text().strip())
    except (ValueError, OSError):
        return False, None

    # Check if process exists
    try:
        os.kill(pid, 0)  # Signal 0 just checks if process exists
        return True, pid
    except (ProcessLookupError, PermissionError):
        # Process doesn't exist, clean up PID file
        try:
            PID_FILE.unlink()
        except OSError:
            pass
        return False, None


async def _stream_output(proc: subprocess.Popen):
    """Stream process output to log manager."""
    global _log_manager

    async def read_stream(stream, level: str):
        """Read from stream and send to log manager."""
        if stream is None:
            return

        loop = asyncio.get_event_loop()

        while True:
            try:
                line = await loop.run_in_executor(None, stream.readline)
                if not line:
                    break
                text = line.decode("utf-8", errors="replace").rstrip()
                if text and _log_manager:
                    await _log_manager.broadcast_log(text, level)
            except Exception:
                break

    if proc.stdout:
        asyncio.create_task(read_stream(proc.stdout, "info"))
    if proc.stderr:
        asyncio.create_task(read_stream(proc.stderr, "error"))


class StartBotRequest(BaseModel):
    """Request body for starting the bot."""

    prevent_sleep: bool = False
    write_env: bool = False
    config: dict[str, str] | None = None


class StopBotRequest(BaseModel):
    """Request body for stopping the bot."""

    pass


@router.get("/status")
async def get_bot_status():
    """Get current bot status."""
    global _bot_status, _bot_error, _started_at

    running, pid = await _check_bot_running()

    # Sync state if process died externally
    if not running and _bot_status == "running":
        _bot_status = "stopped"
        _started_at = None

    return {
        "success": True,
        "status": "running" if running else _bot_status,
        "pid": pid if running else None,
        "started_at": _started_at if running else None,
        "error": _bot_error,
    }


@router.post("/start")
async def start_bot(request: StartBotRequest):
    """Start the bot process."""
    global _bot_process, _bot_status, _bot_error, _started_at

    running, _ = await _check_bot_running()
    if running or _bot_status in ("running", "starting"):
        raise HTTPException(status_code=400, detail="Bot is already running")

    _bot_status = "starting"
    _bot_error = None

    try:
        # Write config to .env if requested
        if request.write_env and request.config:
            lines: list[str] = []
            for key, value in request.config.items():
                if isinstance(value, str):
                    lines.append(f"{key}={_format_env_value(value)}")
            ENV_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")

        # Load environment
        env_vars = await _load_env_for_bot()
        process_env = {**os.environ, **env_vars, "PYTHONUNBUFFERED": "1"}

        # Build command
        uv_path = shutil.which("uv")
        if uv_path:
            command = [uv_path, "run", "python", "-m", "tania_signal_copier.bot"]
        else:
            command = [sys.executable, "-m", "tania_signal_copier.bot"]

        # Wrap with caffeinate on macOS if requested
        if request.prevent_sleep and sys.platform == "darwin":
            caffeinate = shutil.which("caffeinate")
            if caffeinate:
                command = [caffeinate, "-dims", *command]

        # Spawn process
        proc = subprocess.Popen(
            command,
            cwd=str(BOT_DIR),
            env=process_env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True,
        )

        _bot_process = proc
        _started_at = datetime.now().isoformat()

        # Save PID
        if proc.pid:
            PID_FILE.write_text(str(proc.pid), encoding="utf-8")

        _bot_status = "running"

        # Start streaming output
        await _stream_output(proc)

        # Monitor process in background
        async def monitor():
            global _bot_status, _bot_error, _bot_process, _started_at

            loop = asyncio.get_event_loop()
            code = await loop.run_in_executor(None, proc.wait)

            _bot_status = "stopped"
            if code != 0 and code is not None:
                _bot_error = f"Process exited with code {code}"

            _bot_process = None
            _started_at = None

            try:
                PID_FILE.unlink()
            except OSError:
                pass

        asyncio.create_task(monitor())

        return {
            "success": True,
            "status": "starting",
            "pid": proc.pid,
        }

    except Exception as e:
        _bot_status = "error"
        _bot_error = str(e)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/stop")
async def stop_bot():
    """Stop the bot process."""
    global _bot_process, _bot_status, _started_at

    running, pid = await _check_bot_running()

    if not running and _bot_status != "running":
        raise HTTPException(status_code=400, detail="Bot is not running")

    _bot_status = "stopping"

    # Try to stop by PID
    if pid:
        try:
            os.kill(pid, signal.SIGTERM)

            # Give it 5 seconds to terminate gracefully
            async def force_kill():
                await asyncio.sleep(5)
                try:
                    os.kill(pid, 0)  # Check if still running
                    os.kill(pid, signal.SIGKILL)
                except (ProcessLookupError, PermissionError):
                    pass

            asyncio.create_task(force_kill())

        except (ProcessLookupError, PermissionError):
            pass

    # Also try process handle
    if _bot_process:
        try:
            _bot_process.terminate()

            async def force_kill_proc():
                await asyncio.sleep(5)
                if _bot_process and _bot_process.poll() is None:
                    _bot_process.kill()

            asyncio.create_task(force_kill_proc())

        except Exception:
            pass

    # Clean up
    try:
        PID_FILE.unlink()
    except OSError:
        pass

    _bot_status = "stopped"
    _bot_process = None
    _started_at = None

    return {"success": True, "status": "stopped"}


@router.get("/positions")
async def get_tracked_positions():
    """Get bot's tracked positions from state file."""
    import json

    if not STATE_PATH.exists():
        return {
            "success": True,
            "positions": [],
            "total": 0,
            "open": 0,
            "closed": 0,
        }

    try:
        data = json.loads(STATE_PATH.read_text(encoding="utf-8"))
        positions_data = data.get("positions", {})
        positions: list[dict] = []

        for msg_id_str, dual_data in positions_data.items():
            msg_id = int(msg_id_str)

            if dual_data.get("scalp"):
                scalp = dual_data["scalp"]
                positions.append({
                    "msg_id": msg_id,
                    "mt5_ticket": scalp.get("mt5_ticket", 0),
                    "symbol": scalp.get("symbol", ""),
                    "role": "scalp",
                    "order_type": scalp.get("order_type", ""),
                    "entry_price": scalp.get("entry_price"),
                    "stop_loss": scalp.get("stop_loss"),
                    "lot_size": scalp.get("lot_size"),
                    "status": scalp.get("status", ""),
                    "opened_at": scalp.get("opened_at", ""),
                })

            if dual_data.get("runner"):
                runner = dual_data["runner"]
                positions.append({
                    "msg_id": msg_id,
                    "mt5_ticket": runner.get("mt5_ticket", 0),
                    "symbol": runner.get("symbol", ""),
                    "role": "runner",
                    "order_type": runner.get("order_type", ""),
                    "entry_price": runner.get("entry_price"),
                    "stop_loss": runner.get("stop_loss"),
                    "lot_size": runner.get("lot_size"),
                    "status": runner.get("status", ""),
                    "opened_at": runner.get("opened_at", ""),
                })

        # Sort by opened_at descending
        positions.sort(key=lambda x: x.get("opened_at", ""), reverse=True)

        return {
            "success": True,
            "positions": positions,
            "total": len(positions),
            "open": sum(1 for p in positions if p.get("status") == "open"),
            "closed": sum(1 for p in positions if p.get("status") == "closed"),
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.delete("/positions")
async def clear_tracked_positions():
    """Clear bot's tracked positions state file."""
    try:
        if STATE_PATH.exists():
            STATE_PATH.unlink()
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
