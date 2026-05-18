"""
LLM service: Gemini — resume parsing, skill extraction, chat, skill-gap, strengths/weaknesses.
"""
import json
import re
from pathlib import Path

from app.config import GEMINI_API_KEY
from app.services.llm.gemini_client import generate_with_fallback, get_gemini_model
from app.services.llm.resume_skill_fallback import extract_skills_from_text


def _friendly_gemini_error(exc: Exception) -> str:
    err = str(exc).lower()
    if "429" in err or "quota" in err or "rate limit" in err or "limit: 0" in err:
        return (
            "Gemini free-tier quota is exhausted for this Google account (not a bad API key). "
            "Enable billing in Google AI Studio, wait for the daily reset, or use a different Google account. "
            "See https://ai.google.dev/gemini-api/docs/rate-limits"
        )
    if "403" in err or "401" in err or "api key" in err:
        return "Gemini API key is invalid or not authorized. Check GEMINI_API_KEY in backend/.env"
    return str(exc)

# PDF text extraction
try:
    import PyPDF2
except ImportError:
    PyPDF2 = None

# Optional: DOCX support
try:
    import docx
except ImportError:
    docx = None

# Gemini client (lazy init)
_client = None


def _get_client():
    global _client
    if _client is not None:
        return _client
    _client = get_gemini_model()
    return _client


def extract_text_from_file(file_path: str) -> str:
    """Extract text from PDF or DOC/DOCX file."""
    path = Path(file_path)
    if not path.exists():
        return ""
    suffix = path.suffix.lower()
    if suffix == ".pdf" and PyPDF2:
        try:
            with open(path, "rb") as f:
                reader = PyPDF2.PdfReader(f)
                parts = []
                for page in reader.pages:
                    t = page.extract_text()
                    if t:
                        parts.append(t)
                return "\n".join(parts) if parts else ""
        except Exception as e:
            print(f"PDF extraction error: {e}")
            return ""
    if suffix in (".docx", ".doc") and docx:
        try:
            doc = docx.Document(path)
            return "\n".join(p.text for p in doc.paragraphs)
        except Exception as e:
            print(f"DOCX extraction error: {e}")
            return ""
    # Fallback: try reading as text (works for plain text only)
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""


def extract_skills(resume_text: str) -> dict:
    """Extract technical and soft skills from resume text. Returns {technical_skills, soft_skills} or {error}."""
    if not resume_text or len(resume_text.strip()) < 10:
        return {"technical_skills": [], "soft_skills": [], "error": "Resume text too short"}

    def _with_local_fallback(exc: Exception | None = None) -> dict:
        local = extract_skills_from_text(resume_text)
        out = {
            "technical_skills": local.get("technical_skills", []),
            "soft_skills": local.get("soft_skills", []),
        }
        if exc is not None:
            msg = _friendly_gemini_error(exc)
            if out["technical_skills"] or out["soft_skills"]:
                out["warning"] = msg
            else:
                out["error"] = msg
        return out

    if not GEMINI_API_KEY:
        return _with_local_fallback()

    try:
        prompt = """Extract ALL skills from this resume and categorize them.
Rules:
1. Return ONLY valid JSON with two arrays: "technical_skills" and "soft_skills".
2. Technical: programming languages, tools, frameworks, technologies.
3. Soft: leadership, communication, problem-solving, teamwork, etc.
4. No job titles or company names.

Example output:
{"technical_skills": ["Python", "SQL", "React"], "soft_skills": ["Leadership", "Communication"]}

Resume:
"""
        response = generate_with_fallback(prompt + resume_text[:12000], temperature=0.3)
        if response and response.text:
            text = response.text.strip()
            m = re.search(r"\{[^{}]*\"technical_skills\"[^{}]*\"soft_skills\"[^{}]*\}", text, re.DOTALL)
            if m:
                data = json.loads(m.group(0))
                return {
                    "technical_skills": data.get("technical_skills", []),
                    "soft_skills": data.get("soft_skills", []),
                }
    except Exception as e:
        return _with_local_fallback(e)

    local = extract_skills_from_text(resume_text)
    if local.get("technical_skills") or local.get("soft_skills"):
        return local
    return {"technical_skills": [], "soft_skills": [], "error": "Could not extract skills from resume"}


