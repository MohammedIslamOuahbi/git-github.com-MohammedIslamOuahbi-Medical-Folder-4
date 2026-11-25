from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, inspect, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.core.permission_registry import PERMISSION_CODES
from app.core.security import hash_password
from app.models.application_initialization import ApplicationInitialization
from app.models.medical_test import MedicalTest
from app.models.permission import Permission
from app.models.user import User
from app.seed.seed_tests import DEFAULT_TESTS
from app.services.permission_service import permission_service


REFERENCE_DATA_VERSION = 1
INITIALIZATION_VERSION = 1
logger = get_logger("app.application_bootstrap")


@dataclass(slots=True)
class InitialUserPayload:
    first_name: str
    last_name: str
    email: str
    password: str
    phone: str | None = None
    qualification: str | None = None


@dataclass(slots=True)
class BootstrapStageResult:
    stage: str
    seed_name: str
    model_table: str
    operation: str
    started: bool = True
    completed: bool = False
    inserted_count: int = 0
    updated_count: int = 0
    skipped_count: int = 0
    error_type: str | None = None
    error_message: str | None = None
    sqlstate: str | None = None


@dataclass(slots=True)
class ApplicationBootstrapResult:
    success: bool
    already_initialized: bool
    stages: list[BootstrapStageResult] = field(default_factory=list)
    inserted_count: int = 0
    updated_count: int = 0
    skipped_count: int = 0
    failure_code: str | None = None
    failure_stage: str | None = None
    created_user_email: str | None = None
    initialization_completed: bool = False
    has_super_admin: bool = False
    reference_data_seeded: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "already_initialized": self.already_initialized,
            "stages": [asdict(stage) for stage in self.stages],
            "inserted_count": self.inserted_count,
            "updated_count": self.updated_count,
            "skipped_count": self.skipped_count,
            "failure_code": self.failure_code,
            "failure_stage": self.failure_stage,
            "created_user_email": self.created_user_email,
            "initialization_completed": self.initialization_completed,
            "has_super_admin": self.has_super_admin,
            "reference_data_seeded": self.reference_data_seeded,
        }


class ApplicationBootstrapError(ValueError):
    def __init__(
        self,
        *,
        code: str,
        stage: str,
        message: str,
        error_type: str | None = None,
        sqlstate: str | None = None,
    ) -> None:
        super().__init__(code)
        self.code = code
        self.stage = stage
        self.message = message
        self.error_type = error_type
        self.sqlstate = sqlstate

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": False,
            "code": self.code,
            "stage": self.stage,
            "error_type": self.error_type,
            "sqlstate": self.sqlstate,
            "message": self.message,
        }


