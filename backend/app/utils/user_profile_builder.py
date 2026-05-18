"""Build Model 2 / matching payloads from UserProfile."""
from __future__ import annotations

from app import models


def build_model2_user_profile(profile: models.UserProfile) -> dict:
    skills: list[str] = []
    if profile.skills:
        skills.extend(profile.skills if isinstance(profile.skills, list) else [profile.skills])
    if profile.extracted_skills:
        skills.extend(
            profile.extracted_skills
            if isinstance(profile.extracted_skills, list)
            else [profile.extracted_skills]
        )
    certs = profile.certifications or []
    if not isinstance(certs, list):
        certs = [certs]
    achievements = profile.achievements or []
    if not isinstance(achievements, list):
        achievements = [achievements]
    education_parts = [profile.degree, profile.course]
    education = " ".join(p for p in education_parts if p)
    projects = " ".join(str(a) for a in achievements if a)

    return {
        "skills": [str(s).strip() for s in skills if str(s).strip()],
        "experience": 0.0,
        "projects": projects,
        "certifications": ", ".join(str(c) for c in certs if c),
        "education": education,
    }


def build_doc2vec_profile_text(profile: models.UserProfile, gemini_service) -> str:
    parts = []
    if profile.degree:
        parts.append(f"Degree: {profile.degree}")
    if profile.course:
        parts.append(f"Course: {profile.course}")
    if profile.total_cgpa:
        parts.append(f"Total CGPA: {profile.total_cgpa}")
    all_skills = []
    if profile.skills:
        all_skills.extend(profile.skills if isinstance(profile.skills, list) else [profile.skills])
    if profile.extracted_skills:
        all_skills.extend(
            profile.extracted_skills
            if isinstance(profile.extracted_skills, list)
            else [profile.extracted_skills]
        )
    if all_skills:
        parts.append(f"Skills: {', '.join(all_skills)}")
    if profile.certifications:
        certs = profile.certifications if isinstance(profile.certifications, list) else [profile.certifications]
        parts.append(f"Certifications: {', '.join(certs)}")
    if profile.achievements:
        ach = profile.achievements if isinstance(profile.achievements, list) else [profile.achievements]
        parts.append(f"Achievements: {', '.join(ach)}")
    text = " ".join(parts)
    if profile.resume_path:
        try:
            resume_text = gemini_service.extract_text_from_file(profile.resume_path)
            if resume_text and len(resume_text.strip()) > 10:
                text += f" Resume: {resume_text[:2000]}"
        except Exception:
            pass
    return text
