#!/usr/bin/env python3
"""Infer signal outcomes from recently fetched Telegram messages."""

from __future__ import annotations

import json
import os
import re
from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Iterable

ANALYSIS_DIR = Path(__file__).parent.parent / "analysis"
INPUT_FILE = ANALYSIS_DIR / "signals_raw.json"
OUTPUT_JSON = ANALYSIS_DIR / "signals_outcomes.json"
REPORT_FILE = ANALYSIS_DIR / "report.md"
RAW_MESSAGES_FILE = ANALYSIS_DIR / "raw_messages.md"
DEBUG_FILE = ANALYSIS_DIR / "signals_debug.md"

CHECK_MARKS = ("\u2705", "\u2714", "\u2713")
ENTRY_RE = re.compile(
    "@\\s*([0-9]+(?:\\.[0-9]+)?)\\s*(?:-|to|\\u2013|\\u2014)?\\s*([0-9]+(?:\\.[0-9]+)?)?",
    re.IGNORECASE,
)
SL_RE = re.compile(r"\bSL\b[:\s-]*([0-9]+(?:\.[0-9]+)?)", re.IGNORECASE)
TP_RE = re.compile(r"\bTP\d*\b[:\s-]*([0-9]+(?:\.[0-9]+)?)", re.IGNORECASE)
TP_HIT_RE = re.compile(
    r"\btp\s*\d*\b.*(hit|reached|done|target|closed)",
    re.IGNORECASE,
)
TP_NUM_RE = re.compile(r"\btp\s*([0-9]+)\b|\btp([0-9]+)\b", re.IGNORECASE)
PARTIAL_CLOSE_RE = re.compile(r"\bclose\s+([0-9]{1,3})\s*%", re.IGNORECASE)

SYMBOL_KEYWORDS = {
    "gold": "GOLD",
    "xauusd": "GOLD",
}

EXCLUDED_TOKENS = {
    "SL",
    "TP",
    "TP1",
    "TP2",
    "TP3",
    "BUY",
    "SELL",
    "HOLD",
    "ENTRY",
    "TARGET",
}

RAW_MESSAGE_LIMIT = int(os.getenv("RAW_MESSAGE_LIMIT", "0"))
DEBUG_SIGNAL_LIMIT = int(os.getenv("DEBUG_SIGNAL_LIMIT", "0"))


@dataclass
class Signal:
    """Represents a detected trading signal and its inferred outcome."""

    id: int
    date: str | None
    symbol: str
    direction: str
    entry_price: float | None
    entry_price_max: float | None
    stop_loss: float | None
    take_profits: list[float]
    is_re_entry: bool = False
    related_ids: list[int] = field(default_factory=list)
    tp_hits: list[int] = field(default_factory=list)
    tp_hit_at: dict[int, datetime] = field(default_factory=dict)

    @property
    def outcome(self) -> str:
        if not self.tp_hits:
            return "sl_hit"
        numbered = [tp for tp in self.tp_hits if tp > 0]
        if numbered and max(numbered) >= 2:
            return "tp2_hit"
        if 1 in numbered:
            return "tp1_hit"
        return "tp_hit_unnumbered"


def load_raw_messages() -> list[dict]:
    """Load raw Telegram messages from disk."""
    with open(INPUT_FILE) as f:
        data = json.load(f)
    return data.get("messages", [])


def strip_markdown(text: str) -> str:
    """Remove lightweight markdown/link syntax that hinders parsing."""
    cleaned = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    for marker in ("**", "__", "~~", "`"):
        cleaned = cleaned.replace(marker, "")
    return cleaned


def extract_symbol(text: str) -> str:
    """Infer the symbol from common keywords or uppercase tokens."""
    lowered = text.lower()
    for keyword, symbol in SYMBOL_KEYWORDS.items():
        if keyword in lowered:
            return symbol

    tokens = re.findall(r"\b[A-Z]{3,8}\b", text)
    for token in tokens:
        if token not in EXCLUDED_TOKENS:
            return token
    return "UNKNOWN"


def extract_direction(text: str) -> str | None:
    """Extract trade direction (BUY/SELL)."""
    match = re.search(r"\b(buy|sell)\b", text, re.IGNORECASE)
    return match.group(1).upper() if match else None


