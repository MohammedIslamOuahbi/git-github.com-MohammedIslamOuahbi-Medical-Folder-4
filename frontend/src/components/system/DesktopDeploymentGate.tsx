import { useEffect, useMemo, useState, type ReactNode } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  Database,
  Globe,
  KeyRound,
  LaptopMinimal,
  LoaderCircle,
  Network,
  Server,
  ShieldCheck,
} from "lucide-react";

import { Badge } from "@/components/common/Badge";
import { Button } from "@/components/common/Button";
import { Card } from "@/components/common/Card";
import { Input } from "@/components/common/Input";
import type {
  DesktopRuntimeContext,
  FinalizeServerSetupResult,
  PostgresInspection,
  SelectedBackupFile,
  ServerBootstrapResult,
} from "@/desktop/tauriRuntime";
import {
  LOCAL_SERVER_ROOT_URL,
  cleanupSensitiveDeploymentStorage,
  connectionModeToOperationMode,
  detectTauriRuntime,
  getStoredIsTauri,
  getStoredServerUrl,
  getStoredSetupCompleted,
  hasStoredServerUrl,
  isRuntimeSetupRequired,
  readStoredOperationMode,
  readStoredConnectionMode,
  setStoredConnectionMode,
  setStoredOperationMode,
  setStoredServerUrl,
  setStoredSetupCompleted,
  type OperationMode,
  type ConnectionMode,
} from "@/config/runtime";
import { syncConnectionApi } from "@/services/syncConnectionApi";

type DeploymentGateProps = {
  children?: ReactNode;
  forceOpen?: boolean;
  onReady?: () => void;
};

type ReadinessTone = "active" | "pending" | "failed";

type ReadinessItem = {
  id: string;
  label: string;
  status: "ok" | "pending" | "failed";
  detail: string;
};

type ServerBootstrapForm = {
  host: string;
  port: string;
  adminUser: string;
  adminPassword: string;
  appDatabase: string;
  appUser: string;
  appUserPassword: string;
  apiBindHost: string;
  apiPort: string;
  openFirewall: boolean;
  initialAdminFirstName: string;
  initialAdminLastName: string;
  initialAdminEmail: string;
  initialAdminPassword: string;
  initialAdminPasswordConfirmation: string;
  initialAdminPhone: string;
  initialAdminQualification: string;
};

type ServerDataImportMode = "initial" | "restore";

const toRootUrl = (value: string) => value.replace(/\/api\/v1\/?$/, "").replace(/\/$/, "");

const mapItemTone = (status: ReadinessItem["status"]): ReadinessTone =>
  status === "ok" ? "active" : status === "failed" ? "failed" : "pending";

const defaultItems = (mode: OperationMode | null): ReadinessItem[] => {
  if (mode === "server") {
    return [
      { id: "postgres", label: "PostgreSQL", status: "pending", detail: "Verification de l'installation locale." },
      { id: "service", label: "Service PostgreSQL", status: "pending", detail: "Le service Windows sera controle." },
      { id: "config", label: "Configuration production", status: "pending", detail: "backend.env local sera prepare." },
      { id: "migration", label: "Schema Alembic", status: "pending", detail: "La base doit etre migree avant le demarrage." },
      { id: "sidecar", label: "Backend sidecar", status: "pending", detail: "En attente du demarrage local." },
      { id: "health", label: "API /health", status: "pending", detail: "A verifier sur le serveur local." },
      { id: "network", label: "Acces reseau", status: "pending", detail: "L'adresse LAN sera detectee." },
    ];
  }

  if (mode === "client") {
    return [
      { id: "mode", label: "Mode Client", status: "pending", detail: "Le backend local doit rester desactive." },
      { id: "server-url", label: "URL API du serveur", status: "pending", detail: "Saisissez l'URL du serveur principal." },
      { id: "health", label: "API distante", status: "pending", detail: "Le serveur sera teste via /health." },
    ];
  }

  return [
    { id: "mode", label: "Choix du mode", status: "pending", detail: "Selectionnez Mode Serveur ou Mode Client." },
  ];
};

const updateReadinessItem = (
  current: ReadinessItem[],
  id: string,
  next: Partial<Pick<ReadinessItem, "status" | "detail">>,
) =>
  current.map((item) => (item.id === id ? { ...item, ...next } : item));

const validateInitialAdminPasswordPolicy = (value: string) => {
  const password = value.trim();
  if (password.length < 10) {
    throw new Error("Le mot de passe de l'administrateur initial doit contenir au moins 10 caracteres.");
  }

  const hasLetter = /[A-Za-z]/.test(password);
  const hasDigit = /\d/.test(password);
  if (!hasLetter || !hasDigit) {
    throw new Error("Le mot de passe de l'administrateur initial doit contenir au moins une lettre et un chiffre.");
  }
};

const formatReadinessError = (error: unknown) => {
  const message = error instanceof Error ? error.message : String(error || "");
  if (!message.trim()) {
    return "Configuration du serveur impossible: erreur inconnue.";
  }

  const [code, ...rest] = message.split(":");
  const details = rest.join(":").trim();
  const knownMessages: Record<string, string> = {
    INVALID_FASTAPI_BIND_HOST: "Hote FastAPI invalide.",
    INVALID_FASTAPI_PORT: "Port FastAPI invalide.",
    INVALID_STORED_RUNTIME_CONFIG: "Configuration runtime backend.env invalide.",
    LAN_IP_NOT_FOUND: "Adresse LAN introuvable.",
    LOCAL_HEALTH_FAILED: "Le test local du backend a echoue.",
    LOCAL_HEALTH_TIMEOUT: "Le backend local n'a pas repondu a temps.",
    LAN_HEALTH_FAILED: "Le test LAN a echoue.",
    FIREWALL_RULE_FAILED: "La regle du pare-feu Windows n'a pas pu etre creee.",
    PORT_ALREADY_IN_USE: "Le port FastAPI est deja utilise.",
    INITIAL_USER_CREATION_FAILED:
      "Impossible de creer le premier administrateur. Verifiez son email et utilisez un mot de passe d'au moins 10 caracteres contenant au moins une lettre et un chiffre.",
    INITIAL_DATA_SETUP_FAILED:
      "Impossible d'initialiser l'application. Verifiez l'administrateur initial et consultez les journaux techniques si le probleme persiste.",
  };

  if (message.includes("INITIAL_USER_CREATION_FAILED")) {
    return knownMessages.INITIAL_USER_CREATION_FAILED;
  }

  if (message.includes("INITIAL_DATA_SETUP_FAILED")) {
    return knownMessages.INITIAL_DATA_SETUP_FAILED;
  }

  return knownMessages[code] ? `${knownMessages[code]}${details ? ` ${details}` : ""}` : message;
};

