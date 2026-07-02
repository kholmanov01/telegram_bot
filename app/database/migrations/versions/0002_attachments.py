"""attachments table — files / photos / documents linked to a task

Revision ID: 0002_attachments
Revises: 0001_initial
Create Date: 2025-01-02 00:00:00
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "0002_attachments"
down_revision: Union[str, None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "attachments",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("task_id", sa.Integer(), nullable=False),
        sa.Column("file_id", sa.String(length=512), nullable=False),
        sa.Column("file_unique_id", sa.String(length=256), nullable=False),
        sa.Column("file_type", sa.String(length=32), nullable=False),
        sa.Column("file_name", sa.String(length=255), nullable=True),
        sa.Column("file_size", sa.Integer(), nullable=True),
        sa.Column("caption", sa.Text(), nullable=True),
        sa.Column("mime_type", sa.String(length=128), nullable=True),
        sa.Column("uploaded_by", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["uploaded_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_attachments_task_id", "attachments", ["task_id"])
    op.create_index("ix_attachments_file_type", "attachments", ["file_type"])
    op.create_index("ix_attachments_uploaded_by", "attachments", ["uploaded_by"])


def downgrade() -> None:
    op.drop_index("ix_attachments_uploaded_by", table_name="attachments")
    op.drop_index("ix_attachments_file_type", table_name="attachments")
    op.drop_index("ix_attachments_task_id", table_name="attachments")
    op.drop_table("attachments")
