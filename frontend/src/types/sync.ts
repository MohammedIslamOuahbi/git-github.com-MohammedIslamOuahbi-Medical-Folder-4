import type { SyncStatus } from "./common";

export interface OfflineEntity {
  id?: number;
  local_id?: string | null;
  sync_status?: SyncStatus;
  created_at?: string;
  updated_at?: string;
  deleted_at?: string | null;
  [key: string]: unknown;
}

export interface SyncChanges {
  users: OfflineEntity[];
  companies: OfflineEntity[];
  branches: OfflineEntity[];
  drilling_sites: OfflineEntity[];
  workers: OfflineEntity[];
  medical_campaigns: OfflineEntity[];
  campaign_workers: OfflineEntity[];
  medical_tests: OfflineEntity[];
  campaign_tests: OfflineEntity[];
  worker_tests: OfflineEntity[];
  doctor_campaigns: OfflineEntity[];
  assistant_campaigns: OfflineEntity[];
  import_jobs: OfflineEntity[];
  import_rows: OfflineEntity[];
}

export interface SyncPushPayload {
  device_id: string;
  last_sync_at: string | null;
  changes: SyncChanges;
}

export interface SyncPushResponse {
  success: boolean;
  synced_at: string;
  created: Record<string, unknown>;
  updated: Record<string, unknown>;
  deleted: Record<string, unknown>;
  conflicts: SyncConflict[];
}

export interface SyncPullResponse {
  success: boolean;
  server_time: string;
  changes: SyncChanges;
  deleted: Partial<Record<keyof SyncChanges, Array<number | string>>>;
}

export interface SyncConflict {
  entity_type: string;
  entity_id: number | string;
  local_data?: Record<string, unknown>;
  server_data?: Record<string, unknown>;
  reason?: string;
}

export interface SyncResolvePayload {
  entity_type: string;
  entity_id: number;
  resolution: "server_wins" | "client_wins" | "merge";
  merged_data: Record<string, unknown>;
}

export interface SyncStatusResponse {
  last_sync_at: string | null;
  pending_push_count: number;
  pending_pull_count: number;
  conflict_count: number;
  server_time: string;
}
