"""revert enum types to plain VARCHAR (use string storage, not native enum)

Revision ID: 0004_string_columns
Revises: 0003_pg_enums
Create Date: 2026-07-02

Why: Python ``str, Enum`` classes have a name (e.g. ``SUPER_ADMIN``) and a
value (e.g. ``super_admin``). SQLAlchemy sends the *name* to the DB by
default, but Postgres native enums were created with the *values*. This
mismatch caused ``invalid input value for enum userrole: "SUPER_ADMIN"``.

The simplest robust fix is to store these columns as plain VARCHAR and let
the application layer (Python enums) handle validation. This works
identically on SQLite and Postgres.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0004_string_columns"
down_revision: Union[str, None] = "0003_pg_enums"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Convert enum columns back to VARCHAR and drop the native enum types."""
    # 1. Drop server_defaults first (so the type cast is not blocked).
    op.alter_column("tasks", "status", server_default=None, existing_type=sa.Enum(name="taskstatus"))
    op.alter_column("tasks", "priority", server_default=None, existing_type=sa.Enum(name="taskpriority"))
    op.alter_column("users", "role", server_default=None, existing_type=sa.Enum(name="userrole"))

    # 2. Cast columns back to VARCHAR.
    op.alter_column(
        "tasks", "status",
        type_=sa.String(length=32),
        existing_type=sa.Enum(name="taskstatus"),
        postgresql_using="status::text",
    )
    op.alter_column(
        "tasks", "priority",
        type_=sa.String(length=32),
        existing_type=sa.Enum(name="taskpriority"),
        postgresql_using="priority::text",
    )
    op.alter_column(
        "users", "role",
        type_=sa.String(length=32),
        existing_type=sa.Enum(name="userrole"),
        postgresql_using="role::text",
    )
    op.alter_column(
        "audit_logs", "action",
        type_=sa.String(length=32),
        existing_type=sa.Enum(name="auditaction"),
        postgresql_using="action::text",
    )

    # 3. Restore server_defaults as VARCHAR literals.
    op.alter_column("tasks", "status", server_default="pending", existing_type=sa.String(32))
    op.alter_column("tasks", "priority", server_default="medium", existing_type=sa.String(32))
    op.alter_column("users", "role", server_default="employee", existing_type=sa.String(32))

    # 4. Drop the native enum types.
    sa.Enum(name="taskstatus").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="taskpriority").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="userrole").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="auditaction").drop(op.get_bind(), checkfirst=True)


def downgrade() -> None:
    """No-op downgrade — the 0003 approach is abandoned in favour of VARCHAR."""
    pass
