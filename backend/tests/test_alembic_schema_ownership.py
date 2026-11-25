from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
VERSIONS_DIR = PROJECT_ROOT / "alembic" / "versions"
CREATE_TABLE_PATTERN = re.compile(r'op\.create_table\(\s*"([^"]+)"', re.MULTILINE)


def _table_owners() -> dict[str, list[str]]:
    owners: dict[str, list[str]] = defaultdict(list)
    for path in sorted(VERSIONS_DIR.glob("*.py")):
        content = path.read_text(encoding="utf-8")
        for table_name in CREATE_TABLE_PATTERN.findall(content):
            owners[table_name].append(path.name)
    return dict(owners)


def test_each_table_has_single_creation_migration() -> None:
    duplicates = {
        table_name: files
        for table_name, files in _table_owners().items()
        if len(files) > 1
    }
    assert duplicates == {}


def test_application_initialization_owned_by_expected_migration() -> None:
    owners = _table_owners()
    assert owners["application_initialization"] == [
        "20260718_02_add_application_initialization.py"
    ]


def test_medicine_imports_owned_by_expected_migration() -> None:
    owners = _table_owners()
    assert owners["medicine_imports"] == [
        "20260718_03_create_medicine_catalogue.py"
    ]


def test_initial_schema_migration_excludes_later_owned_tables() -> None:
    migration_path = VERSIONS_DIR / "20260606_01_create_initial_schema.py"
    content = migration_path.read_text(encoding="utf-8")
    for expected in (
        '"client_sync_changes"',
        '"client_local_sync_state"',
        '"client_local_sync_runs"',
        '"prescriptions"',
        '"prescription_items"',
        '"application_initialization"',
        '"medicine_imports"',
        '"medicines"',
        '"medicine_import_errors"',
    ):
        assert expected in content
