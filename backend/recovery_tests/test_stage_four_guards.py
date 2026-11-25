"""Static guard checks for direct SQL transport bypasses."""
from pathlib import Path

root = Path(__file__).resolve().parents[1]
source = (root / "app" / "services" / "central_sync_service.py").read_text(encoding="utf-8")
start = source.index("    def push(")
body = source[start:source.index("    def ", start + 10)]
assert body.index('suspend_for_data_safety("legacy_central_push_apply")') < body.index("self.authenticate_device")
assert "db.execute(statement.on_conflict_do_update" in body
print("PASS direct central SQL apply is suspended before authentication/write")
