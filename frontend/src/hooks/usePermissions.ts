import { usePermissionContext } from "@/context/PermissionContext";

export const usePermissions = () => usePermissionContext();

export const useCan = (permission: string) => usePermissionContext().can(permission);

export const useCanAny = (permissions: string[]) => usePermissionContext().canAny(permissions);

export const useCanAll = (permissions: string[]) => usePermissionContext().canAll(permissions);
