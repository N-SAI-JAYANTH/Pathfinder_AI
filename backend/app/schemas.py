from pydantic import BaseModel, EmailStr, Field
from typing import Any, List, Optional
from datetime import datetime, date


class UserCreate(BaseModel):
    email: EmailStr
    password: str
    full_name: str


class UserResponse(BaseModel):
    id: int
    email: str
    full_name: str
    created_at: datetime
    
    class Config:
        from_attributes = True


class RecruiterCreate(BaseModel):
    email: EmailStr
    password: str
    company_name: str


class RecruiterResponse(BaseModel):
    id: int
    email: str
    company_name: str
    created_at: datetime
    
    class Config:
        from_attributes = True


class UserProfileCreate(BaseModel):
    degree: Optional[str] = None
    course: Optional[str] = None
    cgpa_10th: Optional[float] = None
    cgpa_12th: Optional[float] = None
    total_cgpa: Optional[float] = None
    cgpa_sem1: Optional[float] = None
    cgpa_sem2: Optional[float] = None
    cgpa_sem3: Optional[float] = None
    cgpa_sem4: Optional[float] = None
    cgpa_sem5: Optional[float] = None
    cgpa_sem6: Optional[float] = None
    cgpa_sem7: Optional[float] = None
    cgpa_sem8: Optional[float] = None
    skills: Optional[List[str]] = []
    certifications: Optional[List[str]] = []
    achievements: Optional[List[str]] = []
    career_interests: Optional[List[str]] = []


class UserProfileUpdate(BaseModel):
    degree: Optional[str] = None
    course: Optional[str] = None
    cgpa_10th: Optional[float] = None
    cgpa_12th: Optional[float] = None
    total_cgpa: Optional[float] = None
    cgpa_sem1: Optional[float] = None
    cgpa_sem2: Optional[float] = None
    cgpa_sem3: Optional[float] = None
    cgpa_sem4: Optional[float] = None
    cgpa_sem5: Optional[float] = None
    cgpa_sem6: Optional[float] = None
    cgpa_sem7: Optional[float] = None
    cgpa_sem8: Optional[float] = None
    skills: Optional[List[str]] = None
    certifications: Optional[List[str]] = None
    achievements: Optional[List[str]] = None
    career_interests: Optional[List[str]] = None


class UserProfileResponse(BaseModel):
    id: int
    user_id: int
    degree: Optional[str]
    course: Optional[str]
    cgpa_10th: Optional[float]
    cgpa_12th: Optional[float]
    total_cgpa: Optional[float]
    cgpa_sem1: Optional[float]
    cgpa_sem2: Optional[float]
    cgpa_sem3: Optional[float]
    cgpa_sem4: Optional[float]
    cgpa_sem5: Optional[float]
    cgpa_sem6: Optional[float]
    cgpa_sem7: Optional[float]
    cgpa_sem8: Optional[float]
    skills: Optional[List[str]]
    certifications: Optional[List[str]]
    achievements: Optional[List[str]]
    career_interests: Optional[List[str]]
    resume_path: Optional[str]
    extracted_skills: Optional[List[str]]
    
    class Config:
        from_attributes = True


# Legacy Job Schemas (for backward compatibility)
class JobCreate(BaseModel):
    title: str
    description: str
    skills_required: List[str]
    location: Optional[str] = None
    salary: Optional[str] = None
    industry: Optional[str] = None


class JobUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    skills_required: Optional[List[str]] = None
    location: Optional[str] = None
    salary: Optional[str] = None
    industry: Optional[str] = None
    status: Optional[str] = None


class JobResponse(BaseModel):
    id: int
    recruiter_id: int
    title: str
    description: str
    skills_required: List[str]
    location: Optional[str]
    salary: Optional[str]
    industry: Optional[str]
    status: str
    created_at: datetime
    
    class Config:
        from_attributes = True


