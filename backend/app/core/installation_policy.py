from __future__ import annotations

from typing import Final

from app.core.enums import InstallationProfile

CapabilityMap = dict[str, bool]

CENTRAL_SERVER_CAPABILITIES: Final[CapabilityMap] = {
    "central_authority": True,
    "receive_mission_submissions": True,
    "assign_central_sequence": True,
    "resolve_central_conflicts": True,
    "provide_device_bootstrap": True,
    "create_central_backups": True,
    "run_standalone": True,
    "run_mission_server": False,
    "run_mission_client": False,
    "perform_mission_copy": False,
    "push_to_central": False,
    "pull_from_central": False,
    "manage_registered_devices": True,
}

MOBILE_DEVICE_CAPABILITIES: Final[CapabilityMap] = {
    "central_authority": False,
    "receive_mission_submissions": False,
    "assign_central_sequence": False,
    "resolve_central_conflicts": False,
    "provide_device_bootstrap": False,
    "create_central_backups": False,
    "run_standalone": True,
    "run_mission_server": True,
    "run_mission_client": True,
    "perform_mission_copy": True,
    "push_to_central": True,
    "pull_from_central": True,
    "manage_registered_devices": False,
}

PROFILE_CAPABILITIES: Final[dict[InstallationProfile, CapabilityMap]] = {
    InstallationProfile.CENTRAL_SERVER: CENTRAL_SERVER_CAPABILITIES,
    InstallationProfile.MOBILE_DEVICE: MOBILE_DEVICE_CAPABILITIES,
}


def capabilities_for_profile(profile: InstallationProfile | None) -> CapabilityMap:
    if profile is None:
        return {key: False for key in CENTRAL_SERVER_CAPABILITIES}
    return PROFILE_CAPABILITIES[profile].copy()


def profile_has_capability(profile: InstallationProfile | None, capability: str) -> bool:
    return bool(capabilities_for_profile(profile).get(capability, False))
