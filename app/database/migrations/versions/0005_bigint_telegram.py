"""use BigInteger for telegram_id columns (Telegram IDs exceed int32 range)

Revision ID: 0005_bigint_telegram
Revises: 0004_string_columns
Create Date: 2026-07-02

Telegram user IDs can exceed the 32-bit integer range (max 2,147,483,647).
For example 6549101819 is out of int32 range and asyncpg rejects it with
``value out of int32 range``. This migration converts the affected columns
to BIGINT.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0005_bigint_telegram"
down_revision: Union[str, None] = "0004_string_columns"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Convert telegram_id columns from INTEGER to BIGINT."""
    # audit_logs.actor_telegram_id
    op.alter_column(
        "audit_logs", "actor_telegram_id",
        existing_type=sa.Integer(),
        type_=sa.BigInteger(),
        existing_nullable=True,
        postgresql_using="actor_telegram_id::bigint",
    )
    # notifications.recipient_telegram_id
    op.alter_column(
        "notifications", "recipient_telegram_id",
        existing_type=sa.Integer(),
        type_=sa.BigInteger(),
        existing_nullable=True,
        postgresql_using="recipient_telegram_id::bigint",
    )


def downgrade() -> None:
    """Revert BIGINT columns back to INTEGER (may truncate large IDs)."""
    op.alter_column(
        "notifications", "recipient_telegram_id",
        existing_type=sa.BigInteger(),
        type_=sa.Integer(),
        existing_nullable=True,
        postgresql_using="recipient_telegram_id::int",
    )
    op.alter_column(
        "audit_logs", "actor_telegram_id",
        existing_type=sa.BigInteger(),
        type_=sa.Integer(),
        existing_nullable=True,
        postgresql_using="actor_telegram_id::int",
    )
