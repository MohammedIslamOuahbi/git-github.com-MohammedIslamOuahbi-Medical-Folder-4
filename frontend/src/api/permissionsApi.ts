import apiClient from "./axios";
import type {
  CopyUserPermissionsPayload,
  EffectivePermissionExplanationResponse,
  MyPermissionsResponse,
  PermissionDefinition,
  RolePermissionMatrix,
  RoleRecord,
  UpdateUserPermissionsPayload,
  UserPermissionMatrix,
} from "@/types/permissions";

export const permissionsApi = {
  getPermissions: async () => {
    const { data } = await apiClient.get<PermissionDefinition[]>("/permissions");
    return data;
  },
  getRoles: async () => {
    const { data } = await apiClient.get<RoleRecord[]>("/roles");
    return data;
  },
  getRolePermissions: async (roleId: number | string) => {
    const { data } = await apiClient.get<RolePermissionMatrix>(`/roles/${roleId}/permissions`);
    return data;
  },
  updateRolePermissions: async (roleId: number | string, permission_codes: string[]) => {
    const { data } = await apiClient.put(`/roles/${roleId}/permissions`, { permission_codes });
    return data;
  },
  getUserPermissions: async (userId: number | string) => {
    const { data } = await apiClient.get<UserPermissionMatrix>(`/users/${userId}/permissions`);
    return data;
  },
  updateUserPermissions: async (userId: number | string, payload: UpdateUserPermissionsPayload) => {
    const { data } = await apiClient.put<UserPermissionMatrix>(`/users/${userId}/permissions`, payload);
    return data;
  },
  resetUserPermissions: async (userId: number | string) => {
    const { data } = await apiClient.post<UserPermissionMatrix>(`/users/${userId}/permissions/reset`);
    return data;
  },
  copyUserPermissions: async (targetUserId: number | string, payload: CopyUserPermissionsPayload) => {
    const { data } = await apiClient.post<UserPermissionMatrix>(`/users/${targetUserId}/permissions/copy`, payload);
    return data;
  },
  getMyPermissions: async () => {
    const { data } = await apiClient.get<MyPermissionsResponse>("/auth/me/permissions");
    return data;
  },
  getEffectivePermissions: async (params: {
    connection_mode: "CLIENT" | "SERVER_PC" | "SERVER";
    role_id?: number | string;
    user_id?: number | string;
  }) => {
    const { data } = await apiClient.get<EffectivePermissionExplanationResponse>("/permissions/effective", { params });
    return data;
  },
};
