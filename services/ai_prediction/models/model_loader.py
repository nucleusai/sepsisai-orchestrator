"""
Thread-safe model loader.

Supports hot-reloading at runtime via the /predict/reload-model endpoint.
"""

import logging
import threading
from pathlib import Path

import joblib

logger = logging.getLogger(__name__)

_model_lock = threading.Lock()
_current_model = None

DEFAULT_MODEL_PATH = Path(__file__).resolve().parent.parent / "model_store" / "gbdt_model.pkl"


def load_model(path: str | None = None) -> None:
    """Load (or reload) the model from *path* into the global singleton."""
    global _current_model
    model_path = Path(path) if path else DEFAULT_MODEL_PATH
    logger.info("Loading model from %s", model_path)
    model = joblib.load(model_path)
    with _model_lock:
        _current_model = model
    logger.info("Model loaded successfully.")


def get_model():
    """Return the currently loaded model (thread-safe)."""
    with _model_lock:
        if _current_model is None:
            raise RuntimeError("Model not loaded — call load_model() first.")
        return _current_model
