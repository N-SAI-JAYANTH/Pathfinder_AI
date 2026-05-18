from __future__ import annotations

import json
import sys
from typing import Any

import requests


def post(url: str, payload: dict[str, Any]) -> dict[str, Any]:
    r = requests.post(url, json=payload, timeout=60)
    try:
        data = r.json()
    except Exception:
        data = {"raw_text": r.text}
    if not r.ok:
        raise RuntimeError(f"HTTP {r.status_code} from {url}: {data}")
    return data


def main() -> None:
    base_url = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8001"

    analyze_url = f"{base_url}/analyze-jd"
    match_url = f"{base_url}/match-user-job"

    jd_payload = {
        "title": "Backend Developer",
        "jd_text": (
            "We are looking for a Backend Developer with strong experience in Python and FastAPI. "
            "Must have: REST API development, SQL (PostgreSQL), Docker. "
            "Preferred: Redis, Kubernetes, AWS. Responsibilities include building microservices, "
            "writing tests (pytest), and deploying services."
        ),
    }
    print(f"POST {analyze_url}")
    analyze_resp = post(analyze_url, jd_payload)
    print(json.dumps(analyze_resp, indent=2)[:2000])

    user_payload = {
        "user_profile": {
            "skills": ["python", "fastapi", "sql", "docker", "git", "pytest"],
            "experience": 2.0,
            "projects": "Built microservices with FastAPI, Postgres; added CI/CD and monitoring.",
            "certifications": "AWS Certified Cloud Practitioner",
            "education": "BTech CSE",
        },
        "job_description": {
            "title": jd_payload["title"],
            "jd_text": jd_payload["jd_text"],
            "required_experience": 1.0,
        },
    }
    print(f"\nPOST {match_url}")
    match_resp = post(match_url, user_payload)
    print(json.dumps(match_resp, indent=2)[:2000])

    recommend_url = f"{base_url}/recommend-jobs"
    recommend_payload = {"user_profile": user_payload["user_profile"], "top_k": 5}
    print(f"\nPOST {recommend_url}")
    rec_resp = post(recommend_url, recommend_payload)
    print(json.dumps(rec_resp, indent=2)[:2000])


if __name__ == "__main__":
    main()

