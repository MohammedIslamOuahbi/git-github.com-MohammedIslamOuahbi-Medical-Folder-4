import { requireSuccessfulDesktopOperation } from "../services/syncSafety";
import { setApiBaseUrl } from "@/api/axios";
import {
  LOCAL_SERVER_API_BASE_URL,
  ConnectionMode,
  OperationMode,
  connectionModeToOperationMode,
  detectTauriRuntime,
  hasStoredServerUrl,
  getStoredOperationMode,
  getStoredServerUrl,
  getTauriInvoke,
  normalizeApiBaseUrl,
  readStoredOperationMode,
  readStoredConnectionMode,
  resolveRuntimeApiBaseUrl,
  setStoredIsTauri,
  setStoredOperationMode,
  setStoredConnectionMode,
  setStoredServerUrl,
  setStoredSetupCompleted,
} from "@/config/runtime";

export type BackendLifecycleStatus = "Starting" | "Running" | "Failed" | "Stopped";

export type DesktopRuntimeContext = {
  isTauri: boolean;
  operationMode: OperationMode;
  connectionMode: ConnectionMode;
  deploymentState?: string;
  apiBaseUrl: string;
  serverApiUrl: string;
  localIpAddress: string | null;
  backendStatus: BackendLifecycleStatus;
  message: string;
};

export type DeploymentInspection = {
  state: string;
  serverRuntimeConfigExists: boolean;
  serverRuntimeConfigValid: boolean;
  clientServerUrlExists: boolean;
  localCopyConfigExists: boolean;
  operationMode: OperationMode;
  connectionMode: ConnectionMode;
  serverApiUrl: string | null;
  message: string;
};

export type PostgresInspection = {
  installed: boolean;
  psqlPath: string | null;
  serviceName: string | null;
  serviceStatus: string | null;
  localIpAddress: string | null;
  runtimeConfigPath: string;
  runtimeConfigExists: boolean;
  bundledConfigExists: boolean;
  message: string;
};

export type ServerBootstrapPayload = {
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
};

export type ProvisioningCapabilityResponse = {
  capability: string;
  expiresInSeconds: number;
  deploymentState: string;
};

export type ServerBootstrapResult = {
  success: boolean;
  step: string;
  message: string;
  details: string[];
  lanIp: string | null;
  apiUrl: string | null;
  databaseReady: boolean;
  migrationApplied: boolean;
  importApplied: boolean;
  firewallRuleApplied: boolean;
  configPath: string | null;
  warning: string | null;
};

export type ServerResetResult = {
  success: boolean;
  state: string;
  databasePreserved: boolean;
  runtimeConfigRemoved: boolean;
  clientLocalCopyPreserved: boolean;
  backupsPreserved: boolean;
  message: string;
};

export type ClientLocalCopyConfigPayload = {
  host: string;
  port: number;
  databaseName: string;
  user: string;
  password: string;
};

export type ClientLocalCopyInspection = {
  configured: boolean;
  host: string | null;
  port: number | null;
  databaseName: string | null;
  message: string;
};

export type ClientSyncImportResult = {
  success: boolean;
  serverId?: string | null;
  fromCursor?: number | null;
  toCursor?: number | null;
  insertedCount?: number | null;
  updatedCount?: number | null;
  deletedCount?: number | null;
  skippedCount?: number | null;
  fileCount?: number | null;
  attachmentCount?: number | null;
  checksumSha256?: string | null;
  packageId?: string | null;
  packageName?: string | null;
  summary?: {
    server?: string | null;
    workspace?: string | null;
    created?: string | null;
    applicationVersion?: string | null;
    schemaVersion?: number | null;
    workers?: number | null;
    visits?: number | null;
    certificates?: number | null;
    medicalTests?: number | null;
    companies?: number | null;
    campaigns?: number | null;
    users?: number | null;
    totalChanges?: number | null;
  } | null;
  message: string;
};

export type ClientSyncPackagePreview = {
  valid: boolean;
  selectedPath?: string | null;
  packageId?: string | null;
  packageName?: string | null;
  checksumSha256?: string | null;
  serverId?: string | null;
  fromCursor?: number | null;
  toCursor?: number | null;
  createdAt?: string | null;
  applicationVersion?: string | null;
  schemaVersion?: number | null;
  workspace?: { id?: number | null; name?: string | null } | null;
  recordCounts?: Record<string, number> | null;
  tombstoneCount?: number | null;
  attachmentCount?: number | null;
  duplicate?: boolean | null;
  summary?: ClientSyncImportResult["summary"];
};

