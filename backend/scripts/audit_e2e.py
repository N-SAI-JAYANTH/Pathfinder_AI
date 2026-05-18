from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import pandas as pd

# Allow running from repo root: make `backend/` importable so `import app` works.
REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = REPO_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


def exists_report(paths: list[str]) -> list[str]:
    missing = []
    for p in paths:
        if not Path(p).exists():
            missing.append(p)
    return missing


def report_jobs(path: str) -> dict:
    df = pd.read_csv(path)
    dup = df.duplicated(subset=[c for c in ["job_title", "jd_text"] if c in df.columns]).sum()
    jd_text = df["jd_text"].astype(str) if "jd_text" in df.columns else pd.Series([], dtype=str)
    empty = int((jd_text.str.strip() == "").sum()) if "jd_text" in df.columns else 0
    short = int((jd_text.str.len() < 200).sum()) if "jd_text" in df.columns else 0
    avg_len = float(jd_text.str.len().mean()) if "jd_text" in df.columns else 0.0
    null_exp = float(df["required_experience"].isna().mean() * 100) if "required_experience" in df.columns else 100.0
    roles = df["role"].value_counts().to_dict() if "role" in df.columns else {}
    return {
        "rows": int(len(df)),
        "dup_by_title_jd": int(dup),
        "empty_jd": empty,
        "short_jd_lt_200": short,
        "avg_jd_len": round(avg_len, 2),
        "required_experience_null_pct": round(null_exp, 2),
        "role_distribution": roles,
    }


def report_users(path: str) -> dict:
    df = pd.read_csv(path)
    bad_exp = int(((df["experience"] < 0) | (df["experience"] > 50)).sum())
    empty_skills = int((df["skills"].astype(str).str.strip() == "").sum())
    roles = df["target_role"].value_counts().to_dict()
    return {
        "rows": int(len(df)),
        "bad_experience_rows": bad_exp,
        "empty_skills": empty_skills,
        "role_distribution": roles,
    }


def report_skills(path: str) -> dict:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    non_list = [k for k, v in data.items() if not isinstance(v, list)]
    dup_syn = 0
    total_syn = 0
    for _, v in data.items():
        total_syn += len(v)
        dup_syn += len(v) - len(set(v))
    return {
        "canonical_count": int(len(data)),
        "non_list_values": int(len(non_list)),
        "synonym_dup_count": int(dup_syn),
        "total_synonyms": int(total_syn),
    }


def report_skill_importance(path: str) -> dict:
    df = pd.read_csv(path)
    needed = ["context_score", "section_score", "title_similarity", "semantic_similarity", "frequency_score"]
    numeric = {}
    for c in needed:
        if c in df.columns:
            numeric[c] = {
                "nan": int(df[c].isna().sum()),
                "min": float(df[c].min()),
                "max": float(df[c].max()),
            }
    dist = df["importance_label"].value_counts().to_dict() if "importance_label" in df.columns else {}
    return {"rows": int(len(df)), "missing_cols": [c for c in needed if c not in df.columns], "numeric": numeric, "class_distribution": dist}


def report_fit(path: str) -> dict:
    df = pd.read_csv(path)
    dup = int(df.duplicated(subset=["user_id", "job_id"]).sum()) if {"user_id", "job_id"}.issubset(df.columns) else 0
    dist = df["fit_label"].value_counts().to_dict() if "fit_label" in df.columns else {}
    ranges = {}
    for c in ["match_ratio", "experience_score", "profile_job_similarity"]:
        if c in df.columns:
            ranges[c] = {"min": float(df[c].min()), "max": float(df[c].max())}
    return {"rows": int(len(df)), "dup_user_job": dup, "class_distribution": dist, "ranges": ranges}


