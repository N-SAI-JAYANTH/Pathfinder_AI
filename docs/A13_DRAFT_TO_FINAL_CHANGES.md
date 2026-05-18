# A13 Report Draft — Required Changes vs. Implemented System

This checklist maps **`A13 Reort draft copy.docx`** to the **actual PathFinder AI codebase**. Apply these edits so the written report, figures, and tables match implementation, metrics, and diagrams in the repository.

---

## 1. Title page and front matter (minor)

| Item | Issue in draft | Change to make |
|------|----------------|----------------|
| Filename / title | Typo “Reort” in filename | Rename file to `A13 Report draft copy.docx` for submission hygiene. |
| Line 14 (extracted text) | Department header run-on (`...ENGINEERINGAMRITA...`) | Restore proper line breaks / spacing in Word. |
| Date | April 2026 | Keep consistent with signed declaration (e.g. 27 April 2026) vs. body “May 2026” for final code snapshot — pick one and state “as of [date]”. |

---

## 2. Abstract — factual corrections

| Draft wording | Problem | Replace with / add |
|---------------|---------|---------------------|
| “RL … improves **recommendation accuracy**” (generic) | Bandit does **not** re-rank job listings from clicks | State that **contextual bandit** adapts **saved learning roadmaps** from **task-level** feedback (`complete`, `skip`, `rate_difficulty`), with **7 discrete roadmap-edit actions** and persistence in `RoadmapBanditDecision` + `rl_model.pkl`. |
| Single “importance-aware weighted job-fit scoring” | Implementation is **two-stage**: Model 1 (skill importance) + Model 2 (fit label) **plus** separate **Doc2Vec** baseline matcher | Mention **three** mechanisms: (1) Doc2Vec + cosine + 70/30 hybrid for `/api/ai/match-jobs`, (2) XGBoost Model 1 on JD skills, (3) XGBoost Model 2 on engineered fit features. |
| “Resume … NLP” | Primary extraction uses **Gemini** (LLM), not classical NLP-only | Say **LLM-based** extraction (Gemini) + PDF parsing. |
| Career recommendation | Not in abstract | Add **KNN + MultiLabelBinarizer** over career–skill reference table. |

---

## 3. Objectives (Chapter 1.3) — align bullets to code

| Draft objective | Adjustment |
|-----------------|------------|
| RL from “job clicks, applications” | Replace with **roadmap task interactions** and **Phase 2** APIs (`/api/phase2/interactions/log`, `/recommend`, `/roadmap/adapt`). |
| Weighted job-fit only | Add objectives for **baseline semantic job matching (Doc2Vec)** and **offline-trained XGBoost models** (Model 1 / Model 2). |
| Roadmap | Specify **Gemini 2.5 Flash**, JSON schema, endpoints **`/api/jobs/{job_id}/generate-roadmap-for-user`** and deprecated **`/api/ai/generate-roadmap`** (410). |

---

## 4. List of figures — implement diagrams in Markdown

The draft lists figures but the `.docx` extract contained **captions only** (no embedded architecture PNGs in the extracted XML). For the **Markdown report**, implement as follows:

| Fig | Draft name | Implementation in `docs/A13_FULL_PROJECT_REPORT.md` |
|-----|------------|--------------------------------------------------------|
| Fig 1.1 | Overall architecture | **Mermaid** `flowchart` — use same content as `docs/diagram_sources/system-context.mmd` (or Fig 4.1 if you merge). |
| Fig 4.1 | System architecture | **Mermaid** from `docs/diagram_sources/container-architecture.mmd` (Frontend / Backend / Intelligence / Data). |
| Fig 4.2 | Workflow | **Mermaid** from `docs/diagram_sources/user-recruiter-workflow.mmd` + optional **sequence** from `runtime-sequence.mmd`. |
| Fig 5.1–5.5 | UI screenshots | **Placeholders**: “*Insert screenshot: …*” from running app at `http://localhost:3000` (Dashboard, Job Matching warning, Model 2 / UI outputs if exposed). If Word must have images, export PNGs from browser and paste. |

**Diagram source files to keep in sync:** `docs/diagram_sources/*.mmd` — render with Mermaid-compatible viewer or paste into report.

---

## 5. List of tables — add missing tables

