from __future__ import annotations

import json
import re
from pathlib import Path

from services.skill_normalizer import competency_normalizer

def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


class SkillExtractor:
    def __init__(self, skills_path: Path | None = None) -> None:
        root = _repo_root()
        self.skills_path = skills_path or (root / "datasets/skills.json")
        self.lexicon = json.loads(self.skills_path.read_text(encoding="utf-8"))

    def extract(self, text: str) -> list[str]:
        txt = text or ""
        found: set[str] = set()
        synonym_lookup: dict[str, str] = competency_normalizer.reverse_map.copy()

        def add_candidate(raw: str) -> None:
            cleaned = " ".join(str(raw).strip().lower().split())
            if not cleaned:
                return
            cleaned = re.sub(r"^(and|or)\s+", "", cleaned)
            cleaned = re.sub(r"\s+(experience|skills?)$", "", cleaned)
            cleaned = cleaned.strip(" -:,.")
            if len(cleaned) < 2 or len(cleaned) > 70 or len(cleaned.split()) > 6:
                return
            stop = {
                "and", "or", "with", "without", "the", "a", "an", "to", "for",
                "of", "in", "on", "is", "are", "as", "be", "plus", "preferred",
                "required", "skills", "experience", "knowledge", "strong",
            }
            if cleaned in stop:
                return
            noisy = {"llc", "id", "job id", "pan"}
            if cleaned in noisy:
                return
            normalized = synonym_lookup.get(cleaned, cleaned)
            if competency_normalizer.classify_competency_type(normalized) != "discard":
                found.add(normalized)
        for canonical, synonyms in self.lexicon.items():
            for token in synonyms:
                t = str(token).strip()
                if not t:
                    continue
                parts = [re.escape(p) for p in t.lower().split()]
                if parts:
                    parts[-1] = parts[-1] + r"s?"
                pattern = r"\b" + r"\s+".join(parts) + r"\b"
                if re.search(pattern, txt, flags=re.IGNORECASE):
                    add_candidate(canonical)
                    break

        skills_match = re.search(r"skills\s*:\s*(.+)", txt, flags=re.IGNORECASE | re.DOTALL)
        if skills_match:
            skills_blob = skills_match.group(1)
            skills_blob = re.split(
                r"\n\s*(preferred|about|job description|responsibilities|required|qualifications)\b",
                skills_blob,
                flags=re.IGNORECASE,
            )[0]
            candidates = re.split(r"[,\n;|]+", skills_blob)
            for cand in candidates:
                add_candidate(cand)

        pattern_blocks = [
            r"(?:using|tools like|proficiency in|required|preferred|must have)\s*[:\-]\s*([^\n]+)",
            r"(?:skills include|key skills|qualifications include)\s*[:\-]\s*([^\n]+)",
            r"(?:experience in|knowledge of|expertise in)\s*[:\-]\s*([^\n]+)",
        ]
        for pat in pattern_blocks:
            for m in re.finditer(pat, txt, flags=re.IGNORECASE):
                block = m.group(1)
                block = re.sub(r"\b(required|preferred|must have|nice to have|plus)\s*[:\-]", ",", block, flags=re.IGNORECASE)
                block = block.replace(".", ",")
                for cand in re.split(r"[,;/|]+|\band\b", block):
                    add_candidate(cand)

        allowed_acronyms = {
            "AI", "IR", "ATS", "HRIS", "VMS", "SOW", "KPI", "SLA",
            "MSP", "APAC", "FAANG", "SDE", "HR", "MBA",
        }
        for token in re.findall(r"\b[A-Z]{2,8}\b", txt):
            if token.upper() not in allowed_acronyms:
                continue
            add_candidate(token)

        # Phrase-based extraction: noun-ish/process phrases with domain verbs.
        phrase_patterns = [
            r"\b([a-z]+(?:\s+[a-z]+){0,4}\s+(?:management|planning|analysis|screening|supervision|forecasting|deployment|operations|compliance|coordination|estimation|control))\b",
            r"\b(?:design|develop|implement|manage|lead|oversee|maintain)\s+([a-z]+(?:\s+[a-z]+){0,4})\b",
            r"\b(?:iso\s*\d{3,5}|oshas?|boq|sla|sow|vms|hris|ats)\b",
        ]
        low_txt = txt.lower()
        for pat in phrase_patterns:
            for m in re.finditer(pat, low_txt, flags=re.IGNORECASE):
                phrase = m.group(1) if m.groups() else m.group(0)
                add_candidate(phrase)

        # Longest-phrase priority: keep the most specific phrases.
        ordered = sorted(found, key=lambda x: (-len(x.split()), -len(x)))
        kept: list[str] = []
        for cand in ordered:
            c_tokens = set(cand.split())
            is_subsumed = False
            for k in kept:
                k_tokens = set(k.split())
                if c_tokens <= k_tokens and len(c_tokens) < len(k_tokens):
                    is_subsumed = True
                    break
            if not is_subsumed:
                kept.append(cand)

        return sorted(set(kept))

    def extract_with_types(self, text: str) -> list[dict]:
        comps = self.extract(text)
        rows = []
        for c in comps:
            ctype = competency_normalizer.classify_competency_type(c)
            if ctype == "discard":
                continue
            rows.append({"competency": c, "competency_type": ctype})
        return rows


skill_extractor = SkillExtractor()
competency_extractor = skill_extractor


if __name__ == "__main__":
    sample = "Required: Python, FastAPI, SQL. Nice to have: Docker."
    print(skill_extractor.extract(sample))

