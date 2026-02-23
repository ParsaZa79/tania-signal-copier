"""Shared runtime data paths for bot config, presets, and state files."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
BOT_DIR = REPO_ROOT / "bot"
ENV_PATH = BOT_DIR / ".env"


def _resolve_data_dir() -> Path:
    """Resolve persistent data directory.

    Priority:
    1) BOT_DATA_DIR env var
    2) /app/data when running in containerized deployments
    3) repo-local bot directory for local development
    """
    configured = os.getenv("BOT_DATA_DIR", "").strip()
    if configured:
        return Path(configured).expanduser()
    if Path("/app").exists():
        return Path("/app/data")
    return BOT_DIR


DATA_DIR = _resolve_data_dir()
PID_FILE = DATA_DIR / ".bot.pid"
STATE_PATH = DATA_DIR / "bot_state.json"
CACHE_PATH = DATA_DIR / "bot_config_cache.json"
PRESETS_DIR = DATA_DIR / "presets"
LAST_PRESET_PATH = PRESETS_DIR / "_last_preset.json"

# Legacy locations inside /bot in older deployments
LEGACY_CACHE_PATH = BOT_DIR / ".env.gui_cache.json"
LEGACY_PRESETS_DIR = BOT_DIR / ".presets"
LEGACY_STATE_PATH = BOT_DIR / "bot_state.json"


def _copy_file_if_missing(source: Path, target: Path) -> None:
    if not source.exists() or target.exists():
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)


def _migrate_legacy_presets() -> None:
    if not LEGACY_PRESETS_DIR.exists():
        return
    PRESETS_DIR.mkdir(parents=True, exist_ok=True)
    for legacy_preset in LEGACY_PRESETS_DIR.glob("*.json"):
        target_path = PRESETS_DIR / legacy_preset.name
        if not target_path.exists():
            shutil.copy2(legacy_preset, target_path)


def bootstrap_runtime_data() -> None:
    """Ensure runtime directories exist and migrate legacy data once."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    PRESETS_DIR.mkdir(parents=True, exist_ok=True)
    _copy_file_if_missing(LEGACY_CACHE_PATH, CACHE_PATH)
    _copy_file_if_missing(LEGACY_STATE_PATH, STATE_PATH)
    _migrate_legacy_presets()


bootstrap_runtime_data()
