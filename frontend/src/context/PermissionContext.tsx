import { createContext, useContext, useMemo } from "react";
import type { ReactNode } from "react";

import { useAuth } from "@/hooks/useAuth";
import { hasAnyPermission, hasPermission, normalizePermissionList } from "@/utils/permissions";

interface PermissionContextValue {
  permissions: string[];
  can: (permission: string) => boolean;
  canAny: (permissions: string[]) => boolean;
  canAll: (permissions: string[]) => boolean;
}

const PermissionContext = createContext<PermissionContextValue | undefined>(undefined);

export const PermissionProvider = ({ children }: { children: ReactNode }) => {
  const { user } = useAuth();

  const value = useMemo<PermissionContextValue>(
    () => ({
      permissions: normalizePermissionList(user?.permissions),
      can: (permission: string) => hasPermission(user, permission),
      canAny: (permissions: string[]) => hasAnyPermission(user, permissions),
      canAll: (permissions: string[]) => permissions.every((permission) => hasPermission(user, permission)),
    }),
    [user],
  );

  return <PermissionContext.Provider value={value}>{children}</PermissionContext.Provider>;
};

export const usePermissionContext = () => {
  const context = useContext(PermissionContext);
  if (!context) {
    throw new Error("usePermissionContext must be used within PermissionProvider");
  }
  return context;
};
