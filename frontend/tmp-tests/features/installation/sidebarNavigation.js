import { Activity, AlertTriangle, Building2, ClipboardList, FileBarChart2, HardDriveDownload, LayoutDashboard, Microscope, Network, RefreshCw, Settings, ShieldCheck, UserCog, Users, } from "lucide-react";
import { hasAnyPermission, hasRole } from "../../utils/permissions.js";
const ALL_ROLES = ["Super Admin", "Admin", "Doctor", "Assistant"];
const ADMIN_ROLES = ["Super Admin", "Admin"];
const MEDICAL_ROLES = ["Super Admin", "Admin", "Doctor", "Assistant"];
const REPORTING_ROLES = ["Super Admin", "Admin", "Doctor"];
const SHARED_LEGACY_NAVIGATION = [
    {
        id: "shared-dashboard",
        label: "Tableau de bord",
        route: "/dashboard",
        icon: LayoutDashboard,
        roles: ALL_ROLES,
        allowWhenProfileUnresolved: true,
        visibleInClient: true,
        clientRequiredPermissions: ["reports.view"],
    },
    {
        id: "shared-users",
        label: "Utilisateurs",
        route: "/users",
        icon: UserCog,
        requiredPermissions: ["users.view"],
        roles: ADMIN_ROLES,
        allowWhenProfileUnresolved: true,
    },
    {
        id: "shared-companies",
        label: "Entreprises",
        route: "/companies",
        icon: Building2,
        roles: ALL_ROLES,
        allowWhenProfileUnresolved: true,
    },
    {
        id: "shared-workers",
        label: "Travailleurs",
        route: "/workers",
        icon: Users,
        roles: MEDICAL_ROLES,
        allowWhenProfileUnresolved: true,
        visibleInClient: true,
        clientRequiredPermissions: ["workers.view"],
    },
    {
        id: "shared-campaigns",
        label: "Campagnes",
        route: "/campaigns",
        icon: Activity,
        requiredPermissions: ["medical_campaigns.view"],
        roles: MEDICAL_ROLES,
        accessMode: "any",
        allowWhenProfileUnresolved: true,
    },
    {
        id: "shared-medical-records",
        label: "Dossiers medicaux",
        route: "/worker-tests",
        icon: ClipboardList,
        roles: MEDICAL_ROLES,
        allowWhenProfileUnresolved: true,
        visibleInClient: true,
        clientRequiredPermissions: ["worker_tests.view", "medical_visits.view"],
        accessMode: "any",
    },
    {
        id: "shared-medical-tests",
        label: "Examens medicaux",
        route: "/medical-tests",
        icon: Activity,
        roles: REPORTING_ROLES,
        allowWhenProfileUnresolved: true,
    },
    {
        id: "shared-imports",
        label: "Imports",
        route: "/imports",
        icon: Microscope,
        roles: ALL_ROLES,
        allowWhenProfileUnresolved: true,
    },
    {
        id: "shared-permissions",
        label: "Permissions",
        route: "/permissions",
        icon: ShieldCheck,
        requiredPermissions: ["roles.view", "users.view_permissions"],
        roles: ADMIN_ROLES,
        accessMode: "all",
        allowWhenProfileUnresolved: true,
        visibleInClient: true,
    },
    {
        id: "shared-reports",
        label: "Rapports",
        route: "/reports",
        icon: FileBarChart2,
        requiredPermissions: ["reports.view"],
        roles: REPORTING_ROLES,
        accessMode: "any",
        allowWhenProfileUnresolved: true,
        visibleInClient: true,
        clientRequiredPermissions: ["reports.view"],
    },
    {
        id: "shared-audit-logs",
        label: "Journal d'audit",
        route: "/app/audit-logs",
        icon: ShieldCheck,
        requiredPermissions: ["audit_logs.view"],
        roles: ADMIN_ROLES,
        accessMode: "any",
        allowWhenProfileUnresolved: true,
    },
    {
        id: "shared-sync-connection",
        label: "Sync & Connection",
        route: "/sync/connection",
        icon: Network,
        roles: ["Super Admin", "Admin", "Doctor"],
        allowWhenProfileUnresolved: true,
        hiddenInServerPc: true,
        visibleInClient: true,
        clientRequiredPermissions: ["local_network.view", "local_network.view_status"],
        accessMode: "any",
    },
    {
        id: "shared-settings",
        label: "Parametres",
        route: "/profile",
        icon: Settings,
        roles: ["Super Admin", "Admin", "Doctor"],
        accessMode: "any",
        allowWhenProfileUnresolved: true,
        hiddenInServerPc: true,
    },
    {
        id: "shared-about",
        label: "A propos",
        route: "/app/infrastructure/about",
        icon: ShieldCheck,
        roles: ALL_ROLES,
        allowWhenProfileUnresolved: true,
        allowDuringMismatch: true,
    },
];
const PROFILE_SPECIFIC_NAVIGATION = [
    {
        id: "mobile-dashboard",
        label: "Poste mobile",
        route: "/app/infrastructure/mobile",
        icon: LayoutDashboard,
        profiles: ["mobile_device"],
        roles: ALL_ROLES,
    },
    {
        id: "central-dashboard",
        label: "Serveur central",
        route: "/app/infrastructure/central",
        icon: LayoutDashboard,
        profiles: ["central_server"],
        roles: ALL_ROLES,
    },
    {
        id: "mobile-missions",
        label: "Missions",
        route: "/sync/mission",
        icon: RefreshCw,
        profiles: ["mobile_device"],
        requiredCapabilities: ["run_mission_server"],
        roles: ALL_ROLES,
    },
    {
        id: "mobile-central-sync",
        label: "Synchronisation centrale",
        route: "/sync/central",
        icon: RefreshCw,
        profiles: ["mobile_device"],
        roles: ALL_ROLES,
    },
    {
        id: "mobile-local-copy",
        label: "Copie locale de mission",
        route: "/sync/status",
        icon: HardDriveDownload,
        profiles: ["mobile_device"],
        roles: ALL_ROLES,
    },
    {
        id: "central-devices",
        label: "Appareils enregistres",
        route: "/app/infrastructure/central/devices",
        icon: Network,
        profiles: ["central_server"],
        requiredCapabilities: ["manage_registered_devices"],
        roles: ADMIN_ROLES,
    },
    {
        id: "central-submissions",
        label: "Missions recues",
        route: "/app/infrastructure/central/submissions",
        icon: RefreshCw,
        profiles: ["central_server"],
        requiredCapabilities: ["receive_mission_submissions"],
        roles: ADMIN_ROLES,
    },
    {
        id: "central-sync",
        label: "Synchronisations",
        route: "/sync/central",
        icon: RefreshCw,
        profiles: ["central_server"],
        roles: ALL_ROLES,
    },
    {
        id: "central-conflicts",
        label: "Conflits centraux",
        route: "/sync/conflicts",
        icon: AlertTriangle,
        profiles: ["central_server"],
        requiredCapabilities: ["central_authority"],
        roles: ALL_ROLES,
    },
    {
        id: "central-bootstrap",
        label: "Bootstrap des appareils",
        route: "/app/infrastructure/central-sync",
        icon: ShieldCheck,
        profiles: ["central_server"],
        requiredCapabilities: ["provide_device_bootstrap"],
        roles: ADMIN_ROLES,
    },
    {
        id: "central-backups",
        label: "Sauvegardes",
        route: "/app/infrastructure/backups",
        icon: HardDriveDownload,
        profiles: ["central_server"],
        requiredCapabilities: ["central_authority"],
        roles: ADMIN_ROLES,
    },
    {
        id: "shared-diagnostics",
        label: "Infrastructure",
        route: "/app/infrastructure/diagnostics",
        icon: Network,
        roles: ALL_ROLES,
        allowWhenProfileUnresolved: true,
        allowDuringMismatch: true,
    },
];
export const SIDEBAR_NAVIGATION = [
    ...SHARED_LEGACY_NAVIGATION,
    ...PROFILE_SPECIFIC_NAVIGATION,
];
export const resolveProfileSource = (backendProfile, packagedProfile) => {
    if (backendProfile) {
        return "backend";
    }
    if (packagedProfile) {
        return "packaged";
    }
    return "unknown";
};
export const resolveNavigationRoute = (item, currentUser) => {
    if (item.id === "shared-settings" &&
        hasAnyPermission(currentUser, ["settings.view"])) {
        return "/settings";
    }
    return item.route;
};
export const getFallbackCapabilities = () => ({
    central_authority: false,
    run_mission_server: false,
    run_mission_client: false,
    manage_registered_devices: false,
    receive_mission_submissions: false,
    provide_device_bootstrap: false,
    create_central_backups: false,
    perform_mission_copy: false,
    push_to_central: false,
    pull_from_central: false,
});
const evaluatePermissionGate = (user, permissions) => permissions?.length ? hasAnyPermission(user, permissions) : true;
const evaluateRoleGate = (user, roles) => roles?.length ? hasRole(user, roles) : true;
export const canDisplayNavigationItem = (item, context) => {
    if (context.connectionMode === "CLIENT") {
        if (!item.visibleInClient || !evaluatePermissionGate(context.currentUser, item.clientRequiredPermissions)) {
            return { allowed: false, reason: "permission" };
        }
    }
    if (context.connectionMode === "SERVER_PC" && item.hiddenInServerPc) {
        return { allowed: false, reason: "permission" };
    }
    if (context.mismatchError && !item.allowDuringMismatch) {
        return { allowed: false, reason: "profile" };
    }
    const profileUnresolved = !context.profile;
    if (profileUnresolved) {
        if (!item.allowWhenProfileUnresolved) {
            return { allowed: false, reason: "profile" };
        }
    }
    else if (item.onlyWhenProfileUnresolved) {
        return { allowed: false, reason: "profile" };
    }
    if (item.profiles?.length && (!context.profile || !item.profiles.includes(context.profile))) {
        return { allowed: false, reason: "profile" };
    }
    if (item.requiredCapabilities?.length) {
        const capabilities = context.capabilities;
        const hasCapabilities = Boolean(capabilities &&
            item.requiredCapabilities.every((capability) => Boolean(capabilities[capability])));
        if (!hasCapabilities) {
            return { allowed: false, reason: "capability" };
        }
    }
    const permissionAllowed = evaluatePermissionGate(context.currentUser, item.requiredPermissions);
    const roleAllowed = evaluateRoleGate(context.currentUser, item.roles);
    if ((item.accessMode || "all") === "any") {
        const hasPermissionRule = Boolean(item.requiredPermissions?.length);
        const hasRoleRule = Boolean(item.roles?.length);
        if (hasPermissionRule || hasRoleRule) {
            if ((hasPermissionRule && permissionAllowed) || (hasRoleRule && roleAllowed)) {
                return { allowed: true, reason: null };
            }
            return { allowed: false, reason: "permission" };
        }
    }
    else {
        if (!permissionAllowed) {
            return { allowed: false, reason: "permission" };
        }
        if (!roleAllowed) {
            return { allowed: false, reason: "permission" };
        }
    }
    return { allowed: true, reason: null };
};
export const filterNavigationItems = (items, context) => items.reduce((accumulator, item) => {
    const visibleChildren = item.children?.length ? filterNavigationItems(item.children, context) : undefined;
    const access = canDisplayNavigationItem(item, context);
    if (visibleChildren?.length) {
        accumulator.push({
            ...item,
            children: visibleChildren,
        });
        return accumulator;
    }
    if (access.allowed) {
        accumulator.push({
            ...item,
            children: undefined,
        });
    }
    return accumulator;
}, []);
export const flattenNavigationItems = (items) => items.flatMap((item) => (item.children?.length ? flattenNavigationItems(item.children) : [item]));
export const buildNavigationDiagnostics = (items, context) => {
    const visibleItems = flattenNavigationItems(filterNavigationItems(items, context));
    const candidateItems = flattenNavigationItems(items);
    const hiddenByProfile = [];
    const hiddenByCapability = [];
    const hiddenByPermission = [];
    candidateItems.forEach((item) => {
        const result = canDisplayNavigationItem(item, context);
        if (result.allowed) {
            return;
        }
        if (result.reason === "profile") {
            hiddenByProfile.push(item.id);
            return;
        }
        if (result.reason === "capability") {
            hiddenByCapability.push(item.id);
            return;
        }
        hiddenByPermission.push(item.id);
    });
    return {
        profile: context.profile,
        profileSource: resolveProfileSource(context.backendProfile, context.packagedProfile),
        capabilitiesLoaded: context.profileStatus === "ready" && Boolean(context.backendProfile),
        userRole: context.currentUser?.role || null,
        candidateItems: candidateItems.length,
        visibleItems: visibleItems.length,
        hiddenByProfile,
        hiddenByCapability,
        hiddenByPermission,
    };
};
