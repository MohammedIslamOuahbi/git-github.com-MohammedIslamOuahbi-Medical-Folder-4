from __future__ import annotations

import os
import shutil
import subprocess
import threading
import hashlib
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.config import settings
from app.exceptions import BadRequestException, NotFoundException
from app.schemas.sync_connection import BackupCreateResponse, BackupExportResponse, BackupRestoreResponse, BackupStatusResponse


class BackupService:
    _operation_lock = threading.Lock()

    def __init__(self, backup_folder: str | None = None) -> None:
        self.backup_folder = Path(backup_folder or "./backups").resolve()
        self.backup_folder.mkdir(parents=True, exist_ok=True)

    def _database_url(self):
        return make_url(settings.database_url)

    def _tool_path(self, tool_name: str) -> str:
        tool_path = shutil.which(tool_name)
        if tool_path:
            return tool_path

        executable = f"{tool_name}.exe" if os.name == "nt" else tool_name
        candidates: list[Path] = []
        explicit_bin = os.environ.get("POSTGRES_BIN_DIR")
        if explicit_bin:
            candidates.append(Path(explicit_bin) / executable)

        if os.name == "nt":
            for root_key in ("ProgramFiles", "ProgramFiles(x86)"):
                root = os.environ.get(root_key)
                if not root:
                    continue
                postgres_root = Path(root) / "PostgreSQL"
                if postgres_root.exists():
                    candidates.extend(
                        sorted(
                            (entry / "bin" / executable for entry in postgres_root.iterdir() if entry.is_dir()),
                            reverse=True,
                        )
                    )

        for candidate in candidates:
            if candidate.exists() and candidate.is_file():
                return str(candidate)

        raise BadRequestException(
            "POSTGRES_TOOLS_NOT_FOUND: Les outils PostgreSQL pg_dump et pg_restore sont introuvables."
        )

    def _postgres_env(self) -> dict[str, str]:
        env = os.environ.copy()
        password = self._database_url().password
        if password:
            env["PGPASSWORD"] = password
        return env

    def _backup_name(self) -> str:
        return f"medical_backup_{datetime.now(timezone.utc).strftime('%Y-%m-%d_%H-%M-%S')}.dump"

    def _unique_backup_paths(self) -> tuple[Path, Path]:
        base_name = self._backup_name().removesuffix(".dump")
        for index in range(100):
            suffix = "" if index == 0 else f"_{index:02d}"
            backup_path = self.backup_folder / f"{base_name}{suffix}.dump"
            temp_path = self.backup_folder / f"{base_name}{suffix}.dump.tmp"
            if not backup_path.exists() and not temp_path.exists():
                return backup_path, temp_path
        raise BadRequestException("BACKUP_RENAME_FAILED: Impossible de generer un nom de sauvegarde unique.")

    def _base_pg_args(self) -> list[str]:
        url = self._database_url()
        args = [
            "-h",
            url.host or "127.0.0.1",
            "-p",
            str(url.port or 5432),
            "-U",
            url.username or "postgres",
        ]
        return args

    def _run_pg_command(self, command: list[str]) -> None:
        try:
            completed = subprocess.run(
                command,
                env=self._postgres_env(),
                capture_output=True,
                text=True,
                check=False,
                shell=False,
                timeout=60 * 30,
            )
        except subprocess.TimeoutExpired as exc:
            raise BadRequestException("PostgreSQL backup command timed out.") from exc

        if completed.returncode != 0:
            message = completed.stderr.strip() or completed.stdout.strip() or "PostgreSQL backup command failed."
            raise BadRequestException(message)

    def _sha256(self, path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def _backup_files(self) -> list[Path]:
        files = [
            path
            for path in self.backup_folder.glob("medical_backup_*.dump")
            if path.is_file() and path.stat().st_size > 0
        ]
        return sorted(files, key=lambda p: p.stat().st_mtime, reverse=True)

    def _resolve_backup_path(self, value: str | Path) -> Path:
        path = Path(value)
        if not path.is_absolute():
            path = self.backup_folder / path
        resolved = path.resolve()
        try:
            resolved.relative_to(self.backup_folder)
        except ValueError as exc:
            raise BadRequestException("Backup path must stay inside the configured backup folder.") from exc
        if resolved.suffix.lower() != ".dump":
            raise BadRequestException("Only PostgreSQL .dump backup files are accepted.")
        return resolved

    def _acquire_operation_lock(self) -> None:
        if not self._operation_lock.acquire(blocking=False):
            raise BadRequestException("A PostgreSQL backup or restore operation is already running.")

    def _release_operation_lock(self) -> None:
        self._operation_lock.release()

    def status(self, db: Session) -> BackupStatusResponse:
        del db
        files = self._backup_files()
        last_file = files[0] if files else None
        return BackupStatusResponse(
            backup_folder=str(self.backup_folder.resolve()),
            backup_count=len(files),
            last_backup_time=datetime.fromtimestamp(last_file.stat().st_mtime, tz=timezone.utc) if last_file else None,
            last_backup_status="Pret" if last_file else "Aucune sauvegarde PostgreSQL",
        )

    def create_backup(self, db: Session) -> BackupCreateResponse:
        del db
        self._acquire_operation_lock()
        try:
            pg_dump = self._tool_path("pg_dump")
            backup_path, temp_path = self._unique_backup_paths()
            backup_path.parent.mkdir(parents=True, exist_ok=True)
            command = [
                pg_dump,
                *self._base_pg_args(),
                "-d",
                self._database_url().database or settings.database_name,
                "-F",
                "c",
                "-f",
                str(temp_path),
            ]
            try:
                self._run_pg_command(command)
                if not temp_path.exists() or temp_path.stat().st_size == 0:
                    raise BadRequestException("BACKUP_FILE_EMPTY: PostgreSQL backup file is empty.")
                self._sha256(temp_path)
                temp_path.rename(backup_path)
            except Exception:
                temp_path.unlink(missing_ok=True)
                raise
            return BackupCreateResponse(backup_path=str(backup_path.resolve()), created_at=datetime.now(timezone.utc))
        finally:
            self._release_operation_lock()

    def restore_backup(self, db: Session, backup_path: str) -> BackupRestoreResponse:
        source_path = self._resolve_backup_path(backup_path)
        if not source_path.exists():
            raise NotFoundException("PostgreSQL backup file not found")

        self._acquire_operation_lock()
        try:
            safety_backup = self._create_backup_unlocked(db).backup_path
            pg_restore = self._tool_path("pg_restore")
            self._run_pg_command([pg_restore, "--list", str(source_path)])
            command = [
                pg_restore,
                *self._base_pg_args(),
                "-d",
                self._database_url().database or settings.database_name,
                "--clean",
                "--if-exists",
                "--no-owner",
                str(source_path),
            ]
            self._run_pg_command(command)
            return BackupRestoreResponse(emergency_backup_path=safety_backup)
        finally:
            self._release_operation_lock()

    def export_to_usb(self, db: Session, usb_path: str | None = None) -> BackupExportResponse:
        del db
        latest = self._backup_files()
        if not latest:
            raise NotFoundException("No PostgreSQL backup file is available to export.")
        target_dir = Path(usb_path) if usb_path else self.backup_folder / "usb"
        target_dir.mkdir(parents=True, exist_ok=True)
        source_path = latest[0]
        export_path = target_dir / source_path.name
        temp_path = export_path.with_suffix(".dump.tmp")
        shutil.copy2(source_path, temp_path)
        if temp_path.stat().st_size != source_path.stat().st_size:
            temp_path.unlink(missing_ok=True)
            raise BadRequestException("USB_COPY_FAILED: Copied backup size does not match source.")
        if self._sha256(temp_path) != self._sha256(source_path):
            temp_path.unlink(missing_ok=True)
            raise BadRequestException("USB_CHECKSUM_MISMATCH")
        temp_path.replace(export_path)
        return BackupExportResponse(export_path=str(export_path.resolve()))

    def _create_backup_unlocked(self, db: Session) -> BackupCreateResponse:
        del db
        pg_dump = self._tool_path("pg_dump")
        backup_path, temp_path = self._unique_backup_paths()
        backup_path.parent.mkdir(parents=True, exist_ok=True)
        command = [
            pg_dump,
            *self._base_pg_args(),
            "-d",
            self._database_url().database or settings.database_name,
            "-F",
            "c",
            "-f",
            str(temp_path),
        ]
        try:
            self._run_pg_command(command)
            if not temp_path.exists() or temp_path.stat().st_size == 0:
                raise BadRequestException("BACKUP_FILE_EMPTY: PostgreSQL backup file is empty.")
            self._sha256(temp_path)
            temp_path.rename(backup_path)
        except Exception:
            temp_path.unlink(missing_ok=True)
            raise
        return BackupCreateResponse(backup_path=str(backup_path.resolve()), created_at=datetime.now(timezone.utc))
