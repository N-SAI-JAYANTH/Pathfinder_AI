"""
Create a balanced jobs dataset for training.

Output:
- datasets/jobs_balanced.csv

Strategy:
- Keep only rows with non-empty jd_text
- Deduplicate by (job_title, jd_text)
- Keep all minority-role rows
- Cap only overrepresented roles
- Optional light upsampling for extremely rare roles
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd


ROLE_CAPS = {
    "Full Stack Developer": 150,
    "Java Developer": 140,
    "Backend Developer": 100,
    "Frontend Developer": 100,
    # Other roles default to "keep all" unless explicitly capped.
}

# Light upsampling for extremely rare roles (set to 0 to disable).
UPSAMPLE_MIN_COUNT = 0
RARE_ROLE_THRESHOLD = 15


def sample_role(group: pd.DataFrame, cap: int | None, upsample_min: int) -> pd.DataFrame:
    n = len(group)
    if cap is not None and n > cap:
        return group.sample(n=cap, random_state=42)
    if upsample_min > 0 and n < upsample_min:
        return group.sample(n=upsample_min, replace=True, random_state=42)
    return group


def main() -> None:
    in_path = Path("datasets/jobs.csv")
    out_path = Path("datasets/jobs_balanced.csv")

    df = pd.read_csv(in_path)
    df["jd_text"] = df["jd_text"].astype(str)
    df = df[df["jd_text"].str.strip().str.len() > 0].copy()
    df = df.drop_duplicates(subset=["job_title", "jd_text"]).reset_index(drop=True)

    original_counts = df["role"].value_counts().sort_index()
    rare_roles = original_counts[original_counts < RARE_ROLE_THRESHOLD]

    parts = []
    for role, group in df.groupby("role", sort=True):
        cap = ROLE_CAPS.get(role)
        parts.append(sample_role(group, cap=cap, upsample_min=UPSAMPLE_MIN_COUNT))
    balanced = pd.concat(parts, ignore_index=True)

    # Reassign sequential job_id for training convenience
    balanced = balanced.reset_index(drop=True)
    balanced["job_id"] = range(1, len(balanced) + 1)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    balanced.to_csv(out_path, index=False)

    balanced_counts = balanced["role"].value_counts().sort_index()

    print(f"Saved {out_path}")
    print(f"Total rows before: {len(df)}")
    print(f"Total rows after:  {len(balanced)}")
    print("\nOriginal role distribution:")
    print(original_counts)
    print("\nBalanced role distribution:")
    print(balanced_counts)
    if len(rare_roles) > 0:
        print("\nRare roles detected (count below threshold):")
        print(rare_roles)
    else:
        print("\nNo rare roles below threshold were detected.")


if __name__ == "__main__":
    main()

