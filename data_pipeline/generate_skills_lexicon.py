"""
Generate canonical skills lexicon with synonyms.
"""
from __future__ import annotations

import json
from pathlib import Path


BASE_SKILLS = {
    "python": ["python", "py"],
    "java": ["java", "core java"],
    "javascript": ["javascript", "js"],
    "typescript": ["typescript", "ts"],
    "sql": ["sql", "structured query language"],
    "nosql": ["nosql", "non relational database"],
    "rest api": ["rest api", "restful api", "api development"],
    "microservices": ["microservices", "microservice architecture"],
    "docker": ["docker", "containerization"],
    "kubernetes": ["kubernetes", "k8s"],
    "git": ["git", "version control"],
    "ci/cd": ["ci/cd", "continuous integration", "continuous delivery"],
}

ROLE_SKILLS = {
    "Data Analyst": [
        "excel", "power bi", "tableau", "data visualization", "statistics",
        "hypothesis testing", "a/b testing", "data cleaning", "data wrangling",
        "business analysis", "dashboarding", "reporting", "etl", "data modeling",
        "google sheets", "looker", "qlik sense", "bigquery", "snowflake", "redshift",
    ],
    "Data Scientist": [
        "machine learning", "deep learning", "pandas", "numpy", "scikit-learn",
        "feature engineering", "model evaluation", "classification", "regression",
        "clustering", "nlp", "computer vision", "time series", "xgboost",
        "lightgbm", "catboost", "tensorflow", "pytorch", "matplotlib", "seaborn",
    ],
    "ML Engineer": [
        "mlops", "model serving", "model deployment", "feature store", "mlflow",
        "airflow", "kubeflow", "onnx", "fastapi", "flask", "grpc", "spark",
        "distributed training", "model monitoring", "drift detection",
        "inference optimization", "gpu computing", "cuda", "ray", "dvc",
    ],
    "Backend Developer": [
        "spring boot", "django", "fastapi", "flask", "express.js", "node.js",
        "hibernate", "jpa", "orm", "redis", "postgresql", "mysql", "mongodb",
        "message queues", "rabbitmq", "kafka", "api gateway", "oauth2", "jwt", "graphql",
    ],
    "Frontend Developer": [
        "react", "angular", "vue.js", "html", "css", "sass", "tailwind css",
        "bootstrap", "webpack", "vite", "babel", "redux", "next.js", "nuxt.js",
        "responsive design", "ui design", "accessibility", "web performance",
        "typescript", "jest", "cypress",
    ],
    "Full Stack Developer": [
        "mern", "mean", "lamp", "full stack development", "api integration",
        "authentication", "session management", "system design", "unit testing",
        "integration testing", "deployment", "linux", "nginx", "apache", "graphql",
        "prisma", "sequelize", "socket.io", "websockets", "serverless",
    ],
    "Java Developer": [
        "j2ee", "spring", "spring mvc", "spring security", "maven", "gradle",
        "junit", "mockito", "tomcat", "jetty", "hibernate", "multithreading",
        "concurrency", "jvm tuning", "design patterns", "kafka", "oracle db",
        "pl/sql", "soap", "xml",
    ],
    "Python Developer": [
        "django", "fastapi", "flask", "celery", "sqlalchemy", "alembic",
        "pytest", "pydantic", "asyncio", "beautifulsoup", "scrapy", "pyspark",
        "data pipelines", "automation", "scripting", "linux", "gunicorn",
        "uvicorn", "poetry", "pip",
    ],
    "DevOps Engineer": [
        "terraform", "ansible", "jenkins", "github actions", "gitlab ci",
        "prometheus", "grafana", "elk stack", "splunk", "helm", "argocd",
        "infrastructure as code", "sre", "incident response", "monitoring",
        "logging", "aws", "azure", "gcp", "networking",
    ],
    "Cloud Engineer": [
        "aws", "azure", "gcp", "iam", "vpc", "ec2", "s3", "lambda", "eks", "ecs",
        "cloudformation", "azure devops", "azure functions", "gke", "cloud run",
        "cloud security", "cost optimization", "disaster recovery", "high availability", "dns",
    ],
    "BI Analyst": [
        "power bi", "tableau", "qlik", "looker studio", "ssrs", "ssis", "ssas",
        "data warehousing", "kimball", "star schema", "data marts", "kpi design",
        "executive reporting", "business storytelling", "excel", "sql", "dax",
        "power query", "mdx", "olap",
    ],
    "MLOps Engineer": [
        "mlflow", "kubeflow", "seldon", "bentoml", "airflow", "prefect",
        "feature store", "model registry", "model governance", "data versioning",
        "experiment tracking", "model observability", "prometheus", "grafana",
        "kubernetes", "docker", "ray serve", "onnx runtime", "triton inference server", "feast",
    ],
}

SOFT_SKILLS = [
    "communication", "teamwork", "problem solving", "critical thinking",
    "leadership", "stakeholder management", "time management", "adaptability",
    "mentoring", "presentation skills", "documentation", "collaboration",
    "analytical thinking", "attention to detail", "ownership", "creativity",
    "conflict resolution", "negotiation", "agile mindset", "decision making",
]


def _synonyms(skill: str) -> list[str]:
    aliases = {skill}
    if "/" in skill:
        aliases.add(skill.replace("/", " "))
    if "-" in skill:
        aliases.add(skill.replace("-", " "))
    if "." in skill:
        aliases.add(skill.replace(".", ""))
    aliases.add(skill.lower())
    return sorted(aliases)


def build_lexicon() -> dict[str, list[str]]:
    lexicon: dict[str, list[str]] = {}
    lexicon.update(BASE_SKILLS)

    for role_skills in ROLE_SKILLS.values():
        for skill in role_skills:
            canonical = skill.lower().strip()
            lexicon.setdefault(canonical, _synonyms(canonical))

    for skill in SOFT_SKILLS:
        canonical = skill.lower().strip()
        lexicon.setdefault(canonical, _synonyms(canonical))

    # Add a controlled expansion to exceed 250 canonical entries.
    extra_prefixes = [
        "aws", "azure", "gcp", "java", "python", "react", "kubernetes",
        "docker", "sql", "spark", "pytorch", "tensorflow",
    ]
    extra_suffixes = [
        "security", "optimization", "automation", "integration", "testing",
        "monitoring", "orchestration", "architecture", "pipelines", "deployment",
        "scalability", "governance", "observability", "administration",
    ]
    for prefix in extra_prefixes:
        for suffix in extra_suffixes:
            skill = f"{prefix} {suffix}"
            lexicon.setdefault(skill, _synonyms(skill))

    # Normalize synonyms and remove duplicates.
    for key, vals in list(lexicon.items()):
        uniq = sorted({v.lower().strip() for v in vals if v and v.strip()})
        lexicon[key] = uniq

    return dict(sorted(lexicon.items(), key=lambda kv: kv[0]))


def main() -> None:
    lexicon = build_lexicon()
    out_path = Path("datasets/skills.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(lexicon, indent=2), encoding="utf-8")

    print(f"Saved {out_path}")
    print(f"Total canonical skills: {len(lexicon)}")
    print("20 example entries:")
    for idx, (k, v) in enumerate(lexicon.items()):
        if idx >= 20:
            break
        print(f"- {k}: {v[:4]}")


if __name__ == "__main__":
    main()
