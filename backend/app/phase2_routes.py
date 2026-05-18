from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.config import adaptive_rl_debug_enabled
from app.database import get_db
from app import schemas, auth, models
from app.services.rl.bandit import (
    ACTIONS as BANDIT_ACTIONS,
    STATE_FEATURE_NAMES,
    display_action,
    get_valid_actions,
    normalize_action,
)
from app.services.rl_service import rl_service
from app.services.rag_service import rag_service
from app.services.roadmap.roadmap_adaptation import apply_roadmap_action
from app.services.roadmap.roadmap_rl_explainer import explain_action

_ALLOWED_FORCED_ACTIONS = frozenset(BANDIT_ACTIONS)

router = APIRouter(prefix="/api/phase2", tags=["phase2"])

DEFAULT_BANDIT_ACTION = "KEEP_NEXT_TASK"

HIGH_JD_THRESHOLD = 0.7


def _normalized_skill_set(values: Optional[list]) -> set[str]:
    if not values:
        return set()
    out = set()
    for x in values:
        if x is None:
            continue
        s = str(x).strip().lower()
        if s:
            out.add(s)
    return out


def _user_skill_match_for_task_skills(db: Session, user_id: int, task_skills: list) -> float:
    """Overlap(user profile skills, task skills_gained) normalized to [0,1]; default 0.5."""
    ts = _normalized_skill_set(task_skills)
    if not ts:
        return 0.5
    prof = (
        db.query(models.UserProfile)
        .filter(models.UserProfile.user_id == user_id)
        .first()
    )
    pool: set[str] = set()
    if prof:
        for fld in (prof.skills, prof.extracted_skills):
            pool |= _normalized_skill_set(fld if isinstance(fld, list) else [])
    if not pool:
        return 0.35
    overlap = len(pool & ts)
    return float(min(1.0, max(0.0, overlap / len(ts))))


def _norm_task_id(task_id: Optional[str]) -> Optional[str]:
    if task_id is None:
        return None
    return str(task_id).strip() or None


def _roadmap_context_for_task(
    db: Session,
    user_id: int,
    roadmap_id: Optional[int],
    task_id: Optional[str],
) -> tuple[Optional[dict], Optional[int]]:
    tid = _norm_task_id(task_id)
    if roadmap_id is None or not tid:
        return None, None
    rm = (
        db.query(models.Roadmap)
        .filter(models.Roadmap.id == roadmap_id, models.Roadmap.user_id == user_id)
        .first()
    )
    if not rm or not rm.roadmap_data:
        return None, rm.job_id if rm else None
    data = rm.roadmap_data
    inner = data.get("roadmap") if isinstance(data.get("roadmap"), dict) else data
    phases = inner.get("phases") if isinstance(inner, dict) else None
    if not phases:
        return None, rm.job_id
    n_phases = len(phases)
    max_pi = float(max(n_phases - 1, 1))
    for pi, phase in enumerate(phases):
        tasks = phase.get("tasks") or []
        n_tasks = len(tasks)
        max_ti = float(max(n_tasks - 1, 1))
        for ti, task in enumerate(tasks):
            id_ok = tid == _norm_task_id(task.get("task_id"))
            title_ok = tid == _norm_task_id(task.get("title"))
            if id_ok or title_ok:
                ctx = {
                    "phase_index": float(pi),
                    "max_phase_index": max_pi,
                    "task_index": float(ti),
                    "max_task_index": max_ti,
                }
                td = task.get("difficulty") or task.get("task_difficulty")
                if td is not None:
                    try:
                        ctx["task_difficulty"] = float(td)
                    except (TypeError, ValueError):
                        pass
                ja = task.get("jd_alignment") or []
                if isinstance(ja, list):
                    ctx["jd_importance_score"] = float(
                        min(1.0, max(0.0, 0.15 + 0.17 * min(len(ja), 5)))
                    )
                sg = task.get("skills_gained") or []
                if isinstance(sg, list):
                    ctx["prerequisite_missing_score"] = float(
                        min(1.0, max(0.0, 0.4 + 0.06 * min(len(sg), 8)))
                    )
                    ctx["user_skill_match_score"] = _user_skill_match_for_task_skills(
                        db, user_id, sg
                    )
                else:
                    ctx.setdefault("user_skill_match_score", 0.5)
                return ctx, rm.job_id
    return None, rm.job_id