def extract_entry_range(text: str) -> tuple[float | None, float | None]:
    """Extract entry price or range following '@'."""
    match = ENTRY_RE.search(text)
    if not match:
        return None, None
    entry = float(match.group(1))
    entry_max = float(match.group(2)) if match.group(2) else None
    if entry_max is not None and entry_max < entry:
        entry, entry_max = entry_max, entry
    return entry, entry_max


def extract_stop_loss(text: str) -> float | None:
    """Extract stop loss price."""
    match = SL_RE.search(text)
    return float(match.group(1)) if match else None


def extract_take_profits(text: str) -> list[float]:
    """Extract all TP levels."""
    return [float(m.group(1)) for m in TP_RE.finditer(text)]


def is_re_entry(text: str) -> bool:
    """Detect re-entry phrasing."""
    lowered = text.lower()
    return any(phrase in lowered for phrase in ("re-entry", "re entry", "reentry"))


def is_signal_message(text: str) -> bool:
    """Heuristically detect full or re-entry signal messages."""
    direction = extract_direction(text)
    if not direction:
        return False
    if "tp hit" in text.lower():
        return False
    has_sl = extract_stop_loss(text) is not None
    has_tp = bool(extract_take_profits(text))
    return has_sl and (has_tp or is_re_entry(text))


def contains_check_mark(text: str) -> bool:
    """Return True when the message includes a check mark indicator."""
    return any(mark in text for mark in CHECK_MARKS)


def detect_tp_hit(text: str) -> int | None:
    """Return TP number for TP-hit messages, or 0 for unnumbered TP hits."""
    lowered = text.lower()
    if "tp" not in lowered:
        return None

    tp_hit = TP_HIT_RE.search(text) is not None or contains_check_mark(text)
    if not tp_hit:
        return None

    match = TP_NUM_RE.search(text)
    if not match:
        return 0
    groups = [g for g in match.groups() if g]
    return int(groups[0]) if groups else 0


def classify_event(text: str, tp_hit_number: int | None) -> tuple[str | None, str | None]:
    """Classify message-level events for debug visibility."""
    lowered = text.lower()

    if tp_hit_number is not None:
        if tp_hit_number > 0:
            return "tp_hit", f"TP{tp_hit_number}"
        return "tp_hit", "TP"

    if any(phrase in lowered for phrase in ("book some profits", "booking some profits", "book profits")):
        return "book_profits", None

    match = PARTIAL_CLOSE_RE.search(text)
    if match:
        return "partial_close", f"close {match.group(1)}%"
    if "close 70%" in lowered:
        return "partial_close", "close 70%"

    if is_re_entry(text):
        return "re_entry", None

    if "profit running" in lowered or "pips profit" in lowered:
        return "profit_update", None

    return None, None


