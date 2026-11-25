const normalizePermissionCode = (permission) => permission.trim().toLowerCase().replace(/:/g, ".");
const normalizeRoleCode = (role) => role.trim().toLowerCase().replace(/[\s-]+/g, "_");
export const normalizePermissionList = (permissions) => Array.from(new Set((permissions || []).filter(Boolean).map((permission) => normalizePermissionCode(permission)))).sort();
const legacyPermissionAliases = {
    "users.manage": ["users.view", "users.create", "users.update", "users.delete", "users.view_permissions", "users.edit_permissions"],
    "users.view": ["users.manage"],
    "reports.read": ["reports.view"],
    "reports.view": ["reports.read"],
    "settings.manage": ["settings.view", "settings.update"],
    "settings.view": ["settings.manage"],
    "audit.read": ["audit_logs.view"],
    "audit_logs.view": ["audit.read"],
    "campaigns.manage": ["medical_campaigns.view", "medical_campaigns.create", "medical_campaigns.update", "medical_campaigns.delete"],
    "campaigns.read": ["medical_campaigns.view"],
    "medical_campaigns.view": ["campaigns.read", "campaigns.manage"],
};
export const hasPermission = (user, permission) => {
    if (!user)
        return false;
    const normalizedPermissions = normalizePermissionList(user.permissions);
    const requested = normalizePermissionCode(permission);
    if (requested.endsWith(".*")) {
        const prefix = requested.slice(0, -1);
        return normalizedPermissions.some((item) => item.startsWith(prefix));
    }
    if (normalizedPermissions.includes(requested)) {
        return true;
    }
    const aliases = legacyPermissionAliases[requested] || [];
    if (aliases.some((alias) => normalizedPermissions.includes(alias))) {
        return true;
    }
    const parts = requested.split(".");
    if (parts[1] === "manage") {
        return normalizedPermissions.some((item) => item.startsWith(`${parts[0]}.`));
    }
    return false;
};
export const hasAnyPermission = (user, permissions) => permissions.some((permission) => hasPermission(user, permission));
export const hasRole = (user, roles) => Boolean(user &&
    roles.some((role) => normalizeRoleCode(role) === normalizeRoleCode(String(user.role))));
