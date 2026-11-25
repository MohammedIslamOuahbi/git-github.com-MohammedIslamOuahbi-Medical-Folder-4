from __future__ import annotations

from app.database import SessionLocal
from app.services.permission_service import permission_service


def seed_permissions() -> None:
    with SessionLocal() as db:
        permission_service.ensure_seed_data(db, sync_role_defaults=True)
        db.commit()


if __name__ == "__main__":
    seed_permissions()
