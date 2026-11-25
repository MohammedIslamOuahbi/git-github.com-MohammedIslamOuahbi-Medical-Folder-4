import type {
  BackupRecord,
  CentralProvisioningStage,
  InstallationErrorCode,
  InstallationProfileCode,
  InstallationProfilePayload,
  InstallationStatusCheck,
  InstallationStatusPayload,
  MissionSubmissionRecord,
  RegisteredDeviceRecord,
} from "@/types/installation";
import type { CentralServerInfo } from "@/types/centralSync";

export type CentralWizardStepId =
  | "welcome"
  | "postgres"
  | "database"
  | "identity"
  | "network"
  | "admin"
  | "backup"
  | "verification";

export interface CentralIdentityDraft {
  serverName: string;
  serverCode: string;
  description: string;
  apiPort: string;
}

export interface CentralAdminDraft {
  firstName: string;
  lastName: string;
  email: string;
  password: string;
  confirmation: string;
}

export interface CentralBackupDraft {
  directory: string;
  retentionPolicy: string;
}

export interface CentralWizardDraft {
  identity: CentralIdentityDraft;
  admin: CentralAdminDraft;
  backup: CentralBackupDraft;
}

export interface CentralWizardStep {
  id: CentralWizardStepId;
  title: string;
  description: string;
}

export interface CentralDashboardSnapshot {
  identityLabel: string;
  centralSequence: string;
  registeredDevices: number;
  pendingSubmissions: number;
  conflicts: number;
  latestBackups: number;
  health: string;
  schemaRevision: string;
  syncProtocolVersion: string;
}

export type CentralRestrictionDecision =
  | { allowed: true }
  | { allowed: false; redirectTo: string; message: string };

export const CENTRAL_WIZARD_STEPS: CentralWizardStep[] = [
  {
    id: "welcome",
    title: "Installation du serveur central Ibn Sina",
    description: "Ce serveur conserve la version finale des données et reçoit les missions des postes mobiles.",
  },
  { id: "postgres", title: "PostgreSQL readiness", description: "Vérification de l'environnement PostgreSQL local." },
  { id: "database", title: "Base centrale", description: "Suivi des étapes de provisionnement réel de la base centrale." },
  { id: "identity", title: "Identité du serveur", description: "Identification du serveur central et configuration du port API." },
  { id: "network", title: "Réseau", description: "Validation de l'adresse LAN, de l'API et du pare-feu." },
  { id: "admin", title: "Super administrateur", description: "Création du premier compte d'administration." },
  { id: "backup", title: "Sauvegarde", description: "Configuration des sauvegardes automatiques du serveur central." },
  { id: "verification", title: "Vérification finale", description: "Validation finale avant l'ouverture opérationnelle." },
];

export const MOBILE_RUNTIME_LABELS = ["Mode autonome", "Serveur de mission", "Client de mission"];

export const MOBILE_RESTRICTED_ROUTES = [
  "/sync/mission",
  "/sync/connection",
  "/app/workspace",
];

export const CENTRAL_HOME_ROUTE = "/app/infrastructure/central";

export const defaultCentralWizardDraft = (status?: InstallationStatusPayload | null): CentralWizardDraft => ({
  identity: {
    serverName: status?.identity.server_name || "Serveur central Ibn Sina",
    serverCode: status?.identity.server_code || "CENTRAL-SERVER",
    description: status?.identity.description || "",
    apiPort: String(status?.identity.api_port || 8000),
  },
  admin: {
    firstName: "",
    lastName: "",
    email: "",
    password: "",
    confirmation: "",
  },
  backup: {
    directory: status?.backup_directory || "",
    retentionPolicy: status?.retention_policy || "30 jours",
  },
});

export const isCentralProfile = (profile: InstallationProfileCode | null | undefined) => profile === "central_server";

export const detectProfileMismatch = (
  backendProfile: InstallationProfileCode | null | undefined,
  packagedProfile: InstallationProfileCode | null | undefined,
): InstallationErrorCode | null => {
  if (!backendProfile || !packagedProfile) {
    return null;
  }
  return backendProfile !== packagedProfile ? "INSTALLATION_PROFILE_MISMATCH" : null;
};

export const shouldHideMobileModeSelection = (profilePayload: InstallationProfilePayload | null | undefined) =>
  isCentralProfile(profilePayload?.profile);

export const getCentralSetupEntry = ({
  profile,
  provisioningStatus,
}: {
  profile: InstallationProfileCode | null | undefined;
  provisioningStatus: string | null | undefined;
}) => isCentralProfile(profile) && provisioningStatus !== "configured";