def analyze_skill_gap(user_skills: list, required_skills: list) -> dict:
    """Analyze gap between user skills and required skills. Returns transferable, missing, etc."""
    if not required_skills:
        return {
            "transferable_skills": list(user_skills) if user_skills else [],
            "missing_skills": [],
            "summary": "No required skills listed.",
        }
    user_set = set(s.strip().lower() for s in (user_skills or []) if s)
    req_set = set(s.strip().lower() if isinstance(s, str) else str(s).lower() for s in required_skills if s)
    transferable = [s for s in (user_skills or []) if s and s.strip().lower() in req_set]
    missing = [s for s in required_skills if (s.strip().lower() if isinstance(s, str) else str(s).lower()) not in user_set]
    client = _get_client()
    if client and (transferable or missing):
        try:
            prompt = f"""Given:
Current user skills: {json.dumps(user_skills or [])}
Required skills: {json.dumps(required_skills)}
Transferable (user has): {transferable}
Missing: {missing}

Return a short JSON: {"transferable_skills": [...], "missing_skills": [{"skill": "...", "priority": "high|medium|low", "reason": "..."}], "summary": "1-2 sentence summary"}"""
            response = generate_with_fallback(prompt, temperature=0.3)
            if response and response.text:
                m = re.search(r"\{.*\}", response.text, re.DOTALL)
                if m:
                    return json.loads(m.group(0))
        except Exception:
            pass
    return {
        "transferable_skills": transferable,
        "missing_skills": [{"skill": s, "priority": "medium", "reason": "Not in current profile"} for s in missing],
        "summary": f"User has {len(transferable)} of {len(required_skills)} required skills; {len(missing)} to develop.",
    }


def analyze_strengths_weaknesses(profile: dict) -> dict:
    """Analyze strengths and weaknesses from user profile dict."""
    client = _get_client()
    skills = profile.get("skills") or profile.get("extracted_skills") or []
    if isinstance(skills, str):
        skills = [s.strip() for s in skills.split(",")] if skills else []
    profile_str = json.dumps({k: v for k, v in profile.items() if k != "_sa_instance_state" and v is not None}, default=str)[:3000]
    if client:
        try:
            prompt = f"""Based on this user profile, list 3-5 strengths and 2-4 areas to improve. Return JSON: {{"strengths": ["..."], "weaknesses": ["..."], "summary": "1-2 sentences"}}
Profile (excerpt): {profile_str}"""
            response = generate_with_fallback(prompt, temperature=0.3)
            if response and response.text:
                m = re.search(r"\{.*\}", response.text, re.DOTALL)
                if m:
                    return json.loads(m.group(0))
        except Exception as e:
            return {"error": str(e), "strengths": [], "weaknesses": [], "summary": ""}
    return {
        "strengths": list(skills)[:5] if skills else ["Profile incomplete"],
        "weaknesses": ["Add more skills and experience to get personalized analysis."],
        "summary": "Set GEMINI_API_KEY for AI-powered analysis.",
    }


def chat_with_context(message: str, context: dict) -> dict:
    """Chat with optional context (e.g. user name). Returns {response} or {error}."""
    return chat_with_rag_and_history(
        message=message,
        user_name=context.get("name", "User"),
        history=[],
        rag_context="",
        page_context="",
    )


def _history_to_gemini(history: list) -> list:
    """Convert {role, content} messages to Gemini chat history format."""
    gemini_history = []
    for msg in history:
        role = msg.get("role")
        content = (msg.get("content") or "").strip()
        if not content:
            continue
        if role == "user":
            gemini_history.append({"role": "user", "parts": [content]})
        elif role == "assistant":
            gemini_history.append({"role": "model", "parts": [content]})
    return gemini_history


def chat_with_rag_and_history(
    message: str,
    user_name: str = "User",
    history=None,
    rag_context: str = "",
    page_context: str = "",
) -> dict:
    """
    Multi-turn chat with RAG snippets and page context.
    Returns {response} or {response, error}.
    """
    client = _get_client()
    if not client:
        return {
            "response": "Chat requires GEMINI_API_KEY to be set.",
            "error": "No API key",
        }

    history = history or []
    system_parts = [
        "You are PathFinder AI, a helpful career coach.",
        f"The user's name is {user_name}.",
        "Use the knowledge base excerpts and page context when relevant.",
        "Remember the conversation history and answer follow-up questions naturally.",
        "Be supportive, specific, and concise (2-6 sentences unless more detail is needed).",
    ]
    if page_context:
        system_parts.append(f"\nPage context:\n{page_context}")
    if rag_context:
        system_parts.append(f"\nKnowledge base excerpts:\n{rag_context}")

    system_instruction = "\n".join(system_parts)

    try:
        gemini_history = _history_to_gemini(history)
        full_prompt = message
        if not gemini_history:
            full_prompt = f"{system_instruction}\n\nUser: {message}"
        else:
            history_text = "\n".join(
                f"{'User' if h['role'] == 'user' else 'Assistant'}: {h['parts'][0]}"
                for h in gemini_history
            )
            full_prompt = (
                f"{system_instruction}\n\nConversation so far:\n{history_text}\n\nUser: {message}"
            )
        response = generate_with_fallback(full_prompt, temperature=0.5)
        if response and response.text:
            return {"response": response.text.strip()}
        return {"response": "I couldn't generate a reply. Please try again."}
    except Exception as e:
        return {"response": "", "error": str(e)}
