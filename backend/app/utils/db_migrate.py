"""Lightweight SQLite column checks (no Alembic required for dev)."""
from __future__ import annotations

from sqlalchemy import inspect, text

from app.db import engine


def ensure_job_analysis_columns() -> None:
    """Add Model 1 persistence columns if missing (avoids breaking all job queries)."""
    try:
        insp = inspect(engine)
        if "jobs" not in insp.get_table_names():
            return
        cols = {c["name"] for c in insp.get_columns("jobs")}
        statements = []
        if "jd_analyzed_skills" not in cols:
            statements.append("ALTER TABLE jobs ADD COLUMN jd_analyzed_skills JSON")
        if "jd_analysis_hash" not in cols:
            statements.append("ALTER TABLE jobs ADD COLUMN jd_analysis_hash VARCHAR")
        if "jd_skills_analyzed_at" not in cols:
            statements.append("ALTER TABLE jobs ADD COLUMN jd_skills_analyzed_at DATETIME")
        if not statements:
            return
        with engine.begin() as conn:
            for stmt in statements:
                conn.execute(text(stmt))
        print("Applied jobs table column patch:", statements)
    except Exception as e:
        print(f"Warning: ensure_job_analysis_columns failed: {e}")
