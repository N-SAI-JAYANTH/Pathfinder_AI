"""Add roadmap_bandit_decisions for bandit credit assignment

Revision ID: f7a8b9c0
Revises: eb6c29bae3a2
Create Date: 2026-05-03

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f7a8b9c0"
down_revision: Union[str, Sequence[str], None] = "eb6c29bae3a2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if "roadmap_bandit_decisions" in insp.get_table_names():
        return
    op.create_table(
        "roadmap_bandit_decisions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("job_id", sa.Integer(), nullable=True),
        sa.Column("roadmap_id", sa.Integer(), nullable=True),
        sa.Column("task_id", sa.String(), nullable=True),
        sa.Column("selected_action", sa.String(), nullable=False),
        sa.Column("state_vector", sa.JSON(), nullable=False),
        sa.Column("reward_value", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"]),
        sa.ForeignKeyConstraint(["roadmap_id"], ["roadmaps.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_roadmap_bandit_decisions_id"),
        "roadmap_bandit_decisions",
        ["id"],
        unique=False,
    )


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if "roadmap_bandit_decisions" not in insp.get_table_names():
        return
    op.drop_index(op.f("ix_roadmap_bandit_decisions_id"), table_name="roadmap_bandit_decisions")
    op.drop_table("roadmap_bandit_decisions")
