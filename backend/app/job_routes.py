"""Enhanced Job Board API Routes"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_, func, String
from typing import Optional
from datetime import datetime, timedelta

from app import models, schemas, auth
from app.database import get_db
from app.job_roadmap_service import generate_job_roadmap
from app.services.job_skills_store import analyze_and_save_job_skills
from app.services.roadmap.roadmap_store import upsert_job_roadmap
from app.utils.job_serialize import job_to_response

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


@router.post("/create", response_model=schemas.JobResponseEnhanced)
def create_job_enhanced(
    job: schemas.JobCreateEnhanced,
    current_recruiter: models.Recruiter = Depends(auth.get_current_recruiter),
    db: Session = Depends(get_db)
):
    """Create a new job posting with enhanced fields"""
    company_name = job.company_name or current_recruiter.company_name
    
    db_job = models.Job(
        recruiter_id=current_recruiter.id,
        job_title=job.job_title,
        company_name=company_name,
        location_city=job.location_city,
        location_country=job.location_country,
        is_remote=job.is_remote,
        work_type=job.work_type,
        job_type=job.job_type,
        experience_level=job.experience_level,
        min_experience_years=job.min_experience_years,
        max_experience_years=job.max_experience_years,
        min_salary=job.min_salary,
        max_salary=job.max_salary,
        salary_currency=job.salary_currency,
        salary_pay_period=job.salary_pay_period,
        is_salary_visible=job.is_salary_visible,
        industry=job.industry,
        jd_text=job.jd_text,
        skills_required=job.skills_required or [],
        nice_to_have_skills=job.nice_to_have_skills or [],
        employment_level=job.employment_level,
        application_url=job.application_url,
        application_email=job.application_email,
        application_deadline=job.application_deadline,
        status="active",
        # Legacy fields
        title=job.job_title,
        description=job.jd_text[:500] if len(job.jd_text) > 500 else job.jd_text,
        location=f"{job.location_city or ''}, {job.location_country or ''}".strip(", "),
    )
    
    db.add(db_job)
    db.commit()
    db.refresh(db_job)
    try:
        analyze_and_save_job_skills(db, db_job)
    except Exception as e:
        print(f"Warning: Model 1 JD analysis on create failed: {e}")
    return db_job


@router.get("/search")
def search_jobs(
    keyword: Optional[str] = Query(None),
    location_city: Optional[str] = Query(None),
    location_country: Optional[str] = Query(None),
    remote_only: Optional[bool] = Query(None),
    experience_level: Optional[str] = Query(None),
    job_type: Optional[str] = Query(None),
    work_type: Optional[str] = Query(None),
    min_salary: Optional[int] = Query(None),
    max_salary: Optional[int] = Query(None),
    industry: Optional[str] = Query(None),
    skills_required: Optional[str] = Query(None),
    posted_within: Optional[str] = Query("any"),
    sort_by: Optional[str] = Query("newest"),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """Search and filter jobs with pagination"""
    # Include both "active" and "open" status for backward compatibility
    query = db.query(models.Job).filter(models.Job.status.in_(["active", "open"]))
    
    if keyword:
        keyword_filter = or_(
            models.Job.job_title.ilike(f"%{keyword}%"),
            models.Job.company_name.ilike(f"%{keyword}%"),
            models.Job.jd_text.ilike(f"%{keyword}%"),
            models.Job.industry.ilike(f"%{keyword}%")
        )
        query = query.filter(keyword_filter)
    
    if location_city:
        query = query.filter(models.Job.location_city.ilike(f"%{location_city}%"))
    if location_country:
        query = query.filter(models.Job.location_country.ilike(f"%{location_country}%"))
    if remote_only:
        query = query.filter(models.Job.is_remote == True)
    
    if experience_level:
        levels = [l.strip() for l in experience_level.split(",")]
        query = query.filter(models.Job.experience_level.in_(levels))
    
    if job_type:
        types = [t.strip() for t in job_type.split(",")]
        query = query.filter(models.Job.job_type.in_(types))
    
    if work_type:
        types = [t.strip() for t in work_type.split(",")]
        query = query.filter(models.Job.work_type.in_(types))
    
    if min_salary:
        query = query.filter(
            or_(
                models.Job.max_salary >= min_salary,
                models.Job.min_salary >= min_salary
            )
        )
    if max_salary:
        query = query.filter(
            or_(
                models.Job.min_salary <= max_salary,
                models.Job.max_salary <= max_salary
            )
        )
    
    if industry:
        industries = [i.strip() for i in industry.split(",")]
        query = query.filter(models.Job.industry.in_(industries))
    
    if skills_required:
        skills = [s.strip().lower() for s in skills_required.split(",")]
        for skill in skills:
            query = query.filter(
                func.lower(func.cast(models.Job.skills_required, String)).contains(skill)
            )
    
    if posted_within and posted_within != "any":
        days = int(posted_within)
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        query = query.filter(models.Job.created_at >= cutoff_date)
    
    if sort_by == "salary_high":
        query = query.order_by(models.Job.max_salary.desc().nulls_last())
    elif sort_by == "relevance":
        query = query.order_by(models.Job.created_at.desc())
    else:
        query = query.order_by(models.Job.created_at.desc())
    
    total = query.count()
    jobs = query.offset(skip).limit(limit).all()
    
    jobs_list = [job_to_response(job) for job in jobs]

    return {
        "jobs": jobs_list,
        "total": total,
        "skip": skip,
        "limit": limit,
        "has_more": (skip + limit) < total
    }


@router.get("/{job_id}", response_model=schemas.JobResponseEnhanced)
def get_job_by_id(job_id: int, db: Session = Depends(get_db)):
    """Get a single job by ID"""
    job = db.query(models.Job).filter(models.Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.post("/{job_id}/generate-roadmap")
def generate_job_roadmap_endpoint(
    job_id: int,
    current_recruiter: models.Recruiter = Depends(auth.get_current_recruiter),
    db: Session = Depends(get_db)
):
    """Generate AI roadmap for a job (recruiter can generate template roadmap)"""
    job = db.query(models.Job).filter(
        models.Job.id == job_id,
        models.Job.recruiter_id == current_recruiter.id
    ).first()
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Create a generic user profile for template roadmap
    generic_user = {
        "name": "Generic Candidate",
        "degree": "B.Tech/B.E.",
        "experience_years": job.min_experience_years or 0,
        "technical_skills": [],
        "soft_skills": [],
        "certifications": [],
        "achievements": [],
        "target_career": job.job_title
    }
    
    # Convert job to dict format
    job_dict = {
        "id": job.id,
        "job_title": job.job_title or job.title,
        "company_name": job.company_name,
        "jd_text": job.jd_text or job.description or "",
        "location_city": job.location_city,
        "location_country": job.location_country,
        "work_type": job.work_type,
        "job_type": job.job_type,
        "experience_level": job.experience_level,
        "min_experience_years": job.min_experience_years,
        "max_experience_years": job.max_experience_years,
        "skills_required": job.skills_required if isinstance(job.skills_required, list) else [],
        "nice_to_have_skills": job.nice_to_have_skills if isinstance(job.nice_to_have_skills, list) else [],
        "industry": job.industry,
    }
    
    result = generate_job_roadmap(job_dict, generic_user)
    
    if result.get("error"):
        raise HTTPException(status_code=503, detail=result["error"])
    
    # Save roadmap to job
    job.roadmap_json = result.get("roadmap")
    db.commit()
    
    return {
        "job_id": job_id,
        "roadmap": result.get("roadmap"),
        "message": "Roadmap generated successfully"
    }


@router.post("/{job_id}/generate-roadmap-for-user")
def generate_job_roadmap_for_user(
    job_id: int,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    """Generate personalized AI roadmap for a specific job and user"""
    job = db.query(models.Job).filter(models.Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Get user profile
    profile = db.query(models.UserProfile).filter(models.UserProfile.user_id == current_user.id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="User profile not found. Please complete your profile first.")
    
    # Prepare user profile data
    all_skills = (profile.skills or []) + (profile.extracted_skills or [])
    # Separate technical and soft skills (basic heuristic)
    technical_skills = [s for s in all_skills if any(tech in s.lower() for tech in ['python', 'java', 'react', 'node', 'sql', 'aws', 'docker', 'javascript', 'html', 'css', 'api', 'database', 'cloud', 'ml', 'ai'])]
    soft_skills = [s for s in all_skills if s not in technical_skills]
    
    # Collect semester CGPA values
    semester_cgpas = []
    for sem in range(1, 9):
        cgpa_value = getattr(profile, f'cgpa_sem{sem}', None)
        if cgpa_value:
            semester_cgpas.append(f"Semester {sem}: {cgpa_value}")
    
    user_profile = {
        "name": current_user.full_name,
        "degree": profile.degree or "N/A",
        "course": profile.course or "N/A",
        "cgpa_10th": profile.cgpa_10th,
        "cgpa_12th": profile.cgpa_12th,
        "total_cgpa": profile.total_cgpa,
        "semester_cgpas": semester_cgpas,
        "cgpa_sem1": profile.cgpa_sem1,
        "cgpa_sem2": profile.cgpa_sem2,
        "cgpa_sem3": profile.cgpa_sem3,
        "cgpa_sem4": profile.cgpa_sem4,
        "cgpa_sem5": profile.cgpa_sem5,
        "cgpa_sem6": profile.cgpa_sem6,
        "cgpa_sem7": profile.cgpa_sem7,
        "cgpa_sem8": profile.cgpa_sem8,
        "experience_years": 0,  # Could be calculated from profile if available
        "current_role": "Student",
        "technical_skills": technical_skills,
        "soft_skills": soft_skills,
        "certifications": profile.certifications or [],
        "achievements": profile.achievements or [],
        "target_career": job.job_title or "Software Engineer"
    }
    
    # Convert job to dict format
    job_dict = {
        "id": job.id,
        "job_title": job.job_title or job.title,
        "company_name": job.company_name,
        "jd_text": job.jd_text or job.description or "",
        "location_city": job.location_city,
        "location_country": job.location_country,
        "work_type": job.work_type,
        "job_type": job.job_type,
        "experience_level": job.experience_level,
        "min_experience_years": job.min_experience_years,
        "max_experience_years": job.max_experience_years,
        "skills_required": job.skills_required if isinstance(job.skills_required, list) else [],
        "nice_to_have_skills": job.nice_to_have_skills if isinstance(job.nice_to_have_skills, list) else [],
        "industry": job.industry,
    }
    
    # Generate roadmap
    result = generate_job_roadmap(job_dict, user_profile)
    
    if result.get("error"):
        raise HTTPException(status_code=503, detail=result["error"])

    roadmap_payload = result.get("roadmap")
    title = f"Roadmap: {job.job_title or job.title}"
    db_roadmap = upsert_job_roadmap(
        db,
        current_user.id,
        job.id,
        roadmap_payload,
        title,
        target_career=job.job_title or job.title,
    )

    return {
        "job_id": job_id,
        "job_title": job.job_title or job.title,
        "roadmap": roadmap_payload,
        "roadmap_id": db_roadmap.id,
        "saved": True,
        "message": "Personalized roadmap generated and saved successfully",
    }