export type ClientSyncHistoryEntry = {
  id: number;
  packageId?: string | null;
  packageName?: string | null;
  date?: string | null;
  durationMs?: number | null;
  rowsImported?: number | null;
  rowsUpdated?: number | null;
  rowsSkipped?: number | null;
  attachmentsImported?: number | null;
  checksumSha256?: string | null;
  status: string;
  serverId?: string | null;
  fromCursor?: number | null;
  toCursor?: number | null;
  deletedCount?: number | null;
  errorCode?: string | null;
};

export type ClientSyncLocalStatus = {
  configured: boolean;
  serverId?: string | null;
  lastSyncCursor?: number | null;
  lastSyncAt?: string | null;
  lastPackageId?: string | null;
  lastPackageName?: string | null;
  lastImportedAt?: string | null;
  lastPackageChecksum?: string | null;
  schemaVersion?: number | null;
  lastStatus?: string | null;
  historyCount?: number | null;
  importedRowsTotal?: number | null;
  skippedRowsTotal?: number | null;
  latestRun?: Record<string, unknown> | null;
};

export type PostgresBackupToolsInspection = {
  pgDumpAvailable: boolean;
  pgRestoreAvailable: boolean;
  pgDumpPath: string | null;
  pgRestorePath: string | null;
  postgresBinDirectory: string | null;
  message: string;
};

export type PostgresBackupFile = {
  filename: string;
  path: string;
  createdAt: string | null;
  sizeBytes: number;
  format: string;
  status: string;
  checksumSha256: string | null;
};

export type PostgresBackupStatus = {
  deviceMode: string;
  serverActionsAvailable: boolean;
  backupFolder: string | null;
  backupFolderWritable: boolean;
  tools: PostgresBackupToolsInspection;
  operationState: string;
  backups: PostgresBackupFile[];
  lastBackupTime: string | null;
  lastBackupStatus: string;
  message: string;
};

export type PostgresBackupOperationResult = {
  success: boolean;
  operationState: string;
  message: string;
  backup: PostgresBackupFile | null;
  safetyBackup: PostgresBackupFile | null;
  destinationPath: string | null;
  checksumSha256: string | null;
};

export type SelectedBackupFile = {
  filename: string;
  path: string;
  sizeBytes: number;
};

export type FinalizeServerSetupResult = {
  success: boolean;
  state: string;
  message: string;
  detail: string;
  completed: boolean;
  activeStep: string;
  steps: string[];
  selectedBackup: SelectedBackupFile | null;
  safetyBackup: PostgresBackupFile | null;
};

const defaultContext = (): DesktopRuntimeContext => ({
  isTauri: detectTauriRuntime(),
  operationMode: getStoredOperationMode(),
  connectionMode: readStoredConnectionMode() || (getStoredOperationMode() === "client" ? "CLIENT" : "SERVER_PC"),
  apiBaseUrl: resolveRuntimeApiBaseUrl(),
  serverApiUrl: getStoredServerUrl(),
  localIpAddress: null,
  backendStatus: "Stopped",
  message: "",
});

const invokeDesktop = async <T>(command: string, args?: Record<string, unknown>): Promise<T | null> => {
  const invoke = getTauriInvoke();
  if (!invoke) {
    return null;
  }

  return invoke<T>(command, args);
};

const normalizeContext = (context: DesktopRuntimeContext | null): DesktopRuntimeContext => {
  if (!context) {
    return defaultContext();
  }

  return {
    ...context,
    connectionMode:
      context.connectionMode === "CLIENT" || context.connectionMode === "SERVER_PC" || context.connectionMode === "SERVER"
        ? context.connectionMode
        : context.operationMode === "client"
          ? "CLIENT"
          : "SERVER_PC",
    apiBaseUrl: normalizeApiBaseUrl(context.apiBaseUrl || resolveRuntimeApiBaseUrl()),
    serverApiUrl: context.serverApiUrl ? context.serverApiUrl.replace(/\/$/, "") : getStoredServerUrl(),
  };
};

