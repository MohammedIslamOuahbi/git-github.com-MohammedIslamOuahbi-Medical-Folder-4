from __future__ import annotations

import subprocess

import pytest

from app.exceptions import BadRequestException
from app.services.backup_service import BackupService


def test_restore_rejects_backup_path_outside_configured_folder(tmp_path):
    service = BackupService(backup_folder=str(tmp_path / "backups"))
    outside_dump = tmp_path / "outside.dump"
    outside_dump.write_bytes(b"not a real dump")

    with pytest.raises(BadRequestException, match="inside the configured backup folder"):
        service.restore_backup(db=None, backup_path=str(outside_dump))  # type: ignore[arg-type]


def test_restore_rejects_non_dump_file_inside_backup_folder(tmp_path):
    service = BackupService(backup_folder=str(tmp_path / "backups"))
    invalid_file = service.backup_folder / "backup.sql"
    invalid_file.write_text("-- not accepted", encoding="utf-8")

    with pytest.raises(BadRequestException, match="Only PostgreSQL .dump"):
        service.restore_backup(db=None, backup_path=str(invalid_file))  # type: ignore[arg-type]


def test_pg_command_uses_argument_array_without_shell(monkeypatch, tmp_path):
    service = BackupService(backup_folder=str(tmp_path / "backups"))
    captured: dict[str, object] = {}

    def fake_run(command, **kwargs):
        captured["command"] = command
        captured["shell"] = kwargs.get("shell")
        captured["env"] = kwargs.get("env")
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(subprocess, "run", fake_run)

    service._run_pg_command(["pg_dump", "-d", "medical_folder"])

    assert captured["command"] == ["pg_dump", "-d", "medical_folder"]
    assert captured["shell"] is False
    assert isinstance(captured["env"], dict)


def test_create_backup_prevents_concurrent_operation(monkeypatch, tmp_path):
    service = BackupService(backup_folder=str(tmp_path / "backups"))
    monkeypatch.setattr(service, "_tool_path", lambda _: "pg_dump")
    monkeypatch.setattr(service, "_run_pg_command", lambda _: None)

    assert service._operation_lock.acquire(blocking=False)
    try:
        with pytest.raises(BadRequestException, match="already running"):
            service.create_backup(db=None)  # type: ignore[arg-type]
    finally:
        service._operation_lock.release()


def test_unique_backup_paths_adds_suffix_without_overwriting_existing_file(monkeypatch, tmp_path):
    service = BackupService(backup_folder=str(tmp_path / "backups"))
    monkeypatch.setattr(service, "_backup_name", lambda: "medical_backup_2026-07-14_10-00-00.dump")
    first_backup, first_temp = service._unique_backup_paths()
    first_backup.write_bytes(b"completed backup")

    second_backup, second_temp = service._unique_backup_paths()

    assert first_backup != second_backup
    assert first_temp != second_temp
    assert second_backup.name == "medical_backup_2026-07-14_10-00-00_01.dump"
    assert second_temp.name == "medical_backup_2026-07-14_10-00-00_01.dump.tmp"
    assert first_backup.read_bytes() == b"completed backup"


def test_backup_files_ignore_empty_and_temp_files(tmp_path):
    service = BackupService(backup_folder=str(tmp_path / "backups"))
    valid_backup = service.backup_folder / "medical_backup_2026-07-14_10-00-00.dump"
    empty_backup = service.backup_folder / "medical_backup_2026-07-14_10-00-01.dump"
    temp_backup = service.backup_folder / "medical_backup_2026-07-14_10-00-02.dump.tmp"
    valid_backup.write_bytes(b"completed backup")
    empty_backup.write_bytes(b"")
    temp_backup.write_bytes(b"partial backup")

    backups = service._backup_files()

    assert backups == [valid_backup]
