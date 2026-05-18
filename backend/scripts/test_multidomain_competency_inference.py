from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = REPO_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.services.model1_service import model1_service


LABEL_WEIGHT = {"core": 3.0, "important": 2.0, "supporting": 1.0, "optional": 0.5}

SAMPLES = [
    {
        "name": "software_role",
        "title": "Backend Engineer",
        "jd_text": "Required: Python, FastAPI, SQL, Docker. Preferred: Redis, Kubernetes. Must have API design experience.",
    },
    {
        "name": "hr_operations_role",
        "title": "HR Operations Manager",
        "jd_text": "Lead staff augmentation, workforce strategy, stakeholder management, onboarding compliance, ATS/HRIS reporting, vendor management.",
    },
    {
        "name": "civil_role",
        "title": "Civil Site Engineer",
        "jd_text": "Responsibilities include boq preparation, project estimation, site supervision, autocad drafting, structural analysis and safety compliance.",
    },
    {
        "name": "management_program_role",
        "title": "Program Manager - Supply Chain",
        "jd_text": "Need procurement planning, inventory control, logistics coordination, risk mitigation, sla management and cross-functional leadership.",
    },
]


def main() -> None:
    all_out = {}
    for s in SAMPLES:
        rows = model1_service.analyze_jd(s["title"], s["jd_text"])
        df = pd.DataFrame(rows)
        if not df.empty:
            df["weight"] = df["importance_label"].map(LABEL_WEIGHT).fillna(0.0)
            df = df.sort_values(["weight", "importance_score"], ascending=[False, False]).reset_index(drop=True)

        print(f"\n=== {s['name']} :: {s['title']} ===")
        if df.empty:
            print("No competencies extracted.")
            all_out[s["name"]] = []
            continue
        cols = ["competency", "competency_type", "importance_label", "importance_score", "weight"]
        print(df[cols].to_string(index=False))
        critical = df[df["importance_label"].isin(["core", "important"])].head(8)
        print("Top critical competencies (core/important):")
        if critical.empty:
            print("(none)")
        else:
            print(critical[["competency", "competency_type", "importance_label", "importance_score"]].to_string(index=False))
        rec = df[cols].to_dict(orient="records")
        rec_critical = critical[["competency", "competency_type", "importance_label", "importance_score"]].to_dict(
            orient="records"
        )
        all_out[s["name"]] = {"all": rec, "critical": rec_critical}

    out_path = REPO_ROOT / "backend/scripts/multidomain_competency_results.json"
    out_path.write_text(json.dumps(all_out, indent=2), encoding="utf-8")
    print(f"\nSaved {out_path}")


if __name__ == "__main__":
    main()