# Enhanced Job Schemas
class JobCreateEnhanced(BaseModel):
    job_title: str = Field(..., min_length=1, max_length=200)
    company_name: str = Field(..., min_length=1, max_length=200)
    location_city: Optional[str] = None
    location_country: Optional[str] = None
    is_remote: bool = False
    work_type: str = Field(default="onsite", pattern="^(onsite|remote|hybrid)$")
    job_type: str = Field(default="full_time", pattern="^(full_time|part_time|internship|contract|freelance)$")
    experience_level: str = Field(default="fresher", pattern="^(fresher|junior|mid|senior|lead)$")
    min_experience_years: Optional[int] = Field(None, ge=0, le=50)
    max_experience_years: Optional[int] = Field(None, ge=0, le=50)
    min_salary: Optional[int] = Field(None, ge=0)
    max_salary: Optional[int] = Field(None, ge=0)
    salary_currency: str = Field(default="INR", max_length=10)
    salary_pay_period: str = Field(default="year", pattern="^(year|month|hour|fixed)$")
    is_salary_visible: bool = True
    industry: Optional[str] = None
    jd_text: str = Field(..., min_length=10)
    skills_required: List[str] = Field(default_factory=list)
    nice_to_have_skills: List[str] = Field(default_factory=list)
    employment_level: Optional[str] = Field(None, pattern="^(entry_level|mid_level|senior_level)$")
    application_url: Optional[str] = None
    application_email: Optional[EmailStr] = None
    application_deadline: Optional[date] = None


class JobUpdateEnhanced(BaseModel):
    job_title: Optional[str] = Field(None, min_length=1, max_length=200)
    company_name: Optional[str] = Field(None, min_length=1, max_length=200)
    location_city: Optional[str] = None
    location_country: Optional[str] = None
    is_remote: Optional[bool] = None
    work_type: Optional[str] = Field(None, pattern="^(onsite|remote|hybrid)$")
    job_type: Optional[str] = Field(None, pattern="^(full_time|part_time|internship|contract|freelance)$")
    experience_level: Optional[str] = Field(None, pattern="^(fresher|junior|mid|senior|lead)$")
    min_experience_years: Optional[int] = Field(None, ge=0, le=50)
    max_experience_years: Optional[int] = Field(None, ge=0, le=50)
    min_salary: Optional[int] = Field(None, ge=0)
    max_salary: Optional[int] = Field(None, ge=0)
    salary_currency: Optional[str] = Field(None, max_length=10)
    salary_pay_period: Optional[str] = Field(None, pattern="^(year|month|hour|fixed)$")
    is_salary_visible: Optional[bool] = None
    industry: Optional[str] = None
    jd_text: Optional[str] = Field(None, min_length=10)
    skills_required: Optional[List[str]] = None
    nice_to_have_skills: Optional[List[str]] = None
    employment_level: Optional[str] = Field(None, pattern="^(entry_level|mid_level|senior_level)$")
    application_url: Optional[str] = None
    application_email: Optional[EmailStr] = None
    application_deadline: Optional[date] = None
    status: Optional[str] = Field(None, pattern="^(active|closed|draft)$")


class JobResponseEnhanced(BaseModel):
    id: int
    recruiter_id: int
    job_title: str
    company_name: str
    location_city: Optional[str]
    location_country: Optional[str]
    is_remote: bool
    work_type: str
    job_type: str
    experience_level: str
    min_experience_years: Optional[int]
    max_experience_years: Optional[int]
    min_salary: Optional[int]
    max_salary: Optional[int]
    salary_currency: str
    salary_pay_period: str
    is_salary_visible: bool
    industry: Optional[str]
    jd_text: str
    skills_required: List[str]
    nice_to_have_skills: List[str]
    employment_level: Optional[str]
    application_url: Optional[str]
    application_email: Optional[str]
    application_deadline: Optional[date]
    status: str
    roadmap_json: Optional[dict] = None
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class JobFilters(BaseModel):
    keyword: Optional[str] = None
    location_city: Optional[str] = None
    location_country: Optional[str] = None
    remote_only: Optional[bool] = None
    experience_level: Optional[List[str]] = None
    job_type: Optional[List[str]] = None
    work_type: Optional[List[str]] = None
    min_salary: Optional[int] = None
    max_salary: Optional[int] = None
    industry: Optional[List[str]] = None
    skills_required: Optional[List[str]] = None
    posted_within: Optional[str] = None  # "1", "7", "30", "any"
    sort_by: Optional[str] = "newest"  # "newest", "salary_high", "relevance"
    skip: int = 0
    limit: int = 20


class CareerPredictionRequest(BaseModel):
    cgpa_10th: float
    cgpa_12th: float
    cgpa_avg: float
    skills: List[str]


class RoadmapRequest(BaseModel):
    target_career: str
    missing_skills: Optional[List[str]] = []
    experience_level: Optional[str] = "beginner"
    time_commitment: Optional[str] = "part-time"


class ChatMessage(BaseModel):
    role: str  # user | assistant | system
    content: str


class ChatRequest(BaseModel):
    message: str
    session_id: Optional[int] = None
    page_type: Optional[str] = "global"
    page_id: Optional[str] = ""
    context: Optional[dict] = None


class ChatResponse(BaseModel):
    response: str
    session_id: int
    messages: List[ChatMessage]


