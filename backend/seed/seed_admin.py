from __future__ import annotations

import re
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import select  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.models.user import User  # noqa: E402
from app.services.auth_service import AuthService  # noqa: E402


USERS_TO_INSERT: list[dict[str, str]] = [
    {
        "first_name": "Babziz",
        "last_name": "Saleh",
        "email": "babzizsaleh@ibnsina.com",
        "password": "babziz saleh",
        "role": "super_admin",
    },
    {
        "first_name": "Babziz",
        "last_name": "Mostafa",
        "email": "babzizmostafa@ibnsina.com",
        "password": "babziz mostafa",
        "role": "admin",
    },
    {
        "first_name": "Ouahbi",
        "last_name": "Mohammed Islam",
        "email": "ouahbimohammedislam@ibnsina.com",
        "password": "mohammed islam",
        "role": "admin",
    },
]


def normalize_value(value: str) -> str:
    value = unicodedata.normalize("NFKD", value)
    value = "".join(
        char for char in value
        if not unicodedata.combining(char)
    )
    value = value.lower().strip()
    value = re.sub(r"[^a-z0-9@._-]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def user_key(email: str) -> str:
    return normalize_value(email)


def seed_admin() -> tuple[int, int]:
    inserted = 0
    updated = 0

    with SessionLocal() as db:
        service = AuthService()

        existing_users = db.scalars(select(User)).all()

        existing_by_key = {
            user_key(user.email): user
            for user in existing_users
        }

        for payload in USERS_TO_INSERT:
            first_name = payload["first_name"]
            last_name = payload["last_name"]
            email = payload["email"]
            password = payload["password"]
            role = payload["role"]

            key = user_key(email)
            existing = existing_by_key.get(key)

            if existing:
                existing.first_name = first_name
                existing.last_name = last_name
                existing.email = email
                existing.role = role

                # Keep the existing password.
                # Do not reset it every time the seed runs.

                updated += 1
                continue

            service.create_platform_user(
                db,
                first_name=first_name,
                last_name=last_name,
                email=email,
                password=password,
                role=role,
            )

            inserted += 1

        db.commit()

    print(f"Inserted: {inserted}")
    print(f"Updated: {updated}")

    return inserted, updated


if __name__ == "__main__":
    seed_admin()