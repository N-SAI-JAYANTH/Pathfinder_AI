"""
Build Model-2 pairwise user-job fit features.
"""
from __future__ import annotations

import argparse
import json
import math
import re
from pathlib import Path

import pandas as pd

try:
    from sentence_transformers import SentenceTransformer, util
except Exception:  # pragma: no cover
    SentenceTransformer = None
    util = None


ROLE_KEYWORDS = {
    "Data Analyst": ["analysis", "dashboard", "report", "sql", "bi"],
    "Data Scientist": ["machine learning", "model", "statistics", "python"],
    "ML Engineer": ["mlops", "deployment", "model serving", "kubernetes"],
    "Backend Developer": ["api", "microservice", "backend", "database"],
    "Frontend Developer": ["react", "frontend", "ui", "javascript"],
    "Full Stack Developer": ["frontend", "backend", "api", "web"],
    "Java Developer": ["java", "spring", "jvm", "hibernate"],
    "Python Developer": ["python", "django", "fastapi", "flask"],
    "DevOps Engineer": ["ci/cd", "docker", "kubernetes", "terraform"],
    "Cloud Engineer": ["aws", "azure", "gcp", "cloud"],
    "BI Analyst": ["power bi", "tableau", "dax", "reporting"],
    "MLOps Engineer": ["mlflow", "kubeflow", "deployment", "monitoring"],
}

IMPORTANCE_WEIGHT = {"core": 3.0, "important": 2.0, "supporting": 1.0, "optional": 0.5}