def parse_date(value: str | None) -> datetime | None:
    """Parse ISO datetime strings safely."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def find_parent_signal(
    msg: dict,
    messages_by_id: dict[int, dict],
    message_to_signal: dict[int, int],
) -> int | None:
    """Follow reply chains to locate the nearest ancestor signal."""
    parent_id = msg.get("reply_to_msg_id")
    seen: set[int] = set()
    while parent_id and parent_id not in seen:
        seen.add(parent_id)
        if parent_id in message_to_signal:
            return message_to_signal[parent_id]
        parent = messages_by_id.get(parent_id)
        parent_id = parent.get("reply_to_msg_id") if parent else None
    return None


def build_signals(
    messages: Iterable[dict],
) -> tuple[list[Signal], dict[int, int], dict[int, dict[str, str | int | None]]]:
    """Detect signals and attach related TP-hit messages."""
    ordered = sorted(messages, key=lambda m: m.get("id", 0))
    messages_by_id = {m["id"]: m for m in ordered if "id" in m}

    signals: list[Signal] = []
    signals_by_id: dict[int, Signal] = {}
    message_to_signal: dict[int, int] = {}
    latest_signal_by_symbol: dict[str, int] = {}
    latest_signal_id: int | None = None
    message_events: dict[int, dict[str, str | int | None]] = {}

    for msg in ordered:
        msg_id = msg.get("id")
        text = msg.get("text") or ""
        if msg_id is None or not text.strip():
            continue

        cleaned = strip_markdown(text)

        if is_signal_message(cleaned):
            symbol = extract_symbol(cleaned)
            direction = extract_direction(cleaned) or "UNKNOWN"
            entry, entry_max = extract_entry_range(cleaned)
            stop_loss = extract_stop_loss(cleaned)
            take_profits = extract_take_profits(cleaned)

            signal = Signal(
                id=msg_id,
                date=msg.get("date"),
                symbol=symbol,
                direction=direction,
                entry_price=entry,
                entry_price_max=entry_max,
                stop_loss=stop_loss,
                take_profits=take_profits,
                is_re_entry=is_re_entry(cleaned),
            )
            signals.append(signal)
            signals_by_id[msg_id] = signal
            message_to_signal[msg_id] = msg_id
            latest_signal_by_symbol[symbol] = msg_id
            latest_signal_id = msg_id
            message_events[msg_id] = {
                "event_type": "signal",
                "tp_hit_number": None,
                "event_detail": None,
            }
            continue

        tp_hit_number = detect_tp_hit(cleaned)
        symbol = extract_symbol(cleaned)
        msg_date = parse_date(msg.get("date"))
        event_type, event_detail = classify_event(cleaned, tp_hit_number)

        signal_id = find_parent_signal(msg, messages_by_id, message_to_signal)
        if signal_id is None and tp_hit_number is not None:
            signal_id = latest_signal_by_symbol.get(symbol) or latest_signal_id

        if signal_id is None or signal_id not in signals_by_id:
            if event_type:
                message_events[msg_id] = {
                    "event_type": event_type,
                    "tp_hit_number": tp_hit_number,
                    "event_detail": event_detail,
                }
            continue

        message_to_signal[msg_id] = signal_id
        signal = signals_by_id[signal_id]
        signal.related_ids.append(msg_id)
        message_events[msg_id] = {
            "event_type": event_type,
            "tp_hit_number": tp_hit_number,
            "event_detail": event_detail,
        }

        if tp_hit_number is not None:
            signal.tp_hits.append(tp_hit_number)
            if msg_date is not None:
                prev = signal.tp_hit_at.get(tp_hit_number)
                if prev is None or msg_date < prev:
                    signal.tp_hit_at[tp_hit_number] = msg_date

    return signals, message_to_signal, message_events


def format_price(value: float | None) -> str:
    """Format numeric prices consistently."""
    if value is None:
        return "-"
    return f"{value:.2f}".rstrip("0").rstrip(".")


def format_entry(signal: Signal) -> str:
    """Format entry price or range."""
    if signal.entry_price is None:
        return "-"
    if signal.entry_price_max is None:
        return format_price(signal.entry_price)
    low = format_price(signal.entry_price)
    high = format_price(signal.entry_price_max)
    return f"{low}-{high}"


def summarize_dates(messages: list[dict]) -> tuple[str, str]:
    """Return YYYY-MM-DD bounds for the analyzed messages."""
    dates = [parse_date(m.get("date")) for m in messages]
    valid = [d for d in dates if d is not None]
    if not valid:
        return "-", "-"
    return min(valid).date().isoformat(), max(valid).date().isoformat()


def save_outcomes(signals: list[Signal]) -> None:
    """Persist parsed signals for debugging and reuse."""
    signal_payloads: list[dict] = []
    for signal in signals:
        payload = asdict(signal)
        payload["tp_hit_at"] = {
            str(tp): dt.isoformat(timespec="seconds") for tp, dt in signal.tp_hit_at.items()
        }
        payload["outcome"] = signal.outcome
        signal_payloads.append(payload)
    payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "total_signals": len(signals),
        "signals": signal_payloads,
    }
    with open(OUTPUT_JSON, "w") as f:
        json.dump(payload, f, indent=2)


def outcome_label(signal: Signal) -> str:
    if signal.outcome == "tp2_hit":
        return "TP2 hit"
    if signal.outcome == "tp1_hit":
        return "TP1 hit"
    if signal.outcome == "tp_hit_unnumbered":
        return "TP hit"
    return "SL hit (inferred)"


def preview_text(text: str, limit: int = 180) -> str:
    compact = " ".join(text.split()).replace("|", "\\|")
    if len(compact) <= limit:
        return compact
    head = max(1, limit - 3)
    return compact[:head] + "..."


def generate_raw_messages(
    messages: list[dict],
    signals: list[Signal],
    message_to_signal: dict[int, int],
    message_events: dict[int, dict[str, str | int | None]],
) -> None:
    """Write a raw-message view limited to signal-related messages."""
    signals_by_id = {s.id: s for s in signals}
    relevant = [m for m in messages if m.get("id") in message_to_signal]
    relevant.sort(key=lambda m: m.get("id", 0), reverse=True)
    if RAW_MESSAGE_LIMIT > 0:
        relevant = relevant[:RAW_MESSAGE_LIMIT]

    lines: list[str] = []
    lines.append("# Raw Signal-Related Messages")
    lines.append("")
    lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append(f"Relevant messages: {len(relevant)}")
    lines.append(f"Signals detected: {len(signals)}")
    lines.append("")
    lines.append("| ID | Date | Reply To | Signal | Event | Signal Outcome | Text |")
    lines.append("|----|------|----------|--------|-------|----------------|------|")

    for msg in relevant:
        msg_id = msg.get("id")
        if msg_id is None:
            continue
        signal_id = message_to_signal.get(msg_id)
        signal = signals_by_id.get(signal_id) if signal_id is not None else None
        signal_outcome = outcome_label(signal) if signal else "-"
        event = message_events.get(msg_id) or {}
        event_type = event.get("event_type") or "-"
        event_detail = event.get("event_detail")
        if event_detail:
            event_label = f"{event_type} ({event_detail})"
        else:
            event_label = str(event_type)
        text = preview_text(msg.get("text") or "")
        date = (msg.get("date") or "")[:10]
        reply_to = msg.get("reply_to_msg_id") or "-"
        lines.append(
            f"| {msg_id} | {date} | {reply_to} | {signal_id} | {event_label} | {signal_outcome} | {text} |"
        )

    with open(RAW_MESSAGES_FILE, "w") as f:
        f.write("\n".join(lines))


def generate_signal_debug(
    messages: list[dict],
    signals: list[Signal],
    message_to_signal: dict[int, int],
    message_events: dict[int, dict[str, str | int | None]],
) -> None:
    """Write a per-signal chain debug view with raw message text."""
    messages_by_id = {m.get("id"): m for m in messages if m.get("id") is not None}
    signals_ordered = sorted(signals, key=lambda s: s.id, reverse=True)
    if DEBUG_SIGNAL_LIMIT > 0:
        signals_ordered = signals_ordered[:DEBUG_SIGNAL_LIMIT]

    lines: list[str] = []
    lines.append("# Signal Chains Debug")
    lines.append("")
    lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append(f"Signals included: {len(signals_ordered)}")
    if DEBUG_SIGNAL_LIMIT > 0:
        lines.append(f"Limit: {DEBUG_SIGNAL_LIMIT} (set DEBUG_SIGNAL_LIMIT=0 for all)")
    lines.append("")

    for signal in signals_ordered:
        signal_msg = messages_by_id.get(signal.id, {})
        signal_text = signal_msg.get("text") or ""
        date = (signal.date or "")[:19]
        tps = ", ".join(format_price(tp) for tp in signal.take_profits) or "-"
        related = sorted(set(signal.related_ids))
        related_str = ", ".join(str(rid) for rid in related) if related else "none"

        lines.append(f"## Signal {signal.id} - {signal.symbol} {signal.direction} - {outcome_label(signal)}")
        lines.append("")
        lines.append(f"- Date: {date}")
        lines.append(f"- Entry: {format_entry(signal)}")
        lines.append(f"- SL: {format_price(signal.stop_loss)}")
        lines.append(f"- TPs: {tps}")
        lines.append(f"- Related IDs: {related_str}")
        lines.append("")
        lines.append("Signal message:")
        lines.append("```")
        lines.append(signal_text.strip())
        lines.append("```")
        lines.append("")

        if not related:
            continue

        lines.append("Related messages:")
        lines.append("")
        for rid in related:
            rel_msg = messages_by_id.get(rid)
            if not rel_msg:
                continue
            rel_date = (rel_msg.get("date") or "")[:19]
            reply_to = rel_msg.get("reply_to_msg_id") or "-"
            rel_signal = message_to_signal.get(rid)
            event = message_events.get(rid) or {}
            event_type = event.get("event_type") or "-"
            event_detail = event.get("event_detail")
            if event_detail:
                event_label = f"{event_type} ({event_detail})"
            else:
                event_label = str(event_type)
            lines.append(
                f"[{rid}] {rel_date} (reply to {reply_to}, signal {rel_signal}, event {event_label})"
            )
            lines.append("```")
            lines.append((rel_msg.get("text") or "").strip())
            lines.append("```")
            lines.append("")

        lines.append("---")
        lines.append("")

    with open(DEBUG_FILE, "w") as f:
        f.write("\n".join(lines))


def generate_report(messages: list[dict], signals: list[Signal]) -> None:
    """Create a markdown report using the user's TP/SL inference rules."""
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M")
    date_start, date_end = summarize_dates(messages)

    total_signals = len(signals)
    tp2_signals = sum(1 for s in signals if s.outcome == "tp2_hit")
    tp1_signals = sum(1 for s in signals if s.outcome == "tp1_hit")
    tp_unnumbered_signals = sum(1 for s in signals if s.outcome == "tp_hit_unnumbered")
    tp_signals = tp1_signals + tp2_signals + tp_unnumbered_signals
    sl_signals = total_signals - tp_signals
    win_rate = (tp_signals / total_signals * 100) if total_signals else 0.0
    tp1_reached = tp1_signals + tp2_signals
    tp2_conversion = (tp2_signals / tp1_reached * 100) if tp1_reached else 0.0

    tp_hit_counter: Counter[int] = Counter()
    for signal in signals:
        for tp_hit in signal.tp_hits:
            if tp_hit is not None:
                tp_hit_counter[tp_hit] += 1

    signals_by_symbol: Counter[str] = Counter(s.symbol for s in signals)
    signals_by_direction: Counter[str] = Counter(s.direction for s in signals)
    re_entries = sum(1 for s in signals if s.is_re_entry)

    tp1_minutes: list[float] = []
    tp2_minutes: list[float] = []
    for signal in signals:
        signal_dt = parse_date(signal.date)
        if signal_dt is None:
            continue
        tp1_dt = signal.tp_hit_at.get(1)
        tp2_dt = signal.tp_hit_at.get(2)
        if tp1_dt and tp1_dt >= signal_dt:
            tp1_minutes.append((tp1_dt - signal_dt).total_seconds() / 60)
        if tp2_dt and tp2_dt >= signal_dt:
            tp2_minutes.append((tp2_dt - signal_dt).total_seconds() / 60)

    def avg_minutes(values: list[float]) -> float | None:
        return (sum(values) / len(values)) if values else None

    avg_tp1 = avg_minutes(tp1_minutes)
    avg_tp2 = avg_minutes(tp2_minutes)

    lines: list[str] = []
    lines.append("# Signal Outcome Report - TaniaTradingAcademy")
    lines.append("")
    lines.append(f"Generated: {generated_at}")
    lines.append(f"Date Range: {date_start} to {date_end}")
    lines.append(f"Messages Analyzed: {len(messages)}")
    lines.append(f"Signals Detected: {total_signals}")
    lines.append("")
    lines.append("---")
    lines.append("")

    lines.append("## Assumptions")
    lines.append("")
    lines.append("- TP hits are always mentioned explicitly in follow-up messages.")
    lines.append("- If no TP hit is mentioned for a signal, it is counted as SL hit.")
    lines.append("- Re-entry messages are treated as new signals when they include SL.")
    lines.append("")

    lines.append("## Performance Summary")
    lines.append("")
    lines.append(f"- TP2 hit signals: {tp2_signals}")
    lines.append(f"- TP1-only hit signals: {tp1_signals}")
    lines.append(f"- TP hit signals (unnumbered): {tp_unnumbered_signals}")
    lines.append(f"- TP hit signals (total): {tp_signals}")
    lines.append(f"- SL hit signals (inferred): {sl_signals}")
    lines.append(f"- Win rate (TP mentioned): {win_rate:.1f}%")
    lines.append(f"- TP1 -> TP2 conversion: {tp2_conversion:.1f}%")
    lines.append(f"- Re-entry signals: {re_entries}")
    if avg_tp1 is not None:
        lines.append(f"- Avg time to TP1: {avg_tp1:.1f} minutes")
    if avg_tp2 is not None:
        lines.append(f"- Avg time to TP2: {avg_tp2:.1f} minutes")
    lines.append("")
    lines.append("| Outcome | Count | % |")
    lines.append("|---------|-------|---|")
    lines.append(
        f"| TP2 hit | {tp2_signals} | {((tp2_signals / total_signals) * 100) if total_signals else 0:.1f}% |"
    )
    lines.append(
        f"| TP1 hit (no TP2) | {tp1_signals} | {((tp1_signals / total_signals) * 100) if total_signals else 0:.1f}% |"
    )
    lines.append(
        f"| TP hit (unnumbered) | {tp_unnumbered_signals} | {((tp_unnumbered_signals / total_signals) * 100) if total_signals else 0:.1f}% |"
    )
    lines.append(
        f"| TP hit (total) | {tp_signals} | {((tp_signals / total_signals) * 100) if total_signals else 0:.1f}% |"
    )
    lines.append(
        f"| SL hit (inferred) | {sl_signals} | {((sl_signals / total_signals) * 100) if total_signals else 0:.1f}% |"
    )
    lines.append("")

    lines.append("## Conversion Insight")
    lines.append("")
    lines.append(f"- Signals reaching TP1: {tp1_reached}")
    lines.append(f"- Of those, TP2 reached: {tp2_signals} ({tp2_conversion:.1f}%)")
    lines.append("")

    lines.append("## TP Hit Breakdown (Mentions)")
    lines.append("")
    if tp_hit_counter:
        lines.append("| TP # | Mentions |")
        lines.append("|------|----------|")
        for tp_number, count in sorted(tp_hit_counter.items()):
            label = f"TP{tp_number}" if tp_number > 0 else "TP (unnumbered)"
            lines.append(f"| {label} | {count} |")
    else:
        lines.append("No TP hit messages were detected.")
    lines.append("")

    lines.append("## Signal Mix")
    lines.append("")
    lines.append("### By Symbol")
    lines.append("")
    lines.append("| Symbol | Count |")
    lines.append("|--------|-------|")
    for symbol, count in signals_by_symbol.most_common():
        lines.append(f"| {symbol} | {count} |")
    lines.append("")
    lines.append("### By Direction")
    lines.append("")
    lines.append("| Direction | Count |")
    lines.append("|-----------|-------|")
    for direction, count in signals_by_direction.most_common():
        lines.append(f"| {direction} | {count} |")
    lines.append("")

    lines.append("## Recent Signals")
    lines.append("")
    lines.append("| Date | ID | Symbol | Dir | Entry | SL | TPs | Outcome |")
    lines.append("|------|----|--------|-----|-------|----|-----|---------|")

    recent_signals = sorted(signals, key=lambda s: s.id, reverse=True)[:60]
    for signal in recent_signals:
        date = (signal.date or "-")[:10]
        tps = ",".join(format_price(tp) for tp in signal.take_profits) or "-"
        if signal.outcome == "tp2_hit":
            outcome = "TP2 hit"
        elif signal.outcome == "tp1_hit":
            outcome = "TP1 hit"
        elif signal.outcome == "tp_hit_unnumbered":
            outcome = "TP hit (unnumbered)"
        else:
            outcome = "SL hit (inferred)"
        if signal.is_re_entry:
            outcome = f"{outcome}; re-entry"
        lines.append(
            f"| {date} | {signal.id} | {signal.symbol} | {signal.direction} | {format_entry(signal)} | {format_price(signal.stop_loss)} | {tps} | {outcome} |"
        )

    REPORT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(REPORT_FILE, "w") as f:
        f.write("\n".join(lines))


def main() -> None:
    """Run the outcome inference pipeline."""
    messages = load_raw_messages()
    signals, message_to_signal, message_events = build_signals(messages)
    save_outcomes(signals)
    generate_report(messages, signals)
    generate_raw_messages(messages, signals, message_to_signal, message_events)
    generate_signal_debug(messages, signals, message_to_signal, message_events)
    print(f"Signals analyzed: {len(signals)}")
    print(f"Report written to: {REPORT_FILE}")
    print(f"Outcomes saved to: {OUTPUT_JSON}")
    print(f"Raw messages written to: {RAW_MESSAGES_FILE}")
    print(f"Signal debug written to: {DEBUG_FILE}")


if __name__ == "__main__":
    main()
