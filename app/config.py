import os
import sys


def _resolve_base_dir():
    """Return the base directory: exe location for PyInstaller, project root for dev."""
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class Config:
    BASE_DIR = _resolve_base_dir()

    DATABASE_PATH = os.path.join(BASE_DIR, "data", "testcase.db")
    LOG_DIR = os.path.join(BASE_DIR, "log")
    BUILTIN_MODEL_PATH = os.path.join(BASE_DIR, "models", "text2vec-base-chinese")
    UPLOAD_FOLDER = os.path.join(BASE_DIR, "data", "uploads")

    DEFAULT_SIMILARITY_THRESHOLD = 0.80
    MIN_SAMPLES = 2

    SECRET_KEY = "testcase-cluster-tool-secret-key"
    MAX_CONTENT_LENGTH = 100 * 1024 * 1024  # 100MB
