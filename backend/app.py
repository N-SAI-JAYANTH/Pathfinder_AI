"""
Backward-compatible FastAPI entrypoint.

Some tooling expects `backend/app.py` with `app` exported.
The main application lives at `backend/app/main.py`.
"""

from __future__ import annotations

import importlib
from pathlib import Path

# IMPORTANT:
# This repo also contains a real `backend/app/` package.
# Having this file named `app.py` can shadow that package when importing `app.*`.
# To keep backward compatibility and still allow `import app.main`, we make this
# module behave like a package by setting `__path__` to the package directory.
__path__ = [str(Path(__file__).resolve().parent / "app")]

app = importlib.import_module("app.main").app  # noqa: F401

