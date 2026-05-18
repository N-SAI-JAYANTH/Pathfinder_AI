from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import schemas, models
from app.database import get_db
from app.services.job_skills_store import analyze_and_save_job_skills, get_or_analyze_job_skills
from app.services.model1_service import model1_service
from app.services.model2_service import model2_service


router = APIRouter(tags=["ml-matching"])


def _rows_to_predictions(rows: list) -> list[schemas.SkillImportancePrediction]:
    return [
        schemas.SkillImportancePrediction(
            skill=r.get("skill", ""),
            importance_label=r.get("importance_label", "supporting"),
            importance_score=r.get("importance_score"),
        )
        for r in rows
    ]


@router.post("/analyze-jd", response_model=schemas.AnalyzeJDResponse)
def analyze_jd(request: schemas.AnalyzeJDRequest, db: Session = Depends(get_db)):
    """Extract JD skills with importance. Persists on job when job_id is provided."""
    try:
        if request.job_id is not None:
            job = db.query(models.Job).filter(models.Job.id == request.job_id).first()
            if not job:
                raise HTTPException(status_code=404, detail="Job not found")
            rows = analyze_and_save_job_skills(db, job, force=request.force_refresh)
            return {
                "extracted_skills": _rows_to_predictions(rows),
                "saved": True,
                "job_id": job.id,
                "analyzed_at": job.jd_skills_analyzed_at,
            }
        rows = model1_service.analyze_jd(request.title, request.jd_text)
        return {
            "extracted_skills": _rows_to_predictions(rows),
            "saved": False,
            "job_id": None,
            "analyzed_at": None,
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to analyze JD: {exc}")


@router.get("/jobs/{job_id}/analyzed-skills")
def get_job_analyzed_skills(job_id: int, db: Session = Depends(get_db)):
    """Return fixed Model 1 skills for a job (runs Model 1 once, then cached)."""
    try:
        rows = get_or_analyze_job_skills(db, job_id)
        job = db.query(models.Job).filter(models.Job.id == job_id).first()
        return {
            "job_id": job_id,
            "extracted_skills": rows,
            "analyzed_at": job.jd_skills_analyzed_at if job else None,
            "saved": True,
        }
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to load analyzed skills: {exc}")


@router.post("/match-user-job", response_model=schemas.MatchUserJobResponse)
def match_user_job(request: schemas.MatchUserJobRequest, db: Session = Depends(get_db)):
    try:
        analyzed = None
        job_id = request.job_description.job_id
        if job_id is not None:
            analyzed = get_or_analyze_job_skills(db, job_id)
        result = model2_service.match_user_job(
            user_profile=request.user_profile.model_dump(),
            job_description=request.job_description.model_dump(),
            analyzed_skills=analyzed,
        )
        return result
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to match user and job: {exc}")


@router.post("/recommend-jobs", response_model=schemas.RecommendJobsResponse)
def recommend_jobs(request: schemas.RecommendJobsRequest, db: Session = Depends(get_db)):
    """Rank jobs by weighted skill similarity + experience (no high/medium/low labels)."""
    try:
        jobs = (
            db.query(models.Job)
            .filter(models.Job.status.in_(["active", "open"]))
            .order_by(models.Job.created_at.desc())
            .limit(500)
            .all()
        )
        results = []
        user = request.user_profile.model_dump()
        for job in jobs:
            title = job.job_title or job.title or "Untitled Job"
            jd_text = job.jd_text or job.description or ""
            required_experience = job.min_experience_years or 0
            analyzed = analyze_and_save_job_skills(db, job)
            pred = model2_service.match_user_job(
                user_profile=user,
                job_description={
                    "title": title,
                    "jd_text": jd_text,
                    "required_experience": required_experience,
                    "job_id": job.id,
                },
                analyzed_skills=analyzed,
            )
            results.append(
                {
                    "job_id": int(job.id),
                    "job_title": title,
                    "company_name": job.company_name,
                    "similarity_score": pred["similarity_score"],
                    "match_score": pred["match_score"],
                    "matched_skills_count": len(pred.get("matched_skills", [])),
                    "missing_skills_count": len(pred.get("missing_skills", [])),
                    "critical_missing_skills": pred.get("critical_missing_skills", []),
                    "experience_score": pred.get("experience_score"),
                }
            )

        results.sort(key=lambda r: r["similarity_score"], reverse=True)
        top_k = request.top_k
        return {"results": results[:top_k]}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to recommend jobs: {exc}")
