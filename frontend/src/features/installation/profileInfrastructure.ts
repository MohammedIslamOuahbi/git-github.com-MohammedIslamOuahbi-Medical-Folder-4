import type { AuthUser } from "../../types/auth";
import type {
  InstallationErrorCode,
  InstallationProfileCapabilities,
  InstallationProfileCode,
  InstallationProfilePayload,
  InstallationProfileSource,
  InstallationProvisioningStatus,
  InstallationStatusPayload,
  InstallationWarning,
} from "../../types/installation";
import {
  canDisplayNavigationItem,
  filterNavigationItems,
  flattenNavigationItems,
  getFallbackCapabilities,
  SIDEBAR_NAVIGATION,
} from "./sidebarNavigation.js";

export type InstallationProfile = InstallationProfileCode;

export interface ResolvedInstallationProfile {
  profile: InstallationProfile | null;
  source: InstallationProfileSource;
}

export interface InstallationProfileContextState {
  profile: InstallationProfile | null;
  capabilities: InstallationProfileCapabilities;
  provisioningStatus: InstallationProvisioningStatus | string;
  deviceIdentity: {
    uuid: string | null;
    code: string | null;
    name: string | null;
    centralUuid: string | null;
  };
  loading: boolean;
  error: string | null;
}

export interface ProductIdentity {
  packageLabel: string;
  productTitle: string;
  buildId: string;
  installerIdentifier: string;
}

export interface NavigationItem {
  label: string;
  path: string;
  capability?: keyof InstallationProfileCapabilities;
}

export interface DiagnosticsSnapshot {
  installationProfile: string | null;
  provisioningState: string;
  sidecarPath: string | null;
  backendStatus: string;
  backendEnvPath: string | null;
  databaseHost: string | null;
  databaseName: string | null;
  port: string | null;
  health: string | null;
  logPaths: string[];
  migrationRevision: string | null;
  firewallStatus: string | null;
  backupPath: string | null;
}

export interface RecoveryAction {
  key: string;
  label: string;
  description: string;
  destructive?: boolean;
}

export interface CapabilityAccessDecision {
  allowed: boolean;
  reason: "ok" | "missing_profile" | "missing_capability" | "missing_permission";
  redirectTo: string;
}

const ALL_CAPABILITIES: InstallationProfileCapabilities = getFallbackCapabilities();

const CONFIGURED_STATUSES = new Set<string>(["configured"]);

const FIRST_RUN_STATUSES = new Set<string>([
  "unconfigured",
  "checking_prerequisites",
  "postgresql_missing",
  "postgresql_ready",
  "database_creating",
  "database_ready",
  "migrations_running",
  "identity_creating",
  "admin_setup_required",
  "central_configuration_required",
  "mobile_device_configuration_required",
  "bootstrap_required",
  "bootstrap_running",
  "provisioning",
  "failed",
  "reset_required",
]);

const isCentralProfile = (profile: InstallationProfile | null | undefined) => profile === "central_server";

export const resolveEffectiveProfile = ({
  backendProfile,
  lastKnownGoodProfile,
  packagedProfile,
}: {
  backendProfile: InstallationProfile | null;
  lastKnownGoodProfile: InstallationProfile | null;
  packagedProfile: InstallationProfile | null;
}): ResolvedInstallationProfile => {
  if (backendProfile) {
    return { profile: backendProfile, source: "backend" };
  }
  if (lastKnownGoodProfile) {
    return { profile: lastKnownGoodProfile, source: "last_known_good" };
  }
  if (packagedProfile) {
    return { profile: packagedProfile, source: "packaged" };
  }
  return { profile: null, source: "none" };
};

export const createBackendUnavailableWarning = (): InstallationWarning => ({
  code: "INSTALLATION_PROFILE_BACKEND_UNAVAILABLE",
  message: "Le profil local temporaire est utilise car le backend local ne repond pas.",
});

export const deriveInstallationCapabilities = (
  payload: InstallationProfilePayload | null | undefined,
): InstallationProfileCapabilities => ({
  ...ALL_CAPABILITIES,
  ...(payload?.capabilities || {}),
});

export const deriveDeviceIdentity = (
  payload: InstallationProfilePayload | null | undefined,
  status: InstallationStatusPayload | null | undefined,
) => ({
  uuid: payload?.device?.uuid || status?.server_uuid || null,
  code: payload?.device?.code || status?.identity.server_code || null,
  name: payload?.device?.name || status?.identity.server_name || null,
  centralUuid: status?.server_uuid || payload?.central_server_uuid || null,
});

