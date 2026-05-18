import sys
import os
from pathlib import Path

# Add backend directory to path
current_dir = Path(__file__).resolve().parent
backend_dir = current_dir.parent
sys.path.append(str(backend_dir))

from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models import Job, Roadmap, User, Recruiter
# Fix import to work when running as script
try:
    from app.services.rag_service import rag_service
except ImportError:
    sys.path.append(str(backend_dir.parent))
    from backend.app.services.rag_service import rag_service

def create_dummy_data(db: Session):
    print("Creating dummy data for RAG...")
    
    # Check if we have users
    if not db.query(User).first():
        from app.auth import get_password_hash
        user = User(
            email="test@example.com", 
            hashed_password=get_password_hash("password123"), 
            full_name="Test User"
        )
        db.add(user)
        db.commit()
    
    # Check if we have recruiters
    recruiter = db.query(Recruiter).first()
    if not recruiter:
        from app.auth import get_password_hash
        recruiter = Recruiter(
            email="recruiter@example.com", 
            hashed_password=get_password_hash("password123"), 
            company_name="Tech Corp"
        )
        db.add(recruiter)
        db.commit()
        
    # Create  Jobs
    jobs_data = [
        {
            "job_title": "Senior Software Engineer",
            "company_name": "Tech Corp",
            "location_city": "San Francisco",
            "location_country": "USA",
            "work_type": "hybrid",
            "jd_text": "We are looking for a Senior Software Engineer with experience in Python, React, and AWS. You will be responsible for building scalable web applications.",
            "skills_required": ["Python", "React", "AWS", "Docker"],
            "experience_level": "senior"
        },
        {
            "job_title": "Data Scientist",
            "company_name": "Data AI Inc",
            "location_city": "New York",
            "location_country": "USA",
            "work_type": "remote",
            "jd_text": "Join our team as a Data Scientist. We need someone with strong skills in Machine Learning, PyTorch, and SQL. Experience with NLP is a plus.",
            "skills_required": ["Python", "Machine Learning", "PyTorch", "SQL"],
            "experience_level": "mid"
        }
    ]
    
    for job_data in jobs_data:
        job = Job(**job_data, recruiter_id=recruiter.id)
        db.add(job)
    
    db.commit()
    print("Dummy jobs created.")

def seed_rag_db():
    print("Starting RAG Database Seeding...")
    db = SessionLocal()
    
    try:
        # 1. Clear existing collection
        print("Clearing existing collection...")
        try:
            rag_service.clear_collection()
        except Exception as e:
            print(f"Warning clearing collection: {e}")
        
        jobs = db.query(Job).all()
        if not jobs:
            create_dummy_data(db)
            jobs = db.query(Job).all()

        print(f"Found {len(jobs)} jobs to index.")
        
        for job in jobs:
            # Create a rich text representation for RAG
            skills = job.skills_required
            if isinstance(skills, list):
                skills_str = ", ".join(skills)
            else:
                skills_str = str(skills)

            job_text = f"""
            JOB TITLE: {job.job_title}
            COMPANY: {job.company_name}
            LOCATION: {job.location_city}, {job.location_country} ({job.work_type})
            DESCRIPTION: {job.jd_text}
            SKILLS: {skills_str}
            EXPERIENCE: {job.experience_level}
            """
            
            metadata = {
                "type": "job",
                "id": str(job.id),
                "title": job.job_title or "No Title",
                "company": job.company_name or "No Company"
            }
            
            rag_service.index_content(
                doc_id=f"job_{job.id}",
                text=job_text,
                metadata=metadata
            )
            # Count chunks for this job
            chunks = rag_service.chunk_text(job_text)
            print(f"Indexed Job: {job.job_title} ({len(chunks)} chunk{'s' if len(chunks) > 1 else ''})")
            
        # 3. Index Roadmaps (if any)
        roadmaps = db.query(Roadmap).all()
        print(f"Found {len(roadmaps)} roadmaps to index.")
        
        for roadmap in roadmaps:
            if not roadmap.roadmap_data:
                continue
                
            # Convert roadmap JSON to readable text
            roadmap_json = roadmap.roadmap_data
            roadmap_phases = roadmap_json.get("roadmap", {}).get("phases", [])
            
            phase_texts = []
            for phase in roadmap_phases:
                tasks = []
                for t in phase.get("tasks", []):
                    tasks.append(t.get("title", "Task"))
                
                phase_texts.append(f"Phase {phase.get('phase_id')}: {phase.get('phase_name')} - Tasks: {', '.join(tasks)}")
            
            roadmap_text = f"""
            ROADMAP FOR: {roadmap.target_career or 'Custom Career'}
            USER ID: {roadmap.user_id}
            SUMMARY: {', '.join(phase_texts)}
            """
            
            metadata = {
                "type": "roadmap",
                "id": str(roadmap.id),
                "career": roadmap.target_career or "Unknown"
            }
            
            rag_service.index_content(
                doc_id=f"roadmap_{roadmap.id}",
                text=roadmap_text,
                metadata=metadata
            )
            # Count chunks for this roadmap
            chunks = rag_service.chunk_text(roadmap_text)
            print(f"Indexed Roadmap: {roadmap.id} ({len(chunks)} chunk{'s' if len(chunks) > 1 else ''})")
            
        print("RAG Seeding Completed Successfully!")
        
    except Exception as e:
        print(f"Error during seeding: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    seed_rag_db()
