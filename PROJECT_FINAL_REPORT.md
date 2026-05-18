# PathFinder AI — Final Technical Report

**Document purpose:** Single reference for stakeholders and reviewers describing implemented features, methods, APIs, data, and measured results.

**Codebase:** PathFinder AI (React + FastAPI + SQLite + optional ChromaDB / Gemini)

**Last updated:** May 2026

---

## Table of contents

1. [Executive summary](#1-executive-summary)  
2. [Architecture at a glance](#2-architecture-at-a-glance)  
3. [Career recommendation](#3-career-recommendation)  
4. [Job matching: baseline and two ML models](#4-job-matching-baseline-and-two-ml-models)  
5. [Roadmap generation](#5-roadmap-generation)  
6. [Adaptive roadmap “RL” (contextual bandit)](#6-adaptive-roadmap-rl-contextual-bandit)  
7. [Other implemented features](#7-other-implemented-features)  
8. [Data pipeline and artifacts](#8-data-pipeline-and-artifacts)  
9. [Evaluation results (offline)](#9-evaluation-results-offline)  
10. [API surface (reference)](#10-api-surface-reference)  
11. [Frontend coverage](#11-frontend-coverage)  
12. [How to run and reproduce](#12-how-to-run-and-reproduce)  
13. [Related documentation in the repo](#13-related-documentation-in-the-repo)  
14. [Limitations and honest scope notes](#14-limitations-and-honest-scope-notes)  

---

## 1. Executive summary

PathFinder AI is an end-to-end career guidance web application. It supports **users** (profiles, resume upload, career suggestions, job discovery, personalized roadmaps) and **recruiters** (job postings). Intelligence combines:

| Area | Approach | Role in product |
|------|----------|-----------------|
| **Career recommendation** | KNN over multi-label skill vectors vs. a career–skill reference table | “What careers fit my skills?” |
| **Baseline job matching** | Doc2Vec embeddings + cosine similarity + optional skill-overlap hybrid on live DB jobs | Primary UX path: `POST /api/ai/match-jobs` |
| **Model 1 — JD skill importance** | Weak labels + features → **XGBoost** classifier (`core` / `important` / `supporting` / `optional`) | Parses JD into weighted skills for explainable fit |
| **Model 2 — User–job fit** | Hand-built fit features (including Model 1 outputs) → **XGBoost** (`high_fit` / `medium_fit` / `low_fit`) | Structured fit label, confidence, critical missing skills |
| **Roadmap generation** | **Google Gemini** structured JSON (role summary, gap analysis, phased tasks) | Personalized learning plan per job + user |
| **Roadmap adaptation** | **Contextual bandit** (linear model, ε-greedy), *not* full MDP RL | After feedback: local edits to roadmap JSON; Gemini only for new task text when needed |

Offline metrics for the two XGBoost models are strong on held-out data (see [§9](#9-evaluation-results-offline)). The bandit is designed for **sample-efficient** online learning from explicit user signals (complete, skip, difficulty).

---

## 2. Architecture at a glance

```text
┌─────────────────────────────────────────────────────────────┐
│  React 19 frontend (TypeScript, Axios, React Router)        │
│  Landing · Auth · User/Recruiter dashboards · Jobs ·        │
│  Career recommendations · Job matching · Roadmaps · Chat    │
└───────────────────────────┬─────────────────────────────────┘
                            │ HTTPS / JSON (JWT)
┌───────────────────────────▼─────────────────────────────────┐
│  FastAPI backend (app/main.py + routers)                     │
│  Auth · Profiles · Jobs CRUD/search · AI endpoints ·        │
│  Roadmaps · Phase 2 (log / recommend / adapt / RAG)          │
└───────┬─────────────────┬─────────────────┬───────────────┘
        │                 │                 │
        ▼                 ▼                 ▼
   SQLite DB         ML artifacts       ChromaDB (optional)
   (users, jobs,     KNN, Doc2Vec,     RAG over jobs/
    roadmaps,        model1.pkl,       roadmap chunks
    interactions,   model2.pkl,
    bandit rows)     rl_model.pkl
```

**Key technologies:** FastAPI, SQLAlchemy, Alembic, JWT, scikit-learn, gensim (Doc2Vec), XGBoost, Google Gemini, ChromaDB.

---

## 3. Career recommendation

### What it does

Given the user’s skills (profile + resume extraction), the backend returns **top-K similar careers** from a reference table with **similarity score**, **matching skills**, **missing skills**, and **required skills** for the top match (used elsewhere for gap analysis).

### Implementation

- **Module:** `backend/app/services/ml/career_ml.py` → `recommend_careers_knn`
- **Algorithm:** `MultiLabelBinarizer` on skill lists → **KNN** (distance → similarity `1 - distance`)
- **Artifacts (under configured `ML_MODELS_DIR`, typically `backend/ml_models/`):** `knn_career_model.pkl`, `skills_mlb.pkl`, `career_reference.pkl`
- **API:** `POST /api/ai/recommend-careers` (requires profile with skills)

### Why this design

Interpretable, fast at inference, no GPU; “nearest neighbor” explanations map naturally to product copy (“careers like yours”).

---

## 4. Job matching: baseline and two ML models

This project implements **three complementary** mechanisms. They answer different questions and are wired to different endpoints.

### 4.1 Baseline matcher — Doc2Vec + hybrid score (primary app flow)

**Purpose:** Rank **live jobs in SQLite** for the logged-in user using resume + profile text.

**Implementation:** `match_jobs_from_database` in `backend/app/services/ml/career_ml.py`

- Tokenize with `gensim.utils.simple_preprocess` (deaccent, length limits).
- **Infer** a vector for the user text and for each job’s concatenated title, JD, skills, industry, experience level via **Doc2Vec** (`infer_vector`, 20 epochs).
- **Cosine similarity** between user vector and each job vector.
- **Hybrid score:** `0.7 * embedding_similarity + 0.3 * (skill_match_fraction)` then scaled to a percentage-style `match_score`.
- **API:** `POST /api/ai/match-jobs` (`main.py`) — used by the Job Matching UI.

**Artifacts:** `doc2vec_job_model.model`, `job_vectors.pkl`, `job_metadata.pkl` (also used for static Kaggle-style job lists via `match_jobs_doc2vec`).

### 4.2 Model 1 — Skill importance from the job description

**Purpose:** Turn a raw JD into a list of **canonical skills** each labeled by **importance** for that role.

**Implementation:** `backend/app/services/model1_service.py` (`Model1Service`)

- Extracts candidate competencies (lexicon-driven pipeline under `backend/services/` with `competency_extractor` / `competency_normalizer`).
- Builds features per skill: **context** cues (e.g. “must have”, “preferred”), **section** cues (requirements vs. bonus), title/JD **similarity** (sentence-transformer **MiniLM-L6-v2** when available; lexical fallback), frequency, competency type code.
- **Classifier:** XGBoost (`models/model1_skill_importance/model1.pkl`) with `label_encoder.pkl`.
- **Lexicon:** `datasets/skills.json` (canonical skills + synonyms; audit noted ~416 canonical entries).

**API:** `POST /analyze-jd` (body: title + `jd_text`) — router `backend/app/match_routes.py` (no `/api` prefix on this router; see [§10](#10-api-surface-reference)).

### 4.3 Model 2 — User–job fit (stacked on Model 1)

**Purpose:** Predict **overall fit** and list **matched / missing / critical missing** skills with an explanation feature map.

**Implementation:** `backend/app/services/model2_service.py` (`Model2Service`)

1. Run **Model 1** on the JD to get weighted skill rows.
2. Compare **user skills** (normalized set) to those rows; aggregate **matched/missing** counts by importance bucket (`core`, `important`, `supporting`; `optional` skipped for fit).
3. Build a fixed **feature vector** (counts, weighted sums, `match_ratio`, experience gap/score, project/cert/education heuristics, lexical profile–JD similarity).
4. **XGBoost** predicts `fit_label` ∈ {`high_fit`, `medium_fit`, `low_fit`}; `predict_proba` exposes **confidence** as `fit_score`.

**APIs:**

- `POST /match-user-job` — single user profile + single job description.
- `POST /recommend-jobs` — scores up to 500 active DB jobs, sorts by `fit_score` / label rank, returns top `top_k`.

**Note:** The React `api.js` client currently wires **Doc2Vec** matching (`matchJobs`) and Phase 2; the Model 1/2 REST endpoints are implemented for **APIs, scripts, and integration** (`backend/scripts/test_match_endpoints.py`).

---

## 5. Roadmap generation

### What it does

Produces a **structured JSON roadmap**: `role_summary`, `gap_analysis`, and `roadmap.phases[]` with tasks (`task_id`, `title`, `description`, `status_options`, courses/projects, `skills_gained`, `jd_alignment`, etc.).

### Implementation

- **Module:** `backend/app/services/roadmap/job_roadmap.py` (Gemini `gemini-2.5-flash`, temperature **0.4**).
- **Service wrapper:** `backend/app/job_roadmap_service.py` re-exports `generate_job_roadmap`, `regenerate_task`.
- **User flow:** `POST /api/jobs/{job_id}/generate-roadmap-for-user` builds `job_dict` + rich `user_profile` from `UserProfile` + resume-derived skills.
- **Recruiter template:** `POST /api/jobs/{job_id}/generate-roadmap` uses a generic candidate profile.
- **Persistence:** `POST /api/roadmaps/save` — max **3** saved roadmaps per user (oldest evicted).
- **Task refresh:** `POST /api/roadmaps/{roadmap_id}/tasks/{task_id}/regenerate` with feedback (Gemini, higher temperature **0.7** for variation).

**Important:** Initial generation does **not** run the bandit; adaptation is a **separate** Phase 2 loop after the user interacts (see [§6](#6-adaptive-roadmap-rl-contextual-bandit)).

**Deprecated:** `POST /api/ai/generate-roadmap` returns HTTP 410 with a message to use job-based generation.

---

## 6. Adaptive roadmap “RL” (contextual bandit)

### Terminology

The README and code describe this correctly as a **contextual bandit** (single-step decision with immediate reward), **not** full Markov Decision Process RL (no long-horizon credit assignment).

### Policy and mechanics

- **Implementation:** `backend/app/services/rl/bandit.py` (`RLService`), persisted to **`rl_model.pkl`** (path from `RL_MODEL_PATH` in config).
- **State dimension:** **10** (named in `STATE_FEATURE_NAMES`: phase/task indices, difficulty, recent ratings, skip/completion/regenerate counts, JD importance, user–task skill match, prerequisite signal).
- **Actions (7):** `KEEP_NEXT_TASK`, `ADD_PREREQUISITE_TASK`, `DECREASE_DIFFICULTY`, `INCREASE_DIFFICULTY`, `REPEAT_WITH_VARIATION`, `REORDER_NEARBY_TASK`, `SKIP_OPTIONAL_TASK`.
- **Exploration:** ε-greedy with **ε = 0.15** (code default).
- **Learning:** Linear reward prediction per arm; **SGD-style** update on observed reward; legacy arm names mapped via `LEGACY_ACTION_MAP`.

### Rewards (high level, aligned with `phase2_routes.py`)

- **Complete:** +1.0, or **+1.3** when the task is high JD-importance.
- **Difficulty rating:** mapped from 1→5 (e.g. 5 → +1.0, 1 → −0.8).
- **Skip:** penalties with stronger penalty for high JD-importance and repeated skips on the same task.

### API flow

1. **`POST /api/phase2/interactions/log`** — stores `JobInteraction`; attributes reward to pending `RoadmapBanditDecision` when present; updates policy.
2. **`GET /api/phase2/recommend?roadmap_id=&task_id=`** — builds state, selects action, persists `RoadmapBanditDecision`, returns action + **`state_vector`** + human-readable **`reason`** (`roadmap_rl_explainer.explain_action`).
3. **`POST /api/phase2/roadmap/adapt`** — applies `roadmap_adaptation.apply_roadmap_action` to mutate saved JSON; may call Gemini for rewritten task text.

**QA:** With `ENVIRONMENT` in `development`/`test` or `ADAPTIVE_RL_DEBUG=true`, `forced_action` is accepted on `/recommend`. End-to-end script: `backend/scripts/e2e_adaptive_roadmap_flow.py`.

**Database:** Alembic migration `f7a8b9c0_add_roadmap_bandit_decisions.py` adds **`RoadmapBanditDecision`** for auditing decisions and rewards.

### UI

`frontend/src/pages/User/RoadmapDetail.js` chains log → recommend → adapt when appropriate (see `phase2API` in `frontend/src/services/api.js`).

---

## 7. Other implemented features

| Feature | Description |
|--------|-------------|
| **Authentication** | JWT for users and recruiters; register + OAuth2 password login. |
| **User profile** | CRUD profile; CGPA fields, skills, certs, achievements. |
| **Resume upload** | PDF/DOC; text extraction + **Gemini** structured skill extraction (`gemini_service`). |
| **Recruiter jobs** | Legacy and **enhanced** job schemas (title, JD, salary, remote, skills arrays, etc.). |
| **Job search** | Filter/sort: keyword, location, remote, experience, type, salary, industry, skills, recency. |
| **Skill gap analysis** | Top-1 KNN career → required skills → **Gemini** narrative gap analysis. |
| **Strengths / weaknesses** | **Gemini** analysis from profile dict. |
| **AI chat** | **Gemini** chat with light user context. |
| **RAG** | ChromaDB indexing of jobs/roadmaps; **`POST /api/phase2/rag/query`** (`phase2_routes` + `rag_service`). Optional seed: `backend/scripts/seed_rag.py`. |
| **Scripts / QA** | `audit_e2e.py`, `test_match_endpoints.py`, multidomain competency tests, Model 1 JD inference JSON outputs under `backend/scripts/`. |

---

## 8. Data pipeline and artifacts

Under `data_pipeline/`:

| Script | Role (conceptual) |
|--------|-------------------|
| `prepare_jobs_from_hf.py` | Ingest / normalize job postings. |
| `balance_jobs.py` | Role-balanced job subsets. |
| `generate_skills_lexicon.py`, `expand_competency_lexicon.py` | Skills / synonym expansion. |
| `build_skill_dataset.py`, `weak_label_skill_importance.py` | Weak labels + dataset for Model 1. |
| `generate_users_dataset.py`, `build_fit_dataset.py`, `weak_label_fit.py` | Synthetic / weak-labeled user–job fit rows for Model 2. |

**Datasets (repo):** e.g. `datasets/jobs.csv`, `jobs_balanced.csv`, `user_job_fit_balanced.csv`, `skill_importance_labeled.csv`, `skills.json` — used for training and audits.

**Audit snapshot:** `backend/scripts/audit_report.json` summarizes row counts and distributions (e.g. ~1005 jobs in `jobs.csv`, 55 balanced rows, 480 synthetic users, lexicon stats, numeric ranges for training columns).

---

## 9. Evaluation results (offline)

Results below are from **`metrics.txt`** after training with **XGBoost** (stratified splits in `train_model1.py` / `train_model2.py`). They reflect **held-out test** performance on the project’s labeled tables, not live A/B production metrics.

### Model 1 — Skill importance (`models/model1_skill_importance/metrics.txt`)

| Metric | Value |
|--------|------:|
| Accuracy | **0.9860** |
| Macro precision | **0.9782** |
| Macro recall | **0.9683** |
| Macro F1 | **0.9732** |

Per-class F1 (support on test split, total support **1857**): `core` ~0.97, `important` ~0.95, `optional` ~0.99, `supporting` ~0.99.

### Model 2 — User–job fit (`models/model2_job_fit/metrics.txt`)

| Metric | Value |
|--------|------:|
| Accuracy | **0.9235** |
| Macro precision | **0.9269** |
| Macro recall | **0.9278** |
| Macro F1 | **0.9272** |

Per-class F1 (support **56,323**): `high_fit` ~0.97, `low_fit` ~0.93, `medium_fit` ~0.88.

### Doc2Vec / bandit

- **Doc2Vec:** No single aggregate accuracy metric in-repo (ranking task); quality is assessed qualitatively + hybrid skill term.
- **Bandit:** Online metric depends on deployment and traffic; policy file `rl_model.pkl` updates from real `JobInteraction` / decisions.

---

## 10. API surface (reference)

**Prefix convention:** Most user-facing routes use `/api/...`. The ML matching router is mounted **without** a prefix — call the absolute paths below against the same host/port as the app (e.g. `http://127.0.0.1:8001`).

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| POST | `/api/auth/register-user` | No | User signup |
| POST | `/api/auth/register-recruiter` | No | Recruiter signup |
| POST | `/api/auth/login` | No | OAuth2 form login |
| GET/POST/PUT | `/api/user/profile` | User | Profile |
| POST | `/api/user/upload-resume` | User | Resume + skills |
| POST | `/api/ai/recommend-careers` | User | KNN careers |
| POST | `/api/ai/match-jobs` | User | Doc2Vec DB match |
| POST | `/api/ai/skill-gap-analysis` | User | Gap narrative |
| POST | `/api/ai/strengths-weaknesses` | User | Profile analysis |
| POST | `/api/ai/chat` | User | Chat |
| GET | `/api/jobs`, `/api/jobs/search`, `/api/jobs/{id}` | Mixed | Job board |
| POST | `/api/jobs/create` | Recruiter | Enhanced create (job router) |
| POST | `/api/jobs/{id}/generate-roadmap-for-user` | User | Roadmap JSON |
| POST | `/api/jobs/{id}/generate-roadmap` | Recruiter | Template roadmap |
| POST | `/api/roadmaps/save`, GET `/api/roadmaps`, DELETE `/api/roadmaps/{id}` | User | Saved roadmaps |
| POST | `/api/roadmaps/{id}/tasks/{task_id}/regenerate` | User | Task regenerate |
| POST | `/analyze-jd` | No* | Model 1 JD parse |
| POST | `/match-user-job` | No* | Model 2 single match |
| POST | `/recommend-jobs` | No* | Model 2 rank DB jobs |
| POST | `/api/phase2/interactions/log` | User | Bandit feedback |
| GET | `/api/phase2/recommend` | User | Bandit action + state |
| POST | `/api/phase2/roadmap/adapt` | User | Apply adaptation |
| POST | `/api/phase2/rag/query` | User | RAG |

\*Match routes are implemented without `Depends(auth)` in the snippet reviewed; **secure them behind auth / API gateway in production** if exposed publicly.

OpenAPI: `/docs` when the server is running.

---

## 11. Frontend coverage

| Area | Representative pages |
|------|----------------------|
| Marketing / auth | `LandingPage.js`, `Login.js`, `Register.js` |
| User | `Dashboard.js`, `Profile.js`, `ResumeUpload.js`, `CareerRecommendations.js`, `JobBoard.js`, `JobMatching.js`, `JobDetail.js`, `Roadmaps.js`, `RoadmapDetail.js`, `Analysis.js`, `Chat.js` |
| Recruiter | `Dashboard.js`, `CreateJob.js`, `CreateJobEnhanced.js`, `ManageJobs.js` |

---

## 12. How to run and reproduce

**Backend (port 8001):**

```bash
cd backend
pip install -r requirements.txt
# Copy backend/.env.example to backend/.env — set GEMINI_API_KEY for LLM features
python -m uvicorn app.main:app --host 127.0.0.1 --port 8001 --reload
```

**Frontend (port 3000):**

```bash
cd frontend
npm install
npm start
```

**RAG seed (optional):** from `backend/`, `python scripts/seed_rag.py`.

**Retrain models:** from repo root, run `python models/model1_skill_importance/train_model1.py` and `python models/model2_job_fit/train_model2.py` (requires prepared CSVs under `datasets/`).

---

## 13. Related documentation in the repo

| File | Content |
|------|---------|
| `README.md` | Run instructions + **authoritative** adaptive bandit description (rewards, 7 actions, 10-D state, ε=0.15). |
| `SYSTEM_DESIGN_EXPLAINED.md` | Broad system design (some RL details may predate the 7-arm bandit; prefer README + `bandit.py` for RL specifics). |
| `RL_EXPLAINED.md` | Conceptual bandit explanation; **may describe older 3-action / ε=0.2** wording — code + README win for exact numbers. |
| `docs/diagram_sources/*.mmd` | Mermaid sources for architecture / workflows. |

---

## 14. Limitations and honest scope notes

1. **Gemini dependency:** Roadmaps, chat, gap analysis, and parts of resume/RAG flows require API keys and network access.  
2. **SQLite + file models:** Suitable for demo and single-node deployment; production would typically add PostgreSQL, secrets management, and authenticated ML admin routes.  
3. **Two “RL” narratives:** Older docs refer to three high-level actions; production bandit uses **seven roadmap-edit actions** and richer state — see `backend/app/services/rl/bandit.py`.  
4. **Model 1/2 HTTP surface:** Mounted at **root-level** paths (`/analyze-jd`, etc.); align API gateway or add `APIRouter(prefix="/api/ml")` if you want a uniform `/api` namespace.  
5. **Evaluation:** Model metrics are **offline** on project datasets; they do not guarantee equal performance on arbitrary real employers’ JDs without monitoring.

---

*End of report.*
