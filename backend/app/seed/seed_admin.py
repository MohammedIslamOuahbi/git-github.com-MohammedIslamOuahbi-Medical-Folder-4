from __future__ import annotations

from app.database import SessionLocal
from app.services.auth_service import AuthService

SEED_USERS = [
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


def seed_admin() -> None:
    with SessionLocal() as db:
        service = AuthService()
        for user in SEED_USERS:
            service.create_platform_user(
                db,
                first_name=user["first_name"],
                last_name=user["last_name"],
                email=user["email"],
                password=user["password"],
                role=user["role"],
            )


if __name__ == "__main__":
    seed_admin()
