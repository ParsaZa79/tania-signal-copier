from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.account import AccountMembership, MembershipRole, TradingAccount
from src.repositories.copy import serialize_trader, upsert_trader
from src.repositories.users import create_user_profile


def test_serialize_trader_includes_persisted_pending_orders() -> None:
    now = datetime.now(UTC)
    profile = SimpleNamespace(
        id=uuid4(),
        account_id=uuid4(),
        owner_user_id="copy-profile-owner",
        display_name="Pending strategy",
        description="",
        is_copyable=True,
        markets=["XAUUSD"],
        statistics={
            "trade_count": 0,
            "pending_orders": [
                {
                    "symbol": "XAUUSDb",
                    "type": "sell_limit",
                    "volume": 0.01,
                    "price_open": 4069,
                    "sl": 4092,
                    "tp": 4028,
                }
            ],
        },
        stats_updated_at=now,
        created_at=now,
        updated_at=now,
    )

    serialized = serialize_trader(profile)

    assert serialized["statistics"]["trade_count"] == 0
    assert serialized["statistics"]["pending_order_count"] == 1
    assert serialized["pending_orders"][0]["symbol"] == "XAUUSD"
    assert serialized["pending_orders"][0]["tp"] == 4028.0


@pytest.mark.integration
async def test_trader_upsert_refreshes_server_managed_timestamps(
    repository_session: AsyncSession,
) -> None:
    owner = await create_user_profile(
        repository_session,
        auth_subject="copy-profile-owner",
        email="copy-profile-owner@example.com",
        email_verified=True,
    )
    account = TradingAccount(name="Copy profile account")
    repository_session.add(account)
    await repository_session.flush()
    repository_session.add(
        AccountMembership(
            account_id=account.id,
            user_id=owner.auth_subject,
            role=MembershipRole.OWNER,
        )
    )
    await repository_session.flush()

    profile = await upsert_trader(
        repository_session,
        user_id=owner.auth_subject,
        account_id=account.id,
        display_name="Initial name",
        description="Initial description",
        is_copyable=False,
    )
    updated = await upsert_trader(
        repository_session,
        user_id=owner.auth_subject,
        account_id=account.id,
        display_name="Updated name",
        description="Updated description",
        is_copyable=True,
    )

    assert updated is profile
    assert serialize_trader(updated)["updated_at"]
    assert updated.display_name == "Updated name"
