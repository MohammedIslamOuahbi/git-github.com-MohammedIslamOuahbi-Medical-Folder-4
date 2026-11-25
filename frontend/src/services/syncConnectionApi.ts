import apiClient, { setApiBaseUrl } from "@/api/axios";
import {
  tauriRuntime,
  type ClientSyncHistoryEntry,
  type ClientSyncLocalStatus,
  type ClientSyncPackagePreview,
} from "@/desktop/tauriRuntime";
import { syncApi } from "@/api/syncApi";
import { syncStorage } from "@/utils/storage";
import type { SyncChanges } from "@/types/sync";
import type { NetworkStatusResponse } from "@/types/network";
import {
  BACKUP_FOLDER_KEY,
  apiRootFromBase,
  detectTauriRuntime,
  getStoredIsTauri,
  getStoredServerUrl,
  IS_TAURI_KEY,
  normalizeApiBaseUrl,
  OPERATION_MODE_KEY,
  SERVER_URL_KEY,
} from "@/config/runtime";

type BackupStatusPayload = {
  enabled?: boolean;
  backup_folder?: string;
  backup_count?: number;
  last_backup_time?: string | null;
  last_backup_status?: string | null;
};

type SystemBackupStatusPayload = {
  state: string;
  operation?: string | null;
  stage?: string | null;
  message?: string | null;
  started_at?: string | null;
  elapsed_seconds?: number;
  last_completed_at?: string | null;
  last_error?: string | null;
  safety_backup_filename?: string | null;
  server_mode: boolean;
  can_backup: boolean;
  can_restore: boolean;
  pg_dump_available: boolean;
  pg_restore_available: boolean;
};

type SystemBackupRestorePayload = {
  success: boolean;
  message: string;
  safety_backup_filename: string;
  migration_status: string;
};

type ServerIdentityPayload = {
  application?: string;
  api_status?: string;
  api_version?: string;
  database_engine?: string;
  server_id?: string;
};

export type ClientSyncStatusPayload = {
  server_id: string;
  schema_version: number;
  last_available_cursor: number;
  available_update_count: number;
  record_counts: Record<string, number>;
  supported_entities: string[];
  mode: "SERVER_TO_CLIENT_ONLY";
};

export type ClientSyncExportPayload = {
  server_id: string;
  from_cursor: number;
  to_cursor: number;
  schema_version: number;
  generated_at: string;
  mode: "SERVER_TO_CLIENT_ONLY";
  source_of_truth: "SERVER_POSTGRESQL";
  target_model: "LOCAL_SYNCHRONIZED_COPY";
  record_counts: Record<string, number>;
  table_order: string[];
  tombstones: Array<{
    entity_type: string;
    entity_id: number | string;
    deleted_at: string;
    sync_cursor: number;
  }>;
  data: Record<string, Array<Record<string, unknown>>>;
  checksum_sha256: string;
};

const readString = (key: string) =>
  typeof window === "undefined" ? null : window.localStorage.getItem(key);

const writeString = (key: string, value: string) => {
  if (typeof window !== "undefined") {
    window.localStorage.setItem(key, value);
  }
};

const fetchHealthEndpoint = async <T>(baseUrl: string, path: string): Promise<T | null> => {
  try {
    const response = await fetch(`${apiRootFromBase(baseUrl)}${path}`, {
      method: "GET",
      headers: {
        Accept: "application/json",
      },
    });

    if (!response.ok) {
      return null;
    }

    const payload = (await response.json()) as T | { data?: T };
    if (payload && typeof payload === "object" && "data" in payload) {
      return payload.data ?? null;
    }
    return payload as T;
  } catch {
    return null;
  }
};

