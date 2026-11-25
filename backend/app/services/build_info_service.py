from __future__ import annotations

import json
import os
import subprocess
import sys
from functools import lru_cache
from pathlib import Path

from alembic.config import Config as AlembicConfig
from alembic.script import ScriptDirectory


BUILD_INFO_FILENAME = "backend-build-info.json"
BOOTSTRAP_VERSION = "Application Bootstrap v2"


def backend_root() -> Path:
    return Path(__file__).resolve().parents[2]


def runtime_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return backend_root()


def bundle_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", runtime_dir()))
    return backend_root()


def workspace_root() -> Path:
    return backend_root().parent


def _read_json(path: Path) -> dict[str, object] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _candidate_paths() -> list[Path]:
    frontend_binaries = workspace_root() / "frontend" / "src-tauri" / "binaries" / BUILD_INFO_FILENAME
    candidates = [
        runtime_dir() / BUILD_INFO_FILENAME,
        bundle_dir() / BUILD_INFO_FILENAME,
        backend_root() / BUILD_INFO_FILENAME,
        frontend_binaries,
    ]
    unique: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        key = str(candidate.resolve()) if candidate.exists() else str(candidate)
        if key in seen:
            continue
        seen.add(key)
        unique.append(candidate)
    return unique


def _read_package_version() -> str:
    package_path = workspace_root() / "frontend" / "package.json"
    payload = _read_json(package_path)
    version = payload.get("version") if isinstance(payload, dict) else None
    if isinstance(version, str) and version.strip():
        return version.strip()
    return os.environ.get("IBNSINA_APP_VERSION", "unknown").strip() or "unknown"


def _read_git_commit() -> str:
    env_commit = (os.environ.get("IBNSINA_GIT_COMMIT") or "").strip()
    if env_commit:
        return env_commit
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=workspace_root(),
            capture_output=True,
            check=False,
            text=True,
        )
    except OSError:
        return "unknown"
    return result.stdout.strip() if result.returncode == 0 and result.stdout.strip() else "unknown"


def _read_alembic_head() -> str:
    try:
        config = AlembicConfig(str(backend_root() / "alembic.ini"))
        config.set_main_option("script_location", str(backend_root() / "alembic"))
        script = ScriptDirectory.from_config(config)
        heads = sorted(script.get_heads())
    except Exception:
        return "unknown"
    return heads[0] if len(heads) == 1 else "unknown"


@lru_cache(maxsize=1)
def get_build_info() -> dict[str, object]:
    payload = None
    for candidate in _candidate_paths():
        if candidate.exists():
            payload = _read_json(candidate)
            if payload:
                break

    version = _read_package_version()
    info = {
        "version": version,
        "frontendVersion": version,
        "backendVersion": version,
        "installerVersion": version,
        "gitCommit": _read_git_commit(),
        "buildTimestampUtc": None,
        "alembicHead": _read_alembic_head(),
        "bootstrapVersion": BOOTSTRAP_VERSION,
        "source": "computed",
    }

    if isinstance(payload, dict):
        info.update(payload)
        info["source"] = "bundled"

    info.setdefault("bootstrapVersion", BOOTSTRAP_VERSION)
    info.setdefault("version", version)
    info.setdefault("frontendVersion", info["version"])
    info.setdefault("backendVersion", info["version"])
    info.setdefault("installerVersion", info["version"])
    info.setdefault("gitCommit", _read_git_commit())
    info.setdefault("alembicHead", _read_alembic_head())
    return info
