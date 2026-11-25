import { setApiBaseUrl } from "@/api/axios";
import { LOCAL_SERVER_API_BASE_URL, LOCAL_SERVER_ROOT_URL, apiRootFromBase, clearConnectionValidationCache, connectionModeToOperationMode, detectTauriRuntime, getStoredServerUrl, getStoredSetupCompleted, isConnectionValidationCacheFresh, normalizeApiBaseUrl, readConnectionValidationCache, readStoredOperationMode, setConnectionValidationCache, setStoredOperationMode, setStoredServerUrl, setStoredSetupCompleted, readStoredConnectionMode, } from "@/config/runtime";
import { syncConnectionApi } from "@/services/syncConnectionApi";
import { shouldRequireDatabaseHealth } from "@/services/runtimeConnectionValidationRules";
const TAURI_PENDING_SETUP_STATES = new Set([
    "UNCONFIGURED",
    "SERVER_PROVISIONING",
    "SERVER_DATA_IMPORT_PENDING",
    "SERVER_BACKUP_VALIDATING",
    "SERVER_SAFETY_BACKUP_CREATING",
    "SERVER_BACKUP_RESTORING",
    "SERVER_DATABASE_MIGRATING",
    "SERVER_BACKEND_RESTARTING",
    "SERVER_RESTORE_VERIFYING",
    "SERVER_RESTORE_FAILED",
]);
const NON_FATAL_BACKGROUND_ERRORS = new Set([
    "BACKEND_UNREACHABLE",
    "REQUEST_TIMEOUT",
    "DATABASE_UNAVAILABLE",
    "DATABASE_HEALTH_UNAVAILABLE",
    "BACKEND_STARTING",
    "HEALTH_ENDPOINT_MISSING",
]);
export const isRenderableConnectionState = (state) => state === "connected" || state === "connected_pending_validation";
const createTimeoutSignal = (timeoutMs, parentSignal) => {
    const controller = new AbortController();
    const timeoutId = window.setTimeout(() => controller.abort(), timeoutMs);
    const abortFromParent = () => controller.abort();
    if (parentSignal) {
        if (parentSignal.aborted) {
            controller.abort();
        }
        else {
            parentSignal.addEventListener("abort", abortFromParent, { once: true });
        }
    }
    return {
        signal: controller.signal,
        dispose: () => {
            window.clearTimeout(timeoutId);
            if (parentSignal) {
                parentSignal.removeEventListener("abort", abortFromParent);
            }
        },
    };
};
const parseSafeJson = async (response) => {
    try {
        return (await response.json());
    }
    catch {
        return null;
    }
};
const unwrapEnvelope = (payload) => {
    if (!payload) {
        return null;
    }
    if ("data" in payload && payload.data && typeof payload.data === "object") {
        return payload.data;
    }
    return payload;
};
const strictNormalizeApiBaseUrl = (value) => {
    const trimmed = value.trim();
    if (!trimmed) {
        throw new Error("INVALID_URL");
    }
    const withProtocol = /^https?:\/\//i.test(trimmed) ? trimmed : `http://${trimmed}`;
    let url;
    try {
        url = new URL(withProtocol);
    }
    catch {
        throw new Error("INVALID_URL");
    }
    if (!["http:", "https:"].includes(url.protocol)) {
        throw new Error("INVALID_URL");
    }
    if (!url.hostname) {
        throw new Error("INVALID_URL");
    }
    if (url.username || url.password) {
        throw new Error("INVALID_URL");
    }
    const path = url.pathname.replace(/\/+$/, "");
    if (!path || path === "/") {
        url.pathname = "/api/v1";
    }
    else if (!path.endsWith("/api/v1")) {
        url.pathname = `${path}/api/v1`.replace(/\/{2,}/g, "/");
    }
    url.search = "";
    url.hash = "";
    return normalizeApiBaseUrl(url.toString());
};
const resolveModeTargetUrl = (mode, rawUrl) => mode === "server" ? LOCAL_SERVER_API_BASE_URL : strictNormalizeApiBaseUrl(rawUrl || "");
const buildLocalhostWarning = (baseUrl, mode) => {
    const rootUrl = apiRootFromBase(baseUrl);
    try {
        const { hostname } = new URL(rootUrl);
        if (["localhost", "127.0.0.1", "::1"].includes(hostname)) {
            return mode === "server"
                ? "Cette adresse locale convient a un poste serveur local. Pour les autres postes du reseau, utilisez l'adresse LAN du serveur."
                : "Cette adresse locale convient au developpement sur ce poste, mais elle ne convient pas a un client reseau distant.";
        }
    }
    catch {
        return null;
    }
    return null;
};
const fetchJsonWithValidation = async (rootUrl, path, signal) => {
    const response = await fetch(`${rootUrl}${path}`, {
        method: "GET",
        headers: {
            Accept: "application/json",
        },
        signal,
    });
    const data = await parseSafeJson(response);
    return {
        ok: response.ok,
        status: response.status,
        data,
    };
};
const buildFailure = (result) => ({
    success: false,
    ...result,
});
const persistValidatedConnection = (mode, apiBaseUrl, deploymentState) => {
    const normalizedApiBaseUrl = normalizeApiBaseUrl(apiBaseUrl);
    setStoredOperationMode(mode);
    setStoredServerUrl(normalizedApiBaseUrl);
    setStoredSetupCompleted(true);
    setApiBaseUrl(normalizedApiBaseUrl);
    setConnectionValidationCache({
        mode,
        apiBaseUrl: normalizedApiBaseUrl,
        serverRootUrl: apiRootFromBase(normalizedApiBaseUrl),
        validatedAt: new Date().toISOString(),
        isTauri: detectTauriRuntime(),
        deploymentState,
    });
};
const startupSuccessSnapshot = (baseSnapshot, options) => ({
    ...baseSnapshot,
    state: options.state || "connected_pending_validation",
    mode: options.mode,
    apiBaseUrl: options.apiBaseUrl,
    serverRootUrl: apiRootFromBase(options.apiBaseUrl),
    deploymentState: options.deploymentState,
    message: options.message || null,
    warning: options.warning || null,
    errorCode: null,
    lastValidatedAt: options.lastValidatedAt || null,
});
const failureSnapshot = (baseSnapshot, options) => ({
    ...baseSnapshot,
    state: "connection_error",
    mode: options.mode,
    apiBaseUrl: options.configuredUrl ? strictNormalizeApiBaseUrl(options.configuredUrl) : null,
    serverRootUrl: options.configuredUrl ? apiRootFromBase(strictNormalizeApiBaseUrl(options.configuredUrl)) : null,
    deploymentState: options.deploymentState,
    errorCode: options.errorCode || null,
    message: options.message || null,
    warning: options.warning || null,
});
const validateHealthOnly = async ({ mode, rawUrl, signal, timeoutMs = 3000, persist = false, }) => {
    let canonicalApiBase;
    try {
        canonicalApiBase = resolveModeTargetUrl(mode, rawUrl);
    }
    catch {
        return buildFailure({
            errorCode: "INVALID_URL",
            message: "Adresse de serveur invalide.",
            healthOk: false,
            databaseOk: false,
            mode,
        });
    }
    const rootUrl = apiRootFromBase(canonicalApiBase);
    const { signal: timeoutSignal, dispose } = createTimeoutSignal(timeoutMs, signal);
    try {
        const healthResponse = await fetchJsonWithValidation(rootUrl, "/health", timeoutSignal);
        if (!healthResponse.ok) {
            return buildFailure({
                errorCode: healthResponse.status === 404 ? "HEALTH_ENDPOINT_MISSING" : "BACKEND_UNREACHABLE",
                message: healthResponse.status === 404
                    ? "L'endpoint /health est introuvable sur ce serveur."
                    : "Impossible de joindre l'API. Verifiez que FastAPI est demarre.",
                healthOk: false,
                databaseOk: false,
                mode,
            });
        }
        const healthData = unwrapEnvelope(healthResponse.data);
        if ((healthData?.status || "").toLowerCase() !== "ok") {
            return buildFailure({
                errorCode: "BACKEND_STARTING",
                message: "Le service est en cours de demarrage. Reessayez dans quelques instants.",
                healthOk: false,
                databaseOk: false,
                mode,
            });
        }
        const warning = buildLocalhostWarning(canonicalApiBase, mode);
        if (persist) {
            persistValidatedConnection(mode, canonicalApiBase, null);
        }
        return {
            success: true,
            apiBaseUrl: canonicalApiBase,
            warning: warning || undefined,
            healthOk: true,
            mode,
        };
    }
    catch (error) {
        if (error.name === "AbortError") {
            return buildFailure({
                errorCode: "REQUEST_TIMEOUT",
                message: "La verification a expire. Verifiez l'adresse IP, le port et le pare-feu.",
                healthOk: false,
                databaseOk: false,
                mode,
            });
        }
        return buildFailure({
            errorCode: "BACKEND_UNREACHABLE",
            message: "Impossible de joindre l'API. Verifiez que FastAPI est demarre.",
            healthOk: false,
            databaseOk: false,
            mode,
        });
    }
    finally {
        dispose();
    }
};
export const runtimeConnectionService = {
    defaultSnapshot() {
        return {
            state: "loading",
            isTauri: detectTauriRuntime(),
            mode: null,
            connectionMode: readStoredConnectionMode(),
            apiBaseUrl: null,
            serverRootUrl: null,
            message: null,
            warning: null,
            errorCode: null,
            deploymentState: null,
            lastValidatedAt: null,
        };
    },
    async validateConnection({ mode, rawUrl, signal, timeoutMs = 6000, persist = false, }) {
        let canonicalApiBase;
        try {
            canonicalApiBase = resolveModeTargetUrl(mode, rawUrl);
        }
        catch {
            return buildFailure({
                errorCode: "INVALID_URL",
                message: "Adresse de serveur invalide.",
                healthOk: false,
                databaseOk: false,
                mode,
            });
        }
        const rootUrl = apiRootFromBase(canonicalApiBase);
        const { signal: timeoutSignal, dispose } = createTimeoutSignal(timeoutMs, signal);
        try {
            const healthResponse = await fetchJsonWithValidation(rootUrl, "/health", timeoutSignal);
            if (!healthResponse.ok) {
                return buildFailure({
                    errorCode: healthResponse.status === 404 ? "HEALTH_ENDPOINT_MISSING" : "BACKEND_UNREACHABLE",
                    message: healthResponse.status === 404
                        ? "L'endpoint /health est introuvable sur ce serveur."
                        : "Impossible de joindre l'API. Verifiez que FastAPI est demarre.",
                    healthOk: false,
                    databaseOk: false,
                    mode,
                });
            }
            const healthData = unwrapEnvelope(healthResponse.data);
            if ((healthData?.status || "").toLowerCase() !== "ok") {
                return buildFailure({
                    errorCode: "BACKEND_STARTING",
                    message: "Le service est en cours de demarrage. Reessayez dans quelques instants.",
                    healthOk: false,
                    databaseOk: false,
                    mode,
                });
            }
            const databaseHealthRequest = shouldRequireDatabaseHealth(mode)
                ? fetchJsonWithValidation(rootUrl, "/health/database", timeoutSignal)
                : Promise.resolve(null);
            const identityRequest = fetchJsonWithValidation(rootUrl, "/health/identity", timeoutSignal).catch(() => null);
            const [databaseResponse, identityResponse] = await Promise.all([databaseHealthRequest, identityRequest]);
            let databaseOk = true;
            if (databaseResponse) {
                if (!databaseResponse.ok) {
                    return buildFailure({
                        errorCode: "DATABASE_HEALTH_UNAVAILABLE",
                        message: "L'API repond, mais l'endpoint /health/database est indisponible.",
                        apiBaseUrl: canonicalApiBase,
                        healthOk: true,
                        databaseOk: false,
                        mode,
                    });
                }
                const databaseData = unwrapEnvelope(databaseResponse.data);
                const databaseStatus = String(databaseData?.status || databaseData?.database_status || "").toLowerCase();
                if (databaseStatus !== "ok") {
                    return buildFailure({
                        errorCode: "DATABASE_UNAVAILABLE",
                        message: "L'API repond, mais PostgreSQL n'est pas disponible.",
                        apiBaseUrl: canonicalApiBase,
                        healthOk: true,
                        databaseOk: false,
                        mode,
                    });
                }
            }
            if (identityResponse?.ok) {
                const identityData = unwrapEnvelope(identityResponse.data);
                if (identityData?.application && identityData.application !== "medical-folder") {
                    return buildFailure({
                        errorCode: "WRONG_API_SERVER",
                        message: "Cette adresse ne correspond pas au backend Ibn Sina attendu.",
                        apiBaseUrl: canonicalApiBase,
                        healthOk: true,
                        databaseOk,
                        mode,
                    });
                }
            }
            const warning = buildLocalhostWarning(canonicalApiBase, mode);
            if (persist) {
                persistValidatedConnection(mode, canonicalApiBase, null);
            }
            return {
                success: true,
                apiBaseUrl: canonicalApiBase,
                warning: warning || undefined,
                healthOk: true,
                databaseOk,
                mode,
            };
        }
        catch (error) {
            if (error.name === "AbortError") {
                return buildFailure({
                    errorCode: "REQUEST_TIMEOUT",
                    message: "La verification a expire. Verifiez l'adresse IP, le port et le pare-feu.",
                    healthOk: false,
                    databaseOk: false,
                    mode,
                });
            }
            return buildFailure({
                errorCode: "BACKEND_UNREACHABLE",
                message: "Impossible de joindre l'API. Verifiez que FastAPI est demarre.",
                healthOk: false,
                databaseOk: false,
                mode,
            });
        }
        finally {
            dispose();
        }
    },
    async validateStartupConnection({ mode, rawUrl, signal, timeoutMs = 3000, persist = false, }) {
        return validateHealthOnly({
            mode,
            rawUrl,
            signal,
            timeoutMs,
            persist,
        });
    },
    async validateConnectedSnapshot({ mode, rawUrl, signal, timeoutMs = 6000, persist = false, deploymentState = null, }) {
        const result = await runtimeConnectionService.validateConnection({
            mode,
            rawUrl,
            signal,
            timeoutMs,
            persist: false,
        });
        if (result.success && result.apiBaseUrl && persist) {
            persistValidatedConnection(mode, result.apiBaseUrl, deploymentState);
        }
        return result;
    },
    async initializeConnection(signal) {
        const resolved = await runtimeConnectionService.resolveConfiguredTarget(signal);
        const { snapshot, mode, deploymentState, targetUrl, inspectionMessage } = resolved;
        if (!mode || !targetUrl) {
            return snapshot;
        }
        let normalizedTargetUrl;
        try {
            normalizedTargetUrl = strictNormalizeApiBaseUrl(targetUrl);
        }
        catch {
            return failureSnapshot(snapshot, {
                mode,
                configuredUrl: targetUrl,
                deploymentState,
                errorCode: "INVALID_URL",
                message: "Adresse de serveur invalide.",
            });
        }
        const cachedValidation = readConnectionValidationCache();
        if (isConnectionValidationCacheFresh(cachedValidation, {
            mode,
            apiBaseUrl: normalizedTargetUrl,
            isTauri: snapshot.isTauri,
            deploymentState,
        })) {
            setApiBaseUrl(normalizedTargetUrl);
            return startupSuccessSnapshot(snapshot, {
                mode,
                apiBaseUrl: normalizedTargetUrl,
                deploymentState,
                message: inspectionMessage || "Connexion en cours de revalidation.",
                warning: buildLocalhostWarning(normalizedTargetUrl, mode),
                lastValidatedAt: cachedValidation?.validatedAt || null,
            });
        }
        const validation = await runtimeConnectionService.validateStartupConnection({
            mode,
            rawUrl: normalizedTargetUrl,
            signal,
            persist: false,
        });
        if (!validation.success || !validation.apiBaseUrl) {
            setStoredSetupCompleted(false);
            clearConnectionValidationCache();
            return failureSnapshot(snapshot, {
                mode,
                configuredUrl: normalizedTargetUrl,
                deploymentState,
                errorCode: validation.errorCode || null,
                message: validation.message || inspectionMessage || null,
                warning: validation.warning || null,
            });
        }
        persistValidatedConnection(mode, validation.apiBaseUrl, deploymentState);
        return startupSuccessSnapshot(snapshot, {
            mode,
            apiBaseUrl: validation.apiBaseUrl,
            deploymentState,
            message: inspectionMessage || "Validation complete en arriere-plan.",
            warning: validation.warning || null,
            lastValidatedAt: new Date().toISOString(),
        });
    },
    async resolveConfiguredTarget(_signal) {
        const isTauri = detectTauriRuntime();
        const snapshot = runtimeConnectionService.defaultSnapshot();
        if (isTauri) {
            const inspection = await syncConnectionApi.inspectDeploymentState().catch(() => null);
            const deploymentState = inspection?.state || null;
            const inspectedMode = inspection?.operationMode === "server" || inspection?.operationMode === "client"
                ? inspection.operationMode
                : null;
            const inspectedConnectionMode = inspection?.connectionMode === "CLIENT" || inspection?.connectionMode === "SERVER_PC" || inspection?.connectionMode === "SERVER"
                ? inspection.connectionMode
                : null;
            const storedConnectionMode = readStoredConnectionMode();
            const storedMode = readStoredOperationMode();
            const connectionMode = inspectedConnectionMode || storedConnectionMode;
            const mode = connectionMode ? connectionModeToOperationMode(connectionMode) : inspectedMode || storedMode;
            const configuredServerUrl = inspection?.serverApiUrl || getStoredServerUrl() || null;
            if (!mode || TAURI_PENDING_SETUP_STATES.has(deploymentState || "UNCONFIGURED")) {
                return {
                    snapshot: {
                        ...snapshot,
                        state: "unconfigured",
                        mode,
                        apiBaseUrl: configuredServerUrl ? strictNormalizeApiBaseUrl(configuredServerUrl) : null,
                        serverRootUrl: configuredServerUrl ? apiRootFromBase(strictNormalizeApiBaseUrl(configuredServerUrl)) : null,
                        deploymentState,
                        message: inspection?.message || null,
                    },
                    mode,
                    deploymentState,
                    targetUrl: null,
                    inspectionMessage: inspection?.message || null,
                };
            }
            if (mode === "server" && !["SERVER_CONFIGURED", "SERVER_RUNNING"].includes(deploymentState || "")) {
                return {
                    snapshot: {
                        ...snapshot,
                        state: "unconfigured",
                        mode,
                        deploymentState,
                        message: inspection?.message || null,
                    },
                    mode,
                    deploymentState,
                    targetUrl: null,
                    inspectionMessage: inspection?.message || null,
                };
            }
            if (mode === "server") {
                await syncConnectionApi.startLocalServer();
            }
            return {
                snapshot,
                mode,
                deploymentState,
                targetUrl: mode === "server" ? inspection?.serverApiUrl || LOCAL_SERVER_ROOT_URL : configuredServerUrl,
                inspectionMessage: inspection?.message || null,
            };
        }
        const storedConnectionMode = readStoredConnectionMode();
        const storedMode = storedConnectionMode ? connectionModeToOperationMode(storedConnectionMode) : readStoredOperationMode();
        const storedUrl = getStoredServerUrl();
        if (!storedMode || !storedUrl || !getStoredSetupCompleted()) {
            return {
                snapshot: {
                    ...snapshot,
                    state: "unconfigured",
                    mode: storedMode,
                    apiBaseUrl: storedUrl || null,
                    serverRootUrl: storedUrl ? apiRootFromBase(storedUrl) : null,
                },
                mode: storedMode,
                deploymentState: null,
                targetUrl: null,
                inspectionMessage: null,
            };
        }
        return {
            snapshot,
            mode: storedMode,
            deploymentState: null,
            targetUrl: storedUrl,
            inspectionMessage: null,
        };
    },
    applyBackgroundValidationResult(current, result) {
        if (!current.mode || !current.apiBaseUrl) {
            return current;
        }
        if (result.success && result.apiBaseUrl) {
            return {
                ...current,
                state: "connected",
                apiBaseUrl: result.apiBaseUrl,
                serverRootUrl: apiRootFromBase(result.apiBaseUrl),
                message: null,
                warning: result.warning || null,
                errorCode: null,
                lastValidatedAt: new Date().toISOString(),
            };
        }
        if (NON_FATAL_BACKGROUND_ERRORS.has(result.errorCode || "")) {
            return {
                ...current,
                state: "connected",
                message: result.message || current.message,
                warning: result.warning || current.warning,
                errorCode: result.errorCode || current.errorCode,
            };
        }
        return {
            ...current,
            state: "connection_error",
            message: result.message || current.message,
            warning: result.warning || current.warning,
            errorCode: result.errorCode || current.errorCode,
        };
    },
};
