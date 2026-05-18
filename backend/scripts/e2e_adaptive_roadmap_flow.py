"""
Adaptive roadmap E2E — constrained contextual bandit + optional Gemini.

Enable QA predictability:
  set ADAPTIVE_RL_DEBUG=true or ENVIRONMENT=test before importing the app.

Usage (from backend/):
  set ADAPTIVE_RL_DEBUG=true   # Windows PowerShell: $env:ADAPTIVE_RL_DEBUG=\"true\"
  python scripts/e2e_adaptive_roadmap_flow.py

Requires:
  - Seeded user test@example.com / password123
  - User profile (seed_full_profile.py), jobs (seed_rag.py)
  - GEMINI_API_KEY for Gemini-backed adapt steps

Writes scripts/e2e_adaptive_demo_snippets.json (compact task snapshots for screenshots).
"""
from __future__ import annotations

import copy
import json
import os
import sys
from pathlib import Path

os.environ["ADAPTIVE_RL_DEBUG"] = "true"

backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from fastapi.testclient import TestClient

from app.config import GEMINI_API_KEY, adaptive_rl_debug_enabled
from app.database import SessionLocal
from app.main import app
from app.models import Job, RewardLog, Roadmap, RoadmapBanditDecision
from app.services.rl.bandit import STATE_FEATURE_NAMES

SNIPPETS_OUTPUT = Path(__file__).resolve().parent / "e2e_adaptive_demo_snippets.json"

_demo_snippets: list[dict] = []

STUB_ROADMAP = {
    "role_summary": {
        "title": "E2E Engineer",
        "what_you_do": [],
        "required_stack": {
            "frontend": [],
            "backend": [],
            "ai_ml": [],
            "cloud_devops": [],
            "data": [],
            "nice_to_have": [],
        },
    },
    "gap_analysis": {
        "current_skills": [],
        "transferable_skills": [],
        "missing_skills": [],
        "summary": "E2E stub",
    },
    "roadmap": {
        "phases": [
            {
                "phase_id": 1,
                "phase_name": "Foundations",
                "goal": "Learn core skills",
                "estimated_duration_weeks": 4,
                "tasks": [
                    {
                        "task_id": "task_1",
                        "title": "Build a REST API module",
                        "jd_alignment": ["Backend APIs"],
                        "description": "Implement a small REST service with routing, validation, and tests. "
                        * 10,
                        "status_options": [
                            "start",
                            "already_know",
                            "need_easier",
                            "skip",
                            "finished",
                        ],
                        "subtasks": ["Define routes", "Add persistence layer"],
                        "recommended_courses": [],
                        "recommended_projects": [],
                        "skills_gained": ["REST", "Python"],
                    },
                    {
                        "task_id": "task_2",
                        "title": "Deploy service basics",
                        "jd_alignment": ["DevOps"],
                        "description": "Package and deploy the API with env config and health checks. " * 8,
                        "status_options": [
                            "start",
                            "already_know",
                            "need_easier",
                            "skip",
                            "finished",
                        ],
                        "subtasks": ["Dockerfile", "Health endpoint"],
                        "recommended_courses": [],
                        "recommended_projects": [],
                        "skills_gained": ["Docker"],
                    },
                ],
            }
        ]
    },
}


def phase_task_summary(roadmap_data: dict) -> list[str]:
    out = []
    phases = roadmap_data.get("roadmap", {}).get("phases") or []
    for pi, ph in enumerate(phases):
        for t in ph.get("tasks") or []:
            tid = t.get("task_id") or t.get("title")
            title = (t.get("title") or "")[:48]
            out.append(f"  P{pi + 1} {tid!r}: {title}")
    return out


def print_tasks(label: str, roadmap_data: dict) -> None:
    print(f"[TASKS] {label}")
    for line in phase_task_summary(roadmap_data):
        print(line)


def compact_tasks_snapshot(roadmap_data: dict, desc_preview_len: int = 180) -> dict:
    phases = roadmap_data.get("roadmap", {}).get("phases") or []
    out_phases: list[dict] = []
    for ph in phases:
        tasks_out: list[dict] = []
        for t in ph.get("tasks") or []:
            raw_desc = t.get("description") or ""
            prev = raw_desc[:desc_preview_len]
            if len(raw_desc) > desc_preview_len:
                prev += "..."
            tasks_out.append(
                {
                    "task_id": t.get("task_id"),
                    "title": t.get("title"),
                    "description_preview": prev,
                    "subtasks": t.get("subtasks"),
                    "jd_alignment": t.get("jd_alignment"),
                }
            )
        out_phases.append(
            {
                "phase_id": ph.get("phase_id"),
                "phase_name": ph.get("phase_name"),
                "tasks": tasks_out,
            }
        )
    return {"roadmap": {"phases": out_phases}}


