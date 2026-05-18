"""Persist Model 1 JD skill analysis per job (fixed until JD changes)."""
from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Any, Optional

from sqlalchemy.orm import Session

from app import models
from app.services.model1_service import model1_service


def jd_fingerprint(title: str, jd_text: str) -> str:
    payload = f"{(title or '').strip()}\n{(jd_text or '').strip()}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:32]


def job_title_and_jd(job: models.Job) -> tuple[str, str]:
    title = job.job_title or job.title or ""
    jd = job.jd_text or job.description or ""
    return title, jd


def get_stored_job_skills(job: models.Job) -> Optional[list[dict[str, Any]]]:
    stored = getattr(job, "jd_analyzed_skills", None)
    if not stored or not isinstance(stored, list):
        return None
    title, jd = job_title_and_jd(job)
    fp = jd_fingerprint(title, jd)
    if getattr(job, "jd_analysis_hash", None) != fp:
        return None
    return stored


def analyze_and_save_job_skills(
    db: Session,
    job: models.Job,
    *,
    force: bool = False,
) -> list[dict[str, Any]]:
    """Run Model 1 once per JD version; reuse stored rows until title/JD changes."""
    if not force:
        cached = get_stored_job_skills(job)
        if cached is not None:
            return cached

    title, jd = job_title_and_jd(job)
    rows = model1_service.analyze_jd(title, jd)
    try:
        job.jd_analyzed_skills = rows
        job.jd_analysis_hash = jd_fingerprint(title, jd)
        job.jd_skills_analyzed_at = datetime.utcnow()
        db.commit()
        db.refresh(job)
    except Exception as e:
        db.rollback()
        print(f"Warning: could not persist JD skills (run alembic upgrade head): {e}")
    return rows


def get_or_analyze_job_skills(
    db: Session,
    job_id: int,
    *,
    force: bool = False,
) -> list[dict[str, Any]]:
    job = db.query(models.Job).filter(models.Job.id == job_id).first()
    if not job:
        raise ValueError(f"Job {job_id} not found")
    return analyze_and_save_job_skills(db, job, force=force)
