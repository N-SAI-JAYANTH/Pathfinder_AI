"""Add feedback_type to roadmap_bandit_decisions

Revision ID: g8h9i0j1
Revises: f7a8b9c0
Create Date: 2026-05-14

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "g8h9i0j1"
down_revision: Union[str, Sequence[str], None] = "f7a8b9c0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if "roadmap_bandit_decisions" not in insp.get_table_names():
        return
    cols = {c["name"] for c in insp.get_columns("roadmap_bandit_decisions")}
    if "feedback_type" not in cols:
        op.add_column(
            "roadmap_bandit_decisions",
            sa.Column("feedback_type", sa.String(), nullable=True),
        )


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if "roadmap_bandit_decisions" not in insp.get_table_names():
        return
    cols = {c["name"] for c in insp.get_columns("roadmap_bandit_decisions")}
    if "feedback_type" in cols:
        op.drop_column("roadmap_bandit_decisions", "feedback_type")
