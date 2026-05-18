"""
Apply contextual bandit actions to saved roadmap_data (JSON) with optional Gemini rewrites.
Does not regenerate the full roadmap; phases stay linear. No quiz/video/course content.
"""
from __future__ import annotations

import copy
import json
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from app.config import GEMINI_API_KEY
from app.services.llm.gemini_client import generate_with_fallback
from app.services.rl.bandit import ACTIONS, LEGACY_ACTION_MAP, normalize_action

_DEFAULT_STATUS = ["start", "already_know", "need_easier", "skip", "finished"]
_EASIER_KEYWORDS = (
    "intro",
    "introduction",
    "fundamental",
    "fundamentals",
    "basic",
    "basics",
    "foundation",
    "prerequisite",
    "overview",
    "getting started",
)


def _jd_importance_from_state(state_vector: Any) -> float:
    if state_vector is None:
        return 0.5
    try:
        sv = list(state_vector)
        if len(sv) > 7:
            return float(max(0.0, min(1.0, float(sv[7]))))
    except (TypeError, ValueError, IndexError):
        pass
    return 0.5


def _unwrap_roadmap(rdata: dict[str, Any]) -> tuple[Optional[dict[str, Any]], Optional[list]]:
    """Return (inner roadmap dict with phases, phases list) or (None, None)."""
    if not rdata or not isinstance(rdata, dict):
        return None, None
    inner = rdata.get("roadmap")
    if isinstance(inner, dict):
        phases = inner.get("phases")
        if isinstance(phases, list):
            return inner, phases
    phases = rdata.get("phases")
    if isinstance(phases, list):
        return rdata, phases
    return None, None


def _norm_tid(tid: Optional[str]) -> str:
    if tid is None:
        return ""
    return str(tid).strip()


def _find_task_location(
    phases: list,
    task_id: str,
) -> Optional[tuple[int, int, dict[str, Any]]]:
    tid = _norm_tid(task_id)
    if not tid:
        return None
    for pi, phase in enumerate(phases):
        tasks = phase.get("tasks")
        if not isinstance(tasks, list):
            continue
        for ti, task in enumerate(tasks):
            if not isinstance(task, dict):
                continue
            cur = _norm_tid(task.get("task_id")) or _norm_tid(task.get("title"))
            if tid == cur or tid == _norm_tid(task.get("task_id")):
                return pi, ti, task
    return None


def _collect_task_ids(phases: list) -> set[str]:
    out: set[str] = set()
    for phase in phases:
        for task in phase.get("tasks") or []:
            if isinstance(task, dict):
                tid = _norm_tid(task.get("task_id"))
                if tid:
                    out.add(tid)
    return out


def _make_unique_task_id(prefix: str, existing: set[str]) -> str:
    for _ in range(12):
        cand = f"{prefix}_{uuid.uuid4().hex[:8]}"
        if cand not in existing:
            return cand
    return f"{prefix}_{uuid.uuid4().hex}"


def _ensure_task_shape(raw: dict[str, Any], task_id: str) -> dict[str, Any]:
    skills = raw.get("skills_gained")
    if not skills and raw.get("skill_tags"):
        skills = raw["skill_tags"]
    return {
        "task_id": task_id,
        "title": (raw.get("title") or "Learning task").strip(),
        "jd_alignment": list(raw.get("jd_alignment") or []),
        "description": (raw.get("description") or "").strip(),
        "status_options": list(raw.get("status_options") or _DEFAULT_STATUS),
        "subtasks": list(raw.get("subtasks") or []),
        "recommended_courses": [],
        "recommended_projects": [],
        "skills_gained": list(skills or []),
    }


def _extract_json_object(text: str) -> dict[str, Any]:
    if not text:
        raise ValueError("Empty model response")
    t = text.strip().replace("```json", "").replace("```", "").strip()
    m = re.search(r"\{.*\}", t, re.DOTALL)
    if m:
        t = m.group(0)
    return json.loads(t)


def _gemini_json(prompt: str, temperature: float = 0.45) -> dict[str, Any]:
    if not GEMINI_API_KEY:
        raise RuntimeError("Gemini API not configured. Set GEMINI_API_KEY.")
    response = generate_with_fallback(prompt, temperature=temperature)
    if not response or not response.text:
        raise RuntimeError("Empty response from Gemini")
    return _extract_json_object(response.text)


