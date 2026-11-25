export const BROWSER_SERVER_UNAVAILABLE_MESSAGE = "Le navigateur ne peut pas installer ou demarrer le serveur local. Demarrez le backend manuellement ou utilisez l'application de bureau pour effectuer la configuration complete.";
export const BROWSER_SERVER_START_COMMANDS = [
    "cd C:\\Users\\pc\\Desktop\\medical-folder-1\\backend",
    ".\\venv\\Scripts\\Activate.ps1",
    "python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload",
];
export const BROWSER_AVAILABLE_MODES = ["server", "client"];
export const TAURI_AVAILABLE_MODES = ["server", "client"];
export const isLocalhostHostname = (hostname) => ["localhost", "127.0.0.1", "::1"].includes(hostname.trim().toLowerCase());
export const resolveRuntimePlatform = (isTauri) => (isTauri ? "tauri" : "browser");
export const canProvisionServer = (runtimePlatform) => runtimePlatform === "tauri";
export const resolveSetupStrategy = (runtimePlatform, mode) => {
    if (runtimePlatform === "tauri") {
        return mode === "server" ? "tauri-server-provisioning" : "tauri-client-validation";
    }
    return mode === "server" ? "browser-server-manual-validation" : "browser-client-validation";
};
export const canNavigateToLoginAfterValidation = (result) => result.success;
export const resolveSetupConnectionPolicy = (connectionMode, localServerRootUrl) => ({
    requiresRemoteServerUrl: connectionMode !== "SERVER_PC",
    resolvedServerRootUrl: connectionMode === "SERVER_PC" ? localServerRootUrl : null,
});
export const normalizeOptionalApiUrl = (value) => value.trim();
const ensureHttpProtocol = (value) => (/^https?:\/\//i.test(value) ? value : `http://${value}`);
export const deriveServerRootUrl = (serverAddress, apiPort, optionalApiUrl) => {
    const explicitUrl = normalizeOptionalApiUrl(optionalApiUrl);
    if (explicitUrl) {
        return ensureHttpProtocol(explicitUrl).replace(/\/+$/, "");
    }
    const address = serverAddress.trim();
    const port = apiPort.trim();
    if (!address) {
        return "";
    }
    const withProtocol = ensureHttpProtocol(address).replace(/\/+$/, "");
    if (!port) {
        return withProtocol;
    }
    try {
        const parsed = new URL(withProtocol);
        parsed.port = port;
        parsed.pathname = "";
        parsed.search = "";
        parsed.hash = "";
        return parsed.toString().replace(/\/$/, "");
    }
    catch {
        return `${withProtocol}:${port}`;
    }
};
export const deriveApiBaseUrl = (serverRoot) => {
    const trimmed = serverRoot.trim();
    if (!trimmed) {
        return "";
    }
    const url = new URL(ensureHttpProtocol(trimmed));
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
};
export const shouldRequireModeChangeConfirmation = ({ currentMode, nextMode, hasExistingConfiguration, }) => hasExistingConfiguration && Boolean(currentMode) && currentMode !== nextMode;
export const mapValidationStateToHealthStatuses = (validationState) => {
    switch (validationState) {
        case "connected":
            return { apiStatus: "available", databaseStatus: "available" };
        case "database_unavailable":
            return { apiStatus: "available", databaseStatus: "unavailable" };
        case "api_unavailable":
            return { apiStatus: "unavailable", databaseStatus: "idle" };
        case "validating":
        case "idle":
        default:
            return { apiStatus: "idle", databaseStatus: "idle" };
    }
};
export const buildBrowserStatusPanel = ({ mode, usedUrl, validationState, canProvision, }) => ({
    ...mapValidationStateToHealthStatuses(validationState),
    selectedModeLabel: mode === "server" ? "Serveur" : "Client",
    usedUrl,
    manualStartMessage: mode === "server" && !canProvision && validationState === "api_unavailable"
        ? BROWSER_SERVER_UNAVAILABLE_MESSAGE
        : null,
});
export const getStatusLabel = (status) => {
    if (status === "available") {
        return "Disponible";
    }
    if (status === "unavailable") {
        return "Indisponible";
    }
    return "Non verifiee";
};
