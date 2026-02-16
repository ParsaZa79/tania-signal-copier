"""System prompts management router."""

import json
from datetime import datetime
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()

# Path to custom prompts file (shared with the bot)
BOT_DIR = Path(__file__).parent.parent.parent.parent / "bot"
PROMPTS_PATH = BOT_DIR / ".system_prompts.json"

# Default prompts (mirrored from bot/src/tania_signal_copier/parser.py SignalParser class)
# Keep in sync with parser.py when the defaults change.
DEFAULT_SYSTEM_PROMPT = """Analyze this forex/gold trading message and extract ALL actions.

IMPORTANT: A message can contain MULTIPLE independent actions. Always return ALL actions in the "actions" array.

ACTION TYPES:
1. "new_signal" - Open new position/pending order (contains symbol + direction + usually entry/SL/TPs)
2. "modification" - Change SL/TP to specific price (e.g., "move SL to 2650", "new SL 2640")
3. "move_sl_to_entry" - Move SL to breakeven/entry (e.g., "SL to entry", "secure at breakeven")
4. "partial_close" - Close X% of position (e.g., "close half", "close 70%")
5. "full_close" - Close entire position (e.g., "close gold", "exit trade", "can close now", "close to secure profits")
6. "tp_hit" - TP was hit notification (e.g., "TP1 hit", "first target reached")
7. "re_entry" - Close losing position and re-enter (contains "re-entry" + new entry/SL)

MULTI-ACTION EXAMPLES:
- "CLOSE HALF FOR 54+ PIPS, MOVE SL TO ENTRY" → 2 actions: partial_close + move_sl_to_entry
- "TP1 HIT, MOVE SL TO BREAKEVEN" → 2 actions: tp_hit + move_sl_to_entry
- "Add Sell-Limit 4342, Update SL to 4344" → 2 actions: new_signal + modification

ORDER TYPE RULES (for new_signal actions):
- "buy" or "sell" = MARKET orders (execute immediately). Use for "BUY GOLD @", "SELL XAUUSD @".
- "buy_limit", "sell_limit", "buy_stop", "sell_stop" = PENDING orders. ONLY if message says "limit" or "stop".

MOVE_SL_TO_ENTRY vs MODIFICATION:
- Use "move_sl_to_entry" for: "SL to entry", "SL to breakeven", "secure at entry", "move SL to entry"
- Use "modification" with new_stop_loss for: "move SL to 2650", "SL 2640", "new SL 2635" (specific price)

TP_HIT RULES:
- ONLY use tp_hit if message EXPLICITLY confirms TP was hit: "TP1 hit", "First target reached", "TP2 ✅"
- Messages like "+50 pips running", "book some profits" are NOT tp_hit - they're informational

FULL_CLOSE RULES:
- Use full_close for direct commands AND suggestions/recommendations to close
- Examples: "close gold", "exit trade", "can close now", "should close", "close to secure profits", "fully close now"
- If the message recommends or suggests closing a position, treat it as full_close

PARTIAL_CLOSE RULES:
- If percentage is specified (e.g., "close 70%", "close half"), use that value
- If no percentage specified (e.g., "close partial", "book some profits"), default to 50%

Return JSON:
{{
    "symbol": "XAUUSD" or null,
    "actions": [
        {{
            "action_type": "new_signal|modification|move_sl_to_entry|partial_close|full_close|tp_hit|re_entry",
            "order_type": "buy|sell|buy_limit|sell_limit|buy_stop|sell_stop" or null,
            "entry_price": number or null,
            "entry_price_max": number or null,
            "stop_loss": number or null,
            "take_profits": [numbers] or [],
            "new_stop_loss": number or null,
            "new_take_profit": number or null,
            "close_percentage": number or null (for partial_close, e.g., 50 for "close half"),
            "tp_hit_number": 1|2|3|null (for tp_hit),
            "re_entry_price": number or null,
            "re_entry_price_max": number or null
        }}
    ],
    "confidence": 0-1
}}

IMPORTANT:
- ALWAYS populate "actions" array, even for single actions
- For non-trading messages (ads, greetings), return empty actions array: {{"symbol": null, "actions": [], "confidence": 1.0}}

Return ONLY valid JSON, no explanation."""

