"""
Chat with RAG retrieval, multi-turn history, and per-page session persistence.
"""
from datetime import datetime
from typing import Any, List, Optional

from sqlalchemy.orm import Session

from app import models
from app.services.llm.gemini import chat_with_rag_and_history
from app.services.rag_service import rag_service

MAX_HISTORY_TURNS = 20
WELCOME_MESSAGE = (
    "Hi! I'm your PathFinder AI Career Copilot. Ask me about careers, skills, "
    "roadmaps, or jobs — I'll remember our conversation on this page."
)


def _norm_page_id(page_id: Optional[str]) -> str:
    if page_id is None:
        return ""
    return str(page_id).strip()


def _norm_page_type(page_type: Optional[str]) -> str:
    if not page_type or not str(page_type).strip():
        return "global"
    return str(page_type).strip().lower()


def _messages_list(raw: Any) -> List[dict]:
    if not raw or not isinstance(raw, list):
        return []
    out = []
    for m in raw:
        if not isinstance(m, dict):
            continue
        role = m.get("role")
        content = m.get("content")
        if role in ("user", "assistant", "system") and content:
            out.append({"role": role, "content": str(content)})
    return out


def format_rag_context(query: str, n_results: int = 5) -> str:
    try:
        results = rag_service.retrieve_context(query, n_results=n_results)
        docs = (results or {}).get("documents") or [[]]
        metas = (results or {}).get("metadatas") or [[]]
        chunks = []
        for i, doc in enumerate(docs[0] if docs else []):
            if not doc:
                continue
            meta = metas[0][i] if metas and metas[0] and i < len(metas[0]) else {}
            label = meta.get("type") or meta.get("source") or "knowledge"
            preview = doc[:800] + ("..." if len(doc) > 800 else "")
            chunks.append(f"[{label}] {preview}")
        return "\n\n".join(chunks)
    except Exception as e:
        print(f"RAG retrieve failed: {e}")
        return ""


def build_page_context(db: Session, user_id: int, context: Optional[dict]) -> str:
    if not context:
        return ""
    parts = []
    roadmap_id = context.get("roadmapId") or context.get("roadmap_id")
    job_id = context.get("jobId") or context.get("job_id")

    if roadmap_id:
        try:
            rid = int(roadmap_id)
            rm = (
                db.query(models.Roadmap)
                .filter(models.Roadmap.id == rid, models.Roadmap.user_id == user_id)
                .first()
            )
            if rm:
                parts.append(f"Current roadmap: {rm.title or rm.target_career or 'Saved roadmap'}")
                data = rm.roadmap_data or {}
                summary = data.get("role_summary") or {}
                if summary.get("title"):
                    parts.append(f"Target role: {summary['title']}")
                if summary.get("what_you_do"):
                    parts.append("Responsibilities: " + "; ".join(summary["what_you_do"][:4]))
                gap = data.get("gap_analysis") or {}
                if gap.get("summary"):
                    parts.append(f"Gap analysis: {gap['summary'][:400]}")
        except (TypeError, ValueError):
            pass

    if job_id:
        try:
            jid = int(job_id)
            job = db.query(models.Job).filter(models.Job.id == jid).first()
            if job:
                parts.append(
                    f"Current job: {job.job_title} at {job.company_name or 'company'}"
                )
                if job.skills_required:
                    sk = job.skills_required
                    if isinstance(sk, list):
                        parts.append("Required skills: " + ", ".join(sk[:12]))
        except (TypeError, ValueError):
            pass

    prof = (
        db.query(models.UserProfile)
        .filter(models.UserProfile.user_id == user_id)
        .first()
    )
    if prof:
        skills = []
        for fld in (prof.skills, prof.extracted_skills):
            if isinstance(fld, list):
                skills.extend(str(s) for s in fld[:8])
        if skills:
            parts.append("User skills: " + ", ".join(skills[:12]))
        if prof.degree:
            parts.append(f"Education: {prof.degree}")

    return "\n".join(parts)


