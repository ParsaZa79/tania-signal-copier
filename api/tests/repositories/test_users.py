from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, cast

import pytest
from alembic.autogenerate import compare_metadata
from alembic.config import Config as AlembicConfig
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import Table, inspect, select
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.db import session as db_session
from src.db.base import Base, include_app_schema_name
from src.models.account import AccountMembership, MembershipRole, TradingAccount
from src.models.audit import LegacyIdentityAlias
from src.models.copy import CopySubscription, CopyTraderProfile
from src.models.user import UserProfile, UserRole, UserStatus
from src.repositories.users import (
    create_user_profile,
    get_user_by_auth_subject,
    reconcile_verified_user_profile,
    set_user_access,
)

API_ROOT = Path(__file__).resolve().parents[2]


def test_copy_marketplace_is_the_current_alembic_revision() -> None:
    scripts = ScriptDirectory.from_config(AlembicConfig(API_ROOT / "alembic.ini"))
    head = scripts.get_revision("head")
    assert head is not None
    assert head.revision == "0005_copy_trade_sizing"
    assert head.down_revision == "0004_rebind_workos_identity"


def test_user_profile_is_owned_by_app_schema_without_auth_foreign_key() -> None:
    table = cast(Table, UserProfile.__table__)

    assert table.schema == "app"
    assert table.name == "app_user_profiles"
    assert table.c.email.unique is True
    assert {column.name for column in table.primary_key} == {"auth_subject"}
    assert "id" not in table.c

    mapper = inspect(UserProfile)
    assert "password" not in mapper.attrs
    assert "credentials" not in mapper.attrs


@pytest.mark.integration
async def test_user_repository_defaults_verified_identity_to_trader(
    repository_session: AsyncSession,
) -> None:
    profile = await create_user_profile(
        repository_session,
        auth_subject="workos-user-1",
        email="  TRADER@Example.COM ",
        email_verified=True,
    )
    await repository_session.flush()

    assert profile.auth_subject == "workos-user-1"
    assert profile.email == "trader@example.com"
    assert profile.email_verified is True
    assert profile.role is UserRole.TRADER
    assert profile.status is UserStatus.ACTIVE
    assert await get_user_by_auth_subject(repository_session, "workos-user-1") is profile


@pytest.mark.integration
async def test_user_access_change_is_explicit_and_persisted(
    repository_session: AsyncSession,
) -> None:
    profile = await create_user_profile(
        repository_session,
        auth_subject="workos-user-2",
        email="admin@example.com",
        email_verified=True,
    )

    await set_user_access(
        repository_session,
        profile.auth_subject,
        role=UserRole.ADMIN,
        status=UserStatus.DISABLED,
    )
    await repository_session.flush()

    stored = await repository_session.scalar(
        select(UserProfile).where(UserProfile.auth_subject == profile.auth_subject)
    )
    assert stored is not None
    assert stored.role is UserRole.ADMIN
    assert stored.status is UserStatus.DISABLED


@pytest.mark.integration
async def test_migrated_schema_matches_sqlalchemy_metadata(
    repository_session: AsyncSession,
) -> None:
    connection = await repository_session.connection()

    def compare(connection: Connection) -> list[Any]:
        context = MigrationContext.configure(
            connection,
            opts={
                "include_schemas": True,
                "include_name": include_app_schema_name,
                "compare_type": True,
                "compare_server_default": True,
            },
        )
        return compare_metadata(context, Base.metadata)

    differences = await connection.run_sync(compare)
    assert differences == []


@pytest.mark.integration
async def test_user_subject_and_email_are_unique(repository_session: AsyncSession) -> None:
    await create_user_profile(
        repository_session,
        auth_subject="duplicate-subject",
        email="first@example.com",
        email_verified=True,
    )
    await repository_session.flush()

    with pytest.raises(ValueError, match="already exists"):
        await create_user_profile(
            repository_session,
            auth_subject="duplicate-subject",
            email="second@example.com",
            email_verified=True,
        )


@pytest.mark.integration
async def test_verified_email_rebinds_legacy_subject_and_owned_records(
    repository_session: AsyncSession,
) -> None:
    legacy_subject = "legacy-local-user"
    workos_subject = "workos-user-current"
    profile = await create_user_profile(
        repository_session,
        auth_subject=legacy_subject,
        email="same-person@example.com",
        email_verified=True,
        role=UserRole.OWNER,
    )
    account = TradingAccount(name="Migrated trader account")
    follower_account = TradingAccount(name="Migrated follower account")
    repository_session.add_all([account, follower_account])
    await repository_session.flush()
    membership = AccountMembership(
        account_id=account.id,
        user_id=legacy_subject,
        role=MembershipRole.OWNER,
    )
    follower_membership = AccountMembership(
        account_id=follower_account.id,
        user_id=legacy_subject,
        role=MembershipRole.OWNER,
    )
    alias = LegacyIdentityAlias(
        user_id=legacy_subject,
        source="local-auth",
        legacy_id=legacy_subject,
    )
    trader = CopyTraderProfile(
        account_id=account.id,
        owner_user_id=legacy_subject,
        display_name="Migrated trader",
    )
    repository_session.add_all([membership, follower_membership, alias, trader])
    await repository_session.flush()
    subscription = CopySubscription(
        trader_id=trader.id,
        follower_account_id=follower_account.id,
        follower_user_id=legacy_subject,
    )
    repository_session.add(subscription)
    await repository_session.flush()
    account_id = account.id
    follower_account_id = follower_account.id
    alias_id = alias.id
    trader_id = trader.id
    subscription_id = subscription.id

    await reconcile_verified_user_profile(
        repository_session,
        auth_subject=workos_subject,
        email=profile.email,
        role=UserRole.OWNER,
    )
    await repository_session.flush()
    repository_session.expunge_all()

    assert await repository_session.get(UserProfile, legacy_subject) is None
    reconciled = await repository_session.get(UserProfile, workos_subject)
    assert reconciled is not None
    assert reconciled.email == "same-person@example.com"
    assert reconciled.role is UserRole.OWNER
    assert (
        await repository_session.get(AccountMembership, (account_id, workos_subject))
        is not None
    )
    assert (
        await repository_session.get(
            AccountMembership,
            (follower_account_id, workos_subject),
        )
        is not None
    )
    migrated_alias = await repository_session.get(LegacyIdentityAlias, alias_id)
    migrated_trader = await repository_session.get(CopyTraderProfile, trader_id)
    migrated_subscription = await repository_session.get(CopySubscription, subscription_id)
    assert migrated_alias is not None
    assert migrated_trader is not None
    assert migrated_subscription is not None
    assert migrated_alias.user_id == workos_subject
    assert migrated_trader.owner_user_id == workos_subject
    assert migrated_subscription.follower_user_id == workos_subject


@pytest.mark.integration
async def test_concurrent_user_creation_has_one_clean_winner(
    repository_database_url: str,
) -> None:
    engine = db_session.create_database_engine(repository_database_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async def create_once() -> UserProfile | ValueError:
        async with factory() as session:
            try:
                profile = await create_user_profile(
                    session,
                    auth_subject="concurrent-subject",
                    email="concurrent@example.com",
                    email_verified=True,
                )
                await session.commit()
                return profile
            except ValueError as error:
                await session.rollback()
                return error

    try:
        outcomes = await asyncio.gather(create_once(), create_once())
    finally:
        await engine.dispose()

    assert sum(isinstance(item, UserProfile) for item in outcomes) == 1
    assert sum(isinstance(item, ValueError) for item in outcomes) == 1
