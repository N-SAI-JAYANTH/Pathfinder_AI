"""Add chat_sessions table

Revision ID: h9i0j1k2
Revises: g8h9i0j1
Create Date: 2026-05-17

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "h9i0j1k2"
down_revision: Union[str, Sequence[str], None] = "g8h9i0j1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "chat_sessions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("page_type", sa.String(), nullable=False),
        sa.Column("page_id", sa.String(), nullable=False, server_default=""),
        sa.Column("title", sa.String(), nullable=True),
        sa.Column("messages", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "page_type", "page_id", name="uq_chat_user_page"),
    )
    op.create_index(op.f("ix_chat_sessions_id"), "chat_sessions", ["id"], unique=False)
    op.create_index("ix_chat_sessions_user_page", "chat_sessions", ["user_id", "page_type", "page_id"])


def downgrade() -> None:
    op.drop_index("ix_chat_sessions_user_page", table_name="chat_sessions")
    op.drop_index(op.f("ix_chat_sessions_id"), table_name="chat_sessions")
    op.drop_table("chat_sessions")