export const createInstallationProfileState = ({
  payload,
  status,
  loading,
  error,
}: {
  payload: InstallationProfilePayload | null | undefined;
  status: InstallationStatusPayload | null | undefined;
  loading: boolean;
  error: string | null;
}): InstallationProfileContextState => ({
  profile: payload?.profile || status?.profile || null,
  capabilities: deriveInstallationCapabilities(payload),
  provisioningStatus: status?.provisioning_status || payload?.provisioning_status || "unconfigured",
  deviceIdentity: deriveDeviceIdentity(payload, status),
  loading,
  error,
});

export const getProductIdentity = ({
  profile,
  version,
  buildId,
  installerIdentifier,
}: {
  profile: InstallationProfile | null;
  version: string;
  buildId: string | null;
  installerIdentifier: string | null;
}): ProductIdentity => {
  if (profile === "central_server") {
    return {
      packageLabel: "Central Server",
      productTitle: "Ibn Sina - Serveur central",
      buildId: buildId || `${version}+central.local`,
      installerIdentifier: installerIdentifier || "com.ibnsina.medicalclinic.central",
    };
  }
  return {
    packageLabel: "Mobile Device",
    productTitle: "Ibn Sina - Poste mobile",
    buildId: buildId || `${version}+mobile.local`,
    installerIdentifier: installerIdentifier || "com.ibnsina.medicalclinic.mobile",
  };
};

export const buildAboutPanel = ({
  profile,
  status,
  deviceIdentity,
  productIdentity,
}: {
  profile: InstallationProfile | null;
  status: InstallationStatusPayload | null | undefined;
  deviceIdentity: InstallationProfileContextState["deviceIdentity"];
  productIdentity: ProductIdentity;
}) => [
  ["Profil produit", profile === "central_server" ? "Serveur central" : "Poste mobile"],
  ["Version application", status?.app_version || "-"],
  ["Revision du schema", status?.schema_revision || "-"],
  ["Version du protocole", status?.sync_protocol_version || "-"],
  ["UUID appareil", deviceIdentity.uuid || "-"],
  ["UUID central", profile === "central_server" ? status?.server_uuid || "-" : status?.server_uuid || "Sans objet"],
  ["Build installateur", productIdentity.buildId],
  ["Package", productIdentity.packageLabel],
] as const;

export const buildProfileNavigation = (
  profile: InstallationProfile | null,
  capabilities: InstallationProfileCapabilities | null,
) =>
  flattenNavigationItems(
    filterNavigationItems(SIDEBAR_NAVIGATION, {
      profile,
      packagedProfile: profile,
      backendProfile: profile,
      capabilities,
      profileStatus: profile ? "ready" : "error",
      mismatchError: null,
      currentUser: {
        role: "Admin",
        permissions: ["users.view", "reports.view", "medical_campaigns.view", "settings.view"],
      } as AuthUser,
    }),
  ).map((item) => ({
    label: item.label,
    path: item.route,
    capability: item.requiredCapabilities?.[0],
  }));

export const evaluateCapabilityAccess = ({
  profile,
  capabilities,
  user,
  requiredProfile,
  requiredCapability,
  requiredPermissions,
  requiredRoles,
  accessMode,
}: {
  profile: InstallationProfile | null;
  capabilities: InstallationProfileCapabilities | null;
  user: AuthUser | null;
  requiredProfile?: InstallationProfile;
  requiredCapability?: keyof InstallationProfileCapabilities;
  requiredPermissions?: string[];
  requiredRoles?: Array<AuthUser["role"]>;
  accessMode?: "all" | "any";
}): CapabilityAccessDecision => {
  const redirectTo = isCentralProfile(profile) ? "/app/infrastructure/central" : "/app/infrastructure/mobile";
  const access = canDisplayNavigationItem(
    {
      id: "route-guard",
      label: "Route guard",
      route: redirectTo,
      icon: SIDEBAR_NAVIGATION[0]!.icon,
      profiles: requiredProfile ? [requiredProfile] : undefined,
      requiredCapabilities: requiredCapability ? [requiredCapability] : undefined,
      requiredPermissions,
      roles: requiredRoles,
      accessMode,
    },
    {
      profile,
      packagedProfile: profile,
      backendProfile: profile,
      capabilities,
      profileStatus: profile ? "ready" : "error",
      mismatchError: null,
      currentUser: user,
    },
  );

  if (access.allowed) {
    return { allowed: true, reason: "ok", redirectTo };
  }

  return {
    allowed: false,
    reason:
      access.reason === "capability"
        ? "missing_capability"
        : access.reason === "profile"
          ? "missing_profile"
          : "missing_permission",
    redirectTo,
  };
};

