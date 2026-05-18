"""Add persisted Model 1 JD skill analysis columns to jobs."""
from alembic import op
import sqlalchemy as sa


revision = "i0j1k2l3"
down_revision = "h9i0j1k2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("jobs", sa.Column("jd_analyzed_skills", sa.JSON(), nullable=True))
    op.add_column("jobs", sa.Column("jd_analysis_hash", sa.String(), nullable=True))
    op.add_column("jobs", sa.Column("jd_skills_analyzed_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("jobs", "jd_skills_analyzed_at")
    op.drop_column("jobs", "jd_analysis_hash")
    op.drop_column("jobs", "jd_analyzed_skills")
