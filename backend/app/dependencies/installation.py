from __future__ import annotations

from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.enums import InstallationProfile, InstallationProvisioningStatus
from app.dependencies.auth import get_optional_current_user
from app.dependencies.database import get_db
from app.exceptions import ForbiddenException
from app.models.installation_state import InstallationState
from app.models.user import User
from app.services.installation_service import installation_service


def _forbidden(
    db: Session,
    *,
    user: User | None,
    reason: str,
    requested_profile: str | None = None,
    configured_profile: str | None = None,
    required_capability: str | None = None,
) -> None:
    installation_service.record_audit_event(
        db,
        action="forbidden_profile_operation_attempted",
        user=user,
        details={
            "reason": reason,
            "requested_profile": requested_profile,
            "configured_profile": configured_profile,
            "required_capability": required_capability,
        },
    )


def require_installation_profile(*profiles: InstallationProfile):
    allowed_profiles = {profile.value for profile in profiles}

    def dependency(
        db: Session = Depends(get_db),
        current_user: User | None = Depends(get_optional_current_user),
    ) -> InstallationState:
        state = installation_service.require_configured_state(db)
        configured_profile = state.profile_enum
        if (
            state.provisioning_status_enum != InstallationProvisioningStatus.CONFIGURED
            or configured_profile is None
            or configured_profile.value not in allowed_profiles
        ):
            _forbidden(
                db,
                user=current_user,
                reason="installation_profile_forbidden",
                requested_profile="|".join(sorted(allowed_profiles)),
                configured_profile=configured_profile.value if configured_profile else None,
            )
            raise ForbiddenException("INSTALLATION_PROFILE_FORBIDDEN")
        return state

    return dependency


def require_installation_capability(capability: str):
    def dependency(
        db: Session = Depends(get_db),
        current_user: User | None = Depends(get_optional_current_user),
    ) -> InstallationState:
        state = installation_service.require_configured_state(db)
        configured_profile = state.profile_enum
        if configured_profile is None:
            _forbidden(
                db,
                user=current_user,
                reason="installation_profile_forbidden",
                configured_profile=None,
                required_capability=capability,
            )
            raise ForbiddenException("INSTALLATION_PROFILE_FORBIDDEN")
        if not installation_service.has_capability(db, capability):
            _forbidden(
                db,
                user=current_user,
                reason="capability_not_available",
                configured_profile=configured_profile.value,
                required_capability=capability,
            )
            raise ForbiddenException("CAPABILITY_NOT_AVAILABLE")
        return state

    return dependency


def require_central_authority(
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
) -> InstallationState:
    state = installation_service.require_configured_state(db)
    configured_profile = state.profile_enum
    if configured_profile != InstallationProfile.CENTRAL_SERVER or not installation_service.has_capability(db, "central_authority"):
        _forbidden(
            db,
            user=current_user,
            reason="central_authority_required",
            configured_profile=configured_profile.value if configured_profile else None,
            required_capability="central_authority",
        )
        raise ForbiddenException("CENTRAL_AUTHORITY_REQUIRED")
    return state


def require_mobile_device(
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
) -> InstallationState:
    state = installation_service.require_configured_state(db)
    configured_profile = state.profile_enum
    if configured_profile != InstallationProfile.MOBILE_DEVICE:
        _forbidden(
            db,
            user=current_user,
            reason="installation_profile_forbidden",
            requested_profile=InstallationProfile.MOBILE_DEVICE.value,
            configured_profile=configured_profile.value if configured_profile else None,
        )
        raise ForbiddenException("INSTALLATION_PROFILE_FORBIDDEN")
    return state