const persistContext = (context: DesktopRuntimeContext) => {
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
    const context = normalizeContext(await invokeDesktop<DesktopRuntimeContext>("get_runtime_context"));
    persistContext(context);
    return context;
  },
  inspectDeploymentState: async () =>
    (await invokeDesktop<DeploymentInspection>("inspect_deployment_state")) ?? null,
  applyOperationMode: async (mode: OperationMode | ConnectionMode, serverUrl?: string) => {
    const connectionMode: ConnectionMode =
      mode === "CLIENT" || mode === "SERVER_PC" || mode === "SERVER"
        ? mode
        : mode === "client"
          ? "CLIENT"
          : "SERVER_PC";
    const operationMode = connectionModeToOperationMode(connectionMode);
    const normalizedServerUrl = serverUrl ? normalizeApiBaseUrl(serverUrl) : getStoredServerUrl();
    const context = normalizeContext(
      await invokeDesktop<DesktopRuntimeContext>("apply_operation_mode", {
        mode: connectionMode,
        serverUrl: normalizedServerUrl,
      }),
    );

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
    const context = normalizeContext(await invokeDesktop<DesktopRuntimeContext>("start_backend_sidecar"));
    persistContext(context);
    return context;
  },
  stopBackendSidecar: async () => {
    const context = normalizeContext(await invokeDesktop<DesktopRuntimeContext>("stop_backend_sidecar"));
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
  inspectPostgresInstallation: async () =>
    (await invokeDesktop<PostgresInspection>("inspect_postgres_installation")) ?? null,
  beginServerProvisioning: async () =>
    (await invokeDesktop<ProvisioningCapabilityResponse>("begin_server_provisioning")) ?? null,
  bootstrapServerPostgres: async (payload: ServerBootstrapPayload) =>
    (await invokeDesktop<ServerBootstrapResult>("bootstrap_server_postgres", { request: payload })) ?? null,
  resetServerConfiguration: async (confirmationPhrase: string) => {
    const result =
      (await invokeDesktop<ServerResetResult>("reset_server_configuration", { confirmationPhrase })) ?? null;
    if (result?.success) {
      setStoredOperationMode("client");
      setStoredServerUrl("");
      setStoredSetupCompleted(false);
      setApiBaseUrl(resolveRuntimeApiBaseUrl());
    }
    return result;
  },
  inspectClientLocalCopy: async () =>
    (await invokeDesktop<ClientLocalCopyInspection>("inspect_client_local_copy")) ?? null,
  configureClientLocalCopy: async (payload: ClientLocalCopyConfigPayload) =>
    (await invokeDesktop<ClientLocalCopyInspection>("configure_client_local_copy", { request: payload })) ?? null,
  importClientSync: async (packagePayload: unknown, expectedServerId?: string | null) =>
    (await invokeDesktop<ClientSyncImportResult>("import_client_sync", {
      request: {
        packagePayload,
        expectedServerId: expectedServerId || null,
      },
    })) ?? null,
  importClientSyncPackageFile: async (expectedServerId?: string | null) =>
    (await invokeDesktop<ClientSyncImportResult>("import_client_sync_package_file", {
      expectedServerId: expectedServerId || null,
    })) ?? null,
  importClientSyncPackagePath: async (packagePath: string, expectedServerId?: string | null) =>
    (await invokeDesktop<ClientSyncImportResult>("import_client_sync_package_path", {
      packagePath,
      expectedServerId: expectedServerId || null,
    })) ?? null,
  previewClientSyncPackageFile: async (expectedServerId?: string | null) =>
    (await invokeDesktop<ClientSyncPackagePreview>("preview_client_sync_package_file", {
      expectedServerId: expectedServerId || null,
    })) ?? null,
  getClientSyncImportHistory: async () =>
    (await invokeDesktop<{ history: ClientSyncHistoryEntry[] }>("get_client_sync_import_history")) ?? null,
  getClientSyncLocalStatus: async () =>
    (await invokeDesktop<ClientSyncLocalStatus>("get_client_sync_local_status")) ?? null,
  inspectPostgresBackupTools: async () =>
    (await invokeDesktop<PostgresBackupToolsInspection>("inspect_postgres_backup_tools")) ?? null,
  getPostgresBackupStatus: async () =>
    (await invokeDesktop<PostgresBackupStatus>("get_postgres_backup_status")) ?? null,
  chooseBackupDirectory: async () =>
    (await invokeDesktop<PostgresBackupStatus>("choose_backup_directory")) ?? null,
  openBackupDirectory: async () => invokeDesktop<void>("open_backup_directory"),
  createPostgresBackup: async () =>
    requireSuccessfulDesktopOperation(await invokeDesktop<PostgresBackupOperationResult>("create_postgres_backup")),
  validatePostgresBackup: async (backupPath: string) =>
    (await invokeDesktop<PostgresBackupFile>("validate_postgres_backup", { backupPath })) ?? null,
  chooseServerRestoreBackupFile: async () =>
    (await invokeDesktop<SelectedBackupFile>("choose_server_restore_backup_file")) ?? null,
  finalizeServerSetup: async (payload: {
    mode: "initial" | "restore";
    backupPath?: string;
    confirmationPhrase?: string;
  }) =>
    (await invokeDesktop<FinalizeServerSetupResult>("finalize_server_setup", {
      request: payload,
    })) ?? null,
  restorePostgresBackup: async (backupPath: string, confirmationPhrase: string) =>
    (await invokeDesktop<PostgresBackupOperationResult>("restore_postgres_backup", {
      request: { backupPath, confirmationPhrase },
    })) ?? null,
  exportBackupToUsb: async (backupPath: string, overwrite = false) =>
    (await invokeDesktop<PostgresBackupOperationResult>("export_backup_to_usb", {
      request: { backupPath, overwrite },
    })) ?? null,
};
