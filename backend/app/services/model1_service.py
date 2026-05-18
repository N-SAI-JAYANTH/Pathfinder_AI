from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Any

import joblib
from services.skill_extractor import competency_extractor
from services.skill_normalizer import competency_normalizer

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


def _repo_root() -> Path:
    # backend/app/services -> repo root
    return Path(__file__).resolve().parents[3]


def _token_set(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9\+\#\.]+", (text or "").lower()))


def _lexical_similarity(a: str, b: str) -> float:
    ta, tb = _token_set(a), _token_set(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / math.sqrt(len(ta) * len(tb))


class _SimilarityEngine:
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
            ea = self._embed(a)
            eb = self._embed(b)
            return float(util.cos_sim(ea, eb).item())
        return _lexical_similarity(a, b)


class Model1Service:
    def __init__(self) -> None:
        root = _repo_root()
        self.model = joblib.load(root / "models/model1_skill_importance/model1.pkl")
        self.label_encoder = joblib.load(root / "models/model1_skill_importance/label_encoder.pkl")
        self.lexicon = json.loads((root / "datasets/skills.json").read_text(encoding="utf-8"))
        self.sim = _SimilarityEngine()
        self.type_code = {
            "technical_skill": 0,
            "tool_or_platform": 1,
            "domain_knowledge": 2,
            "workflow_or_process": 3,
            "leadership_or_stakeholder": 4,
            "compliance_or_standard": 5,
            "certification_or_qualification": 6,
            "discard": 7,
        }

    def extract_skills(self, text: str) -> list[str]:
        return competency_extractor.extract(text)

    def extract_competencies_with_types(self, text: str) -> list[dict[str, str]]:
        return competency_extractor.extract_with_types(text)

    def _context_score(self, jd_text: str, skill: str) -> float:
        text = jd_text.lower()
        score = 0.0
        for phrase, weight in CONTEXT_PATTERNS.items():
            pattern = rf"{re.escape(phrase)}[^.\n]{{0,80}}{re.escape(skill)}|{re.escape(skill)}[^.\n]{{0,80}}{re.escape(phrase)}"
            if re.search(pattern, text):
                score = max(score, weight)
        return float(score)

    def _section_score(self, jd_text: str, skill: str) -> float:
        text = jd_text.lower()
        idx = text.find(skill.lower())
        if idx == -1:
            return 0.0
        score = 0.4
        for section, weight in SECTION_PATTERNS.items():
            s_idx = text.find(section)
            if s_idx != -1 and abs(idx - s_idx) < 700:
                score = max(score, weight)
        return float(score)

    def _frequency_score(self, jd_text: str, skill: str) -> float:
        count = len(re.findall(rf"\b{re.escape(skill.lower())}\b", jd_text.lower()))
        return min(1.0, count / 4.0)

    def _build_features(
        self, title: str, jd_text: str, skill: str, competency_type: str | None = None
    ) -> list[float]:
        ctype = competency_type or competency_normalizer.classify_competency_type(skill)
        type_code = float(self.type_code.get(ctype, self.type_code["discard"]))
        return [
            self._context_score(jd_text, skill),
            self._section_score(jd_text, skill),
            self.sim.similarity(title, skill),
            self.sim.similarity(jd_text[:2500], skill),
            self._frequency_score(jd_text, skill),
            type_code,
        ]

    def analyze_jd(self, title: str, jd_text: str) -> list[dict[str, Any]]:
        typed = self.extract_competencies_with_types(jd_text)
        skills = [r["competency"] for r in typed if r.get("competency_type") != "discard"]
        competency_type_lookup = {r["competency"]: r["competency_type"] for r in typed}
        # Suppress overly-generic skills when a specific variant is present.
        suppression = {
            "spring": "spring boot",
        }
        for generic, specific in suppression.items():
            if specific in skills and generic in skills:
                skills.remove(generic)
        if not skills:
            return []

        rows = []
        for skill in skills:
            ctype = competency_type_lookup.get(skill, competency_normalizer.classify_competency_type(skill))
            feat = self._build_features(title, jd_text, skill, ctype)
            pred_idx = int(self.model.predict([feat])[0])
            pred_label = str(self.label_encoder.inverse_transform([pred_idx])[0])
            score = None
            if hasattr(self.model, "predict_proba"):
                proba = self.model.predict_proba([feat])[0]
                score = float(max(proba))
            rows.append(
                {
                    "skill": skill,
                    "competency": skill,
                    "competency_type": ctype,
                    "importance_label": pred_label,
                    "importance_score": round(score, 4) if score is not None else None,
                    "features": {
                        "context_score": round(feat[0], 4),
                        "section_score": round(feat[1], 4),
                        "title_similarity": round(feat[2], 4),
                        "semantic_similarity": round(feat[3], 4),
                        "frequency_score": round(feat[4], 4),
                        "competency_type_code": int(feat[5]),
                    },
                }
            )
        return rows


model1_service = Model1Service()
