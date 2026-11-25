export type Role = "Super Admin" | "Admin" | "Doctor" | "Assistant";

export type SyncStatus = "synced" | "created" | "updated" | "deleted" | "conflict";

export interface ApiListResponse<T> {
  items: T[];
  total?: number;
  page?: number;
  page_size?: number;
  meta?: {
    page: number;
    limit: number;
    total: number;
    pages: number;
    search?: string | null;
    sort_by?: string | null;
    sort_order?: "asc" | "desc";
  };
}

export interface PaginationParams {
  page?: number;
  page_size?: number;
  limit?: number;
  search?: string;
  sort_by?: string;
  sort_order?: "asc" | "desc";
}
export interface ResourceResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}
export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  per_page: number;
}

export interface BaseEntity {
  id: number;
  created_at: string;
  updated_at: string;
  deleted_at?: string | null;
  local_id?: string | null;
  sync_status?: SyncStatus;
  uuid?: string;
  sync_version?: number;
  origin_device_uuid?: string | null;
  last_modified_device_uuid?: string | null;
  origin_mission_session_uuid?: string | null;
  last_modified_mission_session_uuid?: string | null;
  central_version?: number | null;
  central_sync_status?:
    | "never_submitted"
    | "central_pending"
    | "central_accepted"
    | "central_conflict"
    | "central_rejected"
    | "central_finalized"
    | string;
  central_sequence?: number | null;
  central_finalized_at?: string | null;
  central_server_uuid?: string | null;
}

export interface Option {
  label: string;
  value: string | number;
}

export interface NavItem {
  label: string;
  path: string;
  roles?: Role[];
  icon: string;
}
