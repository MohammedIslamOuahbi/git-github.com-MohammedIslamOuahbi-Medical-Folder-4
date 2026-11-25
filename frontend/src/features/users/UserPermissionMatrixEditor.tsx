import { useEffect, useMemo, useState } from "react";

import { AlertTriangle } from "lucide-react";

import { permissionsApi } from "@/api/permissionsApi";
import { Button } from "@/components/common/Button";
import { Card } from "@/components/common/Card";
import { Modal } from "@/components/common/Modal";
import type { EffectivePermission, PermissionOverrideState, UserPermissionMatrix } from "@/types/permissions";

const buildDraftFromMatrix = (
  result: UserPermissionMatrix,
): Record<string, PermissionOverrideState> =>
  Object.fromEntries(
    result.permissions.map((permission) => [
      permission.code,
      (permission.override ?? "inherit") as PermissionOverrideState,
    ]),
  ) as Record<string, PermissionOverrideState>;

const isPermissionSelected = (
  permission: EffectivePermission,
  state: PermissionOverrideState,
) => {
  if (state === "allow") return true;
  if (state === "deny") return false;
  return permission.role_allowed;
};

const getNextOverrideState = (
  permission: EffectivePermission,
  selected: boolean,
) => (selected ? (permission.role_allowed ? "inherit" : "allow") : permission.role_allowed ? "deny" : "inherit");

