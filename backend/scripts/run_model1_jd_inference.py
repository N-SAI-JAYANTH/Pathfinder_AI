from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

# Make backend package importable when script is run from repo root.
REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = REPO_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.services.model1_service import model1_service


LABEL_WEIGHT = {
    "core": 3.0,
    "important": 2.0,
    "supporting": 1.0,
    "optional": 0.5,
}


JD_1_TITLE = "Software Development Engineer, AGI - Web information retrieval"
JD_1_TEXT = """
Job ID: 10408357 | Amazon.com Services LLC
Description
Amazon AGI is pioneering the next frontier of artificial general intelligence, leveraging over 25 years of AI and machine learning expertise along with Amazon's world-class infrastructure and commitment to responsible AI. Join our diverse team of scientists, engineers, and researchers to push the boundaries of what's possible - from reinventing commerce and enterprise productivity to advancing universal agents and robotics.

We are looking for a Software Development Engineer within AGI to develop a multi-modal, multi-lingual web-scale information retrieval system to make the world's information accessible to AI models and customers everywhere. We are pushing the boundaries of what's possible by combining the power of large language models with retrieval systems, enabling capabilities in question-answering, knowledge synthesis, and information grounding.

You will have an opportunity to directly impact the customer experience, design, architecture, and implementation of products that will be used every day by people you know. We're looking for someone passionate about innovating on behalf of customers, who demonstrates strong product ownership and is willing to think in new ways to solve difficult problems.

You will have track record of success in delivering new products, solving problems, and learning new technologies quickly. A commitment to teamwork, proactive approach to solving problems, and strong verbal and written communication skills are essential. Creating reliable, scalable, and high-performance products requires technical expertise, understanding of computer science fundamentals, and practical experience building efficient large-scale distributed systems. This person is comfortable delivering quality solutions in a fast-growing environment where priorities may change rapidly.

Key job responsibilities
* Build high-throughput, cost-effective data pipelines to support feature extraction and indexing for our web-scale Information Retrieval (IR) system
* Develop and optimize the core algorithms in Rust and ranking models that power the search engine's ability to retrieve and rank relevant results for user queries.
* Design and implement efficient data structures and indexing techniques to store and retrieve massive amounts of web data and content using Rust programming language.
* Optimize the performance, scalability, and reliability of the search engine's core components, including query parsing, retrieval, ranking, and result rendering.
* Collaborate with machine learning teams to integrate and deploy advanced machine learning models for query understanding, ranking, and personalization.
* Develop and maintain the control plane systems that manage and orchestrate the IR system infrastructure, including the distributed compute clusters, storage systems, and networking components.
* Design and implement real-time updates and freshness mechanisms to ensure the I engine reflects the latest web content and user behavior.
* Develop efficient, state-of-the-art streaming algorithms for processing large datasets (e.g. deduplication, topic clustering)
* Participate in the design and implementation of real-time updates and freshness mechanisms to ensure the search engine reflects the latest web content and user behavior.

Basic Qualifications
- 3+ years of non-internship professional software development experience
- 2+ years of non-internship design or architecture (design patterns, reliability and scaling) of new and existing systems experience
- 1+ years of software development engineer or related occupational experience
- 1+ years of designing and developing large-scale, multi-tiered, multi-threaded, embedded or distributed software applications, tools, systems, and services using: C#, C++, Java, or Perl experience
- 1+ years of Object Oriented Design experience
- Bachelor's degree or foreign equivalent in Computer Science, Engineering, Mathematics, or a related field

Preferred Qualifications
- 3+ years of full software development life cycle, including coding standards, code reviews, source control management, build processes, testing, and operations experience
- Proficiency in Rust
"""


