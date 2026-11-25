export type CentralSyncState =
  | "idle"
  | "checking"
  | "not_ready"
  | "pushing"
  | "processing"
  | "pulling"
  | "applying"
  | "completed"
  | "completed_with_conflicts"
  | "failed";

export type CentralReadinessStatus = "passed" | "warning" | "failed";

export interface CentralServerInfo {
  server_uuid: string;
  server_generation_uuid: string;
  device_uuid: string | null;
  status: string;
  schema_revision: string | null;
  protocol_version: string | null;
  current_central_sequence: number;
  activated_at: string | null;
  last_health_check_at: string | null;
}

export interface CentralCapabilities {
  central_authority_active: boolean;
  protocol_version: string | null;
  schema_revision: string | null;
  supports_bootstrap: boolean;
  supports_conflict_resolution: boolean;
  supports_incremental_pull: boolean;
}

export interface CentralReadinessCheck {
  key: string;
  label: string;
  status: CentralReadinessStatus;
  detail: string | null;
}

export interface CentralReadiness {
  ready: boolean;
  checks: CentralReadinessCheck[];
}

export interface CentralConflictRecord {
  uuid: string;
  mission_uuid: string | null;
  entity_type: string;
  entity_uuid: string;
  incoming_change_uuid: string;
  source_device_uuid: string | null;
  source_user_uuid: string | null;
  mission_sequence: number | null;
  base_version: number | null;
  central_version: number | null;
  conflicting_fields: string[];
  central_snapshot: Record<string, unknown> | null;
  mission_snapshot: Record<string, unknown> | null;
  status: "pending" | "resolved" | "dismissed" | "superseded" | string;
  resolution_type: string | null;
  resolved_payload: Record<string, unknown> | null;
  resolved_by_user_uuid: string | null;
  resolved_at: string | null;
  created_at: string;
  updated_at: string;
}

export type CentralConflictResolutionType =
  | "keep_central"
  | "accept_mission"
  | "manual_merge"
  | "create_revision";

export interface CentralPushChange {
  change_uuid: string;
  mission_sequence: number | null;
  entity_type: string;
  entity_uuid: string;
  operation: "insert" | "update" | "delete" | string;
  base_version: number | null;
  entity_version: number;
  changed_fields: string[];
  source_device_uuid: string | null;
  source_user_uuid: string | null;
  payload: Record<string, unknown> | null;
}

export interface CentralPushRequest {
  batch_uuid: string;
  device_uuid: string;
  mission_uuid: string;
  mission_manifest_checksum: string;
  base_central_sequence: number;
  changes: CentralPushChange[];
}

export interface CentralPushResponse {
  batch_uuid: string;
  accepted: string[];
  duplicates: string[];
  auto_merged: string[];
  conflicts: string[];
  rejected: string[];
  central_sequence: number | null;
  has_more_required: boolean;
}

export interface CentralPulledChange {
  change_uuid: string;
  entity_type: string;
  entity_uuid: string;
  operation: "insert" | "update" | "delete" | string;
  base_version: number | null;
  entity_version: number;
  changed_fields: string[];
  payload: Record<string, unknown> | null;
  source_device_uuid: string | null;
  source_user_uuid: string | null;
  mission_session_uuid: string | null;
  mission_sequence: number | null;
  central_server_uuid: string | null;
  central_sequence: number;
  central_status: string | null;
  central_finalized_at: string | null;
}

export interface CentralPullResponse {
  changes: CentralPulledChange[];
  next_central_sequence: number;
  has_more: boolean;
  central_server_uuid: string;
  central_generation_uuid: string;
  schema_revision: string | null;
}

export interface CentralApplyRequest {
  central_server_uuid: string;
  central_generation_uuid: string;
  changes: CentralPulledChange[];
  next_central_sequence: number;
  final_central_sequence: number;
  current_run_uuid?: string | null;
}

export interface CentralApplyResponse {
  last_pulled_sequence: number;
  final_sequence: number | null;
  copy_status: string;
}

export interface CentralBootstrapRequestPayload {
  device_uuid: string;
  allow_overwrite_without_unsent_work: boolean;
}

export interface CentralBootstrapRequestResponse {
  bootstrap_uuid: string;
  status: string;
  requested_by: number | null;
}

export interface CentralBootstrapManifest {
  bootstrap_uuid: string;
  checksum: string;
  central_server_uuid: string;
  central_generation_uuid: string;
  snapshot_central_sequence: number;
  schema_revision: string | null;
  protocol_version: string | null;
  creation_time: string;
  entity_counts: Record<string, number>;
  file_metadata: Record<string, unknown>;
}

export interface CentralBootstrapDownload {
  bootstrap_uuid: string;
  manifest: Omit<CentralBootstrapManifest, "bootstrap_uuid" | "checksum">;
  payload: Record<string, unknown>;
  checksum: string;
}

export interface DataIntegrityStatus {
  null_uuid_issues: string[];
  duplicate_uuid_issues: string[];
  broken_uuid_relationships: string[];
  duplicate_change_uuid_issues: string[];
  invalid_cursor_issues: string[];
  sync_version_issues: string[];
  missing_device_identity: boolean;
  orphaned_mission_session: string[];
  missing_mission_sequence: string[];
  missing_central_sequence_for_finalized_changes: string[];
  orphaned_medical_visits: string[];
  orphaned_certificates: string[];
  missing_signature_file_metadata: string[];
  invalid_central_generation_reference: string[];
}

export interface CentralSyncCounts {
  pending: number;
  sent: number;
  accepted: number;
  duplicates: number;
  autoMerged: number;
  conflicts: number;
  rejected: number;
  pulled: number;
  applied: number;
}

export interface CentralSyncSummary {
  status:
    | "never_submitted"
    | "pending"
    | "running"
    | "centralized"
    | "centralized_with_conflicts"
    | "failed";
  firstCentralSequence: number | null;
  lastCentralSequence: number | null;
  centralizedAt: string | null;
  acceptedCount: number;
  conflictCount: number;
  rejectedCount: number;
}

export interface CentralSyncRunRecord {
  uuid: string;
  direction: "mission_to_central_push" | "central_to_mobile_pull" | "bootstrap";
  status: string;
  mission_uuid: string | null;
  device_code: string | null;
  started_at: string;
  completed_at: string | null;
  duration_ms: number | null;
  counts: CentralSyncCounts;
  cursor_start: number | null;
  cursor_end: number | null;
  error_code: string | null;
  error_message: string | null;
  server_url: string | null;
}

export interface InfrastructureTimelineEvent {
  id: string;
  type:
    | "mission_created"
    | "device_joined"
    | "mission_finalized"
    | "client_copy_completed"
    | "mission_submitted_centrally"
    | "conflict_detected"
    | "conflict_resolved"
    | "centralization_completed"
    | "bootstrap_completed"
    | "integrity_checked"
    | "server_identity_verified";
  title: string;
  description: string;
  occurred_at: string;
  tone: "active" | "pending" | "failed" | "inactive";
}

export interface StoredCentralServerIdentity {
  serverUrl: string;
  serverUuid: string;
  generationUuid: string;
  verifiedAt: string;
  verifiedByUserId: number | null;
}

export interface CentralEntitySyncMetadata {
  central_sync_status?: string | null;
  central_sequence?: number | null;
  central_version?: number | null;
  central_finalized_at?: string | null;
  origin_mission_session_uuid?: string | null;
}
