# PathFinder AI – Full RL (Reinforcement Learning) Explained

This document covers: **why** RL is used, **where** it is used, **which methods and models** are used, and **why a contextual bandit** is chosen over other approaches.

---

## 1. Why RL Is Used

### Problem
When a user follows a **learning roadmap** (phases and tasks for a job), we don’t know in advance:

- Whether to **recommend the next task** in order,
- **Insert a prerequisite** (easier task) if the user is struggling, or
- **Skip ahead** if the user already knows the material.

A **fixed** rule (e.g. always “next task”) doesn’t adapt to:
- User feedback: “too hard,” “skip,” “finished,” difficulty ratings.
- Different users: some need more prerequisites, some can skip.

### Role of RL
Reinforcement Learning is used to **learn from user actions** (complete, skip, difficulty 1–5) and **personalize** the next recommendation:

- **Exploit:** Use the action that has worked best so far for this kind of user (state).
- **Explore:** Sometimes try other actions (e.g. INSERT_PREREQUISITE) to discover what works.

So RL is used to **improve over time** which “next step” we suggest (recommend next, insert prerequisite, skip ahead) based on **rewards** derived from real interactions.

---

## 2. Where RL Is Used

### A. Roadmap generation (`job_roadmap.py`)

When a **personalized roadmap** is generated for a user and a job:

- The code calls `rl_service.get_recommendation(user_id, db=None)`.
- The returned **action** (e.g. RECOMMEND_NEXT, INSERT_PREREQUISITE, SKIP_AHEAD) and **explanation** are attached to the roadmap JSON as `rl_adaptation`:
  - `recommended_action`, `explanation`, `model_version: "v1_contextual_bandit"`.
- The frontend or downstream logic can use this to **order or suggest** tasks (e.g. “model suggests: recommend next” or “insert prerequisite”).

So RL is used **at roadmap generation time** to suggest how to adapt the flow for this user.

### B. Phase 2 API – log interaction and get recommendation

**1) Log interaction** – `POST /api/phase2/interactions/log`

- The frontend sends: `task_id`, `action_type` (start | complete | skip | rate_difficulty), optional `difficulty_rating` (1–5), `job_id`, `roadmap_id`, `duration_seconds`.
- Backend:
  - Saves a **JobInteraction** row (user_id, task_id, action_type, difficulty_rating, etc.).
  - Converts the interaction into a **reward**:
    - `complete` → +1.0  
    - `skip` → -0.5  
    - `difficulty_rating`: 1→-1.0, 2→-0.5, 3→0.1, 4→0.5, 5→1.0  
  - If reward ≠ 0, calls `rl_service.update_policy(user_id, "RECOMMEND_NEXT", reward, db)` so the **policy improves** from this feedback.

So RL is used **when the user interacts** with a task: we log the event and **update the bandit** with the computed reward.

**2) Get recommendation** – `GET /api/phase2/recommend`

- Returns the **current best action** (and explanation) for the logged-in user.
- Calls `rl_service.get_recommendation(current_user.id, db)`.
- Used when the app needs to know: “What should we recommend next for this user?” (e.g. next task, insert prerequisite, or skip ahead).

So RL is used **whenever the app needs a “next step” recommendation** for the current user.

### Summary of usage

| Where | What happens |
|-------|------------------|
| **Roadmap generation** | `get_recommendation()` → attach `rl_adaptation` to roadmap JSON so the UI can use the suggested action. |
| **POST /api/phase2/interactions/log** | Save interaction, compute reward, call `update_policy()` to learn from feedback. |
| **GET /api/phase2/recommend** | Return current recommended action for the user (for “what next?”). |

---

## 3. Methods and Models Used

### Model: Contextual bandit with linear reward

- **No neural network.** The “model” is a **weight matrix** `theta` of shape `(num_actions, state_dim)`.
- **Actions:** `["RECOMMEND_NEXT", "INSERT_PREREQUISITE", "SKIP_AHEAD"]` → 3 actions.
- **State:** 5-dimensional vector per user, built from **JobInteraction** history:
  - `avg_difficulty`: average difficulty_rating (1–5) normalized to [0,1] (e.g. /5).
  - `completion_rate`: fraction of interactions that are `action_type == "complete"`.
  - Three extra fixed values in the code: `0.1`, `0.5`, `1.0` (placeholders for future state features).
- **Expected reward** for action `a` in state `s`:  
  `Q(a, s) = theta[a] · s` (dot product).
