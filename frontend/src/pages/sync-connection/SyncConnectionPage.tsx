import { useEffect, useMemo, useState } from "react";
import {
  Activity,
  AlertTriangle,
  Database,
  Globe,
  HardDrive,
  Info,
  LayoutDashboard,
  MonitorSmartphone,
  Network,
  RefreshCw,
  Server,
  ShieldCheck,
  Trash2,
} from "lucide-react";

import { Badge } from "@/components/common/Badge";
import { Button } from "@/components/common/Button";
import { Card } from "@/components/common/Card";
import { Modal } from "@/components/common/Modal";
import { SectionHeader } from "@/components/common/SectionHeader";
import { useAuth } from "@/hooks/useAuth";
import { useNetworkCenter } from "@/hooks/useNetworkCenter";
import { useSync } from "@/hooks/useSync";
import {
  extractBlobError,
  syncConnectionApi,
  type ClientSyncExportPayload,
  type ClientSyncStatusPayload,
} from "@/services/syncConnectionApi";
import type {
  ClientLocalCopyInspection,
  ClientSyncHistoryEntry,
  ClientSyncImportResult,
  ClientSyncLocalStatus,
  ClientSyncPackagePreview,
  DesktopRuntimeContext,
  PostgresBackupFile,
  PostgresBackupToolsInspection,
} from "@/desktop/tauriRuntime";

import { BackupPanel } from "./BackupPanel";
import { RecoveryPanel } from "./RecoveryPanel";
import { ClientModePanel } from "./ClientModePanel";
import { ConnectedUsersTable, type ConnectedUserRow } from "./ConnectedUsersTable";
import { DeviceRuntimePanel } from "./DeviceRuntimePanel";
import { ServerModePanel } from "./ServerModePanel";
import { SyncStatusPanel } from "./SyncStatusPanel";

const LAST_SYNC_KEY = "clinic_sync_connection_last_sync";
const MODE_KEY = "clinic_sync_connection_mode";
const SERVER_URL_KEY = "clinic_sync_connection_server_url";
const IS_TAURI_KEY = "clinic_sync_connection_is_tauri";
const SETUP_COMPLETED_KEY = "clinic_sync_connection_setup_completed";
const SERVER_RESET_CONFIRMATION = "REINITIALISER LE SERVEUR";

type ConnectionMode = "server" | "client";

type LocalSystemLog = {
  id: string;
  message: string;
  timestamp: string;
  tone: "active" | "pending" | "failed";
};

type BackupStatusState = {
  enabled: boolean;
  backup_folder: string;
  backup_count: number;
  last_backup_time: string | null;
  last_backup_status: string | null;
  server_actions_available?: boolean;
  backup_folder_writable?: boolean;
  operation_state?: string;
  operation_started_at?: string | null;
  operation_last_error?: string | null;
  pg_dump_available?: boolean;
  pg_restore_available?: boolean;
  tools?: PostgresBackupToolsInspection | null;
  backups?: PostgresBackupFile[];
} | null;

type ClientLocalCopyState =
  | "IDLE"
  | "LOCAL_DATABASE_REQUIRED"
  | "VALIDATION"
  | "CHECKING"
  | "NO_UPDATE"
  | "UPDATE_AVAILABLE"
  | "PREPARING"
  | "DOWNLOADING"
  | "VERIFYING"
  | "INITIALIZING_SCHEMA"
  | "IMPORTING"
  | "COMPLETED"
  | "CANCELLED"
  | "FAILED";

type ClientLocalCopyForm = {
  host: string;
  port: string;
  databaseName: string;
  user: string;
  password: string;
};

const formatDateTime = (value: string | null | undefined) => {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return new Intl.DateTimeFormat("fr-FR", {
    dateStyle: "short",
    timeStyle: "short",
  }).format(date);
};

const normalizeRoleLabel = (role: string | null | undefined) => {
  if (!role) return "Utilisateur";
  return role.replace(/_/g, " ");
};

const parseUrlInfo = (value: string) => {
  try {
    const url = new URL(value);
    return {
      host: url.hostname,
      port: url.port || (url.protocol === "https:" ? "443" : "80"),
      href: url.toString().replace(/\/$/, ""),
    };
  } catch {
    return {
      host: "-",
      port: "-",
      href: value || "-",
    };
  }
};

const getQueueLength = (value: unknown) => (Array.isArray(value) ? value.length : 0);
const clientSyncStageLabels: Record<ClientLocalCopyState, string> = {
  IDLE: "En attente",
  LOCAL_DATABASE_REQUIRED: "Base locale requise",
  VALIDATION: "Validation",
  CHECKING: "Validation",
  NO_UPDATE: "Aucune mise a jour",
  UPDATE_AVAILABLE: "Mises a jour detectees",
  PREPARING: "Lecture",
  DOWNLOADING: "Analyse",
  VERIFYING: "Verification",
  INITIALIZING_SCHEMA: "Initialisation",
  IMPORTING: "Importation",
  COMPLETED: "Finalisation",
  CANCELLED: "Annule",
  FAILED: "Echec",
};

const mapConnectionStatus = (value: string | null | undefined) => {
  const normalized = (value || "").toLowerCase();
  if (normalized.includes("offline")) return "Déconnecté";
  if (normalized.includes("mission server") || normalized.includes("connected") || normalized.includes("online")) {
    return "Connecté";
  }
  if (normalized.includes("error") || normalized.includes("erreur")) return "Erreur";
  return value || "Déconnecté";
};

const getUserRowStatus = (status: string | null | undefined, lastSeen: string | null | undefined) => {
  const normalized = (status || "").toLowerCase();
  if (normalized.includes("offline")) return "offline";
  if (lastSeen) {
    const diff = Date.now() - new Date(lastSeen).getTime();
    if (Number.isFinite(diff) && diff > 5 * 60 * 1000) {
      return "inactive";
    }
  }
  if (normalized.includes("mission server") || normalized.includes("connected") || normalized.includes("online")) {
    return "online";
  }
  return "offline";
};

const detectTauriRuntime = () =>
  typeof window !== "undefined" &&
  (("__TAURI__" in window && Boolean((window as Window & { __TAURI__?: unknown }).__TAURI__)) ||
    ("__TAURI_INTERNALS__" in window &&
      Boolean((window as Window & { __TAURI_INTERNALS__?: unknown }).__TAURI_INTERNALS__)));

