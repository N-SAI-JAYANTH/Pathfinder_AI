"""
Backward compatibility: re-export LLM (Gemini) service.
Prefer: from app.services.llm import extract_skills, chat_with_context, ...
"""
from app.services.llm import (
    extract_text_from_file,
    extract_skills,
    analyze_skill_gap,
    analyze_strengths_weaknesses,
    chat_with_context,
    chat_with_rag_and_history,
)

__all__ = [
    "extract_text_from_file",
    "extract_skills",
    "analyze_skill_gap",
    "analyze_strengths_weaknesses",
    "chat_with_context",
    "chat_with_rag_and_history",
]
