from __future__ import annotations

import argparse
import getpass

from sqlalchemy import func, select

from app.database import SessionLocal
from app.exceptions import ConflictException
from app.services.auth_service import AuthService
from app.services.permission_service import permission_service
from app.models.user import User


def _prompt_non_empty(label: str) -> str:
    while True:
        value = input(f"{label}: ").strip()
        if value:
            return value
        print(f"{label} is required.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Create the first Super Admin user safely.")
    parser.parse_args()

    with SessionLocal() as db:
        permission_service.ensure_seed_data(db)
        existing_super_admins = db.scalar(
            select(func.count(User.id)).where(
                User.deleted_at.is_(None),
                User.is_active.is_(True),
                func.lower(User.role) == "super_admin",
            )
        ) or 0
        if existing_super_admins > 0:
            raise ConflictException("An active Super Admin already exists. Use the application to manage additional Super Admins.")

        first_name = _prompt_non_empty("First name")
        last_name = _prompt_non_empty("Last name")
        email = _prompt_non_empty("Email").lower()

        while True:
            password = getpass.getpass("Password: ")
            confirm_password = getpass.getpass("Confirm password: ")
            if not password:
                print("Password is required.")
                continue
            if password != confirm_password:
                print("Passwords do not match.")
                continue
            break

        user = AuthService().create_platform_user(
            db,
            first_name=first_name,
            last_name=last_name,
            email=email,
            password=password,
            role="super_admin",
        )
        print(f"Created Super Admin user #{user.id} for {user.email}.")


if __name__ == "__main__":
    main()