class ApplicationSeedService:
    def _has_initialization_table(self, db: Session) -> bool:
        try:
            return inspect(db.bind).has_table("application_initialization")  # type: ignore[arg-type]
        except Exception:
            return False

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    def _normalise_email(self, value: str) -> str:
        normalized = (value or "").strip().lower()
        if not normalized or "@" not in normalized or normalized.startswith("@") or normalized.endswith("@"):
            raise ValueError("INITIAL_USER_CREATION_FAILED")
        return normalized

    def _validate_password(self, value: str) -> None:
        password = value or ""
        if len(password) < 10:
            raise ValueError("INITIAL_USER_CREATION_FAILED")
        has_alpha = any(ch.isalpha() for ch in password)
        has_digit = any(ch.isdigit() for ch in password)
        if not has_alpha or not has_digit:
            raise ValueError("INITIAL_USER_CREATION_FAILED")

    def _description(self, fields: list[str]) -> str:
        return json.dumps({"type": "dynamic_medical_test", "fields": fields}, ensure_ascii=False)

    def _state_row(self, db: Session) -> ApplicationInitialization | None:
        if not self._has_initialization_table(db):
            return None
        state = db.get(ApplicationInitialization, 1)
        if state is None:
            state = ApplicationInitialization(
                id=1,
                initialization_version=INITIALIZATION_VERSION,
                reference_data_version=REFERENCE_DATA_VERSION,
                initialization_status="PENDING",
                last_verified_at=self._now(),
            )
            db.add(state)
            db.flush()
        return state

    def _sqlstate(self, exc: BaseException) -> str | None:
        for candidate in [getattr(exc, "orig", None), exc]:
            sqlstate = getattr(candidate, "sqlstate", None)
            if sqlstate:
                return str(sqlstate)
            pgcode = getattr(candidate, "pgcode", None)
            if pgcode:
                return str(pgcode)
        return None

    def _stage_started(self, stage: BootstrapStageResult) -> None:
        logger.info(
            "application_bootstrap.seed_started",
            extra={
                "stage": stage.stage,
                "seed_name": stage.seed_name,
                "table": stage.model_table,
                "operation": stage.operation,
                "started": True,
            },
        )

    def _stage_completed(self, stage: BootstrapStageResult) -> None:
        logger.info(
            "application_bootstrap.seed_completed",
            extra={
                "stage": stage.stage,
                "seed_name": stage.seed_name,
                "table": stage.model_table,
                "operation": stage.operation,
                "completed": stage.completed,
                "inserted_count": stage.inserted_count,
                "updated_count": stage.updated_count,
                "skipped_count": stage.skipped_count,
            },
        )

    def _stage_failed(self, stage: BootstrapStageResult, exc: BaseException) -> None:
        logger.exception(
            "application_bootstrap.seed_failed",
            extra={
                "stage": stage.stage,
                "seed_name": stage.seed_name,
                "table": stage.model_table,
                "operation": stage.operation,
                "error_type": type(exc).__name__,
                "error_message": str(exc),
                "sqlstate": self._sqlstate(exc),
            },
        )

    def _run_stage(
        self,
        result: ApplicationBootstrapResult,
        *,
        stage: str,
        seed_name: str,
        model_table: str,
        operation: str,
        fn,
    ):
        stage_result = BootstrapStageResult(
            stage=stage,
            seed_name=seed_name,
            model_table=model_table,
            operation=operation,
        )
        result.stages.append(stage_result)
        self._stage_started(stage_result)
        try:
            payload = fn()
            if isinstance(payload, dict):
                stage_result.inserted_count = int(payload.get("inserted_count", 0))
                stage_result.updated_count = int(payload.get("updated_count", 0))
                stage_result.skipped_count = int(payload.get("skipped_count", 0))
            stage_result.completed = True
            result.inserted_count += stage_result.inserted_count
            result.updated_count += stage_result.updated_count
            result.skipped_count += stage_result.skipped_count
            self._stage_completed(stage_result)
            return payload
        except Exception as exc:
            stage_result.error_type = type(exc).__name__
            stage_result.error_message = str(exc)
            stage_result.sqlstate = self._sqlstate(exc)
            self._stage_failed(stage_result, exc)
            raise

    def _seed_permissions(self, db: Session) -> dict[str, int]:
        before_count = int(db.scalar(select(func.count(Permission.id))) or 0)
        permission_service.ensure_seed_data(db, sync_role_defaults=True)
        after_count = int(db.scalar(select(func.count(Permission.id))) or 0)
        inserted = max(after_count - before_count, 0)
        skipped = max(len(PERMISSION_CODES) - inserted, 0)
        return {"inserted_count": inserted, "updated_count": 0, "skipped_count": skipped}

    def _seed_medical_tests(self, db: Session) -> dict[str, int]:
        inserted = 0
        updated = 0
        skipped = 0
        for payload in DEFAULT_TESTS:
            name = str(payload["name"])
            section = str(payload["section"])
            description = self._description(list(payload["fields"]))
            existing = db.scalar(select(MedicalTest).where(MedicalTest.name == name, MedicalTest.section == section))
            if existing is not None:
                changed = False
                for attr, value in {
                    "category": section,
                    "description": description,
                    "requires_doctor_review": False,
                    "is_active": True,
                }.items():
                    if getattr(existing, attr) != value:
                        setattr(existing, attr, value)
                        changed = True
                if changed:
                    updated += 1
                else:
                    skipped += 1
                continue
            db.add(
                MedicalTest(
                    name=name,
                    section=section,
                    category=section,
                    description=description,
                    requires_doctor_review=False,
                    is_active=True,
                )
            )
            inserted += 1
        db.flush()
        return {"inserted_count": inserted, "updated_count": updated, "skipped_count": skipped}

    def _create_first_user(self, db: Session, payload: InitialUserPayload) -> tuple[User, bool]:
        email = self._normalise_email(payload.email)
        existing = db.scalar(select(User).where(func.lower(User.email) == email, User.deleted_at.is_(None)))
        if existing is not None:
            return existing, False
        self._validate_password(payload.password)
        user = User(
            first_name=payload.first_name.strip(),
            last_name=payload.last_name.strip(),
            email=email,
            password_hash=hash_password(payload.password),
            role="super_admin",
            phone=(payload.phone or "").strip() or None,
            qualification=(payload.qualification or "").strip() or None,
            is_active=True,
        )
        db.add(user)
        db.flush()
        return user, True

    def _reference_data_counts(self, db: Session) -> dict[str, int]:
        return {
            "permission_count": int(db.scalar(select(func.count(Permission.id))) or 0),
            "tests_count": int(db.scalar(select(func.count(MedicalTest.id))) or 0),
            "required_permissions": len(PERMISSION_CODES),
            "required_tests": len(DEFAULT_TESTS),
        }

    def _verify_reference_data(self, db: Session) -> bool:
        counts = self._reference_data_counts(db)
        return (
            counts["permission_count"] >= counts["required_permissions"]
            and counts["tests_count"] >= counts["required_tests"]
        )

    def _build_status_payload(self, db: Session) -> dict[str, object]:
        state = db.get(ApplicationInitialization, 1) if self._has_initialization_table(db) else None
        users_count = int(db.scalar(select(func.count(User.id))) or 0)
        super_admin_count = int(
            db.scalar(select(func.count(User.id)).where(func.lower(User.role) == "super_admin", User.deleted_at.is_(None))) or 0
        )
        reference_data_seeded = self._verify_reference_data(db)
        initialization_completed = bool(
            state
            and state.initialization_status == "COMPLETED"
            and users_count > 0
            and super_admin_count > 0
            and reference_data_seeded
        )
        return {
            "database_ready": True,
            "alembic_at_head": True,
            "has_users": users_count > 0,
            "has_super_admin": super_admin_count > 0,
            "reference_data_seeded": reference_data_seeded,
            "initialization_completed": initialization_completed,
            "requires_initial_setup": not initialization_completed,
            "initialization_status": state.initialization_status if state else "PENDING",
            "initialization_version": state.initialization_version if state else INITIALIZATION_VERSION,
            "reference_data_version": state.reference_data_version if state else REFERENCE_DATA_VERSION,
        }

    def status(self, db: Session) -> dict[str, object]:
        return self._build_status_payload(db)

    def _mark_failed_state(self, db: Session) -> None:
        if not self._has_initialization_table(db):
            return
        with db.begin_nested():
            state = self._state_row(db)
            if state is not None:
                state.initialization_status = "FAILED"
                state.last_verified_at = self._now()
                db.add(state)
                db.flush()

    def _wrap_failure(self, *, stage: str, exc: BaseException) -> ApplicationBootstrapError:
        if isinstance(exc, ApplicationBootstrapError):
            return exc
        code = "INITIAL_REFERENCE_DATA_FAILED" if stage != "initial_user" else "INITIAL_USER_CREATION_FAILED"
        return ApplicationBootstrapError(
            code=code,
            stage=stage,
            message="Initial reference data creation failed." if stage != "initial_user" else "Initial user creation failed.",
            error_type=type(exc).__name__,
            sqlstate=self._sqlstate(exc),
        )

    def ensure_reference_data(self, db: Session) -> dict[str, Any]:
        result = ApplicationBootstrapResult(success=False, already_initialized=False)
        preexisting = self._build_status_payload(db)
        try:
            with db.begin_nested():
                self._run_stage(
                    result,
                    stage="installation_state",
                    seed_name="application_initialization",
                    model_table="application_initialization",
                    operation="upsert",
                    fn=lambda: self._prepare_state(db),
                )
                self._run_stage(
                    result,
                    stage="default_permissions",
                    seed_name="permissions",
                    model_table="permissions",
                    operation="upsert",
                    fn=lambda: self._seed_permissions(db),
                )
                self._run_stage(
                    result,
                    stage="medical_tests",
                    seed_name="medical_tests",
                    model_table="medical_tests",
                    operation="upsert",
                    fn=lambda: self._seed_medical_tests(db),
                )
                self._run_stage(
                    result,
                    stage="final_verification",
                    seed_name="reference_data",
                    model_table="permissions,medical_tests",
                    operation="verify",
                    fn=lambda: self._final_verify_reference_data(db),
                )
                self._complete_state(db, initialized_by_user_id=None)
            db.commit()
        except Exception as exc:
            db.rollback()
            self._mark_failed_state(db)
            db.commit()
            raise self._wrap_failure(stage=self._failed_stage(result), exc=exc) from exc

        payload = self._build_status_payload(db)
        result.success = True
        result.already_initialized = bool(preexisting["reference_data_seeded"])
        result.initialization_completed = bool(payload["initialization_completed"])
        result.has_super_admin = bool(payload["has_super_admin"])
        result.reference_data_seeded = bool(payload["reference_data_seeded"])
        return result.to_dict() | payload

    def _prepare_state(self, db: Session) -> dict[str, int]:
        state = self._state_row(db)
        if state is not None:
            state.initialization_version = INITIALIZATION_VERSION
            state.reference_data_version = REFERENCE_DATA_VERSION
            state.initialization_status = "IN_PROGRESS"
            state.last_verified_at = self._now()
            db.add(state)
            db.flush()
        return {"inserted_count": 0, "updated_count": 1 if state is not None else 0, "skipped_count": 0}

    def _complete_state(self, db: Session, initialized_by_user_id: int | None) -> None:
        state = self._state_row(db)
        if state is not None:
            state.initialization_status = "COMPLETED"
            if state.initialized_at is None:
                state.initialized_at = self._now()
            state.last_verified_at = self._now()
            if initialized_by_user_id is not None:
                state.initialized_by_user_id = initialized_by_user_id
            db.add(state)
            db.flush()

    def _final_verify_reference_data(self, db: Session) -> dict[str, int]:
        db.flush()
        counts = self._reference_data_counts(db)
        if counts["permission_count"] < counts["required_permissions"] or counts["tests_count"] < counts["required_tests"]:
            raise RuntimeError(
                "REFERENCE_DATA_COUNTS_MISMATCH: "
                f"permissions={counts['permission_count']}/{counts['required_permissions']} "
                f"medical_tests={counts['tests_count']}/{counts['required_tests']}"
            )
        return {"inserted_count": 0, "updated_count": 0, "skipped_count": counts["permission_count"] + counts["tests_count"]}

    def _failed_stage(self, result: ApplicationBootstrapResult) -> str:
        for stage in reversed(result.stages):
            if stage.error_type is not None:
                return stage.stage
        return "reference_data"

    def initialize_application(
        self,
        db: Session,
        initial_user: InitialUserPayload | None = None,
    ) -> dict[str, object]:
        result = ApplicationBootstrapResult(success=False, already_initialized=False)
        created_user_email: str | None = None
        created_user_id: int | None = None
        preexisting = self._build_status_payload(db)
        try:
            with db.begin_nested():
                self._run_stage(
                    result,
                    stage="installation_state",
                    seed_name="application_initialization",
                    model_table="application_initialization",
                    operation="upsert",
                    fn=lambda: self._prepare_state(db),
                )

                def initial_user_stage() -> dict[str, int]:
                    nonlocal created_user_email, created_user_id
                    if initial_user is None:
                        existing_users = int(db.scalar(select(func.count(User.id))) or 0)
                        if existing_users == 0:
                            raise ValueError("INITIAL_USER_CREATION_FAILED")
                        return {"inserted_count": 0, "updated_count": 0, "skipped_count": 1}
                    user, created = self._create_first_user(db, initial_user)
                    created_user_email = user.email
                    created_user_id = user.id
                    return {
                        "inserted_count": 1 if created else 0,
                        "updated_count": 0,
                        "skipped_count": 0 if created else 1,
                    }

                self._run_stage(
                    result,
                    stage="initial_user",
                    seed_name="initial_user",
                    model_table="users",
                    operation="upsert",
                    fn=initial_user_stage,
                )
                self._run_stage(
                    result,
                    stage="default_permissions",
                    seed_name="permissions",
                    model_table="permissions",
                    operation="upsert",
                    fn=lambda: self._seed_permissions(db),
                )
                self._run_stage(
                    result,
                    stage="medical_tests",
                    seed_name="medical_tests",
                    model_table="medical_tests",
                    operation="upsert",
                    fn=lambda: self._seed_medical_tests(db),
                )
                self._run_stage(
                    result,
                    stage="final_verification",
                    seed_name="reference_data",
                    model_table="users,permissions,medical_tests",
                    operation="verify",
                    fn=lambda: self._final_verify_application(db),
                )
                self._complete_state(db, initialized_by_user_id=created_user_id)
            db.commit()
        except Exception as exc:
            db.rollback()
            self._mark_failed_state(db)
            db.commit()
            failure = self._wrap_failure(stage=self._failed_stage(result), exc=exc)
            raise failure from exc

        payload = self._build_status_payload(db)
        result.success = True
        result.already_initialized = bool(preexisting["initialization_completed"])
        result.created_user_email = created_user_email
        result.initialization_completed = bool(payload["initialization_completed"])
        result.has_super_admin = bool(payload["has_super_admin"])
        result.reference_data_seeded = bool(payload["reference_data_seeded"])
        return result.to_dict() | payload

    def _final_verify_application(self, db: Session) -> dict[str, int]:
        db.flush()
        counts = self._reference_data_counts(db)
        users_count = int(db.scalar(select(func.count(User.id))) or 0)
        super_admin_count = int(
            db.scalar(select(func.count(User.id)).where(func.lower(User.role) == "super_admin", User.deleted_at.is_(None))) or 0
        )
        if users_count == 0 or super_admin_count == 0:
            raise RuntimeError(
                f"INITIAL_USER_COUNTS_MISMATCH: users={users_count} super_admins={super_admin_count}"
            )
        if counts["permission_count"] < counts["required_permissions"] or counts["tests_count"] < counts["required_tests"]:
            raise RuntimeError(
                "REFERENCE_DATA_COUNTS_MISMATCH: "
                f"permissions={counts['permission_count']}/{counts['required_permissions']} "
                f"medical_tests={counts['tests_count']}/{counts['required_tests']}"
            )
        return {
            "inserted_count": 0,
            "updated_count": 0,
            "skipped_count": users_count + counts["permission_count"] + counts["tests_count"],
        }
