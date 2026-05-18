"""
Human-readable explanations for adaptive roadmap bandit actions (not model internals).
"""
from __future__ import annotations

from typing import Any, Mapping, Optional

_EXPLANATIONS: dict[str, str] = {
    "KEEP_NEXT_TASK": "Proceed to the next task without changing the task you just finished.",
    "ADD_PREREQUISITE_TASK": (
        "Inserted a prerequisite task so you can build foundations before the harder step."
    ),
    "DECREASE_DIFFICULTY": (
        "Simplified this task because feedback indicates it feels too difficult right now."
    ),
    "INCREASE_DIFFICULTY": (
        "Raised the challenge level because prior progress suggests you are ready for depth."
    ),
    "REPEAT_WITH_VARIATION": (
        "Added a similar practice task with a different scenario to reinforce the same skills."
    ),
    "REORDER_NEARBY_TASK": (
        "Reordered tasks in this phase so easier or prerequisite-like work comes first."
    ),
    "SKIP_OPTIONAL_TASK": (
        "Marked a low-priority optional task as skipped because your skill overlap is already strong."
    ),
}


def _float_state(state_vector: Optional[Mapping[str, Any]], key: str, default: float = 0.5) -> float:
    if not state_vector or key not in state_vector:
        return default
    try:
        return float(max(0.0, min(1.0, float(state_vector[key]))))
    except (TypeError, ValueError):
        return default


def explain_action(
    selected_action: str,
    state_vector: Optional[Mapping[str, Any]] = None,
    feedback_type: Optional[str] = None,
) -> str:
    """
    Short explanation for the UI. Uses coarse state hints when available.
    """
    base = _EXPLANATIONS.get(
        selected_action,
        "Adjusted the roadmap based on your learning signals.",
    )
    parts = [base]
    ft = (feedback_type or "").strip().lower()
    if ft == "skip":
        ft = "skip_regenerate"

    pm = _float_state(state_vector, "prerequisite_missing_score", 0.5)
    jd = _float_state(state_vector, "jd_importance_score", 0.5)
    um = _float_state(state_vector, "user_skill_match_score", 0.5)

    if selected_action == "ADD_PREREQUISITE_TASK" and pm >= 0.6:
        parts.append("Prerequisite scope is high relative to the role, so foundations were prioritized.")
    if selected_action == "SKIP_OPTIONAL_TASK" and jd < 0.7 and um >= 0.8:
        parts.append("JD emphasis for this task is moderate and your profile already overlaps the skills.")
    if ft == "too_hard" and selected_action == "DECREASE_DIFFICULTY":
        parts.append("This matches a “too hard” signal, so the plan eases the immediate workload.")
    if ft == "too_easy" and selected_action == "INCREASE_DIFFICULTY":
        parts.append("This matches a “too easy” signal, so the plan adds depth.")
    if ft == "complete":
        return "You finished this task. It was marked complete and was not rewritten."

    return " ".join(parts).strip()