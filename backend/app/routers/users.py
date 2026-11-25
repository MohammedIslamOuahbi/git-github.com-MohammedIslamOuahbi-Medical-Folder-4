from __future__ import annotations

from fastapi import APIRouter, Depends, File, Request, UploadFile, status
from fastapi.responses import FileResponse
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.core.audit import build_update_details, create_audit_log
from app.core.permissions import get_effective_permissions
from app.dependencies.auth import get_current_user
from app.dependencies.database import get_db
from app.dependencies.pagination import get_pagination_params
from app.models.user import User
from app.schemas.common import PasswordDeleteRequest
from app.schemas.pagination import PaginationParams
from app.schemas.user import UserCreate, UserRead, UserUpdate
from app.schemas.permission import UserPermissionCopyRequest, UserPermissionUpdateRequest
from app.services.user_signature_service import UserSignatureService
from app.services.permission_service import permission_service
from app.services.user_service import UserService
from app.services.sync_safety import suspend_for_data_safety
from app.utils.responses import success_response

router = APIRouter(prefix="/users", tags=["Users"])
service = UserService()
signature_service = UserSignatureService()


def serialize_user(user: User) -> dict:
    try:
        payload = UserRead.model_validate(user).model_dump()
    except ValidationError:
        # Legacy/demo rows may contain an address that is not RFC-valid (for
        # example an example.invalid address).  Keep the stored value visible
        # without weakening validation for create/update payloads.
        payload = UserRead.model_construct(
            id=user.id,
            first_name=user.first_name,
            last_name=user.last_name,
            email=user.email,
            role=user.role,
            role_code=None,
            phone=user.phone,
            qualification=user.qualification,
            signature_png=user.signature_png,
            signatureImageUrl=None,
            hasSignature=bool(user.signature_path or user.signature_png),
            signatureUploadedAt=user.signature_uploaded_at,
            is_active=user.is_active,
            permissions_version=user.permissions_version,
            last_login=user.last_login,
            uuid=user.uuid,
            sync_version=user.sync_version,
            sync_status=user.sync_status,
            local_id=user.local_id,
            created_at=user.created_at,
            updated_at=user.updated_at,
            deleted_at=user.deleted_at,
            permissions=[],
        ).model_dump()
    payload["role_code"] = permission_service.normalize_role_code(user.role)
    payload["permissions_version"] = user.permissions_version
    payload["permissions"] = get_effective_permissions(user)
    payload.update(signature_service.serialize_signature(user))
    return payload


@router.get("/me/signature")
def get_my_signature(current_user: User = Depends(get_current_user)):
    return success_response("Signature metadata retrieved", signature_service.serialize_signature(current_user))


@router.get("/me/signature/file")
def get_my_signature_file(current_user: User = Depends(get_current_user)):
    file_path = signature_service.get_signature_file_path(current_user)
    return FileResponse(path=file_path, media_type="image/png", filename=file_path.name)


