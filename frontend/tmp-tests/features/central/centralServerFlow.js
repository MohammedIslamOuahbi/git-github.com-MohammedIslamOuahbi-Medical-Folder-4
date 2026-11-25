export const CENTRAL_WIZARD_STEPS = [
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
export const defaultCentralWizardDraft = (status) => ({
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
export const isCentralProfile = (profile) => profile === "central_server";
export const detectProfileMismatch = (backendProfile, packagedProfile) => {
    if (!backendProfile || !packagedProfile) {
        return null;
    }
    return backendProfile !== packagedProfile ? "INSTALLATION_PROFILE_MISMATCH" : null;
};
export const shouldHideMobileModeSelection = (profilePayload) => isCentralProfile(profilePayload?.profile);
export const getCentralSetupEntry = ({ profile, provisioningStatus, }) => isCentralProfile(profile) && provisioningStatus !== "configured";
export const normalizeProvisioningStages = (stages) => stages && stages.length > 0
    ? stages
    : [
        { key: "database", label: "Création de la base", status: "pending", detail: null },
        { key: "role", label: "Création du rôle applicatif", status: "pending", detail: null },
        { key: "permissions", label: "Configuration des permissions", status: "pending", detail: null },
        { key: "migrations", label: "Application des migrations", status: "pending", detail: null },
        { key: "sequence", label: "Initialisation de la séquence centrale", status: "pending", detail: null },
    ];
export const normalizeReadinessChecks = (checks) => checks && checks.length > 0
    ? checks
    : [
        { key: "postgres_service", label: "Service PostgreSQL", status: "pending", detail: null },
        { key: "local_connection", label: "Connexion locale", status: "pending", detail: null },
        { key: "central_database", label: "Base centrale", status: "pending", detail: null },
        { key: "app_user", label: "Utilisateur applicatif", status: "pending", detail: null },
        { key: "schema_permissions", label: "Permissions du schéma", status: "pending", detail: null },
    ];
export const validateSuperAdminDraft = (draft) => {
    const errors = {};
    if (!draft.firstName.trim())
        errors.firstName = "Le prénom est requis.";
    if (!draft.lastName.trim())
        errors.lastName = "Le nom est requis.";
    if (!draft.email.trim() || !draft.email.includes("@"))
        errors.email = "Une adresse e-mail valide est requise.";
    if (draft.password.length < 8)
        errors.password = "Le mot de passe doit contenir au moins 8 caractères.";
    if (draft.confirmation !== draft.password)
        errors.confirmation = "La confirmation doit correspondre au mot de passe.";
    return errors;
};
export const validateBackupDraft = (draft) => {
    if (!draft.directory.trim()) {
        return { directory: "Le dossier de sauvegarde est requis." };
    }
    return {};
};
export const buildFinalVerificationItems = (status) => [
    { label: "PostgreSQL opérationnel", passed: Boolean(status?.postgres_ready) },
    { label: "Base centrale opérationnelle", passed: Boolean(status?.central_database_ready) },
    { label: "Migrations à jour", passed: Boolean(status?.migrations_up_to_date) },
    { label: "Serveur FastAPI opérationnel", passed: Boolean(status?.fastapi_ready) },
    { label: "Administrateur créé", passed: Boolean(status?.admin_created) },
    { label: "Sauvegarde configurée", passed: Boolean(status?.backup_configured) },
];
export const buildCentralDashboardSnapshot = ({ status, serverInfo, devices, submissions, backups, }) => ({
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
export const getCentralRestrictionDecision = (pathname, profile) => {
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
