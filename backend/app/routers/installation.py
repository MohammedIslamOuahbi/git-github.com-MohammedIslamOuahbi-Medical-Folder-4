from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.dependencies.database import get_db
from app.exceptions import BadRequestException
from app.schemas.installation import CentralCompleteRequest, CentralProvisionRequest, MobileProvisionRequest
from app.services.installation_service import installation_service
from app.utils.responses import success_response

router = APIRouter(prefix="/installation", tags=["Installation"])


@router.get("/profile")
def get_installation_profile(db: Session = Depends(get_db)):
    return success_response("Installation profile", installation_service.profile_summary(db))


@router.get("/status")
def get_installation_status(db: Session = Depends(get_db)):
    return success_response("Installation status", installation_service.installation_status(db))


@router.get("/readiness")
def get_installation_readiness(db: Session = Depends(get_db)):
    return success_response("Installation readiness", installation_service.installation_readiness(db))


@router.post("/central/provision")
def provision_central_installation(payload: CentralProvisionRequest, db: Session = Depends(get_db)):
    try:
        state = installation_service.provision_central_installation(
            db,
            server_name=payload.server_name,
            server_code=payload.server_code,
            description=payload.description,
            api_port=payload.api_port,
            backup_directory=payload.backup_directory,
            admin_payload=payload.admin.model_dump(),
        )
    except ValueError as exc:
        raise BadRequestException(str(exc)) from exc
    status = installation_service.installation_status(db)
    return success_response(
        "Central installation provisioned",
        {
            "provisioning_status": state.provisioning_status,
            "stages": status["provisioning_stages"],
            "checks": status["checks"],
        },
    )


@router.post("/central/complete")
def complete_central_installation(payload: CentralCompleteRequest, db: Session = Depends(get_db)):
    try:
        state = installation_service.complete_central_installation(
            db,
            backup_directory=payload.backup_directory,
            retention_policy=payload.retention_policy,
        )
    except ValueError as exc:
        raise BadRequestException(str(exc)) from exc
    return success_response(
        "Central installation completed",
        {
            "provisioning_status": state.provisioning_status,
            "completed_at": state.provisioned_at.isoformat() if state.provisioned_at else None,
        },
    )


@router.post("/mobile/provision")
def provision_mobile_installation(payload: MobileProvisionRequest, db: Session = Depends(get_db)):
    try:
        state = installation_service.provision_mobile_installation(
            db,
            device_name=payload.device_name,
            device_code=payload.device_code,
            description=payload.description,
            central_server_url=payload.central_server_url,
        )
    except ValueError as exc:
        raise BadRequestException(str(exc)) from exc
    status = installation_service.installation_status(db)
    return success_response(
        "Mobile installation provisioned",
        {
            "provisioning_status": state.provisioning_status,
            "checks": status["checks"],
            "device_uuid": str(state.device_uuid) if state.device_uuid else None,
        },
    )
