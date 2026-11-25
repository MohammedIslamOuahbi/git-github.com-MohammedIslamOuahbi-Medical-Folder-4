import {
  CENTRAL_HOME_ROUTE,
  MOBILE_RUNTIME_LABELS,
  detectProfileMismatch,
  isCentralProfile,
} from "../central/centralServerFlow.js";
import type {
  DeviceRegistrationResponse,
  InstallationProfileCode,
  InstallationProfilePayload,
  InstallationStatusCheck,
  InstallationStatusPayload,
  MobileProvisionResponse,
} from "@/types/installation";
import type { CentralBootstrapManifest } from "@/types/centralSync";

export type MobileWizardStepId =
  | "welcome"
  | "postgres"
  | "identity"
  | "connection"
  | "registration"
  | "readiness"
  | "bootstrap"
  | "completion";

export interface MobileIdentityDraft {
  deviceName: string;
  deviceCode: string;
  description: string;
}

export interface MobileConnectionDraft {
  centralServerUrl: string;
}

export interface MobileWizardDraft {
  identity: MobileIdentityDraft;
  connection: MobileConnectionDraft;
}

export const MOBILE_HOME_ROUTE = "/app/infrastructure/mobile";

export const MOBILE_WIZARD_STEPS: Array<{ id: MobileWizardStepId; title: string }> = [
  { id: "welcome", title: "Configuration du poste mobile" },
  { id: "postgres", title: "PostgreSQL local" },
  { id: "identity", title: "Identité de l’appareil" },
  { id: "connection", title: "Connexion au serveur central" },
  { id: "registration", title: "Enregistrement" },
  { id: "readiness", title: "Bootstrap readiness" },
  { id: "bootstrap", title: "Bootstrap progress" },
  { id: "completion", title: "Choisir le mode de fonctionnement" },
];

export const defaultMobileWizardDraft = (status?: InstallationStatusPayload | null): MobileWizardDraft => ({
  identity: {
    deviceName: status?.identity.server_name || "PC Médecin 01",
    deviceCode: status?.identity.server_code || "PC-01",
    description: status?.identity.description || "",
  },
  connection: {
    centralServerUrl: status?.network.api_url || "http://192.168.1.5:8000",
  },
});

export const isMobileProfile = (profile: InstallationProfileCode | null | undefined) => profile === "mobile_device";

export const shouldHideCentralSetup = (payload: InstallationProfilePayload | null | undefined) =>
  isMobileProfile(payload?.profile);

export const shouldShowMobileProvisioning = ({
  profile,
  provisioningStatus,
}: {
  profile: InstallationProfileCode | null | undefined;
  provisioningStatus: string | null | undefined;
}) => isMobileProfile(profile) && provisioningStatus !== "configured";

export const normalizeMobilePostgresChecks = (checks: InstallationStatusCheck[] | null | undefined) =>
  checks && checks.length > 0
    ? checks
    : [
        { key: "postgres_service", label: "Service PostgreSQL", status: "pending", detail: null },
        { key: "local_database", label: "Base locale", status: "pending", detail: null },
        { key: "app_user", label: "Utilisateur applicatif", status: "pending", detail: null },
        { key: "migrations", label: "Migrations", status: "pending", detail: null },
        { key: "disk", label: "Espace disque", status: "pending", detail: null },
      ];

export const buildBootstrapReadiness = (status: InstallationStatusPayload | null | undefined) => [
  { label: "Base locale vide ou sûre", passed: Boolean(status?.central_database_ready || status?.provisioning_status !== "configured") },
  { label: "Aucune modification locale non envoyée", passed: true },
  { label: "Espace disque suffisant", passed: Boolean(status?.available_disk_space) },
  { label: "Schéma compatible", passed: Boolean(status?.migrations_up_to_date) },
  { label: "Serveur central reconnu", passed: Boolean(status?.network.api_url) },
];

export const MOBILE_BOOTSTRAP_STAGES = [
  "Création de la sauvegarde locale",
  "Téléchargement du manifeste",
  "Téléchargement de l’instantané",
  "Validation du checksum",
  "Restauration temporaire",
  "Vérification des UUID",
  "Vérification des relations",
  "Activation de la base locale",
  "Téléchargement des changements récents",
] as const;

export const validateMobileIdentityDraft = (draft: MobileIdentityDraft) => {
  const errors: Partial<Record<keyof MobileIdentityDraft, string>> = {};
  if (!draft.deviceName.trim()) errors.deviceName = "Le nom de l’appareil est requis.";
  if (!draft.deviceCode.trim()) errors.deviceCode = "Le code de l’appareil est requis.";
  return errors;
};

export const validateCentralConnectionUrl = (value: string) => {
  if (!value.trim()) {
    return "L’adresse du serveur central est requise.";
  }
  if (!/^https?:\/\//i.test(value.trim())) {
    return "L’adresse doit commencer par http:// ou https://";
  }
  return null;
};

export const buildMobileRegistrationSummary = ({
  draft,
  serverName,
  registration,
}: {
  draft: MobileWizardDraft;
  serverName: string | null | undefined;
  registration: DeviceRegistrationResponse | null;
}) => ({
  deviceName: draft.identity.deviceName,
  code: draft.identity.deviceCode,
  centralServer: serverName || "Serveur central",
  authorized: Boolean(registration?.device_uuid),
});

export const buildBootstrapStageStates = ({
  manifest,
  checksumFailed,
  interrupted,
}: {
  manifest: CentralBootstrapManifest | null;
  checksumFailed: boolean;
  interrupted: boolean;
}) =>
  Object.fromEntries(
    MOBILE_BOOTSTRAP_STAGES.map((stage) => {
      if (interrupted) return [stage, "failed"];
      if (stage === "Validation du checksum" && checksumFailed) return [stage, "failed"];
      if (manifest && stage === "Téléchargement du manifeste") return [stage, "completed"];
      return [stage, "pending"];
    }),
  ) as Record<(typeof MOBILE_BOOTSTRAP_STAGES)[number], "pending" | "completed" | "failed">;

export const detectMobileProfileMismatch = detectProfileMismatch;

export const getMobileRestrictedCentralRoute = (pathname: string, profile: InstallationProfileCode | null | undefined) => {
  if (!isMobileProfile(profile)) return { allowed: true as const };
  if (pathname.startsWith(CENTRAL_HOME_ROUTE)) {
    return {
      allowed: false as const,
      redirectTo: MOBILE_HOME_ROUTE,
      message: "Les paramètres d’autorité centrale sont masqués sur un poste mobile.",
    };
  }
  return { allowed: true as const };
};

export const buildMobileCompletionSummary = ({
  manifest,
  provision,
}: {
  manifest: CentralBootstrapManifest | null;
  provision: MobileProvisionResponse | null;
}) => ({
  configured: Boolean(provision),
  localDataAvailable: Boolean(manifest),
  serverRegistered: Boolean(provision?.device_uuid),
  lastCentralSequence: manifest?.snapshot_central_sequence ?? 0,
});

export const MOBILE_RUNTIME_MODE_OPTIONS = MOBILE_RUNTIME_LABELS;
