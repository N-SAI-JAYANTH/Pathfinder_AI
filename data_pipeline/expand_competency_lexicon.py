from __future__ import annotations

import json
from pathlib import Path


EXPANSION = {
    # HR / staffing / workforce
    "workforce strategy": ["workforce strategy", "workforce planning", "talent strategy"],
    "staff augmentation": ["staff augmentation", "resource augmentation", "it staffing"],
    "talent deployment": ["talent deployment", "resource deployment", "consultant deployment"],
    "background screening": ["background screening", "bgv", "background verification"],
    "visa management": ["visa management", "immigration documentation"],
    "hr operations": ["hr operations", "human resources operations"],
    "vendor protocol compliance": ["vendor protocol compliance", "vendor compliance"],
    "contingent workforce management": ["contingent workforce management", "contract workforce management"],
    # Operations / management
    "business operations": ["business operations", "operational management"],
    "delivery operations": ["delivery operations", "service delivery operations"],
    "sla management": ["sla management", "service level agreement management"],
    "risk mitigation": ["risk mitigation", "risk control"],
    "cross-functional leadership": ["cross-functional leadership", "cross functional leadership"],
    "stakeholder alignment": ["stakeholder alignment", "stakeholder coordination"],
    "process optimization": ["process optimization", "process improvement"],
    # Civil engineering / construction
    "civil engineering": ["civil engineering", "civil works"],
    "site supervision": ["site supervision", "site management"],
    "boq preparation": ["boq preparation", "bill of quantities", "boq"],
    "project estimation": ["project estimation", "cost estimation"],
    "structural analysis": ["structural analysis", "structure analysis"],
    "quantity surveying": ["quantity surveying", "quantity survey"],
    "construction planning": ["construction planning", "construction scheduling"],
    # Finance / accounting
    "budget forecasting": ["budget forecasting", "financial forecasting"],
    "cost analysis": ["cost analysis", "cost analytics"],
    "financial reporting": ["financial reporting", "finance reporting"],
    "accounts payable": ["accounts payable", "ap"],
    "accounts receivable": ["accounts receivable", "ar"],
    "variance analysis": ["variance analysis", "budget variance analysis"],
    # Procurement / supply chain / logistics
    "procurement planning": ["procurement planning", "purchase planning"],
    "inventory control": ["inventory control", "inventory management"],
    "supply chain management": ["supply chain management", "scm"],
    "logistics coordination": ["logistics coordination", "logistics management"],
    "purchase order management": ["purchase order management", "po management"],
    "vendor evaluation": ["vendor evaluation", "supplier evaluation"],
    # Compliance / standards / regulatory
    "audit compliance": ["audit compliance", "compliance audit"],
    "regulatory compliance": ["regulatory compliance", "statutory compliance"],
    "iso 9001": ["iso 9001", "iso-9001"],
    "iso 27001": ["iso 27001", "iso-27001"],
    "osha compliance": ["osha compliance", "osha standards"],
    "safety compliance": ["safety compliance", "ehs compliance"],
    # Healthcare / non-software technical
    "patient data management": ["patient data management", "clinical data management"],
    "medical coding": ["medical coding", "icd coding"],
    "quality control": ["quality control", "qc"],
    "quality assurance": ["quality assurance", "qa"],
}


def main() -> None:
    path = Path("datasets/skills.json")
    data = json.loads(path.read_text(encoding="utf-8"))

    for canonical, synonyms in EXPANSION.items():
        key = canonical.lower().strip()
        existing = set(data.get(key, []))
        existing.add(key)
        existing.update(s.lower().strip() for s in synonyms)
        data[key] = sorted(existing)

    # normalize duplicates / key sorting
    normalized = {}
    for k, vals in data.items():
        key = k.lower().strip()
        unique_vals = sorted({str(v).lower().strip() for v in vals if str(v).strip()})
        normalized[key] = unique_vals

    path.write_text(json.dumps(dict(sorted(normalized.items())), indent=2), encoding="utf-8")
    print(f"Updated {path} with {len(normalized)} canonical competencies")


if __name__ == "__main__":
    main()

