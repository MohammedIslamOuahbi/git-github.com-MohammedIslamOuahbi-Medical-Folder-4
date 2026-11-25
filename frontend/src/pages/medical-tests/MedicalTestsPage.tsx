import { Fragment, useCallback, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { AlertTriangle, ChevronDown, ChevronUp, Pencil, Plus, Power, Trash2 } from "lucide-react";
import { Navigate, useSearchParams } from "react-router-dom";
import { medicalTestsApi } from "@/api/medicalTestsApi";
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
import { useAuth } from "@/hooks/useAuth";
import { usePaginatedResource } from "@/hooks/usePaginatedResource";
import { cn } from "@/utils/cn";
import type { MedicalTest } from "@/types/entities";
import { formatDisplayDate } from "@/utils/date";
import { mockMedicalTests } from "@/utils/mockData";
import { hasRole } from "@/utils/permissions";

const SECTION_OPTIONS = [
  { label: "Fiche interne de visite médicale", value: "Fiche interne de visite médicale" },
  { label: "Examen clinique", value: "Examen clinique" },
  { label: "Examens complémentaires", value: "Examens complémentaires" },
];

const defaultForm: Partial<MedicalTest> = {
  name: "",
  section: SECTION_OPTIONS[1].value,
  active: true,
  description: "",
};

type DynamicFieldType = "text" | "number" | "textarea" | "checkbox" | "select" | "date" | "radio";

type DynamicFieldOption = {
  label: string;
  value: string;
};

type DynamicFieldConfig = {
  type: DynamicFieldType;
  name: string;
  label: string;
  placeholder?: string;
  required?: boolean;
  colSpan?: number;
  wrapperClassName?: string;
  labelClassName?: string;
  inputClassName?: string;
  options?: DynamicFieldOption[];
};

type DynamicLayoutConfig = {
  columns?: number;
  gap?: number;
};

type DynamicTestConfig = {
  layout?: DynamicLayoutConfig;
  fields?: DynamicFieldConfig[];
};

const previewInputBase =
  "w-full rounded-xl border border-slate-200 bg-slate-50/80 px-3 py-2.5 text-sm font-medium text-slate-800 outline-none transition-all duration-200 focus:border-cyan-400/40 focus:bg-white focus:ring-4 focus:ring-cyan-500/10";

const previewLabelBase = "text-sm font-bold tracking-[0.01em] text-slate-800";

const previewCardClassName = "rounded-3xl border-slate-200/90";

const emptyPreviewConfig: DynamicTestConfig = { layout: { columns: 2, gap: 4 }, fields: [] };

const sanitizeColumns = (value?: number) => {
  if (!value || !Number.isFinite(value)) return 2;
  return Math.max(1, Math.min(4, Math.trunc(value)));
};

const sanitizeGap = (value?: number) => {
  if (!value || !Number.isFinite(value)) return 4;
  return Math.max(2, Math.min(8, Math.trunc(value)));
};

const gapToClassName = (gap: number) => {
  const normalized = Math.max(2, Math.min(8, Math.trunc(gap)));
  return {
    2: "gap-2",
    3: "gap-3",
    4: "gap-4",
    5: "gap-5",
    6: "gap-6",
    7: "gap-7",
    8: "gap-8",
  }[normalized as 2 | 3 | 4 | 5 | 6 | 7 | 8];
};

const createPreviewValue = (field: DynamicFieldConfig) => {
  if (field.type === "checkbox") return false;
  if (field.type === "number") return "";
  if (field.type === "select" || field.type === "radio") return field.options?.[0]?.value ?? "";
  return "";
};

const DynamicPreviewField = ({
  field,
  value,
  onChange,
}: {
  field: DynamicFieldConfig;
  value: string | boolean;
  onChange: (name: string, nextValue: string | boolean) => void;
}) => {
  const wrapperClassName = cn(field.wrapperClassName);
  const labelClassName = cn(previewLabelBase, field.labelClassName);
  const inputClassName = cn(previewInputBase, field.inputClassName);

  return (
    <div className={wrapperClassName}>
      <label className="block space-y-2">
        <span className={labelClassName}>{field.label}</span>

        {field.type === "textarea" ? (
          <textarea
            rows={4}
            className={cn(inputClassName, "min-h-[110px]")}
            value={String(value ?? "")}
            placeholder={field.placeholder}
            onChange={(event) => onChange(field.name, event.target.value)}
          />
        ) : field.type === "checkbox" ? (
          <label className="flex items-center gap-3 rounded-2xl border border-slate-200 bg-slate-50/80 px-4 py-3">
            <input
              type="checkbox"
              checked={Boolean(value)}
              onChange={(event) => onChange(field.name, event.target.checked)}
              className="h-4 w-4 rounded border-slate-300 text-cyan-600 focus:ring-cyan-500"
            />
            <span className="text-sm font-medium text-slate-700">{field.placeholder || "Activer"}</span>
          </label>
        ) : field.type === "select" ? (
          <Select
            label=""
            options={(field.options || []).map((option) => ({
              label: option.label,
              value: option.value,
            }))}
            value={String(value ?? "")}
            onChange={(event) => onChange(field.name, event.target.value)}
            className={inputClassName}
          />
        ) : field.type === "radio" ? (
          <div className="space-y-2">
            {(field.options || []).map((option) => (
              <label
                key={option.value}
                className="flex items-center gap-3 rounded-2xl border border-slate-200 bg-slate-50/80 px-4 py-3"
              >
                <input
                  type="radio"
                  name={field.name}
                  checked={String(value ?? "") === option.value}
                  onChange={() => onChange(field.name, option.value)}
                  className="h-4 w-4 border-slate-300 text-cyan-600 focus:ring-cyan-500"
                />
                <span className="text-sm font-medium text-slate-700">{option.label}</span>
              </label>
            ))}
          </div>
        ) : (
          <Input
            type={field.type}
            value={String(value ?? "")}
            placeholder={field.placeholder}
            onChange={(event) => onChange(field.name, event.target.value)}
            className={inputClassName}
          />
        )}
      </label>
    </div>
  );
};

const DynamicPreviewPanel = ({ configJson }: { configJson: string }) => {
  const parsed = useMemo(() => {
    if (!configJson.trim()) return { config: emptyPreviewConfig, error: null as string | null };
    try {
      const next = JSON.parse(configJson) as DynamicTestConfig;
      const fields = Array.isArray(next?.fields) ? next.fields : [];
      return {
        config: {
          layout: {
            columns: sanitizeColumns(next?.layout?.columns),
            gap: sanitizeGap(next?.layout?.gap),
          },
          fields: fields
            .filter((field): field is DynamicFieldConfig => Boolean(field?.name && field?.label && field?.type))
            .map((field) => ({
              ...field,
              colSpan: field.colSpan ? Math.max(1, Math.min(4, Math.trunc(field.colSpan))) : undefined,
            })),
        },
        error: null as string | null,
      };
    } catch {
      return { config: emptyPreviewConfig, error: "JSON invalide. Vérifiez la syntaxe." };
    }
  }, [configJson]);

  const [previewValues, setPreviewValues] = useState<Record<string, string | boolean>>({});
  const fields = parsed.config.fields ?? [];

  useEffect(() => {
    if (parsed.error) return;
    const nextValues: Record<string, string | boolean> = {};
    fields.forEach((field) => {
      nextValues[field.name] = field.name in previewValues ? previewValues[field.name] : createPreviewValue(field);
    });
    setPreviewValues(nextValues);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [configJson, parsed.error]);

  const updatePreviewValue = (name: string, nextValue: string | boolean) => {
    setPreviewValues((current) => ({ ...current, [name]: nextValue }));
  };

  const columns = parsed.config.layout?.columns ?? 2;
  const gap = parsed.config.layout?.gap ?? 4;

  return (
    <Card className={cn("rounded-3xl border-slate-200/90 p-6", previewCardClassName)}>
      <div className="mb-5">
        <h3 className="text-lg font-black text-slate-950">Aperçu (Live Preview)</h3>
        <p className="mt-1 text-sm text-slate-500">
          L’aperçu est local à l’éditeur et ne modifie pas les données enregistrées.
        </p>
      </div>

      {parsed.error ? (
        <div className="rounded-2xl border border-amber-200 bg-amber-50/80 px-4 py-4 text-sm font-medium text-amber-800">
          <div className="flex items-center gap-2">
            <AlertTriangle className="h-4 w-4" />
            <span>{parsed.error}</span>
          </div>
        </div>
      ) : fields.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-slate-200 bg-slate-50/70 px-4 py-10 text-center text-sm text-slate-500">
          Ajoutez un JSON de configuration pour générer l’aperçu du formulaire.
        </div>
      ) : (
        <div
          className={cn("grid", gapToClassName(gap))} style={{ gridTemplateColumns: `repeat(${columns}, minmax(0, 1fr))` }}
        >
          {fields.map((field) => (
            <div
              key={field.name}
              className={cn(field.wrapperClassName)} style={{ gridColumn: `span ${field.colSpan ? Math.min(columns, field.colSpan) : 1} / span ${field.colSpan ? Math.min(columns, field.colSpan) : 1}` }}
            >
              <DynamicPreviewField
                field={field}
                value={previewValues[field.name] ?? createPreviewValue(field)}
                onChange={updatePreviewValue}
              />
            </div>
          ))}
        </div>
      )}
    </Card>
  );
};

export const MedicalTestsPage = () => {
  const { user } = useAuth();
  const isAdmin = hasRole(user, ["Admin", "Super Admin"]);
  const [searchParams, setSearchParams] = useSearchParams();
  const { items, total, page, pageSize, search, loading, error, setPage, setSearch, setItems } =
    usePaginatedResource<MedicalTest>(useCallback(medicalTestsApi.list, []), mockMedicalTests);
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState<Partial<MedicalTest>>(defaultForm);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<MedicalTest | null>(null);
  const [deletePassword, setDeletePassword] = useState("");
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [notice, setNotice] = useState<{ type: "success" | "error"; message: string } | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [expandedRowId, setExpandedRowId] = useState<number | null>(null);

  useEffect(() => {
    if (searchParams.get("action") === "create") {
      setEditingId(null);
      setForm(defaultForm);
      setFormError(null);
      setOpen(true);
      setSearchParams({}, { replace: true });
    }
  }, [searchParams, setSearchParams]);

  const sortedItems = useMemo(
    () => [...items].sort((left, right) => (left.id ?? Number.MAX_SAFE_INTEGER) - (right.id ?? Number.MAX_SAFE_INTEGER)),
    [items],
  );

  if (!isAdmin) {
    return <Navigate to="/dashboard" replace />;
  }

  const save = async () => {
    if (!form.name?.trim() || !form.section?.trim()) {
      setFormError("Le nom et la section sont obligatoires.");
      return;
    }

    setFormError(null);
    setNotice(null);

    try {
      if (editingId) {
        const updated = await medicalTestsApi.update(editingId, form);
        setItems((current) => current.map((item) => (item.id === editingId ? updated : item)));
        setExpandedRowId(editingId);
        setNotice({ type: "success", message: "Examen médical mis à jour avec succès." });
      } else {
        const created = await medicalTestsApi.create(form);
        setItems((current) => [created, ...current]);
        setExpandedRowId(created.id);
        setNotice({ type: "success", message: "Examen médical créé avec succès." });
      }
    } catch {
      setFormError("Impossible d'enregistrer cet examen médical.");
      return;
    }

    setEditingId(null);
    setForm(defaultForm);
    setOpen(false);
  };

  const toggleActive = async (row: MedicalTest) => {
    setNotice(null);
    try {
      const updated = await medicalTestsApi.update(row.id, { active: !row.active });
      setItems((current) => current.map((item) => (item.id === row.id ? updated : item)));
      setExpandedRowId(row.id);
      setNotice({
        type: "success",
        message: updated.active
          ? "Examen médical activé avec succès."
          : "Examen médical désactivé avec succès.",
      });
    } catch {
      setNotice({ type: "error", message: "Impossible de modifier le statut de cet examen médical." });
    }
  };

  const removeMedicalTest = async () => {
    if (!deleteTarget) return;
    if (!deletePassword.trim()) {
      setDeleteError("Veuillez saisir votre mot de passe.");
      return;
    }

    try {
      const removed = await medicalTestsApi.remove(deleteTarget.id, { password: deletePassword });
      setItems((current) => current.map((item) => (item.id === deleteTarget.id ? removed : item)));
      setExpandedRowId(deleteTarget.id);
      setNotice({
        type: "success",
        message: "Examen médical désactivé avec succès.",
      });
      setDeleteTarget(null);
      setDeletePassword("");
      setDeleteError(null);
    } catch {
      setDeleteError("Mot de passe invalide ou suppression impossible.");
    }
  };

  return (
    <div className="space-y-6">
      <SectionHeader
        eyebrow="Administration"
        title="Medical Tests"
        description={error || "Gérez la liste globale des examens médicaux utilisés dans l'application."}
        actionLabel="Nouveau test"
        actionIcon={Plus}
        onAction={() => {
          setEditingId(null);
          setForm(defaultForm);
          setFormError(null);
          setOpen(true);
        }}
      />

      {notice ? (
        <p className={notice.type === "error" ? "text-sm font-medium text-rose-600" : "text-sm font-medium text-emerald-700"}>
          {notice.message}
        </p>
      ) : null}

      <SearchInput value={search} onChange={setSearch} placeholder="Rechercher un examen médical..." />
      <Card className="overflow-hidden p-0">
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-ink-100">
            <thead className="bg-ink-50">
              <tr>
                <th className="w-14 px-4 py-4" />
                <th className="px-6 py-4 text-left text-xs font-semibold uppercase tracking-[0.2em] text-ink-500">ID</th>
                <th className="px-6 py-4 text-left text-xs font-semibold uppercase tracking-[0.2em] text-ink-500">Nom</th>
                <th className="px-6 py-4 text-left text-xs font-semibold uppercase tracking-[0.2em] text-ink-500">Section</th>
                <th className="px-6 py-4 text-left text-xs font-semibold uppercase tracking-[0.2em] text-ink-500">Statut</th>
                <th className="px-6 py-4 text-left text-xs font-semibold uppercase tracking-[0.2em] text-ink-500">Créé le</th>
                <th className="px-6 py-4 text-left text-xs font-semibold uppercase tracking-[0.2em] text-ink-500">Mis à jour</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-ink-100 bg-white">
              {loading ? (
                <tr>
                  <td colSpan={7} className="px-6 py-16 text-center text-sm font-medium text-slate-500">
                    Chargement des examens m??dicaux...
                  </td>
                </tr>
              ) : sortedItems.length === 0 ? (
                <tr>
                  <td colSpan={7} className="p-6">
                    <EmptyState
                      title="Aucun examen m??dical"
                      description="Aucun enregistrement ne correspond ?? votre recherche actuelle."
                      actionLabel="Nouveau test"
                      onAction={() => {
                        setEditingId(null);
                        setForm(defaultForm);
                        setFormError(null);
                        setOpen(true);
                      }}
                    />
                  </td>
                </tr>
              ) : (
                sortedItems.map((row) => {
                  const isExpanded = expandedRowId === row.id;

                  return (
                    <Fragment key={row.id}>
                      <tr
                        className={cn(
                          "group cursor-pointer transition-colors hover:bg-ink-50/70",
                          isExpanded ? "bg-slate-50/80" : "bg-white",
                        )}
                        onClick={() => setExpandedRowId((current) => (current === row.id ? null : row.id))}
                      >
                        <td className="px-4 py-4">
                          <span className="inline-flex h-8 w-8 items-center justify-center rounded-full border border-slate-200 bg-white text-slate-500 transition group-hover:border-slate-300 group-hover:text-slate-900">
                            {isExpanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
                          </span>
                        </td>
                        <td className="px-6 py-4 text-sm font-semibold text-brand-700">{row.id}</td>
                        <td className="px-6 py-4 text-sm font-semibold text-ink-900">{row.name}</td>
                        <td className="px-6 py-4 text-sm text-ink-700">{row.section}</td>
                        <td className="px-6 py-4 text-sm text-ink-700">
                          <Badge tone={row.active ? "active" : "inactive"}>
                            {row.active ? "Actif" : "Inactif"}
                          </Badge>
                        </td>
                        <td className="px-6 py-4 text-sm text-ink-700">{formatDisplayDate(row.created_at) || "-"}</td>
                        <td className="px-6 py-4 text-sm text-ink-700">{formatDisplayDate(row.updated_at) || "-"}</td>
                      </tr>
                      {isExpanded ? (
                        <tr className="bg-slate-50/90">
                          <td colSpan={7} className="px-6 py-4">
                            
                              <Button
                                variant="secondary"
                                size="sm"
                                icon={Pencil}
                               
                                onClick={(event) => {
                                  event.stopPropagation();
                                  setEditingId(row.id);
                                  setForm({
                                    name: row.name,
                                    section: row.section,
                                    active: row.active,
                                    description: row.description || "",
                                  });
                                  setFormError(null);
                                  setOpen(true);
                                  
                                }}
                              >
                                Modifier
                              </Button>
                              <Button
                                variant="ghost"
                                size="sm"
                                icon={Power}
                                onClick={(event) => {
                                  event.stopPropagation();
                                  void toggleActive(row);
                                }}
                              >
                                {row.active ? "Désactiver" : "Activer"}
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
                                Supprimer
                              </Button>
                           
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

      <Modal
        open={open}
        title={editingId ? "Modifier un examen médical" : "Créer un examen médical"}
        onClose={() => {
          setOpen(false);
          setEditingId(null);
          setForm(defaultForm);
          setFormError(null);
        }}
      >
        <div className="space-y-4">
          <div className="grid gap-6 lg:grid-cols-2">
            <div className="space-y-4">
              <Input
                label="Nom"
                value={form.name || ""}
                onChange={(e) => setForm((current) => ({ ...current, name: e.target.value }))}
              />
              <Select
                label="Section"
                options={SECTION_OPTIONS}
                value={form.section || SECTION_OPTIONS[1].value}
                onChange={(e) => setForm((current) => ({ ...current, section: e.target.value }))}
              />
              <Select
                label="Statut"
                options={[
                  { label: "Actif", value: "true" },
                  { label: "Inactif", value: "false" },
                ]}
                value={form.active ? "true" : "false"}
                onChange={(e) =>
                  setForm((current) => ({ ...current, active: e.target.value === "true" }))
                }
              />
            </div>
            <label className="block space-y-2">
              <span className="text-sm font-bold tracking-[0.01em] text-slate-800">
                Description JSON
              </span>
              <textarea
                rows={18}
                value={String(form.description || "")}
                onChange={(event) =>
                  setForm((current) => ({ ...current, description: event.target.value }))
                }
                className="w-full rounded-2xl border border-slate-200 bg-slate-50/80 px-4 py-3 font-mono text-sm text-slate-800 outline-none transition focus:border-cyan-400/40 focus:bg-white focus:ring-4 focus:ring-cyan-500/10"
                placeholder='{"layout":{"columns":4},"fields":[{"type":"text","name":"od_sc","label":"OD SC"}]}'
              />
            </label>
            <div className="lg:col-span-2">
              <DynamicPreviewPanel configJson={String(form.description || "")} />
            </div>
          </div>

          {formError ? <p className="text-sm font-medium text-rose-600">{formError}</p> : null}

          <div className="flex justify-end">
            <Button onClick={() => void save()}>
              {editingId ? "Mettre à jour" : "Enregistrer"}
            </Button>
          </div>
        </div>
      </Modal>

      <Modal
        open={Boolean(deleteTarget)}
        title={deleteTarget ? `Supprimer ${deleteTarget.name}` : "Supprimer un examen médical"}
        onClose={() => {
          setDeleteTarget(null);
          setDeletePassword("");
          setDeleteError(null);
        }}
      >
        <div className="space-y-4">
          <p className="text-sm text-ink-600">
            Cette suppression désactive le test pour les futures affectations sans casser l'historique existant.
          </p>
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
          <div className="flex justify-end gap-2">
            <Button variant="secondary" onClick={() => setDeleteTarget(null)}>
              Annuler
            </Button>
            <Button variant="danger" onClick={() => void removeMedicalTest()}>
              Désactiver le test
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
};