@router.post("/me/signature", status_code=status.HTTP_200_OK)
def upload_my_signature(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service.signature_service.ensure_signature_owner(current_user)
    payload = signature_service.upload_signature(current_user, file)
    current_user.updated_at = current_user.signature_updated_at or current_user.updated_at
    db.add(current_user)
    db.commit()
    db.refresh(current_user)
    payload = signature_service.serialize_signature(current_user)
    return success_response("Signature uploaded", payload)


@router.delete("/me/signature")
def delete_my_signature(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    payload = signature_service.remove_signature(current_user)
    current_user.updated_at = current_user.signature_updated_at or current_user.updated_at
    db.add(current_user)
    db.commit()
    db.refresh(current_user)
    return success_response("Signature removed", payload)


@router.get("")
def list_users(
    params: PaginationParams = Depends(get_pagination_params),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    permission_service.require_permission(current_user, "users.view")
    result = service.list(db, params).model_dump()
    result["items"] = [serialize_user(item) for item in result["items"]]
    return success_response("Users retrieved", result)


@router.post("", status_code=status.HTTP_201_CREATED)
def create_user(
    payload: UserCreate,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    permission_service.require_permission(current_user, "users.create")
    suspend_for_data_safety("users.create")
    item = service.create(db, payload, current_user)
    create_audit_log(db, current_user.id, "create", "user", item.id, request.client.host if request.client else None)
    return success_response("User created", serialize_user(item))


@router.get("/doctors")
def list_doctors(
    params: PaginationParams = Depends(get_pagination_params),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    permission_service.require_permission(current_user, "users.view")
    result = service.list(db, params, role="doctor").model_dump()
    result["items"] = [serialize_user(item) for item in result["items"]]
    return success_response("Doctors retrieved", result)


@router.post("/doctors", status_code=status.HTTP_201_CREATED)
def create_doctor(
    payload: UserCreate,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    permission_service.require_permission(current_user, "users.create")
    suspend_for_data_safety("users.create.doctor")
    item = service.create(db, payload, current_user, role="doctor")
    create_audit_log(db, current_user.id, "create", "doctor", item.id, request.client.host if request.client else None)
    return success_response("Doctor created", serialize_user(item))


@router.get("/assistants")
def list_assistants(
    params: PaginationParams = Depends(get_pagination_params),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    permission_service.require_permission(current_user, "users.view")
    result = service.list(db, params, role="assistant").model_dump()
    result["items"] = [serialize_user(item) for item in result["items"]]
    return success_response("Assistants retrieved", result)


@router.post("/assistants", status_code=status.HTTP_201_CREATED)
def create_assistant(
    payload: UserCreate,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    permission_service.require_permission(current_user, "users.create")
    suspend_for_data_safety("users.create.assistant")
    item = service.create(db, payload, current_user, role="assistant")
    create_audit_log(db, current_user.id, "create", "assistant", item.id, request.client.host if request.client else None)
    return success_response("Assistant created", serialize_user(item))


@router.get("/{user_id}")
def get_user(user_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    permission_service.require_permission(current_user, "users.view")
    return success_response("User retrieved", serialize_user(service.get(db, user_id)))


@router.put("/{user_id}")
def update_user(
    user_id: int,
    payload: UserUpdate,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    permission_service.require_permission(current_user, "users.update")
    before = service.get(db, user_id)
    changes = payload.model_dump(exclude_unset=True)
    details = build_update_details(before, changes)
    item = service.update(db, user_id, payload, current_user)
    create_audit_log(
        db,
        current_user.id,
        "update",
        "user",
        item.id,
        request.client.host if request.client else None,
        details=details,
    )
    return success_response("User updated", serialize_user(item))


@router.delete("/{user_id}")
def delete_user(
    user_id: int,
    payload: PasswordDeleteRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    permission_service.require_permission(current_user, "users.delete")
    item = service.delete(db, user_id, current_user, payload.password)
    create_audit_log(db, current_user.id, "delete", "user", item.id, request.client.host if request.client else None)
    return success_response("User deleted", serialize_user(item))


@router.get("/{user_id}/permissions")
def get_user_permissions(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return success_response("User permissions retrieved", permission_service.get_user_permission_matrix(db, user_id, current_user))


@router.put("/{user_id}/permissions")
def update_user_permissions(
    user_id: int,
    payload: UserPermissionUpdateRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    matrix = permission_service.update_user_permissions(
        db,
        user_id,
        payload,
        current_user,
        request.client.host if request.client else None,
        request.headers.get("user-agent"),
    )
    return success_response("User permissions updated", matrix)


@router.post("/{user_id}/permissions/reset")
def reset_user_permissions(
    user_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    matrix = permission_service.reset_user_permissions(
        db,
        user_id,
        current_user,
        request.client.host if request.client else None,
        request.headers.get("user-agent"),
    )
    return success_response("User permissions reset", matrix)


@router.post("/{target_user_id}/permissions/copy")
def copy_user_permissions(
    target_user_id: int,
    payload: UserPermissionCopyRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    matrix = permission_service.copy_user_permissions(
        db,
        target_user_id,
        payload,
        current_user,
        request.client.host if request.client else None,
        request.headers.get("user-agent"),
    )
    return success_response("User permissions copied", matrix)