def tokenize(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9\+\#\.]+", (text or "").lower()))


class SimilarityEngine:
    def __init__(self, use_transformer: bool = False) -> None:
        self.model = None
        self._cache = {}
        if use_transformer and SentenceTransformer is not None:
            try:
                self.model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
            except Exception:
                self.model = None

    def _embed(self, text: str):
        if text in self._cache:
            return self._cache[text]
        emb = self.model.encode(text, convert_to_tensor=True)
        self._cache[text] = emb
        return emb

    def similarity(self, a: str, b: str) -> float:
        if not a or not b:
            return 0.0
        if self.model is not None:
            ea = self._embed(a)
            eb = self._embed(b)
            return float(util.cos_sim(ea, eb).item())
        ta, tb = tokenize(a), tokenize(b)
        if not ta or not tb:
            return 0.0
        return len(ta & tb) / math.sqrt(len(ta) * len(tb))


def normalize_user_skills(skills_str: str, lexicon: dict[str, list[str]]) -> set[str]:
    raw = [s.strip().lower() for s in str(skills_str).split(",") if s.strip()]
    normalized = set()
    for token in raw:
        matched = False
        for canonical, synonyms in lexicon.items():
            if token == canonical or token in synonyms:
                normalized.add(canonical)
                matched = True
                break
        if not matched:
            normalized.add(token)
    return normalized


def score_projects(role: str, projects: str) -> float:
    txt = (projects or "").lower()
    hits = sum(1 for kw in ROLE_KEYWORDS.get(role, []) if kw in txt)
    return min(1.0, hits / 3.0)


def score_certs(role: str, certs: str) -> float:
    txt = (certs or "").lower()
    if not txt.strip():
        return 0.0
    hits = sum(1 for kw in ROLE_KEYWORDS.get(role, []) if kw in txt)
    return min(1.0, 0.3 + hits / 4.0)


def score_education(role: str, education: str) -> float:
    edu = (education or "").lower()
    stem_terms = ["btech", "be", "bsc", "mca", "msc", "computer", "it", "ai", "data"]
    base = 0.2 + 0.1 * sum(1 for term in stem_terms if term in edu)
    if "analyst" in role.lower() and "mba analytics" in edu:
        base += 0.2
    return min(1.0, base)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build user-job fit dataset")
    parser.add_argument(
        "--use_transformer_similarity",
        action="store_true",
        help="Use sentence-transformers similarity (slower).",
    )
    args = parser.parse_args()

    users = pd.read_csv("datasets/users.csv")
    jobs_path = Path("datasets/jobs_balanced.csv")
    jobs = pd.read_csv(jobs_path if jobs_path.exists() else "datasets/jobs.csv")
    skill_labels = pd.read_csv("datasets/skill_importance_labeled.csv")
    lexicon = json.loads(Path("datasets/skills.json").read_text(encoding="utf-8"))
    sim = SimilarityEngine(use_transformer=args.use_transformer_similarity)

    comp_col = "competency" if "competency" in skill_labels.columns else "skill"
    grouped = {}
    for _, row in skill_labels.iterrows():
        grouped.setdefault(int(row["job_id"]), []).append(
            (row[comp_col], row["importance_label"])
        )

    rows = []
    for _, user in users.iterrows():
        user_id = int(user["user_id"])
        user_skills = normalize_user_skills(user["skills"], lexicon)
        user_exp = float(user["experience"])
        projects = str(user["projects"])
        certs = str(user["certifications"])
        education = str(user["education"])
        profile_text = f"{user['skills']} {projects} {certs} {education}"

        for _, job in jobs.iterrows():
            job_id = int(job.get("job_id", job.get("id")))
            role = str(job["role"])
            title = str(job["job_title"])
            jd_text = str(job["jd_text"])
            exp_req = job.get("required_experience")
            exp_req = float(exp_req) if pd.notna(exp_req) else 0.0

            skill_rows = grouped.get(job_id, [])
            matched = {"core": 0, "important": 0, "supporting": 0}
            missing = {"core": 0, "important": 0, "supporting": 0}
            weighted_match = 0.0
            weighted_missing = 0.0

            for skill, importance in skill_rows:
                if importance not in IMPORTANCE_WEIGHT:
                    importance = "supporting"
                if importance == "optional":
                    continue
                is_match = skill in user_skills
                if is_match:
                    matched[importance] += 1
                    weighted_match += IMPORTANCE_WEIGHT[importance]
                else:
                    missing[importance] += 1
                    weighted_missing += IMPORTANCE_WEIGHT[importance]

            total_considered = (
                matched["core"] + matched["important"] + matched["supporting"]
                + missing["core"] + missing["important"] + missing["supporting"]
            )
            match_ratio = (matched["core"] + matched["important"] + matched["supporting"]) / total_considered if total_considered else 0.0
            exp_gap = max(0.0, exp_req - user_exp)
            exp_score = max(0.0, 1.0 - (exp_gap / 6.0))
            proj_score = score_projects(role, projects)
            cert_score = score_certs(role, certs)
            edu_score = score_education(role, education)
            profile_job_sim = sim.similarity(profile_text[:1800], f"{title} {jd_text[:2000]}")

            rows.append(
                {
                    "user_id": user_id,
                    "job_id": job_id,
                    "role": role,
                    "job_title": title,
                    "matched_core_sum": matched["core"],
                    "matched_important_sum": matched["important"],
                    "matched_supporting_sum": matched["supporting"],
                    "missing_core_sum": missing["core"],
                    "missing_important_sum": missing["important"],
                    "missing_supporting_sum": missing["supporting"],
                    "weighted_match_total": round(weighted_match, 4),
                    "weighted_missing_total": round(weighted_missing, 4),
                    "match_ratio": round(match_ratio, 4),
                    "experience_gap": round(exp_gap, 4),
                    "experience_score": round(exp_score, 4),
                    "project_score": round(proj_score, 4),
                    "cert_score": round(cert_score, 4),
                    "education_score": round(edu_score, 4),
                    "profile_job_similarity": round(profile_job_sim, 4),
                }
            )

    out_df = pd.DataFrame(rows).drop_duplicates(subset=["user_id", "job_id"]).reset_index(drop=True)
    out_path = Path("datasets/user_job_fit_dataset.csv")
    out_df.to_csv(out_path, index=False)

    print(f"Saved {out_path}")
    print(f"Total rows: {len(out_df)}")
    print("\nFeature preview:")
    print(out_df.head(10).to_string(index=False))
    print("\nPer-role distribution:")
    print(out_df["role"].value_counts())


if __name__ == "__main__":
    main()