export const extractBlobError = async (
  error: unknown,
  fallback = "Une erreur est survenue pendant l'operation de sauvegarde PostgreSQL.",
): Promise<string> => {
  if (!error || typeof error !== "object") {
    return fallback;
  }

  const maybeResponse = (error as {
    response?: {
      data?: Blob | { message?: string; detail?: string; error?: string };
      status?: number;
    };
    message?: string;
  }).response;

  if (!maybeResponse) {
    return (error as { message?: string }).message || fallback;
  }

  const payload = maybeResponse.data;
  if (payload instanceof Blob) {
    try {
      const text = await payload.text();
      if (!text) return fallback;
      try {
        const parsed = JSON.parse(text) as {
          message?: string;
          detail?: string | { message?: string };
        };
        if (typeof parsed.detail === "string") return parsed.detail;
        if (parsed.detail && typeof parsed.detail === "object" && parsed.detail.message) return parsed.detail.message;
        return parsed.message || fallback;
      } catch {
        return text;
      }
    } catch {
      return fallback;
    }
  }

  if (payload && typeof payload === "object") {
    const payloadRecord = payload as { message?: unknown; detail?: unknown };
    if (typeof payloadRecord.message === "string") return payloadRecord.message;
    if ("detail" in payloadRecord) {
      const detail = payloadRecord.detail;
      if (typeof detail === "string") return detail;
      if (detail && typeof detail === "object" && "message" in detail && typeof detail.message === "string") {
        return detail.message;
      }
    }
  }

  return (error as { message?: string }).message || fallback;
};

export const getApiErrorMessage = extractBlobError;