export const buildUpgradeSteps = () => [
  "Sauvegarde de securite",
  "Arret du backend",
  "Application des migrations",
  "Redemarrage",
  "Verification",
] as const;

export const getUpgradeTitle = (profile: InstallationProfile | null) =>
  isCentralProfile(profile) ? "Mise a jour du serveur central" : "Mise a jour du poste mobile";

export const getUpgradeMessage = (mismatchError: InstallationErrorCode | null) =>
  mismatchError === "INSTALLATION_PROFILE_MISMATCH"
    ? "Ce programme d'installation ne correspond pas au type de cette installation."
    : null;

export const redactDiagnosticEntries = (snapshot: DiagnosticsSnapshot) => ({
  ...snapshot,
  databaseHost: redactDiagnosticValue("database_host", snapshot.databaseHost),
  databaseName: redactDiagnosticValue("database_name", snapshot.databaseName),
  sidecarPath: redactDiagnosticValue("sidecar_path", snapshot.sidecarPath),
  backendEnvPath: redactDiagnosticValue("backend_env_path", snapshot.backendEnvPath),
  backupPath: redactDiagnosticValue("backup_path", snapshot.backupPath),
});

export const redactDiagnosticValue = (key: string, value: string | null) => {
  if (!value) {
    return value;
  }
  const lowered = key.toLowerCase();
  if (lowered.includes("password") || lowered.includes("secret") || lowered.includes("token")) {
    return "[redacted]";
  }
  return value.replace(/(postgresql:\/\/[^:]+:)([^@]+)(@)/i, "$1[redacted]$3");
};

export const buildDiagnosticsSnapshot = ({
  profile,
  status,
  sidecarPath,
  backendEnvPath,
  databaseHost,
  databaseName,
  port,
  health,
  logPaths,
  migrationRevision,
}: {
  profile: InstallationProfile | null;
  status: InstallationStatusPayload | null | undefined;
  sidecarPath: string | null;
  backendEnvPath: string | null;
  databaseHost: string | null;
  databaseName: string | null;
  port: string | null;
  health: string | null;
  logPaths: string[];
  migrationRevision: string | null;
}): DiagnosticsSnapshot => ({
  installationProfile: profile,
  provisioningState: status?.provisioning_status || "unconfigured",
  sidecarPath,
  backendStatus: status?.fastapi_ready ? "running" : "stopped",
  backendEnvPath,
  databaseHost,
  databaseName,
  port,
  health,
  logPaths,
  migrationRevision,
  firewallStatus: status?.network.firewall_status || null,
  backupPath: status?.backup_directory || null,
});

export const buildRecoveryActions = (
  profile: InstallationProfile | null,
  provisioningStatus: string,
): RecoveryAction[] => {
  if (isCentralProfile(profile)) {
    return [
      { key: "retry_postgres", label: "Retry PostgreSQL provisioning", description: "Relancer la verification et le provisionnement PostgreSQL." },
      { key: "retry_migrations", label: "Retry migrations", description: "Reprendre l'application des migrations interrompues." },
      { key: "resume_admin", label: "Resume admin setup", description: "Rouvrir l'etape de creation du super administrateur." },
      { key: "open_logs", label: "Open logs", description: "Afficher les journaux techniques de provisionnement." },
      { key: "restore_backup", label: "Restore safety backup", description: "Restaurer la derniere sauvegarde de securite en cas d'echec critique.", destructive: true },
    ];
  }

  return [
    { key: "retry_local", label: "Retry local provisioning", description: "Relancer le provisionnement PostgreSQL local et les migrations." },
    { key: "retry_central", label: "Retry central connection", description: "Retester la connexion au serveur central configure." },
    { key: "resume_bootstrap", label: "Resume bootstrap", description: "Reprendre le bootstrap a partir de l'etat courant." },
    { key: "reset_runtime", label: "Reset runtime mode safely", description: "Revenir en mode sur sans effacer la base locale." },
    { key: "open_logs", label: "Open logs", description: "Afficher les journaux techniques de bootstrap et de synchronisation." },
  ].filter(() => provisioningStatus !== "configured" || true);
};

export const isFirstRunRequired = (provisioningStatus: string | null | undefined) =>
  provisioningStatus ? FIRST_RUN_STATUSES.has(provisioningStatus) && !CONFIGURED_STATUSES.has(provisioningStatus) : true;

export const shouldSkipFirstRun = (provisioningStatus: string | null | undefined) =>
  Boolean(provisioningStatus && CONFIGURED_STATUSES.has(provisioningStatus));
