"""Analysis router for signal outcomes and reports."""

import asyncio
import json
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()

# Paths
BOT_DIR = Path(__file__).parent.parent.parent.parent / "bot"
ANALYSIS_DIR = BOT_DIR / "analysis"
OUTCOMES_PATH = ANALYSIS_DIR / "signals_outcomes.json"
SCRIPTS_DIR = BOT_DIR / "scripts"


class RunAnalysisRequest(BaseModel):
    """Request body for running analysis scripts."""

    action: str  # "fetch" or "report"
    total: int = 1000
    batch: int = 100
    delay: float = 2.0


@router.get("/summary")
async def get_analysis_summary():
    """Get analysis summary from signals_outcomes.json."""
    if not OUTCOMES_PATH.exists():
        return {
            "success": True,
            "summary": {
                "total_signals": 0,
                "tp2_hit": 0,
                "tp1_hit": 0,
                "sl_hit": 0,
                "tp_unnumbered": 0,
                "win_rate": 0,
                "tp1_to_tp2_conversion": 0,
                "date_range": None,
            },
        }

    try:
        data = json.loads(OUTCOMES_PATH.read_text(encoding="utf-8"))
        signals = data.get("signals", [])

        if len(signals) == 0:
            return {
                "success": True,
                "summary": {
                    "total_signals": 0,
                    "tp2_hit": 0,
                    "tp1_hit": 0,
                    "sl_hit": 0,
                    "tp_unnumbered": 0,
                    "win_rate": 0,
                    "tp1_to_tp2_conversion": 0,
                    "date_range": None,
                },
            }

        total = len(signals)
        tp2 = sum(1 for s in signals if s.get("outcome") == "tp2_hit")
        tp1 = sum(1 for s in signals if s.get("outcome") == "tp1_hit")
        sl = sum(1 for s in signals if s.get("outcome") == "sl_hit")
        tp_unnumbered = sum(1 for s in signals if s.get("outcome") == "tp_hit_unnumbered")

        tp_total = tp1 + tp2 + tp_unnumbered
        win_rate = (tp_total / total) * 100 if total > 0 else 0
        tp1_reached = tp1 + tp2
        conversion = (tp2 / tp1_reached) * 100 if tp1_reached > 0 else 0

        # Calculate average time to TP
        tp1_minutes: list[float] = []
        tp2_minutes: list[float] = []

        for signal in signals:
            signal_date_str = signal.get("date")
            if not signal_date_str:
                continue

            try:
                signal_date = datetime.fromisoformat(signal_date_str.replace("Z", "+00:00"))
            except Exception:
                continue

            tp_hit_at = signal.get("tp_hit_at", {})

            if tp_hit_at.get("1"):
                try:
                    tp1_date = datetime.fromisoformat(tp_hit_at["1"].replace("Z", "+00:00"))
                    if tp1_date >= signal_date:
                        tp1_minutes.append((tp1_date - signal_date).total_seconds() / 60)
                except Exception:
                    pass

            if tp_hit_at.get("2"):
                try:
                    tp2_date = datetime.fromisoformat(tp_hit_at["2"].replace("Z", "+00:00"))
                    if tp2_date >= signal_date:
                        tp2_minutes.append((tp2_date - signal_date).total_seconds() / 60)
                except Exception:
                    pass

        # Get date range
        dates = []
        for s in signals:
            date_str = s.get("date")
            if date_str:
                try:
                    dates.append(datetime.fromisoformat(date_str.replace("Z", "+00:00")))
                except Exception:
                    pass

        dates.sort()
        date_range = None
        if dates:
            date_range = {
                "start": dates[0].strftime("%Y-%m-%d"),
                "end": dates[-1].strftime("%Y-%m-%d"),
            }

        summary = {
            "total_signals": total,
            "tp2_hit": tp2,
            "tp1_hit": tp1,
            "sl_hit": sl,
            "tp_unnumbered": tp_unnumbered,
            "win_rate": win_rate,
            "tp1_to_tp2_conversion": conversion,
            "date_range": date_range,
        }

        if tp1_minutes:
            summary["avg_time_to_tp1_minutes"] = sum(tp1_minutes) / len(tp1_minutes)

        if tp2_minutes:
            summary["avg_time_to_tp2_minutes"] = sum(tp2_minutes) / len(tp2_minutes)

        return {"success": True, "summary": summary}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/run")
async def run_analysis(request: RunAnalysisRequest):
    """Run analysis scripts (fetch signals or generate report).

    Uses asyncio.create_subprocess_exec for safe command execution
    without shell injection risks.
    """
    # Determine which script to run
    if request.action == "fetch":
        script_path = SCRIPTS_DIR / "fetch_signals.py"
        args = [
            "--total",
            str(request.total),
            "--batch-size",
            str(request.batch),
            "--delay",
            str(request.delay),
        ]
    elif request.action == "report":
        script_path = SCRIPTS_DIR / "report_signal_outcomes.py"
        args = []
    else:
        raise HTTPException(status_code=400, detail="Invalid action")

    # Check if script exists
    if not script_path.exists():
        raise HTTPException(status_code=404, detail=f"Script not found: {script_path}")

    # Build command - using create_subprocess_exec for safety (no shell)
    uv_path = shutil.which("uv")
    if uv_path:
        cmd = [uv_path, "run", "python", str(script_path)] + args
    else:
        cmd = [sys.executable, str(script_path)] + args

    try:
        # Run the script using subprocess_exec (safe, no shell)
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=str(BOT_DIR),
            env={**os.environ, "PYTHONUNBUFFERED": "1"},
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout, stderr = await proc.communicate()

        stdout_text = stdout.decode("utf-8", errors="replace") if stdout else ""
        stderr_text = stderr.decode("utf-8", errors="replace") if stderr else ""

        if proc.returncode == 0:
            return {
                "success": True,
                "output": stdout_text,
                "action": request.action,
            }
        else:
            return {
                "success": False,
                "error": stderr_text or stdout_text or f"Exit code {proc.returncode}",
            }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
