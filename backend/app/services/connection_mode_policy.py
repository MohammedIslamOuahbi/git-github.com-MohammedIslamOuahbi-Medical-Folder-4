from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.enums import ConnectionMode
from app.core.permission_registry import PERMISSION_CODES, PERMISSION_LOOKUP
from app.exceptions import ForbiddenException
from app.models.runtime_config import RuntimeConfig
from app.models.user import User
from app.services.connection_mode_service import connection_mode_service


# CLIENT is a medical-workstation role. This deliberately lists individual
# permissions so new registry entries are denied until reviewed here.
CLIENT_ALLOWED_PERMISSION_CODES = frozenset(
    {
        "workers.view", "workers.create", "workers.update", "workers.delete", "workers.archive", "workers.restore",
        "workers.import", "workers.export", "workers.merge", "workers.view_medical_history", "workers.manage_documents",
        "worker_tests.view", "worker_tests.create", "worker_tests.update", "worker_tests.delete", "worker_tests.validate",
        "worker_tests.invalidate", "worker_tests.print", "worker_tests.export_pdf",
        "medical_visits.view", "medical_visits.create", "medical_visits.update", "medical_visits.delete", "medical_visits.close",
        "medical_visits.reopen", "medical_visits.validate", "medical_visits.view_history",
        "aptitude_certificates.view", "aptitude_certificates.create", "aptitude_certificates.update", "aptitude_certificates.delete",
        "aptitude_certificates.sign", "aptitude_certificates.unsign", "aptitude_certificates.validate", "aptitude_certificates.cancel",
        "aptitude_certificates.print", "aptitude_certificates.export_pdf", "aptitude_certificates.view_history",
        "orientation_certificates.view", "orientation_certificates.create", "orientation_certificates.update", "orientation_certificates.delete",
        "orientation_certificates.sign", "orientation_certificates.unsign", "orientation_certificates.validate", "orientation_certificates.cancel",
        "orientation_certificates.print", "orientation_certificates.export_pdf", "orientation_certificates.view_history",
        "work_stop_certificates.view", "work_stop_certificates.create", "work_stop_certificates.update", "work_stop_certificates.delete",
        "work_stop_certificates.sign", "work_stop_certificates.unsign", "work_stop_certificates.validate", "work_stop_certificates.cancel",
        "work_stop_certificates.extend", "work_stop_certificates.print", "work_stop_certificates.export_pdf", "work_stop_certificates.view_history",
        "prescriptions.view", "prescriptions.create", "prescriptions.update", "prescriptions.delete", "prescriptions.sign",
        "prescriptions.unsign", "prescriptions.validate", "prescriptions.cancel", "prescriptions.print", "prescriptions.export_pdf",
        "prescriptions.view_history",
        "reports.view", "reports.workers", "reports.medical", "reports.campaigns", "reports.companies", "reports.statistics",
        "reports.export_pdf", "reports.export_excel", "reports.print",
        "backups.view", "backups.create", "backups.download",
        "local_network.view", "local_network.view_status",
        "files.view", "files.upload", "files.download", "files.delete",
        "imports.view", "imports.create", "imports.validate", "imports.cancel", "imports.retry", "imports.view_errors",
        "exports.create", "exports.download",
        "companies.view", "branches.view", "drilling_sites.view", "medical_campaigns.view", "medical_tests.view",
        # Administrators can inspect permission diagnostics in every mode.
        # Permission mutations remain subject to the normal mode ceiling.
        "users.view", "users.view_permissions", "roles.view",
    }
)

CLIENT_DENIED_PERMISSION_CODES = frozenset(
    {
        "users.create", "users.update", "users.delete", "users.activate", "users.deactivate", "users.reset_password",
        "users.assign_role", "users.promote_to_super_admin", "users.demote_super_admin", "users.edit_permissions",
        "users.edit_super_admin_permissions", "users.copy_permissions", "users.view_activity", "users.export",
        "users.grant_sensitive_permissions",
        "roles.create", "roles.update", "roles.delete", "roles.activate", "roles.deactivate", "roles.manage_permissions", "roles.clone",
        "companies.create", "companies.update", "companies.delete", "companies.activate", "companies.deactivate",
        "branches.create", "branches.update", "branches.delete", "branches.activate", "branches.deactivate",
        "drilling_sites.create", "drilling_sites.update", "drilling_sites.delete", "drilling_sites.activate", "drilling_sites.deactivate",
        "medical_campaigns.create", "medical_campaigns.update", "medical_campaigns.delete", "medical_campaigns.open", "medical_campaigns.close",
        "medical_campaigns.complete", "medical_campaigns.reopen", "medical_campaigns.assign_doctors", "medical_campaigns.assign_assistants",
        "medical_campaigns.assign_workers", "medical_campaigns.remove_workers", "medical_campaigns.clone", "medical_campaigns.export",
        "medical_campaigns.view_statistics",
        "medical_tests.create", "medical_tests.update", "medical_tests.delete", "medical_tests.activate", "medical_tests.deactivate",
        "medical_tests.configure", "medical_tests.reorder", "medical_tests.manage_templates",
        "backups.restore", "backups.delete", "backups.configure_schedule",
        "workspaces.view", "workspaces.manage",
        "settings.view", "settings.update", "settings.general", "settings.security", "settings.pdf", "settings.certificates",
        "settings.printing", "settings.language", "settings.signatures", "settings.network", "settings.database",
        "audit_logs.view", "audit_logs.export", "audit_logs.view_sensitive",
        "notifications.view", "notifications.create", "notifications.send", "notifications.delete", "notifications.send_to_all", "notifications.send_by_role",
        "sync.view", "sync.start", "sync.retry", "sync.cancel", "sync.force", "sync.resolve_conflicts", "sync.view_logs",
        "sync.manage_devices", "sync.disconnect_device",
        "local_network.start_server", "local_network.stop_server", "local_network.manage_clients", "local_network.disconnect_client",
        "licenses.view", "licenses.activate", "licenses.update", "licenses.deactivate", "licenses.manage_devices",
    }
)