DEFAULT_CORRECTION_SYSTEM_PROMPT = """You are analyzing a CORRECTION message for a trading signal.

The original signal had these values:
- Entry Price: {original_entry}
- Stop Loss: {original_sl}
- Take Profits: {original_tps}
- Symbol: {symbol}
- Order Type: {order_type}

Common shorthand correction patterns traders use:
- "44*" or "*44" = The significant digits should be 44xx (e.g., 4146 was typo, meant 4446)
- "SL 2640" or "sl:2640" = New stop loss is 2640
- "TP 2700" or "tp:2700" = New take profit is 2700
- Just a number like "4446" = Usually correcting the most recently mentioned or most likely wrong value
- "44" (two digits) = Replace the significant digits in the wrong value

Analyze the correction and determine what value(s) the trader meant to fix.
Consider which original value the correction most likely refers to based on digit patterns.

Return JSON:
{{
    "corrected_entry": number or null,
    "corrected_stop_loss": number or null,
    "corrected_take_profits": [numbers] or null,
    "confidence": 0-1,
    "interpretation": "brief explanation of what was corrected and why"
}}

Return ONLY valid JSON, no explanation outside the JSON."""


def _load_custom_prompts() -> dict:
    """Load custom prompts from file."""
    if not PROMPTS_PATH.exists():
        return {}
    try:
        return json.loads(PROMPTS_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _save_custom_prompts(data: dict) -> None:
    """Save custom prompts to file."""
    data["modified_at"] = datetime.now().isoformat()
    PROMPTS_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


class SavePromptsRequest(BaseModel):
    """Request body for saving system prompts."""

    system_prompt: str | None = None
    correction_system_prompt: str | None = None


@router.get("")
@router.get("/")
async def get_prompts():
    """Get current system prompts.

    Returns the active prompts (custom if set, otherwise defaults)
    along with flags indicating which prompts are customized.
    """
    try:
        custom = _load_custom_prompts()

        system_prompt = custom.get("system_prompt") or DEFAULT_SYSTEM_PROMPT
        correction_prompt = custom.get("correction_system_prompt") or DEFAULT_CORRECTION_SYSTEM_PROMPT

        return {
            "success": True,
            "system_prompt": system_prompt,
            "correction_system_prompt": correction_prompt,
            "default_system_prompt": DEFAULT_SYSTEM_PROMPT,
            "default_correction_system_prompt": DEFAULT_CORRECTION_SYSTEM_PROMPT,
            "is_custom_system_prompt": "system_prompt" in custom,
            "is_custom_correction_prompt": "correction_system_prompt" in custom,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.put("")
@router.put("/")
async def save_prompts(request: SavePromptsRequest):
    """Save custom system prompts.

    Only saves prompts that are provided (non-None). Preserves existing
    custom values for prompts not included in the request.
    """
    try:
        if request.system_prompt is not None and not request.system_prompt.strip():
            raise HTTPException(
                status_code=400,
                detail="System prompt cannot be empty",
            )

        # Load existing custom prompts to preserve unmodified ones
        existing = _load_custom_prompts()

        if request.system_prompt is not None:
            existing["system_prompt"] = request.system_prompt
        if request.correction_system_prompt is not None:
            existing["correction_system_prompt"] = request.correction_system_prompt

        _save_custom_prompts(existing)
        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.delete("")
@router.delete("/")
async def reset_all_prompts():
    """Reset all prompts to defaults by removing the custom prompts file."""
    try:
        if PROMPTS_PATH.exists():
            PROMPTS_PATH.unlink()
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.delete("/{which}")
async def reset_prompt(which: Literal["system", "correction"]):
    """Reset a specific prompt to its default.

    Args:
        which: "system" to reset the signal parsing prompt,
               "correction" to reset the correction parsing prompt.
    """
    try:
        custom = _load_custom_prompts()
        key = "system_prompt" if which == "system" else "correction_system_prompt"

        if key in custom:
            del custom[key]

        # If no custom prompts remain, delete the file entirely
        remaining_keys = {k for k in custom if k != "modified_at"}
        if not remaining_keys:
            if PROMPTS_PATH.exists():
                PROMPTS_PATH.unlink()
        else:
            _save_custom_prompts(custom)

        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
