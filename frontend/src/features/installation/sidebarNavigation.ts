import {
  Activity,
  AlertTriangle,
  Building2,
  ClipboardList,
  FileBarChart2,
  HardDriveDownload,
  LayoutDashboard,
  Microscope,
  Network,
  RefreshCw,
  Settings,
  ShieldCheck,
  UserCog,
  Users,
  type LucideIcon,
} from "lucide-react";

import type { AuthUser } from "../../types/auth.js";
import type {
  InstallationErrorCode,
  InstallationProfileCapabilities,
  InstallationProfileCode,
  InstallationProfileLoadState,
} from "../../types/installation.js";
import type { Role } from "../../types/common.js";
import type { ConnectionMode } from "../../config/runtime.js";
import { hasAnyPermission, hasRole } from "../../utils/permissions.js";

export type InstallationProfile = InstallationProfileCode;
export type InstallationCapability = keyof InstallationProfileCapabilities;
export type Permission = string;
export type UserRole = Role;

export interface NavigationItem {
  id: string;
  label: string;
  route: string;
  icon: LucideIcon;
  profiles?: InstallationProfile[];
  requiredCapabilities?: InstallationCapability[];
  requiredPermissions?: Permission[];
  roles?: UserRole[];
  children?: NavigationItem[];
  allowWhenProfileUnresolved?: boolean;
  allowDuringMismatch?: boolean;
  onlyWhenProfileUnresolved?: boolean;
  accessMode?: "all" | "any";
  hiddenInServerPc?: boolean;
  visibleInClient?: boolean;
  clientRequiredPermissions?: Permission[];
}

export interface NavigationAccessContext {
  profile: InstallationProfile | null;
  packagedProfile: InstallationProfile | null;
  backendProfile: InstallationProfile | null;
  capabilities: InstallationProfileCapabilities | null;
  profileStatus: InstallationProfileLoadState;
  mismatchError: InstallationErrorCode | null;
  currentUser: AuthUser | null;
  connectionMode?: ConnectionMode | null;
}

export interface NavigationDiagnostics {
  profile: InstallationProfile | null;
  profileSource: "backend" | "packaged" | "unknown";
  capabilitiesLoaded: boolean;
  userRole: Role | null;
  candidateItems: number;
  visibleItems: number;
  hiddenByProfile: string[];
  hiddenByCapability: string[];
  hiddenByPermission: string[];
}

const ALL_ROLES: Role[] = ["Super Admin", "Admin", "Doctor", "Assistant"];
const ADMIN_ROLES: Role[] = ["Super Admin", "Admin"];
const MEDICAL_ROLES: Role[] = ["Super Admin", "Admin", "Doctor", "Assistant"];
const REPORTING_ROLES: Role[] = ["Super Admin", "Admin", "Doctor"];

const SHARED_LEGACY_NAVIGATION: NavigationItem[] = [
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

const PROFILE_SPECIFIC_NAVIGATION: NavigationItem[] = [
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

export const SIDEBAR_NAVIGATION: NavigationItem[] = [
  ...SHARED_LEGACY_NAVIGATION,
  ...PROFILE_SPECIFIC_NAVIGATION,
];

export const resolveProfileSource = (
  backendProfile: InstallationProfile | null,
  packagedProfile: InstallationProfile | null,
) => {
  if (backendProfile) {
    return "backend" as const;
  }
  if (packagedProfile) {
    return "packaged" as const;
  }
  return "unknown" as const;
};

export const resolveNavigationRoute = (item: NavigationItem, currentUser: AuthUser | null) => {
  if (
    item.id === "shared-settings" &&
    hasAnyPermission(currentUser, ["settings.view"])
  ) {
    return "/settings";
  }

  return item.route;
};

export const getFallbackCapabilities = (): InstallationProfileCapabilities => ({
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

const evaluatePermissionGate = (user: AuthUser | null, permissions?: Permission[]) =>
  permissions?.length ? hasAnyPermission(user, permissions) : true;

const evaluateRoleGate = (user: AuthUser | null, roles?: UserRole[]) =>
  roles?.length ? hasRole(user, roles) : true;

export const canDisplayNavigationItem = (
  item: NavigationItem,
  context: NavigationAccessContext,
) => {
  if (context.connectionMode === "CLIENT") {
    if (!item.visibleInClient || !evaluatePermissionGate(context.currentUser, item.clientRequiredPermissions)) {
      return { allowed: false, reason: "permission" as const };
    }
  }
  if (context.connectionMode === "SERVER_PC" && item.hiddenInServerPc) {
    return { allowed: false, reason: "permission" as const };
  }
  if (context.mismatchError && !item.allowDuringMismatch) {
    return { allowed: false, reason: "profile" as const };
  }

  const profileUnresolved = !context.profile;
  if (profileUnresolved) {
    if (!item.allowWhenProfileUnresolved) {
      return { allowed: false, reason: "profile" as const };
    }
  } else if (item.onlyWhenProfileUnresolved) {
    return { allowed: false, reason: "profile" as const };
  }

  if (item.profiles?.length && (!context.profile || !item.profiles.includes(context.profile))) {
    return { allowed: false, reason: "profile" as const };
  }

  if (item.requiredCapabilities?.length) {
    const capabilities = context.capabilities;
    const hasCapabilities = Boolean(
      capabilities &&
        item.requiredCapabilities.every((capability) => Boolean(capabilities[capability])),
    );
    if (!hasCapabilities) {
      return { allowed: false, reason: "capability" as const };
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
      return { allowed: false, reason: "permission" as const };
    }
  } else {
    if (!permissionAllowed) {
      return { allowed: false, reason: "permission" as const };
    }

    if (!roleAllowed) {
      return { allowed: false, reason: "permission" as const };
    }
  }

  return { allowed: true, reason: null };
};

export const filterNavigationItems = (
  items: NavigationItem[],
  context: NavigationAccessContext,
): NavigationItem[] =>
  items.reduce<NavigationItem[]>((accumulator, item) => {
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

export const flattenNavigationItems = (items: NavigationItem[]): NavigationItem[] =>
  items.flatMap((item) => (item.children?.length ? flattenNavigationItems(item.children) : [item]));

export const buildNavigationDiagnostics = (
  items: NavigationItem[],
  context: NavigationAccessContext,
): NavigationDiagnostics => {
  const visibleItems = flattenNavigationItems(filterNavigationItems(items, context));
  const candidateItems = flattenNavigationItems(items);
  const hiddenByProfile: string[] = [];
  const hiddenByCapability: string[] = [];
  const hiddenByPermission: string[] = [];

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
