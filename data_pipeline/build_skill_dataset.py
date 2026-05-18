"""
Build Model-1 dataset: one row per (job, competency) with engineered features.
"""
from __future__ import annotations

import math
import re
import sys
from pathlib import Path

import pandas as pd

try:
    from sentence_transformers import SentenceTransformer, util
except Exception:  # pragma: no cover
    SentenceTransformer = None
    util = None


CONTEXT_PATTERNS = {
    "required": 1.0,
    "must have": 1.0,
    "mandatory": 1.0,
    "essential": 0.95,
    "strong experience in": 0.9,
    "expertise in": 0.9,
    "knowledge of": 0.65,
    "familiarity with": 0.5,
    "preferred": 0.3,
    "nice to have": 0.2,
    "plus": 0.2,
}

SECTION_PATTERNS = {
    "required qualifications": 1.0,
    "requirements": 1.0,
    "responsibilities": 0.75,
    "preferred qualifications": 0.35,
    "bonus": 0.2,
    "optional": 0.2,
}

TYPE_CODE = {
    "technical_skill": 0,
    "tool_or_platform": 1,
    "domain_knowledge": 2,
    "workflow_or_process": 3,
    "leadership_or_stakeholder": 4,
    "compliance_or_standard": 5,
    "certification_or_qualification": 6,
    "discard": 7,
}


def load_jobs() -> pd.DataFrame:
    balanced = Path("datasets/jobs_balanced.csv")
    fallback = Path("datasets/jobs.csv")
    if balanced.exists():
        return pd.read_csv(balanced)
    return pd.read_csv(fallback)


def _get_competency_tools():
    repo_root = Path(__file__).resolve().parents[1]
    backend_dir = repo_root / "backend"
    if str(backend_dir) not in sys.path:
        sys.path.insert(0, str(backend_dir))
    from services.skill_extractor import competency_extractor
    from services.skill_normalizer import competency_normalizer

    return competency_extractor, competency_normalizer


def context_score(jd_text: str, competency: str) -> float:
    text = jd_text.lower()
    score = 0.0
    for phrase, weight in CONTEXT_PATTERNS.items():
        pattern = rf"{re.escape(phrase)}[^.\n]{{0,80}}{re.escape(competency)}|{re.escape(competency)}[^.\n]{{0,80}}{re.escape(phrase)}"
        if re.search(pattern, text):
            score = max(score, weight)
    return float(score)


def section_score(jd_text: str, competency: str) -> float:
    text = jd_text.lower()
    idx = text.find(competency.lower())
    if idx == -1:
        return 0.0
    score = 0.4
    for section, weight in SECTION_PATTERNS.items():
        section_idx = text.find(section)
        if section_idx != -1 and abs(idx - section_idx) < 700:
            score = max(score, weight)
    return float(score)


class SimilarityEngine:
    def __init__(self) -> None:
        self.model = None
        self._cache = {}
        if SentenceTransformer is not None:
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
            emb_a = self._embed(a)
            emb_b = self._embed(b)
            return float(util.cos_sim(emb_a, emb_b).item())
        # Deterministic lexical fallback.
        a_set = set(re.findall(r"[a-z0-9]+", a.lower()))
        b_set = set(re.findall(r"[a-z0-9]+", b.lower()))
        if not a_set or not b_set:
            return 0.0
        return len(a_set & b_set) / math.sqrt(len(a_set) * len(b_set))

    def similarity_with_left_embedding(self, left_emb, text_right: str) -> float:
        """Cosine similarity when left side was pre-embedded (faster per-job loops)."""
        if not text_right:
            return 0.0
        emb_r = self._embed(text_right)
        return float(util.cos_sim(left_emb, emb_r).item())


def frequency_score(jd_text: str, competency: str) -> float:
    count = len(re.findall(rf"\b{re.escape(competency.lower())}\b", jd_text.lower()))
    return min(1.0, count / 4.0)


def main() -> None:
    jobs = load_jobs()
    competency_extractor, _ = _get_competency_tools()
    sim = SimilarityEngine()

    rows = []
    for _, job in jobs.iterrows():
        job_id = int(job.get("job_id", job.get("id", 0)))
        role = str(job.get("role", "Unknown"))
        title = str(job.get("job_title", "")).strip()
        jd_text = str(job.get("jd_text", "")).strip()
        if not jd_text:
            continue
        competencies = competency_extractor.extract_with_types(jd_text)
        jd_prefix = jd_text[:2500]
        if sim.model is not None:
            title_emb = sim._embed(title)
            jd_emb = sim._embed(jd_prefix)
        else:
            title_emb = jd_emb = None
        for row in competencies:
            competency = row["competency"]
            ctype = row["competency_type"]
            if ctype == "discard":
                continue
            if title_emb is not None:
                t_sim = sim.similarity_with_left_embedding(title_emb, competency)
                s_sim = sim.similarity_with_left_embedding(jd_emb, competency)
            else:
                t_sim = sim.similarity(title, competency)
                s_sim = sim.similarity(jd_prefix, competency)
            rows.append(
                {
                    "job_id": job_id,
                    "role": role,
                    "job_title": title,
                    "jd_text": jd_text,
                    # New preferred naming
                    "competency": competency,
                    "competency_type": ctype,
                    "competency_type_code": TYPE_CODE.get(ctype, TYPE_CODE["discard"]),
                    # Backward compatibility columns
                    "skill": competency,
                    "context_score": round(context_score(jd_text, competency), 4),
                    "section_score": round(section_score(jd_text, competency), 4),
                    "title_similarity": round(t_sim, 4),
                    "semantic_similarity": round(s_sim, 4),
                    "frequency_score": round(frequency_score(jd_text, competency), 4),
                }
            )

    out_df = pd.DataFrame(rows).drop_duplicates(subset=["job_id", "competency"]).reset_index(drop=True)
    out_path = Path("datasets/skill_importance_dataset.csv")
    out_df.to_csv(out_path, index=False)

    print(f"Saved {out_path}")
    print(f"Total rows: {len(out_df)}")
    print("Per-role row counts:")
    print(out_df["role"].value_counts())
    print("\nFirst 10 rows:")
    print(out_df.head(10).to_string(index=False))


if __name__ == "__main__":
    main()
