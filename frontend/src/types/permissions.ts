export type UserRoleCode =
  | "super_admin"
  | "admin"
  | "doctor"
  | "assistant";

export type PermissionOverrideState =
  | "inherit"
  | "allow"
  | "deny";

export type PermissionSource =
  | "user_allow"
  | "user_deny"
  | "role"
  | "default_deny";

export interface PermissionDefinition {
  id: number;
  module: string;
  action: string;
  code: string;
  name: string;
  description?: string | null;
  category?: string | null;
  is_sensitive: boolean;
  is_system: boolean;
  sort_order: number;
  created_at: string;
  updated_at: string;
}

export interface RoleRecord {
  id: number;
  name: string;
  code: UserRoleCode;
  description?: string | null;
  is_system: boolean;
  is_active: boolean;
}

export interface RolePermissionMatrix {
  role: RoleRecord;
  permissions: PermissionDefinition[];
  assigned_permission_codes: string[];
}

export interface EffectivePermission {
  id: number;
  code: string;
  module: string;
  action: string;
  name: string;
  description?: string | null;
  category?: string | null;
  is_sensitive: boolean;
  role_allowed: boolean;
  override: "allow" | "deny" | null;
  effective_allowed: boolean;
  source: PermissionSource;
  can_manage: boolean;
}

export interface UserPermissionMatrix {
  user: {
    id: number;
    name: string;
    username?: string | null;
    email?: string | null;
    role: UserRoleCode;
    isActive: boolean;
  };
  permissions_version: number;
  direct_override_count: number;
  effective_permission_count: number;
  is_last_active_super_admin: boolean;
  permissions: EffectivePermission[];
}

export interface UpdateUserPermissionsPayload {
  permissions: Array<{
    permission_code: string;
    state: PermissionOverrideState;
  }>;
  reason?: string | null;
}

export interface CopyUserPermissionsPayload {
  source_user_id: number;
  copy_role: boolean;
  copy_overrides: boolean;
  reason?: string | null;
}

export interface MyPermissionsResponse {
  role: UserRoleCode;
  permissions_version: number;
  permissions: string[];
}

export type PermissionExplanationReason = "allowed" | "mode_denied" | "user_denied" | "role_denied";

export interface EffectivePermissionExplanation extends PermissionDefinition {
  mode_allowed: boolean;
  role_allowed: boolean;
  user_override: PermissionOverrideState;
  context_allowed: boolean;
  effective_allowed: boolean;
  reason: PermissionExplanationReason;
}

export interface EffectivePermissionExplanationResponse {
  connection_mode: "CLIENT" | "SERVER_PC" | "SERVER";
  role: RoleRecord;
  user: { id: number; name: string; role: UserRoleCode } | null;
  permissions: EffectivePermissionExplanation[];
}
