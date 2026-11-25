import { useEffect, useMemo, useState } from "react";
import {
  Activity,
  AlertCircle,
  ArrowLeft,
  BadgeCheck,
  CalendarDays,
  KeyRound,
  Mail,
  Phone,
  Save,
  ShieldCheck,
  UserRound,
  UsersRound,
} from "lucide-react";
import { useNavigate, useParams } from "react-router-dom";

import { usersApi } from "@/api/usersApi";
import { Button } from "@/components/common/Button";
import { Card } from "@/components/common/Card";
import { Input } from "@/components/common/Input";
import { Select } from "@/components/common/Select";
import { UserPermissionMatrixEditor } from "@/features/users/UserPermissionMatrixEditor";
import { getRoleBadgeClassName } from "@/features/users/userAccess";
import type { Role } from "@/types/common";
import type { User } from "@/types/entities";
import { cn } from "@/utils/cn";
import { formatDisplayDate } from "@/utils/date";
import { mockUsers } from "@/utils/mockData";

type UserFormState = Partial<User> & {
  password?: string;
};

type FormErrorKey =
  | "first_name"
  | "last_name"
  | "email"
  | "qualification";

const normalizeUser = (
  user: Partial<User> & { is_active?: boolean | null },
) =>
  ({
    ...user,
    full_name:
      user.full_name ||
      `${user.first_name || ""} ${user.last_name || ""}`.trim() ||
      "Medical User",
    status:
      user.status ||
      (typeof user.is_active === "boolean"
        ? user.is_active
          ? "active"
          : "inactive"
        : "inactive"),
  }) as User;

const formatDate = (value?: string | null) =>
  formatDisplayDate(value) || "—";

const buildUserPayload = (currentForm: UserFormState) => {
  const role = (currentForm.role || "Doctor") as Role;

  const payload: Record<string, unknown> = {
    first_name: currentForm.first_name,
    last_name: currentForm.last_name,
    phone: currentForm.phone,
    qualification:
      role === "Doctor"
        ? currentForm.qualification?.trim() || null
        : null,
    role,
    email: currentForm.email,
    is_active: (currentForm.status || "active") === "active",
  };

  if (currentForm.password?.trim()) {
    payload.password = currentForm.password.trim();
  }

  return payload;
};

const roleDescriptions: Record<Role, string> = {
  "Super Admin":
    "Accès global à l'administration et à la configuration du système.",
  Admin:
    "Gestion opérationnelle selon les autorisations attribuées.",
  Doctor:
    "Accès aux fonctions médicales et aux dossiers autorisés.",
  Assistant:
    "Accès aux tâches d'assistance et aux fonctions autorisées.",
};

