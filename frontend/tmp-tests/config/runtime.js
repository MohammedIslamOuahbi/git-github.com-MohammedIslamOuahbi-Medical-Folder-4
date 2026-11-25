import { env } from "@/config/env";
export { getConnectionModeLabel } from "@/config/connectionModeDisplay";
export const OPERATION_MODE_KEY = "clinic_sync_connection_mode";
export const CONNECTION_MODE_KEY = "clinic_connection_mode_v2";
export const SERVER_URL_KEY = "clinic_sync_connection_server_url";
export const LAST_SYNC_KEY = "clinic_sync_connection_last_sync";
export const IS_TAURI_KEY = "clinic_sync_connection_is_tauri";
export const API_BASE_URL_KEY = "clinic_api_base_url";
export const BACKUP_FOLDER_KEY = "clinic_backup_folder";
export const SETUP_COMPLETED_KEY = "clinic_sync_connection_setup_completed";
export const CONNECTION_VALIDATION_CACHE_KEY = "clinic_runtime_connection_validation_cache";
// The development/API target is supplied by the same Vite environment used by
// the HTTP client. Setup must display and validate this exact target.
export const LOCAL_SERVER_API_BASE_URL = env.apiBaseUrl;
export const LOCAL_SERVER_ROOT_URL = env.apiBaseUrl.replace(/\/api\/v1\/?$/, "");
export const UNCONFIGURED_CLIENT_API_BASE_URL = "http://0.0.0.0:0/api/v1";
export const isUnconfiguredClientApiBaseUrl = (value) => (value || "").trim().replace(/\/+$/, "") === UNCONFIGURED_CLIENT_API_BASE_URL;
export const normalizeApiBaseUrl = (value) => {
    const trimmed = value.trim();
    if (!trimmed) {
        return LOCAL_SERVER_API_BASE_URL;
    }
    try {
        const withProtocol = /^https?:\/\//i.test(trimmed) ? trimmed : `http://${trimmed}`;
        const url = new URL(withProtocol);
        const cleanPath = url.pathname.replace(/\/+$/, "");
        if (!cleanPath || cleanPath === "/") {
            url.pathname = "/api/v1";
        }
        else if (!cleanPath.endsWith("/api/v1")) {
            url.pathname = `${cleanPath}/api/v1`.replace(/\/{2,}/g, "/");
        }
        url.search = "";
        url.hash = "";
        return url.toString().replace(/\/$/, "");
    }
    catch {
        if (typeof window !== "undefined") {
            window.localStorage.removeItem(SERVER_URL_KEY);
            window.localStorage.removeItem(API_BASE_URL_KEY);
        }
        return LOCAL_SERVER_API_BASE_URL;
    }
};
export const apiRootFromBase = (baseUrl) => {
    const url = new URL(normalizeApiBaseUrl(baseUrl));
    url.pathname = url.pathname.replace(/\/api\/v1\/?$/, "") || "/";
    url.search = "";
    url.hash = "";
    return url.toString().replace(/\/$/, "");
};
export const detectTauriRuntime = () => {
    if (typeof window === "undefined") {
        return false;
    }
    const runtimeWindow = window;
    return Boolean(runtimeWindow.__TAURI__ || runtimeWindow.__TAURI_INTERNALS__);
};
const clearConnectionValidationCacheInternal = () => {
    if (typeof window !== "undefined") {
        window.localStorage.removeItem(CONNECTION_VALIDATION_CACHE_KEY);
    }
};
export const getTauriInvoke = () => {
    if (typeof window === "undefined") {
        return null;
    }
    const runtimeWindow = window;
    return runtimeWindow.__TAURI__?.core?.invoke || runtimeWindow.__TAURI_INTERNALS__?.invoke || null;
};
export const getStoredOperationMode = () => {
    if (typeof window === "undefined") {
        return "client";
    }
    const saved = window.localStorage.getItem(OPERATION_MODE_KEY);
    return saved === "server" ? "server" : "client";
};
export const readStoredOperationMode = () => {
    if (typeof window === "undefined") {
        return null;
    }
    const saved = window.localStorage.getItem(OPERATION_MODE_KEY);
    if (saved === "server" || saved === "client") {
        return saved;
    }
    return null;
};
export const setStoredOperationMode = (mode) => {
    if (typeof window !== "undefined") {
        window.localStorage.setItem(OPERATION_MODE_KEY, mode);
        clearConnectionValidationCacheInternal();
    }
};
export const connectionModeToOperationMode = (mode) => mode === "SERVER_PC" ? "server" : "client";
export const readStoredConnectionMode = () => {
    if (typeof window === "undefined") {
        return null;
    }
    const saved = window.localStorage.getItem(CONNECTION_MODE_KEY);
    return saved === "CLIENT" || saved === "SERVER_PC" || saved === "SERVER" ? saved : null;
};
export const setStoredConnectionMode = (mode) => {
    if (typeof window === "undefined") {
        return;
    }
    if (mode) {
        window.localStorage.setItem(CONNECTION_MODE_KEY, mode);
    }
    else {
        window.localStorage.removeItem(CONNECTION_MODE_KEY);
    }
    clearConnectionValidationCacheInternal();
};
export const getStoredServerUrl = () => {
    if (typeof window === "undefined") {
        return env.apiBaseUrl;
    }
    return window.localStorage.getItem(SERVER_URL_KEY) || "";
};
export const hasStoredServerUrl = () => Boolean(getStoredServerUrl().trim());
export const setStoredServerUrl = (value) => {
    const normalized = value.trim() ? normalizeApiBaseUrl(value) : "";
    if (typeof window !== "undefined") {
        window.localStorage.setItem(SERVER_URL_KEY, normalized);
        clearConnectionValidationCacheInternal();
    }
    return normalized;
};
export const setStoredIsTauri = (value) => {
    if (typeof window !== "undefined") {
        window.localStorage.setItem(IS_TAURI_KEY, String(value));
    }
};
export const getStoredIsTauri = () => {
    if (typeof window === "undefined") {
        return false;
    }
    return window.localStorage.getItem(IS_TAURI_KEY) === "true";
};
export const getStoredSetupCompleted = () => {
    if (typeof window === "undefined") {
        return false;
    }
    return window.localStorage.getItem(SETUP_COMPLETED_KEY) === "true";
};
export const setStoredSetupCompleted = (value) => {
    if (typeof window !== "undefined") {
        window.localStorage.setItem(SETUP_COMPLETED_KEY, String(value));
        if (!value) {
            clearConnectionValidationCacheInternal();
        }
    }
};
export const readConnectionValidationCache = () => {
    if (typeof window === "undefined") {
        return null;
    }
    const raw = window.localStorage.getItem(CONNECTION_VALIDATION_CACHE_KEY);
    if (!raw) {
        return null;
    }
    try {
        const parsed = JSON.parse(raw);
        if ((parsed.mode !== "server" && parsed.mode !== "client") ||
            typeof parsed.apiBaseUrl !== "string" ||
            typeof parsed.serverRootUrl !== "string" ||
            typeof parsed.validatedAt !== "string") {
            clearConnectionValidationCacheInternal();
            return null;
        }
        return {
            mode: parsed.mode,
            apiBaseUrl: normalizeApiBaseUrl(parsed.apiBaseUrl),
            serverRootUrl: parsed.serverRootUrl,
            validatedAt: parsed.validatedAt,
            isTauri: parsed.isTauri === true,
            deploymentState: typeof parsed.deploymentState === "string" ? parsed.deploymentState : null,
        };
    }
    catch {
        clearConnectionValidationCacheInternal();
        return null;
    }
};
export const setConnectionValidationCache = (entry) => {
    if (typeof window === "undefined") {
        return;
    }
    window.localStorage.setItem(CONNECTION_VALIDATION_CACHE_KEY, JSON.stringify({
        ...entry,
        apiBaseUrl: normalizeApiBaseUrl(entry.apiBaseUrl),
        serverRootUrl: entry.serverRootUrl.replace(/\/+$/, ""),
    }));
};
export const clearConnectionValidationCache = () => {
    clearConnectionValidationCacheInternal();
};
export const isConnectionValidationCacheFresh = (entry, options) => {
    if (!entry) {
        return false;
    }
    const normalizedApiBaseUrl = normalizeApiBaseUrl(options.apiBaseUrl);
    if (entry.mode !== options.mode || entry.apiBaseUrl !== normalizedApiBaseUrl || entry.isTauri !== options.isTauri) {
        return false;
    }
    if ((options.deploymentState || null) !== entry.deploymentState) {
        return false;
    }
    const validatedAt = Date.parse(entry.validatedAt);
    if (!Number.isFinite(validatedAt)) {
        return false;
    }
    const ttlMs = options.isTauri ? 5 * 60 * 1000 : 60 * 1000;
    return Date.now() - validatedAt <= ttlMs;
};
const SENSITIVE_DEPLOYMENT_KEYS = [
    "clinic_postgres_host",
    "clinic_postgres_port",
    "clinic_postgres_user",
    "clinic_postgres_password",
    "clinic_postgres_database",
    "clinic_database_url",
    "clinic_sync_connection_postgres_host",
    "clinic_sync_connection_postgres_port",
    "clinic_sync_connection_postgres_user",
    "clinic_sync_connection_postgres_password",
    "clinic_sync_connection_database_url",
    "clinic_sync_connection_admin_password",
    "clinic_sync_connection_app_user_password",
];
const removeSensitiveKeys = (storage) => {
    const keys = Array.from({ length: storage.length }, (_, index) => storage.key(index)).filter((key) => Boolean(key));
    keys.forEach((key) => {
        const lowered = key.toLowerCase();
        const isKnownSensitive = SENSITIVE_DEPLOYMENT_KEYS.includes(key);
        const isLegacyDeploymentSecret = lowered.startsWith("clinic_") &&
            (lowered.includes("postgres") ||
                lowered.includes("database_url") ||
                lowered.includes("admin_password") ||
                lowered.includes("app_user_password"));
        if (isKnownSensitive || isLegacyDeploymentSecret) {
            storage.removeItem(key);
        }
    });
};
export const cleanupSensitiveDeploymentStorage = () => {
    if (typeof window === "undefined") {
        return;
    }
    removeSensitiveKeys(window.localStorage);
    removeSensitiveKeys(window.sessionStorage);
};
export const isRuntimeSetupRequired = () => {
    if (typeof window === "undefined") {
        return false;
    }
    const isTauri = detectTauriRuntime() || getStoredIsTauri();
    if (!isTauri) {
        return false;
    }
    const connectionMode = readStoredConnectionMode();
    const mode = readStoredOperationMode();
    if (!mode) {
        return true;
    }
    if ((connectionMode === "CLIENT" || connectionMode === "SERVER" || mode === "client") && !hasStoredServerUrl()) {
        return true;
    }
    return !getStoredSetupCompleted();
};
export const resolveRuntimeApiBaseUrl = () => {
    if (typeof window === "undefined") {
        return env.apiBaseUrl;
    }
    const isTauri = detectTauriRuntime() || getStoredIsTauri();
    if (!isTauri) {
        return env.apiBaseUrl;
    }
    const connectionMode = readStoredConnectionMode();
    if (connectionMode === "SERVER_PC") {
        return LOCAL_SERVER_API_BASE_URL;
    }
    if (connectionMode === "CLIENT" || connectionMode === "SERVER") {
        return hasStoredServerUrl()
            ? normalizeApiBaseUrl(getStoredServerUrl())
            : UNCONFIGURED_CLIENT_API_BASE_URL;
    }
    const operationMode = readStoredOperationMode() || getStoredOperationMode();
    if (operationMode === "server") {
        return LOCAL_SERVER_API_BASE_URL;
    }
    if (operationMode === "client") {
        return hasStoredServerUrl()
            ? normalizeApiBaseUrl(getStoredServerUrl())
            : UNCONFIGURED_CLIENT_API_BASE_URL;
    }
    return env.apiBaseUrl;
};