- **Persistence:** `theta` is saved/loaded from disk as **`rl_model.pkl`** (path from `RL_MODEL_PATH`).

### Algorithm 1: Epsilon-greedy selection

- With probability **ε = 0.2**: choose an action **at random** (exploration).
- With probability **1 − ε**: choose the action with **highest** `Q(a, s)` (exploitation).
- So: **20% exploration**, **80% exploitation**.

### Algorithm 2: Policy update (SGD-style)

When we get a **reward** `r` for taking action `a` in state `s`:

- **Prediction:** `pred = theta[a] · s`
- **Error:** `error = r - pred`
- **Update:** `theta[a] += 0.1 * error * s`  
  (learning rate 0.1; same idea as stochastic gradient descent for linear prediction.)
- Then we **save** `theta` to `rl_model.pkl` and append a **RewardLog** row (user_id, reward_value, model_version, timestamp).

So the **methods** are:

- **Model:** Linear contextual bandit (one linear model per action).
- **Selection:** Epsilon-greedy.
- **Learning:** Incremental linear reward prediction update (SGD-style).

### Data used by RL

- **JobInteraction:** user_id, task_id, action_type (start/complete/skip/rate_difficulty), difficulty_rating (1–5), job_id, roadmap_id, duration_seconds, timestamp.
- **RewardLog:** user_id, reward_value, model_version, timestamp (audit trail of every reward used for updates).

---

## 4. Why Contextual Bandit Is Better Than Other Options

### What a contextual bandit is (short)

- **Context** = state (here: user state from interaction history).
- **Arms** = actions (RECOMMEND_NEXT, INSERT_PREREQUISITE, SKIP_AHEAD).
- Each round: see **context** → choose **one action** → get **one reward** (no long sequence of steps).
- Goal: learn a **policy** context → action that maximizes expected reward.

So we treat “what to recommend next” as **one-shot** decision per step, not a long-horizon MDP.

### Why contextual bandit vs other RL / non-RL options

| Alternative | Why contextual bandit is better (for this app) |
|-------------|-------------------------------------------------|
| **No personalization (fixed rule)** | Fixed rule (e.g. always “next task”) doesn’t adapt. Bandit uses state (e.g. difficulty, completion rate) to **choose different actions for different users**. |
| **Full MDP RL (e.g. DQN, PPO)** | Full RL needs many steps, careful reward design, and more data. Our problem is **one decision per interaction** (“what to recommend next”). Bandit fits that **single-step** setting with **less data and simpler tuning**. |
| **Multi-armed bandit without context** | Non-contextual bandit would learn one global “best” action for everyone. We want **per-user** adaptation (e.g. “this user finds things hard → insert prerequisite”). **Context** (state) allows that. |
| **A/B test only** | A/B gives a static winner. Bandit **continuously** updates from every user’s feedback and can **converge to a good policy** over time without running many fixed experiments. |
| **Complex model (e.g. deep RL)** | Deep RL needs more interactions and compute. Our **linear** bandit is **small data friendly**, **interpretable** (weights per state dimension), and **fast** to update and deploy. |

### Why this specific design (linear + epsilon-greedy + SGD)

- **Linear Q(a,s) = θ·s:** Simple, stable, works with limited interaction data; easy to debug (which state dimensions matter).
- **Epsilon-greedy:** Simple exploration; avoids getting stuck on one action early on.
- **SGD-style update:** Standard way to fit a linear predictor from (state, reward) pairs; no need for replay buffers or target networks.

---

## 5. End-to-End Flow (Recap)

1. **First time:** No `rl_model.pkl` → `theta` initialized randomly; recommendations are partly random (exploration).
2. **User gets roadmap:** Roadmap response includes `rl_adaptation.recommended_action` from `get_recommendation()`.
3. **User interacts:** Frontend calls `POST /api/phase2/interactions/log` with action_type and optional difficulty_rating.
4. **Backend:** Stores JobInteraction, maps to reward, calls `update_policy(user_id, "RECOMMEND_NEXT", reward, db)` → updates `theta`, saves model, logs reward.
5. **Next time:** `get_state(user_id)` uses updated JobInteraction history → new state → `get_recommendation()` returns action with higher expected reward for that state.

So: **RL is used to personalize “what to recommend next” (recommend next / insert prerequisite / skip ahead) using user interaction data, with a linear contextual bandit as the method and model.**