def print_demo_snippet_banner(label: str, phase: str, payload: dict) -> None:
    print(f"\n----- DEMO SNIPPET ({phase}) | {label} -----")
    print(json.dumps(payload, indent=2, ensure_ascii=True))


def append_demo_record(label: str, before_rd: dict, after_rd: dict) -> None:
    rec = {
        "label": label,
        "before": compact_tasks_snapshot(before_rd),
        "after": compact_tasks_snapshot(after_rd),
    }
    _demo_snippets.append(rec)
    print_demo_snippet_banner(label, "before", rec["before"])
    print_demo_snippet_banner(label, "after", rec["after"])


def assert_recommend_response_fields(body: dict) -> None:
    assert isinstance(body.get("reason"), str) and body["reason"].strip(), (
        "recommend response must include non-empty reason"
    )
    sv = body.get("state_vector")
    assert isinstance(sv, dict) and sv, "recommend response must include non-empty state_vector dict"
    for name in STATE_FEATURE_NAMES:
        assert name in sv, f"state_vector missing key {name!r}"
    assert isinstance(body.get("selected_action"), str) and body["selected_action"].strip()
    assert isinstance(body.get("valid_actions"), list) and body["valid_actions"], "valid_actions required"
    assert body["selected_action"] in body["valid_actions"], (
        f"selected_action {body['selected_action']!r} not in valid_actions"
    )


def assert_adapt_response_fields(body: dict) -> None:
    assert isinstance(body.get("explanation"), str) and body["explanation"].strip(), (
        "adapt response must include non-empty explanation"
    )
    sa = body.get("selected_action")
    assert isinstance(sa, str) and sa.strip(), "adapt response must include non-empty selected_action"
    assert isinstance(body.get("updated_roadmap"), dict), "adapt must return updated_roadmap dict"


def find_task_in_roadmap(roadmap_data: dict, task_id: str) -> dict | None:
    phases = roadmap_data.get("roadmap", {}).get("phases") or []
    tid = str(task_id).strip()
    for ph in phases:
        for t in ph.get("tasks") or []:
            if str(t.get("task_id") or "").strip() == tid or str(t.get("title") or "").strip() == tid:
                return t
    return None


def gemini_configured() -> bool:
    return bool(GEMINI_API_KEY and str(GEMINI_API_KEY).strip())


def save_roadmap(client, headers, job_id: int, suffix: str) -> int:
    payload = copy.deepcopy(STUB_ROADMAP)
    sv = client.post(
        "/api/roadmaps/save",
        headers=headers,
        json={
            "roadmap_data": payload,
            "title": f"E2E forced {suffix}",
            "job_id": job_id,
            "roadmap_type": "job",
        },
    )
    assert sv.status_code == 200, sv.text
    return sv.json()["id"]


