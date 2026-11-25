import { useEffect, useMemo, useState } from "react";

import { AlertTriangle, Check, ShieldCheck, X } from "lucide-react";

import { permissionsApi } from "@/api/permissionsApi";
import { usersApi } from "@/api/usersApi";
import { Button } from "@/components/common/Button";
import { Card } from "@/components/common/Card";
import { Input } from "@/components/common/Input";
import { SectionHeader } from "@/components/common/SectionHeader";
import { readStoredConnectionMode } from "@/config/runtime";
import { UserPermissionMatrixEditor } from "@/features/users/UserPermissionMatrixEditor";
import type { User } from "@/types/entities";
import type {
  EffectivePermissionExplanation,
  EffectivePermissionExplanationResponse,
  PermissionDefinition,
  RolePermissionMatrix,
  RoleRecord,
} from "@/types/permissions";

type PermissionTab = "effective" | "mode" | "roles" | "overrides" | "registry";
type ConnectionMode = "CLIENT" | "SERVER_PC" | "SERVER";
type DecisionFilter = "all" | "allow" | "deny";

const tabs: Array<{ id: PermissionTab; label: string }> = [
  { id: "effective", label: "Effective permissions" },
  { id: "mode", label: "Mode permissions" },
  { id: "roles", label: "Role permissions" },
  { id: "overrides", label: "User overrides" },
  { id: "registry", label: "Permission registry" },
];
const modes: ConnectionMode[] = ["CLIENT", "SERVER_PC", "SERVER"];

const initialConnectionMode = (): ConnectionMode => readStoredConnectionMode() || "SERVER";

const permissionLoadError = (error: unknown) => {
  const status = typeof error === "object" && error !== null && "response" in error
    ? (error as { response?: { status?: number } }).response?.status
    : undefined;
  if (status === 401) return "Votre session a expiré. Veuillez vous reconnecter.";
  if (status === 403) {
    return readStoredConnectionMode() === "SERVER"
      ? "Vous n'avez pas l'autorisation de consulter cette section."
      : "Cette fonction est disponible uniquement sur le Serveur central.";
  }
  if (status) return "Erreur lors du chargement des permissions (code " + status + ").";
  return "Impossible de charger les permissions. Réessayez dans un instant.";
};

const decisionBadge = (allowed: boolean) => (
  <span className={"inline-flex items-center gap-1 rounded-full px-2 py-1 text-[10px] font-bold " + (allowed ? "bg-emerald-50 text-emerald-700" : "bg-rose-50 text-rose-700")}>
    {allowed ? <Check className="h-3 w-3" /> : <X className="h-3 w-3" />}
    {allowed ? "ALLOW" : "DENY"}
  </span>
);

const reasonLabels: Record<EffectivePermissionExplanation["reason"], string> = {
  allowed: "Allowed by mode and assigned access",
  mode_denied: "Blocked by connection mode policy",
  user_denied: "Denied by user override",
  role_denied: "Not granted by the selected role",
};

const groupByModule = <T extends { module: string }>(permissions: T[]) =>
  permissions.reduce<Record<string, T[]>>((groups, permission) => {
    groups[permission.module] = [...(groups[permission.module] || []), permission];
    return groups;
  }, {});

