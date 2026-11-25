import { CENTRAL_HOME_ROUTE, MOBILE_RUNTIME_LABELS, detectProfileMismatch, } from "../central/centralServerFlow.js";
export const MOBILE_HOME_ROUTE = "/app/infrastructure/mobile";
export const MOBILE_WIZARD_STEPS = [
    { id: "welcome", title: "Configuration du poste mobile" },
    { id: "postgres", title: "PostgreSQL local" },
    { id: "identity", title: "Identité de l’appareil" },
    { id: "connection", title: "Connexion au serveur central" },
    { id: "registration", title: "Enregistrement" },
    { id: "readiness", title: "Bootstrap readiness" },
    { id: "bootstrap", title: "Bootstrap progress" },
    { id: "completion", title: "Choisir le mode de fonctionnement" },
];
export const defaultMobileWizardDraft = (status) => ({
    identity: {
        deviceName: status?.identity.server_name || "PC Médecin 01",
        deviceCode: status?.identity.server_code || "PC-01",
        description: status?.identity.description || "",
    },
    connection: {
        centralServerUrl: status?.network.api_url || "http://192.168.1.5:8000",
    },
});
export const isMobileProfile = (profile) => profile === "mobile_device";
export const shouldHideCentralSetup = (payload) => isMobileProfile(payload?.profile);
export const shouldShowMobileProvisioning = ({ profile, provisioningStatus, }) => isMobileProfile(profile) && provisioningStatus !== "configured";
export const normalizeMobilePostgresChecks = (checks) => checks && checks.length > 0
    ? checks
    : [
        { key: "postgres_service", label: "Service PostgreSQL", status: "pending", detail: null },
        { key: "local_database", label: "Base locale", status: "pending", detail: null },
        { key: "app_user", label: "Utilisateur applicatif", status: "pending", detail: null },
        { key: "migrations", label: "Migrations", status: "pending", detail: null },
        { key: "disk", label: "Espace disque", status: "pending", detail: null },
    ];
export const buildBootstrapReadiness = (status) => [
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
];
export const validateMobileIdentityDraft = (draft) => {
    const errors = {};
    if (!draft.deviceName.trim())
        errors.deviceName = "Le nom de l’appareil est requis.";
    if (!draft.deviceCode.trim())
        errors.deviceCode = "Le code de l’appareil est requis.";
    return errors;
};
export const validateCentralConnectionUrl = (value) => {
    if (!value.trim()) {
        return "L’adresse du serveur central est requise.";
    }
    if (!/^https?:\/\//i.test(value.trim())) {
        return "L’adresse doit commencer par http:// ou https://";
    }
    return null;
};
export const buildMobileRegistrationSummary = ({ draft, serverName, registration, }) => ({
    deviceName: draft.identity.deviceName,
    code: draft.identity.deviceCode,
    centralServer: serverName || "Serveur central",
    authorized: Boolean(registration?.device_uuid),
});
export const buildBootstrapStageStates = ({ manifest, checksumFailed, interrupted, }) => Object.fromEntries(MOBILE_BOOTSTRAP_STAGES.map((stage) => {
    if (interrupted)
        return [stage, "failed"];
    if (stage === "Validation du checksum" && checksumFailed)
        return [stage, "failed"];
    if (manifest && stage === "Téléchargement du manifeste")
        return [stage, "completed"];
    return [stage, "pending"];
}));
export const detectMobileProfileMismatch = detectProfileMismatch;
export const getMobileRestrictedCentralRoute = (pathname, profile) => {
    if (!isMobileProfile(profile))
        return { allowed: true };
    if (pathname.startsWith(CENTRAL_HOME_ROUTE)) {
        return {
            allowed: false,
            redirectTo: MOBILE_HOME_ROUTE,
            message: "Les paramètres d’autorité centrale sont masqués sur un poste mobile.",
        };
    }
    return { allowed: true };
};
export const buildMobileCompletionSummary = ({ manifest, provision, }) => ({
    configured: Boolean(provision),
    localDataAvailable: Boolean(manifest),
    serverRegistered: Boolean(provision?.device_uuid),
    lastCentralSequence: manifest?.snapshot_central_sequence ?? 0,
});
export const MOBILE_RUNTIME_MODE_OPTIONS = MOBILE_RUNTIME_LABELS;