def _task_jd_importance(
    db: Session,
    user_id: int,
    roadmap_id: Optional[int],
    task_id: Optional[str],
) -> float:
    """Match heuristic used in roadmap_context jd_importance_score; safe default 0.5."""
    tid = _norm_task_id(task_id)
    if roadmap_id is None or not tid:
        return 0.5
    rm = (
        db.query(models.Roadmap)
        .filter(models.Roadmap.id == roadmap_id, models.Roadmap.user_id == user_id)
        .first()
    )
    if not rm or not rm.roadmap_data:
        return 0.5
    data = rm.roadmap_data
    inner = data.get("roadmap") if isinstance(data.get("roadmap"), dict) else data
    phases = inner.get("phases") if isinstance(inner, dict) else None
    if not phases:
        return 0.5
    for phase in phases:
        for task in phase.get("tasks") or []:
            id_ok = tid == _norm_task_id(task.get("task_id"))
            title_ok = tid == _norm_task_id(task.get("title"))
            if id_ok or title_ok:
                ja = task.get("jd_alignment") or []
                if isinstance(ja, list):
                    return float(min(1.0, max(0.0, 0.15 + 0.17 * min(len(ja), 5))))
                return 0.5
    return 0.5


def _prior_skip_regenerate_count(
    db: Session,
    user_id: int,
    roadmap_id: Optional[int],
    task_id: Optional[str],
) -> int:
    tid = _norm_task_id(task_id)
    if roadmap_id is None or not tid:
        return 0
    return (
        db.query(models.JobInteraction)
        .filter(
            models.JobInteraction.user_id == user_id,
            models.JobInteraction.roadmap_id == roadmap_id,
            models.JobInteraction.task_id == tid,
            models.JobInteraction.action_type.in_(["skip", "skip_regenerate"]),
        )
        .count()
    )


def _prior_too_hard_count(
    db: Session,
    user_id: int,
    roadmap_id: Optional[int],
    task_id: Optional[str],
) -> int:
    tid = _norm_task_id(task_id)
    if roadmap_id is None or not tid:
        return 0
    return (
        db.query(models.JobInteraction)
        .filter(
            models.JobInteraction.user_id == user_id,
            models.JobInteraction.roadmap_id == roadmap_id,
            models.JobInteraction.task_id == tid,
            models.JobInteraction.action_type == "too_hard",
        )
        .count()
    )


def _logical_action(request: schemas.InteractionLogRequest) -> str:
    at = request.action_type
    if at == "rate_difficulty" and request.difficulty_rating is not None:
        r = int(request.difficulty_rating)
        if r <= 2:
            return "too_hard"
        if r == 3:
            return "neutral"
        return "too_easy"
    if at == "skip":
        return "skip_regenerate"
    return at


def _storage_action_and_rating(
    request: schemas.InteractionLogRequest,
) -> tuple[str, Optional[int]]:
    at = request.action_type
    if at == "rate_difficulty" and request.difficulty_rating is not None:
        r = int(request.difficulty_rating)
        if r <= 2:
            return "too_hard", None
        if r == 3:
            return "rate_difficulty", 3
        return "too_easy", None
    if at == "skip":
        return "skip_regenerate", None
    return at, request.difficulty_rating


def _compute_reward(
    db: Session,
    user_id: int,
    request: schemas.InteractionLogRequest,
    logical: str,
    pending: Optional[models.RoadmapBanditDecision],
) -> float:
    if logical == "neutral":
        return 0.0

    jd_imp = _task_jd_importance(db, user_id, request.roadmap_id, request.task_id)
    tid = _norm_task_id(request.task_id)
    roadmap_id = request.roadmap_id

    if logical == "complete":
        if pending and pending.selected_action == "INCREASE_DIFFICULTY":
            return 1.2
        if pending and pending.selected_action == "SKIP_OPTIONAL_TASK":
            return 0.85
        return 1.3 if jd_imp >= HIGH_JD_THRESHOLD else 1.0

    if logical == "too_hard":
        prior_th = _prior_too_hard_count(db, user_id, roadmap_id, tid)
        if prior_th >= 1:
            return -1.1
        if jd_imp >= HIGH_JD_THRESHOLD:
            return -1.0
        return -0.8

    if logical == "too_easy":
        return -0.3

    if logical == "skip_regenerate":
        prior = _prior_skip_regenerate_count(db, user_id, roadmap_id, tid)
        if jd_imp >= HIGH_JD_THRESHOLD:
            return -1.2
        if prior >= 1:
            return -1.0
        return -0.6

    return 0.0


