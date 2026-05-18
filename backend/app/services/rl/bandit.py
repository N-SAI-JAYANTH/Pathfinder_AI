"""
RL (constrained contextual bandit): roadmap actions, epsilon-greedy over a masked
action set, linear SGD updates. Uses app.config for RL_MODEL_PATH.

State is 10-D; actions are 7 roadmap operations. Legacy arm names from older clients
are mapped to the new vocabulary for policy updates.
"""
from __future__ import annotations

import os
import pickle
import random
from datetime import datetime
from typing import Any, Mapping, Optional, Sequence, Union

import numpy as np
from sqlalchemy.orm import Session

from app.config import RL_MODEL_PATH
from app.models import JobInteraction, RewardLog

STATE_DIM = 10

# Ordered feature names (must match theta columns).
STATE_FEATURE_NAMES = (
    "phase_index_norm",
    "task_index_norm",
    "task_difficulty",
    "recent_difficulty_feedback",
    "skip_count_norm",
    "completion_count_norm",
    "regenerate_count_norm",
    "jd_importance_score",
    "user_skill_match_score",
    "prerequisite_missing_score",
)

ACTIONS: tuple[str, ...] = (
    "KEEP_NEXT_TASK",
    "ADD_PREREQUISITE_TASK",
    "DECREASE_DIFFICULTY",
    "INCREASE_DIFFICULTY",
    "REPEAT_WITH_VARIATION",
    "REORDER_NEARBY_TASK",
    "SKIP_OPTIONAL_TASK",
)

# Older API / stored values -> current arms (for update_policy & persisted logs).
LEGACY_ACTION_MAP: dict[str, str] = {
    "RECOMMEND_NEXT": "KEEP_NEXT_TASK",
    "INSERT_PREREQUISITE": "ADD_PREREQUISITE_TASK",
    "SKIP_AHEAD": "SKIP_OPTIONAL_TASK",
    # Clearer canonical names (API/docs) -> internal bandit arms
    "DECREASE_CURRENT_TASK_DIFFICULTY": "DECREASE_DIFFICULTY",
    "INCREASE_CURRENT_TASK_DIFFICULTY": "INCREASE_DIFFICULTY",
    "ADD_ADVANCED_FOLLOWUP_TASK": "REPEAT_WITH_VARIATION",
    "REORDER_PREREQUISITE_BEFORE_CURRENT": "REORDER_NEARBY_TASK",
    "ADD_ALTERNATIVE_TASK_SAME_PHASE": "REPEAT_WITH_VARIATION",
    "ADD_ALTERNATIVE_TASK_OPTIONAL_SECTION": "SKIP_OPTIONAL_TASK",
}

# Human-readable labels returned to the UI (internal arm -> display name).
ACTION_DISPLAY_NAMES: dict[str, str] = {
    "KEEP_NEXT_TASK": "KEEP_NEXT_TASK",
    "ADD_PREREQUISITE_TASK": "ADD_PREREQUISITE_TASK",
    "DECREASE_DIFFICULTY": "DECREASE_CURRENT_TASK_DIFFICULTY",
    "INCREASE_DIFFICULTY": "INCREASE_CURRENT_TASK_DIFFICULTY",
    "REPEAT_WITH_VARIATION": "ADD_ADVANCED_FOLLOWUP_TASK",
    "REORDER_NEARBY_TASK": "REORDER_PREREQUISITE_BEFORE_CURRENT",
    "SKIP_OPTIONAL_TASK": "SKIP_OPTIONAL_TASK",
}


def normalize_action(action: str) -> str:
    """Map legacy/canonical names to internal bandit arm ids."""
    a = (action or "").strip()
    if a in ACTIONS:
        return a
    return LEGACY_ACTION_MAP.get(a, "KEEP_NEXT_TASK")


def display_action(action: str, feedback_type: Optional[str] = None) -> str:
    """UI label; varies by feedback for REPEAT_WITH_VARIATION / SKIP_OPTIONAL_TASK."""
    internal = normalize_action(action)
    ft = (feedback_type or "").strip().lower()
    if ft == "skip":
        ft = "skip_regenerate"
    if internal == "REPEAT_WITH_VARIATION":
        if ft == "skip_regenerate":
            return "ADD_ALTERNATIVE_TASK_SAME_PHASE"
        if ft == "too_easy":
            return "ADD_ADVANCED_FOLLOWUP_TASK"
    if internal == "SKIP_OPTIONAL_TASK" and ft == "skip_regenerate":
        return "ADD_ALTERNATIVE_TASK_OPTIONAL_SECTION"
    return ACTION_DISPLAY_NAMES.get(internal, internal)