export const normalizeProvisioningStages = (stages: CentralProvisioningStage[] | null | undefined) =>
  stages && stages.length > 0
    ? stages
    : [
        { key: "database", label: "Création de la base", status: "pending", detail: null },
        { key: "role", label: "Création du rôle applicatif", status: "pending", detail: null },
        { key: "permissions", label: "Configuration des permissions", status: "pending", detail: null },
        { key: "migrations", label: "Application des migrations", status: "pending", detail: null },
        { key: "sequence", label: "Initialisation de la séquence centrale", status: "pending", detail: null },
      ];

export const normalizeReadinessChecks = (checks: InstallationStatusCheck[] | null | undefined) =>
  checks && checks.length > 0
    ? checks
    : [
        { key: "postgres_service", label: "Service PostgreSQL", status: "pending", detail: null },
        { key: "local_connection", label: "Connexion locale", status: "pending", detail: null },
        { key: "central_database", label: "Base centrale", status: "pending", detail: null },
        { key: "app_user", label: "Utilisateur applicatif", status: "pending", detail: null },
        { key: "schema_permissions", label: "Permissions du schéma", status: "pending", detail: null },
      ];

export const validateSuperAdminDraft = (draft: CentralAdminDraft) => {
  const errors: Partial<Record<keyof CentralAdminDraft, string>> = {};
  if (!draft.firstName.trim()) errors.firstName = "Le prénom est requis.";
  if (!draft.lastName.trim()) errors.lastName = "Le nom est requis.";
  if (!draft.email.trim() || !draft.email.includes("@")) errors.email = "Une adresse e-mail valide est requise.";
  if (draft.password.length < 8) errors.password = "Le mot de passe doit contenir au moins 8 caractères.";
  if (draft.confirmation !== draft.password) errors.confirmation = "La confirmation doit correspondre au mot de passe.";
  return errors;
};

export const validateBackupDraft = (draft: CentralBackupDraft) => {
  if (!draft.directory.trim()) {
    return { directory: "Le dossier de sauvegarde est requis." };
  }
  return {};
};

export const buildFinalVerificationItems = (status: InstallationStatusPayload | null | undefined) => [
  { label: "PostgreSQL opérationnel", passed: Boolean(status?.postgres_ready) },
  { label: "Base centrale opérationnelle", passed: Boolean(status?.central_database_ready) },
  { label: "Migrations à jour", passed: Boolean(status?.migrations_up_to_date) },
  { label: "Serveur FastAPI opérationnel", passed: Boolean(status?.fastapi_ready) },
  { label: "Administrateur créé", passed: Boolean(status?.admin_created) },
  { label: "Sauvegarde configurée", passed: Boolean(status?.backup_configured) },
];

export const buildCentralDashboardSnapshot = ({
  status,
  serverInfo,
  devices,
  submissions,
  backups,
}: {
  status: InstallationStatusPayload | null | undefined;
  serverInfo: CentralServerInfo | null | undefined;
  devices: RegisteredDeviceRecord[];
  submissions: MissionSubmissionRecord[];
  backups: BackupRecord[];
}): CentralDashboardSnapshot => ({
  identityLabel: status?.identity.server_code || status?.identity.server_name || "CENTRAL-SERVER",
  centralSequence: String(serverInfo?.current_central_sequence ?? status?.central_sequence ?? 0),
  registeredDevices: devices.length,
  pendingSubmissions: submissions.filter((item) => item.status === "En attente" || item.status === "En cours").length,
  conflicts: submissions.reduce((total, item) => total + item.conflicts, 0),
  latestBackups: backups.length,
  health: status?.fastapi_ready ? "Opérationnel" : "Vérification requise",
  schemaRevision: serverInfo?.schema_revision || status?.schema_revision || "-",
  syncProtocolVersion: serverInfo?.protocol_version || status?.sync_protocol_version || "-",
});

export const getCentralRestrictionDecision = (
  pathname: string,
  profile: InstallationProfileCode | null | undefined,
): CentralRestrictionDecision => {
  if (!isCentralProfile(profile)) {
    return { allowed: true };
  }
  const restricted = MOBILE_RESTRICTED_ROUTES.some((route) => pathname.startsWith(route));
  if (!restricted) {
    return { allowed: true };
  }
  return {
    allowed: false,
    redirectTo: CENTRAL_HOME_ROUTE,
    message: "Ce poste est configuré comme serveur central. Les fonctions mobiles et mission sont indisponibles.",
  };
};
