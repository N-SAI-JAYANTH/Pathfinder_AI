"""Lexicon-based skill extraction when Gemini is unavailable (quota, offline, etc.)."""
from __future__ import annotations

import json
import re
from pathlib import Path

from app.config import BASE_DIR

_SOFT_KEYWORDS = {
    "communication",
    "leadership",
    "teamwork",
    "problem solving",
    "adaptability",
    "analytical thinking",
    "critical thinking",
    "collaboration",
    "negotiation",
    "mentoring",
    "time management",
    "presentation",
    "interpersonal",
    "emotional intelligence",
    "conflict resolution",
    "stakeholder management",
}

_TECH_HINTS = re.compile(
    r"\b(python|java|javascript|typescript|react|node|sql|aws|docker|kubernetes|"
    r"git|linux|api|html|css|ml|ai|tensorflow|pytorch|fastapi|django|flask|"
    r"mongodb|postgres|redis|azure|gcp|c\+\+|c#|angular|vue|spark|hadoop)\b",
    re.I,
)

_lexicon: dict[str, list[str]] | None = None


def _load_lexicon() -> dict[str, list[str]]:
    global _lexicon
    if _lexicon is not None:
        return _lexicon
    path = BASE_DIR.parent / "datasets" / "skills.json"
    if not path.exists():
        _lexicon = {}
        return _lexicon
    _lexicon = json.loads(path.read_text(encoding="utf-8"))
    return _lexicon


def _is_soft(canonical: str) -> bool:
    c = canonical.lower()
    if c in _SOFT_KEYWORDS:
        return True
    return any(k in c for k in _SOFT_KEYWORDS)


def extract_skills_from_text(text: str) -> dict:
    """Return {technical_skills, soft_skills} using datasets/skills.json matching."""
    if not text or len(text.strip()) < 10:
        return {"technical_skills": [], "soft_skills": []}

    lexicon = _load_lexicon()
    technical: set[str] = set()
    soft: set[str] = set()

    for canonical, synonyms in lexicon.items():
        for token in synonyms:
            t = str(token).strip()
            if len(t) < 2:
                continue
            parts = [re.escape(p) for p in t.lower().split()]
            if parts:
                parts[-1] = parts[-1] + r"s?"
            pattern = r"\b" + r"\s+".join(parts) + r"\b"
            if re.search(pattern, text, flags=re.IGNORECASE):
                label = canonical.title() if canonical.islower() else canonical
                if _is_soft(canonical):
                    soft.add(label)
                else:
                    technical.add(label)
                break

    for m in _TECH_HINTS.finditer(text):
        technical.add(m.group(0).title())

    for phrase in _SOFT_KEYWORDS:
        if re.search(r"\b" + re.escape(phrase) + r"\b", text, flags=re.IGNORECASE):
            soft.add(phrase.title())

    return {
        "technical_skills": sorted(technical),
        "soft_skills": sorted(soft),
    }
