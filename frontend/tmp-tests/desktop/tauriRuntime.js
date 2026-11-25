import { requireSuccessfulDesktopOperation } from "../services/syncSafety";
import { setApiBaseUrl } from "@/api/axios";
import { LOCAL_SERVER_API_BASE_URL, connectionModeToOperationMode, detectTauriRuntime, hasStoredServerUrl, getStoredOperationMode, getStoredServerUrl, getTauriInvoke, normalizeApiBaseUrl, readStoredOperationMode, readStoredConnectionMode, resolveRuntimeApiBaseUrl, setStoredIsTauri, setStoredOperationMode, setStoredConnectionMode, setStoredServerUrl, setStoredSetupCompleted, } from "@/config/runtime";
const defaultContext = () => ({
    isTauri: detectTauriRuntime(),
    operationMode: getStoredOperationMode(),
    connectionMode: readStoredConnectionMode() || (getStoredOperationMode() === "client" ? "CLIENT" : "SERVER_PC"),
    apiBaseUrl: resolveRuntimeApiBaseUrl(),
    serverApiUrl: getStoredServerUrl(),
    localIpAddress: null,
    backendStatus: "Stopped",
    message: "",
});
const invokeDesktop = async (command, args) => {
    const invoke = getTauriInvoke();
    if (!invoke) {
        return null;
    }
    return invoke(command, args);
};
const normalizeContext = (context) => {
    if (!context) {
        return defaultContext();
    }
    return {
        ...context,
        connectionMode: context.connectionMode === "CLIENT" || context.connectionMode === "SERVER_PC" || context.connectionMode === "SERVER"
            ? context.connectionMode
            : context.operationMode === "client"
                ? "CLIENT"
                : "SERVER_PC",
        apiBaseUrl: normalizeApiBaseUrl(context.apiBaseUrl || resolveRuntimeApiBaseUrl()),
        serverApiUrl: context.serverApiUrl ? context.serverApiUrl.replace(/\/$/, "") : getStoredServerUrl(),
    };
};
const persistContext = (context) => {
    setStoredIsTauri(context.isTauri);
    setStoredOperationMode(context.operationMode);
    setStoredConnectionMode(context.connectionMode);
    if (context.operationMode === "client" && context.serverApiUrl) {
        setStoredServerUrl(context.serverApiUrl);
    }
    setApiBaseUrl(context.apiBaseUrl || resolveRuntimeApiBaseUrl());
};
export const tauriRuntime = {
    isTauri: detectTauriRuntime,
    getContext: async () => {
        const context = normalizeContext(await invokeDesktop("get_runtime_context"));
        persistContext(context);
        return context;
    },
    inspectDeploymentState: async () => (await invokeDesktop("inspect_deployment_state")) ?? null,
    applyOperationMode: async (mode, serverUrl) => {
        const connectionMode = mode === "CLIENT" || mode === "SERVER_PC" || mode === "SERVER"
            ? mode
            : mode === "client"
                ? "CLIENT"
                : "SERVER_PC";
        const operationMode = connectionModeToOperationMode(connectionMode);
        const normalizedServerUrl = serverUrl ? normalizeApiBaseUrl(serverUrl) : getStoredServerUrl();
        const context = normalizeContext(await invokeDesktop("apply_operation_mode", {
            mode: connectionMode,
            serverUrl: normalizedServerUrl,
        }));
        const nextContext = {
            ...context,
            operationMode,
            connectionMode,
            serverApiUrl: operationMode === "client" ? normalizedServerUrl : context.serverApiUrl,
            apiBaseUrl: operationMode === "server" ? LOCAL_SERVER_API_BASE_URL : context.apiBaseUrl,
        };
        persistContext(nextContext);
        return nextContext;
    },
    startBackendSidecar: async () => {
        const context = normalizeContext(await invokeDesktop("start_backend_sidecar"));
        persistContext(context);
        return context;
    },
    stopBackendSidecar: async () => {
        const context = normalizeContext(await invokeDesktop("stop_backend_sidecar"));
        persistContext(context);
        return context;
    },
    initialize: async () => {
        const isTauri = detectTauriRuntime();
        setStoredIsTauri(isTauri);
        if (!isTauri) {
            const context = defaultContext();
            setApiBaseUrl(context.apiBaseUrl);
            return context;
        }
        const storedMode = readStoredOperationMode();
        if (!storedMode) {
            const context = defaultContext();
            setApiBaseUrl(context.apiBaseUrl);
            return context;
        }
        if (storedMode === "client" && !hasStoredServerUrl()) {
            const context = defaultContext();
            setApiBaseUrl(context.apiBaseUrl);
            return context;
        }
        const context = await tauriRuntime.applyOperationMode(getStoredOperationMode(), getStoredServerUrl());
        setStoredSetupCompleted(true);
        setApiBaseUrl(context.apiBaseUrl);
        return context;
    },
    inspectPostgresInstallation: async () => (await invokeDesktop("inspect_postgres_installation")) ?? null,
    beginServerProvisioning: async () => (await invokeDesktop("begin_server_provisioning")) ?? null,
    bootstrapServerPostgres: async (payload) => (await invokeDesktop("bootstrap_server_postgres", { request: payload })) ?? null,
    resetServerConfiguration: async (confirmationPhrase) => {
        const result = (await invokeDesktop("reset_server_configuration", { confirmationPhrase })) ?? null;
        if (result?.success) {
            setStoredOperationMode("client");
            setStoredServerUrl("");
            setStoredSetupCompleted(false);
            setApiBaseUrl(resolveRuntimeApiBaseUrl());
        }
        return result;
    },
    inspectClientLocalCopy: async () => (await invokeDesktop("inspect_client_local_copy")) ?? null,
    configureClientLocalCopy: async (payload) => (await invokeDesktop("configure_client_local_copy", { request: payload })) ?? null,
    importClientSync: async (packagePayload, expectedServerId) => (await invokeDesktop("import_client_sync", {
        request: {
            packagePayload,
            expectedServerId: expectedServerId || null,
        },
    })) ?? null,
    importClientSyncPackageFile: async (expectedServerId) => (await invokeDesktop("import_client_sync_package_file", {
        expectedServerId: expectedServerId || null,
    })) ?? null,
    importClientSyncPackagePath: async (packagePath, expectedServerId) => (await invokeDesktop("import_client_sync_package_path", {
        packagePath,
        expectedServerId: expectedServerId || null,
    })) ?? null,
    previewClientSyncPackageFile: async (expectedServerId) => (await invokeDesktop("preview_client_sync_package_file", {
        expectedServerId: expectedServerId || null,
    })) ?? null,
    getClientSyncImportHistory: async () => (await invokeDesktop("get_client_sync_import_history")) ?? null,
    getClientSyncLocalStatus: async () => (await invokeDesktop("get_client_sync_local_status")) ?? null,
    inspectPostgresBackupTools: async () => (await invokeDesktop("inspect_postgres_backup_tools")) ?? null,
    getPostgresBackupStatus: async () => (await invokeDesktop("get_postgres_backup_status")) ?? null,
    chooseBackupDirectory: async () => (await invokeDesktop("choose_backup_directory")) ?? null,
    openBackupDirectory: async () => invokeDesktop("open_backup_directory"),
    createPostgresBackup: async () => requireSuccessfulDesktopOperation(await invokeDesktop("create_postgres_backup")),
    validatePostgresBackup: async (backupPath) => (await invokeDesktop("validate_postgres_backup", { backupPath })) ?? null,
    chooseServerRestoreBackupFile: async () => (await invokeDesktop("choose_server_restore_backup_file")) ?? null,
    finalizeServerSetup: async (payload) => (await invokeDesktop("finalize_server_setup", {
        request: payload,
    })) ?? null,
    restorePostgresBackup: async (backupPath, confirmationPhrase) => (await invokeDesktop("restore_postgres_backup", {
        request: { backupPath, confirmationPhrase },
    })) ?? null,
    exportBackupToUsb: async (backupPath, overwrite = false) => (await invokeDesktop("export_backup_to_usb", {
        request: { backupPath, overwrite },
    })) ?? null,
};