def model1_sanity() -> dict:
    from app.services.model1_service import model1_service

    tests = [
        (
            "Backend Developer",
            "We are hiring a Backend Developer. Required skills: Java, Spring Boot, REST APIs. Strong experience in microservices is mandatory. Docker is a plus.",
        ),
        (
            "Data Analyst",
            "Required: SQL, Excel, Tableau. Strong knowledge of statistics is required. Python is preferred.",
        ),
    ]
    out = []
    for title, jd in tests:
        preds = model1_service.analyze_jd(title, jd)
        out.append({"title": title, "preds": preds})
    return {"tests": out}


def model2_sanity() -> dict:
    from app.services.model2_service import model2_service

    # Test case A
    user_a = {
        "skills": ["java", "spring boot"],
        "experience": 1.5,
        "projects": "Built REST backend for e-commerce system",
        "certifications": "",
        "education": "BTech CSE",
    }
    job_a = {
        "title": "Backend Developer",
        "jd_text": "Backend Developer role. Required: Java, Spring Boot, REST APIs. Important: microservices. Plus: Docker.",
        "required_experience": 2,
    }
    # Test case B
    user_b = {
        "skills": ["excel", "word"],
        "experience": 0,
        "projects": "",
        "certifications": "",
        "education": "BCom",
    }
    job_b = {
        "title": "ML Engineer",
        "jd_text": "Required: Python, Machine Learning, TensorFlow. Must have MLOps and Kubernetes. Experience with model deployment.",
        "required_experience": 2,
    }

    return {
        "case_a": model2_service.match_user_job(user_a, job_a),
        "case_b": model2_service.match_user_job(user_b, job_b),
    }


def main() -> None:
    required_files = [
        "datasets/jobs.csv",
        "datasets/jobs_balanced.csv",
        "datasets/users.csv",
        "datasets/skills.json",
        "datasets/skill_importance_dataset.csv",
        "datasets/skill_importance_labeled.csv",
        "datasets/user_job_fit_dataset.csv",
        "datasets/user_job_fit_labeled.csv",
        "datasets/user_job_fit_balanced.csv",
        "models/model1_skill_importance/model1.pkl",
        "models/model1_skill_importance/label_encoder.pkl",
        "models/model1_skill_importance/metrics.txt",
        "models/model1_skill_importance/confusion_matrix.csv",
        "models/model1_skill_importance/feature_importance.csv",
        "models/model2_job_fit/model2.pkl",
        "models/model2_job_fit/label_encoder.pkl",
        "models/model2_job_fit/metrics.txt",
        "models/model2_job_fit/confusion_matrix.csv",
        "models/model2_job_fit/feature_importance.csv",
        "backend/app.py",
        "backend/routes/match.py",
        "backend/services/skill_extractor.py",
        "backend/services/skill_normalizer.py",
        "backend/services/model1_service.py",
        "backend/services/model2_service.py",
    ]

    report = {
        "phase1_missing_files": exists_report(required_files),
        "phase2_data_quality": {
            "jobs_csv": report_jobs("datasets/jobs.csv"),
            "jobs_balanced_csv": report_jobs("datasets/jobs_balanced.csv"),
            "users_csv": report_users("datasets/users.csv"),
            "skills_json": report_skills("datasets/skills.json"),
            "skill_importance_dataset": report_skill_importance("datasets/skill_importance_dataset.csv"),
            "skill_importance_labeled": report_skill_importance("datasets/skill_importance_labeled.csv"),
            "user_job_fit_dataset": report_fit("datasets/user_job_fit_dataset.csv"),
            "user_job_fit_labeled": report_fit("datasets/user_job_fit_labeled.csv"),
            "user_job_fit_balanced": report_fit("datasets/user_job_fit_balanced.csv"),
        },
        "phase3_model1_sanity": model1_sanity(),
        "phase4_model2_sanity": model2_sanity(),
        "generated_at": time.time(),
    }

    out_path = Path("backend/scripts/audit_report.json")
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Saved audit report to {out_path}")
    print(json.dumps(report["phase2_data_quality"]["jobs_csv"], indent=2))
    print(json.dumps(report["phase2_data_quality"]["users_csv"], indent=2))
    print(json.dumps(report["phase4_model2_sanity"], indent=2)[:2000])


if __name__ == "__main__":
    main()

