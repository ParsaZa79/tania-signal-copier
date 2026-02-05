"""Bot configuration and presets router."""

import json
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()

# Paths
BOT_DIR = Path(__file__).parent.parent.parent.parent / "bot"
ENV_PATH = BOT_DIR / ".env"
CACHE_PATH = BOT_DIR / ".env.gui_cache.json"
PRESETS_DIR = BOT_DIR / ".presets"
LAST_PRESET_PATH = PRESETS_DIR / "_last_preset.json"


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


def _read_env_file() -> dict[str, str]:
    """Read and parse .env file."""
    if not ENV_PATH.exists():
        return {}

    env: dict[str, str] = {}
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

    return env


def _write_env_file(updates: dict[str, str]) -> None:
    """Write updates to .env file, preserving existing structure."""
    lines: list[str] = []
    if ENV_PATH.exists():
        try:
            lines = ENV_PATH.read_text(encoding="utf-8").splitlines()
        except Exception:
            pass

    out_lines: list[str] = []
    seen: set[str] = set()

    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in line:
            out_lines.append(line)
            continue

        key = line.split("=", 1)[0].strip()
        if key in updates:
            out_lines.append(f"{key}={_format_env_value(updates[key])}")
            seen.add(key)
        else:
            out_lines.append(line)

    # Add new keys
    for key, value in updates.items():
        if key not in seen:
            out_lines.append(f"{key}={_format_env_value(value)}")

    content = "\n".join(out_lines).rstrip() + "\n"
    ENV_PATH.write_text(content, encoding="utf-8")


def _load_cache() -> dict[str, str]:
    """Load cached config values."""
    if not CACHE_PATH.exists():
        return {}

    try:
        data = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return {str(k): str(v) for k, v in data.items()}
    except Exception:
        pass

    return {}


def _save_cache(values: dict[str, str]) -> None:
    """Save config values to cache."""
    CACHE_PATH.write_text(json.dumps(values, indent=2), encoding="utf-8")


def _ensure_presets_dir() -> None:
    """Create presets directory if it doesn't exist."""
    PRESETS_DIR.mkdir(parents=True, exist_ok=True)


def _sanitize_preset_name(name: str) -> str:
    """Convert preset name to safe filename."""
    safe = "".join(c if c.isalnum() or c in " _-" else "" for c in name)
    return safe.strip().lower().replace(" ", "_").replace("-", "_")


class SaveConfigRequest(BaseModel):
    """Request body for saving config."""

    config: dict[str, str]
    write_env: bool = False


class SavePresetRequest(BaseModel):
    """Request body for saving a preset."""

    name: str
    values: dict[str, str]


# ============================================================
# Config Endpoints
# ============================================================


@router.get("")
@router.get("/")
async def get_config():
    """Get current bot configuration.

    Merges .env file with cached values (cache takes precedence).
    """
    try:
        env_values = _read_env_file()
        cache_values = _load_cache()
        merged = {**env_values, **cache_values}
        return {"success": True, "config": merged}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.put("")
@router.put("/")
async def save_config(request: SaveConfigRequest):
    """Save bot configuration.

    Always saves to cache. Optionally writes to .env file.
    """
    try:
        if not request.config or not isinstance(request.config, dict):
            raise HTTPException(status_code=400, detail="Invalid config")

        # Always save to cache
        _save_cache(request.config)

        # Optionally write to .env file
        if request.write_env:
            _write_env_file(request.config)

        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


# ============================================================
# Preset Endpoints
# ============================================================


@router.get("/presets")
async def list_presets():
    """List all saved presets."""
    try:
        _ensure_presets_dir()

        presets: list[dict] = []
        for path in PRESETS_DIR.glob("*.json"):
            if path.name == "_last_preset.json":
                continue

            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                presets.append({
                    "name": data.get("name", path.stem),
                    "created_at": data.get("created_at", ""),
                    "modified_at": data.get("modified_at", ""),
                })
            except Exception:
                continue

        presets.sort(key=lambda x: x["name"].lower())

        # Get last used preset
        last_preset: str | None = None
        if LAST_PRESET_PATH.exists():
            try:
                data = json.loads(LAST_PRESET_PATH.read_text(encoding="utf-8"))
                last_preset = data.get("name")
            except Exception:
                pass

        return {"success": True, "presets": presets, "lastPreset": last_preset}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/presets/{name}")
async def get_preset(name: str):
    """Get a specific preset by name."""
    try:
        _ensure_presets_dir()

        filename = _sanitize_preset_name(name) + ".json"
        preset_path = PRESETS_DIR / filename

        if not preset_path.exists():
            raise HTTPException(status_code=404, detail="Preset not found")

        data = json.loads(preset_path.read_text(encoding="utf-8"))

        # Update last preset
        LAST_PRESET_PATH.write_text(
            json.dumps({"name": data.get("name", name)}),
            encoding="utf-8",
        )

        return {
            "success": True,
            "preset": {
                "name": data.get("name", name),
                "created_at": data.get("created_at"),
                "modified_at": data.get("modified_at"),
                "values": data.get("values", {}),
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/presets")
async def save_preset(request: SavePresetRequest):
    """Save a preset (create or update)."""
    try:
        if not request.name or not isinstance(request.name, str):
            raise HTTPException(status_code=400, detail="Invalid preset name")

        _ensure_presets_dir()

        filename = _sanitize_preset_name(request.name) + ".json"
        preset_path = PRESETS_DIR / filename
        now = datetime.now().isoformat()

        # Preserve created_at if updating
        created_at = now
        if preset_path.exists():
            try:
                existing = json.loads(preset_path.read_text(encoding="utf-8"))
                created_at = existing.get("created_at", now)
            except Exception:
                pass

        data = {
            "name": request.name,
            "created_at": created_at,
            "modified_at": now,
            "values": request.values or {},
        }

        preset_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

        # Update last preset
        LAST_PRESET_PATH.write_text(json.dumps({"name": request.name}), encoding="utf-8")

        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.delete("/presets/{name}")
async def delete_preset(name: str):
    """Delete a preset by name."""
    try:
        _ensure_presets_dir()

        filename = _sanitize_preset_name(name) + ".json"
        preset_path = PRESETS_DIR / filename

        if not preset_path.exists():
            raise HTTPException(status_code=404, detail="Preset not found")

        preset_path.unlink()

        # Clear last preset if it matches
        if LAST_PRESET_PATH.exists():
            try:
                data = json.loads(LAST_PRESET_PATH.read_text(encoding="utf-8"))
                if data.get("name") == name:
                    LAST_PRESET_PATH.unlink()
            except Exception:
                pass

        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
