from __future__ import annotations

import json
import re
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


class SkillNormalizer:
    def __init__(self, skills_path: Path | None = None) -> None:
        root = _repo_root()
        self.skills_path = skills_path or (root / "datasets/skills.json")
        self.lexicon: dict[str, list[str]] = json.loads(
            self.skills_path.read_text(encoding="utf-8")
        )
        self.reverse_map: dict[str, str] = {}
        for canonical, synonyms in self.lexicon.items():
            canonical_key = canonical.lower().strip()
            self.reverse_map[canonical_key] = canonical_key
            for s in synonyms:
                self.reverse_map[s.lower().strip()] = canonical_key

        self.type_keywords = {
            "tool_or_platform": {
                "jira", "trello", "bamboohr", "successfactors", "sap", "autocad",
                "revit", "primavera", "ms project", "beeline", "fieldglass",
                "excel", "tableau", "power bi", "greenhouse", "hris", "ats",
                "vms", "oracle", "quickbooks", "erp", "crm",
            },
            "leadership_or_stakeholder": {
                "stakeholder management", "cross-functional leadership",
                "team leadership", "people management", "communication",
                "negotiation", "mentoring", "vendor management",
            },
            "compliance_or_standard": {
                "compliance", "audit compliance", "regulatory", "iso", "osha",
                "data privacy", "background screening", "sla management",
                "risk mitigation", "quality assurance",
            },
            "certification_or_qualification": {
                "mba", "pmp", "six sigma", "chartered", "certified",
                "bachelor", "master", "degree", "license", "licensure",
            },
            "workflow_or_process": {
                "staff augmentation", "workforce planning", "talent deployment",
                "onboarding", "offboarding", "procurement planning",
                "inventory control", "project estimation", "boq preparation",
                "site supervision", "budget forecasting", "resource allocation",
                "process optimization", "operations management",
            },
            "domain_knowledge": {
                "civil engineering", "structural analysis", "finance", "accounting",
                "supply chain", "procurement", "logistics", "healthcare",
                "construction", "hr operations", "it consulting",
            },
        }

    def normalize(self, skill: str) -> str:
        key = " ".join(str(skill).lower().strip().split())
        return self.reverse_map.get(key, key)

    def normalize_many(self, skills: list[str]) -> list[str]:
        return sorted({self.normalize(s) for s in skills if str(s).strip()})

    def classify_competency_type(self, competency: str) -> str:
        c = self.normalize(competency)
        if not c or len(c) < 2:
            return "discard"

        if re.search(r"\b(c\+\+|c#|python|java|sql|api|docker|kubernetes|tensorflow|pytorch)\b", c):
            return "technical_skill"

        for t, words in self.type_keywords.items():
            if c in words or any(w in c for w in words):
                return t

        if re.search(r"\b(analysis|modeling|engineering|architecture|development|programming)\b", c):
            return "technical_skill"
        if re.search(r"\b(management|planning|execution|operations|deployment|supervision|screening|compliance)\b", c):
            return "workflow_or_process"
        if re.search(r"\b(stakeholder|leadership|communication|coordination|collaboration)\b", c):
            return "leadership_or_stakeholder"
        if re.search(r"\b(tool|platform|software|system|portal)\b", c):
            return "tool_or_platform"

        # Generic one-word fillers are discarded.
        if len(c.split()) == 1 and c in {
            "team", "work", "support", "business", "company", "role", "client", "project"
        }:
            return "discard"
        return "domain_knowledge"


skill_normalizer = SkillNormalizer()
competency_normalizer = skill_normalizer


if __name__ == "__main__":
    print(skill_normalizer.normalize_many(["SQL", "postgres", "Py", "python"]))

