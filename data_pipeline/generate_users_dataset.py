"""
Generate synthetic users dataset aligned with skills lexicon.
"""
from __future__ import annotations

import json
import random
from pathlib import Path

import pandas as pd


TARGET_ROLES = [
    "Data Analyst",
    "Data Scientist",
    "ML Engineer",
    "Backend Developer",
    "Frontend Developer",
    "Full Stack Developer",
    "Java Developer",
    "Python Developer",
    "DevOps Engineer",
    "Cloud Engineer",
    "BI Analyst",
    "MLOps Engineer",
]

FIRST_NAMES = [
    "Aarav", "Ishita", "Rohan", "Meera", "Aditya", "Priya", "Rahul", "Sneha",
    "Kiran", "Neha", "Varun", "Ananya", "Arjun", "Pooja", "Vikram", "Nisha",
    "Ritika", "Dev", "Naveen", "Asha", "Tarun", "Simran", "Aman", "Kavya",
]
LAST_NAMES = [
    "Sharma", "Patel", "Reddy", "Nair", "Gupta", "Singh", "Kumar", "Joshi",
    "Iyer", "Jain", "Agarwal", "Kapoor", "Das", "Verma", "Mishra", "Mehta",
]
EDUCATION_POOL = [
    "BTech CSE", "BE IT", "BSc Data Science", "MSc AI", "MCA",
    "BTech ECE", "BE CSE", "MTech CSE", "BSc Computer Science", "MBA Analytics",
]

ROLE_SKILL_SEEDS = {
    "Data Analyst": ["sql", "excel", "power bi", "tableau", "statistics", "data visualization"],
    "Data Scientist": ["python", "machine learning", "pandas", "numpy", "scikit-learn", "sql"],
    "ML Engineer": ["python", "mlops", "docker", "kubernetes", "model deployment", "mlflow"],
    "Backend Developer": ["java", "spring boot", "rest api", "postgresql", "redis", "microservices"],
    "Frontend Developer": ["javascript", "typescript", "react", "html", "css", "redux"],
    "Full Stack Developer": ["javascript", "react", "node.js", "sql", "docker", "rest api"],
    "Java Developer": ["java", "spring", "hibernate", "junit", "maven", "sql"],
    "Python Developer": ["python", "fastapi", "django", "flask", "sqlalchemy", "pytest"],
    "DevOps Engineer": ["docker", "kubernetes", "terraform", "jenkins", "aws", "monitoring"],
    "Cloud Engineer": ["aws", "azure", "gcp", "iam", "kubernetes", "cloud security"],
    "BI Analyst": ["sql", "power bi", "tableau", "dax", "data warehousing", "excel"],
    "MLOps Engineer": ["mlops", "mlflow", "kubeflow", "docker", "kubernetes", "airflow"],
}


def make_name(rng: random.Random) -> str:
    return f"{rng.choice(FIRST_NAMES)} {rng.choice(LAST_NAMES)}"


def build_users(num_users: int = 480, seed: int = 42) -> pd.DataFrame:
    rng = random.Random(seed)
    skills_path = Path("datasets/skills.json")
    lexicon = json.loads(skills_path.read_text(encoding="utf-8"))
    canonical_skills = sorted(lexicon.keys())

    rows = []
    for user_id in range(1, num_users + 1):
        role = TARGET_ROLES[(user_id - 1) % len(TARGET_ROLES)]
        strength_bucket = user_id % 3  # 0 weak, 1 medium, 2 strong
        exp_max = 2 if strength_bucket == 0 else (5 if strength_bucket == 1 else 8)
        experience = round(rng.uniform(0, exp_max), 1)

        role_seed_skills = ROLE_SKILL_SEEDS[role]
        extra_pool = [s for s in canonical_skills if s not in role_seed_skills]
        base_count = 4 if strength_bucket == 0 else (7 if strength_bucket == 1 else 10)
        chosen = set(rng.sample(role_seed_skills, k=min(len(role_seed_skills), base_count)))
        extra_n = 2 if strength_bucket == 0 else (3 if strength_bucket == 1 else 4)
        chosen.update(rng.sample(extra_pool, k=extra_n))
        skills = ", ".join(sorted(chosen))

        project_templates = [
            f"Built {role.lower()} capstone with production-like workflow",
            f"Developed automation dashboard for {role.lower()} metrics",
            f"Implemented API/data pipeline and monitoring for internal platform",
            f"Shipped end-to-end feature with testing and deployment",
        ]
        projects = rng.choice(project_templates)

        cert_pool = [
            "AWS Certified Cloud Practitioner", "Microsoft Azure Fundamentals",
            "Google Associate Cloud Engineer", "Databricks Lakehouse Fundamentals",
            "TensorFlow Developer Certificate", "Scrum Fundamentals",
            "Tableau Desktop Specialist", "Power BI Data Analyst Associate",
            "",
        ]
        cert_count = 0 if strength_bucket == 0 else (1 if strength_bucket == 1 else 2)
        certifications = ", ".join([c for c in rng.sample(cert_pool, k=cert_count) if c])

        education = rng.choice(EDUCATION_POOL)

        rows.append(
            {
                "user_id": user_id,
                "name": make_name(rng),
                "skills": skills,
                "experience": experience,
                "projects": projects,
                "certifications": certifications,
                "education": education,
                "target_role": role,
            }
        )
    return pd.DataFrame(rows)


def main() -> None:
    out_path = Path("datasets/users.csv")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df = build_users()
    df.to_csv(out_path, index=False)

    print(f"Saved {out_path}")
    print(f"Total rows: {len(df)}")
    print("Role distribution:")
    print(df["target_role"].value_counts())
    print("\nFirst 10 rows:")
    print(df.head(10).to_string(index=False))


if __name__ == "__main__":
    main()
