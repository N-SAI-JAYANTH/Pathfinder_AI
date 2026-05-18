"""
Application configuration. All settings loaded from environment.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Paths (backend root)
BASE_DIR = Path(__file__).resolve().parent.parent
ML_MODELS_DIR = BASE_DIR / "ml_models"
UPLOADS_DIR = BASE_DIR / "uploads"
CHROMA_DIR = BASE_DIR / "chroma_db"

# Database
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./pathfinder.db")

# Auth
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7 days

# LLM (Gemini) — gemini-1.5-flash was removed from the v1beta API; override via .env if needed
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
# Prefer models that often still have free-tier quota; override in .env if needed
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite")
GEMINI_MODEL_FALLBACKS = [
    m.strip()
    for m in os.getenv(
        "GEMINI_MODEL_FALLBACKS",
        "gemini-2.0-flash-lite,gemini-2.5-flash,gemini-1.5-flash-8b,gemini-1.5-flash",
    ).split(",")
    if m.strip()
]


def gemini_model_names() -> list:
    """Primary model first, then fallbacks (deduped)."""
    names = []
    for name in [GEMINI_MODEL, *GEMINI_MODEL_FALLBACKS]:
        if name and name not in names:
            names.append(name)
    return names

# RL
RL_MODEL_PATH = str(BASE_DIR / "rl_model.pkl")

# Adaptive roadmap QA: forced_action on /api/phase2/recommend only when enabled (never treat prod as debug by accident)
ENVIRONMENT = os.getenv("ENVIRONMENT", "production").strip().lower()


def _env_truthy(name: str, default: str = "") -> bool:
    return os.getenv(name, default).strip().lower() in ("1", "true", "yes", "on")


ADAPTIVE_RL_DEBUG = _env_truthy("ADAPTIVE_RL_DEBUG")


def adaptive_rl_debug_enabled() -> bool:
    return ENVIRONMENT in ("development", "dev", "test", "testing") or ADAPTIVE_RL_DEBUG
