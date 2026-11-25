from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import IO
from urllib.parse import unquote

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from app.config import settings
from app.core.logging import get_logger
from app.core.maintenance_mode import maintenance_mode_state
from app.database import dispose_engine, reset_session_factory
from app.exceptions import (
    BadRequestException,
    ConflictException,
    GatewayTimeoutException,
    ServiceUnavailableException,
    UnprocessableEntityAppException,
)
from app.schemas.system_backup import SystemBackupRestoreResponse, SystemBackupStatusResponse

logger = get_logger("app.system_backup")

ALLOWED_EXTENSIONS = {".backup", ".dump"}
MAX_BACKUP_SIZE_BYTES = 5 * 1024 * 1024 * 1024


def _delete_file_quietly(path: str) -> None:
    try:
        Path(path).unlink(missing_ok=True)
    except OSError:
        logger.warning("backup.download_cleanup_failed", extra={"path": path})


@dataclass
class BackupArtifact:
    path: Path
    filename: str
    created_at: datetime
    size_bytes: int


class PostgresBackupService:
    _lock = threading.Lock()
    _state = {
        "state": "idle",
        "operation": None,
        "stage": None,
        "message": "Aucune operation en cours.",
        "started_at": None,
        "elapsed_seconds": 0,
        "last_completed_at": None,
        "last_error": None,
        "safety_backup_filename": None,
    }

    def __init__(self) -> None:
        self._database_url = make_url(settings.database_url)
        local_app_data = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        self._data_root = local_app_data / "Ibn Sina Medical Clinic"
        self._backup_root = self._data_root / "backups"
        self._restore_temp_root = self._data_root / "temp" / "restore"
        self._temp_root = self._restore_temp_root
        self._backup_root.mkdir(parents=True, exist_ok=True)
        self._restore_temp_root.mkdir(parents=True, exist_ok=True)
        self._backend_root = Path(__file__).resolve().parents[2]
        self._alembic_ini = self._backend_root / "alembic.ini"

    def get_status(self) -> SystemBackupStatusResponse:
        snapshot = dict(self._state)
        started_at = snapshot.get("started_at")
        if started_at:
            snapshot["elapsed_seconds"] = max(0, int((datetime.now(timezone.utc) - started_at).total_seconds()))
        pg_dump_available = self._is_executable_available("pg_dump")
        pg_restore_available = self._is_executable_available("pg_restore")
        maintenance_snapshot = maintenance_mode_state.snapshot()
        snapshot["server_mode"] = True
        snapshot["can_backup"] = pg_dump_available and not bool(maintenance_snapshot["enabled"])
        snapshot["can_restore"] = pg_restore_available
        snapshot["pg_dump_available"] = pg_dump_available
        snapshot["pg_restore_available"] = pg_restore_available
        return SystemBackupStatusResponse(**snapshot)

    def create_backup(self, *, current_user_id: int, current_user_email: str) -> BackupArtifact:
        self._acquire("creating_backup", "backup", "backup")
        try:
            self._set_stage("backup", "Creation de la sauvegarde PostgreSQL en cours...")
            self._log_stage("backup.requested", current_user_id, current_user_email)
            filename = self._build_backup_filename("medical_clinic_backup")
            backup_path = self._backup_root / filename
            self._log_stage("backup.executable_resolved", current_user_id, current_user_email)
            self._log_stage("backup.started", current_user_id, current_user_email, filename=filename)
            self._run_pg_dump(backup_path)
            artifact = self._build_artifact(backup_path)
            self._mark_completed("Sauvegarde PostgreSQL creee avec succes.")
            self._log_stage(
                "backup.completed",
                current_user_id,
                current_user_email,
                filename=artifact.filename,
                file_size=artifact.size_bytes,
            )
            return artifact
        except Exception as exc:
            self._mark_failed(str(exc))
            self._log_stage("backup.failed", current_user_id, current_user_email, error_summary=str(exc))
            raise
        finally:
            self._release()

    def restore_backup(
        self,
        *,
        upload_filename: str,
        upload_stream: IO[bytes],
        current_user_id: int,
        current_user_email: str,
    ) -> SystemBackupRestoreResponse:
        self._acquire("restoring", "restore", "validating")
        maintenance_enabled = False
        temp_dir: Path | None = None
        uploaded_path: Path | None = None
        safety_backup: BackupArtifact | None = None
        terminated_connections = 0
        try:
            self._log_stage("restore.requested", current_user_id, current_user_email, filename=upload_filename)
            temp_dir = self._create_restore_temp_dir()
            uploaded_path = self._store_uploaded_backup(temp_dir, upload_filename, upload_stream)
            self._log_stage(
                "restore.upload_saved",
                current_user_id,
                current_user_email,
                filename=uploaded_path.name,
                file_size=uploaded_path.stat().st_size,
            )

            self._set_stage("validation", "Validation de la sauvegarde...")
            self._log_stage("restore.validation_started", current_user_id, current_user_email, filename=uploaded_path.name)
            self.validate_backup_file(uploaded_path)
            self._log_stage("restore.validation_completed", current_user_id, current_user_email, filename=uploaded_path.name)

            self._set_stage("creating_safety_backup", "Creation de la sauvegarde de securite...")
            self._log_stage("restore.safety_backup_started", current_user_id, current_user_email)
            safety_backup = self.create_safety_backup()
            self._state["safety_backup_filename"] = safety_backup.filename
            self._log_stage(
                "restore.safety_backup_completed",
                current_user_id,
                current_user_email,
                filename=safety_backup.filename,
                file_size=safety_backup.size_bytes,
            )

            maintenance_mode_state.enable(stage="maintenance", message="Fermeture des connexions PostgreSQL...")
            maintenance_enabled = True
            self._set_stage("maintenance", "Fermeture des connexions PostgreSQL...")
            self._log_stage("restore.database_pool_dispose_started", current_user_id, current_user_email)
            self._dispose_application_engines()
            self._log_stage("restore.database_pool_dispose_completed", current_user_id, current_user_email)

            terminated_connections = self._terminate_target_database_connections()
            self._log_stage(
                "restore.active_connections_terminated",
                current_user_id,
                current_user_email,
                error_summary=f"terminated_connections={terminated_connections}",
            )

            self._set_stage("pg_restore", "Restauration des donnees PostgreSQL en cours.")
            self._log_stage("restore.pg_restore_found", current_user_id, current_user_email)
            self._log_stage("restore.pg_restore_started", current_user_id, current_user_email, filename=uploaded_path.name)
            self._restore_backup(uploaded_path)
            self._log_stage("restore.pg_restore_completed", current_user_id, current_user_email, filename=uploaded_path.name)

            self._set_stage("migrating", "Mise a niveau de la base...")
            self._log_stage("restore.alembic_started", current_user_id, current_user_email)
            self.run_alembic_upgrade()
            self._log_stage("restore.alembic_completed", current_user_id, current_user_email)

            self._set_stage("verifying", "Verification de la base...")
            self.verify_database()

            self._mark_completed("La sauvegarde a ete restauree avec succes.")
            self._log_stage(
                "restore.completed",
                current_user_id,
                current_user_email,
                filename=uploaded_path.name,
                file_size=uploaded_path.stat().st_size,
            )
            return SystemBackupRestoreResponse(
                message="La sauvegarde a ete restauree avec succes. La base PostgreSQL est maintenant a jour.",
                safety_backup_filename=safety_backup.filename,
                migration_status="completed",
            )
        except subprocess.TimeoutExpired as exc:
            message = (
                "La restauration PostgreSQL a depasse le delai autorise. "
                "Des connexions actives ou des verrous empechent probablement la restauration."
            )
            self._mark_failed(message)
            self._log_stage(
                "restore.pg_restore_timeout",
                current_user_id,
                current_user_email,
                filename=uploaded_path.name if uploaded_path else upload_filename,
                error_summary=(
                    f"timeout={settings.postgres_restore_timeout_seconds} "
                    f"stdout={self._sanitize_output(self._normalize_subprocess_output(exc.stdout))[-8000:]} "
                    f"stderr={self._sanitize_output(self._normalize_subprocess_output(exc.stderr))[-8000:]}"
                ),
            )
            raise GatewayTimeoutException(
                message,
                {
                    "code": "POSTGRES_RESTORE_TIMEOUT",
                    "safety_backup_filename": safety_backup.filename if safety_backup else None,
                },
            ) from exc
        except UnprocessableEntityAppException:
            raise
        except ServiceUnavailableException:
            raise
        except Exception as exc:
            self._mark_failed(str(exc))
            self._log_stage(
                "restore.failed",
                current_user_id,
                current_user_email,
                filename=uploaded_path.name if uploaded_path else upload_filename,
                error_summary=str(exc),
            )
            raise
        finally:
            self._dispose_application_engines()
            if maintenance_enabled:
                maintenance_mode_state.disable()
            if temp_dir:
                shutil.rmtree(temp_dir, ignore_errors=True)
            self._release()

    def validate_backup_file(self, path: Path) -> None:
        if path.suffix.lower() not in ALLOWED_EXTENSIONS:
            raise UnprocessableEntityAppException("Le fichier selectionne doit etre au format .backup ou .dump.")
        if not path.exists() or path.stat().st_size <= 0:
            raise UnprocessableEntityAppException("Le fichier de sauvegarde est vide.")
        if path.stat().st_size > MAX_BACKUP_SIZE_BYTES:
            raise UnprocessableEntityAppException("Le fichier de sauvegarde depasse la taille maximale autorisee.")
        self._run_subprocess(
            [self._discover_executable("pg_restore"), "--list", str(path)],
            "Le fichier selectionne n'est pas une sauvegarde PostgreSQL valide.",
            timeout_seconds=settings.postgres_restore_validation_timeout_seconds,
        )

    def create_safety_backup(self) -> BackupArtifact:
        filename = self._build_backup_filename("medical_clinic_before_restore")
        backup_path = self._backup_root / filename
        try:
            self._run_pg_dump(backup_path)
        except Exception as exc:
            raise BadRequestException(
                "La restauration a ete annulee car la sauvegarde de securite n'a pas pu etre creee."
            ) from exc
        return self._build_artifact(backup_path)

    def run_alembic_upgrade(self) -> None:
        command = [
            sys.executable,
            "-m",
            "alembic",
            "-c",
            str(self._alembic_ini),
            "upgrade",
            "head",
        ]
        self._run_subprocess(
            command,
            "Les donnees ont ete restaurees, mais la mise a niveau Alembic a echoue.",
            cwd=self._backend_root,
            timeout_seconds=settings.postgres_alembic_timeout_seconds,
        )

    def verify_database(self) -> None:
        self._dispose_application_engines()
        reset_session_factory()
        from app.database import engine

        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))

    def _terminate_target_database_connections(self) -> int:
        application_database = self._database_url.database
        if not application_database:
            raise ServiceUnavailableException("Impossible de se connecter a la base PostgreSQL.")
        maintenance_url = self._database_url.set(database="postgres")
        maintenance_engine = create_engine(
            maintenance_url,
            isolation_level="AUTOCOMMIT",
            pool_pre_ping=True,
        )
        try:
            with maintenance_engine.connect() as connection:
                rows = connection.execute(
                    text(
                        """
                        SELECT pg_terminate_backend(pid)
                        FROM pg_stat_activity
                        WHERE datname = :database_name
                          AND pid <> pg_backend_pid()
                        """
                    ),
                    {"database_name": application_database},
                ).fetchall()
                return len(rows)
        except Exception as exc:
            raise ServiceUnavailableException(
                "La restauration ne peut pas demarrer car certaines connexions PostgreSQL actives n'ont pas pu etre fermees."
            ) from exc
        finally:
            maintenance_engine.dispose()

    def _restore_backup(self, path: Path) -> None:
        self._dispose_application_engines()
        command = [
            self._discover_executable("pg_restore"),
            "--verbose",
            "--clean",
            "--if-exists",
            "--no-owner",
            "--no-privileges",
            "--exit-on-error",
            "--host",
            str(self._database_url.host or "localhost"),
            "--port",
            str(self._database_url.port or 5432),
            "--username",
            str(self._database_url.username or ""),
            "--dbname",
            str(self._database_name()),
            str(path),
        ]
        environment = self._postgres_env()
        environment["PGOPTIONS"] = "-c lock_timeout=30000 -c statement_timeout=0"
        self._run_subprocess(
            command,
            "La restauration PostgreSQL a echoue. La sauvegarde de securite a ete conservee.",
            timeout_seconds=settings.postgres_restore_timeout_seconds,
            env=environment,
        )
        self._dispose_application_engines()

    def _run_pg_dump(self, output_path: Path) -> None:
        command = [
            self._discover_executable("pg_dump"),
            "--format=custom",
            "--no-owner",
            "--no-privileges",
            "--host",
            str(self._database_url.host or "localhost"),
            "--port",
            str(self._database_url.port or 5432),
            "--username",
            str(self._database_url.username or ""),
            "--file",
            str(output_path),
            str(self._database_name()),
        ]
        self._run_subprocess(
            command,
            "La creation de la sauvegarde PostgreSQL a echoue.",
            timeout_seconds=settings.postgres_backup_timeout_seconds,
        )
        if not output_path.exists() or output_path.stat().st_size <= 0:
            raise BadRequestException("Le fichier de sauvegarde genere est vide.")

    def _store_uploaded_backup(self, temp_dir: Path, filename: str, upload_stream: IO[bytes]) -> Path:
        safe_name = Path(unquote(filename or "backup.dump")).name
        if Path(safe_name).suffix.lower() not in ALLOWED_EXTENSIONS:
            raise UnprocessableEntityAppException("Le fichier selectionne doit etre au format .backup ou .dump.")
        destination = temp_dir / safe_name
        size = 0
        with destination.open("wb") as target:
            while True:
                chunk = upload_stream.read(1024 * 1024)
                if not chunk:
                    break
                size += len(chunk)
                if size > MAX_BACKUP_SIZE_BYTES:
                    raise UnprocessableEntityAppException("Le fichier de sauvegarde depasse la taille maximale autorisee.")
                target.write(chunk)
        if size <= 0:
            raise UnprocessableEntityAppException("Le fichier de sauvegarde est vide.")
        return destination

    def _discover_executable(self, tool_name: str) -> str:
        explicit = settings.pg_dump_path if tool_name == "pg_dump" else settings.pg_restore_path
        if not explicit:
            explicit = os.environ.get("PG_DUMP_PATH" if tool_name == "pg_dump" else "PG_RESTORE_PATH")
        if explicit and Path(explicit).is_file():
            return str(Path(explicit).resolve())

        for candidate_name in (tool_name, f"{tool_name}.exe"):
            from_path = shutil.which(candidate_name)
            if from_path and Path(from_path).is_file():
                return str(Path(from_path).resolve())

        executable = f"{tool_name}.exe" if os.name == "nt" else tool_name
        if os.name == "nt":
            candidates: list[Path] = []
            for root in filter(None, (os.environ.get("ProgramFiles"), os.environ.get("ProgramFiles(x86)"))):
                postgres_root = Path(root) / "PostgreSQL"
                if not postgres_root.exists():
                    continue
                for version_dir in sorted(postgres_root.iterdir(), key=lambda value: value.name, reverse=True):
                    candidates.append(version_dir / "bin" / executable)
            for candidate in candidates:
                if candidate.is_file():
                    return str(candidate.resolve())

        raise BadRequestException(f"L'outil PostgreSQL {tool_name} est introuvable sur le serveur.")

    def _database_name(self) -> str:
        if not self._database_url.drivername.startswith("postgresql"):
            raise ServiceUnavailableException("La base configuree n'est pas une base PostgreSQL.")
        if not self._database_url.username:
            raise ServiceUnavailableException("Le nom d'utilisateur PostgreSQL est manquant.")
        if not self._database_url.database:
            raise ServiceUnavailableException("Le nom de la base PostgreSQL est manquant.")
        return self._database_url.database

    def _postgres_env(self) -> dict[str, str]:
        env = os.environ.copy()
        if self._database_url.password:
            env["PGPASSWORD"] = self._database_url.password
        return env

    def _run_subprocess(
        self,
        command: list[str],
        default_message: str,
        *,
        cwd: Path | None = None,
        timeout_seconds: int | None = None,
        env: dict[str, str] | None = None,
    ) -> None:
        resolved_timeout = timeout_seconds if timeout_seconds is not None else settings.postgres_restore_validation_timeout_seconds
        started = time.perf_counter()
        try:
            completed = subprocess.run(
                command,
                check=False,
                capture_output=True,
                text=True,
                timeout=resolved_timeout,
                env=env or self._postgres_env(),
                shell=False,
                cwd=str(cwd) if cwd else None,
            )
        except FileNotFoundError as exc:
            raise BadRequestException(default_message) from exc
        except subprocess.TimeoutExpired as exc:
            logger.error(
                "restore.pg_restore_timeout timeout=%s elapsed=%.2fs stdout=%s stderr=%s",
                resolved_timeout,
                time.perf_counter() - started,
                self._sanitize_output(self._normalize_subprocess_output(exc.stdout))[-8000:],
                self._sanitize_output(self._normalize_subprocess_output(exc.stderr))[-8000:],
            )
            raise

        if completed.returncode != 0:
            stderr = self._sanitize_output(completed.stderr or "")
            stdout = self._sanitize_output(completed.stdout or "")
            if "lock timeout" in stderr.lower() or "lock timeout" in stdout.lower():
                raise ServiceUnavailableException(
                    "La restauration PostgreSQL est bloquee par des connexions actives. Fermez les sessions utilisant la base puis reessayez.",
                    {"code": "POSTGRES_RESTORE_LOCK_TIMEOUT"},
                )
            raise ServiceUnavailableException(
                stderr or stdout or default_message,
                {"code": "POSTGRES_RESTORE_FAILED"},
            )

    def _normalize_subprocess_output(self, value: str | bytes | None) -> str:
        if value is None:
            return ""
        if isinstance(value, bytes):
            return value.decode("utf-8", errors="replace")
        return value

    def _sanitize_output(self, value: str) -> str:
        sanitized = value or ""
        password = self._database_url.password or ""
        if password:
            sanitized = sanitized.replace(password, "***")
        sanitized = sanitized.replace(str(self._database_url), "[DATABASE_URL]")
        return sanitized

    def _build_backup_filename(self, prefix: str) -> str:
        return f"{prefix}_{datetime.now(timezone.utc).strftime('%Y-%m-%d_%H-%M-%S')}.backup"

    def _create_restore_temp_dir(self) -> Path:
        return Path(tempfile.mkdtemp(prefix="restore_", dir=self._restore_temp_root))

    def _build_artifact(self, path: Path) -> BackupArtifact:
        stats = path.stat()
        return BackupArtifact(
            path=path,
            filename=path.name,
            created_at=datetime.fromtimestamp(stats.st_mtime, tz=timezone.utc),
            size_bytes=stats.st_size,
        )

    def _dispose_application_engines(self) -> None:
        dispose_engine()

    def _acquire(self, state: str, operation: str, stage: str) -> None:
        if not self._lock.acquire(blocking=False):
            raise ConflictException("Une operation de sauvegarde ou de restauration est deja en cours.")
        self._state.update(
            {
                "state": state,
                "operation": operation,
                "stage": stage,
                "message": "Operation systeme en cours.",
                "started_at": datetime.now(timezone.utc),
                "elapsed_seconds": 0,
                "last_error": None,
                "safety_backup_filename": None,
            }
        )

    def _release(self) -> None:
        if self._lock.locked():
            self._lock.release()

    def _set_stage(self, stage: str, message: str) -> None:
        self._state["stage"] = stage
        self._state["message"] = message

    def _mark_completed(self, message: str) -> None:
        self._state.update(
            {
                "state": "completed",
                "operation": None,
                "stage": "completed",
                "message": message,
                "started_at": None,
                "elapsed_seconds": 0,
                "last_completed_at": datetime.now(timezone.utc),
                "last_error": None,
            }
        )
        maintenance_mode_state.disable()

    def _mark_failed(self, message: str) -> None:
        self._state.update(
            {
                "state": "failed",
                "operation": None,
                "stage": "failed",
                "message": "La restauration PostgreSQL a echoue.",
                "started_at": None,
                "elapsed_seconds": 0,
                "last_error": self._sanitize_output(message),
            }
        )
        maintenance_mode_state.disable()

    def _is_executable_available(self, tool_name: str) -> bool:
        try:
            self._discover_executable(tool_name)
            return True
        except Exception:
            return False

    def _log_stage(
        self,
        stage: str,
        user_id: int,
        user_email: str,
        *,
        filename: str | None = None,
        file_size: int | None = None,
        error_summary: str | None = None,
    ) -> None:
        logger.info(
            stage,
            extra={
                "stage": stage,
                "user_id": user_id,
                "user_email": user_email,
                "backup_filename": filename,
                "file_size": file_size,
                "error_summary": self._sanitize_output(error_summary or ""),
            },
        )
