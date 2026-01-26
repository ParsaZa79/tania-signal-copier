#!/usr/bin/env python3
"""
Analyze fetched signals using Claude AI parser.

Parses all messages and generates statistics for bot improvement analysis.
"""

import asyncio
import json
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from tania_signal_copier.parser import SignalParser

# Files
ANALYSIS_DIR = Path(__file__).parent.parent / "analysis"
INPUT_FILE = ANALYSIS_DIR / "signals_raw.json"
OUTPUT_FILE = ANALYSIS_DIR / "signals_parsed.json"
REPORT_FILE = ANALYSIS_DIR / "report.md"


def load_raw_signals():
    """Load raw signals from JSON file."""
    with open(INPUT_FILE) as f:
        return json.load(f)


async def analyze_signals():
    """Parse and analyze all fetched signals."""
    print("Loading raw signals...")

    data = load_raw_signals()

    messages = data["messages"]
    print(f"Loaded {len(messages)} messages")

    parser = SignalParser()
    parsed_results = []

    # Statistics
    stats = {
        "total": len(messages),
        "by_type": defaultdict(int),
        "with_reply": 0,
        "original_signals": 0,
        "tp_hits": defaultdict(int),
        "sl_moves_triggered": 0,
        "sl_moves_skipped": 0,  # "Book profits" type messages
        "close_signals": 0,
        "modifications": 0,
        "re_entries": 0,
        "compound_actions": 0,
        "non_trading": 0,
        "parsing_errors": 0,
    }

    # Track signal chains
    signal_chains = {}  # msg_id -> list of related messages

    print("\nParsing messages with Claude AI...")
    print("This will take a while (200 messages)...")

    for i, msg in enumerate(messages):
        msg_id = msg["id"]
        text = msg["text"]
        reply_to = msg["reply_to_msg_id"]

        if reply_to:
            stats["with_reply"] += 1

        # Skip empty messages
        if not text.strip():
            stats["by_type"]["empty"] += 1
            continue

        # Parse with AI
        try:
            signal = await parser.parse_signal(text)

            result = {
                "id": msg_id,
                "date": msg["date"],
                "text": text[:500],  # Truncate for storage
                "reply_to": reply_to,
                "parsed": None,
            }

            if signal is None:
                stats["by_type"]["not_trading"] += 1
                stats["non_trading"] += 1
                result["message_type"] = "not_trading"
            else:
                msg_type = signal.message_type.value
                stats["by_type"][msg_type] += 1

                result["message_type"] = msg_type
                result["parsed"] = {
                    "symbol": signal.symbol,
                    "order_type": signal.order_type.value if signal.order_type else None,
                    "entry_price": signal.entry_price,
                    "stop_loss": signal.stop_loss,
                    "take_profits": signal.take_profits,
                    "confidence": signal.confidence,
                    "tp_hit_number": signal.tp_hit_number,
                    "move_sl_to_entry": signal.move_sl_to_entry,
                    "close_position": signal.close_position,
                    "new_stop_loss": signal.new_stop_loss,
                    "new_take_profit": signal.new_take_profit,
                }

                # Track specific types
                if msg_type in ["new_signal_complete", "new_signal_incomplete"]:
                    stats["original_signals"] += 1
                    signal_chains[msg_id] = {"original": msg, "replies": []}

                elif msg_type == "profit_notification":
                    if signal.tp_hit_number is not None:
                        stats["tp_hits"][signal.tp_hit_number] += 1
                        stats["sl_moves_triggered"] += 1
                    elif signal.move_sl_to_entry:
                        stats["sl_moves_triggered"] += 1
                    else:
                        # This is a "book profits" message that won't trigger SL move
                        stats["sl_moves_skipped"] += 1
                        result["issue"] = "PROFIT_NOTIFICATION_NO_ACTION"

                elif msg_type == "modification":
                    stats["modifications"] += 1

                elif msg_type == "re_entry":
                    stats["re_entries"] += 1

                elif msg_type == "close_signal":
                    stats["close_signals"] += 1

                elif msg_type == "compound_action":
                    stats["compound_actions"] += 1

                # Link to original signal
                if reply_to and reply_to in signal_chains:
                    signal_chains[reply_to]["replies"].append(result)

            parsed_results.append(result)

        except Exception as e:
            stats["parsing_errors"] += 1
            parsed_results.append({
                "id": msg_id,
                "text": text[:200],
                "error": str(e),
            })

        # Progress
        if (i + 1) % 10 == 0:
            print(f"  Parsed {i + 1}/{len(messages)} messages...")

    print(f"\nDone! Parsed {len(parsed_results)} messages")

    # Save parsed results
    save_parsed_results(parsed_results, stats)

    # Generate report
    generate_report(parsed_results, stats, signal_chains)

    # Print summary
    print_summary(stats)


def save_parsed_results(results: list, stats: dict) -> None:
    """Save parsed results to JSON."""
    output_data = {
        "analyzed_at": datetime.now().isoformat(),
        "statistics": dict(stats),
        "results": results,
    }

    # Convert defaultdict to regular dict for JSON
    output_data["statistics"]["by_type"] = dict(stats["by_type"])
    output_data["statistics"]["tp_hits"] = dict(stats["tp_hits"])

    with open(OUTPUT_FILE, "w") as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)

    print(f"Saved parsed results to: {OUTPUT_FILE}")