def _user_context_snippet(user_context: Optional[dict[str, Any]]) -> str:
    if not user_context:
        return ""
    parts = []
    if user_context.get("name"):
        parts.append(f"Learner: {user_context['name']}")
    if user_context.get("target_role"):
        parts.append(f"Target role: {user_context['target_role']}")
    if user_context.get("technical_skills"):
        ts = user_context["technical_skills"]
        if isinstance(ts, list):
            parts.append("Skills: " + ", ".join(str(x) for x in ts[:25]))
    if user_context.get("jd_excerpt"):
        parts.append("JD excerpt:\n" + str(user_context["jd_excerpt"])[:1200])
    return "\n".join(parts)


def _easiness_rank(task: dict[str, Any]) -> tuple:
    title = (task.get("title") or "").lower()
    score = sum(1 for k in _EASIER_KEYWORDS if k in title)
    n_sub = len(task.get("subtasks") or [])
    return (-score, n_sub, title)


def _norm_feedback(ft: Optional[str]) -> str:
    s = (ft or "").strip().lower()
    return "skip_regenerate" if s == "skip" else s


def _is_task_done(task: dict[str, Any]) -> bool:
    return bool(task.get("completed")) or (task.get("status") or "").lower() == "completed"


def _is_task_skipped(task: dict[str, Any]) -> bool:
    st = (task.get("status") or "").lower()
    return bool(task.get("skipped")) or st == "skipped" or bool(task.get("skipped_optional"))


def _mark_skipped(task_ref: dict[str, Any], optional: bool = False) -> None:
    task_ref["skipped"] = True
    task_ref["status"] = "skipped"
    if optional:
        task_ref["skipped_optional"] = True


def _mark_completed(task_ref: dict[str, Any]) -> None:
    task_ref["completed"] = True
    task_ref["status"] = "completed"
    task_ref["completed_at"] = datetime.now(timezone.utc).isoformat()


def _find_next_task_id(phases: list, phase_idx: int, task_idx: int) -> Optional[str]:
    phase = phases[phase_idx]
    tasks = phase.get("tasks") or []
    for j in range(task_idx + 1, len(tasks)):
        t = tasks[j]
        if not isinstance(t, dict):
            continue
        if _is_task_done(t) or _is_task_skipped(t):
            continue
        tid = _norm_tid(t.get("task_id")) or _norm_tid(t.get("title"))
        if tid:
            return tid
    for pi in range(phase_idx + 1, len(phases)):
        for t in phases[pi].get("tasks") or []:
            if not isinstance(t, dict):
                continue
            if _is_task_done(t) or _is_task_skipped(t):
                continue
            tid = _norm_tid(t.get("task_id")) or _norm_tid(t.get("title"))
            if tid:
                return tid
    return None


def _apply_complete(
    roadmap_data: dict[str, Any],
    task_id: str,
) -> dict[str, Any]:
    data = copy.deepcopy(roadmap_data)
    inner, phases = _unwrap_roadmap(data)
    if inner is None or phases is None:
        return {
            "updated_roadmap": data,
            "applied": False,
            "selected_action": "KEEP_NEXT_TASK",
            "message": "Invalid roadmap_data: missing roadmap.phases",
            "changed_task_id": None,
            "inserted_task_id": None,
            "next_task_id": None,
        }
    loc = _find_task_location(phases, task_id)
    if loc is None:
        return {
            "updated_roadmap": data,
            "applied": False,
            "selected_action": "KEEP_NEXT_TASK",
            "message": f"Task not found for task_id={task_id!r}",
            "changed_task_id": None,
            "inserted_task_id": None,
            "next_task_id": None,
        }
    pi, ti, task_ref = loc
    if _is_task_done(task_ref):
        next_id = _find_next_task_id(phases, pi, ti)
        return {
            "updated_roadmap": data,
            "applied": True,
            "selected_action": "KEEP_NEXT_TASK",
            "message": "Task already completed.",
            "changed_task_id": _norm_tid(task_ref.get("task_id")),
            "inserted_task_id": None,
            "next_task_id": next_id,
        }
    _mark_completed(task_ref)
    next_id = _find_next_task_id(phases, pi, ti)
    return {
        "updated_roadmap": data,
        "applied": True,
        "selected_action": "KEEP_NEXT_TASK",
        "message": "Task marked complete; proceed to the next task.",
        "changed_task_id": _norm_tid(task_ref.get("task_id")),
        "inserted_task_id": None,
        "next_task_id": next_id,
    }