| Table | Draft | Add or change |
|-------|-------|---------------|
| Table 2.1 | Comparative existing vs proposed | Add row: **Job matching** — split into “keyword/portal” vs “Doc2Vec + ML fit (Model1+2)”. Add row: **RL scope** — “N/A or generic” vs “Roadmap contextual bandit (7 actions, 10-D state)”. |
| Table 4.1 | Modules | **Add rows:** Career recommendation (KNN); Baseline job matcher (Doc2Vec); ML job fit (Model 1 + Model 2 APIs); Roadmap adaptation (Phase 2); **Remove or fix** “interview evaluation” if not implemented. |
| Table 4.2 | Performance metrics | **Extend** with rows for **Model 1** / **Model 2** offline accuracy, macro-F1 (from `metrics.txt`). Keep qualitative “response time” only if measured — else say “typical local deployment &lt; 2s for cached models”. |
| **New** | — | **Table 5.2** — Model 1 per-class precision/recall/F1 (from `models/model1_skill_importance/metrics.txt`). |
| **New** | — | **Table 5.3** — Model 2 per-class metrics (from `models/model2_job_fit/metrics.txt`). |
| **New** | — | **Table A.1** — Key REST endpoints (`/api/...` + `/analyze-jd`, `/match-user-job`, `/recommend-jobs` note: no `/api` prefix on match router). |

---

## 6. Chapter 4 (Proposed system) — technical rewrites

| Section | Change |
|---------|--------|
| 4.1 Overview | Name **SQLite**, **ChromaDB**, **Gemini**, **XGBoost**, **gensim Doc2Vec**, **JWT**. |
| 4.2 Architecture | Four layers OK; ensure **“vector DB for RAG”** is optional (seed script). Include **`match_routes`** and **`phase2_routes`** in backend description. |
| 4.3 Modules | Split “Job Recommendation” into **(A)** Doc2Vec user flow **(B)** Model 1/2 services. Rename “Reinforcement Learning” to **“Contextual bandit (roadmap adaptation)”** to avoid examiner pushback on “full RL”. |
| 4.4 Workflow | Insert step: **Save roadmap** → **task actions** → **log → recommend → adapt** (see `RoadmapDetail.js`). |
| 4.5 Evaluation | Cite **offline** test metrics; clarify bandit has **no** single offline accuracy in repo. |

---

## 7. Chapter 5 (Testing and results) — strengthen evidence

| Draft content | Change |
|---------------|--------|
| Weighted job-fit figures only | Add **quantitative** subsection with **Model 1** and **Model 2** tables from `metrics.txt`. |
| “Skills extracted from JD” narrative | Cite **Model 1** pipeline: lexicon `datasets/skills.json`, features (`context_score`, `section_score`, …), **XGBoost** (`train_model1.py`). |
| Testing strategy | Mention scripts: `backend/scripts/test_match_endpoints.py`, `e2e_adaptive_roadmap_flow.py`, `audit_e2e.py` / `audit_report.json`. |
| Table 5.1 | Map “Adaptability” to **roadmap** bandit, not generic job ranking. |

---

## 8. Chapter 6 (Conclusion / Future work) — accuracy

| Draft statement | Change |
|-----------------|--------|
| RL from clicks/applications | Same fix as abstract — **roadmap** feedback only. |
| Future: DQN / PPO | Add caveat: **contextual bandit** was chosen intentionally; deep RL is **future research**, not a gap in v1. |

---

## 9. Appendix — code samples outdated

| Appendix block | Issue | Fix |
|----------------|-------|-----|
| `main.py` snippet | Missing `match_router` | Show `app.include_router(match_router)` and imports from actual `backend/app/main.py`. |
| — | No Model 1/2 | Add short snippets or file paths: `app/services/model1_service.py`, `model2_service.py`, `match_routes.py`. |

---

## 10. References — editorial (optional but recommended)

Several references in the draft (blockchain freelancing, quantum EV charging, fake news, etc.) are **tangential** to career guidance.

- **Option A:** Replace with standard surveys on **job recommendation**, **skill extraction**, **RAG**, **contextual bandits** (e.g. Li et al. on contextual bandits; ACM RecSys tutorials).
- **Option B:** Keep draft list for submission continuity but add **2–3** directly relevant citations.

---

## 11. Cross-document consistency

| Document | Action |
|----------|--------|
| `RL_EXPLAINED.md` | May describe **3 actions** and **ε=0.2** — **do not** copy into final report; use **`README.md`** + `backend/app/services/rl/bandit.py` (7 actions, ε=0.15). |
| `SYSTEM_DESIGN_EXPLAINED.md` | Good for prose; verify RL section against code before pasting. |
| `PROJECT_FINAL_REPORT.md` | Technical summary; **A13 full report** should be superset for academic formatting. |

---

## 12. Deliverables produced in this repo

| File | Purpose |
|------|---------|
| `docs/A13_DRAFT_TO_FINAL_CHANGES.md` | This checklist. |
| `docs/A13_FULL_PROJECT_REPORT.md` | Full corrected report: chapters, **Mermaid** diagrams, tables, implementation, **offline results**, appendix. |

---

*Generated from comparison of `A13 Reort draft copy.docx` (text extraction) with the PathFinder AI repository (May 2026).*
