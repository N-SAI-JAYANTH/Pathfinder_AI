# PathFinder AI – Full System Design Explained

This document explains **what** each component is, **why** we use it, **why it is better** than alternatives, and the **methods, algorithms, tools, and datasets** used.

---

## 1. High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           FRONTEND (React)                                    │
│  Landing, Auth, User Dashboard, Profile, Resume Upload, Jobs, Roadmaps, Chat  │
└─────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           BACKEND (FastAPI)                                  │
│  REST API: /api/auth, /api/user, /api/jobs, /api/phase2, roadmaps, AI        │
└─────────────────────────────────────────────────────────────────────────────┘
                                        │
        ┌───────────────────────────────┼───────────────────────────────┐
        ▼                               ▼                               ▼
┌───────────────┐              ┌─────────────────┐              ┌───────────────┐
│ INTELLIGENCE  │              │ DATA LAYER      │              │ RL + RAG     │
│ LLM • ML • RAG│              │ SQLite • Chroma │              │ Bandit • RAG │
└───────────────┘              └─────────────────┘              └───────────────┘
```

---

## 2. Frontend Layer

### What it is
A single-page web application built with **React 19** and **TypeScript** that provides the UI for users (job seekers) and recruiters. It includes: landing page, login/register, user dashboard, profile, resume upload, career recommendations, job board, job matching, job details, roadmaps, roadmap detail, skill analysis, and an AI chat widget.

### Why we used it
- **React**: Component-based, large ecosystem, and easy to integrate with REST APIs.
- **TypeScript**: Type safety reduces bugs and improves maintainability.
- **React Router 7**: Handles client-side routing (e.g. `/jobs`, `/roadmaps`).
- **Axios**: Simple HTTP client for calling the FastAPI backend.

### Why it is better than alternatives
- **vs plain HTML/JS**: Reusable components, clear state flow, and better UX (e.g. protected routes, loading states).
- **vs Vue/Angular**: React’s ecosystem and hiring pool are large; React fits well with a JSON API backend.
- **vs server-rendered only**: Fast interactions after load, no full page reloads for navigation and API calls.

### Methods / Algorithms / Tools / Datasets
| Item | What |
|------|------|
| **Library** | React 19, React DOM |
| **Language** | TypeScript 4.9 |
| **Routing** | react-router-dom 7 |
| **HTTP** | Axios |
| **Build** | react-scripts (Create React App) |
| **Dataset** | None (consumes backend API only) |

---

## 3. Backend Layer (FastAPI)

### What it is
A **FastAPI** REST API that handles authentication, user profiles, resume uploads, recruiter job CRUD, job search/filter, roadmap generation, career/job-matching AI, and Phase 2 endpoints (interaction logging, RL recommendation, RAG query).

### Why we used it
- **FastAPI**: Async support, automatic OpenAPI docs (`/docs`), Pydantic validation, and high performance.
- **Python**: Same language as ML/LLM/RAG/RL code; easy to call scikit-learn, gensim, Gemini, ChromaDB from routes.

### Why it is better than alternatives
- **vs Flask**: Native async, automatic request/response validation, and built-in API docs.
- **vs Django REST**: Lighter and more flexible for an API-focused app with custom ML pipelines.
- **vs Node.js**: Python is the standard for ML/NLP; no need for a separate ML service in another language.

### Methods / Algorithms / Tools / Datasets
| Item | What |
|------|------|
| **Framework** | FastAPI ≥0.122, uvicorn 0.24 |
| **Auth** | JWT (python-jose), HS256, bcrypt for passwords |
| **DB access** | SQLAlchemy 2, sessions, `get_db` |
| **Validation** | Pydantic schemas |
| **Dataset** | None (orchestrates other components) |

---

## 4. Resume Parsing & Skill Extraction (LLM / Gemini)

### What it is
A pipeline that (1) extracts raw text from uploaded **PDF/DOC** resumes and (2) extracts **technical and soft skills** from that text. Implemented via **Google Gemini** API (LLM) for both text extraction and skill categorization.

### Why we used it
- **Gemini**: Strong at following instructions and returning structured JSON (e.g. `technical_skills`, `soft_skills`), works on unstructured text.
- **LLM vs rule-based**: Handles varied resume formats and wording without maintaining large keyword lists or complex regex.

### Why it is better than alternatives
- **vs regex/keyword lists**: Adapts to new phrasings and formats; fewer false negatives.
- **vs dedicated resume parsers (e.g. commercial APIs)**: Single API (Gemini), no extra vendor lock-in, and same model can be used for chat and roadmap generation.
- **vs local NER only**: Gemini gives good quality with no GPU or model training; easy to iterate on prompts.

### Methods / Algorithms / Tools / Datasets
| Item | What |
|------|------|
| **Text extraction** | PyPDF2 (PDF), Gemini or file parsing for DOC/DOCX |
| **Skill extraction** | Gemini API with a structured prompt (JSON output: `technical_skills`, `soft_skills`) |
| **Tools** | `google-generativeai`, PyPDF2 |
| **Storage** | Extracted text and skills stored in `UserProfile` (SQLite): `resume_path`, `extracted_skills` |
| **Dataset** | No fixed dataset; model generalizes over resume text |

---

## 5. ML Career Predictor (KNN)

### What it is
A **K-Nearest Neighbors (KNN)** model that takes a user’s **skill list** (from resume extraction), encodes it with **Multi-Label Binarizer (MLB)**, and finds the nearest career profiles in a reference table. It returns top-K careers with similarity score, matching skills, and missing skills.

### Why we used it
- **KNN**: Simple, interpretable, no heavy training pipeline; works well when “similar skills → similar career”.
- **MLB**: Turns variable-length skill lists into fixed-length binary vectors so KNN can compute distances (e.g. Hamming or metric on binary features).

### Why it is better than alternatives
- **vs decision trees only**: KNN uses the full skill vector; naturally handles multi-label skills.
- **vs deep learning**: No GPU, fast inference, easier to debug and explain (“nearest careers”).
- **vs rule-based mapping**: Learns from the career–skill reference data; adding new careers is a data update, not code change.

### Methods / Algorithms / Tools / Datasets
| Item | What |
|------|------|
| **Algorithm** | K-Nearest Neighbors (scikit-learn) |
| **Encoding** | Multi-Label Binarizer (sklearn) for skill lists → binary vector |
| **Similarity** | Distance from KNN (e.g. 1 - distance as similarity score) |
| **Tools** | scikit-learn, joblib, pandas, numpy |
| **Artifacts** | `knn_career_model.pkl`, `skills_mlb.pkl`, `career_reference.pkl` |
| **Dataset** | **AI Career Recommendation System** (Kaggle): career–skill mappings used to train KNN and build `career_reference.pkl` |

---

## 6. Job Embedding Matcher (Doc2Vec + Cosine Similarity)

### What it is
**Doc2Vec** (paragraph vector) represents each job and the resume as fixed-size vectors. **Cosine similarity** between the resume vector and all job vectors ranks jobs. The system supports (1) precomputed job vectors from a static dataset and (2) **live DB jobs**: encode each job’s title + JD + skills with Doc2Vec, then rank by similarity (and optional skill-overlap bonus).

### Why we used it
- **Doc2Vec**: Captures semantic similarity between resume and job text without requiring per-job labels; works on variable-length text.
- **Cosine similarity**: Standard for comparing embedding vectors; scale-invariant.
- **Hybrid score (for DB jobs)**: Combines 70% embedding similarity + 30% skill-match percentage so that explicit skill overlap is rewarded.

### Why it is better than alternatives
- **vs keyword match only**: Captures “Python, ML” matching “machine learning, Python” and similar phrasings.
- **vs TF-IDF + cosine**: Doc2Vec gives dense, semantic representations; often better for short documents like JDs.
- **vs BERT-style encoders**: Lighter and faster to train and run; good fit for in-memory job matching.

### Methods / Algorithms / Tools / Datasets
| Item | What |
|------|------|
| **Algorithm** | Doc2Vec (PV-DBOW), cosine similarity |
| **Tokenization** | `gensim.utils.simple_preprocess` (deacc=True, min_len=2, max_len=15) |
| **Inference** | `infer_vector(tokens, epochs=20)` for resume and for each job text |
| **Similarity** | `sklearn.metrics.pairwise.cosine_similarity` |
| **Tools** | gensim (Doc2Vec), scikit-learn, joblib, numpy, pandas |
| **Artifacts** | `doc2vec_job_model.model`, `job_vectors.pkl`, `job_metadata.pkl` |
| **Dataset** | **Jobs and Skills Mapping for Career Analysis** (Kaggle): `formatted_jobs.csv` — job title, Short_description, Skills_required, Industry, Pay_grade; used to train Doc2Vec and precompute job vectors. For app, live jobs from SQLite are also embedded on the fly. |

---

## 7. RAG Layer (Retrieval-Augmented Generation)

### What it is
A **RAG** service that (1) stores job descriptions and roadmap summaries in **ChromaDB** as chunked, embedded documents and (2) retrieves relevant chunks for a user query. Embeddings are from **Gemini embedding API** (or a default function if no API key). Retrieved context can be fed to the LLM for chat or roadmap generation so answers are grounded in your jobs/roadmaps.

### Why we used it
- **RAG**: Reduces hallucination by grounding the LLM in real job/roadmap data.
- **ChromaDB**: Simple, persistent vector store; no separate server; good for prototyping and small-to-medium scale.
- **Chunking**: Improves retrieval granularity (e.g. by sentence/word with overlap) so long JDs don’t dominate as one big block.

### Why it is better than alternatives
- **vs LLM only**: Answers reflect actual jobs and roadmaps in the DB.
- **vs Elasticsearch only**: Native vector search and embedding integration; simpler for “semantic search then LLM.”
- **vs Pinecone/Weaviate**: ChromaDB is embeddable and file-based; fewer moving parts for a single-app deployment.

### Methods / Algorithms / Tools / Datasets
| Item | What |
|------|------|
| **Vector DB** | ChromaDB (persistent client, collection `pathfinder_context`) |
| **Embeddings** | Gemini `models/embedding-001` (task_type=retrieval_document) or DefaultEmbeddingFunction |
| **Chunking** | Sentence-first, then word-based; `chunk_size=500`, `chunk_overlap=100`; overlap keeps context across chunks |
| **Retrieval** | Collection `query(query_texts=[query], n_results=n)` (uses embedding + similarity internally) |
| **Tools** | chromadb, google-generativeai (for embeddings) |
| **Indexed data** | Jobs (title, company, location, JD, skills, experience) and roadmaps (phase/task summaries) from SQLite; seeded via `scripts/seed_rag.py` |
| **Dataset** | Application data (jobs + roadmaps), not an external dataset |

---

## 8. LLM Roadmap Generator (Gemini)

### What it is
A **Gemini** (e.g. `gemini-2.5-flash`) based module that generates a **personalized learning roadmap** in JSON. Inputs: job (title, company, JD, skills, etc.) and user profile (degree, skills, experience, certifications, achievements). Output: structured roadmap with role summary, gap analysis (current/transferable/missing skills), and phases with tasks (title, description, status_options, recommended_courses/projects, skills_gained). Optionally uses **RL** to attach a recommended action (e.g. RECOMMEND_NEXT, INSERT_PREREQUISITE, SKIP_AHEAD). **Task regeneration** uses Gemini with user feedback (e.g. “skip” or “need easier”) to produce an alternative task.

### Why we used it
- **LLM**: Can follow complex instructions and produce structured JSON; fits variable job and user profiles.
- **Structured prompt**: Ensures consistent schema (phases, tasks, gap analysis) for the frontend and for RAG indexing.
- **Regenerate task**: Improves UX when a task is too hard or not relevant.

### Why it is better than alternatives
- **vs template-only roadmaps**: Content adapts to each JD and user.
- **vs rule-based steps**: Handles diverse roles and skill combinations without hand-written rules for every case.
- **vs another LLM**: Gemini balances cost/speed and quality for structured generation; single provider simplifies keys and monitoring.

### Methods / Algorithms / Tools / Datasets
| Item | What |
|------|------|
| **Model** | Google Gemini (e.g. `gemini-2.5-flash`) |
| **Method** | Single prompt with job + user profile → one JSON response; regex to strip markdown and parse JSON |
| **Temperature** | 0.4 for roadmap, 0.7 for task regeneration (more variation) |
| **Output schema** | role_summary, gap_analysis, roadmap.phases[].tasks[] with task_id, title, description, status_options, subtasks, recommended_courses, recommended_projects, skills_gained |
| **Tools** | google-generativeai |
| **Dataset** | No training dataset; in-context learning from prompt |

---

## 9. Reinforcement Learning Layer (Contextual Bandit)

### What it is
A **contextual bandit** that chooses among actions (e.g. `RECOMMEND_NEXT`, `INSERT_PREREQUISITE`, `SKIP_AHEAD`) given a **state** derived from user interaction history (e.g. average difficulty rating, completion rate). It uses **linear reward prediction** per action: reward is estimated as `θᵢ · state`; policy is **ε-greedy** (explore with probability ε, else choose action with highest predicted reward). On feedback, **SGD-style update**: `θ[action] += 0.1 * (reward - prediction) * state`, and rewards are logged for auditing.

### Why we used it
- **Contextual bandit**: Balances exploration and exploitation with user-specific state; simpler than full MDP RL.
- **Linear model**: Small, interpretable, fast to update; works with limited interaction data.
- **Reward from interactions**: Completing a task, skip, and difficulty ratings (e.g. 1–5 mapped to reward) provide a clear signal.

### Why it is better than alternatives
- **vs no personalization**: Ordering and suggestions can adapt to “too hard” / “skip” / “finished.”
- **vs full RL (e.g. DQN)**: Fewer parameters and samples needed; stable for a single-user flow.
- **vs A/B only**: Continuously improves the same policy from logged rewards instead of fixed variants.

### Methods / Algorithms / Tools / Datasets
| Item | What |
|------|------|
| **Algorithm** | Contextual bandit with linear reward model; ε-greedy (ε=0.2) |
| **State** | From `JobInteraction`: e.g. avg difficulty (normalized), completion rate, fixed extra dimensions (e.g. [0.1, 0.5, 1.0]) |
| **Actions** | RECOMMEND_NEXT, INSERT_PREREQUISITE, SKIP_AHEAD |
| **Update** | Incremental: `error = reward - θᵢ·state`; `θᵢ += 0.1 * error * state`; then save `rl_model.pkl` |
| **Reward** | complete=1.0, skip=-0.5; difficulty 1→-1.0, 2→-0.5, 3→0.1, 4→0.5, 5→1.0 |
| **Tools** | numpy, pickle; SQLAlchemy for JobInteraction, RewardLog |
| **Dataset** | **User interaction logs** (JobInteraction, RewardLog in SQLite); no external dataset |

---

## 10. Data Layer

### What it is
- **SQLite** (default): Stores users, user_profiles, recruiters, jobs, roadmaps, job_interactions, reward_logs.
- **ChromaDB** (files under `chroma_db/`): Vector store for RAG (job and roadmap chunks).
- **File storage**: `uploads/` for resumes; `ml_models/` for KNN, MLB, career reference, Doc2Vec, job vectors/metadata; `rl_model.pkl` for bandit weights.

### Why we used it
- **SQLite**: No separate DB server; good for development and single-node deployment; SQLAlchemy allows switching to PostgreSQL later.
- **ChromaDB on disk**: Same as above—no extra service; persistence across restarts.
- **File-based ML/RL**: Simple deployment; models can be replaced without schema changes.

### Why it is better than alternatives
- **vs in-memory only**: Data and models persist across restarts.
- **vs many separate DBs**: One relational DB + one vector DB + files keeps the stack minimal.

### Methods / Algorithms / Tools / Datasets
| Item | What |
|------|------|
| **Relational DB** | SQLite (pathfinder.db), SQLAlchemy 2, Alembic for migrations |
| **Vector DB** | ChromaDB, persisted under `CHROMA_DIR` |
| **Stored data** | Users, profiles, recruiters, jobs, roadmaps, job_interactions, reward_logs; RAG: job + roadmap text chunks |
| **Tools** | sqlalchemy, chromadb, python-dotenv, alembic |

---

## 11. End-to-End Flow (Brief)

1. **User** signs up, uploads resume (PDF/DOC) → **Gemini** extracts text and skills → stored in **UserProfile**.
2. **Career recommendations**: User skills → **MLB** encode → **KNN** → top-K careers from **career_reference** (from AI Career Recommendation dataset).
3. **Job matching**: Resume text (and DB jobs) → **Doc2Vec** vectors → **cosine similarity** (and optional skill match) → ranked jobs (from **formatted_jobs** and/or **SQLite jobs**).
4. **Roadmap**: Job + user profile → **Gemini** generates JSON roadmap; optionally **RL** suggests next action; user can **regenerate task** with feedback.
5. **RAG**: Jobs and roadmaps are **chunked and indexed** in **ChromaDB**; **Phase 2** `/rag/query` retrieves context for queries.
6. **RL**: User interactions (complete/skip/difficulty) → **reward** → **contextual bandit** updates θ and saves; `/recommend` returns next action.

---

## 12. Summary Table

| Component | What | Why used | Better than | Methods / Algo | Tools | Datasets |
|-----------|------|----------|-------------|----------------|-------|----------|
| **Frontend** | React SPA | Components, TypeScript, API integration | Plain HTML/JS, heavier frameworks | Client-side routing, REST consumption | React, Axios, React Router | — |
| **Backend** | FastAPI API | Async, docs, Python ML stack | Flask, Django, Node for ML | JWT auth, CRUD, orchestration | FastAPI, SQLAlchemy, Pydantic | — |
| **Resume / Skills** | LLM extraction | Handles unstructured resumes, JSON skills | Regex, commercial parsers | Prompted Gemini for text + skills | Gemini, PyPDF2 | — |
| **Career ML** | KNN recommender | Interpretable, skill-based similarity | Pure rules, heavy DL | KNN, Multi-Label Binarizer | sklearn, joblib | AI Career Recommendation (Kaggle) |
| **Job matcher** | Doc2Vec + cosine | Semantic match, hybrid with skills | Keyword only, TF-IDF only | Doc2Vec, cosine similarity, optional skill % | gensim, sklearn | Jobs & Skills Mapping (Kaggle) + DB jobs |
| **RAG** | Vector retrieval | Grounded answers from jobs/roadmaps | LLM-only, keyword search | Chunking, Gemini embeddings, similarity search | ChromaDB, Gemini | App data (jobs, roadmaps) |
| **Roadmap LLM** | Structured generation | Personalized, JSON roadmap + gap analysis | Static templates, rules | Single-shot prompt, JSON parse | Gemini | — |
| **RL** | Contextual bandit | Personalize next action from feedback | No adaptation, A/B only | Linear reward, ε-greedy, SGD update | numpy, pickle | User interaction logs |
| **Data** | SQLite + Chroma + files | Persistence, no extra servers | In-memory only, many DBs | Relational + vector + artifacts | SQLAlchemy, ChromaDB | — |

This is the full system design: what each part is, why it’s there, why it’s preferred, and what methods, algorithms, tools, and datasets power it.
