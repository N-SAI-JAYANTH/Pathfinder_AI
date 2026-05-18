"""
Weak-label Model-2 fit dataset.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd


ROLE_ADJUSTMENTS = {
    # These groups often need stronger breadth, so high-fit is slightly stricter.
    "Full Stack Developer": {"high_delta": 0.03, "med_delta": 0.02},
    "Backend Developer": {"high_delta": 0.02, "med_delta": 0.01},
    "Frontend Developer": {"high_delta": 0.02, "med_delta": 0.01},
    # Data roles can be skewed by sparse cert/project text; slightly relaxed.
    "Data Analyst": {"high_delta": -0.02, "med_delta": -0.02},
    "Data Scientist": {"high_delta": -0.03, "med_delta": -0.02},
    "ML Engineer": {"high_delta": -0.03, "med_delta": -0.02},
}


def compute_signals(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    # Positive fit signal.
    df["fit_signal"] = (
        0.34 * (df["weighted_match_total"] / (df["weighted_match_total"].quantile(0.95) + 1e-6)).clip(0, 1)
        + 0.20 * df["match_ratio"].clip(0, 1)
        + 0.14 * df["experience_score"].clip(0, 1)
        + 0.10 * df["project_score"].clip(0, 1)
        + 0.08 * df["cert_score"].clip(0, 1)
        + 0.07 * df["education_score"].clip(0, 1)
        + 0.07 * df["profile_job_similarity"].clip(lower=0, upper=1)
    )
    # Mismatch penalty.
    df["miss_signal"] = (
        0.45 * (df["missing_core_sum"] / 3.0).clip(0, 1)
        + 0.25 * (df["missing_important_sum"] / 4.0).clip(0, 1)
        + 0.20 * (df["weighted_missing_total"] / (df["weighted_missing_total"].quantile(0.95) + 1e-6)).clip(0, 1)
        + 0.10 * (1.0 - df["experience_score"].clip(0, 1))
    )
    return df


def assign_fit_label(row: pd.Series, high_base: float, med_base: float) -> str:
    role_adj = ROLE_ADJUSTMENTS.get(row["role"], {"high_delta": 0.0, "med_delta": 0.0})
    high_thr = high_base + role_adj["high_delta"]
    med_thr = med_base + role_adj["med_delta"]

    # Hard-fail low fit if core requirements and readiness are very poor.
    if row["missing_core_sum"] >= 4:
        return "low_fit"
    if row["missing_core_sum"] >= 2 and row["experience_score"] < 0.35:
        return "low_fit"

    # High fit: strong fit signal and controlled miss signal.
    if (
        row["fit_signal"] >= high_thr
        and row["miss_signal"] <= 0.55
        and row["missing_core_sum"] <= 1
    ):
        return "high_fit"

    # Medium fit: moderate signal, some misses acceptable.
    if row["fit_signal"] >= med_thr and row["miss_signal"] <= 0.80:
        return "medium_fit"

    return "low_fit"


def build_balanced(df: pd.DataFrame) -> pd.DataFrame:
    high = df[df["fit_label"] == "high_fit"]
    medium = df[df["fit_label"] == "medium_fit"]
    low = df[df["fit_label"] == "low_fit"]

    # Keep all high/medium; downsample low to healthier ratio.
    # Keep low-fit present but not dominant.
    target_low = min(len(low), max(int((len(high) + len(medium)) * 0.9), 30000))
    low_sampled = low.sample(n=target_low, random_state=42) if target_low < len(low) else low

    balanced = pd.concat([high, medium, low_sampled], ignore_index=True)
    return balanced.sample(frac=1.0, random_state=42).reset_index(drop=True)


def main() -> None:
    in_path = Path("datasets/user_job_fit_dataset.csv")
    out_path = Path("datasets/user_job_fit_labeled.csv")
    balanced_path = Path("datasets/user_job_fit_balanced.csv")

    df = pd.read_csv(in_path)
    df = compute_signals(df)

    # Data-driven global thresholds, then role-level adjustments apply on top.
    high_base = float(df["fit_signal"].quantile(0.78))
    med_base = float(df["fit_signal"].quantile(0.52))
    df["fit_label"] = df.apply(lambda row: assign_fit_label(row, high_base, med_base), axis=1)
    df.to_csv(out_path, index=False)
    balanced_df = build_balanced(df)
    balanced_df.to_csv(balanced_path, index=False)

    print(f"Saved {out_path}")
    class_counts = df["fit_label"].value_counts()
    class_pct = (class_counts / len(df) * 100).round(2)
    print("Class distribution:")
    print(class_counts)
    print("\nClass percentages:")
    print(class_pct.astype(str) + "%")

    print("\nPer-role class distribution:")
    print(pd.crosstab(df["role"], df["fit_label"]))

    print(f"\nSaved {balanced_path}")
    print("Balanced class distribution:")
    print(balanced_df["fit_label"].value_counts())

    if class_counts.get("high_fit", 0) < max(1000, int(0.01 * len(df))):
        print(
            "\nNOTE: high_fit is still relatively rare; apply pairwise pre-filtering before training "
            "(e.g., keep top-k jobs per user by weighted_match_total/match_ratio and drop obviously irrelevant low-fit pairs)."
        )


if __name__ == "__main__":
    main()