export const UserPermissionMatrixEditor = ({ userId }: { userId: string | number }) => {
  const [matrix, setMatrix] = useState<UserPermissionMatrix | null>(null);
  const [draft, setDraft] = useState<Record<string, PermissionOverrideState>>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [confirmSensitive, setConfirmSensitive] = useState(false);

  useEffect(() => {
    let mounted = true;

    const load = async () => {
      setLoading(true);
      try {
        const result = await permissionsApi.getUserPermissions(userId);
        if (!mounted) return;
        setMatrix(result);
        setDraft(buildDraftFromMatrix(result));
        setError(null);
      } catch (loadError) {
        if (!mounted) return;
        setError(loadError instanceof Error ? loadError.message : "Unable to load permission matrix.");
      } finally {
        if (mounted) {
          setLoading(false);
        }
      }
    };

    void load();
    return () => {
      mounted = false;
    };
  }, [userId]);

  const changedItems = useMemo(() => {
    if (!matrix) return [];
    return matrix.permissions
      .map((permission) => ({
        code: permission.code,
        name: permission.name,
        previous: permission.override ?? "inherit",
        next: draft[permission.code] ?? "inherit",
        isSensitive: permission.is_sensitive,
      }))
      .filter((item) => item.previous !== item.next);
  }, [draft, matrix]);

  useEffect(() => {
    if (!changedItems.length) return undefined;
    const handleBeforeUnload = (event: BeforeUnloadEvent) => {
      event.preventDefault();
      event.returnValue = "";
    };
    window.addEventListener("beforeunload", handleBeforeUnload);
    return () => window.removeEventListener("beforeunload", handleBeforeUnload);
  }, [changedItems.length]);

  const permissionGroups = useMemo(() => {
    if (!matrix) return [];

    const groups = matrix.permissions.reduce<
      Array<{
        key: string;
        label: string;
        permissions: EffectivePermission[];
      }>
    >((accumulator, permission) => {
      const key = permission.category || permission.module;
      const existingGroup = accumulator.find((group) => group.key === key);
      if (existingGroup) {
        existingGroup.permissions.push(permission);
        return accumulator;
      }

      accumulator.push({
        key,
        label: key,
        permissions: [permission],
      });
      return accumulator;
    }, []);

    return groups;
  }, [matrix]);

  const selectedPermissionCount = useMemo(
    () =>
      matrix
        ? matrix.permissions.filter((permission) =>
            isPermissionSelected(permission, draft[permission.code] ?? "inherit"),
          ).length
        : 0,
    [draft, matrix],
  );

  const canBulkSelect = useMemo(
    () => Boolean(matrix?.permissions.some((permission) => permission.can_manage)),
    [matrix],
  );

  const sensitiveChanges = changedItems.filter((item) => item.isSensitive);

  const updatePermissionState = (permission: EffectivePermission, selected: boolean) => {
    setDraft((current) => ({
      ...current,
      [permission.code]: getNextOverrideState(permission, selected),
    }));
  };

  const updateGroupState = (
    permissions: EffectivePermission[],
    selected: boolean,
  ) => {
    setDraft((current) => {
      const nextDraft = { ...current };
      permissions.forEach((permission) => {
        if (!permission.can_manage) return;
        nextDraft[permission.code] = getNextOverrideState(permission, selected);
      });
      return nextDraft;
    });
  };

  const updateAllPermissions = (selected: boolean) => {
    if (!matrix) return;
    updateGroupState(matrix.permissions, selected);
  };

  const saveChanges = async () => {
    if (!changedItems.length) return;
    if (sensitiveChanges.length > 0 && !confirmSensitive) {
      setConfirmSensitive(true);
      return;
    }

    setSaving(true);
    try {
      const result = await permissionsApi.updateUserPermissions(userId, {
        permissions: changedItems.map((item) => ({
          permission_code: item.code,
          state: item.next,
        })),
      });
      setMatrix(result);
      setDraft(buildDraftFromMatrix(result));
      setError(null);
      setConfirmSensitive(false);
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : "Unable to save permission changes.");
    } finally {
      setSaving(false);
    }
  };

  const cancelChanges = () => {
    if (!matrix) return;
    setDraft(buildDraftFromMatrix(matrix));
    setConfirmSensitive(false);
  };

  if (loading) {
    return (
      <Card className="space-y-5">
        <div className="space-y-2">
          <div className="h-6 w-40 animate-pulse rounded bg-slate-200" />
          <div className="h-4 w-72 max-w-full animate-pulse rounded bg-slate-100" />
        </div>
        <div className="h-10 w-48 animate-pulse rounded bg-slate-100" />
        <div className="grid gap-3 sm:grid-cols-2">
          {Array.from({ length: 4 }).map((_, index) => (
            <div key={`permission-group-skeleton-${index}`} className="rounded-xl border border-slate-200 bg-white p-4">
              <div className="mb-4 flex items-center justify-between">
                <div className="h-4 w-28 animate-pulse rounded bg-slate-200" />
                <div className="h-4 w-10 animate-pulse rounded bg-slate-100" />
              </div>
              <div className="space-y-2">
                {Array.from({ length: 4 }).map((_, rowIndex) => (
                  <div key={`permission-row-skeleton-${index}-${rowIndex}`} className="flex items-center gap-3 rounded-lg px-2 py-2">
                    <div className="h-4 w-4 animate-pulse rounded border border-slate-200 bg-slate-100" />
                    <div className="h-4 flex-1 animate-pulse rounded bg-slate-100" />
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      </Card>
    );
  }

  if (!matrix) {
    return (
      <Card>
        <div className="rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
          {error || "Permission matrix unavailable."}
        </div>
      </Card>
    );
  }

  return (
    <>
      <Card className="space-y-5">
        <div className="space-y-1">
          <h3 className="text-lg font-semibold text-slate-950">Autorisations</h3>
          <p className="text-sm text-slate-500">
            Selectionnez les fonctions accessibles a cet utilisateur.
          </p>
        </div>

        {matrix.is_last_active_super_admin ? (
          <div className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
            Minimum recovery permissions are protected for the last active Super Admin.
          </div>
        ) : null}

        {error ? (
          <div className="rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
            {error}
          </div>
        ) : null}

        <div className="flex flex-col gap-3 rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
          <p className="text-sm font-medium text-slate-700">
            {selectedPermissionCount} autorisations selectionnees
          </p>

          {canBulkSelect ? (
            <div className="flex flex-col gap-2 sm:flex-row">
              <Button variant="ghost" size="sm" type="button" onClick={() => updateAllPermissions(true)}>
                Tout selectionner
              </Button>
              <Button variant="ghost" size="sm" type="button" onClick={() => updateAllPermissions(false)}>
                Tout deselectionner
              </Button>
            </div>
          ) : null}
        </div>

        {permissionGroups.length ? (
          <div className="grid gap-3 sm:grid-cols-1">
            {permissionGroups.map((group) => {
              const selectedCount = group.permissions.filter((permission) =>
                isPermissionSelected(permission, draft[permission.code] ?? "inherit"),
              ).length;
              const manageablePermissions = group.permissions.filter((permission) => permission.can_manage);
              const allManageableSelected =
                manageablePermissions.length > 0 &&
                manageablePermissions.every((permission) =>
                  isPermissionSelected(permission, draft[permission.code] ?? "inherit"),
                );

              return (
                <div key={group.key} className="rounded-xl border border-slate-200 bg-white p-4">
                  <div className="mb-3 flex items-center justify-between gap-3">
                    <h3 className="text-sm font-semibold text-slate-900">{group.label}</h3>
                    <span className="text-xs text-slate-500">
                      {selectedCount}/{group.permissions.length}
                    </span>
                  </div>

                  {manageablePermissions.length ? (
                    <label className="mb-3 flex cursor-pointer items-center gap-2 px-1 text-xs text-slate-500">
                      <input
                        type="checkbox"
                        checked={allManageableSelected}
                        onChange={(event) => updateGroupState(group.permissions, event.target.checked)}
                        className="h-4 w-4 rounded border-slate-300"
                      />
                      <span>Selectionner le groupe</span>
                    </label>
                  ) : null}

                  <div className="space-y-1">
                    {group.permissions.map((permission) => {
                      const isSelected = isPermissionSelected(
                        permission,
                        draft[permission.code] ?? "inherit",
                      );

                      return (
                        <label
                          key={permission.code}
                          className="flex cursor-pointer items-start gap-3 rounded-lg px-2 py-2 hover:bg-slate-50"
                          title={permission.code}
                        >
                          <input
                            type="checkbox"
                            checked={isSelected}
                            disabled={!permission.can_manage}
                            onChange={(event) => updatePermissionState(permission, event.target.checked)}
                            className="mt-0.5 h-4 w-4 rounded border-slate-300"
                          />

                          <span className="min-w-0 text-sm font-medium text-slate-700">
                            {permission.name}
                          </span>
                        </label>
                      );
                    })}
                  </div>
                </div>
              );
            })}
          </div>
        ) : (
          <div className="rounded-xl border border-dashed border-slate-200 px-4 py-6 text-sm text-slate-500">
            Aucune autorisation disponible.
          </div>
        )}

        <div className="flex flex-col gap-3 border-t border-slate-200 pt-4 sm:flex-row sm:justify-end">
          <Button variant="ghost" type="button" onClick={cancelChanges} disabled={!changedItems.length || saving}>
            Annuler
          </Button>
          <Button type="button" loading={saving} disabled={!changedItems.length} onClick={() => void saveChanges()}>
            Enregistrer les autorisations
          </Button>
        </div>
      </Card>

      <Modal
        open={confirmSensitive}
        title="Confirm sensitive permission changes"
        onClose={() => setConfirmSensitive(false)}
      >
        <div className="space-y-5">
          <div className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-4 text-sm text-amber-900">
            <div className="flex items-start gap-3">
              <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0" />
              <p>These changes include sensitive permissions and need explicit confirmation.</p>
            </div>
          </div>

          <div className="space-y-2">
            {sensitiveChanges.map((change) => (
              <div key={change.code} className="rounded-xl border border-slate-200 px-3 py-3 text-sm">
                <p className="font-semibold text-slate-900">{change.name}</p>
                <p className="mt-1 text-xs uppercase tracking-[0.12em] text-slate-500">{change.code}</p>
                <p className="mt-1 text-slate-600">
                  {change.previous} {"->"} {change.next}
                </p>
              </div>
            ))}
          </div>

          <div className="flex justify-end gap-3">
            <Button variant="ghost" onClick={() => setConfirmSensitive(false)}>
              Cancel
            </Button>
            <Button variant="danger" loading={saving} onClick={() => void saveChanges()}>
              Confirm save
            </Button>
          </div>
        </div>
      </Modal>
    </>
  );
};
