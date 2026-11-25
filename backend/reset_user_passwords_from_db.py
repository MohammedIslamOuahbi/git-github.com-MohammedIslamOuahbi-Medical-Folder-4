from __future__ import annotations

from app.database import SessionLocal
from app.models.user import User
from app.utils.password import hash_password


KNOWN_PASSWORDS: dict[str, str] = {
    "babzizsaleh@ibnsina.com": "babziz saleh",
    "babzizmostafa@ibnsina.com": "babziz mostafa",
    "ouahbimohammedislam@ibnsina.com": "mohammed islam",
}

DEMO_PASSWORD = "demo12345"


def resolve_password(user: User) -> str:
    email = (user.email or "").strip().lower()
    if email in KNOWN_PASSWORDS:
        return KNOWN_PASSWORDS[email]
    if email.endswith("@demo.ibnsina.com"):
        return DEMO_PASSWORD
    return email


def main() -> int:
    updated = 0
    with SessionLocal() as db:
        users = db.query(User).filter(User.deleted_at.is_(None), User.is_active.is_(True)).order_by(User.id.asc()).all()
        for user in users:
            next_password = resolve_password(user)
            user.password_hash = hash_password(next_password)
            updated += 1
            print(f"[password-reset] {user.email} -> {next_password}")

        db.commit()

    print(f"[password-reset] Updated {updated} active users.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