def apply_roadmap_action(
    roadmap_data: dict[str, Any],
    task_id: str,
    selected_action: str,
    state_vector: Any = None,
    user_context: Optional[dict[str, Any]] = None,
    feedback_type: Optional[str] = None,
) -> dict[str, Any]:
    """
    Mutate a copy of roadmap_data according to the bandit action (Gemini only rewrites text).

    Returns:
      updated_roadmap, applied, selected_action, message,
      changed_task_id, inserted_task_id, next_task_id
    """
    ft = _norm_feedback(feedback_type)
    if ft == "complete":
        return _apply_complete(roadmap_data, task_id)

    action = normalize_action(selected_action)
    if action not in ACTIONS:
        return {
            "updated_roadmap": roadmap_data,
            "applied": False,
            "selected_action": selected_action,
            "message": f"Unknown action: {selected_action}",
            "changed_task_id": None,
            "inserted_task_id": None,
            "next_task_id": None,
        }

    inner, phases = _unwrap_roadmap(roadmap_data)
    if inner is None or phases is None:
        return {
            "updated_roadmap": roadmap_data,
            "applied": False,
            "selected_action": action,
            "message": "Invalid roadmap_data: missing roadmap.phases",
            "changed_task_id": None,
            "inserted_task_id": None,
            "next_task_id": None,
        }

    loc = _find_task_location(phases, task_id)
    if loc is None:
        return {
            "updated_roadmap": copy.deepcopy(roadmap_data),
            "applied": False,
            "selected_action": action,
            "message": f"Task not found for task_id={task_id!r}",
            "changed_task_id": None,
            "inserted_task_id": None,
            "next_task_id": None,
        }

    _pi, _ti, target_task = loc
    if _is_task_done(target_task) and ft != "skip_regenerate":
        return {
            "updated_roadmap": copy.deepcopy(roadmap_data),
            "applied": False,
            "selected_action": action,
            "message": "Cannot adapt a completed task.",
            "changed_task_id": _norm_tid(target_task.get("task_id")),
            "inserted_task_id": None,
            "next_task_id": _find_next_task_id(phases, _pi, _ti),
        }

    changed_id: Optional[str] = _norm_tid(target_task.get("task_id")) or None
    inserted_id: Optional[str] = None

    if action == "KEEP_NEXT_TASK":
        return {
            "updated_roadmap": copy.deepcopy(roadmap_data),
            "applied": True,
            "selected_action": action,
            "message": "No structural change (keep next task).",
            "changed_task_id": changed_id,
            "inserted_task_id": None,
            "next_task_id": None,
        }

    data = copy.deepcopy(roadmap_data)
    _, phases_m = _unwrap_roadmap(data)
    assert phases_m is not None
    loc2 = _find_task_location(phases_m, task_id)
    if loc2 is None:
        return {
            "updated_roadmap": roadmap_data,
            "applied": False,
            "selected_action": action,
            "message": "Internal error: task lost after copy",
            "changed_task_id": None,
            "inserted_task_id": None,
            "next_task_id": None,
        }
    pi, ti, task_ref = loc2
    phase = phases_m[pi]
    tasks_m: list = phase.setdefault("tasks", [])
    inner_m, _ = _unwrap_roadmap(data)
    assert inner_m is not None

    existing_ids = _collect_task_ids(phases_m)
    uc = _user_context_snippet(user_context)
    jd_imp = _jd_importance_from_state(state_vector)

    try:
        if action == "SKIP_OPTIONAL_TASK":
            if ft == "skip_regenerate" and jd_imp < 0.7:
                _mark_skipped(task_ref, optional=True)
                prompt = f"""Return ONLY a single JSON object (no markdown). Keys: title, description (50-100 words), subtasks (array of strings), skill_tags (array of strings), jd_alignment (array of strings).
Create ONE alternative hands-on task for the same skills as the skipped task, suitable for optional practice later.
Reference title: {task_ref.get("title", "")}
{uc}
JSON object:"""
                raw = _gemini_json(prompt, temperature=0.55)
                nid = _make_unique_task_id("alt_opt", existing_ids)
                alt = _ensure_task_shape(raw, nid)
                alt["is_alternative"] = True
                alt["replaces_task_id"] = changed_id
                opts = inner_m.setdefault("optional_tasks", [])
                if not isinstance(opts, list):
                    opts = []
                    inner_m["optional_tasks"] = opts
                opts.append(alt)
                return {
                    "updated_roadmap": data,
                    "applied": True,
                    "selected_action": action,
                    "message": "Task marked skipped; alternative added to optional section.",
                    "changed_task_id": changed_id,
                    "inserted_task_id": nid,
                    "next_task_id": _find_next_task_id(phases_m, pi, ti),
                }
            if jd_imp >= 0.7:
                return {
                    "updated_roadmap": data,
                    "applied": False,
                    "selected_action": action,
                    "message": f"Cannot skip high-importance task without same-phase alternative (jd={jd_imp:.2f}).",
                    "changed_task_id": changed_id,
                    "inserted_task_id": None,
                    "next_task_id": None,
                }
            _mark_skipped(task_ref, optional=True)
            task_ref["adaptation_note"] = "Marked optional/skipped (low JD emphasis)."
            return {
                "updated_roadmap": data,
                "applied": True,
                "selected_action": action,
                "message": "Task marked as optional/skipped.",
                "changed_task_id": changed_id,
                "inserted_task_id": None,
                "next_task_id": _find_next_task_id(phases_m, pi, ti),
            }

        if action == "REORDER_NEARBY_TASK":
            pool = [t for t in tasks_m if isinstance(t, dict)]
            if len(pool) < 2:
                return {
                    "updated_roadmap": data,
                    "applied": False,
                    "selected_action": action,
                    "message": "Not enough tasks in phase to reorder.",
                    "changed_task_id": changed_id,
                    "inserted_task_id": None,
                    "next_task_id": None,
                }
            pool.sort(key=_easiness_rank)
            phase["tasks"] = pool
            return {
                "updated_roadmap": data,
                "applied": True,
                "selected_action": action,
                "message": "Reordered tasks within the phase (easier/prerequisite-like first).",
                "changed_task_id": changed_id,
                "inserted_task_id": None,
                "next_task_id": None,
            }

        if action == "ADD_PREREQUISITE_TASK":
            prompt = f"""Return ONLY a single JSON object (no markdown, no prose). Keys: title (string), description (string, 50-100 words), subtasks (array of short strings), skill_tags (array of strings), jd_alignment (array of short strings tying to job needs).
You suggest ONE easier prerequisite learning task that should be done immediately BEFORE this task in the same phase.
Do NOT include quizzes, videos, or external courses. Hands-on practice only.

Current task title: {task_ref.get("title", "")}
Current task description summary: {(task_ref.get("description") or "")[:800]}

{uc}

JSON object:"""
            raw = _gemini_json(prompt, temperature=0.45)
            nid = _make_unique_task_id("prereq", existing_ids)
            existing_ids.add(nid)
            new_task = _ensure_task_shape(raw, nid)
            tasks_m.insert(ti, new_task)
            inserted_id = nid
            return {
                "updated_roadmap": data,
                "applied": True,
                "selected_action": action,
                "message": "Inserted prerequisite task before the selected task.",
                "changed_task_id": changed_id,
                "inserted_task_id": inserted_id,
                "next_task_id": None,
            }

        if action == "DECREASE_DIFFICULTY":
            prompt = f"""Return ONLY a single JSON object (no markdown, no prose). Keys: title, description (50-100 words), subtasks (array of strings), jd_alignment (array of strings), skills_gained (array of strings).
Rewrite this learning task to be EASIER for the same learning goal. Split complex subtasks into smaller beginner-friendly steps.
No quizzes, videos, or course recommendations.

Task JSON summary:
title: {task_ref.get("title", "")}
description: {(task_ref.get("description") or "")[:1200]}
subtasks: {json.dumps(task_ref.get("subtasks") or [], ensure_ascii=False)}

{uc}
"""
            raw = _gemini_json(prompt, temperature=0.5)
            tid_keep = _norm_tid(task_ref.get("task_id")) or _make_unique_task_id("task", existing_ids)
            merged = _ensure_task_shape({**task_ref, **raw}, tid_keep)
            tasks_m[ti] = merged
            return {
                "updated_roadmap": data,
                "applied": True,
                "selected_action": action,
                "message": "Task rewritten to a simpler version with smaller subtasks.",
                "changed_task_id": tid_keep,
                "inserted_task_id": None,
                "next_task_id": None,
            }

        if action == "INCREASE_DIFFICULTY":
            prompt = f"""Return ONLY a single JSON object (no markdown, no prose). Keys: title, description (50-100 words), subtasks (array of strings), jd_alignment (array of strings), skills_gained (array of strings).
Rewrite this learning task to be MORE ADVANCED: add project, performance, deployment, or real-world challenge while keeping the same core skill goal.
No quizzes, videos, or course recommendations.

Task JSON summary:
title: {task_ref.get("title", "")}
description: {(task_ref.get("description") or "")[:1200]}
subtasks: {json.dumps(task_ref.get("subtasks") or [], ensure_ascii=False)}

{uc}
"""
            raw = _gemini_json(prompt, temperature=0.55)
            tid_keep = _norm_tid(task_ref.get("task_id")) or _make_unique_task_id("task", existing_ids)
            merged = _ensure_task_shape({**task_ref, **raw}, tid_keep)
            tasks_m[ti] = merged
            return {
                "updated_roadmap": data,
                "applied": True,
                "selected_action": action,
                "message": "Task rewritten to a more advanced version.",
                "changed_task_id": tid_keep,
                "inserted_task_id": None,
                "next_task_id": None,
            }

        if action == "REPEAT_WITH_VARIATION":
            if ft == "skip_regenerate":
                _mark_skipped(task_ref, optional=False)
                prompt = f"""Return ONLY a single JSON object (no markdown). Keys: title, description (50-100 words), subtasks (array of strings), skill_tags (array of strings), jd_alignment (array of strings).
Create ONE alternative hands-on task covering the SAME skills as the skipped task, different scenario. Required for job alignment — same learning phase.
Skipped task title: {task_ref.get("title", "")}
{uc}
JSON object:"""
                prefix = "alt"
            elif ft == "too_easy":
                prompt = f"""Return ONLY a single JSON object (no markdown). Keys: title, description (50-100 words), subtasks (array of strings), skill_tags (array of strings), jd_alignment (array of strings).
Create ONE ADVANCED follow-up task building on the reference task (harder project/deployment challenge). Insert after current task.
Reference:
title: {task_ref.get("title", "")}
description: {(task_ref.get("description") or "")[:1200]}
{uc}
JSON object:"""
                prefix = "advanced"
            else:
                prompt = f"""Return ONLY a single JSON object (no markdown). Keys: title, description (50-100 words), subtasks (array of strings), skill_tags (array of strings), jd_alignment (array of strings).
Create ONE additional practice task — same skills, different context. No quizzes or videos.
Reference:
title: {task_ref.get("title", "")}
description: {(task_ref.get("description") or "")[:1200]}
{uc}
JSON object:"""
                prefix = "practice"
            raw = _gemini_json(prompt, temperature=0.6)
            nid = _make_unique_task_id(prefix, existing_ids)
            new_task = _ensure_task_shape(raw, nid)
            if ft == "skip_regenerate":
                new_task["is_alternative"] = True
                new_task["replaces_task_id"] = changed_id
            insert_at = ti + 1
            tasks_m.insert(insert_at, new_task)
            inserted_id = nid
            msg = (
                "Skipped task; alternative inserted in same phase."
                if ft == "skip_regenerate"
                else (
                    "Advanced follow-up task inserted after current task."
                    if ft == "too_easy"
                    else "Inserted practice task after the selected task."
                )
            )
            return {
                "updated_roadmap": data,
                "applied": True,
                "selected_action": action,
                "message": msg,
                "changed_task_id": changed_id,
                "inserted_task_id": inserted_id,
                "next_task_id": _find_next_task_id(phases_m, pi, ti) if ft == "skip_regenerate" else None,
            }

    except Exception as e:
        return {
            "updated_roadmap": copy.deepcopy(roadmap_data),
            "applied": False,
            "selected_action": action,
            "message": f"Adaptation failed: {e}",
            "changed_task_id": changed_id,
            "inserted_task_id": inserted_id,
            "next_task_id": None,
        }

    raise RuntimeError(f"Adaptation internal error: action {action!r} not handled")