def _clamp01(x: float) -> float:
    return float(max(0.0, min(1.0, x)))


def _state_as_dict(
    state_vector: Optional[Union[Mapping[str, Any], Sequence[float], np.ndarray]],
) -> dict[str, float]:
    if state_vector is None:
        return {}
    if isinstance(state_vector, Mapping):
        return {str(k): float(v) for k, v in state_vector.items()}
    arr = np.asarray(state_vector, dtype=np.float64).reshape(-1)
    return {
        STATE_FEATURE_NAMES[i]: float(arr[i])
        for i in range(min(len(arr), len(STATE_FEATURE_NAMES)))
    }


def get_valid_actions(
    feedback_type: Optional[str],
    state_vector: Optional[Union[Mapping[str, Any], Sequence[float], np.ndarray]] = None,
    task_context: Optional[Mapping[str, Any]] = None,
) -> list[str]:
    """
    Mask invalid arms for the constrained contextual bandit (internal action ids).
    """
    _ = task_context
    ft_raw = (feedback_type or "").strip().lower()
    ft = "skip_regenerate" if ft_raw == "skip" else ft_raw
    s = _state_as_dict(state_vector)
    jd = _clamp01(float(s.get("jd_importance_score", 0.5)))
    um = _clamp01(float(s.get("user_skill_match_score", 0.5)))
    pm = _clamp01(float(s.get("prerequisite_missing_score", 0.5)))
    td = _clamp01(float(s.get("task_difficulty", 0.5)))

    def order_subset(subset: set[str]) -> list[str]:
        out = [a for a in ACTIONS if a in subset]
        return out if out else ["KEEP_NEXT_TASK"]

    if ft == "complete":
        return ["KEEP_NEXT_TASK"]

    if ft == "too_hard":
        valid = {
            "ADD_PREREQUISITE_TASK",
            "DECREASE_DIFFICULTY",
            "REORDER_NEARBY_TASK",
            "REPEAT_WITH_VARIATION",
        }
        return order_subset(valid)

    if ft == "too_easy":
        valid = {"INCREASE_DIFFICULTY", "KEEP_NEXT_TASK", "REPEAT_WITH_VARIATION"}
        if jd < 0.7 and um >= 0.8:
            valid.add("SKIP_OPTIONAL_TASK")
        return order_subset(valid)

    if ft == "skip_regenerate":
        valid = {
            "REPEAT_WITH_VARIATION",
            "DECREASE_DIFFICULTY",
            "ADD_PREREQUISITE_TASK",
            "REORDER_NEARBY_TASK",
        }
        if jd < 0.7:
            valid.add("SKIP_OPTIONAL_TASK")
        return order_subset(valid)

    base = set(ACTIONS)
    if jd >= 0.7:
        base.discard("SKIP_OPTIONAL_TASK")
    return order_subset(base)


def _interaction_difficulty_signal(i: JobInteraction) -> Optional[float]:
    at = (i.action_type or "").strip()
    if at == "too_hard":
        return 0.2
    if at == "too_easy":
        return 0.8
    if at == "complete":
        return 0.5
    if at in ("skip", "skip_regenerate"):
        return 0.5
    if at == "rate_difficulty" and i.difficulty_rating is not None:
        r = int(i.difficulty_rating)
        if r <= 2:
            return 0.2
        if r == 3:
            return 0.5
        return 0.8
    return None


def _norm_scope_tid(task_id: Optional[str]) -> str:
    if task_id is None:
        return ""
    return str(task_id).strip()


