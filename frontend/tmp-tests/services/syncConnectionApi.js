import apiClient, { setApiBaseUrl } from "@/api/axios";
import { tauriRuntime, } from "@/desktop/tauriRuntime";
import { syncApi } from "@/api/syncApi";
import { syncStorage } from "@/utils/storage";
import { BACKUP_FOLDER_KEY, apiRootFromBase, detectTauriRuntime, getStoredIsTauri, getStoredServerUrl, IS_TAURI_KEY, normalizeApiBaseUrl, OPERATION_MODE_KEY, SERVER_URL_KEY, } from "@/config/runtime";
const readString = (key) => typeof window === "undefined" ? null : window.localStorage.getItem(key);
const writeString = (key, value) => {
    if (typeof window !== "undefined") {
        window.localStorage.setItem(key, value);
    }
};
const fetchHealthEndpoint = async (baseUrl, path) => {
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
        const payload = (await response.json());
        if (payload && typeof payload === "object" && "data" in payload) {
            return payload.data ?? null;
        }
        return payload;
    }
    catch {
        return null;
    }
};
export const extractBlobError = async (error, fallback = "Une erreur est survenue pendant l'operation de sauvegarde PostgreSQL.") => {
    if (!error || typeof error !== "object") {
        return fallback;
    }
    const maybeResponse = error.response;
    if (!maybeResponse) {
        return error.message || fallback;
    }
    const payload = maybeResponse.data;
    if (payload instanceof Blob) {
        try {
            const text = await payload.text();
            if (!text)
                return fallback;
            try {
                const parsed = JSON.parse(text);
                if (typeof parsed.detail === "string")
                    return parsed.detail;
                if (parsed.detail && typeof parsed.detail === "object" && parsed.detail.message)
                    return parsed.detail.message;
                return parsed.message || fallback;
            }
            catch {
                return text;
            }
        }
        catch {
            return fallback;
        }
    }
    if (payload && typeof payload === "object") {
        const payloadRecord = payload;
        if (typeof payloadRecord.message === "string")
            return payloadRecord.message;
        if ("detail" in payloadRecord) {
            const detail = payloadRecord.detail;
            if (typeof detail === "string")
                return detail;
            if (detail && typeof detail === "object" && "message" in detail && typeof detail.message === "string") {
                return detail.message;
            }
        }
    }
    return error.message || fallback;
};
export const getApiErrorMessage = extractBlobError;
export const syncConnectionApi = {
    getLastServerUrl: () => readString(SERVER_URL_KEY) || getStoredServerUrl() || "",
    setLastServerUrl: (value) => {
        const normalized = value.trim() ? normalizeApiBaseUrl(value) : "";
        writeString(SERVER_URL_KEY, normalized);
        if (normalized) {
            setApiBaseUrl(normalized);
        }
        return normalized;
    },
    getConnectionMode: () => readString(OPERATION_MODE_KEY) || "client",
    setConnectionMode: (value) => writeString(OPERATION_MODE_KEY, value),
    getIsTauri: () => getStoredIsTauri() || detectTauriRuntime(),
    setIsTauri: (value) => writeString(IS_TAURI_KEY, String(value)),
    getBackupFolder: () => readString(BACKUP_FOLDER_KEY) || "",
    setBackupFolder: (value) => writeString(BACKUP_FOLDER_KEY, value),
    initializeDesktopRuntime: () => tauriRuntime.initialize(),
    getDesktopRuntimeContext: () => tauriRuntime.getContext(),
    inspectDeploymentState: () => tauriRuntime.inspectDeploymentState(),
    applyOperationMode: (mode, serverUrl) => tauriRuntime.applyOperationMode(mode, serverUrl),
    inspectPostgresInstallation: () => tauriRuntime.inspectPostgresInstallation(),
    beginServerProvisioning: () => tauriRuntime.beginServerProvisioning(),
    bootstrapServerPostgres: (payload) => tauriRuntime.bootstrapServerPostgres(payload),
    chooseServerRestoreBackupFile: () => tauriRuntime.chooseServerRestoreBackupFile(),
    finalizeServerSetup: (payload) => tauriRuntime.finalizeServerSetup(payload),
    resetServerConfiguration: (confirmationPhrase) => tauriRuntime.resetServerConfiguration(confirmationPhrase),
    startLocalServer: async () => {
        if (tauriRuntime.isTauri()) {
            return tauriRuntime.startBackendSidecar();
        }
        const { data } = await apiClient.post("/local/server/start");
        return data;
    },
    stopLocalServer: async () => {
        if (tauriRuntime.isTauri()) {
            return tauriRuntime.stopBackendSidecar();
        }
        const { data } = await apiClient.post("/local/server/stop");
        return data;
    },
    connectClient: async (serverUrl, deviceName) => {
        const normalized = syncConnectionApi.setLastServerUrl(serverUrl);
        if (tauriRuntime.isTauri()) {
            return tauriRuntime.applyOperationMode("client", normalized);
        }
        const { data } = await apiClient.post("/local/client/connect", {
            server_url: normalized,
            device_name: deviceName,
        });
        return data;
    },
    disconnectClient: async (deviceName) => {
        if (tauriRuntime.isTauri()) {
            return tauriRuntime.applyOperationMode("client", syncConnectionApi.getLastServerUrl());
        }
        const { data } = await apiClient.post("/local/client/disconnect", {
            device_name: deviceName || null,
        });
        return data;
    },
    getServerIdentity: async (serverUrl) => fetchHealthEndpoint(serverUrl || syncConnectionApi.getLastServerUrl(), "/health/identity"),
    testServer: async (serverUrl) => {
        const target = serverUrl || syncConnectionApi.getLastServerUrl();
        const health = await fetchHealthEndpoint(target, "/health");
        if (health?.status !== "ok") {
            return null;
        }
        const identity = await syncConnectionApi.getServerIdentity(target);
        const isExpectedServer = identity?.application === "medical-folder" &&
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
    getDatabaseHealth: async (serverUrl) => fetchHealthEndpoint(serverUrl || syncConnectionApi.getLastServerUrl(), "/health/database"),
    getDatabaseHealthDetails: async (serverUrl) => fetchHealthEndpoint(serverUrl || syncConnectionApi.getLastServerUrl(), "/health/database/details"),
    // TODO: backend may not expose this endpoint yet in all environments.
    getNetworkInfo: async (serverUrl) => fetchHealthEndpoint(serverUrl || syncConnectionApi.getLastServerUrl(), "/health/network-info"),
    getBackupStatus: async () => {
        const { data } = await apiClient.get("/backup/status");
        return data;
    },
    getSystemBackupStatus: async () => {
        const { data } = await apiClient.get("/system-backups/status");
        return data;
    },
    downloadSystemBackup: async () => {
        const response = await apiClient.post("/system-backups/download", undefined, {
            responseType: "blob",
        });
        const blob = response.data;
        const contentDisposition = response.headers["content-disposition"];
        const filenameMatch = contentDisposition?.match(/filename="?([^"]+)"?/i);
        return {
            blob,
            filename: filenameMatch?.[1] || "medical_clinic_backup.backup",
        };
    },
    restoreSystemBackup: async (file) => {
        const formData = new FormData();
        formData.append("file", file);
        const { data } = await apiClient.post("/system-backups/restore", formData);
        return data;
    },
    getClientSyncStatus: async (afterCursor = 0) => {
        const { data } = await apiClient.get("/client-sync/status", {
            params: { after_cursor: Math.max(0, afterCursor) },
        });
        return data;
    },
    exportClientSyncPackage: async (afterCursor = 0) => {
        const { data } = await apiClient.get("/client-sync/export", {
            params: { after_cursor: Math.max(0, afterCursor) },
        });
        return data;
    },
    inspectClientLocalCopy: () => tauriRuntime.inspectClientLocalCopy(),
    configureClientLocalCopy: (payload) => tauriRuntime.configureClientLocalCopy(payload),
    importClientSyncPackage: (packagePayload, expectedServerId) => tauriRuntime.importClientSync(packagePayload, expectedServerId),
    importClientSyncPackageFile: (expectedServerId) => tauriRuntime.importClientSyncPackageFile(expectedServerId),
    importClientSyncPackagePath: (packagePath, expectedServerId) => tauriRuntime.importClientSyncPackagePath(packagePath, expectedServerId),
    previewClientSyncPackageFile: (expectedServerId) => tauriRuntime.previewClientSyncPackageFile(expectedServerId),
    getClientSyncImportHistory: async () => {
        const result = await tauriRuntime.getClientSyncImportHistory();
        return result?.history ?? [];
    },
    getClientSyncLocalStatus: async () => tauriRuntime.getClientSyncLocalStatus(),
    inspectPostgresBackupTools: () => tauriRuntime.inspectPostgresBackupTools(),
    getPostgresBackupStatus: () => tauriRuntime.getPostgresBackupStatus(),
    chooseBackupDirectory: () => tauriRuntime.chooseBackupDirectory(),
    openBackupDirectory: () => tauriRuntime.openBackupDirectory(),
    createPostgresBackup: () => tauriRuntime.createPostgresBackup(),
    validatePostgresBackup: (backupPath) => tauriRuntime.validatePostgresBackup(backupPath),
    restorePostgresBackup: (backupPath, confirmationPhrase) => tauriRuntime.restorePostgresBackup(backupPath, confirmationPhrase),
    exportBackupToUsb: (backupPath, overwrite = false) => tauriRuntime.exportBackupToUsb(backupPath, overwrite),
    createBackup: async () => {
        const { data } = await apiClient.post("/backup/create");
        return data;
    },
    restoreBackup: async (backupPath) => {
        const { data } = await apiClient.post("/backup/restore", {
            backup_path: backupPath,
        });
        return data;
    },
    exportBackup: async () => {
        const { data } = await apiClient.post("/backup/export-usb");
        return data;
    },
    getSyncStatus: async () => syncApi.getStatus(),
    syncNow: async () => syncApi.push({
        device_id: "sync-connection",
        last_sync_at: syncStorage.getMeta()?.last_sync_at || null,
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
        },
    }),
};
