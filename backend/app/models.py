from sqlalchemy import Column, Integer, String, Float, JSON, Text, DateTime, ForeignKey, Boolean, Date
from sqlalchemy.orm import relationship
from datetime import datetime
from app.db import Base


class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    full_name = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    profile = relationship("UserProfile", back_populates="user", uselist=False)
    roadmaps = relationship("Roadmap", back_populates="user")
    chat_sessions = relationship("ChatSession", back_populates="user")


class UserProfile(Base):
    __tablename__ = "user_profiles"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True)
    degree = Column(String)
    course = Column(String)
    cgpa_10th = Column(Float)
    cgpa_12th = Column(Float)
    total_cgpa = Column(Float)
    cgpa_sem1 = Column(Float)
    cgpa_sem2 = Column(Float)
    cgpa_sem3 = Column(Float)
    cgpa_sem4 = Column(Float)
    cgpa_sem5 = Column(Float)
    cgpa_sem6 = Column(Float)
    cgpa_sem7 = Column(Float)
    cgpa_sem8 = Column(Float)
    skills = Column(JSON)
    certifications = Column(JSON)
    achievements = Column(JSON)
    career_interests = Column(JSON)
    resume_path = Column(String)
    extracted_skills = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    user = relationship("User", back_populates="profile")


class Recruiter(Base):
    __tablename__ = "recruiters"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    company_name = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    jobs = relationship("Job", back_populates="recruiter")


class Job(Base):
    __tablename__ = "jobs"
    
    id = Column(Integer, primary_key=True, index=True)
    recruiter_id = Column(Integer, ForeignKey("recruiters.id"))
    
    # Basic Information
    job_title = Column(String, nullable=False)
    company_name = Column(String, nullable=False)
    
    # Location
    location_city = Column(String, nullable=True)
    location_country = Column(String, nullable=True)
    is_remote = Column(Boolean, default=False)
    work_type = Column(String, default="onsite")  # onsite, remote, hybrid
    
    # Job Type & Experience
    job_type = Column(String, default="full_time")  # full_time, part_time, internship, contract, freelance
    experience_level = Column(String, default="fresher")  # fresher, junior, mid, senior, lead
    min_experience_years = Column(Integer, nullable=True)
    max_experience_years = Column(Integer, nullable=True)
    employment_level = Column(String, nullable=True)  # entry_level, mid_level, senior_level
    
    # Salary
    min_salary = Column(Integer, nullable=True)
    max_salary = Column(Integer, nullable=True)
    salary_currency = Column(String, default="INR")
    salary_pay_period = Column(String, default="year")  # year, month, hour, fixed
    is_salary_visible = Column(Boolean, default=True)
    
    # Job Details
    industry = Column(String, nullable=True)
    jd_text = Column(Text, nullable=False)  # Job Description
    skills_required = Column(JSON, default=list)  # Array of strings
    nice_to_have_skills = Column(JSON, default=list)  # Array of strings
    
    # Application
    application_url = Column(String, nullable=True)
    application_email = Column(String, nullable=True)
    application_deadline = Column(Date, nullable=True)
    
    # Status & Metadata
    status = Column(String, default="active")  # active, closed, draft
    roadmap_json = Column(JSON, nullable=True)  # For AI-generated roadmap
    jd_analyzed_skills = Column(JSON, nullable=True)  # Model 1: [{skill, importance_label, ...}]
    jd_analysis_hash = Column(String, nullable=True)  # fingerprint of title+jd_text
    jd_skills_analyzed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Legacy fields for backward compatibility
    title = Column(String, nullable=True)  # Maps to job_title
    description = Column(Text, nullable=True)  # Maps to jd_text
    location = Column(String, nullable=True)  # Legacy location field
    salary = Column(String, nullable=True)  # Legacy salary field
    
    recruiter = relationship("Recruiter", back_populates="jobs")


class Roadmap(Base):
    __tablename__ = "roadmaps"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    target_career = Column(String, nullable=True)  # For career-based roadmaps
    roadmap_data = Column(JSON)
    selected_variant = Column(Integer, nullable=True)
    feedback_rating = Column(Integer, nullable=True)
    # New fields for job-based roadmaps
    job_id = Column(Integer, ForeignKey("jobs.id"), nullable=True)  # For job-based roadmaps
    roadmap_type = Column(String, default="career")  # "career" or "job"
    title = Column(String, nullable=True)  # Display title for the roadmap
    created_at = Column(DateTime, default=datetime.utcnow)
    
    user = relationship("User", back_populates="roadmaps")


class ChatSession(Base):
    """One persisted conversation per user + page (e.g. roadmap/3, global chat)."""

    __tablename__ = "chat_sessions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    page_type = Column(String, nullable=False)  # global, roadmap, job, etc.
    page_id = Column(String, nullable=False, default="")
    title = Column(String, nullable=True)
    messages = Column(JSON, default=list)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="chat_sessions")


class JobInteraction(Base):
    __tablename__ = "job_interactions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    job_id = Column(Integer, ForeignKey("jobs.id"), nullable=True)
    roadmap_id = Column(Integer, ForeignKey("roadmaps.id"), nullable=True)
    task_id = Column(String)  # ID from the JSON structure
    action_type = Column(String)  # start, complete, skip, skip_regenerate, too_hard, too_easy, rate_difficulty
    difficulty_rating = Column(Integer, nullable=True)  # 1-5
    timestamp = Column(DateTime, default=datetime.utcnow)
    duration_seconds = Column(Integer, nullable=True)
    
    user = relationship("User")


class RewardLog(Base):
    __tablename__ = "reward_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    interaction_id = Column(Integer, ForeignKey("job_interactions.id"), nullable=True)
    reward_value = Column(Float)
    model_version = Column(String)
    timestamp = Column(DateTime, default=datetime.utcnow)

    user = relationship("User")


class RoadmapBanditDecision(Base):
    """
    One row per /phase2/recommend call: selected bandit action + state at decision time.
    reward_value is set when the user logs feedback (interactions/log) for the same
    user + roadmap + task (credit assignment). feedback_type mirrors the query param
    used to build the action mask when present.
    """

    __tablename__ = "roadmap_bandit_decisions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    job_id = Column(Integer, ForeignKey("jobs.id"), nullable=True)
    roadmap_id = Column(Integer, ForeignKey("roadmaps.id"), nullable=True)
    task_id = Column(String, nullable=True)
    selected_action = Column(String, nullable=False)
    feedback_type = Column(String, nullable=True)
    state_vector = Column(JSON, nullable=False)
    reward_value = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User")