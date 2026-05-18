"""Shared Gemini client with model fallback."""
import google.generativeai as genai

from app.config import GEMINI_API_KEY, gemini_model_names

_cached_model = None
_cached_model_name = None


def reset_gemini_client():
    global _cached_model, _cached_model_name
    _cached_model = None
    _cached_model_name = None


def get_gemini_model():
    """Return a GenerativeModel, trying configured names until one works."""
    global _cached_model, _cached_model_name
    if _cached_model is not None:
        return _cached_model
    if not GEMINI_API_KEY:
        return None
    genai.configure(api_key=GEMINI_API_KEY)
    last_err = None
    for name in gemini_model_names():
        try:
            model = genai.GenerativeModel(name)
            _cached_model = model
            _cached_model_name = name
            print(f"Gemini client ready: {name}")
            return model
        except Exception as e:
            last_err = e
            print(f"Gemini model init failed ({name}): {e}")
    print(f"Gemini: no model available. Last error: {last_err}")
    return None


def active_gemini_model_name() -> str:
    return _cached_model_name or ""


def _is_retryable(err: str) -> bool:
    err = err.lower()
    return any(
        token in err
        for token in (
            "not found",
            "404",
            "not supported",
            "429",
            "quota",
            "rate limit",
            "rate-limit",
            "resource exhausted",
            "too many requests",
            "limit: 0",
        )
    )


def generate_with_fallback(prompt: str, *, temperature: float = 0.4):
    """Call generate_content, retrying other models on 404 or quota/rate-limit errors."""
    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY is not set")

    genai.configure(api_key=GEMINI_API_KEY)
    last_err = None
    for name in gemini_model_names():
        try:
            model = genai.GenerativeModel(name)
            response = model.generate_content(
                prompt,
                generation_config=genai.types.GenerationConfig(temperature=temperature),
            )
            global _cached_model, _cached_model_name
            _cached_model = model
            _cached_model_name = name
            return response
        except Exception as e:
            last_err = e
            err = str(e)
            if _is_retryable(err):
                print(f"Gemini generate failed ({name}): {err[:120]}... trying next model")
                continue
            raise
    raise RuntimeError(str(last_err) if last_err else "Gemini generation failed")