def get_or_create_session(
    db: Session,
    user_id: int,
    page_type: Optional[str],
    page_id: Optional[str],
    session_id: Optional[int] = None,
    title_hint: Optional[str] = None,
) -> models.ChatSession:
    pt = _norm_page_type(page_type)
    pid = _norm_page_id(page_id)

    if session_id:
        existing = (
            db.query(models.ChatSession)
            .filter(
                models.ChatSession.id == session_id,
                models.ChatSession.user_id == user_id,
            )
            .first()
        )
        if existing:
            return existing

    session = (
        db.query(models.ChatSession)
        .filter(
            models.ChatSession.user_id == user_id,
            models.ChatSession.page_type == pt,
            models.ChatSession.page_id == pid,
        )
        .first()
    )
    if session:
        return session

    session = models.ChatSession(
        user_id=user_id,
        page_type=pt,
        page_id=pid,
        title=title_hint or _default_title(pt, pid),
        messages=[{"role": "assistant", "content": WELCOME_MESSAGE}],
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def _default_title(page_type: str, page_id: str) -> str:
    if page_type == "roadmap" and page_id:
        return f"Roadmap chat #{page_id}"
    if page_type == "job" and page_id:
        return f"Job chat #{page_id}"
    if page_type == "global":
        return "Career advisor"
    return f"{page_type} chat"


def process_chat(
    db: Session,
    user_id: int,
    user_name: str,
    message: str,
    session_id: Optional[int] = None,
    page_type: Optional[str] = "global",
    page_id: Optional[str] = "",
    context: Optional[dict] = None,
) -> dict:
    session = get_or_create_session(
        db, user_id, page_type, page_id, session_id=session_id
    )
    history = _messages_list(session.messages)
    # Exclude welcome-only assistant messages from model history if user has chatted
    model_history = [
        m for m in history
        if m["role"] in ("user", "assistant")
    ][-MAX_HISTORY_TURNS * 2 :]

    rag_context = format_rag_context(message)
    page_context = build_page_context(db, user_id, context)

    result = chat_with_rag_and_history(
        message=message,
        user_name=user_name or "User",
        history=model_history,
        rag_context=rag_context,
        page_context=page_context,
    )

    assistant_text = result.get("response") or "I couldn't generate a reply. Please try again."
    if result.get("error") and not result.get("response"):
        assistant_text = f"I'm having trouble right now ({result['error']}). Please try again."

    now_iso = datetime.utcnow().isoformat() + "Z"
    new_messages = history + [
        {"role": "user", "content": message, "timestamp": now_iso},
        {"role": "assistant", "content": assistant_text, "timestamp": now_iso},
    ]
    session.messages = new_messages
    session.updated_at = datetime.utcnow()
    if not session.title or session.title.startswith("Roadmap chat") and context:
        hint = (context or {}).get("title")
        if hint:
            session.title = str(hint)[:120]
    db.commit()
    db.refresh(session)

    return {
        "response": assistant_text,
        "session_id": session.id,
        "messages": [
            {"role": m["role"], "content": m["content"]}
            for m in new_messages
            if m["role"] in ("user", "assistant", "system")
        ],
    }


def list_sessions(db: Session, user_id: int) -> list[models.ChatSession]:
    return (
        db.query(models.ChatSession)
        .filter(models.ChatSession.user_id == user_id)
        .order_by(models.ChatSession.updated_at.desc())
        .all()
    )


def get_session(db: Session, user_id: int, session_id: int) -> Optional[models.ChatSession]:
    return (
        db.query(models.ChatSession)
        .filter(
            models.ChatSession.id == session_id,
            models.ChatSession.user_id == user_id,
        )
        .first()
    )


def clear_session_messages(db: Session, user_id: int, session_id: int) -> Optional[models.ChatSession]:
    session = get_session(db, user_id, session_id)
    if not session:
        return None
    session.messages = [{"role": "assistant", "content": WELCOME_MESSAGE}]
    session.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(session)
    return session
