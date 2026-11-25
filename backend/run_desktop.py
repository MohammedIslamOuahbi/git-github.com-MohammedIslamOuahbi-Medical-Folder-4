from __future__ import annotations

import os
import sys
from pathlib import Path

import uvicorn


def ensure_backend_on_path() -> None:
    backend_root = Path(__file__).resolve().parent
    backend_root_str = str(backend_root)
    if backend_root_str not in sys.path:
        sys.path.insert(0, backend_root_str)


def configure_environment() -> None:
    os.environ.setdefault("APP_ENV", "production")
    if not os.environ.get("DATABASE_URL", "").startswith("postgresql"):
        raise RuntimeError("DATABASE_URL must be configured with a PostgreSQL URL before starting the backend.")
    os.environ.setdefault("API_BASE_URL", "http://127.0.0.1:8000/api/v1")
    os.environ.setdefault("BACKEND_CORS_ORIGINS", "http://localhost:5173,file://")
    os.environ.setdefault("APP_NAME", "Ibn Sina Medical Clinic")


if __name__ == "__main__":
    ensure_backend_on_path()
    configure_environment()
    from app.main import app

    uvicorn.run(app, host="127.0.0.1", port=8000, reload=False)