def run_forced_flow(
    client: TestClient,
    headers: dict,
    user_id: int,
    job_id: int,
    forced_action: str,
    label: str,
    feedback_type: str,
) -> None:
    print(f"\n========== Forced: {forced_action} ({label}) | feedback={feedback_type} ==========")
    rid = save_roadmap(client, headers, job_id, label)
    task_id = "task_1"

    db = SessionLocal()
    try:
        rm = db.query(Roadmap).filter(Roadmap.id == rid).first()
        before_rd = copy.deepcopy(rm.roadmap_data)
        print_tasks("BEFORE adapt", rm.roadmap_data)
    finally:
        db.close()

    task_before = find_task_in_roadmap(before_rd, task_id)
    desc_before = (task_before or {}).get("description") or ""
    sub_before = (task_before or {}).get("subtasks")

    rec = client.get(
        "/api/phase2/recommend",
        headers=headers,
        params={
            "roadmap_id": rid,
            "task_id": task_id,
            "job_id": job_id,
            "feedback_type": feedback_type,
            "forced_action": forced_action,
        },
    )
    assert rec.status_code == 200, rec.text
    rec_body = rec.json()
    assert_recommend_response_fields(rec_body)
    decision_id = rec_body["decision_id"]
    assert rec_body["selected_action"] == forced_action
    assert forced_action in rec_body["valid_actions"], rec_body["valid_actions"]
    print("[OK] recommend: selected_action, reason, state_vector, valid_actions")

    db = SessionLocal()
    try:
        d = db.query(RoadmapBanditDecision).filter(RoadmapBanditDecision.id == decision_id).first()
        assert d is not None and d.reward_value is None
        assert d.selected_action == forced_action
        print(f"[OK] RoadmapBanditDecision id={decision_id} feedback_type={d.feedback_type!r}")
    finally:
        db.close()

    log_payload = {
        "task_id": task_id,
        "roadmap_id": rid,
        "job_id": job_id,
        "action_type": (
            "too_hard"
            if feedback_type == "too_hard"
            else (
                "too_easy"
                if feedback_type == "too_easy"
                else ("complete" if feedback_type == "complete" else "skip_regenerate")
            )
        ),
    }
    rate = client.post("/api/phase2/interactions/log", headers=headers, json=log_payload)
    assert rate.status_code == 200, rate.text
    rew = rate.json().get("reward_calculated")
    print(f"[OK] log reward_calculated={rew}")

    db = SessionLocal()
    try:
        d = db.query(RoadmapBanditDecision).filter(RoadmapBanditDecision.id == decision_id).first()
        assert d.reward_value is not None
        print(f"[OK] decision.reward_value set -> {d.reward_value}")
    finally:
        db.close()

    adapt = client.post(
        "/api/phase2/roadmap/adapt",
        headers=headers,
        json={
            "roadmap_id": rid,
            "task_id": task_id,
            "decision_id": decision_id,
        },
    )
    assert adapt.status_code == 200, adapt.text
    ar = adapt.json()
    assert_adapt_response_fields(ar)
    print(
        f"[OK] adapt applied={ar['applied']} selected_action={ar['selected_action']!r} "
        f"message={ar['message']!r}"
    )

    append_demo_record(f"forced_{label}", before_rd, ar["updated_roadmap"])

    db = SessionLocal()
    try:
        rm = db.query(Roadmap).filter(Roadmap.id == rid).first()
        db.refresh(rm)
        print_tasks("AFTER adapt", rm.roadmap_data)
    finally:
        db.close()

    updated = ar["updated_roadmap"]
    phase_tasks = updated["roadmap"]["phases"][0]["tasks"]
    tids = [t.get("task_id") for t in phase_tasks]

    g_ok = gemini_configured()

    if forced_action == "ADD_PREREQUISITE_TASK":
        if ar["applied"]:
            assert any(str(x).startswith("prereq_") for x in tids if x) or len(phase_tasks) >= 3, (
                "ADD_PREREQUISITE applied but no prereq_* id and task count unchanged"
            )
            print("[CHECK] ADD_PREREQUISITE: new task present")
            if g_ok:
                assert any(str(x).startswith("prereq_") for x in tids if x), (
                    "Gemini path: expected task_id starting with prereq_"
                )
                print("[OK] Gemini validation: prereq_* task inserted")
        else:
            print("[WARN] ADD_PREREQUISITE not applied (Gemini missing?)")
            assert not g_ok, "GEMINI_API_KEY set but ADD_PREREQUISITE_TASK did not apply"

    elif forced_action == "DECREASE_DIFFICULTY":
        t1 = next((t for t in phase_tasks if t.get("task_id") == task_id), None)
        assert t1 is not None
        if ar["applied"]:
            print("[CHECK] DECREASE_DIFFICULTY: task_1 rewritten")
            if g_ok:
                t_after = find_task_in_roadmap(updated, task_id)
                assert t_after is not None
                changed = (t_after.get("description") != desc_before) or (
                    t_after.get("subtasks") != sub_before
                )
                assert changed, "Gemini path: DECREASE_DIFFICULTY should change description or subtasks"
                print("[OK] Gemini validation: task simplified (content changed)")
        else:
            print("[WARN] DECREASE_DIFFICULTY not applied (Gemini missing?)")
            assert not g_ok, "GEMINI_API_KEY set but DECREASE_DIFFICULTY did not apply"

    elif forced_action == "INCREASE_DIFFICULTY":
        t1 = next((t for t in phase_tasks if t.get("task_id") == task_id), None)
        assert t1 is not None
        if ar["applied"]:
            print("[CHECK] INCREASE_DIFFICULTY: task_1 rewritten")
            if g_ok:
                t_after = find_task_in_roadmap(updated, task_id)
                assert t_after is not None
                changed = (t_after.get("description") != desc_before) or (
                    t_after.get("subtasks") != sub_before
                )
                assert changed, "Gemini path: INCREASE_DIFFICULTY should change description or subtasks"
                print("[OK] Gemini validation: task advanced (content changed)")
        else:
            print("[WARN] INCREASE_DIFFICULTY not applied (Gemini missing?)")
            assert not g_ok, "GEMINI_API_KEY set but INCREASE_DIFFICULTY did not apply"

    complete_tid = phase_tasks[0]["task_id"]
    done = client.post(
        "/api/phase2/interactions/log",
        headers=headers,
        json={
            "task_id": complete_tid,
            "action_type": "complete",
            "roadmap_id": rid,
            "job_id": job_id,
        },
    )
    assert done.status_code == 200, done.text
    cr = done.json().get("reward_calculated")
    assert cr in (1.0, 1.3), f"complete reward expected 1.0 or 1.3, got {cr}"
    print(f"[OK] complete on {complete_tid!r} reward {cr}")

    db = SessionLocal()
    try:
        lr = (
            db.query(RewardLog)
            .filter(RewardLog.user_id == user_id)
            .order_by(RewardLog.timestamp.desc())
            .first()
        )
        assert lr is not None
        print(f"[OK] RewardLog reward_value={lr.reward_value}")
    finally:
        db.close()


