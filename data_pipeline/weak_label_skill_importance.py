"""
Weak-label Model-1 dataset into core/important/supporting/optional.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd


def assign_label(row: pd.Series) -> str:
    # Interpretable aggregate over engineered features.
    weighted = (
        0.30 * row["context_score"]
        + 0.25 * row["section_score"]
        + 0.20 * row["title_similarity"]
        + 0.15 * row["semantic_similarity"]
        + 0.10 * row["frequency_score"]
    )
    # Optional deterministic type-aware calibration.
    ctype = str(row.get("competency_type", ""))
    if ctype == "compliance_or_standard":
        weighted += 0.03
    elif ctype == "certification_or_qualification":
        weighted -= 0.02

    # Strong mandatory signals -> core.
    if row["context_score"] >= 0.9 and row["section_score"] >= 0.75 and row["title_similarity"] >= 0.2:
        return "core"
    if weighted >= 0.62:
        return "core"

    # Medium-high importance with decent context/section.
    if row["context_score"] >= 0.6 and row["section_score"] >= 0.5:
        return "important"
    if weighted >= 0.45:
        return "important"

    # Preferred/familiarity style usually lower context but semantically relevant.
    if row["context_score"] <= 0.3 and row["section_score"] <= 0.35 and row["semantic_similarity"] >= 0.08:
        return "optional"
    if weighted < 0.22:
        return "optional"

    return "supporting"


def main() -> None:
    in_path = Path("datasets/skill_importance_dataset.csv")
    out_path = Path("datasets/skill_importance_labeled.csv")

    df = pd.read_csv(in_path)
    df["importance_label"] = df.apply(assign_label, axis=1)
    df.to_csv(out_path, index=False)

    print(f"Saved {out_path}")
    print("Class distribution:")
    print(df["importance_label"].value_counts())

    print("\n10 sample rows from each label:")
    for label in ["core", "important", "supporting", "optional"]:
        sample = df[df["importance_label"] == label].head(10)
        print(f"\n[{label}]")
        if sample.empty:
            print("No rows")
        else:
            name_col = "competency" if "competency" in sample.columns else "skill"
            cols = [
                "job_id",
                "role",
                name_col,
            ]
            if "competency_type" in sample.columns:
                cols.append("competency_type")
            cols.extend(
                [
                    "context_score",
                    "section_score",
                    "title_similarity",
                    "semantic_similarity",
                    "frequency_score",
                    "importance_label",
                ]
            )
            print(
                sample[cols].to_string(index=False)
            )


if __name__ == "__main__":
    main()
