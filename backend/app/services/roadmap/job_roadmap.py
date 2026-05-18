"""
Job roadmap: generate personalized learning roadmap (Gemini), regenerate single task.
"""
import json
import re

from app.config import GEMINI_API_KEY
from app.services.llm.gemini_client import generate_with_fallback


def generate_job_roadmap(job: dict, user_profile: dict) -> dict:
    if not GEMINI_API_KEY:
        return {"roadmap": None, "error": "Gemini API not configured. Set GEMINI_API_KEY in backend/.env"}
    target_career = user_profile.get("target_career") or job.get("job_title") or "AI-Integrated Full Stack Engineer"
    job_title = job.get("job_title", "")
    company_name = job.get("company_name", "")
    jd_text = job.get("jd_text", "")
    skills_required = job.get("skills_required", []) or []
    nice_to_have = job.get("nice_to_have_skills", []) or []
    user_tech = user_profile.get("technical_skills", []) or []
    user_soft = user_profile.get("soft_skills", []) or []
    user_certs = user_profile.get("certifications", []) or []
    user_achievements = user_profile.get("achievements", []) or []
    academic_info = f"Degree: {user_profile.get('degree','N/A')}, Course: {user_profile.get('course','')}"
    for k in ["cgpa_10th", "cgpa_12th", "total_cgpa"]:
        if user_profile.get(k):
            academic_info += f", {k}: {user_profile[k]}"
    academic_info += ", " + ", ".join(user_profile.get("semester_cgpas", []))

    prompt = f"""
You are an expert AI career coach. Design an adaptive learning roadmap for this user to match this job.

JOB: Title={job_title}, Company={company_name}, Location={job.get('location_city')}, {job.get('location_country')}, Work={job.get('work_type')}, Type={job.get('job_type')}, Level={job.get('experience_level')}, Industry={job.get('industry')}
REQUIRED SKILLS: {', '.join(skills_required) if skills_required else 'Not listed'}
NICE TO HAVE: {', '.join(nice_to_have) if nice_to_have else 'None'}

JOB DESCRIPTION:
{jd_text[:4000]}

USER: Name={user_profile.get('name','Student')}, Academic={academic_info}, Experience={user_profile.get('experience_years',0)}y, Technical skills={', '.join(user_tech)}, Soft={', '.join(user_soft)}, Certs={', '.join(user_certs)}, Achievements={', '.join(user_achievements)}

Return a SINGLE JSON object with this structure:
{{
  "role_summary": {{ "title": "{target_career}", "what_you_do": [], "required_stack": {{ "frontend": [], "backend": [], "ai_ml": [], "cloud_devops": [], "data": [], "nice_to_have": [] }} }},
  "gap_analysis": {{ "current_skills": [], "transferable_skills": [], "missing_skills": [{{ "skill": "...", "priority": "high/medium/low", "reason": "..." }}], "summary": "..." }},
  "roadmap": {{
    "phases": [
      {{ "phase_id": 1, "phase_name": "...", "goal": "...", "estimated_duration_weeks": 6, "tasks": [
        {{ "task_id": "task_1", "title": "...", "jd_alignment": [], "description": "Detailed 50-100 word paragraph.", "status_options": ["start","already_know","need_easier","skip","finished"], "subtasks": [], "recommended_courses": [], "recommended_projects": [], "skills_gained": [] }}
      ] }}
    ]
  }}
}}

Important: description for every task must be a rich paragraph (min 50 words). 4-6 phases, 2-4 tasks each. Return ONLY the JSON.
"""
    try:
        response = generate_with_fallback(prompt, temperature=0.4)
        if not response or not response.text:
            return {"roadmap": None, "error": "Empty response from AI."}
        text = response.text.strip().replace("```json", "").replace("```", "").strip()
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if m:
            text = m.group(0)
        roadmap = json.loads(text)
        return {"roadmap": roadmap, "error": None}
    except json.JSONDecodeError as e:
        return {"roadmap": None, "error": f"Failed to parse AI response: {str(e)}"}
    except Exception as e:
        err = str(e)
        if "API key" in err or "403" in err or "401" in err:
            return {"roadmap": None, "error": "Gemini API key is invalid or expired. Check backend/.env"}
        return {"roadmap": None, "error": f"AI roadmap generation failed: {err}"}


def regenerate_task(current_task_title: str, feedback_type: str = "skip") -> dict:
    if not GEMINI_API_KEY:
        return {"error": "Gemini API not configured"}
    action = "Provide an alternative task." if feedback_type == "skip" else "User found too hard; provide a simpler task."
    prompt = f'''Original Task: "{current_task_title}". User Feedback: {feedback_type}. Context: {action}
Generate a NEW task as JSON: {{ "task_id": "new_task_...", "title": "...", "jd_alignment": [], "description": "50-100 word paragraph.", "status_options": ["start","already_know","need_easier","skip","finished"], "subtasks": [], "recommended_courses": [], "recommended_projects": [], "skills_gained": [] }}
Return ONLY the JSON.'''
    try:
        response = generate_with_fallback(prompt, temperature=0.7)
        if not response or not response.text:
            return {"error": "Empty response"}
        text = response.text.replace("```json", "").replace("```", "").strip()
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if m:
            text = m.group(0)
        return json.loads(text)
    except Exception as e:
        return {"error": str(e)}
