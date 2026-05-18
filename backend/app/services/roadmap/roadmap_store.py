"""Persist and load user roadmaps per job (upsert, dedupe)."""
from typing import Optional

from sqlalchemy.orm import Session

from app import models


def get_roadmap_for_job(db: Session, user_id: int, job_id: int) -> Optional[models.Roadmap]:
    return (
        db.query(models.Roadmap)
        .filter(
            models.Roadmap.user_id == user_id,
            models.Roadmap.job_id == job_id,
        )
        .order_by(models.Roadmap.created_at.desc())
        .first()
    )


def upsert_job_roadmap(
    db: Session,
    user_id: int,
    job_id: int,
    roadmap_data: dict,
    title: str,
    target_career: Optional[str] = None,
) -> models.Roadmap:
    """Update existing job roadmap or create one; remove duplicate rows for same job."""
    duplicates = (
        db.query(models.Roadmap)
        .filter(
            models.Roadmap.user_id == user_id,
            models.Roadmap.job_id == job_id,
        )
        .order_by(models.Roadmap.created_at.desc())
        .all()
    )

    if duplicates:
        primary = duplicates[0]
        primary.roadmap_data = roadmap_data
        primary.title = title
        primary.target_career = target_career
        primary.roadmap_type = "job"
        for extra in duplicates[1:]:
            db.delete(extra)
        db.commit()
        db.refresh(primary)
        return primary

    existing_roadmaps = (
        db.query(models.Roadmap)
        .filter(models.Roadmap.user_id == user_id)
        .order_by(models.Roadmap.created_at.asc())
        .all()
    )
    if len(existing_roadmaps) >= 3:
        db.delete(existing_roadmaps[0])
        db.commit()

    row = models.Roadmap(
        user_id=user_id,
        job_id=job_id,
        title=title,
        roadmap_data=roadmap_data,
        roadmap_type="job",
        target_career=target_career,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row
