import argparse
import re
from pathlib import Path

import pandas as pd
from datasets import load_dataset


ROLE_PATTERNS = [
    # Specific role mappings first, broader mappings later.
    (r"\bbusiness intelligence analyst\b|\bbi analyst\b", "BI Analyst"),
    (r"\bmlops engineer\b|\bml ops engineer\b", "MLOps Engineer"),
    (r"\bdevops engineer\b", "DevOps Engineer"),
    (r"\bcloud engineer\b", "Cloud Engineer"),
    (r"\bdata analyst\b|\banalytics engineer\b", "Data Analyst"),
    (
        r"\bdata scientist\b|\bml scientist\b|\bdata science engineer\b",
        "Data Scientist",
    ),
    (
        r"\bmachine learning engineer\b|\bml engineer\b|\bai engineer\b|\bai developer\b",
        "ML Engineer",
    ),
    (
        r"\bpython backend developer\b|\bpython engineer\b|\bpython developer\b",
        "Python Developer",
    ),
    (
        r"\bjava software engineer\b|\bjava engineer\b|\bjava developer\b",
        "Java Developer",
    ),
    (
        r"\bbackend engineer\b|\bbackend developer\b",
        "Backend Developer",
    ),
    (
        r"\bfrontend engineer\b|\bfrontend developer\b|\bfront end developer\b",
        "Frontend Developer",
    ),
    (
        r"\bfull stack engineer\b|\bfull stack developer\b|\bfullstack developer\b",
        "Full Stack Developer",
    ),
    (
        r"\bweb developer\b",
        "Frontend Developer",
    ),
    (
        r"\bsoftware engineer\b|\bsoftware developer\b",
        "Full Stack Developer",
    ),
]


def normalize_text(value):
    return " ".join(str(value).split()) if value is not None else ""


def infer_role(job_title: str, jd_text: str):
    haystack = f"{job_title} {jd_text}".lower()
    for pattern, role in ROLE_PATTERNS:
        if re.search(pattern, haystack):
            return role
    return None


def is_likely_english(text: str):
    if not text:
        return False
    ascii_ratio = sum(1 for ch in text if ord(ch) < 128) / max(len(text), 1)
    has_english_tokens = bool(
        re.search(
            r"\b(the|and|with|required|experience|skills|responsibilities|development)\b",
            text.lower(),
        )
    )
    return ascii_ratio >= 0.95 and has_english_tokens


def extract_required_experience(text: str):
    match = re.search(r"(\d+)\s*\+?\s*(?:years|yrs)", text.lower())
    if match:
        return int(match.group(1))
    return None


def pick_col(df: pd.DataFrame, candidates):
    for col in candidates:
        if col in df.columns:
            return col
    return None


def build_base_df(df: pd.DataFrame, source_name: str):
    title_col = pick_col(
        df,
        ["job_title", "title", "position_title", "position", "role", "Job Title"],
    )
    desc_col = pick_col(
        df,
        ["job_description", "description", "jd_text", "text", "job_summary", "Job Description"],
    )
    exp_col = pick_col(
        df,
        ["required_experience", "required experience", "experience", "job level", "job_level"],
    )

    if not title_col or not desc_col:
        return pd.DataFrame(), 0, 0

    base = pd.DataFrame()
    base["job_title"] = df[title_col].map(normalize_text)
    base["jd_text"] = df[desc_col].map(normalize_text)
    base["required_experience_raw"] = (
        df[exp_col].map(normalize_text) if exp_col else ""
    )
    base["source"] = source_name
    return base, len(df), len(base)


def extract_experience_from_text(jd_text: str, exp_text: str):
    extracted = extract_required_experience(jd_text)
    if extracted is not None:
        return extracted
    if exp_text:
        m = re.search(r"(\d+)", exp_text.lower())
        if m:
            return int(m.group(1))
    return None


def main():
    parser = argparse.ArgumentParser(description="Prepare jobs.csv for PathFinder AI")
    parser.add_argument(
        "--source",
        default="hf",
        choices=["hf", "postings"],
        help="Input source: hf dataset or postings.csv file",
    )
    parser.add_argument(
        "--input_csv",
        default="postings.csv/postings.csv",
        help="Path to postings.csv when --source=postings",
    )
    args = parser.parse_args()

    source_frames = []
    contribution = []

    if args.source == "postings":
        input_paths = [
            "postings.csv/postings.csv",
            "postings.csv/DataAnalyst.csv",
            "postings.csv/job_postings.csv",
        ]
        for input_path in input_paths:
            current = pd.read_csv(input_path, engine="python", encoding="utf-8")
            base, raw_count, mapped_count = build_base_df(current, input_path)
            contribution.append((input_path, raw_count, mapped_count))
            if not base.empty:
                source_frames.append(base)
        if not source_frames:
            raise ValueError("No valid source files had both title and job description columns.")
        df = pd.concat(source_frames, ignore_index=True)
    else:
        ds = load_dataset("jacob-hugging-face/job-descriptions")
        split_name = "train" if "train" in ds else list(ds.keys())[0]
        base, raw_count, mapped_count = build_base_df(
            ds[split_name].to_pandas(), "jacob-hugging-face/job-descriptions"
        )
        contribution.append(("jacob-hugging-face/job-descriptions", raw_count, mapped_count))
        df = base

    out = pd.DataFrame()
    out["job_title"] = df["job_title"].map(normalize_text)
    out["jd_text"] = df["jd_text"].map(normalize_text)
    out["source"] = df["source"]
    out["required_experience_raw"] = df["required_experience_raw"]
    out = out[out["jd_text"].map(is_likely_english)].copy()
    out["role"] = [infer_role(t, d) for t, d in zip(out["job_title"], out["jd_text"])]
    out = out[out["role"].notna()].copy()

    out = out[out["jd_text"].str.len() >= 200].copy()
    out["required_experience"] = [
        extract_experience_from_text(jd, raw)
        for jd, raw in zip(out["jd_text"], out["required_experience_raw"])
    ]
    out["source"] = out["source"].fillna(
        "postings.csv/postings.csv"
        if args.source == "postings"
        else "jacob-hugging-face/job-descriptions"
    )

    out = out.drop_duplicates(subset=["job_title", "jd_text"]).reset_index(drop=True)
    out.insert(0, "job_id", range(1, len(out) + 1))
    out = out[
        ["job_id", "role", "job_title", "jd_text", "required_experience", "source"]
    ]

    out = out.groupby("role", group_keys=False).head(300).reset_index(drop=True)
    out["job_id"] = range(1, len(out) + 1)

    datasets_dir = Path("datasets")
    datasets_dir.mkdir(parents=True, exist_ok=True)

    output_path = datasets_dir / "jobs.csv"
    out.to_csv(output_path, index=False)

    print(f"Saved {output_path} with {len(out)} rows")
    print("\nRole distribution:")
    print(out["role"].value_counts())
    print(f"\nAverage jd_text length: {out['jd_text'].str.len().mean():.2f}")
    print(f"Rows with extracted required_experience: {out['required_experience'].notna().sum()}")
    print("\nSource contribution (raw_rows, mapped_rows_with_title_and_jd):")
    for src, raw_count, mapped_count in contribution:
        print(f"- {src}: ({raw_count}, {mapped_count})")


if __name__ == "__main__":
    main()