const validateFastApiRootUrl = (value: string) => {
  const url = new URL(/^https?:\/\//i.test(value) ? value : `http://${value}`);
  if (!["http:", "https:"].includes(url.protocol)) {
    throw new Error("Seules les URL HTTP ou HTTPS sont autorisees.");
  }
  if (!url.hostname) {
    throw new Error("L'URL API doit contenir une adresse serveur.");
  }
  if (url.username || url.password) {
    throw new Error("L'URL API ne doit pas contenir d'identifiants integres.");
  }
  if (url.port === "5173") {
    throw new Error("URL frontend invalide en production. Utilisez http://IP:8000.");
  }
};

export const SyncConnectionPage = () => {
  const { user } = useAuth();
  const { queue, status, conflicts, online, syncing, syncNow } = useSync();
  const {
    connectedDevices,
    currentConnectionState,
    wifiConnectionStatus,
    localIpAddress,
    databaseStatus,
    selectedServer,
    missionServer,
    wsConnected,
    refreshStatus,
  } = useNetworkCenter();

  const [serverUrl, setServerUrl] = useState(syncConnectionApi.getLastServerUrl());
  const [mode, setMode] = useState<ConnectionMode>(
    (typeof window !== "undefined" ? (window.localStorage.getItem(MODE_KEY) as ConnectionMode | null) : null) || "client",
  );
  const [isTauri, setIsTauri] = useState(syncConnectionApi.getIsTauri());
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [lastSyncedAt, setLastSyncedAt] = useState<string | null>(() =>
    typeof window !== "undefined" ? window.localStorage.getItem(LAST_SYNC_KEY) : null,
  );
  const [backupStatus, setBackupStatus] = useState<BackupStatusState>(null);
  const [selectedRestoreFile, setSelectedRestoreFile] = useState<File | null>(null);
  const [restoreModalOpen, setRestoreModalOpen] = useState(false);
  const [backupActionLoading, setBackupActionLoading] = useState<"download" | "restore" | null>(null);
  const [serverReachability, setServerReachability] = useState("Serveur inaccessible");
  const [lastSuccessfulConnection, setLastSuccessfulConnection] = useState<string | null>(null);
  const [systemLogs, setSystemLogs] = useState<LocalSystemLog[]>([]);
  const [desktopContext, setDesktopContext] = useState<DesktopRuntimeContext | null>(null);
  const [clientSyncState, setClientSyncState] = useState<ClientLocalCopyState>("IDLE");
  const [clientSyncStatus, setClientSyncStatus] = useState<ClientSyncStatusPayload | null>(null);
  const [clientSyncExport, setClientSyncExport] = useState<ClientSyncExportPayload | null>(null);
  const [clientSyncCursor, setClientSyncCursor] = useState<number>(() => {
    if (typeof window === "undefined") return 0;
    return Number(window.localStorage.getItem("clinic_client_local_copy_cursor") || 0);
  });
  const [clientLocalCopy, setClientLocalCopy] = useState<ClientLocalCopyInspection | null>(null);
  const [clientSyncImportResult, setClientSyncImportResult] = useState<ClientSyncImportResult | null>(null);
  const [clientSyncPreview, setClientSyncPreview] = useState<ClientSyncPackagePreview | null>(null);
  const [clientSyncHistory, setClientSyncHistory] = useState<ClientSyncHistoryEntry[]>([]);
  const [clientSyncLocalStatus, setClientSyncLocalStatus] = useState<ClientSyncLocalStatus | null>(null);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [detailsOpen, setDetailsOpen] = useState(false);
  const [previewOpen, setPreviewOpen] = useState(false);
  const [clientLocalCopyForm, setClientLocalCopyForm] = useState<ClientLocalCopyForm>({
    host: "127.0.0.1",
    port: "5432",
    databaseName: "medical_folder_local_copy",
    user: "clinic_user",
    password: "",
  });
  const [serverResetConfirmation, setServerResetConfirmation] = useState("");
  const [serverResetBusy, setServerResetBusy] = useState(false);

  const roleNormalized = (user?.role || "").toLowerCase();
  const canUseServerMode = useMemo(
    () => ["super_admin", "admin", "doctor", "super admin"].includes(roleNormalized),
    [roleNormalized],
  );
  const canControlServer = canUseServerMode;
  const canConfigureDatabase = useMemo(
    () => ["super_admin", "admin", "super admin"].includes(roleNormalized),
    [roleNormalized],
  );
  const canCreateServerBackup = useMemo(
    () => ["super_admin", "admin", "super admin"].includes(roleNormalized),
    [roleNormalized],
  );
  const canRestoreServerBackup = useMemo(
    () => ["super_admin", "admin", "super admin"].includes(roleNormalized),
    [roleNormalized],
  );
  const queueEntries = useMemo(() => Object.values(queue ?? {}), [queue]);
  const pendingChanges = useMemo(
    () => queueEntries.reduce((total, entry) => total + getQueueLength(entry), 0),
    [queueEntries],
  );

  const conflictCount = status?.conflict_count ?? conflicts?.length ?? 0;

  const syncStatus: "offline" | "pending" | "synced" | "conflict" | "suspended" = "suspended";

  const backendUrl = selectedServer?.api_base_url || serverUrl;
  const parsedUrl = parseUrlInfo(backendUrl);
  const effectiveMode: ConnectionMode = canUseServerMode ? mode : "client";
  const serverName = missionServer?.server_name || selectedServer?.server_name || "Serveur principal";
  const desktopLocalIp = desktopContext?.localIpAddress || localIpAddress || "-";
  const desktopServerApiUrl =
    desktopContext?.serverApiUrl || `http://${localIpAddress || parsedUrl.host || "127.0.0.1"}:8000`;
  const desktopBackendStatus =
    desktopContext?.backendStatus || (effectiveMode === "server" ? mapConnectionStatus(currentConnectionState) : "Stopped");

  const connectedUsers = useMemo<ConnectedUserRow[]>(
    () =>
      (connectedDevices || []).map((device) => ({
        name: device.username || user?.full_name || "Utilisateur",
        role: normalizeRoleLabel(device.user_role || user?.role || "-"),
        device_name: device.device_name || "-",
        ip_address: device.ip_address || "-",
        last_seen: device.last_seen ? formatDateTime(device.last_seen) : "-",
        status: getUserRowStatus(device.connection_status, device.last_seen),
        connected_since: device.connected_since ? formatDateTime(device.connected_since) : "-",
        app_version: device.app_version || "-",
        operating_system: device.operating_system || "-",
        latency_ms: device.latency_ms ?? null,
        pending_operations_count: device.pending_operations_count ?? 0,
      })),
    [connectedDevices, user?.full_name, user?.role],
  );

  const databaseType = "PostgreSQL";
  const databaseStatusLabel = databaseStatus?.database_status || "Inconnu";

  const appendSystemLog = (messageText: string, tone: LocalSystemLog["tone"]) => {
    setSystemLogs((current) => [
      {
        id: `${Date.now()}-${current.length}`,
        message: messageText,
        timestamp: new Date().toISOString(),
        tone,
      },
      ...current,
    ].slice(0, 12));
  };

  const refreshDesktopContext = async () => {
    if (!syncConnectionApi.getIsTauri()) {
      return null;
    }

    const nextContext = await syncConnectionApi.getDesktopRuntimeContext();
    setDesktopContext(nextContext);
    return nextContext;
  };

  const applyNativeBackupStatus = (nativeStatus: Awaited<ReturnType<typeof syncConnectionApi.getPostgresBackupStatus>>) => {
    if (!nativeStatus) return;
    setBackupStatus({
      enabled: nativeStatus.serverActionsAvailable,
      backup_folder: nativeStatus.backupFolder || "",
      backup_count: nativeStatus.backups.length,
      last_backup_time: nativeStatus.lastBackupTime,
      last_backup_status: nativeStatus.lastBackupStatus,
      server_actions_available: nativeStatus.serverActionsAvailable,
      backup_folder_writable: nativeStatus.backupFolderWritable,
      operation_state: nativeStatus.operationState,
      tools: nativeStatus.tools,
      backups: nativeStatus.backups,
    });
  };

  const loadClientLocalCopy = async () => {
    if (!syncConnectionApi.getIsTauri() || effectiveMode !== "client") {
      return null;
    }

    const inspection = await syncConnectionApi.inspectClientLocalCopy();
    setClientLocalCopy(inspection);
    if (!inspection?.configured) {
      setClientSyncState("LOCAL_DATABASE_REQUIRED");
    }
    return inspection;
  };

  const refreshClientSyncMetadata = async () => {
    if (!syncConnectionApi.getIsTauri() || effectiveMode !== "client") {
      return;
    }
    const [localStatus, history] = await Promise.all([
      syncConnectionApi.getClientSyncLocalStatus(),
      syncConnectionApi.getClientSyncImportHistory(),
    ]);
    setClientSyncLocalStatus(localStatus);
    setClientSyncHistory(history);
    if (typeof localStatus?.lastSyncCursor === "number" && Number.isFinite(localStatus.lastSyncCursor)) {
      setClientSyncCursor(localStatus.lastSyncCursor);
      if (typeof window !== "undefined") {
        window.localStorage.setItem("clinic_client_local_copy_cursor", String(localStatus.lastSyncCursor));
      }
    }
  };

  useEffect(() => {
    const tauriRuntime = detectTauriRuntime();
    setIsTauri(tauriRuntime);
    syncConnectionApi.setIsTauri(tauriRuntime);
    if (typeof window !== "undefined") {
      window.localStorage.setItem(IS_TAURI_KEY, String(tauriRuntime));
    }
  }, []);

  useEffect(() => {
    if (!isTauri) {
      return;
    }

    let cancelled = false;
    void syncConnectionApi
      .applyOperationMode(effectiveMode, serverUrl)
      .then((nextContext) => {
        if (cancelled) return;
        setDesktopContext(nextContext);
      })
      .catch(() => undefined);

    return () => {
      cancelled = true;
    };
  }, [effectiveMode, isTauri]);

  useEffect(() => {
    if (!canUseServerMode && mode !== "client") {
      setMode("client");
    }
  }, [canUseServerMode, mode]);

  useEffect(() => {
    if (typeof window !== "undefined") {
      window.localStorage.setItem(MODE_KEY, effectiveMode);
    }
    syncConnectionApi.setConnectionMode(effectiveMode);
  }, [effectiveMode]);

  useEffect(() => {
    if (typeof window !== "undefined") {
      window.localStorage.setItem(SERVER_URL_KEY, serverUrl);
    }
  }, [serverUrl]);

  const loadBackupStatus = async () => {
    try {
      if (syncConnectionApi.getIsTauri()) {
        const nativeStatus = await syncConnectionApi.getPostgresBackupStatus();
        if (nativeStatus) {
          applyNativeBackupStatus(nativeStatus);
          return;
        }
      }
      const next = await syncConnectionApi.getBackupStatus();
      const operation = await syncConnectionApi.getSystemBackupStatus().catch(() => null);
      setBackupStatus({
        enabled: next?.enabled ?? true,
        backup_folder: next?.backup_folder || syncConnectionApi.getBackupFolder(),
        backup_count: next?.backup_count ?? 0,
        last_backup_time: next?.last_backup_time ?? null,
        last_backup_status: next?.last_backup_status ?? "Inconnu",
        server_actions_available: effectiveMode === "server",
        backup_folder_writable: Boolean(next?.backup_folder),
        operation_state: operation?.state || "IDLE",
        operation_started_at: operation?.started_at || null,
        operation_last_error: operation?.last_error || null,
        pg_dump_available: operation?.pg_dump_available,
        pg_restore_available: operation?.pg_restore_available,
        tools: null,
        backups: [],
      });
    } catch {
      setBackupStatus((current) =>
        current || {
          enabled: true,
          backup_folder: syncConnectionApi.getBackupFolder(),
          backup_count: 0,
          last_backup_time: databaseStatus?.last_backup_time ?? null,
          last_backup_status: "Indisponible",
          server_actions_available: effectiveMode === "server",
          backup_folder_writable: false,
          operation_state: "FAILED",
          operation_started_at: null,
          operation_last_error: null,
          tools: null,
          backups: [],
        },
      );
    }
  };

  useEffect(() => {
    void loadBackupStatus();
  }, [databaseStatus?.last_backup_time, effectiveMode]);

  useEffect(() => {
    const normalized = syncConnectionApi.setLastServerUrl(serverUrl);
    if (normalized !== serverUrl) {
      setServerUrl(normalized);
    }
  }, []);

  useEffect(() => {
    void refreshDesktopContext().catch(() => undefined);
  }, [isTauri]);

  useEffect(() => {
    void loadClientLocalCopy().catch(() => {
      setClientLocalCopy(null);
    });
  }, [effectiveMode, isTauri]);

  useEffect(() => {
    void refreshClientSyncMetadata().catch(() => undefined);
  }, [effectiveMode, isTauri]);

  const validateServerUrl = async (rawUrl: string) => {
    const trimmed = rawUrl.trim();
    if (!trimmed) {
      throw new Error("URL API du serveur requise.");
    }
    validateFastApiRootUrl(trimmed);

    const health = await syncConnectionApi.testServer(trimmed);
    if (health?.status !== "ok") {
      throw new Error(
        health?.incompatible
          ? "Serveur incompatible. Vérifiez que l'URL pointe vers le serveur FastAPI Ibn Sina."
          : "Serveur inaccessible",
      );
    }
    const normalized = syncConnectionApi.setLastServerUrl(trimmed);
    return normalized;
  };

  const formatFileSize = (value: number) => {
    if (value < 1024) return `${value} o`;
    if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} Ko`;
    return `${(value / (1024 * 1024)).toFixed(1)} Mo`;
  };

  const restoreFileError = (() => {
    if (!selectedRestoreFile) return null;
    const filename = selectedRestoreFile.name.toLowerCase();
    if (!filename.endsWith(".backup") && !filename.endsWith(".dump")) {
      return "Le fichier selectionne doit etre au format .backup ou .dump.";
    }
    return null;
  })();

  const handleStartServer = async () => {
    setError(null);
    setMessage(null);
    try {
      await syncConnectionApi.startLocalServer();
      await refreshDesktopContext().catch(() => undefined);
      setMessage("Serveur démarré.");
      setServerReachability("Connexion réussie");
      setLastSuccessfulConnection(new Date().toISOString());
      appendSystemLog("Serveur démarré", "active");
      await refreshStatus();
    } catch {
      setError("Impossible de démarrer le serveur local.");
      setServerReachability("Serveur inaccessible");
      appendSystemLog("Echec du démarrage du serveur", "failed");
    }
  };

  const handleStopServer = async () => {
    setError(null);
    setMessage(null);
    try {
      await syncConnectionApi.stopLocalServer();
      await refreshDesktopContext().catch(() => undefined);
      setMessage("Serveur arrêté.");
      appendSystemLog("Serveur arrêté", "pending");
      await refreshStatus();
    } catch {
      setError("Impossible d'arrêter le serveur local.");
      appendSystemLog("Echec de l'arrêt du serveur", "failed");
    }
  };

  const handleTestServer = async (urlOverride?: string) => {
    setError(null);
    setMessage(null);
    try {
      const normalized = await validateServerUrl(urlOverride || serverUrl);
      setServerUrl(normalized);
      setServerReachability("Connexion réussie");
      setLastSuccessfulConnection(new Date().toISOString());
      setMessage("Connexion réussie.");
      appendSystemLog("Connexion réussie", "active");
    } catch (validationError) {
      const nextError =
        validationError instanceof Error ? validationError.message : "Serveur inaccessible";
      setServerReachability(nextError === "Serveur inaccessible" ? "Serveur inaccessible" : "Erreur");
      setError(nextError);
      appendSystemLog("Connexion échouée", "failed");
    }
  };

  const handleCheckClientSyncUpdates = async () => {
    setClientSyncState("CHECKING");
    setError(null);
    try {
      if (!clientLocalCopy?.configured) {
        setClientSyncState("LOCAL_DATABASE_REQUIRED");
        setError("Configurez d'abord la copie PostgreSQL locale.");
        return;
      }
      const nextStatus = await syncConnectionApi.getClientSyncStatus(clientSyncCursor);
      setClientSyncStatus(nextStatus);
      setClientSyncState(nextStatus.available_update_count > 0 ? "UPDATE_AVAILABLE" : "NO_UPDATE");
      appendSystemLog("Verification de la copie locale terminee", "active");
    } catch {
      setClientSyncState("FAILED");
      setError("Impossible de verifier les mises a jour pour la copie locale.");
      appendSystemLog("Verification de la copie locale echouee", "failed");
    }
  };

  const clearDeploymentSetupStorageAfterReset = () => {
    if (typeof window === "undefined") return;
    window.localStorage.removeItem(MODE_KEY);
    window.localStorage.removeItem(SERVER_URL_KEY);
    window.localStorage.setItem(SETUP_COMPLETED_KEY, "false");
  };

  const handleResetServerConfiguration = async () => {
    setError(null);
    setMessage(null);
    if (serverResetConfirmation.trim() !== SERVER_RESET_CONFIRMATION) {
      setError(`Tapez exactement "${SERVER_RESET_CONFIRMATION}" pour confirmer.`);
      return;
    }

    setServerResetBusy(true);
    try {
      const result = await syncConnectionApi.resetServerConfiguration(serverResetConfirmation);
      if (!result?.success) {
        throw new Error(result?.message || "Reinitialisation serveur refusee.");
      }

      clearDeploymentSetupStorageAfterReset();
      setMode("client");
      setServerUrl("");
      setDesktopContext(null);
      setServerResetConfirmation("");
      setMessage(
        "Configuration serveur reinitialisee. La base PostgreSQL et les sauvegardes sont conservees. Redemarrez l'application ou choisissez un mode au prochain lancement.",
      );
      appendSystemLog("Configuration serveur reinitialisee", "pending");
      await refreshDesktopContext().catch(() => undefined);
    } catch (resetError) {
      setError(
        resetError instanceof Error
          ? resetError.message
          : "Impossible de reinitialiser la configuration serveur.",
      );
      appendSystemLog("Echec de reinitialisation serveur", "failed");
    } finally {
      setServerResetBusy(false);
    }
  };

  const handleConfigureClientLocalCopy = async () => {
    setClientSyncState("INITIALIZING_SCHEMA");
    setError(null);
    setMessage(null);
    try {
      const port = Number(clientLocalCopyForm.port);
      if (!Number.isInteger(port) || port <= 0 || port > 65535) {
        throw new Error("Port PostgreSQL local invalide.");
      }
      if (!clientLocalCopyForm.password.trim()) {
        throw new Error("Mot de passe PostgreSQL local requis.");
      }
      const inspection = await syncConnectionApi.configureClientLocalCopy({
        host: clientLocalCopyForm.host.trim(),
        port,
        databaseName: clientLocalCopyForm.databaseName.trim(),
        user: clientLocalCopyForm.user.trim(),
        password: clientLocalCopyForm.password,
      });
      setClientLocalCopy(inspection);
      setClientLocalCopyForm((current) => ({ ...current, password: "" }));
      setClientSyncState(inspection?.configured ? "IDLE" : "LOCAL_DATABASE_REQUIRED");
      setMessage("Copie PostgreSQL locale configuree.");
      appendSystemLog("Copie PostgreSQL locale configuree", "active");
      await refreshClientSyncMetadata().catch(() => undefined);
    } catch (configurationError) {
      setClientLocalCopyForm((current) => ({ ...current, password: "" }));
      setClientSyncState("FAILED");
      setError(
        configurationError instanceof Error
          ? configurationError.message
          : "Impossible de configurer la copie PostgreSQL locale.",
      );
      appendSystemLog("Configuration de la copie locale echouee", "failed");
    }
  };

  const handlePrepareClientSyncExport = async () => {
    setClientSyncState("PREPARING");
    setError(null);
    try {
      if (!isTauri) {
        throw new Error("L'import PostgreSQL local est disponible uniquement dans l'application Tauri.");
      }
      if (!clientLocalCopy?.configured) {
        setClientSyncState("LOCAL_DATABASE_REQUIRED");
        throw new Error("Configurez d'abord la copie PostgreSQL locale.");
      }
      setClientSyncState("DOWNLOADING");
      const exported = await syncConnectionApi.exportClientSyncPackage(clientSyncCursor);
      setClientSyncExport(exported);
      setClientSyncState("VERIFYING");
      setClientSyncState("IMPORTING");
      const importResult = await syncConnectionApi.importClientSyncPackage(exported, clientSyncStatus?.server_id || exported.server_id);
      if (!importResult?.success) {
        throw new Error(importResult?.message || "Import PostgreSQL local refuse.");
      }
      setClientSyncImportResult(importResult);
      const committedCursor = importResult.toCursor ?? exported.to_cursor;
      setClientSyncCursor(committedCursor);
      if (typeof window !== "undefined") {
        window.localStorage.setItem("clinic_client_local_copy_cursor", String(committedCursor));
      }
      setClientSyncState("COMPLETED");
      appendSystemLog("Copie locale importee dans PostgreSQL", "active");
      await refreshClientSyncMetadata().catch(() => undefined);
    } catch (syncError) {
      setClientSyncState("FAILED");
      setError(syncError instanceof Error ? syncError.message : "Impossible d'importer la copie locale.");
      appendSystemLog("Preparation de la copie locale echouee", "failed");
    }
  };

  const handleImportClientSyncPackageFile = async () => {
    setClientSyncState("VALIDATION");
    setError(null);
    setMessage(null);
    try {
      if (!isTauri) {
        throw new Error("L'import de package est disponible uniquement dans l'application Tauri.");
      }
      if (!clientLocalCopy?.configured) {
        setClientSyncState("LOCAL_DATABASE_REQUIRED");
        throw new Error("Configurez d'abord la copie PostgreSQL locale.");
      }
      const preview = await syncConnectionApi.previewClientSyncPackageFile(
        clientSyncStatus?.server_id || clientSyncImportResult?.serverId || null,
      );
      if (!preview?.valid) {
        throw new Error("SYNC_PACKAGE_INVALID");
      }
      if (preview.duplicate) {
        throw new Error("SYNC_ALREADY_IMPORTED");
      }
      setClientSyncPreview(preview);
      setPreviewOpen(true);
      setClientSyncState("IDLE");
    } catch (syncError) {
      const nextMessage = syncError instanceof Error ? syncError.message : "Impossible d'importer le package.";
      if (nextMessage.includes("SYNC_PACKAGE_SELECTION_CANCELLED")) {
        setClientSyncState(clientLocalCopy?.configured ? "IDLE" : "LOCAL_DATABASE_REQUIRED");
        return;
      }
      setClientSyncState("FAILED");
      setError(nextMessage.includes("SYNC_ALREADY_IMPORTED") ? "Ce package a deja ete importe." : nextMessage);
      appendSystemLog("Import du package de synchronisation echoue", "failed");
    }
  };

  const handleConfirmClientSyncImport = async () => {
    if (!clientSyncPreview?.selectedPath) return;
    setClientSyncState("IMPORTING");
    setError(null);
    setMessage(null);
    try {
      const importResult = await syncConnectionApi.importClientSyncPackagePath(
        clientSyncPreview.selectedPath,
        clientSyncStatus?.server_id || clientSyncImportResult?.serverId || clientSyncPreview.serverId || null,
      );
      if (!importResult?.success) {
        throw new Error(importResult?.message || "Import du package de synchronisation refuse.");
      }
      setClientSyncImportResult(importResult);
      if (importResult.toCursor !== null && importResult.toCursor !== undefined) {
        setClientSyncCursor(importResult.toCursor);
        if (typeof window !== "undefined") {
          window.localStorage.setItem("clinic_client_local_copy_cursor", String(importResult.toCursor));
        }
      }
      setPreviewOpen(false);
      setClientSyncPreview(null);
      setClientSyncState("COMPLETED");
      setMessage(importResult.message || "Package de synchronisation importe.");
      appendSystemLog("Package de synchronisation importe", "active");
      await refreshClientSyncMetadata().catch(() => undefined);
    } catch (syncError) {
      setClientSyncState("FAILED");
      setError(syncError instanceof Error ? syncError.message : "Impossible d'importer le package.");
      appendSystemLog("Import du package de synchronisation echoue", "failed");
    }
  };

  const handleConnect = async () => {
    setError(null);
    setMessage(null);
    try {
      const normalized = await validateServerUrl(serverUrl);
      await syncConnectionApi.connectClient(normalized, user?.full_name || "Poste");
      await refreshDesktopContext().catch(() => undefined);
      setServerUrl(normalized);
      setServerReachability("Connexion réussie");
      setLastSuccessfulConnection(new Date().toISOString());
      setMessage("Connexion réussie.");
      appendSystemLog("Connexion réussie", "active");
      await refreshStatus();
    } catch (connectError) {
      const nextError =
        connectError instanceof Error ? connectError.message : "Serveur inaccessible";
      setServerReachability(nextError === "Serveur inaccessible" ? "Serveur inaccessible" : "Erreur");
      setError(nextError);
      appendSystemLog("Connexion échouée", "failed");
    }
  };

  const handleDisconnect = async () => {
    setError(null);
    setMessage(null);
    try {
      await syncConnectionApi.disconnectClient(user?.full_name || "Poste");
      await refreshDesktopContext().catch(() => undefined);
      setServerReachability("Déconnecté");
      setMessage("Poste déconnecté.");
      appendSystemLog("Déconnexion effectuée", "pending");
      await refreshStatus();
    } catch {
      setError("Impossible de déconnecter ce poste.");
      appendSystemLog("Echec de la déconnexion", "failed");
    }
  };

  const handleBackupFolderLegacy = async () => {
    setError(null);
    setMessage(null);
    try {
      const next = window.prompt("Choisir le dossier des sauvegardes", syncConnectionApi.getBackupFolder());
      if (!next) return;
      syncConnectionApi.setBackupFolder(next);
      setBackupStatus((current) =>
        current
          ? { ...current, backup_folder: next }
          : {
              enabled: true,
              backup_folder: next,
              backup_count: 0,
              last_backup_time: null,
              last_backup_status: "Dossier mis à jour",
            },
      );
      setMessage("Dossier de sauvegarde enregistré.");
      appendSystemLog("Dossier de sauvegarde mis à jour", "pending");
    } catch {
      setError("Impossible d'enregistrer le dossier de sauvegarde.");
      appendSystemLog("Echec de mise à jour du dossier de sauvegarde", "failed");
    }
  };

  const handleCreateBackupLegacy = async () => {
    setError(null);
    setMessage(null);
    try {
      await syncConnectionApi.createBackup();
      setMessage("Sauvegarde créée.");
      appendSystemLog("Sauvegarde créée", "active");
      await loadBackupStatus();
    } catch {
      setError("Impossible de créer la sauvegarde.");
      appendSystemLog("Echec de la sauvegarde", "failed");
    }
  };

  const handleRestoreBackupLegacy = async () => {
    setError(null);
    setMessage(null);
    try {
      const backupPath = window.prompt("Indiquez le chemin complet de la sauvegarde à restaurer");
      if (!backupPath) return;
      await syncConnectionApi.restoreBackup(backupPath);
      setMessage("Restauration lancée.");
      appendSystemLog("Restauration lancée", "pending");
      await loadBackupStatus();
    } catch {
      setError("Impossible de restaurer la sauvegarde.");
      appendSystemLog("Echec de la restauration", "failed");
    }
  };

  const handleExportBackupLegacy = async () => {
    setError(null);
    setMessage(null);
    try {
      await syncConnectionApi.exportBackup();
      setMessage("Sauvegarde exportée vers USB.");
      appendSystemLog("Sauvegarde créée", "active");
      await loadBackupStatus();
    } catch {
      setError("Impossible d'exporter la sauvegarde vers USB.");
      appendSystemLog("Echec de l'export USB", "failed");
    }
  };

  void handleBackupFolderLegacy;
  void handleCreateBackupLegacy;
  void handleRestoreBackupLegacy;
  void handleExportBackupLegacy;

  const handleBackupFolder = async () => {
    setError(null);
    setMessage(null);
    try {
      if (effectiveMode !== "server") {
        throw new Error("Les sauvegardes PostgreSQL du serveur sont disponibles uniquement sur le poste configure comme serveur.");
      }
      if (syncConnectionApi.getIsTauri()) {
        applyNativeBackupStatus(await syncConnectionApi.chooseBackupDirectory());
      } else {
        await handleBackupFolderLegacy();
        return;
      }
      setMessage("Dossier de sauvegarde enregistre.");
      appendSystemLog("Dossier de sauvegarde mis a jour", "pending");
    } catch (backupError) {
      setError(
        backupError instanceof Error
          ? backupError.message
          : "Impossible d'enregistrer le dossier de sauvegarde.",
      );
      appendSystemLog("Echec de mise a jour du dossier de sauvegarde", "failed");
    }
  };

  const handleOpenBackupFolder = async () => {
    setError(null);
    try {
      await syncConnectionApi.openBackupDirectory();
    } catch {
      setError("Impossible d'ouvrir le dossier de sauvegarde.");
    }
  };

  const handleCreateBackup = async () => {
    setError(null);
    setMessage(null);
    try {
      if (!canCreateServerBackup) {
        throw new Error("Permission refusee pour creer une sauvegarde.");
      }
      setBackupActionLoading("download");
      const { blob, filename } = await syncConnectionApi.downloadSystemBackup();
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
      setMessage("La sauvegarde complete a ete creee et telechargee avec succes.");
      appendSystemLog("Sauvegarde complete telechargee", "active");
      await loadBackupStatus();
    } catch (backupError) {
      setError(await extractBlobError(backupError));
      console.error("system backup download failed", backupError);
      appendSystemLog("Echec de la sauvegarde", "failed");
    } finally {
      setBackupActionLoading(null);
    }
  };

  const handleRestoreBackup = async () => {
    setError(null);
    setMessage(null);
    try {
      if (!canRestoreServerBackup) {
        throw new Error("La restauration est reservee aux administrateurs.");
      }
      if (!selectedRestoreFile) {
        throw new Error("Selectionnez un fichier de sauvegarde avant de restaurer.");
      }
      if (restoreFileError) {
        throw new Error(restoreFileError);
      }
      setBackupActionLoading("restore");
      const result = await syncConnectionApi.restoreSystemBackup(selectedRestoreFile);
      setMessage(result.message);
      setSelectedRestoreFile(null);
      setRestoreModalOpen(false);
      appendSystemLog("Sauvegarde restauree avec succes", "active");
      await loadBackupStatus();
    } catch (backupError) {
      setError(await extractBlobError(backupError));
      console.error("system backup restore failed", backupError);
      appendSystemLog("Echec de la restauration", "failed");
    } finally {
      setBackupActionLoading(null);
    }
  };

  const handleExportBackup = async () => {
    setError(null);
    setMessage(null);
    try {
      throw new Error("L'export USB n'est pas disponible dans ce nouveau flux de restauration.");
    } catch (backupError) {
      setError(
        backupError instanceof Error
          ? backupError.message
          : "Impossible d'exporter la sauvegarde vers USB.",
      );
      appendSystemLog("Echec de l'export USB", "failed");
    }
  };

  const handleSyncNow = async () => {
    if (!online) {
      setError("La connexion réseau n'est pas disponible pour lancer la synchronisation.");
      return;
    }

    setError(null);
    setMessage(null);
    try {
      await syncNow();
      const now = new Date().toISOString();
      setLastSyncedAt(now);
      if (typeof window !== "undefined") {
        window.localStorage.setItem(LAST_SYNC_KEY, now);
      }
      setMessage("Synchronisation réussie.");
      appendSystemLog("Synchronisation réussie", "active");
      await refreshStatus();
    } catch {
      setError("Impossible d'exécuter la synchronisation maintenant.");
      appendSystemLog("Echec de la synchronisation", "failed");
    }
  };

  return (
    <div className="space-y-6 pb-10">
      <SectionHeader
        eyebrow="Infrastructure réseau"
        title="Centre de contrôle réseau"
        description="Pilotez le serveur principal, les postes clients, la synchronisation, PostgreSQL et les sauvegardes depuis une interface unifiée."
        actionLabel={syncing ? "Synchronisation..." : "Synchroniser maintenant"}
        actionIcon={RefreshCw}
        onAction={() => void handleSyncNow()}
      />

      {(message || error) && (
        <div
          className={[
            "flex items-start gap-3 rounded-2xl border px-4 py-4 shadow-sm",
            error
              ? "border-rose-200 bg-rose-50 text-rose-800"
              : "border-emerald-200 bg-emerald-50 text-emerald-800",
          ].join(" ")}
        >
          {error ? (
            <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0" />
          ) : (
            <ShieldCheck className="mt-0.5 h-5 w-5 shrink-0" />
          )}
          <div>
            <p className="text-sm font-black">{error ? "Une erreur est survenue" : "Opération réussie"}</p>
            <p className="mt-1 text-sm font-medium">{error || message}</p>
          </div>
        </div>
      )}

      <DeviceRuntimePanel
        user={user}
        serverUrl={serverUrl}
        onServerUrlChange={setServerUrl}
        onModeHintChange={setMode}
      />

      <section className="overflow-hidden rounded-[2rem] border border-slate-200 bg-slate-950 shadow-xl shadow-slate-950/10">
        <div className="relative px-5 py-7 sm:px-7 lg:px-8">
          <div className="absolute inset-0 bg-[radial-gradient(circle_at_top_right,rgba(14,165,233,0.24),transparent_34%),radial-gradient(circle_at_bottom_left,rgba(16,185,129,0.16),transparent_30%)]" />

          <div className="relative flex flex-col gap-7 xl:flex-row xl:items-center xl:justify-between">
            <div className="max-w-3xl">
              <div className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-3 py-1.5 text-xs font-bold uppercase tracking-[0.16em] text-sky-200">
                <MonitorSmartphone className="h-4 w-4" />
                Console d’infrastructure
              </div>

              <h2 className="mt-4 text-2xl font-black tracking-tight text-white sm:text-3xl">
                {effectiveMode === "server"
                  ? "Ce poste opère comme serveur principal"
                  : "Ce poste opère comme client réseau"}
              </h2>

              <p className="mt-3 max-w-2xl text-sm leading-6 text-slate-300">
                Architecture centralisée avec une API FastAPI, une base PostgreSQL sur le serveur
                principal et des postes clients connectés au réseau local de la clinique.
              </p>

              <div className="mt-5 flex flex-wrap gap-2">
                <Badge tone="reviewed">{isTauri ? "Tauri Desktop" : "Web / Développement"}</Badge>
                <Badge tone={online ? "active" : "inactive"}>
                  {online ? "Internet disponible" : "Mode hors ligne"}
                </Badge>
                <Badge tone={wsConnected ? "active" : "pending"}>
                  WebSocket {wsConnected ? "connecté" : "déconnecté"}
                </Badge>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 xl:min-w-[520px]">
              {[
                {
                  label: "Mode actif",
                  value: effectiveMode === "server" ? "Serveur" : "Client",
                  icon: Server,
                },
                {
                  label: "Connexion",
                  value:
                    effectiveMode === "server"
                      ? desktopBackendStatus
                      : mapConnectionStatus(currentConnectionState),
                  icon: Activity,
                },
                {
                  label: "Postes",
                  value: String(connectedUsers.length),
                  icon: Network,
                },
                {
                  label: "Synchronisation",
                  value: "Suspendue pour protection",
                  icon: RefreshCw,
                },
              ].map((item) => {
                const Icon = item.icon;

                return (
                  <div
                    key={item.label}
                    className="rounded-2xl border border-white/10 bg-white/[0.06] p-4 backdrop-blur"
                  >
                    <Icon className="h-4 w-4 text-sky-300" />
                    <p className="mt-3 text-[10px] font-black uppercase tracking-[0.14em] text-slate-400">
                      {item.label}
                    </p>
                    <p className="mt-1 truncate text-sm font-bold text-white">{item.value}</p>
                  </div>
                );
              })}
            </div>
          </div>
        </div>

        <div className="relative border-t border-white/10 bg-white/[0.04] px-5 py-4 sm:px-7 lg:px-8">
          <div className="flex flex-col gap-3 sm:flex-row">
            {canUseServerMode ? (
              <>
                <Button
                  variant={effectiveMode === "server" ? "primary" : "secondary"}
                  className="sm:flex-1"
                  onClick={() => setMode("server")}
                >
                  Utiliser ce PC comme serveur
                </Button>
                <Button
                  variant={effectiveMode === "client" ? "primary" : "secondary"}
                  className="sm:flex-1"
                  onClick={() => setMode("client")}
                >
                  Utiliser ce PC comme client
                </Button>
              </>
            ) : (
              <div className="rounded-xl border border-white/10 bg-white/5 px-4 py-3 text-sm font-medium text-slate-300">
                Votre rôle utilise exclusivement le mode client.
              </div>
            )}
          </div>
        </div>
      </section>

      <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {[
          {
            label: "État réseau",
            value: online ? "Disponible" : "Indisponible",
            detail: wifiConnectionStatus || "État inconnu",
            icon: Globe,
            iconClassName: online
              ? "border-emerald-200 bg-emerald-50 text-emerald-700"
              : "border-rose-200 bg-rose-50 text-rose-700",
          },
          {
            label: "File d’attente",
            value: String(pendingChanges),
            detail: `${conflictCount} conflit(s)`,
            icon: RefreshCw,
            iconClassName: "border-sky-200 bg-sky-50 text-sky-700",
          },
          {
            label: "Base de données",
            value: databaseType,
            detail: databaseStatusLabel,
            icon: Database,
            iconClassName: "border-violet-200 bg-violet-50 text-violet-700",
          },
          {
            label: "Sauvegardes",
            value: String(backupStatus?.backup_count ?? 0),
            detail: backupStatus?.last_backup_status || "Aucun statut",
            icon: HardDrive,
            iconClassName: "border-amber-200 bg-amber-50 text-amber-700",
          },
        ].map((item) => {
          const Icon = item.icon;

          return (
            <Card
              key={item.label}
              className="group rounded-2xl border-slate-200 bg-white p-5 transition duration-200 hover:-translate-y-0.5 hover:shadow-lg"
            >
              <div className="flex items-start justify-between gap-4">
                <div className="min-w-0">
                  <p className="text-xs font-black uppercase tracking-[0.14em] text-slate-500">
                    {item.label}
                  </p>
                  <p className="mt-3 truncate text-2xl font-black tracking-tight text-slate-950">
                    {item.value}
                  </p>
                  <p className="mt-1 truncate text-sm text-slate-500">{item.detail}</p>
                </div>

                <div className={`rounded-2xl border p-3 ${item.iconClassName}`}>
                  <Icon className="h-5 w-5" />
                </div>
              </div>
            </Card>
          );
        })}
      </section>

      {/* Row 1 — Server / Client + Connection Health */}
      <section className="grid gap-6 2xl:grid-cols-[minmax(0,1.65fr)_minmax(360px,0.85fr)]">
        <div className="min-w-0">
          {effectiveMode === "server" && canUseServerMode ? (
            <div className="space-y-4">
              <ServerModePanel
                serverName={serverName}
                localIp={desktopLocalIp}
                backendUrl={desktopServerApiUrl}
                port="8000"
                serverStatus={desktopBackendStatus}
                currentMode="Serveur"
                userRole={normalizeRoleLabel(user?.role)}
                postgresqlStatus={databaseStatusLabel}
                showControls={canControlServer}
                onStart={handleStartServer}
                onStop={handleStopServer}
                onTest={() => handleTestServer(desktopServerApiUrl)}
              />

              {desktopBackendStatus === "Running" && (
                <div className="flex items-start gap-3 rounded-2xl border border-sky-200 bg-sky-50 px-4 py-4 text-sm text-sky-900">
                  <Info className="mt-0.5 h-5 w-5 shrink-0" />
                  <div>
                    <p className="font-black">Serveur disponible sur le réseau local</p>
                    <p className="mt-1 font-medium">
                      Les autres postes peuvent se connecter avec {desktopServerApiUrl}.
                    </p>
                  </div>
                </div>
              )}
            </div>
          ) : (
            <ClientModePanel
              serverUrl={serverUrl}
              connectionStatus={mapConnectionStatus(currentConnectionState)}
              serverReachability={serverReachability}
              warningMessage="Utilisez l’URL API du serveur, par exemple http://192.168.0.136:8000."
              onServerUrlChange={setServerUrl}
              onConnect={handleConnect}
              onDisconnect={handleDisconnect}
              onTest={() => handleTestServer(serverUrl)}
            />
          )}
        </div>

        <Card className="h-full rounded-[1.75rem] border-slate-200 bg-white p-6">
          <div className="flex items-start justify-between gap-4">
            <div>
              <p className="text-xs font-black uppercase tracking-[0.16em] text-sky-600">
                État en temps réel
              </p>
              <h3 className="mt-2 text-xl font-black text-slate-950">
                Santé de la connexion
              </h3>
              <p className="mt-1 text-sm leading-6 text-slate-500">
                Vue synthétique du réseau local, du WebSocket et de l’API serveur.
              </p>
            </div>

            <div className="rounded-2xl bg-sky-50 p-3 text-sky-700">
              <Activity className="h-5 w-5" />
            </div>
          </div>

          <div className="mt-6 space-y-3">
            {[
              {
                label: "Connexion principale",
                value:
                  effectiveMode === "server"
                    ? desktopBackendStatus
                    : mapConnectionStatus(currentConnectionState),
              },
              { label: "Réseau local", value: wifiConnectionStatus || "Inconnu" },
              { label: "Canal WebSocket", value: wsConnected ? "Connecté" : "Déconnecté" },
              { label: "Dernier test API", value: serverReachability },
              {
                label: "Dernière connexion réussie",
                value: formatDateTime(lastSuccessfulConnection),
              },
            ].map((item) => (
              <div
                key={item.label}
                className="flex items-center justify-between gap-4 rounded-2xl border border-slate-200 bg-slate-50/70 px-4 py-3.5"
              >
                <span className="text-sm font-medium text-slate-600">{item.label}</span>
                <span className="text-right text-sm font-bold text-slate-950">
                  {item.value}
                </span>
              </div>
            ))}
          </div>
        </Card>
      </section>

      {effectiveMode === "server" && canUseServerMode && isTauri ? (
        <Card className="rounded-[1.75rem] border-rose-200 bg-white p-6 shadow-sm">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
            <div className="max-w-3xl">
              <p className="text-xs font-black uppercase tracking-[0.16em] text-rose-600">
                Options avancees
              </p>
              <h3 className="mt-2 text-xl font-black text-slate-950">
                Reinitialiser la configuration serveur
              </h3>
              <div className="mt-3 rounded-2xl border border-rose-200 bg-rose-50 px-4 py-4 text-sm leading-6 text-rose-950">
                <p className="font-black">Attention: operation de recuperation locale</p>
                <p className="mt-2">
                  Cette operation reinitialise uniquement la configuration locale du poste serveur.
                </p>
                <p>La base PostgreSQL medical_folder et ses donnees seront conservees.</p>
                <p>
                  Vous devrez reconfigurer ce poste comme Serveur ou Client au prochain demarrage.
                </p>
              </div>
              <p className="mt-3 text-xs font-semibold text-slate-500">
                Limitation de recuperation: si FastAPI est indisponible, cette action repose sur l'acces physique au
                poste et la confirmation explicite. Elle ne supprime jamais les donnees PostgreSQL.
              </p>
            </div>

            <div className="w-full rounded-2xl border border-slate-200 bg-slate-50/80 p-4 lg:max-w-md">
              <label className="text-xs font-black uppercase tracking-[0.14em] text-slate-500">
                Phrase de confirmation
              </label>
              <input
                className="mt-3 w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm font-semibold text-slate-900 outline-none transition focus:border-rose-400"
                value={serverResetConfirmation}
                onChange={(event) => setServerResetConfirmation(event.target.value)}
                placeholder={SERVER_RESET_CONFIRMATION}
              />
              <Button
                className="mt-4 w-full"
                variant="danger"
                icon={Trash2}
                loading={serverResetBusy}
                disabled={serverResetConfirmation.trim() !== SERVER_RESET_CONFIRMATION}
                onClick={() => void handleResetServerConfiguration()}
              >
                Confirmer la reinitialisation
              </Button>
            </div>
          </div>
        </Card>
      ) : null}

      {effectiveMode === "client" ? (
        <Card className="rounded-[1.75rem] border-slate-200 bg-white p-6">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
            <div>
              <p className="text-xs font-black uppercase tracking-[0.16em] text-emerald-600">
                Synchronisation
              </p>
              <h3 className="mt-2 text-xl font-black text-slate-950">
                Panneau de copie PostgreSQL locale
              </h3>
              <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-500">
                La base du serveur reste la source principale. Cette operation telecharge une copie locale et
                n'envoie aucune modification vers le serveur. La base PostgreSQL locale est traitee comme
                LOCAL_SYNCHRONIZED_COPY.
              </p>
            </div>
            <Badge tone={clientSyncState === "FAILED" ? "failed" : clientSyncState === "COMPLETED" ? "active" : "pending"}>
              {clientSyncStageLabels[clientSyncState]}
            </Badge>
          </div>

          <div className="mt-6 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <div className="rounded-2xl border border-slate-200 bg-slate-50/70 px-4 py-4">
              <p className="text-xs font-black uppercase tracking-[0.14em] text-slate-500">Serveur source</p>
              <p className="mt-2 truncate text-sm font-bold text-slate-950">{serverUrl || backendUrl || "-"}</p>
            </div>
            <div className="rounded-2xl border border-slate-200 bg-slate-50/70 px-4 py-4">
              <p className="text-xs font-black uppercase tracking-[0.14em] text-slate-500">Derniere synchronisation</p>
              <p className="mt-2 text-sm font-bold text-slate-950">
                {formatDateTime(clientSyncLocalStatus?.lastImportedAt || clientSyncLocalStatus?.lastSyncAt || null)}
              </p>
            </div>
            <div className="rounded-2xl border border-slate-200 bg-slate-50/70 px-4 py-4">
              <p className="text-xs font-black uppercase tracking-[0.14em] text-slate-500">Lignes importees</p>
              <p className="mt-2 text-sm font-bold text-slate-950">
                {clientSyncLocalStatus?.importedRowsTotal ?? clientSyncStatus?.available_update_count ?? "-"}
              </p>
            </div>
            <div className="rounded-2xl border border-slate-200 bg-slate-50/70 px-4 py-4">
              <p className="text-xs font-black uppercase tracking-[0.14em] text-slate-500">Modifications en attente</p>
              <p className="mt-2 truncate text-sm font-bold text-slate-950">
                {pendingChanges}
              </p>
            </div>
          </div>

          <div className="mt-4 rounded-2xl border border-slate-200 bg-slate-50/80 px-4 py-4">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <p className="text-xs font-black uppercase tracking-[0.14em] text-slate-500">Progression</p>
                <p className="mt-1 text-sm font-semibold text-slate-900">
                  {clientSyncStageLabels[clientSyncState]}
                </p>
              </div>
              {["VALIDATION", "PREPARING", "DOWNLOADING", "VERIFYING", "IMPORTING", "INITIALIZING_SCHEMA", "CHECKING"].includes(clientSyncState) ? (
                <div className="flex items-center gap-2 text-sm font-semibold text-slate-600">
                  <RefreshCw className="h-4 w-4 animate-spin" />
                  Traitement en cours
                </div>
              ) : null}
            </div>
          </div>

          <div className="mt-5 rounded-2xl border border-emerald-200 bg-emerald-50 px-4 py-4 text-sm text-emerald-950">
            La base du serveur reste la source principale. Cette synchronisation copie les donnees vers PostgreSQL
            local et n'envoie aucune modification vers le serveur. Les ecrans normaux continuent d'utiliser le serveur
            FastAPI distant.
          </div>

          <div className="mt-5 rounded-3xl border border-slate-200 bg-white p-4 shadow-sm">
            <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
              <div>
                <p className="text-xs font-black uppercase tracking-[0.14em] text-slate-500">
                  Synchronisation - Copie locale des donnees
                </p>
                <p className="mt-1 text-sm text-slate-600">
                  Configurez une base locale destinee uniquement a recevoir une copie des donnees du serveur.
                </p>
              </div>
              <Badge tone={clientLocalCopy?.configured ? "active" : "pending"}>
                {clientLocalCopy?.configured ? "Base locale configuree" : "Configuration requise"}
              </Badge>
            </div>

            <div className="mt-4 grid gap-3 md:grid-cols-5">
              <input
                className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm font-semibold text-slate-900 outline-none transition focus:border-emerald-400 focus:bg-white"
                placeholder="Hote PostgreSQL local"
                value={clientLocalCopyForm.host}
                onChange={(event) => setClientLocalCopyForm((current) => ({ ...current, host: event.target.value }))}
              />
              <input
                className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm font-semibold text-slate-900 outline-none transition focus:border-emerald-400 focus:bg-white"
                placeholder="Port"
                value={clientLocalCopyForm.port}
                onChange={(event) => setClientLocalCopyForm((current) => ({ ...current, port: event.target.value }))}
              />
              <input
                className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm font-semibold text-slate-900 outline-none transition focus:border-emerald-400 focus:bg-white"
                placeholder="Nom de la base"
                value={clientLocalCopyForm.databaseName}
                onChange={(event) =>
                  setClientLocalCopyForm((current) => ({ ...current, databaseName: event.target.value }))
                }
              />
              <input
                className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm font-semibold text-slate-900 outline-none transition focus:border-emerald-400 focus:bg-white"
                placeholder="Utilisateur"
                value={clientLocalCopyForm.user}
                onChange={(event) => setClientLocalCopyForm((current) => ({ ...current, user: event.target.value }))}
              />
              <input
                className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm font-semibold text-slate-900 outline-none transition focus:border-emerald-400 focus:bg-white"
                placeholder="Mot de passe"
                type="password"
                value={clientLocalCopyForm.password}
                onChange={(event) =>
                  setClientLocalCopyForm((current) => ({ ...current, password: event.target.value }))
                }
              />
            </div>

            <div className="mt-4 flex flex-wrap items-center gap-3">
              <Button
                variant="secondary"
                icon={Database}
                loading={clientSyncState === "INITIALIZING_SCHEMA"}
                onClick={() => void handleConfigureClientLocalCopy()}
              >
                Configurer la copie locale
              </Button>
              <span className="text-xs font-semibold text-slate-500">
                {clientLocalCopy?.configured
                  ? `${clientLocalCopy.databaseName || "Base locale"} sur ${clientLocalCopy.host || "127.0.0.1"}:${clientLocalCopy.port || 5432}`
                  : "Aucun mot de passe PostgreSQL n'est conserve dans le navigateur."}
              </span>
            </div>
          </div>

          {clientSyncImportResult ? (
            <div className="mt-5 grid gap-3 sm:grid-cols-4">
              {[
                { label: "Insertions", value: clientSyncImportResult.insertedCount ?? 0 },
                { label: "Mises a jour", value: clientSyncImportResult.updatedCount ?? 0 },
                { label: "Suppressions", value: clientSyncImportResult.deletedCount ?? 0 },
                { label: "Ignorees", value: clientSyncImportResult.skippedCount ?? 0 },
                { label: "Fichiers", value: clientSyncImportResult.fileCount ?? clientSyncImportResult.attachmentCount ?? 0 },
                { label: "Package", value: clientSyncImportResult.packageName || "-" },
              ].map((item) => (
                <div key={item.label} className="rounded-2xl border border-slate-200 bg-slate-50/70 px-4 py-4">
                  <p className="text-xs font-black uppercase tracking-[0.14em] text-slate-500">{item.label}</p>
                  <p className="mt-2 truncate text-sm font-bold text-slate-950">{item.value}</p>
                </div>
              ))}
            </div>
          ) : null}

          <div className="mt-5 flex flex-wrap gap-3">
            <Button
              icon={HardDrive}
              loading={["VALIDATION", "VERIFYING", "IMPORTING"].includes(clientSyncState)}
              disabled={!clientLocalCopy?.configured}
              onClick={() => void handleImportClientSyncPackageFile()}
            >
              Importer un package
            </Button>
            <Button
              variant="secondary"
              icon={RefreshCw}
              loading={clientSyncState === "CHECKING"}
              disabled={!clientLocalCopy?.configured}
              onClick={() => void handleCheckClientSyncUpdates()}
            >
              Actualiser
            </Button>
            <Button
              icon={Database}
              loading={["PREPARING", "DOWNLOADING", "VERIFYING", "IMPORTING"].includes(clientSyncState)}
              disabled={!clientLocalCopy?.configured || !clientSyncStatus || clientSyncStatus.available_update_count === 0}
              onClick={() => void handlePrepareClientSyncExport()}
            >
              Synchroniser sur ce poste
            </Button>
            <Button variant="secondary" icon={Activity} disabled={!clientLocalCopy?.configured} onClick={() => setHistoryOpen(true)}>
              Historique
            </Button>
            <Button variant="secondary" icon={Info} disabled={!clientLocalCopy?.configured} onClick={() => setDetailsOpen(true)}>
              Details
            </Button>
          </div>
        </Card>
      ) : null}

      <Modal open={previewOpen} title="Importer un package de synchronisation" onClose={() => setPreviewOpen(false)}>
        <div className="space-y-4">
          <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
            <p className="text-sm font-bold text-slate-950">{clientSyncPreview?.packageName || "-"}</p>
            <p className="mt-1 text-xs text-slate-500">{clientSyncPreview?.selectedPath || "-"}</p>
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            {[
              ["Serveur", clientSyncPreview?.summary?.server || clientSyncPreview?.serverId || "-"],
              ["Workspace", clientSyncPreview?.summary?.workspace || clientSyncPreview?.workspace?.name || "-"],
              ["Created", formatDateTime(clientSyncPreview?.summary?.created || clientSyncPreview?.createdAt || null)],
              ["Application version", clientSyncPreview?.summary?.applicationVersion || "-"],
              ["Schema version", String(clientSyncPreview?.summary?.schemaVersion ?? clientSyncPreview?.schemaVersion ?? "-")],
              ["Workers", String(clientSyncPreview?.summary?.workers ?? 0)],
              ["Visits", String(clientSyncPreview?.summary?.visits ?? 0)],
              ["Certificates", String(clientSyncPreview?.summary?.certificates ?? 0)],
              ["Medical Tests", String(clientSyncPreview?.summary?.medicalTests ?? 0)],
              ["Companies", String(clientSyncPreview?.summary?.companies ?? 0)],
              ["Campaigns", String(clientSyncPreview?.summary?.campaigns ?? 0)],
              ["Users", String(clientSyncPreview?.summary?.users ?? 0)],
              ["Total changes", String(clientSyncPreview?.summary?.totalChanges ?? 0)],
            ].map(([label, value]) => (
              <div key={label} className="rounded-2xl border border-slate-200 bg-white p-4">
                <p className="text-xs font-black uppercase tracking-[0.14em] text-slate-500">{label}</p>
                <p className="mt-2 text-sm font-bold text-slate-950">{value}</p>
              </div>
            ))}
          </div>
          {clientSyncPreview?.duplicate ? (
            <div className="rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
              Ce package a deja ete importe.
            </div>
          ) : null}
          <div className="flex justify-end gap-3">
            <Button variant="secondary" onClick={() => setPreviewOpen(false)}>
              Annuler
            </Button>
            <Button disabled={Boolean(clientSyncPreview?.duplicate)} onClick={() => void handleConfirmClientSyncImport()}>
              Confirmer l'import
            </Button>
          </div>
        </div>
      </Modal>

      <Modal open={historyOpen} title="Historique des imports" onClose={() => setHistoryOpen(false)}>
        <div className="space-y-3">
          {clientSyncHistory.length === 0 ? (
            <p className="text-sm text-slate-600">Aucun import enregistre.</p>
          ) : (
            clientSyncHistory.map((entry) => (
              <div key={entry.id} className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <p className="text-sm font-bold text-slate-950">{entry.packageName || entry.packageId || "Package"}</p>
                  <Badge tone={entry.status === "COMPLETED" ? "active" : entry.status === "FAILED" ? "failed" : "pending"}>
                    {entry.status}
                  </Badge>
                </div>
                <p className="mt-1 text-xs text-slate-500">{formatDateTime(entry.date || null)}</p>
                <p className="mt-2 text-sm text-slate-700">
                  {`Importees: ${entry.rowsImported ?? 0}, mises a jour: ${entry.rowsUpdated ?? 0}, ignorees: ${entry.rowsSkipped ?? 0}, checksum: ${entry.checksumSha256 || "-"}`}
                </p>
              </div>
            ))
          )}
        </div>
      </Modal>

      <Modal open={detailsOpen} title="Details de synchronisation" onClose={() => setDetailsOpen(false)}>
        <div className="grid gap-3 sm:grid-cols-2">
          {[
            ["Current local copy", clientLocalCopy?.configured ? `${clientLocalCopy.databaseName || "-"} @ ${clientLocalCopy.host || "-"}:${clientLocalCopy.port || "-"}` : "Non configuree"],
            ["Last synchronization", formatDateTime(clientSyncLocalStatus?.lastSyncAt || clientSyncLocalStatus?.lastImportedAt || null)],
            ["Package version", String(clientSyncLocalStatus?.schemaVersion ?? "-")],
            ["Imported rows", String(clientSyncLocalStatus?.importedRowsTotal ?? 0)],
            ["Pending changes", String(pendingChanges)],
            ["Last package", clientSyncLocalStatus?.lastPackageName || "-"],
            ["Local cursor", String(clientSyncLocalStatus?.lastSyncCursor ?? clientSyncCursor)],
            ["Checksum", clientSyncLocalStatus?.lastPackageChecksum || "-"],
          ].map(([label, value]) => (
            <div key={label} className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
              <p className="text-xs font-black uppercase tracking-[0.14em] text-slate-500">{label}</p>
              <p className="mt-2 text-sm font-bold text-slate-950">{value}</p>
            </div>
          ))}
        </div>
      </Modal>

      <Modal open={restoreModalOpen} title="Confirmer la restauration" onClose={() => setRestoreModalOpen(false)}>
        <div className="space-y-4">
          <div className="rounded-2xl border border-amber-200 bg-amber-50 px-4 py-4 text-sm leading-6 text-amber-900">
            Cette operation va restaurer les donnees de la sauvegarde dans la base PostgreSQL actuelle. Une sauvegarde automatique de l'etat actuel sera creee avant la restauration. Les utilisateurs connectes doivent eviter de modifier les donnees pendant l'operation.
          </div>
          <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-4">
            <p className="text-xs font-black uppercase tracking-[0.14em] text-slate-500">Fichier</p>
            <p className="mt-2 text-sm font-bold text-slate-950">{selectedRestoreFile?.name || "-"}</p>
            <p className="mt-1 text-xs text-slate-500">
              {selectedRestoreFile ? formatFileSize(selectedRestoreFile.size) : "-"}
            </p>
          </div>
          <div className="flex justify-end gap-3">
            <Button variant="secondary" onClick={() => setRestoreModalOpen(false)}>
              Annuler
            </Button>
            <Button loading={backupActionLoading === "restore"} onClick={() => void handleRestoreBackup()}>
              Confirmer la restauration
            </Button>
          </div>
        </div>
      </Modal>

      {/* Row 2 — Database + Network */}
      <section className="grid gap-6 xl:grid-cols-2">
        <Card className="h-full rounded-[1.75rem] border-slate-200 bg-white p-6">
          <div className="flex items-start justify-between gap-4">
            <div>
              <p className="text-xs font-black uppercase tracking-[0.16em] text-violet-600">
                Stockage central
              </p>
              <h3 className="mt-2 text-xl font-black text-slate-950">Base de données</h3>
              <p className="mt-1 text-sm leading-6 text-slate-500">
                État du moteur de données utilisé par l’infrastructure.
              </p>
            </div>

            <div className="rounded-2xl bg-violet-50 p-3 text-violet-700">
              <Database className="h-5 w-5" />
            </div>
          </div>

          <div className="mt-6 grid gap-3 sm:grid-cols-2">
            {[
              { label: "Moteur", value: databaseType },
              { label: "Statut", value: databaseStatusLabel },
              { label: "Base", value: databaseStatus?.database_name || "-" },
              {
                label: "Hote",
                value: `${databaseStatus?.database_host || "-"}:${databaseStatus?.database_port || 5432}`,
              },
              {
                label: "Connexions actives",
                value: String(databaseStatus?.active_connections ?? 0),
              },
              {
                label: "Pool",
                value: `${databaseStatus?.pool_checked_out ?? 0}/${databaseStatus?.pool_size ?? 0}`,
              },
              {
                label: "Dernière sauvegarde",
                value: formatDateTime(
                  backupStatus?.last_backup_time || databaseStatus?.last_backup_time || null,
                ),
              },
              { label: "Sauvegardes", value: String(backupStatus?.backup_count ?? 0) },
            ].map((item) => (
              <div
                key={item.label}
                className="rounded-2xl border border-slate-200 bg-slate-50/70 p-4"
              >
                <p className="text-[11px] font-black uppercase tracking-[0.14em] text-slate-500">
                  {item.label}
                </p>
                <p className="mt-3 break-words text-sm font-bold text-slate-950">
                  {item.value}
                </p>
              </div>
            ))}
          </div>

          {canConfigureDatabase && (
            <div className="mt-4 rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-xs font-medium text-slate-600">
              Les paramètres PostgreSQL sont accessibles aux administrateurs uniquement.
            </div>
          )}
        </Card>

        <Card className="h-full rounded-[1.75rem] border-slate-200 bg-white p-6">
          <div className="flex items-start justify-between gap-4">
            <div>
              <p className="text-xs font-black uppercase tracking-[0.16em] text-cyan-600">
                Paramètres LAN
              </p>
              <h3 className="mt-2 text-xl font-black text-slate-950">
                Configuration réseau
              </h3>
              <p className="mt-1 text-sm leading-6 text-slate-500">
                Informations techniques utilisées par ce poste.
              </p>
            </div>

            <div className="rounded-2xl bg-cyan-50 p-3 text-cyan-700">
              <Network className="h-5 w-5" />
            </div>
          </div>

          <div className="mt-6 grid gap-3 sm:grid-cols-2">
            {[
              { label: "Adresse IP locale", value: desktopLocalIp },
              {
                label: "URL API",
                value: effectiveMode === "server" ? desktopServerApiUrl : serverUrl || "-",
              },
              { label: "Port API", value: "8000" },
              {
                label: "Accès LAN",
                value:
                  localIpAddress && localIpAddress !== "0.0.0.0"
                    ? "Activé"
                    : "Indisponible",
              },
              { label: "Accès Internet", value: online ? "Disponible" : "Indisponible" },
              {
                label: "Dernière connexion",
                value: formatDateTime(lastSuccessfulConnection),
              },
            ].map((item) => (
              <div
                key={item.label}
                className="rounded-2xl border border-slate-200 bg-slate-50/70 px-4 py-3.5"
              >
                <p className="text-[11px] font-black uppercase tracking-[0.14em] text-slate-500">
                  {item.label}
                </p>
                <p className="mt-2 break-all text-sm font-bold text-slate-950">
                  {item.value}
                </p>
              </div>
            ))}
          </div>
        </Card>
      </section>

      {/* Row 3 — Connected Users */}
      <section>
        <ConnectedUsersTable users={connectedUsers} />
      </section>

      <RecoveryPanel />

      {/* Row 4 — Synchronization */}
      <section className="grid gap-6 xl:grid-cols-[minmax(0,1.35fr)_minmax(340px,0.65fr)]">
        <SyncStatusPanel
          pendingChanges={pendingChanges}
          conflictCount={conflictCount}
          lastSyncedAt={formatDateTime(lastSyncedAt || status?.last_sync_at || null)}
          serverTime={formatDateTime(status?.server_time || null)}
          syncStatus={syncStatus}
          canSync={online}
          onSyncNow={handleSyncNow}
        />

        <Card className="h-full rounded-[1.75rem] border-slate-200 bg-white p-6">
          <div className="flex items-start justify-between gap-4">
            <div>
              <p className="text-xs font-black uppercase tracking-[0.16em] text-sky-600">
                Résumé de synchronisation
              </p>
              <h3 className="mt-2 text-xl font-black text-slate-950">Vue opérationnelle</h3>
              <p className="mt-1 text-sm leading-6 text-slate-500">
                Indicateurs rapides sur les échanges avec le serveur.
              </p>
            </div>

            <div className="rounded-2xl bg-sky-50 p-3 text-sky-700">
              <RefreshCw className={`h-5 w-5 ${syncing ? "animate-spin" : ""}`} />
            </div>
          </div>

          <div className="mt-6 space-y-3">
            {[
              { label: "État global", value: syncStatus },
              { label: "Modifications en attente", value: String(pendingChanges) },
              { label: "Conflits détectés", value: String(conflictCount) },
              {
                label: "Dernière synchronisation",
                value: formatDateTime(lastSyncedAt || status?.last_sync_at || null),
              },
            ].map((item) => (
              <div
                key={item.label}
                className="flex items-center justify-between gap-4 rounded-2xl border border-slate-200 bg-slate-50/70 px-4 py-3.5"
              >
                <span className="text-sm font-medium text-slate-600">{item.label}</span>
                <span className="text-right text-sm font-bold capitalize text-slate-950">
                  {item.value}
                </span>
              </div>
            ))}
          </div>
        </Card>
      </section>

      {/* Row 5 — Backup */}
      <section>
        <BackupPanel
          autoBackupStatus={backupStatus?.enabled === false ? "Désactivée" : "Active"}
          lastBackupTime={formatDateTime(
            backupStatus?.last_backup_time || databaseStatus?.last_backup_time || null,
          )}
          lastBackupStatus={backupStatus?.last_backup_status || "Indisponible"}
          serverActionsAvailable={backupStatus?.server_actions_available ?? effectiveMode === "server"}
          operationState={backupStatus?.operation_state || "IDLE"}
          canDownloadBackup={effectiveMode === "server" && canCreateServerBackup}
          canRestoreBackup={
            effectiveMode === "server" &&
            canRestoreServerBackup &&
            Boolean(selectedRestoreFile) &&
            !restoreFileError
          }
          selectedFileName={selectedRestoreFile?.name || null}
          selectedFileSizeLabel={selectedRestoreFile ? formatFileSize(selectedRestoreFile.size) : null}
          restoreWarning={restoreFileError}
          downloadLoading={backupActionLoading === "download"}
          restoreLoading={backupActionLoading === "restore"}
          onPickRestoreFile={setSelectedRestoreFile}
          onDownloadBackup={handleCreateBackup}
          onRestoreBackup={async () => {
            if (!selectedRestoreFile || restoreFileError) {
              setError(restoreFileError || "Selectionnez un fichier de sauvegarde avant de restaurer.");
              return;
            }
            setRestoreModalOpen(true);
          }}
        />
      </section>

      {/* Row 6 — System Logs */}
      <section>
        <Card className="rounded-[1.75rem] border-slate-200 bg-white p-6">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <p className="text-xs font-black uppercase tracking-[0.16em] text-slate-500">
                Activité locale
              </p>
              <h3 className="mt-2 text-xl font-black text-slate-950">Journal système</h3>
              <p className="mt-1 text-sm leading-6 text-slate-500">
                Événements récents liés au serveur, à la connexion, aux sauvegardes et à la
                synchronisation.
              </p>
            </div>

            <div className="rounded-2xl bg-slate-100 p-3 text-slate-700">
              <HardDrive className="h-5 w-5" />
            </div>
          </div>

          <div className="mt-6 space-y-3">
            {systemLogs.length ? (
              systemLogs.map((log) => (
                <div
                  key={log.id}
                  className="group flex flex-col gap-3 rounded-2xl border border-slate-200 bg-slate-50/70 px-4 py-4 transition hover:border-slate-300 hover:bg-white sm:flex-row sm:items-center sm:justify-between"
                >
                  <div className="flex min-w-0 items-start gap-3">
                    <span
                      className={[
                        "mt-1 h-2.5 w-2.5 shrink-0 rounded-full",
                        log.tone === "active"
                          ? "bg-emerald-500"
                          : log.tone === "failed"
                            ? "bg-rose-500"
                            : "bg-amber-500",
                      ].join(" ")}
                    />

                    <div className="min-w-0">
                      <p className="truncate text-sm font-bold text-slate-950">
                        {log.message}
                      </p>
                      <p className="mt-1 text-xs text-slate-500">
                        {formatDateTime(log.timestamp)}
                      </p>
                    </div>
                  </div>

                  <Badge tone={log.tone}>
                    {log.tone === "active"
                      ? "Succès"
                      : log.tone === "failed"
                        ? "Erreur"
                        : "Information"}
                  </Badge>
                </div>
              ))
            ) : (
              <div className="rounded-2xl border border-dashed border-slate-300 bg-slate-50/60 px-4 py-10 text-center">
                <HardDrive className="mx-auto h-6 w-6 text-slate-400" />
                <p className="mt-3 text-sm font-bold text-slate-700">
                  Aucun événement local enregistré
                </p>
                <p className="mt-1 text-xs text-slate-500">
                  Les opérations réseau apparaîtront ici.
                </p>
              </div>
            )}
          </div>
        </Card>
      </section>
    </div>
  );
};
