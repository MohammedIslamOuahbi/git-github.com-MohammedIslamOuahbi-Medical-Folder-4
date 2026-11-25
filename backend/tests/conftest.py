from __future__ import annotations

import os
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")
os.environ.setdefault("IBNSINA_INSTALLATION_PROFILE", "mobile_device")
if not TEST_DATABASE_URL or not TEST_DATABASE_URL.startswith(("postgresql://", "postgresql+psycopg://")):
    raise RuntimeError(
        "Set TEST_DATABASE_URL to a dedicated PostgreSQL test database before running tests. "
        "Example: postgresql+psycopg://user:password@localhost:5432/medical_folder_test"
    )

if TEST_DATABASE_URL == os.environ.get("DATABASE_URL"):
    raise RuntimeError("TEST_DATABASE_URL must not point to the production application database.")

test_url = make_url(TEST_DATABASE_URL)
test_database_name = (test_url.database or "").lower()
dangerous_database_names = {"postgres", "medical_db", "production", "template0", "template1"}
if test_database_name in dangerous_database_names:
    raise RuntimeError(
        f"Refusing to run tests against dangerous database name '{test_database_name}'. "
        "Use a dedicated database whose name ends with '_test' or contains 'test'."
    )

if "test" not in test_database_name:
    raise RuntimeError(
        f"Refusing to run tests against database '{test_database_name}'. "
        "Use a dedicated PostgreSQL database whose name ends with '_test' or contains 'test'."
    )

os.environ["DATABASE_URL"] = TEST_DATABASE_URL

from app.database import Base  # noqa: E402
from app.dependencies.database import get_db  # noqa: E402
from app.main import app  # noqa: E402

engine = create_engine(
    TEST_DATABASE_URL,
    future=True,
    pool_pre_ping=True,
)


@pytest.fixture(scope="session", autouse=True)
def setup_database():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    connection = engine.connect()
    transaction = connection.begin()
    TestingSessionLocal = sessionmaker(bind=connection, autoflush=False, autocommit=False, future=True)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture
def client(db_session: Session) -> Generator[TestClient, None, None]:
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
