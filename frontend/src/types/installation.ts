export type InstallationProfileCode = "central_server" | "mobile_device";

export type InstallationProfileLoadState =
  | "idle"
  | "loading"
  | "ready"
  | "fallback"
  | "degraded"
  | "error";

export type InstallationProfileSource =
  | "backend"
  | "packaged"
  | "last_known_good"
  | "none";

export interface InstallationWarning {
  code: string;
  message: string;
}

export type InstallationProvisioningStatus =
  | "unconfigured"
  | "schema_incomplete"
  | "checking_prerequisites"
  | "postgresql_missing"
  | "postgresql_ready"
  | "database_creating"
  | "database_ready"
  | "migrations_running"
  | "identity_creating"
  | "admin_setup_required"
  | "central_configuration_required"
  | "mobile_device_configuration_required"
  | "bootstrap_required"
  | "bootstrap_running"
  | "provisioning"
  | "configured"
  | "failed"
  | "reset_required";

export type InstallationErrorCode =
  | "POSTGRESQL_UNAVAILABLE"
  | "CENTRAL_SERVER_STATE_TABLE_MISSING"
  | "CENTRAL_DATABASE_NOT_PROVISIONED"
  | "MIGRATION_FAILED"
  | "CENTRAL_IDENTITY_INVALID"
  | "FIREWALL_CONFIGURATION_FAILED"
  | "BACKUP_CONFIGURATION_FAILED"
  | "INSTALLATION_PROFILE_MISMATCH";

export interface InstallationProfileCapabilities {
  central_authority: boolean;
  run_mission_server: boolean;
  run_mission_client: boolean;
  manage_registered_devices: boolean;
  receive_mission_submissions: boolean;
  provide_device_bootstrap: boolean;
  create_central_backups?: boolean;
  perform_mission_copy?: boolean;
  push_to_central?: boolean;
  pull_from_central?: boolean;
}

export interface InstallationProfileDevice {
  installation_uuid: string | null;
  device_uuid: string | null;
  device_code: string | null;
  device_name: string | null;
  app_version: string | null;
  schema_revision: string | null;
  protocol_version: string | null;
}

export interface InstallationProfilePayload {
  profile: InstallationProfileCode | null;
  provisioning_status: InstallationProvisioningStatus;
  profile_version?: number;
  installation_uuid?: string;
  capabilities: Partial<InstallationProfileCapabilities>;
  device: {
    uuid: string | null;
    code: string | null;
    name: string | null;
  } | null;
  packaged_profile?: InstallationProfileCode | null;
  central_server_uuid?: string | null;
  central_generation_uuid?: string | null;
}

export interface InstallationStatusCheck {
  key: string;
  label: string;
  status: "pending" | "running" | "success" | "failed";
  detail: string | null;
}

export interface CentralProvisioningStage {
  key: string;
  label: string;
  status: "pending" | "running" | "success" | "failed";
  detail: string | null;
}

export interface InstallationStatusPayload {
  profile: InstallationProfileCode | null;
  provisioning_status: InstallationProvisioningStatus;
  app_version: string | null;
  schema_revision: string | null;
  sync_protocol_version: string | null;
  server_uuid: string | null;
  generation_uuid: string | null;
  central_sequence: number | null;
  checks: InstallationStatusCheck[];
  provisioning_stages: CentralProvisioningStage[];
  postgres_ready: boolean;
  central_database_ready: boolean;
  migrations_up_to_date: boolean;
  fastapi_ready: boolean;
  admin_created: boolean;
  backup_configured: boolean;
  backup_directory: string | null;
  backup_status: string | null;
  retention_policy: string | null;
  available_disk_space: string | null;
  network: {
    lan_ip: string | null;
    api_url: string | null;
    health_status: string | null;
    firewall_status: string | null;
    network_interface: string | null;
  };
  identity: {
    server_name: string | null;
    server_code: string | null;
    description: string | null;
    api_port: number | null;
  };
  pending_error_codes?: InstallationErrorCode[];
  warnings?: InstallationWarning[];
}

export interface CentralProvisionPayload {
  server_name: string;
  server_code: string;
  description: string | null;
  api_port: number;
  backup_directory: string | null;
  admin: {
    first_name: string;
    last_name: string;
    email: string;
    password: string;
  };
}

export interface CentralProvisionResponse {
  provisioning_status: InstallationProvisioningStatus;
  stages: CentralProvisioningStage[];
  checks: InstallationStatusCheck[];
}

export interface CentralCompletePayload {
  backup_directory: string | null;
  retention_policy: string | null;
}

export interface CentralCompleteResponse {
  provisioning_status: InstallationProvisioningStatus;
  completed_at: string | null;
}

export interface MobileProvisionPayload {
  device_name: string;
  device_code: string;
  description: string | null;
  central_server_url: string;
}

export interface MobileProvisionResponse {
  provisioning_status: InstallationProvisioningStatus;
  checks: InstallationStatusCheck[];
  device_uuid: string | null;
}

export interface DeviceRegistrationPayload {
  device_uuid: string;
  device_secret: string;
  app_version?: string | null;
  schema_revision?: string | null;
  protocol_version?: string | null;
}

export interface DeviceRegistrationResponse {
  device_uuid: string;
}

export interface RegisteredDeviceRecord {
  uuid: string;
  name: string;
  code: string;
  last_connection_at: string | null;
  last_sync_at: string | null;
  version: string | null;
  schema_revision: string | null;
  status: string;
  revoked: boolean;
}

export interface MissionSubmissionRecord {
  uuid: string;
  mission_code: string;
  mission_server_device: string | null;
  final_mission_sequence: number | null;
  submitted_changes: number;
  accepted: number;
  conflicts: number;
  status: "En attente" | "En cours" | "Acceptée" | "Acceptée avec conflits" | "Rejetée" | string;
}

export interface BackupRecord {
  filename: string;
  path: string | null;
  created_at: string | null;
  size_bytes: number | null;
  status: string | null;
}
