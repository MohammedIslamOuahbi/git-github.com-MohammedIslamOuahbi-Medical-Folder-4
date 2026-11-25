from __future__ import annotations

import hashlib
import socket

from app.config import settings

APP_ID = "medical-folder"
API_VERSION = "1.0"


def get_public_server_identity() -> dict[str, str]:
    hostname = socket.gethostname()
    server_id_source = f"{APP_ID}:{hostname}:{settings.database_name}".encode("utf-8")
    return {
        "application": APP_ID,
        "api_status": "online",
        "api_version": API_VERSION,
        "database_engine": "PostgreSQL",
        "server_id": hashlib.sha256(server_id_source).hexdigest()[:16],
    }