export const PermissionsPage = () => {
  const [tab, setTab] = useState<PermissionTab>("effective");
  const [registry, setRegistry] = useState<PermissionDefinition[]>([]);
  const [roles, setRoles] = useState<RoleRecord[]>([]);
  const [users, setUsers] = useState<User[]>([]);
  const [usersLoaded, setUsersLoaded] = useState(false);
  const [selectedRoleId, setSelectedRoleId] = useState<number | null>(null);
  const [selectedUserId, setSelectedUserId] = useState<number | null>(null);
  const [connectionMode, setConnectionMode] = useState<ConnectionMode>(initialConnectionMode);
  const [explanation, setExplanation] = useState<EffectivePermissionExplanationResponse | null>(null);
  const [modeMatrices, setModeMatrices] = useState<Record<ConnectionMode, EffectivePermissionExplanationResponse> | null>(null);
  const [roleMatrix, setRoleMatrix] = useState<RolePermissionMatrix | null>(null);
  const [roleDraft, setRoleDraft] = useState<Set<string>>(new Set());
  const [search, setSearch] = useState("");
  const [moduleFilter, setModuleFilter] = useState("all");
  const [decisionFilter, setDecisionFilter] = useState<DecisionFilter>("all");
  const [loading, setLoading] = useState(true);
  const [savingRole, setSavingRole] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    void Promise.all([
      permissionsApi.getPermissions(),
      permissionsApi.getRoles(),
    ]).then(([permissions, roleRecords]) => {
      if (!active) return;
      setRegistry(permissions);
      setRoles(roleRecords);
      setSelectedRoleId((current) => current ?? roleRecords[0]?.id ?? null);
    }).catch((loadError) => {
      if (active) setError(permissionLoadError(loadError));
    }).finally(() => {
      if (active) setLoading(false);
    });
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    if (tab !== "overrides" || usersLoaded) return;
    let active = true;
    void usersApi.list({ page: 1, page_size: 100 }).then((result) => {
      if (!active) return;
      setUsers(result.items);
      setUsersLoaded(true);
    }).catch((loadError) => {
      if (active) setError(permissionLoadError(loadError));
    });
    return () => {
      active = false;
    };
  }, [tab, usersLoaded]);

  useEffect(() => {
    if (!selectedRoleId) return;
    let active = true;
    void permissionsApi.getRolePermissions(selectedRoleId).then((matrix) => {
      if (!active) return;
      setRoleMatrix(matrix);
      setRoleDraft(new Set(matrix.assigned_permission_codes));
    }).catch((loadError) => {
      if (active) setError(permissionLoadError(loadError));
    });
    return () => {
      active = false;
    };
  }, [selectedRoleId]);

  useEffect(() => {
    if (!selectedRoleId) return;
    let active = true;
    void permissionsApi.getEffectivePermissions({
      connection_mode: connectionMode,
      role_id: selectedRoleId,
      ...(selectedUserId ? { user_id: selectedUserId } : {}),
    }).then((result) => {
      if (active) setExplanation(result);
    }).catch((loadError) => {
      if (active) setError(permissionLoadError(loadError));
    });
    return () => {
      active = false;
    };
  }, [connectionMode, selectedRoleId, selectedUserId]);

  useEffect(() => {
    if (tab !== "mode" || !selectedRoleId) return;
    let active = true;
    void Promise.all(modes.map(async (mode) => [mode, await permissionsApi.getEffectivePermissions({ connection_mode: mode, role_id: selectedRoleId })] as const))
      .then((entries) => {
        if (active) setModeMatrices(Object.fromEntries(entries) as Record<ConnectionMode, EffectivePermissionExplanationResponse>);
      })
      .catch((loadError) => {
        if (active) setError(permissionLoadError(loadError));
      });
    return () => {
      active = false;
    };
  }, [selectedRoleId, tab]);

  const modules = useMemo(() => Array.from(new Set(registry.map((permission) => permission.module))).sort(), [registry]);
  const matchesFilters = (permission: { code: string; module: string; effective_allowed?: boolean }) =>
    (!search || permission.code.toLowerCase().includes(search.toLowerCase())) &&
    (moduleFilter === "all" || permission.module === moduleFilter) &&
    (decisionFilter === "all" || permission.effective_allowed === (decisionFilter === "allow"));
  const filteredPermissions = (explanation?.permissions || []).filter(matchesFilters);
  const registryRows = registry.filter((permission) => matchesFilters(permission));

  const toggleRolePermission = (code: string) => {
    setRoleDraft((current) => {
      const next = new Set(current);
      if (next.has(code)) next.delete(code);
      else next.add(code);
      return next;
    });
  };

  const saveRolePermissions = async () => {
    if (!selectedRoleId) return;
    setSavingRole(true);
    try {
      const result = await permissionsApi.updateRolePermissions(selectedRoleId, [...roleDraft]);
      setRoleMatrix(result);
      setRoleDraft(new Set(result.assigned_permission_codes));
      setError(null);
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : "Unable to save role permissions.");
    } finally {
      setSavingRole(false);
    }
  };

  return (
    <div className="space-y-5">
      <SectionHeader
        eyebrow="Access control"
        title="Permission administration"
        description="Inspect live mode policy, role grants, user overrides, and effective access."
      />

      {error ? <Card className="border-rose-200 bg-rose-50 text-rose-900"><p className="text-sm font-semibold">{error}</p></Card> : null}

      <Card className="space-y-4">
        <div className="flex flex-wrap gap-2 border-b border-slate-100 pb-4">
          {tabs.map((item) => (
            <button key={item.id} type="button" onClick={() => setTab(item.id)} className={"rounded-md px-3 py-2 text-xs font-bold transition-colors " + (tab === item.id ? "bg-[#0085A3] text-white" : "text-slate-600 hover:bg-slate-100")}>
              {item.label}
            </button>
          ))}
        </div>
        <div className="grid gap-3 md:grid-cols-3">
          <label className="text-xs font-bold text-slate-700">Connection mode
            <select value={connectionMode} onChange={(event) => setConnectionMode(event.target.value as ConnectionMode)} className="mt-1.5 w-full rounded-md border border-slate-200 bg-white px-3 py-2 text-sm">
              {modes.map((mode) => <option key={mode} value={mode}>{mode}</option>)}
            </select>
          </label>
          <label className="text-xs font-bold text-slate-700">Role
            <select value={selectedRoleId ?? ""} onChange={(event) => setSelectedRoleId(Number(event.target.value))} className="mt-1.5 w-full rounded-md border border-slate-200 bg-white px-3 py-2 text-sm">
              {roles.map((role) => <option key={role.id} value={role.id}>{role.name}</option>)}
            </select>
          </label>
          <label className="text-xs font-bold text-slate-700">User override context
            <select value={selectedUserId ?? ""} onChange={(event) => setSelectedUserId(event.target.value ? Number(event.target.value) : null)} disabled={!usersLoaded} className="mt-1.5 w-full rounded-md border border-slate-200 bg-white px-3 py-2 text-sm disabled:bg-slate-100">
              <option value="">No user override</option>
              {users.map((user) => <option key={user.id} value={user.id}>{user.full_name || (user.first_name + " " + user.last_name)}</option>)}
            </select>
          </label>
        </div>
      </Card>

      {(tab === "effective" || tab === "registry") ? (
        <Card className="space-y-4">
          <div className="grid gap-3 md:grid-cols-[1fr_180px_160px]">
            <Input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search permission code" aria-label="Search permission code" />
            <select value={moduleFilter} onChange={(event) => setModuleFilter(event.target.value)} className="rounded-md border border-slate-200 bg-white px-3 py-2 text-sm">
              <option value="all">All modules</option>
              {modules.map((module) => <option key={module} value={module}>{module}</option>)}
            </select>
            {tab === "effective" ? <select value={decisionFilter} onChange={(event) => setDecisionFilter(event.target.value as DecisionFilter)} className="rounded-md border border-slate-200 bg-white px-3 py-2 text-sm"><option value="all">All decisions</option><option value="allow">Allowed</option><option value="deny">Denied</option></select> : null}
          </div>

          {tab === "effective" ? (
            <div className="overflow-x-auto"><table className="w-full min-w-[900px] text-left text-xs"><thead className="border-b border-slate-200 text-slate-500"><tr><th className="p-3">Permission</th><th>Mode</th><th>Role</th><th>User override</th><th>Effective</th><th>Reason</th></tr></thead><tbody>
              {filteredPermissions.map((permission) => <tr key={permission.code} className="border-b border-slate-100"><td className="p-3"><p className="font-mono font-semibold text-slate-800">{permission.code}</p><p className="mt-1 text-slate-400">{permission.description}</p></td><td>{decisionBadge(permission.mode_allowed)}</td><td>{decisionBadge(permission.role_allowed)}</td><td className="font-semibold text-slate-600">{permission.user_override.toUpperCase()}</td><td>{decisionBadge(permission.effective_allowed)}</td><td className="text-slate-600">{reasonLabels[permission.reason]}</td></tr>)}
            </tbody></table>{!loading && filteredPermissions.length === 0 ? <p className="p-6 text-sm text-slate-500">No permissions match these filters.</p> : null}</div>
          ) : (
            <div className="overflow-x-auto"><table className="w-full min-w-[760px] text-left text-xs"><thead className="border-b border-slate-200 text-slate-500"><tr><th className="p-3">Code</th><th>Module</th><th>Action</th><th>Description</th><th>Sensitive</th></tr></thead><tbody>{registryRows.map((permission) => <tr key={permission.code} className="border-b border-slate-100"><td className="p-3 font-mono font-semibold">{permission.code}</td><td>{permission.module}</td><td>{permission.action}</td><td className="text-slate-500">{permission.description}</td><td>{permission.is_sensitive ? <ShieldCheck className="h-4 w-4 text-amber-500" /> : "-"}</td></tr>)}</tbody></table></div>
          )}
        </Card>
      ) : null}

      {tab === "mode" ? <Card className="overflow-x-auto"><table className="w-full min-w-[680px] text-left text-xs"><thead className="border-b border-slate-200 text-slate-500"><tr><th className="p-3">Permission</th>{modes.map((mode) => <th key={mode}>{mode}</th>)}</tr></thead><tbody>{registry.map((permission) => <tr key={permission.code} className="border-b border-slate-100"><td className="p-3 font-mono font-semibold">{permission.code}</td>{modes.map((mode) => <td key={mode}>{modeMatrices ? decisionBadge(modeMatrices[mode].permissions.find((item) => item.code === permission.code)?.mode_allowed ?? false) : "..."}</td>)}</tr>)}</tbody></table><p className="px-3 py-4 text-xs text-slate-500">Mode policy is read-only and enforced by FastAPI.</p></Card> : null}

      {tab === "roles" ? <Card className="space-y-5"><div className="flex items-center justify-between gap-3"><div><h2 className="font-semibold text-slate-900">{roleMatrix?.role.name || "Role"}</h2><p className="text-sm text-slate-500">{connectionMode === "SERVER" ? "Changes use the existing audited role-permission endpoint." : "Role permissions are read-only in CLIENT and SERVER_PC modes."}</p></div><Button type="button" loading={savingRole} disabled={connectionMode !== "SERVER"} onClick={() => void saveRolePermissions()}>Save role permissions</Button></div><div className="grid gap-4 lg:grid-cols-2">{Object.entries(groupByModule(roleMatrix?.permissions || [])).map(([module, permissions]) => <div key={module} className="rounded-lg border border-slate-200 p-4"><h3 className="mb-3 text-sm font-bold text-slate-800">{module}</h3><div className="space-y-2">{permissions.map((permission) => <label key={permission.code} className="flex items-center gap-2 text-sm text-slate-600"><input type="checkbox" disabled={connectionMode !== "SERVER"} checked={roleDraft.has(permission.code)} onChange={() => toggleRolePermission(permission.code)} /><span className="font-mono text-xs">{permission.code}</span></label>)}</div></div>)}</div></Card> : null}

      {tab === "overrides" ? <Card className="space-y-4"><div className="flex items-start gap-3 rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900"><AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" /><p>User ALLOW overrides cannot bypass a denied connection-mode policy. {connectionMode === "SERVER" ? "Changes use the existing audited three-state editor." : "Overrides are read-only in CLIENT and SERVER_PC modes."}</p></div>{selectedUserId && connectionMode === "SERVER" ? <UserPermissionMatrixEditor userId={selectedUserId} /> : <p className="text-sm text-slate-500">{selectedUserId ? "Switch to SERVER mode to edit user overrides." : "Select a user above to inspect override context."}</p>}</Card> : null}
    </div>
  );
};