/* ─── Loading Skeleton ─── */
const LoadingSkeleton = () => (
  <div className="space-y-8" aria-label="Chargement du profil utilisateur">
    <div className="flex items-center gap-4">
      <div className="h-10 w-10 animate-pulse rounded-xl bg-slate-200" />
      <div className="h-8 w-64 animate-pulse rounded-lg bg-slate-200" />
    </div>

    <div className="grid gap-8 lg:grid-cols-[1fr_380px]">
      <div className="space-y-6">
        {[1, 2].map((item) => (
          <div
            key={item}
            className="rounded-2xl border border-slate-100 bg-white p-6 shadow-sm"
          >
            <div className="animate-pulse space-y-6">
              <div className="flex items-center gap-3">
                <div className="h-8 w-8 rounded-lg bg-slate-200" />
                <div className="space-y-2">
                  <div className="h-4 w-40 rounded bg-slate-200" />
                  <div className="h-3 w-56 rounded bg-slate-100" />
                </div>
              </div>
              <div className="grid gap-5 md:grid-cols-2">
                {[1, 2, 3, 4].map((field) => (
                  <div key={field} className="space-y-2">
                    <div className="h-3 w-20 rounded bg-slate-200" />
                    <div className="h-11 rounded-xl bg-slate-100" />
                  </div>
                ))}
              </div>
            </div>
          </div>
        ))}
      </div>

      <div className="space-y-6">
        <div className="rounded-2xl border border-slate-100 bg-white p-6 shadow-sm">
          <div className="animate-pulse space-y-5">
            <div className="h-5 w-32 rounded bg-slate-200" />
            <div className="h-16 w-16 rounded-2xl bg-slate-200" />
            {[1, 2, 3, 4].map((row) => (
              <div
                key={row}
                className="flex items-center justify-between border-t border-slate-50 pt-4"
              >
                <div className="h-3 w-24 rounded bg-slate-100" />
                <div className="h-3 w-28 rounded bg-slate-200" />
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  </div>
);

export const UserEditorPage = () => {
  const navigate = useNavigate();
  const { userId } = useParams<{ userId: string }>();

  const [form, setForm] = useState<UserFormState | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [formErrors, setFormErrors] = useState<
    Partial<Record<FormErrorKey, string>>
  >({});

  useEffect(() => {
    let active = true;

    const loadUser = async () => {
      if (!userId) {
        setError("Utilisateur introuvable.");
        setLoading(false);
        return;
      }

      try {
        const fetched = normalizeUser(
          (await usersApi.get(userId)) as User & {
            is_active?: boolean | null;
          },
        );

        if (!active) return;

        setForm({
          ...fetched,
          password: "",
        });
        setError(null);
      } catch {
        const fallback = mockUsers.find(
          (item) => String(item.id) === String(userId),
        );

        if (!active) return;

        if (!fallback) {
          setError("Impossible de charger cet utilisateur.");
          setForm(null);
        } else {
          setForm({
            ...normalizeUser(
              fallback as User & { is_active?: boolean | null },
            ),
            password: "",
          });
          setError(null);
        }
      } finally {
        if (active) {
          setLoading(false);
        }
      }
    };

    void loadUser();

    return () => {
      active = false;
    };
  }, [userId]);

  const fullName = useMemo(() => {
    if (!form) return "Utilisateur";

    return (
      `${form.first_name || ""} ${form.last_name || ""}`.trim() ||
      form.full_name ||
      "Utilisateur"
    );
  }, [form]);

  const initials = useMemo(() => {
    if (!form) return "U";

    const firstInitial = form.first_name?.trim().charAt(0) || "";
    const lastInitial = form.last_name?.trim().charAt(0) || "";

    return `${firstInitial}${lastInitial}`.toUpperCase() || "U";
  }, [form]);

  const role = (form?.role || "Doctor") as Role;
  const isActive = (form?.status || "active") === "active";

  const validateForm = () => {
    if (!form) return false;

    const errors: Partial<Record<FormErrorKey, string>> = {};

    if (!form.first_name?.trim()) {
      errors.first_name = "Le prénom est obligatoire.";
    }

    if (!form.last_name?.trim()) {
      errors.last_name = "Le nom est obligatoire.";
    }

    if (!form.email?.trim()) {
      errors.email = "L'adresse e-mail est obligatoire.";
    } else if (!/\S+@\S+\.\S+/.test(form.email.trim())) {
      errors.email = "Saisissez une adresse e-mail valide.";
    }

    if (
      form.role === "Doctor" &&
      !form.qualification?.trim()
    ) {
      errors.qualification =
        "La qualification est obligatoire pour un médecin.";
    }

    setFormErrors(errors);

    return Object.keys(errors).length === 0;
  };

  const handleSave = async () => {
    if (!form || !userId || !validateForm()) return;

    setSaving(true);
    setError(null);

    try {
      await usersApi.update(userId, buildUserPayload(form));
      navigate("/users");
    } catch {
      setError(
        "Impossible d'enregistrer les modifications pour le moment.",
      );
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return <LoadingSkeleton />;
  }

  if (!form) {
    return (
      <div className="mx-auto max-w-xl pt-12">
        <Card>
          <div
            role="alert"
            className="flex flex-col items-center gap-5 p-2 text-center sm:flex-row sm:text-left"
          >
            <div className="flex h-14 w-14 shrink-0 items-center justify-center rounded-2xl bg-rose-100 text-rose-600">
              <AlertCircle className="h-7 w-7" />
            </div>

            <div className="min-w-0 flex-1">
              <p className="text-lg font-bold text-slate-900">
                Impossible de charger l'utilisateur
              </p>

              <p className="mt-1 text-sm leading-6 text-slate-500">
                {error || "Utilisateur introuvable."}
              </p>

              <div className="mt-5">
                <Button
                  variant="ghost"
                  icon={ArrowLeft}
                  onClick={() => navigate("/users")}
                >
                  Retour aux utilisateurs
                </Button>
              </div>
            </div>
          </div>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-8 pb-8">
      {/* ─── Top Navigation ─── */}
      <div className="flex items-center gap-3">
        <Button
          variant="ghost"
          size="sm"
          icon={ArrowLeft}
          onClick={() => navigate("/users")}
          className="text-slate-500 hover:text-slate-900"
        >
          Retour
        </Button>
        <span className="text-xs font-medium text-slate-400">/</span>
        <span className="text-xs font-medium text-slate-500">
          Utilisateurs
        </span>
        <span className="text-xs font-medium text-slate-400">/</span>
        <span className="truncate text-xs font-semibold text-slate-900">
          {fullName}
        </span>
      </div>

      {/* ─── Header ─── */}
      <div className="flex flex-col gap-6 sm:flex-row sm:items-start sm:justify-between">
        <div className="flex items-start gap-4">
          <div
            className={cn(
              "flex h-16 w-16 shrink-0 items-center justify-center rounded-2xl text-xl font-bold shadow-sm",
              isActive
                ? "bg-slate-900 text-white"
                : "bg-slate-100 text-slate-400",
            )}
          >
            {initials}
          </div>

          <div className="min-w-0 space-y-1">
            <div className="flex flex-wrap items-center gap-2">
              <h1 className="text-2xl font-bold tracking-tight text-slate-900 sm:text-3xl">
                {fullName}
              </h1>
              <span
                className={cn(
                  "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-wider",
                  isActive
                    ? "border-emerald-200 bg-emerald-50 text-emerald-700"
                    : "border-slate-200 bg-slate-100 text-slate-500",
                )}
              >
                <span
                  className={cn(
                    "h-1.5 w-1.5 rounded-full",
                    isActive ? "bg-emerald-500" : "bg-slate-400",
                  )}
                />
                {isActive ? "Actif" : "Inactif"}
              </span>
            </div>

            <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-slate-500">
              <span className="inline-flex items-center gap-1.5">
                <Mail className="h-3.5 w-3.5" />
                {form.email || "E-mail non renseigné"}
              </span>
              {form.phone && (
                <span className="inline-flex items-center gap-1.5">
                  <Phone className="h-3.5 w-3.5" />
                  {form.phone}
                </span>
              )}
            </div>
          </div>
        </div>

        <div className="flex shrink-0 gap-3">
          <Button
            variant="ghost"
            onClick={() => navigate("/users")}
          >
            Annuler
          </Button>
          <Button
            icon={Save}
            loading={saving}
            onClick={() => void handleSave()}
          >
            Enregistrer
          </Button>
        </div>
      </div>

      {/* ─── Error Banner ─── */}
      {error ? (
        <div
          role="alert"
          className="flex items-start gap-3 rounded-2xl border border-rose-200 bg-rose-50 px-5 py-4 text-rose-800"
        >
          <AlertCircle className="mt-0.5 h-5 w-5 shrink-0" />
          <div>
            <p className="text-sm font-semibold">
              Enregistrement impossible
            </p>
            <p className="mt-0.5 text-sm text-rose-700">{error}</p>
          </div>
        </div>
      ) : null}

      {/* ─── Main Grid ─── */}
      <div className="grid gap-8 lg:grid-cols-[1fr_360px]">
        {/* Left Column */}
        <div className="space-y-6">
          {/* Profile */}
          <section className="rounded-2xl border border-slate-100 bg-white p-6 shadow-sm sm:p-8">
            <div className="mb-6 flex items-center gap-3">
              <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-slate-900 text-white">
                <UserRound className="h-4.5 w-4.5" />
              </div>
              <div>
                <h2 className="text-base font-bold text-slate-900">
                  Informations personnelles
                </h2>
                <p className="text-sm text-slate-500">
                  Identité et coordonnées de l'utilisateur
                </p>
              </div>
            </div>

            <div className="grid gap-5 md:grid-cols-2">
              <Input
                label="Prénom"
                value={form.first_name || ""}
                error={formErrors.first_name || null}
                onChange={(event) => {
                  const value = event.target.value;
                  setForm((current) =>
                    current
                      ? { ...current, first_name: value }
                      : current,
                  );
                  if (formErrors.first_name) {
                    setFormErrors((current) => ({
                      ...current,
                      first_name: undefined,
                    }));
                  }
                }}
              />

              <Input
                label="Nom"
                value={form.last_name || ""}
                error={formErrors.last_name || null}
                onChange={(event) => {
                  const value = event.target.value;
                  setForm((current) =>
                    current
                      ? { ...current, last_name: value }
                      : current,
                  );
                  if (formErrors.last_name) {
                    setFormErrors((current) => ({
                      ...current,
                      last_name: undefined,
                    }));
                  }
                }}
              />

              <Input
                label="Adresse e-mail"
                type="email"
                value={form.email || ""}
                error={formErrors.email || null}
                onChange={(event) => {
                  const value = event.target.value;
                  setForm((current) =>
                    current
                      ? { ...current, email: value }
                      : current,
                  );
                  if (formErrors.email) {
                    setFormErrors((current) => ({
                      ...current,
                      email: undefined,
                    }));
                  }
                }}
              />

              <Input
                label="Numéro de téléphone"
                value={form.phone || ""}
                onChange={(event) =>
                  setForm((current) =>
                    current
                      ? {
                          ...current,
                          phone: event.target.value,
                        }
                      : current,
                  )
                }
              />

              {form.role === "Doctor" && (
                <div className="md:col-span-2">
                  <Input
                    label="Qualification"
                    value={form.qualification || ""}
                    error={formErrors.qualification || null}
                    onChange={(event) => {
                      const value = event.target.value;
                      setForm((current) =>
                        current
                          ? {
                              ...current,
                              qualification: value,
                            }
                          : current,
                      );
                      if (formErrors.qualification) {
                        setFormErrors((current) => ({
                          ...current,
                          qualification: undefined,
                        }));
                      }
                    }}
                  />
                </div>
              )}
            </div>
          </section>

          {/* Account & Security */}
          <section className="rounded-2xl border border-slate-100 bg-white p-6 shadow-sm sm:p-8">
            <div className="mb-6 flex items-center gap-3">
              <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-slate-900 text-white">
                <ShieldCheck className="h-4.5 w-4.5" />
              </div>
              <div>
                <h2 className="text-base font-bold text-slate-900">
                  Accès et sécurité
                </h2>
                <p className="text-sm text-slate-500">
                  Rôle, statut du compte et mot de passe
                </p>
              </div>
            </div>

            <div className="grid gap-5 md:grid-cols-2">
              <div className="space-y-3">
                <Select
                  label="Rôle"
                  options={[
                    { label: "Super Admin", value: "Super Admin" },
                    { label: "Admin", value: "Admin" },
                    { label: "Médecin", value: "Doctor" },
                    { label: "Assistant", value: "Assistant" },
                  ]}
                  value={form.role || "Doctor"}
                  onChange={(event) => {
                    const nextRole = event.target.value as Role;
                    setForm((current) =>
                      current
                        ? {
                            ...current,
                            role: nextRole,
                            qualification:
                              nextRole === "Doctor"
                                ? current.qualification || ""
                                : "",
                          }
                        : current,
                    );
                    if (nextRole !== "Doctor") {
                      setFormErrors((current) => ({
                        ...current,
                        qualification: undefined,
                      }));
                    }
                  }}
                />

                <div className="rounded-xl bg-slate-50 px-4 py-3">
                  <div className="flex items-start gap-2.5">
                    <UsersRound className="mt-0.5 h-4 w-4 shrink-0 text-slate-400" />
                    <p className="text-xs leading-5 text-slate-600">
                      {roleDescriptions[role]}
                    </p>
                  </div>
                </div>
              </div>

              <div className="space-y-3">
                <Select
                  label="Statut du compte"
                  options={[
                    { label: "Actif", value: "active" },
                    { label: "Inactif", value: "inactive" },
                  ]}
                  value={form.status || "active"}
                  onChange={(event) =>
                    setForm((current) =>
                      current
                        ? {
                            ...current,
                            status: event.target
                              .value as User["status"],
                          }
                        : current,
                    )
                  }
                />

                <div
                  className={cn(
                    "rounded-xl border px-4 py-3",
                    isActive
                      ? "border-emerald-100 bg-emerald-50/60"
                      : "border-amber-100 bg-amber-50/60",
                  )}
                >
                  <div className="flex items-start gap-2.5">
                    <Activity
                      className={cn(
                        "mt-0.5 h-4 w-4 shrink-0",
                        isActive
                          ? "text-emerald-600"
                          : "text-amber-600",
                      )}
                    />
                    <div>
                      <p
                        className={cn(
                          "text-xs font-semibold",
                          isActive
                            ? "text-emerald-800"
                            : "text-amber-800",
                        )}
                      >
                        {isActive
                          ? "Compte actif"
                          : "Compte désactivé"}
                      </p>
                      <p
                        className={cn(
                          "mt-0.5 text-xs leading-5",
                          isActive
                            ? "text-emerald-700"
                            : "text-amber-700",
                        )}
                      >
                        {isActive
                          ? "L'utilisateur peut accéder à l'application selon ses autorisations."
                          : "L'utilisateur ne pourra plus ouvrir de session."}
                      </p>
                    </div>
                  </div>
                </div>
              </div>

              <div className="md:col-span-2">
                <Input
                  label="Nouveau mot de passe"
                  type="password"
                  placeholder="Laisser vide pour conserver le mot de passe actuel"
                  value={form.password || ""}
                  onChange={(event) =>
                    setForm((current) =>
                      current
                        ? {
                            ...current,
                            password: event.target.value,
                          }
                        : current,
                    )
                  }
                />

                <div className="mt-3 flex items-start gap-2 rounded-xl bg-slate-50 px-4 py-3">
                  <KeyRound className="mt-0.5 h-4 w-4 shrink-0 text-slate-400" />
                  <p className="text-xs leading-5 text-slate-600">
                    Saisissez un nouveau mot de passe uniquement pour
                    le remplacer. Laissez ce champ vide pour conserver
                    le mot de passe actuel.
                  </p>
                </div>
              </div>
            </div>
          </section>
        </div>

        {/* Right Column */}
        <aside className="space-y-6">
          {/* Profile Summary */}
          <section className="rounded-2xl border border-slate-100 bg-white p-6 shadow-sm">
            <div className="mb-5 flex items-center justify-between">
              <h3 className="text-sm font-bold uppercase tracking-wider text-slate-400">
                Résumé
              </h3>
              <BadgeCheck
                className={cn(
                  "h-5 w-5",
                  isActive ? "text-emerald-500" : "text-slate-300",
                )}
              />
            </div>

            <div className="mb-5 flex items-center gap-3">
              <div
                className={cn(
                  "flex h-12 w-12 items-center justify-center rounded-xl text-sm font-bold",
                  isActive
                    ? "bg-slate-900 text-white"
                    : "bg-slate-100 text-slate-400",
                )}
              >
                {initials}
              </div>
              <div className="min-w-0">
                <p className="truncate text-sm font-semibold text-slate-900">
                  {fullName}
                </p>
                <p className="truncate text-xs text-slate-500">
                  {form.email || "—"}
                </p>
              </div>
            </div>

            <div className="divide-y divide-slate-50">
              <div className="flex items-center justify-between py-3">
                <span className="flex items-center gap-2 text-sm text-slate-500">
                  <ShieldCheck className="h-4 w-4 text-slate-400" />
                  Rôle
                </span>
                <span
                  className={cn(
                    "inline-flex rounded-md border px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider",
                    getRoleBadgeClassName(role),
                  )}
                >
                  {role}
                </span>
              </div>

              <div className="flex items-center justify-between py-3">
                <span className="flex items-center gap-2 text-sm text-slate-500">
                  <Activity className="h-4 w-4 text-slate-400" />
                  Statut
                </span>
                <span
                  className={cn(
                    "text-sm font-semibold",
                    isActive
                      ? "text-emerald-600"
                      : "text-slate-500",
                  )}
                >
                  {isActive ? "Actif" : "Inactif"}
                </span>
              </div>

              <div className="flex items-center justify-between py-3">
                <span className="flex items-center gap-2 text-sm text-slate-500">
                  <CalendarDays className="h-4 w-4 text-slate-400" />
                  Créé le
                </span>
                <span className="text-sm font-medium text-slate-700">
                  {formatDate(form.created_at)}
                </span>
              </div>

              <div className="flex items-center justify-between py-3">
                <span className="flex items-center gap-2 text-sm text-slate-500">
                  <CalendarDays className="h-4 w-4 text-slate-400" />
                  Mis à jour
                </span>
                <span className="text-sm font-medium text-slate-700">
                  {formatDate(form.updated_at)}
                </span>
              </div>
            </div>
          </section>

          {/* Permissions */}
          {userId ? (
            <div className="min-w-0">
              <UserPermissionMatrixEditor userId={userId} />
            </div>
          ) : (
            <section className="rounded-2xl border border-slate-100 bg-white p-6 shadow-sm">
              <div className="flex items-start gap-3">
                <AlertCircle className="mt-0.5 h-5 w-5 shrink-0 text-amber-500" />
                <div>
                  <p className="text-sm font-semibold text-slate-900">
                    Autorisations indisponibles
                  </p>
                  <p className="mt-1 text-sm leading-6 text-slate-500">
                    L'identifiant de l'utilisateur est manquant.
                  </p>
                </div>
              </div>
            </section>
          )}
        </aside>
      </div>
    </div>
  );
};