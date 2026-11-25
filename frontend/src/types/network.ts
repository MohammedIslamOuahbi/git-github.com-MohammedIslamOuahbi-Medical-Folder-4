export interface NetworkDeviceSummary {
  device_id: string;
  device_name: string;
  username: string;
  user_role: string;
  ip_address: string;
  connection_status: string;
  last_seen: string;
  connected_since?: string | null;
  latency_ms?: number | null;
  app_version?: string | null;
  operating_system?: string | null;
  pending_operations_count?: number;
}

export interface MissionServerSummary {
  server_name: string;
  server_ip: string;
  uptime_seconds: number;
  active_users_count: number;
  database_status: string;
  started_at: string;
  is_active: boolean;
  websocket_status: string;
}

export interface DiscoveredServerSummary {
  server_name: string;
  ip_address: string;
  online_status: "Online" | "Offline";
  connected_users: number;
  api_base_url: string;
}

export interface DatabaseStatusSummary {
  database_type: string;
  database_status: string;
  active_connections: number;
  last_backup_time: string | null;
  database_engine?: string;
  database_name?: string | null;
  database_host?: string | null;
  database_port?: number | null;
  postgresql_version?: string | null;
  database_size_bytes?: number | null;
  pool_checked_out?: number | null;
  pool_size?: number | null;
  server_time?: string | null;
}

export interface SystemLogEntry {
  event_type: string;
  message: string;
  created_at: string;
  device_id?: string | null;
  device_name?: string | null;
  username?: string | null;
  user_role?: string | null;
  ip_address?: string | null;
  payload: Record<string, unknown>;
}

export interface NetworkStatusResponse {
  device_name: string;
  username: string;
  user_role: string;
  local_ip_address: string;
  wifi_connection_status: string;
  current_connection_state: string;
  selected_server: DiscoveredServerSummary | null;
  mission_server: MissionServerSummary | null;
  discovered_servers: DiscoveredServerSummary[];
  connected_devices: NetworkDeviceSummary[];
  database_status: DatabaseStatusSummary;
  realtime_logs: SystemLogEntry[];
  heartbeat_interval_seconds: number;
  offline_timeout_seconds: number;
}

export interface MissionServerStartPayload {
  server_name: string;
  device_name: string;
}

export interface MissionServerStopPayload {
  reason?: string | null;
}

export interface NetworkConnectPayload {
  server_ip: string;
  server_name: string;
  api_base_url: string;
  device_name: string;
  latency_ms?: number | null;
}

export interface NetworkHeartbeatPayload {
  device_name: string;
  latency_ms?: number | null;
}
