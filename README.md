# PathFinder AI

## Run the project

**Backend (port 8001):**
```bash
cd backend
pip install -r requirements.txt
python -m uvicorn app.main:app --host 127.0.0.1 --port 8001 --reload
```

**Frontend (port 3000):** In a new terminal:
```bash
cd frontend
npm install
npm start
```

- App: http://localhost:3000  
- API: http://localhost:8001  
- API docs: http://localhost:8001/docs  

**Or use:** `start_all.bat` (Windows) to start both.

## Backend setup

- Copy `backend/.env.example` to `backend/.env` and set `GEMINI_API_KEY` if you use Gemini features.
- Database: SQLite at `backend/pathfinder.db` (created on first run).
- RAG vector store: `backend/chroma_db`. Seed with `python scripts/seed_rag.py` from `backend/`.

## Adaptive Roadmap Optimization using Constrained Contextual Bandit Learning

PathFinder uses a **constrained contextual bandit** (linear reward model per arm, **ε-greedy** exploration with ε = **0.15**), **not** full Markov decision-process or deep RL. Each step is one **masked** discrete action given a **10-D state vector** and optional **feedback type** (`complete`, `too_hard`, `too_easy`, `skip_regenerate`). That keeps learning sample-efficient and the roadmap **linear and phase-based**.

### Why a contextual bandit instead of full RL

Full RL fits long horizons and rich simulators. Here, adaptation is a **single local edit** to saved roadmap JSON with **immediate** feedback. A contextual bandit is the standard reduction: choose an arm (roadmap operation) from a **valid subset** conditioned on context, observe reward, update only that arm’s weights. **Action masking** encodes product rules (for example, never skip high–JD-importance tasks) so exploration stays safe.

### Why “Too Hard / Too Easy” instead of 1–5 ratings

Numeric difficulty ratings are ambiguous and feel like grading. Discrete intents (**Complete**, **Too Hard**, **Too Easy**, **Skip & Regenerate**) align with how learners actually behave and map cleanly to **constrained** action sets (for example, “too hard” never proposes `INCREASE_DIFFICULTY`). Legacy `rate_difficulty` with 1–5 is still accepted and mapped to `too_hard` / neutral / `too_easy` for older clients.

### State vector (10 dimensions)

Names (see `backend/app/services/rl/bandit.py`):

1. `phase_index_norm` — default **0.5** if unknown  
2. `task_index_norm` — default **0.5**  
3. `task_difficulty` — default **0.5**  
4. `recent_difficulty_feedback` — **0.2** (too hard), **0.5** (complete / neutral / skip-style), **0.8** (too easy); from recent `JobInteraction` history  
5. `skip_count_norm` — normalized skip / skip_regenerate counts  
6. `completion_count_norm`  
7. `regenerate_count_norm` — proxy from recent skips  
8. `jd_importance_score` — heuristic from task `jd_alignment`  
9. `user_skill_match_score` — profile overlap with task `skills_gained`  
10. `prerequisite_missing_score` — scope signal from task skills  

Missing roadmap fields fall back to safe defaults; handlers do not crash.

### Seven roadmap actions (bandit arms)

| Action | Role |
|--------|------|
| `KEEP_NEXT_TASK` | No structural change. |
| `ADD_PREREQUISITE_TASK` | Insert a simpler prerequisite before the current task (same phase). |
| `DECREASE_DIFFICULTY` | Rewrite/simplify the current task. |
| `INCREASE_DIFFICULTY` | Rewrite to a harder, more applied version. |
| `REPEAT_WITH_VARIATION` | Insert a similar practice task after the current one. |
| `REORDER_NEARBY_TASK` | Deterministic reorder within the phase (no Gemini). |
| `SKIP_OPTIONAL_TASK` | Mark optional skip only when JD emphasis is **low** (< **0.7**). |

### Constraints (action masking)

`get_valid_actions(feedback_type, state_vector, …)` in `bandit.py` builds the allowed set before ε-greedy selection—for example, **never** `SKIP_OPTIONAL_TASK` when `jd_importance_score ≥ 0.7`. The `/recommend` response includes **`valid_actions`** for transparency and tests.

### Rewards (credit assignment)

`POST /api/phase2/interactions/log` writes `JobInteraction`, computes reward, and attributes it to the latest **pending** `RoadmapBanditDecision` for the same user / roadmap / task when present; otherwise the policy update falls back to **`KEEP_NEXT_TASK`** without crashing. Special cases: completing after **`INCREASE_DIFFICULTY`** (+**1.2**), completing after **`SKIP_OPTIONAL_TASK`** (+**0.85**), deferred bonus for an older open skip-optional decision when the learner later completes progress with strong skill match, **`too_hard`** / **`skip_regenerate`** penalties with JD and repetition modifiers, and **`too_easy`** (**-0.3**) on the prior arm.

### Gemini’s role (not the policy)

**Gemini never chooses the RL action.** The bandit selects the arm; Gemini is invoked **only** inside `roadmap_adaptation.py` for arms that need new or rewritten task copy (`ADD_PREREQUISITE_TASK`, `DECREASE_DIFFICULTY`, `INCREASE_DIFFICULTY`, `REPEAT_WITH_VARIATION`). `KEEP_NEXT_TASK`, `REORDER_NEARBY_TASK`, and `SKIP_OPTIONAL_TASK` stay deterministic / metadata-only.

### API flow

1. **Feedback** — `POST /api/phase2/interactions/log` with `action_type` in `{ complete, too_hard, too_easy, skip_regenerate, … }`.  
2. **Recommend** — `GET /api/phase2/recommend?roadmap_id=&task_id=&feedback_type=` builds state, applies the mask, draws an arm, persists `RoadmapBanditDecision` (with optional `feedback_type`), returns **`selected_action`**, **`valid_actions`**, **`reason`**, **`state_vector`**, **`decision_id`**.  
3. **Adapt** — `POST /api/phase2/roadmap/adapt` with `{ roadmap_id, task_id, decision_id }` applies the stored action to `roadmap_data` (Gemini only when needed) and returns **`updated_roadmap`** and **`explanation`**.

The React roadmap detail page follows **recommend → adapt → log** so rewards credit the correct decision. **Complete** marks the task finished (no Gemini, no rewrite), shows a Completed badge, hides buttons, and opens the **next** task. Other feedback shows adaptation banner, RL action, and reason.

**Complete** never calls Gemini and never mutates the finished task. **Too Hard** adapts the current task (prerequisite, easier rewrite). **Too Easy** increases difficulty or adds an advanced follow-up. **Skip & Regenerate** marks the task skipped and adds an alternative (same phase when required; optional section when JD importance is low).

### Example

After **Too Hard**, the mask may allow `ADD_PREREQUISITE_TASK` or `DECREASE_DIFFICULTY`; the bandit picks one; Gemini (if configured) drafts prerequisite or easier task JSON; the API saves the roadmap locally.

**QA / debug:** When `ENVIRONMENT` is `development`/`test` or `ADAPTIVE_RL_DEBUG=true`, `GET /api/phase2/recommend` accepts `forced_action=…` (must still appear in `valid_actions` or it is merged for the debug run). Run `python scripts/e2e_adaptive_roadmap_flow.py` from `backend/`.

**RAG** remains optional for chat; it is not required for the bandit core.