def _user_skill_from_state_vector(state_vector: object) -> float:
    if state_vector is None:
        return 0.5
    key = "user_skill_match_score"
    if isinstance(state_vector, dict):
        return float(state_vector.get(key, 0.5))
    if isinstance(state_vector, list) and len(state_vector) > 8:
        try:
            return float(state_vector[8])
        except (TypeError, ValueError):
            return 0.5
    return 0.5


def _maybe_credit_open_skip_optional_decision(
    db: Session,
    user_id: int,
    request: schemas.InteractionLogRequest,
    interaction_id: int,
) -> None:
    """Deferred positive credit for SKIP_OPTIONAL when learner later completes progress."""
    if request.roadmap_id is None:
        return
    cand = (
        db.query(models.RoadmapBanditDecision)
        .filter(
            models.RoadmapBanditDecision.user_id == user_id,
            models.RoadmapBanditDecision.roadmap_id == request.roadmap_id,
            models.RoadmapBanditDecision.selected_action == "SKIP_OPTIONAL_TASK",
            models.RoadmapBanditDecision.reward_value.is_(None),
        )
        .order_by(models.RoadmapBanditDecision.created_at.desc())
        .first()
    )
    if cand is None:
        return
    if _user_skill_from_state_vector(cand.state_vector) < 0.8:
        return
    bonus = 0.75
    cand.reward_value = bonus
    db.add(cand)
    db.commit()
    rl_service.update_policy(
        user_id,
        "SKIP_OPTIONAL_TASK",
        bonus,
        db,
        roadmap_context=None,
        state_vector=cand.state_vector,
        interaction_id=interaction_id,
    )


def _state_vector_dict(vec: list) -> dict[str, float]:
    n = min(len(vec), len(STATE_FEATURE_NAMES))
    return {STATE_FEATURE_NAMES[i]: float(vec[i]) for i in range(n)}


def _state_vector_as_mapping(state_vector: object) -> Optional[dict[str, float]]:
    if state_vector is None:
        return None
    if isinstance(state_vector, list):
        return _state_vector_dict(state_vector)
    if isinstance(state_vector, dict):
        return {str(k): float(v) for k, v in state_vector.items()}
    return None


def _find_pending_decision(
    db: Session,
    user_id: int,
    roadmap_id: Optional[int],
    task_id: Optional[str],
) -> Optional[models.RoadmapBanditDecision]:
    tid = _norm_task_id(task_id)
    if roadmap_id is None or not tid:
        return None
    return (
        db.query(models.RoadmapBanditDecision)
        .filter(
            models.RoadmapBanditDecision.user_id == user_id,
            models.RoadmapBanditDecision.roadmap_id == roadmap_id,
            models.RoadmapBanditDecision.task_id == tid,
            models.RoadmapBanditDecision.reward_value.is_(None),
        )
        .order_by(models.RoadmapBanditDecision.created_at.desc())
        .first()
    )


def _load_decision_for_adapt(
    db: Session,
    user_id: int,
    roadmap_id: int,
    task_id: str,
    decision_id: Optional[int],
) -> tuple[
    Optional[models.RoadmapBanditDecision],
    Optional[int],
    str,
    Optional[list],
    Optional[str],
]:
    """
    Returns (decision_row, decision_id, selected_action, state_vector, feedback_type).
    """
    tid = _norm_task_id(task_id)
    if not tid:
        raise HTTPException(status_code=400, detail="task_id is required")

    if decision_id is not None:
        d = (
            db.query(models.RoadmapBanditDecision)
            .filter(
                models.RoadmapBanditDecision.id == decision_id,
                models.RoadmapBanditDecision.user_id == user_id,
            )
            .first()
        )
        if d is None:
            raise HTTPException(status_code=404, detail="decision not found")
        if d.roadmap_id != roadmap_id or d.task_id != tid:
            raise HTTPException(
                status_code=400,
                detail="decision does not match roadmap_id / task_id",
            )
        return d, d.id, d.selected_action, d.state_vector, d.feedback_type

    d = _find_pending_decision(db, user_id, roadmap_id, task_id)
    if d is not None:
        return d, d.id, d.selected_action, d.state_vector, d.feedback_type
    return None, None, DEFAULT_BANDIT_ACTION, None, None