def validate_client_permission_policy() -> None:
    overlap = CLIENT_ALLOWED_PERMISSION_CODES & CLIENT_DENIED_PERMISSION_CODES
    unclassified = PERMISSION_CODES - CLIENT_ALLOWED_PERMISSION_CODES - CLIENT_DENIED_PERMISSION_CODES
    unknown = (CLIENT_ALLOWED_PERMISSION_CODES | CLIENT_DENIED_PERMISSION_CODES) - PERMISSION_CODES
    if overlap or unclassified or unknown:
        raise RuntimeError(
            "CLIENT permission policy must explicitly classify every registry permission "
            f"(overlap={sorted(overlap)}, unclassified={sorted(unclassified)}, unknown={sorted(unknown)})."
        )


def client_policy_has_explicit_decision(permission_code: str) -> bool:
    return permission_code in CLIENT_ALLOWED_PERMISSION_CODES or permission_code in CLIENT_DENIED_PERMISSION_CODES


validate_client_permission_policy()


# SERVER_PC is intentionally medical-operational: it can use normal worker,
# visit, certificate, prescription, and campaign permissions, but it cannot
# administer the shared installation.
SERVER_PC_RESTRICTED_PERMISSION_CODES = {
    "sync.manage_devices", "sync.disconnect_device", "sync.force", "backups.restore", "backups.delete",
    "backups.configure_schedule", "local_network.start_server", "local_network.stop_server", "local_network.manage_clients",
    "local_network.disconnect_client",
}
SERVER_PC_RESTRICTED_MODULES = {"users", "roles", "settings", "licenses"}
SERVER_PC_RESTRICTED_COMPANY_ACTIONS = {"create", "update", "delete"}
MODE_ADMINISTRATION_READ_PERMISSION_CODES = {"users.view", "users.view_permissions", "roles.view"}


def mode_allows_permission(mode: ConnectionMode, permission_code: str) -> bool:
    """Return the static deployment-mode decision used by enforcement and diagnostics."""
    if mode == ConnectionMode.CLIENT:
        return permission_code in CLIENT_ALLOWED_PERMISSION_CODES
    if mode == ConnectionMode.SERVER:
        return True
    if permission_code in MODE_ADMINISTRATION_READ_PERMISSION_CODES:
        return True
    definition = PERMISSION_LOOKUP.get(permission_code)
    restricted = permission_code in SERVER_PC_RESTRICTED_PERMISSION_CODES
    if definition is not None:
        restricted = restricted or definition.module in SERVER_PC_RESTRICTED_MODULES
        restricted = restricted or (
            definition.module == "companies" and definition.action in SERVER_PC_RESTRICTED_COMPANY_ACTIONS
        )
    return not restricted


class ConnectionModePolicy:
    def ensure_allowed(self, db: Session | None, user: User, permission_code: str, *, worker_id: int | None = None) -> None:
        if db is None:
            return

        runtime = db.get(RuntimeConfig, 1)
        if runtime is None:
            return
        resolution = connection_mode_service.resolve(runtime)
        del user, worker_id  # Reserved context for future worker-assignment policy.
        if resolution.requires_setup or not resolution.configured or not resolution.verified:
            return

        if resolution.mode == ConnectionMode.CLIENT:
            if not mode_allows_permission(resolution.mode, permission_code):
                raise ForbiddenException("This operation is not available in CLIENT mode.")
            return

        if resolution.mode != ConnectionMode.SERVER_PC:
            return

        if not mode_allows_permission(resolution.mode, permission_code):
            raise ForbiddenException("This administrative operation is not available in SERVER_PC mode.")


connection_mode_policy = ConnectionModePolicy()