def run_feedback_mask_checks(client: TestClient, headers: dict, job_id: int) -> None:
    """Validate valid_actions sets for each feedback_type (no forced_action)."""
    rid = save_roadmap(client, headers, job_id, "masks")
    task_id = "task_1"

    cases = [
        ("too_hard", ("ADD_PREREQUISITE_TASK", "DECREASE_CURRENT_TASK_DIFFICULTY")),
        ("too_easy", ("INCREASE_CURRENT_TASK_DIFFICULTY", "KEEP_NEXT_TASK", "ADD_ADVANCED_FOLLOWUP_TASK")),
        ("complete", ("KEEP_NEXT_TASK",)),
        ("skip_regenerate", ("ADD_ALTERNATIVE_TASK_SAME_PHASE", "DECREASE_CURRENT_TASK_DIFFICULTY")),
    ]
    for fb, must_include in cases:
        r = client.get(
            "/api/phase2/recommend",
            headers=headers,
            params={"roadmap_id": rid, "task_id": task_id, "job_id": job_id, "feedback_type": fb},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        va = body.get("valid_actions") or []
        for m in must_include:
            assert m in va, f"feedback={fb}: expected {m} in {va}"
        print(f"[OK] valid_actions for {fb}: {va}")


def run_complete_flow(client: TestClient, headers: dict, job_id: int) -> None:
    print("\n========== Complete flow ==========")
    rid = save_roadmap(client, headers, job_id, "complete")
    task_id = "task_1"

    rec = client.get(
        "/api/phase2/recommend",
        headers=headers,
        params={
            "roadmap_id": rid,
            "task_id": task_id,
            "job_id": job_id,
            "feedback_type": "complete",
        },
    )
    assert rec.status_code == 200, rec.text
    rec_body = rec.json()
    assert rec_body.get("selected_action") == "KEEP_NEXT_TASK"
    assert rec_body.get("valid_actions") == ["KEEP_NEXT_TASK"]
    decision_id = rec_body["decision_id"]

    adapt = client.post(
        "/api/phase2/roadmap/adapt",
        headers=headers,
        json={"roadmap_id": rid, "task_id": task_id, "decision_id": decision_id},
    )
    assert adapt.status_code == 200, adapt.text
    ar = adapt.json()
    assert ar.get("feedback_type") == "complete"
    assert ar.get("applied") is True
    assert ar.get("next_task_id") == "task_2", f"expected next task_2, got {ar.get('next_task_id')!r}"

    t1 = find_task_in_roadmap(ar["updated_roadmap"], task_id)
    assert t1 is not None
    assert t1.get("completed") is True or (t1.get("status") or "").lower() == "completed"
    desc_before = t1.get("description")
    assert desc_before, "task should keep description"

    log = client.post(
        "/api/phase2/interactions/log",
        headers=headers,
        json={
            "task_id": task_id,
            "action_type": "complete",
            "roadmap_id": rid,
            "job_id": job_id,
        },
    )
    assert log.status_code == 200
    assert log.json().get("reward_calculated") in (1.0, 1.3)
    print("[OK] complete: KEEP_NEXT_TASK only, task marked completed, next_task_id=task_2")


def run_bandit_flow_without_forced(client: TestClient, headers: dict, user_id: int, job_id: int) -> None:
    print("\n========== Bandit path (no forced_action) ==========")
    rid = save_roadmap(client, headers, job_id, "bandit")
    task_id = "task_1"

    db = SessionLocal()
    try:
        rm = db.query(Roadmap).filter(Roadmap.id == rid).first()
        before_rd = copy.deepcopy(rm.roadmap_data)
        print_tasks("BEFORE", rm.roadmap_data)
    finally:
        db.close()

    rec = client.get(
        "/api/phase2/recommend",
        headers=headers,
        params={
            "roadmap_id": rid,
            "task_id": task_id,
            "job_id": job_id,
            "feedback_type": "too_hard",
        },
    )
    assert rec.status_code == 200, rec.text
    rec_body = rec.json()
    assert_recommend_response_fields(rec_body)
    decision_id = rec_body["decision_id"]
    va = rec_body["valid_actions"]
    assert "DECREASE_CURRENT_TASK_DIFFICULTY" in va or "ADD_PREREQUISITE_TASK" in va
    print(f"[OK] recommend decision_id={decision_id} selected_action={rec_body.get('selected_action')!r}")

    adapt = client.post(
        "/api/phase2/roadmap/adapt",
        headers=headers,
        json={"roadmap_id": rid, "task_id": task_id, "decision_id": decision_id},
    )
    assert adapt.status_code == 200
    adapt_body = adapt.json()
    assert_adapt_response_fields(adapt_body)
    print(
        f"[OK] adapt applied={adapt_body['applied']} "
        f"selected_action={adapt_body['selected_action']!r} (explanation present)"
    )

    append_demo_record("bandit_no_force", before_rd, adapt_body["updated_roadmap"])

    rate = client.post(
        "/api/phase2/interactions/log",
        headers=headers,
        json={
            "task_id": task_id,
            "action_type": "too_hard",
            "roadmap_id": rid,
            "job_id": job_id,
        },
    )
    assert rate.status_code == 200
    rew = rate.json().get("reward_calculated")
    assert rew in (-0.8, -1.0, -1.1), f"unexpected too_hard reward {rew}"
    print(f"[OK] too_hard -> reward_calculated {rew}")

    db = SessionLocal()
    try:
        rm = db.query(Roadmap).filter(Roadmap.id == rid).first()
        db.refresh(rm)
        print_tasks("AFTER", rm.roadmap_data)
    finally:
        db.close()


def main() -> None:
    assert adaptive_rl_debug_enabled(), (
        "Set ADAPTIVE_RL_DEBUG=true or ENVIRONMENT=test before starting this script "
        "(must be set before importing app)."
    )

    _demo_snippets.clear()
    print("[INFO] ADAPTIVE_RL_DEBUG=true (script sets env before app import).")
    print(f"[INFO] GEMINI_API_KEY configured: {gemini_configured()}")

    client = TestClient(app)
    auth = client.post(
        "/api/auth/login",
        data={"username": "test@example.com", "password": "password123"},
    )
    assert auth.status_code == 200, auth.text
    token = auth.json()["access_token"]
    user_id = auth.json()["user_id"]
    h = {"Authorization": f"Bearer {token}"}

    dbq = SessionLocal()
    try:
        row = dbq.query(Job).filter(Job.status.in_(["active", "open"])).first()
        assert row is not None, "No jobs in DB; run scripts/seed_rag.py"
        job_id = row.id
    finally:
        dbq.close()

    run_feedback_mask_checks(client, h, job_id)
    run_complete_flow(client, h, job_id)
    run_bandit_flow_without_forced(client, h, user_id, job_id)

    for fa, lab, fb in (
        ("ADD_PREREQUISITE_TASK", "prereq", "too_hard"),
        ("DECREASE_DIFFICULTY", "easier", "too_hard"),
        ("INCREASE_DIFFICULTY", "harder", "too_easy"),
        ("REPEAT_WITH_VARIATION", "followup", "too_easy"),
    ):
        run_forced_flow(client, h, user_id, job_id, fa, lab, fb)

    SNIPPETS_OUTPUT.write_text(
        json.dumps({"demo_snippets": _demo_snippets}, indent=2, ensure_ascii=True),
        encoding="utf-8",
    )
    print(f"\n[OK] Wrote screenshot snippets -> {SNIPPETS_OUTPUT}")

    print("\n[OK] E2E finished.")


if __name__ == "__main__":
    main()