class ChatSessionSummary(BaseModel):
    id: int
    page_type: str
    page_id: str
    title: Optional[str]
    message_count: int
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


class ChatSessionDetail(BaseModel):
    id: int
    page_type: str
    page_id: str
    title: Optional[str]
    messages: List[ChatMessage]
    created_at: Optional[datetime]
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


class FeedbackRequest(BaseModel):
    roadmap_variant: int
    rating: int
    user_context: dict


class RoadmapSaveRequest(BaseModel):
    roadmap_data: dict
    title: str
    job_id: Optional[int] = None
    roadmap_type: str = "job"  # "career" or "job"
    target_career: Optional[str] = None


class RoadmapResponse(BaseModel):
    id: int
    user_id: int
    title: Optional[str]
    target_career: Optional[str]
    roadmap_data: dict
    job_id: Optional[int]
    roadmap_type: str
    created_at: datetime
    
    class Config:
        from_attributes = True


class InteractionLogRequest(BaseModel):
    task_id: str
    action_type: str = Field(
        ...,
        pattern="^(start|complete|skip|skip_regenerate|too_hard|too_easy|rate_difficulty)$",
    )
    difficulty_rating: Optional[int] = Field(None, ge=1, le=5)
    job_id: Optional[int] = None
    roadmap_id: Optional[int] = None
    duration_seconds: Optional[int] = None


class TaskFeedback(BaseModel):
    feedback_type: str = Field(..., pattern="^(skip|too_hard|completed)$")
    rating: Optional[int] = None


class RecommendationResponse(BaseModel):
    """Constrained contextual bandit recommendation."""

    selected_action: str
    action: str
    explanation: str
    reason: str = ""
    state_vector: dict[str, float] = Field(default_factory=dict)
    valid_actions: list[str] = Field(default_factory=list)
    feedback_type: Optional[str] = None
    context_task_id: Optional[str] = None
    decision_id: Optional[int] = None


class RoadmapAdaptRequest(BaseModel):
    roadmap_id: int
    task_id: str
    decision_id: Optional[int] = None


class RoadmapAdaptResponse(BaseModel):
    selected_action: str
    feedback_type: Optional[str] = None
    applied: bool
    message: str
    explanation: Optional[str] = None
    updated_roadmap: dict[str, Any]
    decision_id: Optional[int] = None
    next_task_id: Optional[str] = None


class AnalyzeJDRequest(BaseModel):
    title: str
    jd_text: str
    job_id: Optional[int] = None
    force_refresh: bool = False


class SkillImportancePrediction(BaseModel):
    skill: str
    importance_label: str
    importance_score: Optional[float] = None


class AnalyzeJDResponse(BaseModel):
    extracted_skills: List[SkillImportancePrediction]
    saved: bool = False
    job_id: Optional[int] = None
    analyzed_at: Optional[datetime] = None


class MatchUserProfileInput(BaseModel):
    skills: List[str] = Field(default_factory=list)
    experience: float = 0.0
    projects: Optional[str] = ""
    certifications: Optional[str] = ""
    education: Optional[str] = ""


class MatchJobDescriptionInput(BaseModel):
    title: str
    jd_text: str
    required_experience: Optional[float] = 0.0
    job_id: Optional[int] = None


class MatchUserJobRequest(BaseModel):
    user_profile: MatchUserProfileInput
    job_description: MatchJobDescriptionInput


class MatchUserJobResponse(BaseModel):
    similarity_score: float
    match_score: float
    matched_skills: List[str]
    missing_skills: List[str]
    critical_missing_skills: List[str]
    matched_counts: dict = Field(default_factory=dict)
    missing_counts: dict = Field(default_factory=dict)
    weighted_match_total: float = 0.0
    weighted_missing_total: float = 0.0
    skill_match_percentage: float = 0.0
    experience_score: float = 0.0
    experience_gap: float = 0.0
    explanation_features: dict = Field(default_factory=dict)
    explanation_text: str
    top_roadmap_skills: List[str] = Field(default_factory=list)


class RecommendJobsRequest(BaseModel):
    user_profile: MatchUserProfileInput
    top_k: int = Field(default=10, ge=1, le=50)


class RecommendedJob(BaseModel):
    job_id: int
    job_title: str
    company_name: Optional[str] = None
    similarity_score: float
    match_score: float
    matched_skills_count: int = 0
    missing_skills_count: int = 0
    critical_missing_skills: List[str] = Field(default_factory=list)
    experience_score: Optional[float] = None


class RecommendJobsResponse(BaseModel):
    results: List[RecommendedJob]