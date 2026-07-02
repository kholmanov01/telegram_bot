"""add postgres native enum types for taskstatus, taskpriority, userrole

Revision ID: 0003_pg_enums
Revises: 0002_attachments
Create Date: 2026-07-02
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0003_pg_enums"
down_revision: Union[str, None] = "0002_attachments"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create native Postgres enum types and convert the columns to them.

    The columns were created as VARCHAR in 0001_initial because the model
    uses ``str, Enum`` (which SQLAlchemy stores as the enum *name*). Postgres
    requires the enum type to exist before it can be referenced in a cast
    (``$1::taskstatus``), so we create the types here and alter the columns.

    Columns with a server_default need the default dropped before the type
    change and re-added afterwards (Postgres can't auto-cast the default).
    """
    bind = op.get_bind()

    # 1. Create the enum types.
    taskstatus = sa.Enum(
        "pending", "completed", "expired", "archived",
        name="taskstatus",
    )
    taskpriority = sa.Enum(
        "low", "medium", "high", "urgent",
        name="taskpriority",
    )
    userrole = sa.Enum(
        "super_admin", "employee",
        name="userrole",
    )
    auditaction = sa.Enum(
        "employee_login", "employee_registered", "employee_created",
        "task_created", "task_updated", "task_completed", "task_expired",
        "task_archived", "task_restored", "notification_sent",
        "settings_updated", "login_failed",
        name="auditaction",
    )
    taskstatus.create(bind, checkfirst=True)
    taskpriority.create(bind, checkfirst=True)
    userrole.create(bind, checkfirst=True)
    auditaction.create(bind, checkfirst=True)

    # 2. Drop server_defaults that would block the type cast, alter type, then
    #    restore a sensible default.
    # tasks.status (default 'pending')
    op.alter_column("tasks", "status", server_default=None, existing_type=sa.String(32))
    op.alter_column(
        "tasks", "status", type_=taskstatus, existing_type=sa.String(32),
        postgresql_using="status::text::taskstatus",
    )
    op.alter_column("tasks", "status", server_default="pending", existing_type=taskstatus)

    # tasks.priority (default 'medium')
    op.alter_column("tasks", "priority", server_default=None, existing_type=sa.String(32))
    op.alter_column(
        "tasks", "priority", type_=taskpriority, existing_type=sa.String(32),
        postgresql_using="priority::text::taskpriority",
    )
    op.alter_column("tasks", "priority", server_default="medium", existing_type=taskpriority)

    # users.role (default 'employee')
    op.alter_column("users", "role", server_default=None, existing_type=sa.String(32))
    op.alter_column(
        "users", "role", type_=userrole, existing_type=sa.String(32),
        postgresql_using="role::text::userrole",
    )
    op.alter_column("users", "role", server_default="employee", existing_type=userrole)

    # audit_logs.action (no default — just convert)
    op.alter_column(
        "audit_logs", "action", type_=auditaction, existing_type=sa.String(32),
        postgresql_using="action::text::auditaction",
    )


def downgrade() -> None:
    """Revert columns to VARCHAR and drop the enum types."""
    op.alter_column(
        "tasks", "status",
        type_=sa.String(length=32),
        existing_type=sa.Enum(name="taskstatus"),
    )
    op.alter_column(
        "tasks", "priority",
        type_=sa.String(length=32),
        existing_type=sa.Enum(name="taskpriority"),
    )
    op.alter_column(
        "users", "role",
        type_=sa.String(length=32),
        existing_type=sa.Enum(name="userrole"),
    )
    op.alter_column(
        "audit_logs", "action",
        type_=sa.String(length=32),
        existing_type=sa.Enum(name="auditaction"),
    )
    sa.Enum(name="taskstatus").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="taskpriority").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="userrole").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="auditaction").drop(op.get_bind(), checkfirst=True)