JD_2_TITLE = "HR Operations Manager"
JD_2_TEXT = """
About the job
Job Description

Position Title: HR Operations Manager
Location: REMOTE PAN-INDIA
Experience: 3-6 years
Industry: IT Consulting / Staff Augmentation
Client Focus: FAANG (with specific experience supporting Amazon)
Type: Full-Time

Must have recent experience as an HR Operations Manager in an IT Consultancy/Staffing Company

About The Role
We are seeking a dynamic and detail-oriented HR Operations Manager with deep expertise in workforce strategy, delivery operations, and HR program execution within IT consulting/staffing environments. This role is ideal for someone who has successfully driven staff augmentation initiatives with high-profile clients like Amazon, particularly in deploying Software Development Engineers (SDEs) across multiple business units.

The individual will play a pivotal role in aligning internal operational capabilities with external client demands, ensuring scalable, efficient, and compliant talent deployment for long-term success.

Key Responsibilities
Strategic Workforce Planning & Delivery:
Lead strategic initiatives for scaling SDE deployments into Amazon (and similar FAANG clients), aligning delivery capacity with project demand forecasts.
Design, refine, and implement operational playbooks for full-lifecycle staff augmentation: sourcing, onboarding, compliance, billing, and retention.

FAANG Client Strategy Execution
Build and manage operational frameworks specifically tailored to Amazon's vendor protocols and contingent workforce requirements.
Oversee high-stakes delivery pipelines, ensuring timely onboarding of SDEs and smooth transitions across projects or geographies.
Act as a strategic liaison between client stakeholders (Amazon Vendor Managers/MSP teams) and internal account managers, recruiting leads, and HR partners.

Operations & Process Optimization
Identify inefficiencies across delivery operations and develop solutions that enhance turnaround time, onboarding speed, and compliance accuracy.
Leverage data and reporting (ATS/HRIS insights) to monitor KPIs like onboarding velocity, offer-to-join ratio, resource utilization, and extension/roll-off trends.

Compliance, Risk, And Client Readiness
Ensure all operational processes adhere to client-specific audit standards (e.g., Amazon's compliance framework, data privacy rules, background screening).
Maintain and improve documentation workflows for SOWs, VMS entries (Beeline, Fieldglass), consultant contracts, and visa status management.

Team Leadership & Stakeholder Management
Mentor delivery coordinators, onboarding teams, and HR specialists to align execution with client priorities.
Drive stakeholder engagement with cross-functional teams (HR, Legal, Tech, Recruiting) for seamless execution of talent strategies.

Required Skills & Qualifications
7+ years in strategic operations, HR delivery, or program management in IT consulting or staff augmentation firms.
Proven track record placing SDEs or technical consultants at Amazon, with a deep understanding of their hiring workflows and VMS systems.
Strong working knowledge of workforce operations, vendor engagement models, and delivery SLAs in a high-growth, multi-client environment.
Demonstrated ability to manage complex programs, lead cross-functional teams, and implement data-driven operational strategies.
Proficiency in tools like Jira, Trello, Greenhouse, BambooHR, SuccessFactors, and project tracking/reporting systems.

Preferred
Hands-on experience with Amazon's Contingent Workforce Program, onboarding portals, or vendor compliance tools.
Understanding of India & APAC hiring and resource mobility planning.
MBA or relevant master's degree in Operations, HR Strategy, or Business Management is a plus.

Skills: delivery operations, stakeholder engagement, IT consulting, compliance management, hr program execution, strategic planning, staff augmentation, performance metrics monitoring, vendor management, risk management, project management, sde deployment, amazon, data analysis, operational playbook design, team leadership, workforce strategy
"""


def run_inference(title: str, jd_text: str) -> pd.DataFrame:
    rows = model1_service.analyze_jd(title, jd_text)
    if not rows:
        return pd.DataFrame(columns=["skill", "importance_label", "importance_score", "weight"])

    df = pd.DataFrame(rows)
    df["weight"] = df["importance_label"].map(LABEL_WEIGHT).fillna(0.0)
    df = df.sort_values(["weight", "importance_score"], ascending=[False, False]).reset_index(drop=True)
    return df[["skill", "importance_label", "importance_score", "weight"]]


def top_critical(df: pd.DataFrame, top_k: int = 10) -> pd.DataFrame:
    if df.empty:
        return df
    crit = df[df["importance_label"].isin(["core", "important"])].copy()
    return crit.head(top_k)


def main() -> None:
    jobs = [
        {"name": "JD1_Amazon_AGI_SDE", "title": JD_1_TITLE, "jd_text": JD_1_TEXT},
        {"name": "JD2_HR_Operations_Manager", "title": JD_2_TITLE, "jd_text": JD_2_TEXT},
    ]

    output_bundle = {}

    for job in jobs:
        df = run_inference(job["title"], job["jd_text"])
        critical = top_critical(df, top_k=10)
        output_bundle[job["name"]] = {
            "title": job["title"],
            "num_extracted_skills": int(len(df)),
            "top_critical_skills": critical.to_dict(orient="records"),
            "predictions": df.to_dict(orient="records"),
        }

        print(f"\n===== {job['name']} =====")
        print(f"Title: {job['title']}")
        print(f"Extracted skills: {len(df)}")
        print("\nTop critical skills:")
        if critical.empty:
            print("None")
        else:
            print(critical.to_string(index=False))
        print("\nAll predicted skills:")
        if df.empty:
            print("No skills extracted.")
        else:
            print(df.to_string(index=False))

    out_path = REPO_ROOT / "backend/scripts/model1_inference_results.json"
    out_path.write_text(json.dumps(output_bundle, indent=2), encoding="utf-8")
    print(f"\nSaved structured output: {out_path}")


if __name__ == "__main__":
    main()

