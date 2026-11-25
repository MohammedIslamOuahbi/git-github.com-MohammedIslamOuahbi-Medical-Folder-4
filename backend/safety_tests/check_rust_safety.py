"""Compile only real backup barrier functions with rustc; no Cargo downloads/Tauri startup."""
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
source = (ROOT / "frontend/src-tauri/src/main.rs").read_text(encoding="utf-8")


def item(start):
    begin = source.index(start)
    brace = source.index("{", begin)
    depth = 1
    end = brace + 1
    while depth:
        depth += (source[end] == "{") - (source[end] == "}")
        end += 1
    return source[begin:end]


code = "\n".join([
    "#![allow(dead_code)]\nuse std::{fs, path::Path};\nstruct AppHandle;",
    "fn file_modified_iso(_: &Path) -> Option<String> { None }",
    item("struct PostgresBackupFile {"),
    item("struct PostgresBackupOperationResult {"),
    item("fn suspended_backup_result()"),
    item("fn create_postgres_backup("),
    item("fn file_to_backup("),
    r'''
    #[test]
    fn backup_command_returns_failure_without_a_runtime_or_file() {
        let result = create_postgres_backup(AppHandle).unwrap();
        assert!(!result.success);
        assert_eq!(result.operation_state, "OPERATION_SUSPENDED_FOR_DATA_SAFETY");
        assert!(result.backup.is_none());
        assert!(result.safety_backup.is_none());
        assert!(result.destination_path.is_none());
        assert!(result.checksum_sha256.is_none());
    }
    #[test]
    fn placeholder_stays_on_disk_but_is_not_a_backup() {
        let path = std::env::current_dir().unwrap().join("postgres-backup-test.txt");
        fs::write(&path, "synthetic placeholder").unwrap();
        assert!(file_to_backup(&path).is_none());
        assert_eq!(fs::read_to_string(&path).unwrap(), "synthetic placeholder");
    }
    ''',
])

with tempfile.TemporaryDirectory(prefix="medical-rust-safety-") as folder:
    folder = Path(folder)
    test_source = folder / "safety.rs"
    test_source.write_text(code, encoding="utf-8")
    executable = folder / "safety.exe"
    subprocess.run(["rustc", "--edition=2021", "--test", str(test_source), "-o", str(executable)], check=True)
    subprocess.run([str(executable)], cwd=folder, check=True)
