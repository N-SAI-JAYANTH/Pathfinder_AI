"""
Backward-compatible import path.

Primary implementation is in `backend/app/services/model1_service.py`.
"""

from app.services.model1_service import Model1Service, model1_service  # noqa: F401