export const syncConnectionApi = {
  getLastServerUrl: () => readString(SERVER_URL_KEY) || getStoredServerUrl() || "",
  setLastServerUrl: (value: string) => {
    const normalized = value.trim() ? normalizeApiBaseUrl(value) : "";
    writeString(SERVER_URL_KEY, normalized);
    if (normalized) {
      setApiBaseUrl(normalized);
    }
    return normalized;
  },
  getConnectionMode: () => readString(OPERATION_MODE_KEY) || "client",
  setConnectionMode: (value: "server" | "client") => writeString(OPERATION_MODE_KEY, value),
  getIsTauri: () => getStoredIsTauri() || detectTauriRuntime(),
  setIsTauri: (value: boolean) => writeString(IS_TAURI_KEY, String(value)),
  getBackupFolder: () => readString(BACKUP_FOLDER_KEY) || "",
  setBackupFolder: (value: string) => writeString(BACKUP_FOLDER_KEY, value),
  initializeDesktopRuntime: () => tauriRuntime.initialize(),
  getDesktopRuntimeContext: () => tauriRuntime.getContext(),
  inspectDeploymentState: () => tauriRuntime.inspectDeploymentState(),
  applyOperationMode: (mode: "server" | "client" | "CLIENT" | "SERVER_PC" | "SERVER", serverUrl?: string) =>
    tauriRuntime.applyOperationMode(mode, serverUrl),
  inspectPostgresInstallation: () => tauriRuntime.inspectPostgresInstallation(),
  beginServerProvisioning: () => tauriRuntime.beginServerProvisioning(),
  bootstrapServerPostgres: (payload: {
    provisioningCapability: string;
    host: string;
    port: number;
    adminUser: string;
    adminPassword: string;
    appDatabase: string;
    appUser: string;
    appUserPassword: string;
    apiBindHost: string;
    apiPort: number;
    openFirewall: boolean;
    initialAdminFirstName: string;
    initialAdminLastName: string;
    initialAdminEmail: string;
    initialAdminPassword: string;
    initialAdminPhone?: string;
    initialAdminQualification?: string;
  }) => tauriRuntime.bootstrapServerPostgres(payload),
  chooseServerRestoreBackupFile: () => tauriRuntime.chooseServerRestoreBackupFile(),
  finalizeServerSetup: (payload: {
    mode: "initial" | "restore";
    backupPath?: string;
    confirmationPhrase?: string;
  }) => tauriRuntime.finalizeServerSetup(payload),
  resetServerConfiguration: (confirmationPhrase: string) =>
    tauriRuntime.resetServerConfiguration(confirmationPhrase),
  startLocalServer: async () => {
    if (tauriRuntime.isTauri()) {
      return tauriRuntime.startBackendSidecar();
    }
    const { data } = await apiClient.post<NetworkStatusResponse>("/local/server/start");
    return data;
  },
  stopLocalServer: async () => {
    if (tauriRuntime.isTauri()) {
      return tauriRuntime.stopBackendSidecar();
    }
    const { data } = await apiClient.post<NetworkStatusResponse>("/local/server/stop");
    return data;
  },
  connectClient: async (serverUrl: string, deviceName: string) => {
    const normalized = syncConnectionApi.setLastServerUrl(serverUrl);
    if (tauriRuntime.isTauri()) {
      return tauriRuntime.applyOperationMode("client", normalized);
    }
    const { data } = await apiClient.post<NetworkStatusResponse>("/local/client/connect", {
      server_url: normalized,
      device_name: deviceName,
    });
    return data;
  },
  disconnectClient: async (deviceName?: string) => {
    if (tauriRuntime.isTauri()) {
      return tauriRuntime.applyOperationMode("client", syncConnectionApi.getLastServerUrl());
    }
    const { data } = await apiClient.post<NetworkStatusResponse>("/local/client/disconnect", {
      device_name: deviceName || null,
    });
    return data;
  },
  getServerIdentity: async (serverUrl?: string) =>
    fetchHealthEndpoint<ServerIdentityPayload>(serverUrl || syncConnectionApi.getLastServerUrl(), "/health/identity"),
  testServer: async (serverUrl?: string) => {
    const target = serverUrl || syncConnectionApi.getLastServerUrl();
    const health = await fetchHealthEndpoint<{ status?: string }>(target, "/health");
    if (health?.status !== "ok") {
      return null;
    }

    const identity = await syncConnectionApi.getServerIdentity(target);
    const isExpectedServer =
      identity?.application === "medical-folder" &&
      identity?.api_status === "online" &&
      identity?.database_engine === "PostgreSQL";

    if (!isExpectedServer) {
      return {
        status: "error",
        incompatible: true,
        message: "Serveur incompatible: l'identité de l'application médicale est invalide.",
      };
    }

    return { ...health, identity };
  },
  // TODO: backend may not expose this endpoint yet in all environments.
  getDatabaseHealth: async (serverUrl?: string) =>
    fetchHealthEndpoint<Record<string, unknown>>(serverUrl || syncConnectionApi.getLastServerUrl(), "/health/database"),
  getDatabaseHealthDetails: async (serverUrl?: string) =>
    fetchHealthEndpoint<Record<string, unknown>>(serverUrl || syncConnectionApi.getLastServerUrl(), "/health/database/details"),
  // TODO: backend may not expose this endpoint yet in all environments.
  getNetworkInfo: async (serverUrl?: string) =>
    fetchHealthEndpoint<Record<string, unknown>>(serverUrl || syncConnectionApi.getLastServerUrl(), "/health/network-info"),
  getBackupStatus: async () => {
    const { data } = await apiClient.get<BackupStatusPayload>("/backup/status");
    return data;
  },
  getSystemBackupStatus: async () => {
    const { data } = await apiClient.get<SystemBackupStatusPayload>("/system-backups/status");
    return data;
  },
  downloadSystemBackup: async () => {
    const response = await apiClient.post("/system-backups/download", undefined, {
      responseType: "blob",
    });
    const blob = response.data as Blob;
    const contentDisposition = response.headers["content-disposition"] as string | undefined;
    const filenameMatch = contentDisposition?.match(/filename="?([^"]+)"?/i);
    return {
      blob,
      filename: filenameMatch?.[1] || "medical_clinic_backup.backup",
    };
  },
  restoreSystemBackup: async (file: File) => {
    const formData = new FormData();
    formData.append("file", file);
    const { data } = await apiClient.post<SystemBackupRestorePayload>("/system-backups/restore", formData);
    return data;
  },
  getClientSyncStatus: async (afterCursor = 0) => {
    const { data } = await apiClient.get<ClientSyncStatusPayload>("/client-sync/status", {
      params: { after_cursor: Math.max(0, afterCursor) },
    });
    return data;
  },
  exportClientSyncPackage: async (afterCursor = 0) => {
    const { data } = await apiClient.get<ClientSyncExportPayload>("/client-sync/export", {
      params: { after_cursor: Math.max(0, afterCursor) },
    });
    return data;
  },
  inspectClientLocalCopy: () => tauriRuntime.inspectClientLocalCopy(),
  configureClientLocalCopy: (payload: {
    host: string;
    port: number;
    databaseName: string;
    user: string;
    password: string;
  }) => tauriRuntime.configureClientLocalCopy(payload),
  importClientSyncPackage: (packagePayload: ClientSyncExportPayload, expectedServerId?: string | null) =>
    tauriRuntime.importClientSync(packagePayload, expectedServerId),
  importClientSyncPackageFile: (expectedServerId?: string | null) =>
    tauriRuntime.importClientSyncPackageFile(expectedServerId),
  importClientSyncPackagePath: (packagePath: string, expectedServerId?: string | null) =>
    tauriRuntime.importClientSyncPackagePath(packagePath, expectedServerId),
  previewClientSyncPackageFile: (expectedServerId?: string | null) =>
    tauriRuntime.previewClientSyncPackageFile(expectedServerId),
  getClientSyncImportHistory: async (): Promise<ClientSyncHistoryEntry[]> => {
    const result = await tauriRuntime.getClientSyncImportHistory();
    return result?.history ?? [];
  },
  getClientSyncLocalStatus: async (): Promise<ClientSyncLocalStatus | null> =>
    tauriRuntime.getClientSyncLocalStatus(),
  inspectPostgresBackupTools: () => tauriRuntime.inspectPostgresBackupTools(),
  getPostgresBackupStatus: () => tauriRuntime.getPostgresBackupStatus(),
  chooseBackupDirectory: () => tauriRuntime.chooseBackupDirectory(),
  openBackupDirectory: () => tauriRuntime.openBackupDirectory(),
  createPostgresBackup: () => tauriRuntime.createPostgresBackup(),
  validatePostgresBackup: (backupPath: string) => tauriRuntime.validatePostgresBackup(backupPath),
  restorePostgresBackup: (backupPath: string, confirmationPhrase: string) =>
    tauriRuntime.restorePostgresBackup(backupPath, confirmationPhrase),
  exportBackupToUsb: (backupPath: string, overwrite = false) =>
    tauriRuntime.exportBackupToUsb(backupPath, overwrite),
  createBackup: async () => {
    const { data } = await apiClient.post<{ backup_path?: string; created_at?: string }>("/backup/create");
    return data;
  },
  restoreBackup: async (backupPath: string) => {
    const { data } = await apiClient.post<{ restored?: boolean; emergency_backup_path?: string }>("/backup/restore", {
      backup_path: backupPath,
    });
    return data;
  },
  exportBackup: async () => {
    const { data } = await apiClient.post<{ exported?: boolean; export_path?: string }>("/backup/export-usb");
    return data;
  },
  getSyncStatus: async () => syncApi.getStatus(),
  syncNow: async () =>
    syncApi.push({
      device_id: "sync-connection",
      last_sync_at: syncStorage.getMeta<{ last_sync_at: string | null }>()?.last_sync_at || null,
      changes: {
        users: [],
        companies: [],
        branches: [],
        drilling_sites: [],
        workers: [],
        medical_campaigns: [],
        campaign_workers: [],
        medical_tests: [],
        campaign_tests: [],
        worker_tests: [],
        doctor_campaigns: [],
        assistant_campaigns: [],
        import_jobs: [],
        import_rows: [],
      } satisfies SyncChanges,
    }),
};
