from pathlib import Path

from src.models.copy import CopyVolumeMode
from src.routers.copy import merge_live_pending_orders
from src.services.copy_legacy_migration import _load_legacy_records
from src.services.copy_worker import (
    calculate_risk_volume,
    evaluate_daily_loss_limit,
    evaluate_risk_limits,
    select_copy_volume,
)


def test_risk_volume_uses_money_at_stop_and_rounds_down() -> None:
    result = calculate_risk_volume(
        balance=10_000,
        risk_pct=0.25,
        entry_price=2000,
        stop_loss=1995,
        value_per_price_unit_per_lot=10,
        volume_step=0.01,
    )

    assert result.blocked_reason is None
    assert result.volume == 0.5


def test_risk_volume_blocks_missing_or_invalid_stop_loss() -> None:
    missing = calculate_risk_volume(
        balance=10_000,
        risk_pct=0.25,
        entry_price=2000,
        stop_loss=None,
        value_per_price_unit_per_lot=10,
    )
    invalid = calculate_risk_volume(
        balance=10_000,
        risk_pct=0.25,
        entry_price=2000,
        stop_loss=2000,
        value_per_price_unit_per_lot=10,
    )

    assert missing.blocked_reason == "stop_loss_required"
    assert invalid.blocked_reason == "invalid_stop_loss"


def test_risk_volume_respects_broker_volume_limits() -> None:
    too_small = calculate_risk_volume(
        balance=100,
        risk_pct=0.25,
        entry_price=2000,
        stop_loss=1900,
        value_per_price_unit_per_lot=10,
        volume_min=0.01,
    )
    capped = calculate_risk_volume(
        balance=1_000_000,
        risk_pct=1,
        entry_price=100,
        stop_loss=99,
        value_per_price_unit_per_lot=1,
        volume_max=50,
    )

    assert too_small.blocked_reason == "trade_too_small_for_broker"
    assert capped.volume == 50


def test_fixed_copy_volume_uses_the_explicit_lot_size() -> None:
    result = select_copy_volume(
        volume_mode=CopyVolumeMode.FIXED,
        fixed_volume=0.01,
        source_volume=0.5,
        volume_min=0.01,
        volume_step=0.01,
    )

    assert result.volume == 0.01
    assert result.blocked_reason is None


def test_source_copy_volume_uses_the_traders_exact_lot_size() -> None:
    result = select_copy_volume(
        volume_mode=CopyVolumeMode.SOURCE,
        fixed_volume=0.01,
        source_volume=0.25,
        volume_min=0.01,
        volume_step=0.01,
    )

    assert result.volume == 0.25
    assert result.blocked_reason is None


def test_explicit_copy_volume_is_not_silently_adjusted() -> None:
    result = select_copy_volume(
        volume_mode=CopyVolumeMode.FIXED,
        fixed_volume=0.015,
        source_volume=None,
        volume_min=0.01,
        volume_step=0.01,
    )

    assert result.blocked_reason == "copy_volume_not_supported_by_broker"


def test_legacy_json_reader_is_safe_and_non_mutating(tmp_path: Path) -> None:
    missing = _load_legacy_records(tmp_path / "missing.json")
    invalid_path = tmp_path / "platform.json"
    invalid_path.write_text("not json", encoding="utf-8")

    assert missing == {}
    assert _load_legacy_records(invalid_path) == {}


def test_daily_and_combined_open_risk_limits() -> None:
    daily = evaluate_risk_limits(
        balance=10_000,
        daily_copy_pnl=-200,
        current_open_risk_pct=0.5,
        next_trade_risk_pct=0.5,
        daily_loss_limit_pct=2,
        total_open_risk_pct=2.5,
    )
    combined = evaluate_risk_limits(
        balance=10_000,
        daily_copy_pnl=-50,
        current_open_risk_pct=2.25,
        next_trade_risk_pct=0.5,
        daily_loss_limit_pct=2,
        total_open_risk_pct=2.5,
    )

    assert daily == "daily_loss_limit_reached"
    assert combined == "combined_open_risk_limit_reached"


def test_dollar_daily_loss_protection_does_not_depend_on_account_size() -> None:
    below_limit = evaluate_daily_loss_limit(
        daily_copy_pnl=-4.99,
        daily_loss_limit_amount=5,
        balance=0,
        legacy_daily_loss_limit_pct=1,
    )
    at_limit = evaluate_daily_loss_limit(
        daily_copy_pnl=-5,
        daily_loss_limit_amount=5,
        balance=0,
        legacy_daily_loss_limit_pct=1,
    )

    assert below_limit is None
    assert at_limit == "daily_loss_limit_reached"


def test_live_pending_orders_are_attached_to_the_matching_public_trader() -> None:
    traders = [
        {
            "account_id": "active-account",
            "markets": [],
            "pending_orders": [],
            "statistics": {"pending_order_count": 0},
        },
        {
            "account_id": "other-account",
            "markets": ["EURUSD"],
            "pending_orders": [],
            "statistics": {"pending_order_count": 0},
        },
    ]

    result = merge_live_pending_orders(
        traders,
        account_id="active-account",
        orders=[
            {
                "ticket": 199898322,
                "symbol": "XAUUSDb",
                "type": 3,
                "volume": 0.01,
                "price_open": 4069,
                "sl": 4092,
                "tp": 4028,
                "comment": "private broker comment",
            }
        ],
    )

    active = result[0]
    assert active["statistics"]["pending_order_count"] == 1
    assert active["markets"] == ["XAUUSD"]
    assert active["pending_orders"] == [
        {
            "symbol": "XAUUSD",
            "type": "sell_limit",
            "volume": 0.01,
            "price_open": 4069.0,
            "sl": 4092.0,
            "tp": 4028.0,
        }
    ]
    assert "ticket" not in active["pending_orders"][0]
    assert result[1]["pending_orders"] == []