class RLService:
    def __init__(self, epsilon: float = 0.15, learning_rate: float = 0.1):
        self.epsilon = epsilon
        self.learning_rate = learning_rate
        self.actions = list(ACTIONS)
        self.model_path = RL_MODEL_PATH
        self.load_model()

    def load_model(self) -> None:
        try:
            if os.path.exists(self.model_path):
                with open(self.model_path, "rb") as f:
                    loaded = pickle.load(f)
                if isinstance(loaded, np.ndarray) and loaded.shape == (len(self.actions), STATE_DIM):
                    self.theta = loaded.astype(np.float64)
                    print(f"RL Model loaded from {self.model_path}")
                else:
                    print(
                        "RL checkpoint shape or type mismatch; initializing new weights "
                        f"(expected ({len(self.actions)}, {STATE_DIM}))."
                    )
                    self._init_theta()
            else:
                self._init_theta()
                print("No existing RL model found. Initializing new weights.")
        except Exception as e:
            print(f"Error loading RL model: {e}")
            self._init_theta()

    def _init_theta(self) -> None:
        rng = np.random.default_rng(42)
        self.theta = rng.random((len(self.actions), STATE_DIM)).astype(np.float64)

    def save_model(self) -> None:
        try:
            with open(self.model_path, "wb") as f:
                pickle.dump(self.theta, f)
            print(f"RL Model saved to {self.model_path}")
        except Exception as e:
            print(f"Error saving RL model: {e}")

    def _normalize_action(self, action: str) -> str:
        return normalize_action(action)

    def _default_state_vector(self) -> np.ndarray:
        """Neutral context when DB or roadmap context is unavailable."""
        return np.array(
            [
                0.5,  # phase_index_norm
                0.5,  # task_index_norm
                0.5,  # task_difficulty
                0.5,  # recent_difficulty_feedback
                0.0,  # skip_count_norm
                0.0,  # completion_count_norm
                0.0,  # regenerate_count_norm
                0.5,  # jd_importance_score
                0.5,  # user_skill_match_score
                0.5,  # prerequisite_missing_score
            ],
            dtype=np.float64,
        )

    def _stats_from_interactions(
        self,
        user_id: int,
        db: Session,
        scope_task_id: Optional[str] = None,
        scope_roadmap_id: Optional[int] = None,
    ) -> dict[str, float]:
        q = db.query(JobInteraction).filter(JobInteraction.user_id == user_id)
        if scope_roadmap_id is not None:
            q = q.filter(JobInteraction.roadmap_id == scope_roadmap_id)
        interactions = q.order_by(JobInteraction.timestamp.asc()).all()
        if not interactions:
            return {}

        def _last_difficulty_feedback(entries: Sequence[JobInteraction]) -> float:
            tail = list(entries)[-25:] if len(entries) > 25 else list(entries)
            for i in reversed(tail):
                sig = _interaction_difficulty_signal(i)
                if sig is not None:
                    return float(sig)
            return 0.5

        stid = _norm_scope_tid(scope_task_id)
        if stid:
            scoped = [i for i in interactions if _norm_scope_tid(i.task_id) == stid]
            count_pool = scoped
            recent = interactions[-15:] if len(interactions) > 15 else interactions
            recent_skips = sum(
                1
                for i in recent
                if i.action_type in ("skip", "skip_regenerate")
                and _norm_scope_tid(i.task_id) == stid
            )
            skips = sum(1 for i in count_pool if i.action_type in ("skip", "skip_regenerate"))
            completes = sum(1 for i in count_pool if i.action_type == "complete")
            rdf = _last_difficulty_feedback(scoped if scoped else interactions)
            return {
                "recent_difficulty_feedback": rdf,
                "skip_count_norm": _clamp01(skips / 10.0),
                "completion_count_norm": _clamp01(completes / 10.0),
                "regenerate_count_norm": _clamp01(recent_skips / 4.0),
            }

        recent = interactions[-15:] if len(interactions) > 15 else interactions
        skips = sum(1 for i in interactions if i.action_type in ("skip", "skip_regenerate"))
        completes = sum(1 for i in interactions if i.action_type == "complete")
        recent_skips = sum(1 for i in recent if i.action_type in ("skip", "skip_regenerate"))

        return {
            "recent_difficulty_feedback": _last_difficulty_feedback(interactions),
            "skip_count_norm": _clamp01(skips / 20.0),
            "completion_count_norm": _clamp01(completes / 25.0),
            "regenerate_count_norm": _clamp01(recent_skips / 5.0),
        }

    def _merge_roadmap_context(
        self,
        base: np.ndarray,
        roadmap_context: Optional[Mapping[str, Any]],
    ) -> np.ndarray:
        if not roadmap_context:
            return base
        out = base.copy()
        rc = dict(roadmap_context)

        max_phase = max(int(rc.get("max_phase_index", 1) or 1), 1)
        pidx = float(rc.get("phase_index", 0) or 0)
        out[0] = _clamp01(pidx / max_phase)

        max_task = max(int(rc.get("max_task_index", 1) or 1), 1)
        tidx = float(rc.get("task_index", 0) or 0)
        out[1] = _clamp01(tidx / max_task)

        td = rc.get("task_difficulty")
        if td is not None:
            out[2] = _clamp01(float(td))

        for i, key in enumerate(
            ("jd_importance_score", "user_skill_match_score", "prerequisite_missing_score"),
            start=7,
        ):
            val = rc.get(key)
            if val is not None:
                out[i] = _clamp01(float(val))

        return out

    def get_state(
        self,
        user_id: int,
        db: Optional[Session],
        roadmap_context: Optional[Mapping[str, Any]] = None,
        scope_task_id: Optional[str] = None,
        scope_roadmap_id: Optional[int] = None,
    ) -> np.ndarray:
        """
        Build a 10-D context vector. Uses JobInteraction history when db is provided;
        merges optional roadmap_context for phase/task/JD/skill features.
        When scope_task_id (+ optional scope_roadmap_id) is set, skip/completion/difficulty
        aggregates use interactions for that task (and roadmap) only.
        """
        base = self._default_state_vector()
        if db is None:
            return self._merge_roadmap_context(base, roadmap_context)

        stats = self._stats_from_interactions(
            user_id, db, scope_task_id=scope_task_id, scope_roadmap_id=scope_roadmap_id
        )
        if stats:
            base[3] = float(stats["recent_difficulty_feedback"])
            base[4] = float(stats["skip_count_norm"])
            base[5] = float(stats["completion_count_norm"])
            base[6] = float(stats["regenerate_count_norm"])

        return self._merge_roadmap_context(base, roadmap_context)

    def get_recommendation(
        self,
        user_id: int,
        db: Optional[Session],
        context_task_id: Optional[str] = None,
        roadmap_context: Optional[Mapping[str, Any]] = None,
        valid_actions: Optional[Sequence[str]] = None,
        scope_task_id: Optional[str] = None,
        scope_roadmap_id: Optional[int] = None,
    ) -> dict[str, Any]:
        """
        Epsilon-greedy: with probability epsilon explore over valid_actions;
        else exploit argmax_a theta[a] @ state.

        If valid_actions is None, all seven arms are eligible (execution layer may filter).
        """
        state = self.get_state(
            user_id,
            db,
            roadmap_context=roadmap_context,
            scope_task_id=scope_task_id,
            scope_roadmap_id=scope_roadmap_id,
        )
        arms = list(valid_actions) if valid_actions is not None else self.actions
        arms = [a for a in arms if a in self.actions]
        if not arms:
            arms = list(self.actions)

        if random.random() < self.epsilon:
            action = random.choice(arms)
            explanation = "Exploration (random valid action)"
        else:
            idxs = [self.actions.index(a) for a in arms]
            sub_theta = self.theta[idxs]
            expected = sub_theta @ state
            best_local = int(np.argmax(expected))
            action = arms[best_local]
            explanation = f"Exploit (linear score {expected[best_local]:.3f})"

        return {
            "action": action,
            "explanation": explanation,
            "context_task_id": context_task_id,
        }

    def update_policy(
        self,
        user_id: int,
        action: str,
        reward: float,
        db: Optional[Session],
        roadmap_context: Optional[Mapping[str, Any]] = None,
        state_vector: Optional[Union[Sequence[float], np.ndarray]] = None,
        interaction_id: Optional[int] = None,
    ) -> None:
        """
        Linear contextual bandit update for one arm; compatible with legacy action names.
        If state_vector is provided (e.g. from RoadmapBanditDecision), use it for the update
        so credit matches the context at decision time.
        """
        arm = self._normalize_action(action)
        if arm not in self.actions:
            arm = "KEEP_NEXT_TASK"

        if state_vector is not None:
            state = np.asarray(state_vector, dtype=np.float64).reshape(-1)
            if state.shape[0] != STATE_DIM:
                state = self.get_state(user_id, db, roadmap_context=roadmap_context)
        else:
            state = self.get_state(user_id, db, roadmap_context=roadmap_context)
        action_idx = self.actions.index(arm)
        prediction = float(np.dot(self.theta[action_idx], state))
        error = float(reward) - prediction
        self.theta[action_idx] += self.learning_rate * error * state

        if db is not None:
            db.add(
                RewardLog(
                    user_id=user_id,
                    interaction_id=interaction_id,
                    reward_value=reward,
                    model_version="v3_constrained_bandit_7x10",
                    timestamp=datetime.utcnow(),
                )
            )
            db.commit()
        self.save_model()


rl_service = RLService()
