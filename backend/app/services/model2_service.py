"""
Model 2: weighted skill-match ranking (no high/medium/low classifier).

Uses persisted Model 1 skill-importance rows when provided.
Returns similarity_score (0–100), matched/missing skill lists, and experience alignment.
"""
from __future__ import annotations

import math
import re
from typing import Any, Optional

from app.services.model1_service import model1_service

IMPORTANCE_WEIGHT = {"core": 3.0, "important": 2.0, "supporting": 1.0, "optional": 0.5}

# Blend: weighted skill overlap vs experience vs light profile–JD lexical similarity
SKILL_BLEND = 0.72
EXPERIENCE_BLEND = 0.20
LEXICAL_BLEND = 0.08
CORE_MISS_PENALTY = 0.08  # per missing core skill (capped below)


def _token_set(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9\+\#\.]+", (text or "").lower()))


def _lexical_similarity(a: str, b: str) -> float:
    ta, tb = _token_set(a), _token_set(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / math.sqrt(len(ta) * len(tb))


def _normalize_user_skills(skills: list) -> set[str]:
    out = {str(s).lower().strip() for s in (skills or []) if str(s).strip()}
    if "spring boot" in out:
        out.add("spring")
    return out


class Model2Service:
    def score_user_job(
        self,
        user_profile: dict[str, Any],
        job_description: dict[str, Any],
        analyzed_skills: Optional[list[dict[str, Any]]] = None,
    ) -> dict[str, Any]:
        title = job_description.get("title", "")
        jd_text = job_description.get("jd_text", "")
        required_exp = float(job_description.get("required_experience", 0) or 0)

        if analyzed_skills is None:
            analyzed_skills = model1_service.analyze_jd(title, jd_text)

        user_skills = _normalize_user_skills(user_profile.get("skills") or [])

        matched_skills: list[str] = []
        missing_skills: list[str] = []
        critical_missing_skills: list[str] = []
        matched = {"core": 0, "important": 0, "supporting": 0, "optional": 0}
        missing = {"core": 0, "important": 0, "supporting": 0, "optional": 0}
        weighted_match = 0.0
        weighted_missing = 0.0

        for row in analyzed_skills:
            skill = str(row.get("skill") or row.get("competency") or "").strip()
            if not skill:
                continue
            skill_key = skill.lower()
            importance = str(row.get("importance_label") or "supporting")
            weight = IMPORTANCE_WEIGHT.get(importance, 1.0)

            if skill_key in user_skills:
                matched_skills.append(skill)
                if importance in matched:
                    matched[importance] += 1
                weighted_match += weight
            else:
                missing_skills.append(skill)
                if importance in missing:
                    missing[importance] += 1
                weighted_missing += weight
                if importance in {"core", "important"}:
                    critical_missing_skills.append(skill)

        total_weight = weighted_match + weighted_missing
        skill_ratio = (weighted_match / total_weight) if total_weight > 0 else 0.0
        count_total = sum(matched.values()) + sum(missing.values())
        skill_count_ratio = (sum(matched.values()) / count_total) if count_total else 0.0

        user_exp = float(user_profile.get("experience", 0) or 0)
        experience_gap = max(0.0, required_exp - user_exp)
        experience_score = max(0.0, 1.0 - (experience_gap / 6.0))

        profile_text = " ".join(
            [
                " ".join(str(x) for x in (user_profile.get("skills") or [])),
                str(user_profile.get("projects", "")),
                str(user_profile.get("certifications", "")),
                str(user_profile.get("education", "")),
            ]
        )
        profile_job_similarity = _lexical_similarity(profile_text, f"{title} {jd_text[:2000]}")

        core_penalty = min(0.35, missing["core"] * CORE_MISS_PENALTY)
        raw = (
            SKILL_BLEND * skill_ratio
            + EXPERIENCE_BLEND * experience_score
            + LEXICAL_BLEND * profile_job_similarity
            - core_penalty
        )
        raw = max(0.0, min(1.0, raw))
        similarity_score = round(raw * 100, 2)

        explanation_text = (
            f"Similarity {similarity_score}% — "
            f"matched {len(set(matched_skills))} skills "
            f"(core {matched['core']}, important {matched['important']}, supporting {matched['supporting']}); "
            f"missing {len(set(missing_skills))} "
            f"(core {missing['core']}, important {missing['important']}); "
            f"experience score {round(experience_score * 100)}% "
            f"(required {required_exp}y, you have {user_exp}y)."
        )

        return {
            "similarity_score": similarity_score,
            "match_score": similarity_score,
            "matched_skills": sorted(set(matched_skills)),
            "missing_skills": sorted(set(missing_skills)),
            "critical_missing_skills": sorted(set(critical_missing_skills)),
            "matched_counts": matched,
            "missing_counts": missing,
            "weighted_match_total": round(weighted_match, 4),
            "weighted_missing_total": round(weighted_missing, 4),
            "skill_match_percentage": round(skill_ratio * 100, 2),
            "skill_count_percentage": round(skill_count_ratio * 100, 2),
            "experience_score": round(experience_score, 4),
            "experience_gap": round(experience_gap, 4),
            "profile_job_similarity": round(profile_job_similarity, 4),
            "explanation_features": {
                "weighted_match_total": round(weighted_match, 4),
                "weighted_missing_total": round(weighted_missing, 4),
                "skill_match_percentage": round(skill_ratio * 100, 2),
                "experience_score": round(experience_score, 4),
                "experience_gap": round(experience_gap, 4),
                "profile_job_similarity": round(profile_job_similarity, 4),
                "matched_core": matched["core"],
                "matched_important": matched["important"],
                "missing_core": missing["core"],
                "missing_important": missing["important"],
            },
            "explanation_text": explanation_text,
            "top_roadmap_skills": sorted(set(critical_missing_skills))[:10],
        }

    def match_user_job(
        self,
        user_profile: dict[str, Any],
        job_description: dict[str, Any],
        analyzed_skills: Optional[list[dict[str, Any]]] = None,
    ) -> dict[str, Any]:
        return self.score_user_job(user_profile, job_description, analyzed_skills)


model2_service = Model2Service()
