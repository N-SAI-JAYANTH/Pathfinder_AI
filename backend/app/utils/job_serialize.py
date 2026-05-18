"""Normalize Job ORM rows for API responses."""
from __future__ import annotations

from app import models, schemas


def prepare_job_row(job: models.Job) -> models.Job:
    if not job.job_title and job.title:
        job.job_title = job.title
    if not job.jd_text and job.description:
        job.jd_text = job.description
    if not job.company_name:
        job.company_name = "Company Not Specified"
    if job.skills_required is None:
        job.skills_required = []
    if job.nice_to_have_skills is None:
        job.nice_to_have_skills = []
    if not job.work_type:
        job.work_type = "onsite"
    if not job.job_type:
        job.job_type = "full_time"
    if job.experience_level is None:
        job.experience_level = "fresher"
    if job.salary_currency is None:
        job.salary_currency = "INR"
    if job.salary_pay_period is None:
        job.salary_pay_period = "year"
    if job.is_salary_visible is None:
        job.is_salary_visible = True
    if job.is_remote is None:
        job.is_remote = False
    if not job.jd_text:
        job.jd_text = ""
    if job.recruiter_id is None:
        job.recruiter_id = 0
    return job


def job_to_response(job: models.Job) -> schemas.JobResponseEnhanced:
    return schemas.JobResponseEnhanced.model_validate(prepare_job_row(job))
