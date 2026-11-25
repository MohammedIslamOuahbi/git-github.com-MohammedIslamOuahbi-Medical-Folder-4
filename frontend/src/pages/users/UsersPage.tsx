import { Fragment, useCallback, useEffect, useMemo, useState } from "react";
import {
  Activity,
  Mail,
  ArrowRight,
  Pencil,
  Phone,
  Plus,
  ShieldCheck,
  Stethoscope,
  ToggleLeft,
  Trash2,
  UserCog,
  Users,
} from "lucide-react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { usersApi } from "@/api/usersApi";
import { Badge } from "@/components/common/Badge";
import { Button } from "@/components/common/Button";
import { Card } from "@/components/common/Card";
import { EmptyState } from "@/components/common/EmptyState";
import { Input } from "@/components/common/Input";
import { Modal } from "@/components/common/Modal";
import { Pagination } from "@/components/common/Pagination";
import { SearchInput } from "@/components/common/SearchInput";
import { SectionHeader } from "@/components/common/SectionHeader";
import { Select } from "@/components/common/Select";
import { usePaginatedResource } from "@/hooks/usePaginatedResource";
import { queueOfflineChange } from "@/services/localQueue";
import type { User } from "@/types/entities";
import { formatDisplayDate } from "@/utils/date";
import { mockUsers } from "@/utils/mockData";
import { cn } from "@/utils/cn";
import { getRoleBadgeClassName } from "@/features/users/userAccess";

type UserFormState = Partial<User> & {
  password?: string;
};

const defaultForm: UserFormState = {
  role: "Doctor",
  status: "active",
  qualification: "",
  password: "",
};

const formatDate = (value?: string | null) => {
  return formatDisplayDate(value) || "No activity";
};

const buildUserName = (user: Partial<User>) =>
  user.full_name || `${user.first_name || ""} ${user.last_name || ""}`.trim() || "Medical User";

const initialsFromUser = (user: Partial<User>) => {
  const first = user.first_name?.[0] || "";
  const last = user.last_name?.[0] || "";
  return `${first}${last}`.trim().toUpperCase() || "MU";
};

const normalizeUser = (user: Partial<User> & { is_active?: boolean | null }) =>
  ({
    ...user,
    full_name: buildUserName(user),
    status:
      user.status ||
      (typeof user.is_active === "boolean" ? (user.is_active ? "active" : "inactive") : "inactive"),
  }) as User;

const normalizeRoleKey = (role?: string | null) => (role || "").trim().toLowerCase().replace(/_/g, " ");

const getUsersTableRoleBadgeClassName = (role?: string | null) => {
  const roleKey = normalizeRoleKey(role);

  if (roleKey === "super admin") {
    return "border-emerald-200 bg-emerald-50 text-emerald-700";
  }
  if (roleKey === "admin") {
    return "border-cyan-200 bg-cyan-50 text-cyan-700";
  }
  if (roleKey === "doctor") {
    return "border-violet-200 bg-violet-50 text-violet-700";
  }
  if (roleKey === "assistant") {
    return "border-amber-200 bg-amber-50 text-amber-700";
  }

  return "border-slate-200 bg-slate-100 text-slate-700";
};