@router.post("/interactions/log")
def log_interaction(
    request: schemas.InteractionLogRequest,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    """
    Log roadmap task feedback. Maps legacy rate_difficulty / skip to new vocabulary.
    Attributes reward to the latest pending RoadmapBanditDecision when present.
    """
    pending = _find_pending_decision(db, current_user.id, request.roadmap_id, request.task_id)
    pending_action = pending.selected_action if pending else None
    logical = _logical_action(request)
    store_action, store_rating = _storage_action_and_rating(request)
    reward = _compute_reward(db, current_user.id, request, logical, pending)

    interaction = models.JobInteraction(
        user_id=current_user.id,
        job_id=request.job_id,
        roadmap_id=request.roadmap_id,
        task_id=request.task_id,
        action_type=store_action,
        difficulty_rating=store_rating,
        duration_seconds=request.duration_seconds,
    )
    db.add(interaction)
    db.commit()
    db.refresh(interaction)

    action_arm = DEFAULT_BANDIT_ACTION
    state_vec: Optional[list] = None
    if reward != 0.0:
        if pending:
            action_arm = pending.selected_action
            state_vec = pending.state_vector
            pending.reward_value = reward
            db.add(pending)
            db.commit()
        rl_service.update_policy(
            current_user.id,
            action_arm,
            reward,
            db,
            roadmap_context=None,
            state_vector=state_vec,
            interaction_id=interaction.id,
        )

    if logical == "complete" and pending_action not in ("INCREASE_DIFFICULTY", "SKIP_OPTIONAL_TASK"):
        _maybe_credit_open_skip_optional_decision(db, current_user.id, request, interaction.id)

    return {"status": "success", "reward_calculated": reward}


@router.get("/recommend", response_model=schemas.RecommendationResponse)
def get_recommendation(
    roadmap_id: Optional[int] = Query(None, description="Roadmap scope for state + decision row"),
    task_id: Optional[str] = Query(None, description="Task id within roadmap JSON"),
    job_id: Optional[int] = Query(None, description="Optional job id; defaults from roadmap if omitted"),
    feedback_type: Optional[str] = Query(
        None,
        description="User feedback driving action masking (complete, too_hard, too_easy, skip_regenerate)",
    ),
    forced_action: Optional[str] = Query(
        None,
        description="QA only: bypass bandit when adaptive debug is enabled (ENVIRONMENT dev/test or ADAPTIVE_RL_DEBUG=true)",
    ),
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    """
    Build contextual state, mask arms from feedback_type, epsilon-greedy choose,
    persist RoadmapBanditDecision with feedback_type.
    """
    roadmap_context, job_from_roadmap = _roadmap_context_for_task(
        db, current_user.id, roadmap_id, task_id
    )
    effective_job_id = job_id if job_id is not None else job_from_roadmap

    tid_q = _norm_task_id(task_id)
    state = rl_service.get_state(
        current_user.id,
        db,
        roadmap_context=roadmap_context,
        scope_task_id=tid_q,
        scope_roadmap_id=roadmap_id,
    )
    state_vec_dict = _state_vector_dict(state.tolist())
    ft_norm = _norm_feedback_type(feedback_type)
    valid_actions = get_valid_actions(ft_norm, state_vec_dict, task_context=roadmap_context)

    if forced_action is not None and str(forced_action).strip():
        fa = normalize_action(str(forced_action).strip())
        if not adaptive_rl_debug_enabled():
            raise HTTPException(
                status_code=403,
                detail="forced_action is only allowed when ENVIRONMENT is development/test or ADAPTIVE_RL_DEBUG=true",
            )
        if fa not in _ALLOWED_FORCED_ACTIONS:
            raise HTTPException(
                status_code=400,
                detail=f"invalid forced_action; allowed: {sorted(_ALLOWED_FORCED_ACTIONS)}",
            )
        if fa not in valid_actions:
            valid_actions = list(dict.fromkeys([*valid_actions, fa]))
        rec = {
            "action": fa,
            "explanation": f"Debug forced_action={fa} (constrained bandit bypass)",
            "context_task_id": tid_q,
        }
    else:
        rec = rl_service.get_recommendation(
            current_user.id,
            db,
            context_task_id=tid_q,
            roadmap_context=roadmap_context,
            valid_actions=valid_actions,
            scope_task_id=tid_q,
            scope_roadmap_id=roadmap_id,
        )

    action = rec["action"]
    if ft_norm == "complete":
        action = "KEEP_NEXT_TASK"
    decision = models.RoadmapBanditDecision(
        user_id=current_user.id,
        job_id=effective_job_id,
        roadmap_id=roadmap_id,
        task_id=tid_q,
        selected_action=action,
        feedback_type=ft_norm,
        state_vector=state.tolist(),
        reward_value=None,
    )
    db.add(decision)
    db.commit()
    db.refresh(decision)

    reason = explain_action(action, state_vec_dict, feedback_type=ft_norm)
    action_display = display_action(action, ft_norm)
    return {
        "action": action,
        "selected_action": action_display,
        "explanation": rec["explanation"],
        "reason": reason,
        "state_vector": state_vec_dict,
        "valid_actions": [display_action(a, ft_norm) for a in valid_actions],
        "feedback_type": ft_norm,
        "context_task_id": tid_q,
        "decision_id": decision.id,
    }


def _norm_feedback_type(ft: Optional[str]) -> Optional[str]:
    if ft is None or not str(ft).strip():
        return None
    s = str(ft).strip().lower()
    if s == "skip":
        return "skip_regenerate"
    return s


@router.post(
    "/roadmap/adapt",
    response_model=schemas.RoadmapAdaptResponse,
)
def apply_roadmap_adaptation(
    body: schemas.RoadmapAdaptRequest,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    """
    Apply a persisted bandit decision to roadmap_data (no new RL call).
    Prefer decision_id from /recommend for deterministic credit assignment.
    """
    roadmap = (
        db.query(models.Roadmap)
        .filter(
            models.Roadmap.id == body.roadmap_id,
            models.Roadmap.user_id == current_user.id,
        )
        .first()
    )
    if roadmap is None:
        raise HTTPException(status_code=404, detail="Roadmap not found")

    if not roadmap.roadmap_data:
        raise HTTPException(status_code=400, detail="Roadmap has no roadmap_data")

    _, resp_decision_id, selected_action, state_vector, decision_ft = _load_decision_for_adapt(
        db,
        current_user.id,
        body.roadmap_id,
        body.task_id,
        body.decision_id,
    )

    ft = _norm_feedback_type(decision_ft)
    action_internal = "KEEP_NEXT_TASK" if ft == "complete" else normalize_action(selected_action)

    sv_dict = _state_vector_as_mapping(state_vector)

    result = apply_roadmap_action(
        roadmap.roadmap_data,
        body.task_id,
        action_internal,
        state_vector=state_vector,
        user_context=None,
        feedback_type=ft,
    )

    if result.get("applied"):
        roadmap.roadmap_data = result["updated_roadmap"]
        flag_modified(roadmap, "roadmap_data")
        db.commit()
        db.refresh(roadmap)

    internal_action = result.get("selected_action", action_internal)
    if ft == "complete":
        rl_expl = "Task marked complete. The finished task was not rewritten."
        explanation_out = f"{rl_expl} {result.get('message', '')}".strip()
    else:
        rl_expl = explain_action(internal_action, sv_dict, feedback_type=ft)
        detail_msg = result.get("message", "").strip()
        explanation_out = f"{rl_expl} {detail_msg}".strip()

    return {
        "selected_action": display_action(internal_action, ft),
        "feedback_type": ft,
        "applied": bool(result.get("applied")),
        "message": result.get("message", ""),
        "explanation": explanation_out,
        "updated_roadmap": result["updated_roadmap"],
        "decision_id": resp_decision_id,
        "next_task_id": result.get("next_task_id"),
    }


@router.post("/rag/query")
def query_rag_context(
    query: str,
    top_k: int = 3,
    current_user: models.User = Depends(auth.get_current_user),
):
    """
    Retrieve relevant context using RAG (ChromaDB + Gemini).
    """
    results = rag_service.retrieve_context(query, n_results=top_k)
    return {"results": results}
