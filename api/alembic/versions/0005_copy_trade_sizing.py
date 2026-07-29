"""Add explicit copy-trade sizing and dollar protection.

Revision ID: 0005_copy_trade_sizing
Revises: 0004_rebind_workos_identity
"""

import sqlalchemy as sa

from alembic import op

revision: str = "0005_copy_trade_sizing"
down_revision: str | None = "0004_rebind_workos_identity"
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None

APP_SCHEMA = "app"


def upgrade() -> None:
    op.add_column(
        "copy_risk_policies",
        sa.Column("daily_loss_limit_amount", sa.Float(), nullable=True),
        schema=APP_SCHEMA,
    )
    op.add_column(
        "copy_subscriptions",
        sa.Column("volume_mode", sa.String(length=12), server_default="fixed", nullable=False),
        schema=APP_SCHEMA,
    )
    op.add_column(
        "copy_subscriptions",
        sa.Column("fixed_volume", sa.Float(), server_default="0.01", nullable=False),
        schema=APP_SCHEMA,
    )
    op.create_check_constraint(
        "copy_volume_mode",
        "copy_subscriptions",
        "volume_mode IN ('fixed', 'source')",
        schema=APP_SCHEMA,
    )


def downgrade() -> None:
    op.drop_constraint(
        "copy_volume_mode",
        "copy_subscriptions",
        type_="check",
        schema=APP_SCHEMA,
    )
    op.drop_column("copy_subscriptions", "fixed_volume", schema=APP_SCHEMA)
    op.drop_column("copy_subscriptions", "volume_mode", schema=APP_SCHEMA)
    op.drop_column("copy_risk_policies", "daily_loss_limit_amount", schema=APP_SCHEMA)
