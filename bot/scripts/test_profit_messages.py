#!/usr/bin/env python3
"""Test profit notification message parsing.

Tests that the parser correctly distinguishes between:
- Informational messages (no action): "Book profits", "35 pips running"
- Actionable messages (move SL): "TP1 hit", "Move SL to entry"
"""

import asyncio

from tania_signal_copier.parser import SignalParser

TEST_CASES = [
    # === Should NOT trigger move_sl_to_entry ===
    {
        "name": "Book some profits",
        "message": "GOLD - 35+ pips profit running\n\nBook some profits...",
        "expected_move_sl": False,
        "expected_tp_hit": None,
    },
    {
        "name": "Secure profits",
        "message": "GOLD\nSecure some profits\n+40 pips",
        "expected_move_sl": False,
        "expected_tp_hit": None,
    },
    {
        "name": "Take some profits",
        "message": "XAUUSD - Take some profits here\nWe're up 50 pips",
        "expected_move_sl": False,
        "expected_tp_hit": None,
    },
    {
        "name": "Pips running only",
        "message": "GOLD - Over 40 Pips Profit Running...",
        "expected_move_sl": False,
        "expected_tp_hit": None,
    },
    {
        "name": "Good profits message",
        "message": "GOLD running in good profits\nHold your positions",
        "expected_move_sl": False,
        "expected_tp_hit": None,
    },
    # === SHOULD trigger move_sl_to_entry ===
    {
        "name": "TP1 hit explicit",
        "message": "GOLD TP1 hit!\nMove SL to entry",
        "expected_move_sl": True,
        "expected_tp_hit": 1,
    },
    {
        "name": "First target reached",
        "message": "XAUUSD - First target reached\nSecure at breakeven",
        "expected_move_sl": True,
        "expected_tp_hit": 1,
    },
    {
        "name": "TP1 emoji",
        "message": "GOLD TP1 ✅\n+30 pips locked",
        "expected_move_sl": True,
        "expected_tp_hit": 1,
    },
    {
        "name": "Target 1 done",
        "message": "GOLD - Target 1 done!\nSL to entry now",
        "expected_move_sl": True,
        "expected_tp_hit": 1,
    },
    {
        "name": "TP2 hit",
        "message": "GOLD TP2 hit!\nMove SL to TP1",
        "expected_move_sl": True,
        "expected_tp_hit": 2,
    },
    {
        "name": "Second target reached",
        "message": "XAUUSD Second target reached\nAdjust SL",
        "expected_move_sl": True,
        "expected_tp_hit": 2,
    },
    {
        "name": "Move SL to breakeven explicit",
        "message": "GOLD - Move SL to breakeven",
        "expected_move_sl": True,
        "expected_tp_hit": None,  # No specific TP, just move instruction
    },
    {
        "name": "SL to entry instruction",
        "message": "XAUUSD - SL to entry now\nSecure your position",
        "expected_move_sl": True,
        "expected_tp_hit": None,
    },
]


async def test_message(parser: SignalParser, test_case: dict) -> dict:
    """Test a single message and return results."""
    result = await parser.parse_signal(test_case["message"])

    if result is None:
        return {
            "name": test_case["name"],
            "passed": False,
            "error": "Parser returned None (classified as not_trading)",
            "actual_move_sl": None,
            "actual_tp_hit": None,
            "will_take_action": False,
        }

    actual_move_sl = result.move_sl_to_entry
    actual_tp_hit = result.tp_hit_number

    # What matters: will the bot take action?
    # Bot takes action if: tp_hit_number is set OR move_sl_to_entry is True
    will_take_action = actual_tp_hit is not None or actual_move_sl
    expected_action = test_case["expected_move_sl"]  # This really means "should take action"

    # Check if action expectation matches
    action_correct = will_take_action == expected_action

    # Check tp_hit_number if we expect a specific TP
    tp_hit_correct = True
    if test_case["expected_tp_hit"] is not None:
        tp_hit_correct = actual_tp_hit == test_case["expected_tp_hit"]

    passed = action_correct and tp_hit_correct

    return {
        "name": test_case["name"],
        "passed": passed,
        "expected_action": expected_action,
        "will_take_action": will_take_action,
        "expected_tp_hit": test_case["expected_tp_hit"],
        "actual_tp_hit": actual_tp_hit,
        "actual_move_sl": actual_move_sl,
        "message_type": result.message_type.value,
        "action_correct": action_correct,
        "tp_hit_correct": tp_hit_correct,
    }


async def main():
    """Run all test cases."""
    parser = SignalParser()

    print("=" * 70)
    print("PROFIT NOTIFICATION PARSER TEST")
    print("=" * 70)
    print()

    results = []
    passed = 0
    failed = 0

    for i, test_case in enumerate(TEST_CASES, 1):
        print(f"[{i}/{len(TEST_CASES)}] Testing: {test_case['name']}")
        print(f"    Message: {test_case['message'][:50]}...")

        result = await test_message(parser, test_case)
        results.append(result)

        if result["passed"]:
            passed += 1
            print(f"    ✅ PASSED (action={result['will_take_action']}, tp_hit={result['actual_tp_hit']})")
        else:
            failed += 1
            print("    ❌ FAILED")
            if "error" in result:
                print(f"       Error: {result['error']}")
            else:
                print(f"       Expected: action={result['expected_action']}, tp_hit={result['expected_tp_hit']}")
                print(f"       Actual:   action={result['will_take_action']}, tp_hit={result['actual_tp_hit']}, move_sl={result['actual_move_sl']}")
        print()

    # Summary
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"Passed: {passed}/{len(TEST_CASES)}")
    print(f"Failed: {failed}/{len(TEST_CASES)}")
    print()

    if failed > 0:
        print("FAILED TESTS:")
        for r in results:
            if not r["passed"]:
                print(f"  - {r['name']}")
                if "error" not in r:
                    print(f"    Expected action={r['expected_action']}, got action={r['will_take_action']}")
                    print(f"    Expected tp_hit={r['expected_tp_hit']}, got tp_hit={r['actual_tp_hit']}")

    return failed == 0


if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)
