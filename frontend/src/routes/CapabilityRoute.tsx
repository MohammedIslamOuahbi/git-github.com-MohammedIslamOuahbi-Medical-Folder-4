import { Navigate, Outlet } from "react-router-dom";

import { useAuth } from "@/hooks/useAuth";
import { useInstallationProfile } from "@/hooks/useInstallationProfile";
import { evaluateCapabilityAccess } from "@/features/installation/profileInfrastructure";
import { Spinner } from "@/components/common/Spinner";
import type { InstallationProfileCapabilities, InstallationProfileCode } from "@/types/installation";
import type { Role } from "@/types/common";
import { hasAnyPermission } from "@/utils/permissions";

interface CapabilityRouteProps {
  capability?: keyof InstallationProfileCapabilities;
  permissions?: string[];
  roles?: Role[];
  requiredProfile?: InstallationProfileCode;
  fallbackTo?: string;
  allowWhenProfileUnresolved?: boolean;
  accessMode?: "all" | "any";
}

export const CapabilityRoute = ({
  capability,
  permissions,
  roles,
  requiredProfile,
  fallbackTo,
  allowWhenProfileUnresolved = false,
  accessMode = "all",
}: CapabilityRouteProps) => {
  const { hasStoredSession, profileResolved, user } = useAuth();
  const { profile, capabilities, status, mismatchError } = useInstallationProfile();

  if (status === "idle" || status === "loading" || (hasStoredSession && (!profileResolved || !user))) {
    return (
      <div className="flex min-h-[40vh] items-center justify-center">
        <Spinner />
      </div>
    );
  }

  if (mismatchError) {
    return <Navigate to="/app/infrastructure/about" replace />;
  }

  if (!profile && allowWhenProfileUnresolved) {
    const permissionAllowed = !permissions?.length || hasAnyPermission(user, permissions);
    const roleAllowed = !roles?.length || (user ? roles.includes(user.role) : false);

    const hasPermissionRule = Boolean(permissions?.length);
    const hasRoleRule = Boolean(roles?.length);
    const allowAccess =
      accessMode === "any"
        ? (!hasPermissionRule && !hasRoleRule) ||
          (hasPermissionRule && permissionAllowed) ||
          (hasRoleRule && roleAllowed)
        : permissionAllowed && roleAllowed;

    if (allowAccess) {
      return <Outlet />;
    }
  }

  const decision = evaluateCapabilityAccess({
    profile,
    capabilities,
    user,
    requiredProfile,
    requiredCapability: capability,
    requiredPermissions: permissions,
    requiredRoles: roles,
    accessMode,
  });

  if (!decision.allowed) {
    return <Navigate to={fallbackTo || decision.redirectTo} replace />;
  }

  return <Outlet />;
};
