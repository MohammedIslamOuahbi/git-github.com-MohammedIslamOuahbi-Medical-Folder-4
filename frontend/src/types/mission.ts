export type RuntimeMode = "standalone" | "mission_server" | "mission_client";

export type ConnectionState =
  | "unknown"
  | "testing"
  | "connected"
  | "disconnected"
  | "incompatible"
  | "revoked";

export interface DeviceIdentity {
  device_uuid: string | null;
  device_code: string | null;
  device_name: string | null;
  registered?: boolean;
  revoked?: boolean;
  runtime_mode: RuntimeMode;
  app_version: string | null;
  schema_revision: string | null;
  database_health: string;
  server_time: string;
}

export interface ActiveMissionSummary {
  uuid: string;
  code: string;
  name: string;
  status: string;
  base_central_sequence: number | null;
  current_mission_sequence: number;
}

export interface MissionServerInfo extends DeviceIdentity {
  active_mission: ActiveMissionSummary | null;
  protocol_version: string;
}

export interface DeviceUpdatePayload {
  device_name: string;
}

export interface RuntimeStatus {
  runtimeMode: RuntimeMode;
  activeApiSource: string;
  localDatabaseWriteEnabled: boolean;
  missionServerName: string | null;
  missionServerUrl: string | null;
  connectionState: ConnectionState;
  activeMission: ActiveMissionSummary | null;
  device: DeviceIdentity | null;
}

export interface RuntimeStatusPayload {
  runtime_mode: RuntimeMode;
  active_api_url: string;
  local_api_url: string;
  local_database_write_enabled: boolean;
  active_mission_session_uuid: string | null;
  mission_server_url: string | null;
  mission_server_device_uuid: string | null;
  local_device_registered: boolean;
  local_device_revoked: boolean;
  local_device_uuid: string | null;
}

export interface MissionSessionCreatePayload {
  mission_code: string;
  mission_name: string;
  description: string | null;
  expected_devices: string[];
}

export interface MissionJoinPayload {
  device_uuid: string;
  device_code: string;
  device_name: string;
  installation_uuid: string;
  app_version: string | null;
  schema_revision: string | null;
  last_central_sequence: number | null;
  protocol_version: string;
}

export interface MissionDeviceCredential {
  access_token: string;
  expires_at: string;
  mission_uuid: string;
  device_uuid: string;
}

export interface MissionJoinResponse {
  credential: MissionDeviceCredential;
  participant: {
    device_uuid: string;
    status: string;
  };
}

export interface MissionSessionSummary {
  uuid: string;
  mission_code: string;
  mission_name: string;
  status: string;
  mission_current_sequence: number;
}

export interface MissionParticipant {
  mission_session_uuid: string;
  device_uuid: string;
  device_code_snapshot: string;
  device_name_snapshot: string;
  role: "mission_server" | "mission_client" | string;
  joined_at: string;
  last_seen_at: string | null;
  last_pulled_mission_sequence: number | null;
  local_copy_completed_at: string | null;
  is_connected: boolean;
  status: string;
}

export interface MissionChangeRecord {
  change_uuid: string;
  entity_type: string;
  entity_uuid: string;
  operation: "insert" | "update" | "delete" | string;
  entity_version: number;
  changed_fields: string[];
  payload: Record<string, unknown> | null;
  source_device_uuid: string | null;
  source_user_uuid: string | null;
  mission_session_uuid: string | null;
  mission_sequence: number;
  occurred_at: string;
}

export interface MissionChangesResponse {
  mission_uuid: string;
  server_device_uuid: string | null;
  changes: MissionChangeRecord[];
  next_sequence: number;
  final_sequence: number;
  has_more: boolean;
  mission_status: string;
  schema_revision: string | null;
  manifest_checksum: string | null;
}

export interface MissionFinalizeManifest {
  mission_uuid: string;
  server_device_uuid: string;
  base_central_sequence: number | null;
  final_mission_sequence: number;
  schema_revision: string | null;
  entity_counts: Record<string, number>;
  change_count: number;
  created_at: string;
  checksum: string;
}

export interface MissionCopyState {
  mission_uuid: string;
  mission_server_uuid: string;
  mission_server_url: string;
  last_pulled_mission_sequence: number;
  final_mission_sequence: number | null;
  copy_status: string;
  copy_started_at: string | null;
  copy_completed_at: string | null;
  last_error_code: string | null;
  last_error_message: string | null;
  retry_count: number;
  is_sync_running?: boolean;
  current_run_uuid?: string | null;
  last_successful_sync_at?: string | null;
  last_failed_sync_at?: string | null;
}

export interface MissionCopyApplyPayload {
  mission_uuid: string;
  mission_server_uuid: string;
  mission_server_url: string;
  changes: MissionChangeRecord[];
  next_sequence: number;
  final_sequence: number;
  current_run_uuid?: string | null;
}