const buildServerDefaults = (): ServerBootstrapForm => ({
  host: "localhost",
  port: "5432",
  adminUser: "postgres",
  adminPassword: "",
  appDatabase: "medical_folder",
  appUser: "clinic_user",
  appUserPassword: "",
  apiBindHost: "0.0.0.0",
  apiPort: "8000",
  openFirewall: true,
  initialAdminFirstName: "",
  initialAdminLastName: "",
  initialAdminEmail: "",
  initialAdminPassword: "",
  initialAdminPasswordConfirmation: "",
  initialAdminPhone: "",
  initialAdminQualification: "",
});

const clearBootstrapSecrets = (form: ServerBootstrapForm): ServerBootstrapForm => ({
  ...form,
  adminPassword: "",
  appUserPassword: "",
  initialAdminPassword: "",
  initialAdminPasswordConfirmation: "",
});

const validateClientServerUrl = (value: string) => {
  const trimmed = value.trim();
  if (!trimmed) {
    throw new Error("URL API du serveur requise.");
  }

  const url = new URL(/^https?:\/\//i.test(trimmed) ? trimmed : `http://${trimmed}`);
  if (!["http:", "https:"].includes(url.protocol)) {
    throw new Error("Seules les URL HTTP ou HTTPS sont autorisees pour FastAPI.");
  }
  if (!url.hostname) {
    throw new Error("L'URL API doit contenir l'adresse du serveur.");
  }
  if (url.username || url.password) {
    throw new Error("L'URL API ne doit pas contenir d'identifiants integres.");
  }
  if (url.port === "5173") {
    throw new Error("URL frontend invalide en production. Utilisez http://IP:8000.");
  }
};

const detailForBootstrapStep = (step: string) => {
  switch (step) {
    case "postgres_installation":
      return "postgres";
    case "postgres_service":
      return "service";
    case "database_provision":
      return "config";
    case "alembic":
      return "migration";
    default:
      return "config";
  }
};

export const DesktopDeploymentGate = ({ children, forceOpen = false, onReady }: DeploymentGateProps) => {
  const isTauri = detectTauriRuntime() || getStoredIsTauri();
  const initialConnectionMode = readStoredConnectionMode() || (readStoredOperationMode() === "client" ? "CLIENT" : null);
  const [selectedConnectionMode, setSelectedConnectionMode] = useState<ConnectionMode | null>(initialConnectionMode);
  const [selectedMode, setSelectedMode] = useState<OperationMode | null>(
    initialConnectionMode ? connectionModeToOperationMode(initialConnectionMode) : null,
  );
  const [serverUrl, setServerUrlState] = useState(getStoredServerUrl());
  const [desktopContext, setDesktopContext] = useState<DesktopRuntimeContext | null>(null);
  const [postgresInspection, setPostgresInspection] = useState<PostgresInspection | null>(null);
  const [bootstrapForm, setBootstrapForm] = useState<ServerBootstrapForm>(buildServerDefaults());
  const [bootstrapResult, setBootstrapResult] = useState<ServerBootstrapResult | null>(null);
  const [finalizeResult, setFinalizeResult] = useState<FinalizeServerSetupResult | null>(null);
  const [dataImportMode, setDataImportMode] = useState<ServerDataImportMode>("initial");
  const [selectedBackupFile, setSelectedBackupFile] = useState<SelectedBackupFile | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [isBusy, setIsBusy] = useState(false);
  const [isInspecting, setIsInspecting] = useState(false);
  const [isReady, setIsReady] = useState(!isTauri);
  const [readinessItems, setReadinessItems] = useState<ReadinessItem[]>(defaultItems(readStoredOperationMode()));
  const [restoreConfirmation, setRestoreConfirmation] = useState("");
  const [pendingMode, setPendingMode] = useState<ConnectionMode | null>(null);
  const isLocalServerPc = selectedConnectionMode === "SERVER_PC";
  const remoteServerLabel = selectedConnectionMode === "SERVER" ? "Adresse du serveur central" : "URL API du serveur";

  useEffect(() => {
    cleanupSensitiveDeploymentStorage();
  }, []);

  useEffect(() => {
    setReadinessItems(defaultItems(selectedMode));
    if (selectedMode === "client") {
      cleanupSensitiveDeploymentStorage();
      setBootstrapForm((current) => clearBootstrapSecrets(current));
      setBootstrapResult(null);
    }
  }, [selectedMode]);

  const showGate = useMemo(() => {
    if (forceOpen) {
      return true;
    }
    if (!isTauri) {
      return false;
    }

    return !isReady || isRuntimeSetupRequired();
  }, [isReady, isTauri]);

  const captureContext = async () => {
    const nextContext = await syncConnectionApi.getDesktopRuntimeContext();
    setDesktopContext(nextContext);
    return nextContext;
  };

  const mergeServerDefaults = (inspection: PostgresInspection | null) => {
    const defaults = buildServerDefaults();
    setBootstrapForm((current) => ({
      ...defaults,
      ...current,
    }));
  };

  const refreshInspection = async () => {
    setIsInspecting(true);
    try {
      const inspection = await syncConnectionApi.inspectPostgresInstallation();
      setPostgresInspection(inspection);
      mergeServerDefaults(inspection);
      setReadinessItems((current) =>
        updateReadinessItem(
          updateReadinessItem(current, "postgres", {
            status: inspection?.installed ? "ok" : "failed",
            detail: inspection?.message || "Inspection PostgreSQL indisponible.",
          }),
          "service",
          {
            status:
              !inspection?.serviceStatus || inspection.serviceStatus.toLowerCase() === "running"
                ? "ok"
                : "failed",
            detail: inspection?.serviceStatus
              ? `${inspection.serviceName || "postgresql"}: ${inspection.serviceStatus}`
              : "Aucun service PostgreSQL Windows detecte.",
          },
        ),
      );
      return inspection;
    } finally {
      setIsInspecting(false);
    }
  };

  const handleServerUrlChange = (value: string) => {
    setServerUrlState(value);
    if (!value.trim()) {
      setStoredSetupCompleted(false);
    }
  };

  const handleBootstrapFieldChange = (field: keyof ServerBootstrapForm, value: string | boolean) => {
    setBootstrapForm((current) => ({
      ...current,
      [field]: value,
    }));
  };

  const handlePickRestoreBackup = async () => {
    const selected = await syncConnectionApi.chooseServerRestoreBackupFile();
    if (selected) {
      setSelectedBackupFile(selected);
    }
  };

  const markReady = (mode: OperationMode, nextUrl?: string) => {
    setStoredOperationMode(mode);
    setStoredConnectionMode(selectedConnectionMode);
    const resolvedUrl = nextUrl || (mode === "server" ? LOCAL_SERVER_ROOT_URL : "");
    if (resolvedUrl) {
      setStoredServerUrl(resolvedUrl);
    }
    setStoredSetupCompleted(true);
    setSelectedMode(mode);
    setIsReady(true);
    onReady?.();
  };

  const hasExistingConfiguration = Boolean(readStoredOperationMode() && getStoredServerUrl() && getStoredSetupCompleted());

  const handleModeSelection = (nextConnectionMode: ConnectionMode) => {
    const nextMode = connectionModeToOperationMode(nextConnectionMode);
    if (hasExistingConfiguration && selectedConnectionMode && selectedConnectionMode !== nextConnectionMode) {
      setPendingMode(nextConnectionMode);
      return;
    }

    setPendingMode(null);
    setSelectedConnectionMode(nextConnectionMode);
    setSelectedMode(nextMode);
    setError(null);
    setMessage(null);
  };

  const confirmModeSelection = () => {
    if (!pendingMode) {
      return;
    }
    setSelectedConnectionMode(pendingMode);
    setSelectedMode(connectionModeToOperationMode(pendingMode));
    setPendingMode(null);
    setError(null);
    setMessage(null);
  };

  const runClientReadiness = async (
    rawServerUrl: string,
    persist = true,
    connectionMode: ConnectionMode = selectedConnectionMode || "CLIENT",
  ) => {
    const trimmed = rawServerUrl.trim();
    if (!trimmed) {
      throw new Error("URL API du serveur requise.");
    }

    try {
      validateClientServerUrl(trimmed);
    } catch (validationError) {
      throw new Error(
        validationError instanceof Error ? validationError.message : "URL API du serveur invalide.",
      );
    }

    setReadinessItems((current) =>
      updateReadinessItem(current, "mode", {
        status: "ok",
        detail:
          connectionMode === "SERVER"
            ? "Mode Serveur central distant actif. Aucun backend local ne sera lance."
            : "Mode Client actif. Aucun backend local ne sera lance.",
      }),
    );
    setReadinessItems((current) =>
      updateReadinessItem(current, "server-url", {
        status: "pending",
        detail: "Verification de l'URL API du serveur...",
      }),
    );

    const health = await syncConnectionApi.testServer(trimmed);
    if (health?.status !== "ok") {
      setReadinessItems((current) =>
        updateReadinessItem(current, "health", {
          status: "failed",
          detail: health?.incompatible
            ? "Le service distant ne correspond pas au serveur médical attendu."
            : "Le serveur distant ne repond pas sur /health.",
        }),
      );
      throw new Error(
        health?.incompatible
          ? "Serveur incompatible. Verifiez que l'URL pointe vers le serveur FastAPI Ibn Sina."
          : "Serveur inaccessible. Verifiez l'URL API et le reseau local.",
      );
    }

    const normalized = syncConnectionApi.setLastServerUrl(trimmed);
    setServerUrlState(normalized);

    await syncConnectionApi.connectClient(normalized, connectionMode === "SERVER" ? "Poste Serveur central" : "Poste Client");
    const nextContext =
      connectionMode === "SERVER"
        ? await syncConnectionApi.applyOperationMode("SERVER", normalized)
        : await captureContext();
    setDesktopContext(nextContext);

    setReadinessItems((current) =>
      updateReadinessItem(
        updateReadinessItem(current, "server-url", {
          status: "ok",
          detail: normalized,
        }),
        "health",
        {
          status: "ok",
          detail: "Connexion API reussie.",
        },
      ),
    );

    setMessage(`${connectionMode === "SERVER" ? "Serveur central" : "Client"} configure avec ${toRootUrl(normalized)}.`);
    setError(null);

    if (persist) {
      markReady("client", normalized);
    }

    return nextContext;
  };

  const runServerBootstrap = async () => {
    const inspection = (await refreshInspection()) || postgresInspection;
    if (!inspection?.installed) {
      throw new Error("PostgreSQL n'est pas detecte sur ce PC serveur.");
    }

    if (inspection.serviceStatus && inspection.serviceStatus.toLowerCase() !== "running") {
      throw new Error("Le service PostgreSQL doit etre demarre sur le serveur principal.");
    }

    if (!bootstrapForm.adminPassword.trim()) {
      throw new Error("Renseignez le mot de passe administrateur PostgreSQL.");
    }

    if (!bootstrapForm.appUserPassword.trim()) {
      throw new Error("Renseignez le mot de passe de l'utilisateur applicatif.");
    }
    if (!bootstrapForm.initialAdminFirstName.trim() || !bootstrapForm.initialAdminLastName.trim()) {
      throw new Error("Renseignez le prenom et le nom de l'administrateur initial.");
    }
    if (!bootstrapForm.initialAdminEmail.trim()) {
      throw new Error("Renseignez l'email de l'administrateur initial.");
    }
    if (!bootstrapForm.initialAdminPassword.trim()) {
      throw new Error("Renseignez le mot de passe de l'administrateur initial.");
    }
    if (bootstrapForm.initialAdminPassword !== bootstrapForm.initialAdminPasswordConfirmation) {
      throw new Error("La confirmation du mot de passe administrateur initial ne correspond pas.");
    }
    validateInitialAdminPasswordPolicy(bootstrapForm.initialAdminPassword);

    setReadinessItems((current) =>
      updateReadinessItem(current, "config", {
        status: "pending",
        detail: "Creation de la base, de l'utilisateur et du backend.env local...",
      }),
    );
    setReadinessItems((current) =>
      updateReadinessItem(current, "migration", {
        status: "pending",
        detail: "Execution des migrations Alembic...",
      }),
    );

    const capability = await syncConnectionApi.beginServerProvisioning();
    if (!capability?.capability) {
      throw new Error("Autorisation locale de provisioning indisponible.");
    }

    const result = await syncConnectionApi.bootstrapServerPostgres({
      provisioningCapability: capability.capability,
      host: bootstrapForm.host.trim(),
      port: Number(bootstrapForm.port || 5432),
      adminUser: bootstrapForm.adminUser.trim(),
      adminPassword: bootstrapForm.adminPassword,
      appDatabase: bootstrapForm.appDatabase.trim(),
      appUser: bootstrapForm.appUser.trim(),
      appUserPassword: bootstrapForm.appUserPassword,
      apiBindHost: bootstrapForm.apiBindHost.trim() || "0.0.0.0",
      apiPort: Number(bootstrapForm.apiPort || 8000),
      openFirewall: bootstrapForm.openFirewall,
      initialAdminFirstName: bootstrapForm.initialAdminFirstName.trim(),
      initialAdminLastName: bootstrapForm.initialAdminLastName.trim(),
      initialAdminEmail: bootstrapForm.initialAdminEmail.trim(),
      initialAdminPassword: bootstrapForm.initialAdminPassword,
      initialAdminPhone: bootstrapForm.initialAdminPhone.trim(),
      initialAdminQualification: bootstrapForm.initialAdminQualification.trim(),
    });

    setBootstrapForm((current) => clearBootstrapSecrets(current));
    cleanupSensitiveDeploymentStorage();

    if (!result?.success) {
      setBootstrapResult(null);
      const itemId = detailForBootstrapStep(result?.step || "");
      setReadinessItems((current) =>
        updateReadinessItem(current, itemId, {
          status: "failed",
          detail: result?.message || "Bootstrap PostgreSQL echoue.",
        }),
      );
      throw new Error(result?.message || "Configuration PostgreSQL impossible.");
    }

    setBootstrapResult(result);

    setReadinessItems((current) =>
      updateReadinessItem(
        updateReadinessItem(current, "config", {
          status: "ok",
          detail: result.configPath
            ? `Configuration production enregistree dans ${result.configPath}`
            : "Configuration production enregistree.",
        }),
        "migration",
        {
          status: "ok",
          detail: "Migrations Alembic appliquees.",
        },
      ),
    );

    setMessage(result.warning ? `${result.message} ${result.warning}` : result.message);
    return result;
  };

  const runServerDataImport = async () => {
    const finalize = await syncConnectionApi.finalizeServerSetup({
      mode: dataImportMode,
      backupPath: dataImportMode === "restore" ? selectedBackupFile?.path : undefined,
      confirmationPhrase: dataImportMode === "restore" ? restoreConfirmation : undefined,
    });
    if (!finalize?.success) {
      throw new Error("La finalisation de la configuration serveur a echoue.");
    }
    setFinalizeResult(finalize);
    setMessage(finalize.detail);
    setError(null);
    await runServerReadiness(true);
  };

  const runServerReadiness = async (
    persist = true,
    connectionMode: ConnectionMode = selectedConnectionMode || "SERVER_PC",
  ) => {
    setReadinessItems((current) =>
      updateReadinessItem(current, "sidecar", {
        status: "pending",
        detail: "Demarrage du backend local...",
      }),
    );

    const nextContext = await syncConnectionApi.applyOperationMode(connectionMode);
    setDesktopContext(nextContext);

    setReadinessItems((current) =>
      updateReadinessItem(current, "sidecar", {
        status: nextContext.backendStatus === "Running" ? "ok" : "failed",
        detail: nextContext.message || "Etat du backend local indisponible.",
      }),
    );

    if (nextContext.backendStatus !== "Running") {
      throw new Error(nextContext.message || "Le backend local n'a pas pu demarrer.");
    }

    const localServerRootUrl = toRootUrl(nextContext.apiBaseUrl || LOCAL_SERVER_ROOT_URL);
    const serverPort = (() => {
      try {
        return new URL(localServerRootUrl).port || "8000";
      } catch {
        return "8000";
      }
    })();
    const health = await syncConnectionApi.testServer(localServerRootUrl);
    if (health?.status !== "ok") {
      await syncConnectionApi.stopLocalServer().catch(() => undefined);
      setReadinessItems((current) =>
        updateReadinessItem(current, "health", {
          status: "failed",
          detail: health?.incompatible
            ? "L'identité du serveur local ne correspond pas à l'application médicale."
            : `Le backend local ne repond pas sur ${localServerRootUrl}/health.`,
        }),
      );
      throw new Error(
        health?.incompatible
          ? "Serveur local incompatible. Verifiez le backend sidecar installé."
          : "Le backend local ne repond pas sur l'adresse locale 127.0.0.1. Verifiez le port FastAPI et le demarrage du sidecar.",
      );
    }

    setReadinessItems((current) =>
      updateReadinessItem(current, "health", {
        status: "ok",
        detail: "API locale accessible sur /health.",
      }),
    );

    const databaseHealth = await syncConnectionApi.getDatabaseHealth(localServerRootUrl);
    const databaseStatus = String(databaseHealth?.status || databaseHealth?.database_status || "error").toLowerCase();
    const databaseType = String(databaseHealth?.database_type || "");
    const productionReady =
      databaseHealth?.production_ready !== false && databaseType.toLowerCase().includes("postgres");

    if (databaseStatus !== "ok" || !productionReady) {
      await syncConnectionApi.stopLocalServer().catch(() => undefined);
      setReadinessItems((current) =>
        updateReadinessItem(current, "config", {
          status: "failed",
          detail:
            String(databaseHealth?.warning || "") ||
            "PostgreSQL doit etre configure sur le PC serveur principal.",
        }),
      );
      throw new Error(
        String(databaseHealth?.warning || "") ||
          "Base PostgreSQL non disponible. Installez PostgreSQL sur le serveur et configurez backend.env.",
      );
    }

    setReadinessItems((current) =>
      updateReadinessItem(
        updateReadinessItem(current, "config", {
          status: "ok",
          detail: `${databaseType || "PostgreSQL"} pret pour la production.`,
        }),
        "migration",
        {
          status: "ok",
          detail: "Schema applicatif disponible et base repondante.",
        },
      ),
    );

    const networkInfo = await syncConnectionApi.getNetworkInfo(localServerRootUrl);
    const localIp = String(networkInfo?.local_ip_address || nextContext.localIpAddress || "");
    if (!localIp) {
      setReadinessItems((current) =>
        updateReadinessItem(current, "network", {
          status: "pending",
          detail:
            "Adresse LAN introuvable. Le backend fonctionne localement; choisissez ou verifiez l'adresse reseau avant de connecter les clients.",
        }),
      );
      setMessage(
        `Serveur demarre localement sur ${localServerRootUrl}. Adresse LAN introuvable: verifiez le reseau ou le pare-feu Windows avant de connecter les clients.`,
      );
      setError(null);
      if (persist) {
        markReady("server");
      }
      return nextContext;
    }

    setReadinessItems((current) =>
      updateReadinessItem(current, "network", {
        status: "ok",
        detail: `Clients attendus sur http://${localIp}:${serverPort}`,
      }),
    );

    setMessage(`Serveur pret. Les autres postes peuvent utiliser http://${localIp}:${serverPort}`);
    setError(null);

    if (persist) {
      markReady("server");
    }

    return nextContext;
  };

  const handleContinue = async () => {
    if (!selectedMode) {
      setError("Choisissez d'abord Mode Serveur ou Mode Client.");
      return;
    }

    setIsBusy(true);
    setError(null);
    setMessage(null);
    setStoredSetupCompleted(false);

    try {
      if (selectedMode === "server") {
        const deploymentInspection = await syncConnectionApi.inspectDeploymentState().catch(() => null);
        const hasExistingServerConfig =
          deploymentInspection?.state === "SERVER_CONFIGURED" ||
          deploymentInspection?.state === "SERVER_RUNNING" ||
          deploymentInspection?.serverRuntimeConfigExists;

        if (hasExistingServerConfig) {
          if (!deploymentInspection?.serverRuntimeConfigValid) {
            throw new Error(
              "Configuration serveur existante invalide. Utilisez la reinitialisation explicite avant de reconfigurer ce poste.",
            );
          }
          if (deploymentInspection?.state === "SERVER_DATA_IMPORT_PENDING") {
            await runServerDataImport();
          } else {
            await runServerReadiness(true);
          }
        } else {
          try {
            await runServerReadiness(true);
          } catch (serverError) {
            await syncConnectionApi.stopLocalServer().catch(() => undefined);
            await runServerBootstrap();
            await runServerDataImport();
            if (serverError instanceof Error && serverError.message) {
              setMessage((current) => current || serverError.message);
            }
          }
        }
      } else {
        await runClientReadiness(serverUrl, true);
      }
    } catch (readinessError) {
      setIsReady(false);
      setError(formatReadinessError(readinessError));
    } finally {
      setIsBusy(false);
    }
  };

  useEffect(() => {
    if (!isTauri) {
      return;
    }

    setIsBusy(true);
    setError(null);

    void (async () => {
      try {
        const deploymentInspection = await syncConnectionApi.inspectDeploymentState().catch(() => null);
        const hasConfiguredServer =
          deploymentInspection?.state === "SERVER_DATA_IMPORT_PENDING" ||
          deploymentInspection?.state === "SERVER_CONFIGURED" ||
          deploymentInspection?.state === "SERVER_RUNNING";

        if (hasConfiguredServer && deploymentInspection?.connectionMode === "SERVER_PC") {
          const inspectedConnectionMode = "SERVER_PC";
          setSelectedConnectionMode(inspectedConnectionMode);
          setSelectedMode("server");
          setStoredOperationMode("server");
          setStoredConnectionMode(inspectedConnectionMode);
          if (deploymentInspection?.serverApiUrl) {
            setServerUrlState(deploymentInspection.serverApiUrl);
          }
          setReadinessItems(defaultItems("server"));
          if (!deploymentInspection?.serverRuntimeConfigValid) {
            throw new Error(
              "Configuration serveur existante invalide. Corrigez backend.env ou utilisez la reinitialisation explicite.",
            );
          }
          await refreshInspection().catch(() => undefined);
          if (deploymentInspection?.state === "SERVER_DATA_IMPORT_PENDING") {
            setStoredSetupCompleted(false);
            setIsReady(false);
          } else {
            await runServerReadiness(false, inspectedConnectionMode);
            setStoredSetupCompleted(true);
            setIsReady(true);
          }
          return;
        }

        const storedMode = readStoredOperationMode();
        const storedConnectionMode =
          readStoredConnectionMode() || deploymentInspection?.connectionMode || (storedMode === "server" ? "SERVER_PC" : "CLIENT");
        const effectiveMode = connectionModeToOperationMode(storedConnectionMode);
        if (!storedMode && !readStoredConnectionMode()) {
          setIsReady(false);
          return;
        }

        // A prior V2 build mapped SERVER to the local legacy transport. Require an
        // explicit remote URL instead of silently reusing that local configuration.
        if (storedConnectionMode === "SERVER" && storedMode === "server") {
          setSelectedConnectionMode(storedConnectionMode);
          setSelectedMode("client");
          setStoredSetupCompleted(false);
          setIsReady(false);
          return;
        }

        if (effectiveMode === "client" && !hasStoredServerUrl()) {
          setIsReady(false);
          return;
        }

        setSelectedConnectionMode(storedConnectionMode);
        setSelectedMode(effectiveMode);
        if (effectiveMode === "server") {
          setReadinessItems(defaultItems("server"));
          await refreshInspection().catch(() => undefined);
          await runServerReadiness(false, storedConnectionMode);
        } else {
          await runClientReadiness(getStoredServerUrl(), false, storedConnectionMode);
        }
        setStoredSetupCompleted(true);
        setIsReady(true);
      } catch (readinessError) {
        setStoredSetupCompleted(false);
        setIsReady(false);
        setError(
          readinessError instanceof Error ? readinessError.message : "Verification reseau impossible.",
        );
      } finally {
        setIsBusy(false);
      }
    })();
  }, [isTauri]);

  useEffect(() => {
    if (!isTauri || selectedMode !== "server") {
      return;
    }

    void refreshInspection().catch(() => undefined);
  }, [isTauri, selectedMode]);

  if (!showGate) {
    return <>{children}</>;
  }

  return (
    <div className="min-h-screen bg-[radial-gradient(circle_at_top,_rgba(0,133,163,0.16),_transparent_32%),linear-gradient(180deg,_#f8fbfd,_#eef4f7)] px-6 py-10 text-slate-950">
      <div className="mx-auto flex min-h-[calc(100vh-5rem)] max-w-7xl items-center">
        <div className="grid w-full gap-6 xl:grid-cols-[1.2fr,0.8fr]">
          <Card className="rounded-[2rem] border-slate-200/80 bg-white p-8">
            <div className="flex items-start justify-between gap-4">
              <div className="space-y-3">
                <Badge tone="reviewed">Infrastructure Reseau</Badge>
                <div>
                  <h1 className="text-3xl font-black tracking-tight text-slate-950">
                    Configuration initiale du poste
                  </h1>
                  <p className="mt-3 max-w-3xl text-sm leading-7 text-slate-600">
                    Choisissez le role de ce poste. Seul le poste serveur medical utilise le sidecar et PostgreSQL
                    locaux; les autres roles se connectent a une URL FastAPI configuree.
                  </p>
                </div>
                {pendingMode ? (
                  <div className="rounded-2xl border border-amber-200 bg-amber-50 px-4 py-4 text-sm text-amber-900">
                    <p className="font-semibold">
                      Confirmez le changement vers le mode {pendingMode === "CLIENT" ? "Client" : pendingMode === "SERVER" ? "Serveur central" : "Poste serveur medical"}.
                    </p>
                    <p className="mt-2">
                      Une configuration existante est deja presente. Le mode ne changera pas tant que vous ne l'aurez pas confirme explicitement.
                    </p>
                    <div className="mt-4 flex flex-wrap gap-3">
                      <Button type="button" size="sm" onClick={confirmModeSelection}>
                        Confirmer le changement
                      </Button>
                      <Button type="button" variant="secondary" size="sm" onClick={() => setPendingMode(null)}>
                        Annuler
                      </Button>
                    </div>
                  </div>
                ) : null}
              </div>
              <div className="rounded-3xl border border-sky-200 bg-sky-50 px-4 py-3 text-sm font-semibold text-sky-800">
                {isBusy
                  ? "Verification en cours"
                  : selectedConnectionMode === "SERVER_PC"
                    ? "Poste serveur medical"
                    : selectedConnectionMode === "SERVER"
                      ? "Serveur central distant"
                      : selectedConnectionMode === "CLIENT"
                        ? "Mode Client"
                        : "Configuration requise"}
              </div>
            </div>

            <div className="mt-8 grid gap-4 md:grid-cols-3">
              <button
                type="button"
                onClick={() => handleModeSelection("SERVER")}
                className={`rounded-[1.75rem] border px-5 py-5 text-left transition-all ${
                  selectedConnectionMode === "SERVER"
                    ? "border-[#0085A3]/40 bg-[#0085A3]/8 shadow-lg shadow-[#0085A3]/10"
                    : "border-slate-200 bg-slate-50/80 hover:border-slate-300 hover:bg-white"
                }`}
              >
                <div className="flex items-center gap-3">
                  <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-[#0085A3]/10 text-[#0085A3]">
                    <Server className="h-5 w-5" />
                  </div>
                  <div>
                    <p className="text-lg font-black text-slate-950">Serveur central</p>
                    <p className="mt-1 text-sm text-slate-600">
                      Ce poste se connecte au serveur FastAPI central configure, sans acces PostgreSQL direct.
                    </p>
                  </div>
                </div>
              </button>

              <button
                type="button"
                onClick={() => handleModeSelection("SERVER_PC")}
                className={`rounded-[1.75rem] border px-5 py-5 text-left transition-all ${
                  selectedConnectionMode === "SERVER_PC"
                    ? "border-[#0085A3]/40 bg-[#0085A3]/8 shadow-lg shadow-[#0085A3]/10"
                    : "border-slate-200 bg-slate-50/80 hover:border-slate-300 hover:bg-white"
                }`}
              >
                <div className="flex items-center gap-3">
                  <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-[#0085A3]/10 text-[#0085A3]">
                    <Server className="h-5 w-5" />
                  </div>
                  <div>
                    <p className="text-lg font-black text-slate-950">Poste serveur medical</p>
                    <p className="mt-1 text-sm text-slate-600">
                      Utilise PostgreSQL et FastAPI locaux pour les operations medicales, sans administration globale.
                    </p>
                  </div>
                </div>
              </button>

              <button
                type="button"
                onClick={() => handleModeSelection("CLIENT")}
                className={`rounded-[1.75rem] border px-5 py-5 text-left transition-all ${
                  selectedConnectionMode === "CLIENT"
                    ? "border-[#0085A3]/40 bg-[#0085A3]/8 shadow-lg shadow-[#0085A3]/10"
                    : "border-slate-200 bg-slate-50/80 hover:border-slate-300 hover:bg-white"
                }`}
              >
                <div className="flex items-center gap-3">
                  <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-[#0085A3]/10 text-[#0085A3]">
                    <LaptopMinimal className="h-5 w-5" />
                  </div>
                  <div>
                    <p className="text-lg font-black text-slate-950">Mode Client</p>
                    <p className="mt-1 text-sm text-slate-600">
                      Ce poste garde PostgreSQL local inutilise et se connecte seulement a l'URL FastAPI du serveur.
                    </p>
                  </div>
                </div>
              </button>
            </div>

            {selectedMode === "server" ? (
              <div className="mt-6 space-y-5">
                <div className="rounded-[1.7rem] border border-slate-200 bg-slate-50/70 p-5">
                  <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                    <div>
                      <div className="flex items-center gap-2 text-slate-500">
                        <Database className="h-4 w-4" />
                        <p className="text-xs font-black uppercase tracking-[0.16em]">Bootstrap PostgreSQL</p>
                      </div>
                      <p className="mt-3 text-sm leading-6 text-slate-600">
                        Chaque PC peut avoir PostgreSQL installe, mais seul ce poste serveur utilisera sa base locale.
                        La configuration cree un backend.env runtime protege et demarre FastAPI pour le LAN.
                      </p>
                    </div>

                    <div className="flex flex-wrap gap-2">
                      <Badge tone={postgresInspection?.installed ? "active" : "pending"}>
                        {postgresInspection?.installed ? "PostgreSQL detecte" : "Verification requise"}
                      </Badge>
                      <Badge
                        tone={
                          postgresInspection?.serviceStatus?.toLowerCase() === "running" || !postgresInspection?.serviceStatus
                            ? "completed"
                            : "failed"
                        }
                      >
                        {postgresInspection?.serviceStatus || "Service inconnu"}
                      </Badge>
                    </div>
                  </div>

                  <div className="mt-5 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
                    <div className="rounded-2xl border border-slate-200 bg-white px-4 py-4">
                      <p className="text-xs font-black uppercase tracking-[0.16em] text-slate-500">psql.exe</p>
                      <p className="mt-2 break-all text-sm font-semibold text-slate-900">
                        {postgresInspection?.psqlPath || "Non detecte"}
                      </p>
                    </div>
                    <div className="rounded-2xl border border-slate-200 bg-white px-4 py-4">
                      <p className="text-xs font-black uppercase tracking-[0.16em] text-slate-500">Service</p>
                      <p className="mt-2 text-sm font-semibold text-slate-900">
                        {postgresInspection?.serviceName || "Aucun service detecte"}
                      </p>
                    </div>
                    <div className="rounded-2xl border border-slate-200 bg-white px-4 py-4">
                      <p className="text-xs font-black uppercase tracking-[0.16em] text-slate-500">IP LAN</p>
                      <p className="mt-2 text-sm font-semibold text-slate-900">
                        {postgresInspection?.localIpAddress || desktopContext?.localIpAddress || "-"}
                      </p>
                    </div>
                    <div className="rounded-2xl border border-slate-200 bg-white px-4 py-4">
                      <p className="text-xs font-black uppercase tracking-[0.16em] text-slate-500">backend.env runtime</p>
                      <p className="mt-2 break-all text-sm font-semibold text-slate-900">
                        {postgresInspection?.runtimeConfigPath || "Local App Data"}
                      </p>
                    </div>
                  </div>

                  <div className="mt-5 grid gap-4 md:grid-cols-2">
                    <Input
                      label="Hote PostgreSQL"
                      value={bootstrapForm.host}
                      onChange={(event) => handleBootstrapFieldChange("host", event.target.value)}
                      placeholder="localhost"
                    />
                    <Input
                      label="Port PostgreSQL"
                      value={bootstrapForm.port}
                      onChange={(event) => handleBootstrapFieldChange("port", event.target.value)}
                      placeholder="5432"
                    />
                    <Input
                      label="Utilisateur administrateur"
                      value={bootstrapForm.adminUser}
                      onChange={(event) => handleBootstrapFieldChange("adminUser", event.target.value)}
                      placeholder="postgres"
                    />
                    <Input
                      type="password"
                      label="Mot de passe administrateur"
                      value={bootstrapForm.adminPassword}
                      onChange={(event) => handleBootstrapFieldChange("adminPassword", event.target.value)}
                      placeholder="Mot de passe PostgreSQL"
                    />
                    <Input
                      label="Nom de la base applicative"
                      value={bootstrapForm.appDatabase}
                      onChange={(event) => handleBootstrapFieldChange("appDatabase", event.target.value)}
                      placeholder="medical_folder"
                    />
                    <Input
                      label="Utilisateur applicatif"
                      value={bootstrapForm.appUser}
                      onChange={(event) => handleBootstrapFieldChange("appUser", event.target.value)}
                      placeholder="clinic_user"
                    />
                    <div className="md:col-span-2">
                      <Input
                        type="password"
                        label="Mot de passe utilisateur applicatif"
                        value={bootstrapForm.appUserPassword}
                        onChange={(event) => handleBootstrapFieldChange("appUserPassword", event.target.value)}
                        placeholder="Mot de passe securise pour le backend"
                      />
                    </div>
                    <Input
                      label="Hote d'ecoute FastAPI"
                      value={bootstrapForm.apiBindHost}
                      onChange={(event) => handleBootstrapFieldChange("apiBindHost", event.target.value)}
                      placeholder="0.0.0.0"
                    />
                    <Input
                      label="Port FastAPI"
                      value={bootstrapForm.apiPort}
                      onChange={(event) => handleBootstrapFieldChange("apiPort", event.target.value)}
                      placeholder="8000"
                    />
                  </div>

                  <div className="mt-5 rounded-2xl border border-slate-200 bg-white p-5">
                    <div className="flex items-center gap-2 text-slate-500">
                      <ShieldCheck className="h-4 w-4" />
                      <p className="text-xs font-black uppercase tracking-[0.16em]">Administrateur initial</p>
                    </div>
                    <p className="mt-2 text-sm text-slate-600">
                      Ce compte super administrateur est cree une seule fois pendant l'initialisation securisee du serveur.
                    </p>
                    <div className="mt-4 grid gap-4 md:grid-cols-2">
                      <Input
                        label="Prenom"
                        value={bootstrapForm.initialAdminFirstName}
                        onChange={(event) => handleBootstrapFieldChange("initialAdminFirstName", event.target.value)}
                        placeholder="Prenom"
                      />
                      <Input
                        label="Nom"
                        value={bootstrapForm.initialAdminLastName}
                        onChange={(event) => handleBootstrapFieldChange("initialAdminLastName", event.target.value)}
                        placeholder="Nom"
                      />
                      <Input
                        label="Email"
                        value={bootstrapForm.initialAdminEmail}
                        onChange={(event) => handleBootstrapFieldChange("initialAdminEmail", event.target.value)}
                        placeholder="admin@clinique.local"
                      />
                      <Input
                        label="Telephone facultatif"
                        value={bootstrapForm.initialAdminPhone}
                        onChange={(event) => handleBootstrapFieldChange("initialAdminPhone", event.target.value)}
                        placeholder="+213..."
                      />
                      <Input
                        type="password"
                        label="Mot de passe"
                        value={bootstrapForm.initialAdminPassword}
                        onChange={(event) => handleBootstrapFieldChange("initialAdminPassword", event.target.value)}
                        placeholder="Mot de passe robuste"
                      />
                      <Input
                        type="password"
                        label="Confirmation du mot de passe"
                        value={bootstrapForm.initialAdminPasswordConfirmation}
                        onChange={(event) => handleBootstrapFieldChange("initialAdminPasswordConfirmation", event.target.value)}
                        placeholder="Confirmation"
                      />
                      <div className="md:col-span-2">
                        <Input
                          label="Qualification facultative"
                          value={bootstrapForm.initialAdminQualification}
                          onChange={(event) => handleBootstrapFieldChange("initialAdminQualification", event.target.value)}
                          placeholder="Qualification"
                        />
                      </div>
                    </div>
                  </div>

                  <div className="mt-5 flex items-start gap-3 rounded-2xl border border-slate-200 bg-white px-4 py-4">
                    <input
                      id="open-firewall-port"
                      type="checkbox"
                      checked={bootstrapForm.openFirewall}
                      onChange={(event) => handleBootstrapFieldChange("openFirewall", event.target.checked)}
                      className="mt-1 h-4 w-4 rounded border-slate-300 text-[#0085A3] focus:ring-[#0085A3]/30"
                    />
                    <label htmlFor="open-firewall-port" className="text-sm text-slate-700">
                      Ajouter la regle Windows Firewall pour autoriser le port TCP {bootstrapForm.apiPort || "8000"} sur ce serveur.
                    </label>
                  </div>

                  {bootstrapResult ? (
                    <div className="mt-5 rounded-2xl border border-emerald-200 bg-emerald-50 px-4 py-4 text-sm text-emerald-800">
                      <div className="flex items-start gap-3">
                        <CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0" />
                        <div className="space-y-2">
                          <p className="font-semibold">{bootstrapResult.message}</p>
                          {bootstrapResult.details.map((detail) => (
                            <p key={detail}>{detail}</p>
                          ))}
                          {bootstrapResult.apiUrl ? <p>{`URL API finale: ${bootstrapResult.apiUrl}`}</p> : null}
                        </div>
                      </div>
                    </div>
                  ) : null}

                  {bootstrapResult ? (
                    <div className="mt-5 rounded-2xl border border-slate-200 bg-white p-5">
                      <div className="flex items-center gap-2 text-slate-500">
                        <Server className="h-4 w-4" />
                        <p className="text-xs font-black uppercase tracking-[0.16em]">Importation des donnees</p>
                      </div>
                      <p className="mt-2 text-sm text-slate-600">
                        Derniere etape du serveur. Choisissez soit les donnees initiales, soit la restauration d'une sauvegarde PostgreSQL existante.
                      </p>
                      <div className="mt-4 grid gap-3 md:grid-cols-2">
                        <button
                          type="button"
                          onClick={() => setDataImportMode("initial")}
                          className={`rounded-2xl border px-4 py-4 text-left ${dataImportMode === "initial" ? "border-[#0085A3] bg-[#0085A3]/5" : "border-slate-200 bg-slate-50"}`}
                        >
                          <p className="text-sm font-bold text-slate-950">Demarrer avec les donnees initiales</p>
                          <p className="mt-1 text-sm text-slate-600">Migrations, donnees obligatoires, demarrage du backend et verification finale.</p>
                        </button>
                        <button
                          type="button"
                          onClick={() => setDataImportMode("restore")}
                          className={`rounded-2xl border px-4 py-4 text-left ${dataImportMode === "restore" ? "border-[#0085A3] bg-[#0085A3]/5" : "border-slate-200 bg-slate-50"}`}
                        >
                          <p className="text-sm font-bold text-slate-950">Restaurer une sauvegarde existante</p>
                          <p className="mt-1 text-sm text-slate-600">Validation `pg_restore`, sauvegarde de securite, restauration et mise a niveau Alembic.</p>
                        </button>
                      </div>

                      {dataImportMode === "restore" ? (
                        <div className="mt-4 space-y-4 rounded-2xl border border-amber-200 bg-amber-50 p-4">
                          <p className="text-sm text-amber-900">
                            Attention: les donnees locales actuelles seront remplacees. Cette operation est reservee au Mode Serveur.
                          </p>
                          <div className="flex flex-wrap gap-3">
                            <Button variant="secondary" onClick={() => void handlePickRestoreBackup()}>
                              Choisir une sauvegarde
                            </Button>
                            {selectedBackupFile ? (
                              <div className="rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-700">
                                <p className="font-bold text-slate-950">{selectedBackupFile.filename}</p>
                                <p>{`${(selectedBackupFile.sizeBytes / (1024 * 1024)).toFixed(1)} Mo`}</p>
                              </div>
                            ) : null}
                          </div>
                          <Input
                            label='Tapez "RESTAURER LA SAUVEGARDE" pour confirmer'
                            value={restoreConfirmation}
                            onChange={(event) => setRestoreConfirmation(event.target.value)}
                            placeholder="RESTAURER LA SAUVEGARDE"
                          />
                        </div>
                      ) : null}

                      {finalizeResult ? (
                        <div className="mt-4 rounded-2xl border border-emerald-200 bg-emerald-50 px-4 py-4 text-sm text-emerald-800">
                          <p className="font-semibold">{finalizeResult.message}</p>
                          <p className="mt-1">{finalizeResult.detail}</p>
                        </div>
                      ) : null}
                    </div>
                  ) : null}

                  <div className="mt-5 flex flex-wrap gap-3">
                    <Button
                      variant="secondary"
                      onClick={() => void refreshInspection()}
                      loading={isInspecting}
                      icon={Database}
                    >
                      Verifier PostgreSQL
                    </Button>
                    <div className="rounded-2xl border border-slate-200 bg-slate-50/80 px-4 py-3 text-sm text-slate-600">
                      PostgreSQL doit etre installe separement sur chaque poste. En Mode Client, il reste simplement
                      inutilise par l'application.
                    </div>
                  </div>
                </div>
              </div>
            ) : selectedMode === "client" ? (
              <div className="mt-6 rounded-[1.6rem] border border-slate-200 bg-slate-50/70 p-5">
                <Input
                  label={remoteServerLabel}
                  placeholder="http://192.168.0.136:8000"
                  value={serverUrl}
                  onChange={(event) => handleServerUrlChange(event.target.value)}
                  error={error && !serverUrl.trim() ? error : null}
                />
                <p className="mt-3 text-sm text-slate-500">
                  {selectedConnectionMode === "SERVER"
                    ? "Ce poste utilise le serveur FastAPI central configure. PostgreSQL reste derriere FastAPI et n'est jamais contacte directement."
                    : "Ce poste utilisera le serveur FastAPI selectionne. La base PostgreSQL installee localement ne sera pas utilisee dans ce mode. N'utilisez jamais l'URL Vite `:5173` ni PostgreSQL directement."}
                </p>
              </div>
            ) : null}

            {message ? (
              <div className="mt-6 flex items-start gap-3 rounded-[1.4rem] border border-emerald-200 bg-emerald-50 px-4 py-4 text-sm text-emerald-800">
                <CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0" />
                <p className="font-medium">{message}</p>
              </div>
            ) : null}

            {error ? (
              <div className="mt-6 flex items-start gap-3 rounded-[1.4rem] border border-rose-200 bg-rose-50 px-4 py-4 text-sm text-rose-800">
                <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0" />
                <p className="font-medium">{error}</p>
              </div>
            ) : null}

            <div className="mt-8 flex flex-wrap gap-3">
              <Button
                onClick={() => void handleContinue()}
                loading={isBusy}
                icon={isLocalServerPc ? Server : Globe}
                className="min-w-[260px]"
              >
                {isLocalServerPc
                  ? bootstrapResult
                    ? "Terminer et ouvrir l'application"
                    : "Configurer PostgreSQL et preparer le poste serveur"
                  : selectedConnectionMode === "SERVER"
                    ? "Valider le serveur central"
                    : "Valider la connexion client"}
              </Button>
              {selectedMode ? (
                <Button
                  variant="secondary"
                  onClick={() => {
                    setStoredSetupCompleted(false);
                    setIsReady(false);
                    setError(null);
                    setMessage(null);
                    setBootstrapResult(null);
                    setReadinessItems(defaultItems(selectedMode));
                  }}
                >
                  Reinitialiser l'etape
                </Button>
              ) : null}
            </div>
          </Card>

          <Card className="rounded-[2rem] border-slate-200/80 bg-white p-8">
            <div className="flex items-start gap-3">
              <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-[#0085A3]/10 text-[#0085A3]">
                <ShieldCheck className="h-5 w-5" />
              </div>
              <div>
                <h2 className="text-xl font-black text-slate-950">Checklist de readiness</h2>
                <p className="mt-2 text-sm leading-6 text-slate-500">
                  Le deploiement bloque tant que les verifications critiques ne sont pas reussies sur ce poste.
                </p>
              </div>
            </div>

            <div className="mt-6 space-y-3">
              {readinessItems.map((item) => (
                <div key={item.id} className="rounded-[1.4rem] border border-slate-200 bg-slate-50/70 px-4 py-4">
                  <div className="flex items-center justify-between gap-3">
                    <div className="flex items-center gap-3">
                      {item.id === "postgres" || item.id === "config" || item.id === "migration" ? (
                        <Database className="h-4 w-4 text-slate-500" />
                      ) : item.id === "network" ? (
                        <Network className="h-4 w-4 text-slate-500" />
                      ) : item.id === "service" ? (
                        <KeyRound className="h-4 w-4 text-slate-500" />
                      ) : item.id === "server-url" || item.id === "health" ? (
                        <Globe className="h-4 w-4 text-slate-500" />
                      ) : item.id === "mode" ? (
                        <LaptopMinimal className="h-4 w-4 text-slate-500" />
                      ) : (
                        <Server className="h-4 w-4 text-slate-500" />
                      )}
                      <p className="text-sm font-bold text-slate-900">{item.label}</p>
                    </div>
                    <Badge tone={mapItemTone(item.status)}>
                      {item.status === "ok" ? "Pret" : item.status === "failed" ? "Echec" : "En attente"}
                    </Badge>
                  </div>
                  <p className="mt-2 text-sm text-slate-600">{item.detail}</p>
                </div>
              ))}
            </div>

            {selectedMode === "server" ? (
              <div className="mt-6 rounded-[1.5rem] border border-slate-200 bg-slate-50/70 px-4 py-4 text-sm text-slate-700">
                <p className="font-bold text-slate-900">Architecture attendue</p>
                <div className="mt-3 space-y-2">
                  <p>Ce PC comme Serveur: FastAPI + PostgreSQL local actif.</p>
                  <p>Autres PCs: Mode Client, PostgreSQL local inutilise, connexion uniquement a FastAPI.</p>
                  <p>URL clients attendue: {bootstrapResult?.apiUrl || desktopContext?.serverApiUrl || "http://LAN_IP:8000"}</p>
                </div>
              </div>
            ) : null}

            {desktopContext ? (
              <div className="mt-6 rounded-[1.5rem] border border-slate-200 bg-slate-50/70 px-4 py-4 text-sm text-slate-700">
                <p className="font-bold text-slate-900">Contexte desktop</p>
                <div className="mt-3 space-y-2">
                  <p>Mode: {desktopContext.operationMode}</p>
                  <p>Statut backend: {desktopContext.backendStatus}</p>
                  <p>URL serveur: {desktopContext.serverApiUrl || "-"}</p>
                  <p>IP locale: {desktopContext.localIpAddress || "-"}</p>
                </div>
              </div>
            ) : null}

            {(isBusy || isInspecting) && !message ? (
              <div className="mt-6 flex items-center gap-3 rounded-[1.5rem] border border-sky-200 bg-sky-50 px-4 py-4 text-sm text-sky-800">
                <LoaderCircle className="h-4 w-4 animate-spin" />
                <p className="font-medium">Preparation de l'infrastructure en cours...</p>
              </div>
            ) : null}
          </Card>
        </div>
      </div>
    </div>
  );
};
