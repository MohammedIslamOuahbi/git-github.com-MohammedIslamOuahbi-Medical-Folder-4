from __future__ import annotations

from app.seed.seed_tests import DEFAULT_TESTS, seed_medical_tests


def seed() -> None:
    seed_medical_tests()


if __name__ == "__main__":
    seed()