def generate_report(results: list, stats: dict, chains: dict) -> None:
    """Generate markdown analysis report."""
    report = []
    report.append("# Signal Analysis Report")
    report.append(f"\nGenerated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    report.append(f"\nTotal messages analyzed: {stats['total']}")

    # Message Type Breakdown
    report.append("\n## Message Type Breakdown\n")
    report.append("| Type | Count | % |")
    report.append("|------|-------|---|")
    for msg_type, count in sorted(stats["by_type"].items(), key=lambda x: -x[1]):
        pct = count / stats["total"] * 100
        report.append(f"| {msg_type} | {count} | {pct:.1f}% |")

    # Signal Performance
    report.append("\n## Signal Performance\n")
    report.append(f"- **Original signals**: {stats['original_signals']}")
    report.append(f"- **TP hit notifications**: {sum(stats['tp_hits'].values())}")
    for tp_num, count in sorted(stats["tp_hits"].items()):
        report.append(f"  - TP{tp_num}: {count}")
    report.append(f"- **Modifications**: {stats['modifications']}")
    report.append(f"- **Re-entries**: {stats['re_entries']}")
    report.append(f"- **Close signals**: {stats['close_signals']}")

    # Critical Issue: SL Moves Skipped
    report.append("\n## CRITICAL: Profit Notifications That Don't Trigger SL Movement\n")
    report.append(f"**SL moves triggered by TP hit/breakeven**: {stats['sl_moves_triggered']}")
    report.append(f"**SL moves SKIPPED (informational only)**: {stats['sl_moves_skipped']}")

    if stats['sl_moves_skipped'] > 0:
        pct = stats['sl_moves_skipped'] / (stats['sl_moves_skipped'] + stats['sl_moves_triggered']) * 100
        report.append(f"\n**{pct:.1f}% of profit notifications don't trigger SL protection!**")

    # Find specific examples of skipped SL moves
    skipped_examples = [r for r in results if r.get("issue") == "PROFIT_NOTIFICATION_NO_ACTION"]
    if skipped_examples:
        report.append("\n### Examples of Profit Notifications Without SL Action\n")
        report.append("These messages were classified as PROFIT_NOTIFICATION but did NOT trigger SL movement:\n")
        for ex in skipped_examples[:10]:  # Show up to 10 examples
            text_preview = ex["text"][:150].replace("\n", " ")
            report.append(f"- **[{ex['id']}]**: `{text_preview}...`")

    # Signal Chain Analysis
    report.append("\n## Signal Chain Analysis\n")
    complete_chains = 0
    incomplete_chains = 0
    for chain in chains.values():
        has_tp_hit = any(
            r.get("parsed", {}).get("tp_hit_number") is not None
            for r in chain["replies"]
        )
        if has_tp_hit:
            complete_chains += 1
        else:
            incomplete_chains += 1

    report.append(f"- Signals with TP hit confirmation: {complete_chains}")
    report.append(f"- Signals without TP hit confirmation: {incomplete_chains}")

    # Recommendations
    report.append("\n## Recommendations for Bot Improvement\n")

    if stats['sl_moves_skipped'] > 0:
        report.append("### 1. Handle 'Book Profits' Messages (HIGH PRIORITY)\n")
        report.append("Messages like 'Book some profits', '+X pips running' currently don't trigger any action.")
        report.append("**Solution**: Option A - Treat these as partial close signals, or Option B - Move SL to entry.")
        report.append("")

    report.append("### 2. Set Intermediate TPs on MT5 (MEDIUM PRIORITY)\n")
    report.append("Currently only the furthest TP is set on MT5. If the bot misses a TP notification,")
    report.append("the intermediate TPs are never protected.")
    report.append("**Solution**: Use partial lot sizes for each TP level.")
    report.append("")

    report.append("### 3. Verify SL/TP After Modifications (LOW PRIORITY)\n")
    report.append("Unlike trade execution, modify_position() doesn't verify the changes were applied.")
    report.append("**Solution**: Add post-modification verification like execute_signal() has.")

    # Save report
    with open(REPORT_FILE, "w") as f:
        f.write("\n".join(report))

    print(f"Saved report to: {REPORT_FILE}")


def print_summary(stats: dict) -> None:
    """Print summary statistics."""
    print("\n" + "=" * 60)
    print("ANALYSIS SUMMARY")
    print("=" * 60)

    print(f"\nTotal messages: {stats['total']}")
    print(f"Parsing errors: {stats['parsing_errors']}")

    print("\nMessage Types:")
    for msg_type, count in sorted(stats["by_type"].items(), key=lambda x: -x[1]):
        print(f"  {msg_type}: {count}")

    print(f"\nOriginal signals: {stats['original_signals']}")
    print(f"TP hits detected: {sum(stats['tp_hits'].values())}")
    for tp_num, count in sorted(stats["tp_hits"].items()):
        print(f"  TP{tp_num}: {count}")

    print("\nCRITICAL FINDING:")
    print(f"  SL moves triggered: {stats['sl_moves_triggered']}")
    print(f"  SL moves SKIPPED (informational): {stats['sl_moves_skipped']}")

    if stats['sl_moves_skipped'] > 0:
        pct = stats['sl_moves_skipped'] / (stats['sl_moves_skipped'] + stats['sl_moves_triggered']) * 100
        print(f"  >> {pct:.1f}% of profit notifications don't protect profits!")


if __name__ == "__main__":
    asyncio.run(analyze_signals())
