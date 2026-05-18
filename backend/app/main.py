from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_, func, case, String
from typing import List, Optional
from datetime import datetime, timedelta, date
import uvicorn

from app import models, schemas, auth, database, ml_service, gemini_service
from app.database import engine, get_db
from app.job_routes import router as job_router
from app.phase2_routes import router as phase2_router
from app.match_routes import router as match_router
from app.job_roadmap_service import generate_job_roadmap
from app.services.job_skills_store import analyze_and_save_job_skills, get_or_analyze_job_skills
from app.services.model2_service import model2_service
from app.services.roadmap.roadmap_store import get_roadmap_for_job, upsert_job_roadmap
from app.utils.db_migrate import ensure_job_analysis_columns
from app.utils.job_serialize import job_to_response
from app.utils.user_profile_builder import build_doc2vec_profile_text, build_model2_user_profile

models.Base.metadata.create_all(bind=engine)
ensure_job_analysis_columns()

app = FastAPI(title="PathFinder AI API")

# Include enhanced job routes
app.include_router(job_router)
app.include_router(phase2_router)
app.include_router(match_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/api/auth/register-user", response_model=schemas.UserResponse)
def register_user(user: schemas.UserCreate, db: Session = Depends(get_db)):
    db_user = db.query(models.User).filter(models.User.email == user.email).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    try:
        hashed_password = auth.get_password_hash(user.password)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    db_user = models.User(
        email=user.email,
        hashed_password=hashed_password,
        full_name=user.full_name
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


@app.post("/api/auth/register-recruiter", response_model=schemas.RecruiterResponse)
def register_recruiter(recruiter: schemas.RecruiterCreate, db: Session = Depends(get_db)):
    db_recruiter = db.query(models.Recruiter).filter(models.Recruiter.email == recruiter.email).first()
    if db_recruiter:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    try:
        hashed_password = auth.get_password_hash(recruiter.password)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    db_recruiter = models.Recruiter(
        email=recruiter.email,
        hashed_password=hashed_password,
        company_name=recruiter.company_name
    )
    db.add(db_recruiter)
    db.commit()
    db.refresh(db_recruiter)
    return db_recruiter


@app.post("/api/auth/login")
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == form_data.username).first()
    if user and auth.verify_password(form_data.password, user.hashed_password):
        access_token = auth.create_access_token(data={"sub": user.email, "type": "user"})
        return {"access_token": access_token, "token_type": "bearer", "user_type": "user", "user_id": user.id}
    
    recruiter = db.query(models.Recruiter).filter(models.Recruiter.email == form_data.username).first()
    if recruiter and auth.verify_password(form_data.password, recruiter.hashed_password):
        access_token = auth.create_access_token(data={"sub": recruiter.email, "type": "recruiter"})
        return {"access_token": access_token, "token_type": "bearer", "user_type": "recruiter", "recruiter_id": recruiter.id}
    
    raise HTTPException(status_code=401, detail="Incorrect email or password")


@app.get("/api/user/profile", response_model=schemas.UserProfileResponse)
def get_user_profile(current_user: models.User = Depends(auth.get_current_user), db: Session = Depends(get_db)):
    profile = db.query(models.UserProfile).filter(models.UserProfile.user_id == current_user.id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    return profile


@app.post("/api/user/profile", response_model=schemas.UserProfileResponse)
def create_user_profile(profile: schemas.UserProfileCreate, current_user: models.User = Depends(auth.get_current_user), db: Session = Depends(get_db)):
    existing = db.query(models.UserProfile).filter(models.UserProfile.user_id == current_user.id).first()
    if existing:
        raise HTTPException(status_code=400, detail="Profile already exists. Use PUT to update.")
    
    db_profile = models.UserProfile(user_id=current_user.id, **profile.dict())
    db.add(db_profile)
    db.commit()
    db.refresh(db_profile)
    return db_profile


@app.put("/api/user/profile", response_model=schemas.UserProfileResponse)
def update_user_profile(profile: schemas.UserProfileUpdate, current_user: models.User = Depends(auth.get_current_user), db: Session = Depends(get_db)):
    db_profile = db.query(models.UserProfile).filter(models.UserProfile.user_id == current_user.id).first()
    if not db_profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    
    for key, value in profile.dict(exclude_unset=True).items():
        setattr(db_profile, key, value)
    
    db.commit()
    db.refresh(db_profile)
    return db_profile


@app.post("/api/user/upload-resume")
async def upload_resume(file: UploadFile = File(...), current_user: models.User = Depends(auth.get_current_user), db: Session = Depends(get_db)):
    if not file.filename.endswith(('.pdf', '.doc', '.docx')):
        raise HTTPException(status_code=400, detail="Only PDF and DOC files allowed")
    
    file_path = f"uploads/{current_user.id}_{file.filename}"
    with open(file_path, "wb") as f:
        content = await file.read()
        f.write(content)
    
    resume_text = gemini_service.extract_text_from_file(file_path)
    
    if not resume_text or len(resume_text.strip()) < 10:
        raise HTTPException(
            status_code=400, 
            detail="Could not extract text from resume. Please ensure the file is a valid PDF or DOC file."
        )
    
    skills_data = gemini_service.extract_skills(resume_text)
    
    profile = db.query(models.UserProfile).filter(models.UserProfile.user_id == current_user.id).first()
    if profile:
        profile.resume_path = file_path
        # Combine technical and soft skills, filter out any error messages
        all_skills = []
        if skills_data.get('technical_skills'):
            all_skills.extend(skills_data['technical_skills'])
        if skills_data.get('soft_skills'):
            all_skills.extend(skills_data['soft_skills'])
        profile.extracted_skills = all_skills
        db.commit()
    
    # Return response with error info if present
    response = {
        "message": "Resume Uploaded Successfully",
        "extracted_skills": {
            "technical_skills": skills_data.get('technical_skills', []),
            "soft_skills": skills_data.get('soft_skills', [])
        }
    }
    
    if skills_data.get("warning"):
        response["extraction_warning"] = skills_data["warning"]
        response["message"] = "Resume uploaded. Skills extracted locally (Gemini quota unavailable)."
    elif skills_data.get("error"):
        response["extraction_error"] = skills_data["error"]
        response["message"] = "Resume uploaded, but skill extraction had issues"

    return response


@app.post("/api/recruiter/jobs", response_model=schemas.JobResponse)
def create_job(job: schemas.JobCreate, current_recruiter: models.Recruiter = Depends(auth.get_current_recruiter), db: Session = Depends(get_db)):
    db_job = models.Job(recruiter_id=current_recruiter.id, **job.dict())
    db.add(db_job)
    db.commit()
    db.refresh(db_job)
    return db_job


@app.get("/api/recruiter/jobs", response_model=List[schemas.JobResponse])
def get_recruiter_jobs(current_recruiter: models.Recruiter = Depends(auth.get_current_recruiter), db: Session = Depends(get_db)):
    jobs = db.query(models.Job).filter(models.Job.recruiter_id == current_recruiter.id).all()
    return jobs


@app.put("/api/recruiter/jobs/{job_id}", response_model=schemas.JobResponseEnhanced)
def update_job(job_id: int, job: schemas.JobUpdateEnhanced, current_recruiter: models.Recruiter = Depends(auth.get_current_recruiter), db: Session = Depends(get_db)):
    db_job = db.query(models.Job).filter(models.Job.id == job_id, models.Job.recruiter_id == current_recruiter.id).first()
    if not db_job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Update fields from the enhanced schema
    update_data = job.dict(exclude_unset=True)
    
    for key, value in update_data.items():
        # Handle enum values - convert to string if needed
        if hasattr(value, 'value'):
            value = value.value
        setattr(db_job, key, value)
    
    # Update legacy fields for backward compatibility
    if 'job_title' in update_data:
        db_job.title = update_data['job_title']
    if 'jd_text' in update_data:
        db_job.description = update_data['jd_text'][:500] if len(update_data['jd_text']) > 500 else update_data['jd_text']
    if 'location_city' in update_data or 'location_country' in update_data:
        location_parts = []
        if db_job.location_city:
            location_parts.append(db_job.location_city)
        if db_job.location_country:
            location_parts.append(db_job.location_country)
        db_job.location = ', '.join(location_parts) if location_parts else None
    
    db.commit()
    db.refresh(db_job)
    if "jd_text" in update_data or "job_title" in update_data:
        try:
            analyze_and_save_job_skills(db, db_job, force=True)
        except Exception as e:
            print(f"Warning: Model 1 JD re-analysis on update failed: {e}")
    return db_job


@app.delete("/api/recruiter/jobs/{job_id}")
def close_job(job_id: int, current_recruiter: models.Recruiter = Depends(auth.get_current_recruiter), db: Session = Depends(get_db)):
    db_job = db.query(models.Job).filter(models.Job.id == job_id, models.Job.recruiter_id == current_recruiter.id).first()
    if not db_job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    db_job.status = "closed"
    db.commit()
    return {"message": "Job closed successfully"}


@app.get("/api/jobs", response_model=List[schemas.JobResponse])
def get_all_jobs(skip: int = 0, limit: int = 50, db: Session = Depends(get_db)):
    # Include both "active" and "open" status for backward compatibility
    jobs = db.query(models.Job).filter(models.Job.status.in_(["active", "open"])).offset(skip).limit(limit).all()
    return jobs


# Enhanced Job Board API Endpoints
@app.post("/api/jobs", response_model=schemas.JobResponseEnhanced)
def create_job_enhanced(
    job: schemas.JobCreateEnhanced,
    current_recruiter: models.Recruiter = Depends(auth.get_current_recruiter),
    db: Session = Depends(get_db)
):
    """Create a new job posting with enhanced fields"""
    # Use company_name from recruiter if not provided
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
        # Legacy fields for backward compatibility
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


@app.get("/api/jobs/search", response_model=dict)
def search_jobs(
    keyword: Optional[str] = Query(None),
    location_city: Optional[str] = Query(None),
    location_country: Optional[str] = Query(None),
    remote_only: Optional[bool] = Query(None),
    experience_level: Optional[str] = Query(None),  # Comma-separated
    job_type: Optional[str] = Query(None),  # Comma-separated
    work_type: Optional[str] = Query(None),  # Comma-separated
    min_salary: Optional[int] = Query(None),
    max_salary: Optional[int] = Query(None),
    industry: Optional[str] = Query(None),  # Comma-separated
    skills_required: Optional[str] = Query(None),  # Comma-separated
    posted_within: Optional[str] = Query("any"),  # "1", "7", "30", "any"
    sort_by: Optional[str] = Query("newest"),  # "newest", "salary_high", "relevance"
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """Search and filter jobs with pagination"""
    # Include both "active" and "open" status for backward compatibility
    query = db.query(models.Job).filter(models.Job.status.in_(["active", "open"]))
    
    # Keyword search
    if keyword:
        keyword_filter = or_(
            models.Job.job_title.ilike(f"%{keyword}%"),
            models.Job.company_name.ilike(f"%{keyword}%"),
            models.Job.jd_text.ilike(f"%{keyword}%"),
            models.Job.industry.ilike(f"%{keyword}%")
        )
        query = query.filter(keyword_filter)
    
    # Location filters
    if location_city:
        query = query.filter(models.Job.location_city.ilike(f"%{location_city}%"))
    if location_country:
        query = query.filter(models.Job.location_country.ilike(f"%{location_country}%"))
    if remote_only:
        query = query.filter(models.Job.is_remote == True)
    
    # Experience level filter
    if experience_level:
        levels = [l.strip() for l in experience_level.split(",")]
        query = query.filter(models.Job.experience_level.in_(levels))
    
    # Job type filter
    if job_type:
        types = [t.strip() for t in job_type.split(",")]
        query = query.filter(models.Job.job_type.in_(types))
    
    # Work type filter
    if work_type:
        types = [t.strip() for t in work_type.split(",")]
        query = query.filter(models.Job.work_type.in_(types))
    
    # Salary filters
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
    
    # Industry filter
    if industry:
        industries = [i.strip() for i in industry.split(",")]
        query = query.filter(models.Job.industry.in_(industries))
    
    # Skills filter - simplified for SQLite
    if skills_required:
        skills = [s.strip().lower() for s in skills_required.split(",")]
        # For SQLite, we'll do a simple text search in the JSON array
        # This is a simplified approach - for production, consider full-text search
        for skill in skills:
            query = query.filter(
                func.lower(func.cast(models.Job.skills_required, String)).contains(skill)
            )
    
    # Posted within filter
    if posted_within and posted_within != "any":
        days = int(posted_within)
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        query = query.filter(models.Job.created_at >= cutoff_date)
    
    # Sorting
    if sort_by == "salary_high":
        query = query.order_by(models.Job.max_salary.desc().nulls_last())
    elif sort_by == "relevance":
        query = query.order_by(models.Job.created_at.desc())
    else:  # newest (default)
        query = query.order_by(models.Job.created_at.desc())
    
    # Get total count before pagination
    total = query.count()
    
    # Pagination
    jobs = query.offset(skip).limit(limit).all()
    
    jobs_out = [job_to_response(job) for job in jobs]

    return {
        "jobs": jobs_out,
        "total": total,
        "skip": skip,
        "limit": limit,
        "has_more": (skip + limit) < total
    }


@app.get("/api/jobs/{job_id}", response_model=schemas.JobResponseEnhanced)
def get_job_by_id(job_id: int, db: Session = Depends(get_db)):
    """Get a single job by ID"""
    job = db.query(models.Job).filter(models.Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@app.post("/api/jobs/{job_id}/generate-roadmap")
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
        "target_career": job.job_title or job.title
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


@app.post("/api/ai/recommend-careers")
def recommend_careers(current_user: models.User = Depends(auth.get_current_user), db: Session = Depends(get_db)):
    profile = db.query(models.UserProfile).filter(models.UserProfile.user_id == current_user.id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    
    all_skills = (profile.skills or []) + (profile.extracted_skills or [])
    
    if not all_skills:
        raise HTTPException(status_code=400, detail="No skills found in profile. Please add skills or upload a resume first.")
    
    recommendations = ml_service.recommend_careers_knn(all_skills)
    
    if not recommendations:
        raise HTTPException(status_code=503, detail="Career recommendation service is unavailable. ML models may not be loaded properly.")
    
    return {"careers": recommendations}


def _rank_jobs_model2(db: Session, profile: models.UserProfile, jobs: list, top_k: int = 20) -> list[dict]:
    user_m2 = build_model2_user_profile(profile)
    if not user_m2.get("skills"):
        return []

    ranked: list[dict] = []
    for job in jobs:
        title = job.job_title or job.title or "Untitled Job"
        jd_text = job.jd_text or job.description or ""
        try:
            analyzed = analyze_and_save_job_skills(db, job)
        except Exception as e:
            print(f"Warning: JD analysis for job {job.id}: {e}")
            analyzed = None

        pred = model2_service.match_user_job(
            user_m2,
            {
                "title": title,
                "jd_text": jd_text,
                "required_experience": job.min_experience_years or 0,
                "job_id": job.id,
            },
            analyzed_skills=analyzed,
        )
        jd_preview = (jd_text[:200] + "...") if len(jd_text) > 200 else jd_text
        ranked.append(
            {
                "job_id": job.id,
                "job_title": title,
                "title": title,
                "company_name": job.company_name or "Company Not Specified",
                "description": jd_preview,
                "jd_text": jd_text,
                "location_city": job.location_city,
                "location_country": job.location_country,
                "location": f"{job.location_city or ''}, {job.location_country or ''}".strip(", ") or None,
                "is_remote": job.is_remote or False,
                "industry": job.industry,
                "experience_level": job.experience_level,
                "skills_required": job.skills_required if isinstance(job.skills_required, list) else [],
                "nice_to_have_skills": job.nice_to_have_skills if isinstance(job.nice_to_have_skills, list) else [],
                "match_score": pred["similarity_score"],
                "similarity_score": pred["similarity_score"] / 100.0,
                "skill_match_percentage": pred.get("skill_match_percentage", 0),
                "matching_skills": pred.get("matched_skills", []),
                "missing_skills": pred.get("missing_skills", []),
                "critical_missing_skills": pred.get("critical_missing_skills", []),
                "experience_score": pred.get("experience_score"),
            }
        )

    ranked.sort(key=lambda r: r["match_score"], reverse=True)
    return ranked[:top_k]


@app.post("/api/ai/match-jobs")
def match_jobs(current_user: models.User = Depends(auth.get_current_user), db: Session = Depends(get_db)):
    """Rank jobs by Model 2 weighted skill similarity; fallback to Doc2Vec if needed."""
    profile = db.query(models.UserProfile).filter(models.UserProfile.user_id == current_user.id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found. Please complete your profile first.")

    jobs_from_db = (
        db.query(models.Job)
        .filter(models.Job.status.in_(["active", "open"]))
        .order_by(models.Job.created_at.desc())
        .limit(100)
        .all()
    )

    if not jobs_from_db:
        return {"jobs": [], "message": "No jobs available in the database"}

    try:
        ranked = _rank_jobs_model2(db, profile, jobs_from_db, top_k=20)
        if ranked:
            return {
                "jobs": ranked,
                "total_matched": len(ranked),
                "message": f"Found {len(ranked)} matching jobs (importance-weighted similarity)",
                "matcher": "model2",
            }
    except Exception as e:
        print(f"Model 2 matching failed, trying Doc2Vec fallback: {e}")

    combined_text = build_doc2vec_profile_text(profile, gemini_service)
    if not combined_text or len(combined_text.strip()) < 10:
        raise HTTPException(
            status_code=400,
            detail="Insufficient profile information. Please add skills, upload a resume, or complete your profile.",
        )

    matched_jobs = ml_service.match_jobs_from_database(combined_text, jobs_from_db, top_k=20)
    if not matched_jobs:
        return {
            "jobs": [],
            "message": "No matching jobs found. Try updating your profile or browse all jobs.",
            "fallback_available": True,
        }

    return {
        "jobs": matched_jobs,
        "total_matched": len(matched_jobs),
        "message": f"Found {len(matched_jobs)} matching jobs (semantic similarity)",
        "matcher": "doc2vec",
    }


@app.post("/api/ai/generate-roadmap")
def generate_roadmap(request: schemas.RoadmapRequest, current_user: models.User = Depends(auth.get_current_user), db: Session = Depends(get_db)):
    """DEPRECATED: This endpoint is deprecated. Use job-based roadmap generation instead."""
    raise HTTPException(
        status_code=410, 
        detail="This endpoint is deprecated. Please generate roadmaps from job listings using /api/jobs/{job_id}/generate-roadmap-for-user"
    )


@app.post("/api/roadmaps/save", response_model=schemas.RoadmapResponse)
def save_roadmap(request: schemas.RoadmapSaveRequest, current_user: models.User = Depends(auth.get_current_user), db: Session = Depends(get_db)):
    """Save a roadmap. Job roadmaps upsert by job_id (no duplicate rows). Max 3 total roadmaps."""
    if request.job_id:
        db_roadmap = upsert_job_roadmap(
            db,
            current_user.id,
            request.job_id,
            request.roadmap_data,
            request.title,
            target_career=request.target_career,
        )
        return db_roadmap

    existing_roadmaps = db.query(models.Roadmap).filter(
        models.Roadmap.user_id == current_user.id
    ).order_by(models.Roadmap.created_at.asc()).all()

    if len(existing_roadmaps) >= 3:
        db.delete(existing_roadmaps[0])
        db.commit()

    db_roadmap = models.Roadmap(
        user_id=current_user.id,
        title=request.title,
        roadmap_data=request.roadmap_data,
        job_id=request.job_id,
        roadmap_type=request.roadmap_type,
        target_career=request.target_career,
    )
    db.add(db_roadmap)
    db.commit()
    db.refresh(db_roadmap)
    return db_roadmap


@app.get("/api/roadmaps/by-job/{job_id}", response_model=schemas.RoadmapResponse)
def get_roadmap_by_job(
    job_id: int,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    """Return the saved roadmap for this user and job, if any."""
    row = get_roadmap_for_job(db, current_user.id, job_id)
    if not row:
        raise HTTPException(status_code=404, detail="No saved roadmap for this job")
    return row


@app.get("/api/roadmaps", response_model=List[schemas.RoadmapResponse])
def get_saved_roadmaps(current_user: models.User = Depends(auth.get_current_user), db: Session = Depends(get_db)):
    """Get all saved roadmaps for the current user (max 3)."""
    roadmaps = db.query(models.Roadmap).filter(
        models.Roadmap.user_id == current_user.id
    ).order_by(models.Roadmap.created_at.desc()).limit(3).all()
    
    return roadmaps


@app.delete("/api/roadmaps/{roadmap_id}")
def delete_roadmap(roadmap_id: int, current_user: models.User = Depends(auth.get_current_user), db: Session = Depends(get_db)):
    """Delete a saved roadmap."""
    roadmap = db.query(models.Roadmap).filter(
        models.Roadmap.id == roadmap_id,
        models.Roadmap.user_id == current_user.id
    ).first()
    
    if not roadmap:
        raise HTTPException(status_code=404, detail="Roadmap not found")
    
    db.delete(roadmap)
    db.commit()
    
    return {"message": "Roadmap deleted successfully"}


@app.post("/api/ai/skill-gap-analysis")
def skill_gap_analysis(current_user: models.User = Depends(auth.get_current_user), db: Session = Depends(get_db)):
    profile = db.query(models.UserProfile).filter(models.UserProfile.user_id == current_user.id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    
    user_skills = (profile.skills or []) + (profile.extracted_skills or [])
    career_recommendations = ml_service.recommend_careers_knn(user_skills, top_k=1)
    required_skills = career_recommendations[0]['required_skills'] if career_recommendations else []
    
    gap_analysis = gemini_service.analyze_skill_gap(user_skills, required_skills)
    
    # Check for errors
    if gap_analysis.get("error"):
        raise HTTPException(status_code=503, detail=gap_analysis["error"])
    
    return gap_analysis


@app.post("/api/ai/strengths-weaknesses")
def strengths_weaknesses(current_user: models.User = Depends(auth.get_current_user), db: Session = Depends(get_db)):
    profile = db.query(models.UserProfile).filter(models.UserProfile.user_id == current_user.id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    
    analysis = gemini_service.analyze_strengths_weaknesses(profile.__dict__)
    
    # Check for errors
    if analysis.get("error"):
        raise HTTPException(status_code=503, detail=analysis["error"])
    
    return analysis


@app.post("/api/roadmaps/{roadmap_id}/tasks/{task_id}/regenerate")
def regenerate_roadmap_task(
    roadmap_id: int,
    task_id: str,
    feedback: schemas.TaskFeedback,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    """
    Regenerate a specific task in a roadmap based on user feedback (e.g., 'skip', 'too_hard').
    """
    # 1. Fetch Roadmap
    roadmap = db.query(models.Roadmap).filter(
        models.Roadmap.id == roadmap_id,
        models.Roadmap.user_id == current_user.id
    ).first()
    
    if not roadmap:
        raise HTTPException(status_code=404, detail="Roadmap not found")
        
    roadmap_data = roadmap.roadmap_data
    if not roadmap_data or "roadmap" not in roadmap_data:
        raise HTTPException(status_code=400, detail="Invalid roadmap data structure")
        
    # 2. Find the Task to Regenerate
    target_phase = None
    target_task_index = -1
    found_task = None
    
    for phase in roadmap_data["roadmap"]["phases"]:
        for idx, task in enumerate(phase["tasks"]):
            # Check by ID if available, otherwise fallback to title matching (legacy)
            if task.get("task_id") == task_id or task.get("title") == task_id:
                target_phase = phase
                target_task_index = idx
                found_task = task
                break
        if found_task:
            break
            
    if not found_task:
        raise HTTPException(status_code=404, detail="Task not found in roadmap")
        
    # 3. Call AI to Regenerate
    from app.job_roadmap_service import regenerate_task
    
    new_task = regenerate_task(found_task["title"], feedback.feedback_type)
    
    if new_task.get("error"):
        raise HTTPException(status_code=503, detail=new_task["error"])
        
    # 4. Update Roadmap Data
    # Replace the old task with the new one
    target_phase["tasks"][target_task_index] = new_task
    
    # Check if we need to update the flag to force SQLAlchemy to detect change in JSON
    from sqlalchemy.orm.attributes import flag_modified
    roadmap.roadmap_data = roadmap_data
    flag_modified(roadmap, "roadmap_data")
    
    db.commit()
    db.refresh(roadmap)
    
    return {
        "roadmap_id": roadmap_id,
        "new_task": new_task,
        "message": "Task regenerated successfully"
    }


@app.post("/api/ai/chat", response_model=schemas.ChatResponse)
def chat(
    request: schemas.ChatRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    from app.services import chat_service

    result = chat_service.process_chat(
        db=db,
        user_id=current_user.id,
        user_name=current_user.full_name,
        message=request.message,
        session_id=request.session_id,
        page_type=request.page_type,
        page_id=request.page_id,
        context=request.context,
    )
    return result


@app.get("/api/ai/chat/sessions", response_model=List[schemas.ChatSessionSummary])
def list_chat_sessions(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    from app.services import chat_service

    sessions = chat_service.list_sessions(db, current_user.id)
    return [
        schemas.ChatSessionSummary(
            id=s.id,
            page_type=s.page_type,
            page_id=s.page_id or "",
            title=s.title,
            message_count=len(s.messages or []),
            updated_at=s.updated_at,
        )
        for s in sessions
    ]


@app.get("/api/ai/chat/sessions/{session_id}", response_model=schemas.ChatSessionDetail)
def get_chat_session(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    from app.services import chat_service

    session = chat_service.get_session(db, current_user.id, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Chat session not found")
    msgs = session.messages or []
    return schemas.ChatSessionDetail(
        id=session.id,
        page_type=session.page_type,
        page_id=session.page_id or "",
        title=session.title,
        messages=[
            schemas.ChatMessage(role=m.get("role", "assistant"), content=m.get("content", ""))
            for m in msgs
            if isinstance(m, dict) and m.get("content")
        ],
        created_at=session.created_at,
        updated_at=session.updated_at,
    )


@app.get("/api/ai/chat/sessions/by-page", response_model=schemas.ChatSessionDetail)
def get_chat_session_by_page(
    page_type: str = Query("global"),
    page_id: str = Query(""),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    from app.services import chat_service

    session = chat_service.get_or_create_session(
        db, current_user.id, page_type, page_id
    )
    msgs = session.messages or []
    return schemas.ChatSessionDetail(
        id=session.id,
        page_type=session.page_type,
        page_id=session.page_id or "",
        title=session.title,
        messages=[
            schemas.ChatMessage(role=m.get("role", "assistant"), content=m.get("content", ""))
            for m in msgs
            if isinstance(m, dict) and m.get("content")
        ],
        created_at=session.created_at,
        updated_at=session.updated_at,
    )


@app.delete("/api/ai/chat/sessions/{session_id}")
def clear_chat_session(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    from app.services import chat_service

    session = chat_service.clear_session_messages(db, current_user.id, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Chat session not found")
    return {"message": "Chat cleared", "session_id": session.id}


@app.get("/")
def root():
    return {"message": "PathFinder AI API", "status": "running"}


if __name__ == "__main__":
    uvicorn.run("main:app", port=8001, reload=True)