export const UsersPage = () => {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const loader = useCallback(usersApi.list, []);
  const { items, total, page, pageSize, search, loading, error, setPage, setSearch, setItems } =
    usePaginatedResource<User>(loader, mockUsers);
  const [modalOpen, setModalOpen] = useState(false);
  const [selectUserOpen, setSelectUserOpen] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<User | null>(null);
  const [deletePassword, setDeletePassword] = useState("");
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [expandedUserId, setExpandedUserId] = useState<number | null>(null);
  const [viewTarget, setViewTarget] = useState<User | null>(null);
  const [form, setForm] = useState<UserFormState>(defaultForm);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [roleFilter, setRoleFilter] = useState<"all" | User["role"]>("all");
  const [statusFilter, setStatusFilter] = useState<"all" | User["status"]>("all");
  const [pickerSearch, setPickerSearch] = useState("");
  const [formErrors, setFormErrors] = useState<Partial<Record<"first_name" | "last_name" | "email" | "password" | "qualification", string>>>({});

  const buildUserPayload = (currentForm: UserFormState) => {
    const payload: Record<string, unknown> = {
      first_name: currentForm.first_name,
      last_name: currentForm.last_name,
      phone: currentForm.phone,
      qualification: currentForm.role === "Doctor" ? currentForm.qualification?.trim() || null : null,
      role: currentForm.role,
      email: currentForm.email,
      is_active: (currentForm.status || "active") === "active",
    };

    if (currentForm.password?.trim()) {
      payload.password = currentForm.password.trim();
    }

    return payload;
  };

  const resetEditor = () => {
    setEditingId(null);
    setForm(defaultForm);
    setFormErrors({});
    setModalOpen(false);
  };

  const openCreateModal = () => {
    setEditingId(null);
    setForm(defaultForm);
    setFormErrors({});
    setViewTarget(null);
    setSelectUserOpen(false);
    setModalOpen(true);
  };

  const validateForm = () => {
    const errors: Partial<Record<"first_name" | "last_name" | "email" | "password" | "qualification", string>> = {};

    if (!form.first_name?.trim()) {
      errors.first_name = "First name is required.";
    }
    if (!form.last_name?.trim()) {
      errors.last_name = "Last name is required.";
    }
    if (!form.email?.trim()) {
      errors.email = "Email is required.";
    } else if (!/\S+@\S+\.\S+/.test(form.email.trim())) {
      errors.email = "Enter a valid email address.";
    }
    if (!editingId && !form.password?.trim()) {
      errors.password = "Password is required for new users.";
    }
    if (form.role === "Doctor" && !form.qualification?.trim()) {
      errors.qualification = "Qualification is required for doctors.";
    }

    setFormErrors(errors);
    return Object.keys(errors).length === 0;
  };

  useEffect(() => {
    if (searchParams.get("action") === "create") {
      openCreateModal();
      setSearchParams({}, { replace: true });
    }
    if (searchParams.get("action") === "edit") {
      setSelectUserOpen(true);
      setSearchParams({}, { replace: true });
    }
  }, [searchParams, setSearchParams]);

  const filteredItems = useMemo(
    () =>
      items
        .map((item) => normalizeUser(item as User & { is_active?: boolean | null }))
        .filter((item) => {
        const roleMatch = roleFilter === "all" || item.role === roleFilter;
        const statusMatch = statusFilter === "all" || item.status === statusFilter;
        return roleMatch && statusMatch;
      }),
    [items, roleFilter, statusFilter],
  );

  const pickerItems = useMemo(() => {
    const normalized = pickerSearch.trim().toLowerCase();
    const normalizedItems = items.map((item) => normalizeUser(item as User & { is_active?: boolean | null }));
    if (!normalized) return normalizedItems;
    return normalizedItems.filter((item) =>
      [
        buildUserName(item),
        item.email,
        item.role,
        item.phone || "",
      ]
        .join(" ")
        .toLowerCase()
        .includes(normalized),
    );
  }, [items, pickerSearch]);

  const normalizedUsers = useMemo(
    () => items.map((item) => normalizeUser(item as User & { is_active?: boolean | null })),
    [items],
  );

  const save = async () => {
    if (!validateForm()) return;
    const payload = buildUserPayload(form);
    try {
      if (editingId) {
        const updated = normalizeUser((await usersApi.update(editingId, payload)) as User & { is_active?: boolean | null });
        setItems((current) => current.map((item) => (item.id === editingId ? updated : item)));
      } else {
        const created = normalizeUser((await usersApi.create(payload)) as User & { is_active?: boolean | null });
        setItems((current) => [created, ...current]);
      }
    } catch {
      const offlineRecord = normalizeUser({
        ...form,
        id: editingId || Date.now(),
        full_name: buildUserName(form),
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      } as User);
      queueOfflineChange("users", offlineRecord as unknown as Record<string, unknown>);
      setItems((current) =>
        editingId
          ? current.map((item) => (item.id === editingId ? offlineRecord : item))
          : [offlineRecord, ...current],
      );
    } finally {
      resetEditor();
    }
  };

  const removeUser = async (row: User) => {
    if (!deletePassword.trim()) {
      setDeleteError("Please enter your password to remove this user.");
      return;
    }
    try {
      await usersApi.remove(row.id, { password: deletePassword });
    } catch {
      setDeleteError("Unable to remove this user. Please check your password and try again.");
      return;
    }
    setItems((current) => current.filter((item) => item.id !== row.id));
    setDeleteTarget(null);
    setDeletePassword("");
    setDeleteError(null);
    setExpandedUserId((current) => (current === row.id ? null : current));
  };

  const toggleUserStatus = async (row: User) => {
    const nextStatus: User["status"] = row.status === "active" ? "inactive" : "active";
    const payload = buildUserPayload({ ...row, status: nextStatus });

    try {
      const updated = normalizeUser((await usersApi.update(row.id, payload)) as User & { is_active?: boolean | null });
      setItems((current) => current.map((item) => (item.id === row.id ? updated : item)));
    } catch {
      const offlineRecord = {
        ...row,
        status: nextStatus,
        updated_at: new Date().toISOString(),
      } as User;
      queueOfflineChange("users", offlineRecord as unknown as Record<string, unknown>);
      setItems((current) => current.map((item) => (item.id === row.id ? offlineRecord : item)));
    } finally {
      setExpandedUserId((current) => (current === row.id ? row.id : current));
    }
  };

  const overview = useMemo(
    () => [
      {
        label: "Total Users",
        value: normalizedUsers.length,
        icon: Users,
        tone: "active",
      },
      {
        label: "Admins",
        value: normalizedUsers.filter((item) => {
          const role = normalizeRoleKey(item.role);
          return role === "admin" || role === "super admin";
        }).length,
        icon: ShieldCheck,
        tone: "completed",
      },
      {
        label: "Doctors",
        value: normalizedUsers.filter((item) => normalizeRoleKey(item.role) === "doctor").length,
        icon: Stethoscope,
        tone: "active",
      },
      {
        label: "Assistants",
        value: normalizedUsers.filter((item) => normalizeRoleKey(item.role) === "assistant").length,
        icon: UserCog,
        tone: "pending",
      },
      {
        label: "Active",
        value: normalizedUsers.filter((item) => item.status === "active").length,
        icon: Activity,
        tone: "active",
      },
      {
        label: "Inactive",
        value: normalizedUsers.filter((item) => item.status === "inactive").length,
        icon: Activity,
        tone: "inactive",
      },
    ],
    [normalizedUsers],
  );

  return (
    <div className="space-y-6">
      <SectionHeader
        eyebrow="Identity & access"
        title="Utilisateurs"
        description={error || "Manage administrators, doctors, and assistants with a complete user directory, role filters, and secure account actions."}
        actionLabel="New User"
        actionIcon={Plus}
        onAction={openCreateModal}
      />

      <div className="grid gap-4 grid-cols-2 grid-cols-3">
        {overview.map((item) => (
          <Card key={item.label} className="p-4">
            <div className="flex items-start justify-between gap-4">
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.14em] text-ink-400">
                  {item.label}
                </p>
                <p className="mt-3 text-2xl font-semibold text-navy-900">{item.value}</p>
              </div>
              <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-brand-50 text-brand-700 shadow-soft">
                <item.icon className="h-5 w-5" />
              </div>
            </div>
            <div className="mt-4">
              <Badge tone={item.tone}>Live data</Badge>
            </div>
          </Card>
        ))}
      </div>

      <div className="space-y-6">
        <Card className="">
          <div className="gap-3 grid grid-cols-[minmax(0,1fr)_180px_180px_auto]">
            <SearchInput value={search} onChange={setSearch} placeholder="Search by name, email, role, or phone..." />
            <Select
              options={[
                { label: "All Roles", value: "all" },
                { label: "Admin", value: "Admin" },
                { label: "Doctor", value: "Doctor" },
                { label: "Assistant", value: "Assistant" },
              ]}
              value={roleFilter}
              onChange={(event) => setRoleFilter(event.target.value as "all" | User["role"])}
            />
            <Select
              options={[
                { label: "All Statuses", value: "all" },
                { label: "Active", value: "active" },
                { label: "Inactive", value: "inactive" },
              ]}
              value={statusFilter}
              onChange={(event) => setStatusFilter(event.target.value as "all" | User["status"])}
            />
            <Button
              variant="ghost"
              onClick={() => {
                setSearch("");
                setRoleFilter("all");
                setStatusFilter("all");
              }}
            >
              Reset
            </Button>
          </div>
        </Card>

        <Card className="overflow-hidden p-0">
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-ink-100 bg-white/70 px-5 py-4">
            <div>
              <h3 className="text-lg font-semibold text-navy-900">Répertoire des utilisateurs</h3>
              <p className="mt-1 text-sm text-ink-500">
                {filteredItems.length} visible user{filteredItems.length === 1 ? "" : "s"} in the current view.
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              <Button
                variant="secondary"
                icon={Pencil}
                onClick={() => setSelectUserOpen(true)}
              >
                Edit User
              </Button>
              <Button
                icon={Plus}
                onClick={openCreateModal}
              >
                Create User
              </Button>
            </div>
          </div>
          <div className="overflow-x-auto bg-white/80">
            <table className="min-w-full divide-y divide-ink-100">
              <thead className="bg-ink-50">
                <tr>
                  <th className="px-3 py-3 text-left text-xs font-semibold uppercase tracking-[0.2em] text-ink-500">User</th>
                  <th className="px-3 py-3 text-left text-xs font-semibold uppercase tracking-[0.2em] text-ink-500">E-mail</th>
                  <th className="px-3 py-3 text-left text-xs font-semibold uppercase tracking-[0.2em] text-ink-500">Rôle</th>
                  <th className="px-3 py-3 text-left text-xs font-semibold uppercase tracking-[0.2em] text-ink-500">État</th>
                  <th className="px-3 py-3 text-left text-xs font-semibold uppercase tracking-[0.2em] text-ink-500">Updated</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-ink-100 bg-white">
                {loading ? (
                  <tr>
                    <td colSpan={5} className="px-3 py-10 text-center text-sm text-ink-500">Chargement des utilisateurs...</td>
                  </tr>
                ) : filteredItems.length === 0 ? (
                  <tr>
                    <td colSpan={5} className="p-6">
                      <EmptyState
                        title="No users found"
                        description="Try a different search or filter, or create a new user."
                      />
                    </td>
                  </tr>
                ) : (
                  filteredItems.map((row) => {
                    const expanded = expandedUserId === row.id;
                    return (
                      <Fragment key={row.id}>
                        <tr
                          onClick={() => setExpandedUserId((current) => (current === row.id ? null : row.id))}
                          className="cursor-pointer transition hover:bg-ink-50/60"
                        >
                          <td className="px-3 py-2">
                            <div className="flex items-center gap-2 text-left">
                              <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-brand-100 text-sm font-semibold text-brand-800">
                                {initialsFromUser(row)}
                              </div>
                              <div>
                                <p className="font-semibold text-navy-900">{buildUserName(row)}</p>
                                <div className="mt-1 flex items-center gap-2 text-xs text-ink-500">
                                  <Phone className="h-3.5 w-3.5" />
                                  <span>{row.phone || "No phone number"}</span>
                                </div>
                              </div>
                            </div>
                          </td>
                          <td className="px-3 py-2">
                            <div className="flex items-center gap-1 text-sm text-ink-700">
                              <Mail className="h-4 w-4 text-ink-400" />
                              <span>{row.email}</span>
                            </div>
                          </td>
                          <td className="px-3 py-2">
                            <span
                              className={cn(
                                "inline-flex items-center rounded-full border px-2.5 py-1 text-[10px] font-black uppercase tracking-[0.14em] shadow-sm",
                                getUsersTableRoleBadgeClassName(row.role),
                              )}
                            >
                              {row.role}
                            </span>
                          </td>
                          <td className="px-3 py-2">
                            <div className="flex items-center justify-center">
                              <span
                                className={
                                  row.status === "active"
                                    ? "h-3 w-3 rounded-full bg-emerald-500 shadow-[0_0_0_4px_rgba(16,185,129,0.12)]"
                                    : "h-3 w-3 rounded-full bg-rose-500 shadow-[0_0_0_4px_rgba(244,63,94,0.12)]"
                                }
                              />
                            </div>
                          </td>
                          <td className="px-3 py-2 text-sm text-ink-700">{formatDate(row.updated_at)}</td>
                        </tr>
                        {expanded ? (
                          <tr className="bg-brand-50/35">
                            <td colSpan={5} className="px-3 py-3">
                              <div className="flex flex-wrap items-center gap-2">
                                <Button
                                  variant="secondary"
                                  size="sm"
                                  icon={UserCog}
                                  onClick={(event) => {
                                    event.stopPropagation();
                                    setViewTarget(row);
                                  }}
                                >
                                  View Details
                                </Button>
                                <Button
                                  variant="secondary"
                                  size="sm"
                                  icon={ArrowRight}
                                  onClick={(event) => {
                                    event.stopPropagation();
                                    navigate(`/users/${row.id}/edit`);
                                  }}
                                >
                                  Edit Permissions
                                </Button>
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  icon={Mail}
                                  onClick={(event) => {
                                    event.stopPropagation();
                                    window.location.href = `mailto:${row.email}`;
                                  }}
                                >
                                  Email User
                                </Button>
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  icon={ToggleLeft}
                                  onClick={(event) => {
                                    event.stopPropagation();
                                    void toggleUserStatus(row);
                                  }}
                                >
                                  {row.status === "active" ? "Deactivate User" : "Activate User"}
                                </Button>
                                <Button
                                  variant="danger"
                                  size="sm"
                                  icon={Trash2}
                                  onClick={(event) => {
                                    event.stopPropagation();
                                    setDeleteTarget(row);
                                    setDeletePassword("");
                                    setDeleteError(null);
                                  }}
                                >
                                  Delete User
                                </Button>
                              </div>
                            </td>
                          </tr>
                        ) : null}
                      </Fragment>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
        </Card>

        <Pagination page={page} total={total} pageSize={pageSize} onPageChange={setPage} />
      </div>

      <Modal
        open={modalOpen}
        title={editingId ? "Edit User Profile" : "Create User"}
        onClose={resetEditor}
      >
        <div className="space-y-4">
          <div className="grid gap-2 grid-cols-3">
            <div className="rounded-2xl border border-slate-200/80 bg-white/70 px-4 py-3">
              <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-ink-400">Profil d'accès</p>
              <p className="mt-2 text-sm font-medium text-navy-900">
                {editingId ? "Update identity and access details." : "Create a new medical operations account."}
              </p>
            </div>
            <div className="rounded-2xl border border-slate-200/80 bg-white/70 px-4 py-3">
              <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-ink-400">Rôle</p>
              <p className="mt-2 text-sm font-medium text-navy-900">{form.role || "Doctor"}</p>
            </div>
            <div className="rounded-2xl border border-slate-200/80 bg-white/70 px-4 py-3">
              <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-ink-400">État</p>
              <p className="mt-2 text-sm font-medium capitalize text-navy-900">{form.status || "active"}</p>
            </div>
          </div>

          <div>
            <h4 className="text-base font-semibold text-navy-900">Identity Information</h4>
            <div className="mt-3 grid gap-3 grid-cols-3">
              <Input
                label="First Name"
                error={formErrors.first_name || null}
                value={form.first_name || ""}
                onChange={(event) => setForm((current) => ({ ...current, first_name: event.target.value }))}
              />
              <Input
                label="Last Name"
                error={formErrors.last_name || null}
                value={form.last_name || ""}
                onChange={(event) => setForm((current) => ({ ...current, last_name: event.target.value }))}
              />
              <Input
                label="Phone Number"
                value={form.phone || ""}
                onChange={(event) => setForm((current) => ({ ...current, phone: event.target.value }))}
              />
              {form.role === "Doctor" ? (
                <Input
                  label="Qualification"
                  error={formErrors.qualification || null}
                  value={form.qualification || ""}
                  onChange={(event) => setForm((current) => ({ ...current, qualification: event.target.value }))}
                />
              ) : null}
              <Input
                label="Email"
                type="email"
                error={formErrors.email || null}
                value={form.email || ""}
                onChange={(event) => setForm((current) => ({ ...current, email: event.target.value }))}
                className={form.role === "Doctor" ? "" : "col-span-3"}
              />
            </div>
          </div>

          <div>
            <h4 className="text-base font-semibold text-navy-900">Access & Security</h4>
            <div className="mt-3 grid gap-3 grid-cols-3">
              <Select
                label="Role"
                options={[
                  { label: "Admin", value: "Admin" },
                  { label: "Doctor", value: "Doctor" },
                  { label: "Assistant", value: "Assistant" },
                ]}
                value={form.role || "Doctor"}
                onChange={(event) =>
                  setForm((current) => ({
                    ...current,
                    role: event.target.value as User["role"],
                    qualification: event.target.value === "Doctor" ? current.qualification || "" : "",
                  }))
                }
              />
              <Select
                label="Status"
                options={[
                  { label: "Active", value: "active" },
                  { label: "Inactive", value: "inactive" },
                ]}
                value={form.status || "active"}
                onChange={(event) => setForm((current) => ({ ...current, status: event.target.value as User["status"] }))}
              />
              <Input
                label="Mot de passe"
                type="password"
                error={formErrors.password || null}
                value={form.password || ""}
                onChange={(event) => setForm((current) => ({ ...current, password: event.target.value }))}
                placeholder={editingId ? "Leave blank to keep current password" : "Enter password"}
              />
            </div>
          </div>

          <div className="flex justify-end gap-2">
            <Button variant="ghost" onClick={resetEditor}>
              Cancel
            </Button>
            <Button onClick={() => void save()}>{editingId ? "Update User" : "Create User"}</Button>
          </div>
        </div>
      </Modal>

      <Modal
        open={Boolean(viewTarget)}
        title="User Details"
        onClose={() => setViewTarget(null)}
      >
        {viewTarget ? (
          <div className="space-y-5">
            <div className="flex items-center gap-4">
              <div className="flex h-14 w-14 items-center justify-center rounded-3xl bg-brand-100 text-lg font-semibold text-brand-800">
                {initialsFromUser(viewTarget)}
              </div>
              <div>
                <p className="text-lg font-semibold text-navy-900">{buildUserName(viewTarget)}</p>
                <div className="mt-2 flex flex-wrap items-center gap-2">
                  <span
                    className={cn(
                      "inline-flex items-center rounded-full border px-2.5 py-1 text-[10px] font-black uppercase tracking-[0.14em] shadow-sm",
                      getRoleBadgeClassName(viewTarget.role),
                    )}
                  >
                    {viewTarget.role}
                  </span>
                  <Badge tone={viewTarget.status}>{viewTarget.status}</Badge>
                </div>
              </div>
            </div>

            <div className="grid gap-3 grid-cols-2">
              <div className="rounded-2xl border border-slate-200/80 bg-white/70 px-4 py-3">
                <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-ink-400">First Name</p>
                <p className="text-sm font-medium text-navy-900">{viewTarget.first_name || "-"}</p>
              </div>
              <div className="rounded-2xl border border-slate-200/80 bg-white/70 px-4 py-3">
                <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-ink-400">Last Name</p>
                <p className="text-sm font-medium text-navy-900">{viewTarget.last_name || "-"}</p>
              </div>
              <div className="rounded-2xl border border-slate-200/80 bg-white/70 px-4 py-3">
                <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-ink-400">E-mail</p>
                <p className="text-sm font-medium text-navy-900">{viewTarget.email || "-"}</p>
              </div>
              <div className="rounded-2xl border border-slate-200/80 bg-white/70 px-4 py-3">
                <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-ink-400">Téléphone</p>
                <p className="text-sm font-medium text-navy-900">{viewTarget.phone || "Not provided"}</p>
              </div>
              {viewTarget.role === "Doctor" ? (
                <div className="rounded-2xl border border-slate-200/80 bg-white/70 px-4 py-3">
                  <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-ink-400">Qualification</p>
                  <p className="text-sm font-medium text-navy-900">{viewTarget.qualification || "-"}</p>
                </div>
              ) : null}
              <div className="rounded-2xl border border-slate-200/80 bg-white/70 px-4 py-3">
                <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-ink-400">Created</p>
                <p className="text-sm font-medium text-navy-900">{formatDate(viewTarget.created_at)}</p>
              </div>
              <div className="rounded-2xl border border-slate-200/80 bg-white/70 px-4 py-3">
                <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-ink-400">Updated</p>
                <p className="text-sm font-medium text-navy-900">{formatDate(viewTarget.updated_at)}</p>
              </div>
            </div>

            <div className="flex justify-end gap-3">
              <Button variant="ghost" onClick={() => setViewTarget(null)}>
                Close
              </Button>
              <Button
                variant="secondary"
                icon={Pencil}
                onClick={() => {
                  navigate(`/users/${viewTarget.id}/edit`);
                }}
              >
                Edit User
              </Button>
            </div>
          </div>
        ) : null}
      </Modal>

      <Modal
        open={selectUserOpen}
        title="Select User To Edit"
        onClose={() => {
          setSelectUserOpen(false);
          setPickerSearch("");
        }}
      >
        <div className="space-y-4">
          <SearchInput
            value={pickerSearch}
            onChange={setPickerSearch}
            placeholder="Search user to edit..."
          />
          <div className="max-h-[26rem] space-y-2 overflow-y-auto pr-1">
            {pickerItems.map((item) => (
              <button
                key={item.id}
                type="button"
                onClick={() => {
                  setPickerSearch("");
                  setSelectUserOpen(false);
                  navigate(`/users/${item.id}/edit`);
                }}
                className="block w-full rounded-xl border border-slate-200/80 bg-white/70 px-4 py-3 text-left transition hover:border-brand-200 hover:bg-brand-50"
              >
                <p className="text-sm font-semibold text-navy-900">{buildUserName(item)}</p>
                <p className="mt-1 text-xs text-ink-500">
                  {item.email} | {item.role} | {item.status}
                </p>
              </button>
            ))}
            {!pickerItems.length && (
              <EmptyState
                title="No matching users"
                description="Try a different search term to find the user you want to edit."
              />
            )}
          </div>
        </div>
      </Modal>

      <Modal
        open={Boolean(deleteTarget)}
        title="Delete User"
        onClose={() => {
          setDeleteTarget(null);
          setDeletePassword("");
          setDeleteError(null);
        }}
      >
        <div className="space-y-6">
          <div className="rounded-2xl border border-rose-200/80 bg-rose-50/70 px-4 py-4">
            <p className="text-sm font-medium leading-6 text-rose-700">
              You are about to remove{" "}
              <span className="font-semibold">{deleteTarget ? buildUserName(deleteTarget) : "this user"}</span>.
              This action will remove the account from the current view immediately.
            </p>
          </div>
          <Input
            label="Mot de passe"
            type="password"
            error={deleteError}
            value={deletePassword}
            onChange={(event) => {
              setDeletePassword(event.target.value);
              if (deleteError) setDeleteError(null);
            }}
          />
          <div className="flex justify-end gap-3">
            <Button variant="ghost" onClick={() => {
              setDeleteTarget(null);
              setDeletePassword("");
              setDeleteError(null);
            }}>
              Cancel
            </Button>
            <Button
              variant="danger"
              icon={Trash2}
              onClick={() => {
                if (deleteTarget) {
                  void removeUser(deleteTarget);
                }
              }}
            >
              Delete User
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
};
