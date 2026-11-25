import { useEffect, useMemo, useState } from "react";
import {
  AlertCircle,
  CheckCircle2,
  CircleDashed,
  FileSearch,
  FileUp,
  Layers,
  Link2,
  RefreshCcw,
  Rows3,
  Sparkles,
  UploadCloud,
} from "lucide-react";
import { useNavigate } from "react-router-dom";
import { isAxiosError } from "axios";

import { importsApi, type ImportPreviewRow } from "@/api/importsApi";
import { Badge } from "@/components/common/Badge";
import { Button } from "@/components/common/Button";
import { Card } from "@/components/common/Card";
import { DataTable } from "@/components/common/DataTable";
import { EmptyState } from "@/components/common/EmptyState";
import { SectionHeader } from "@/components/common/SectionHeader";
import { useCampaignWorkspace } from "@/context/CampaignWorkspaceContext";
import { ImportFieldAutocomplete } from "@/features/import/ImportFieldAutocomplete";
import {
  importFieldLookup,
  importFieldSchema,
  type ImportFieldMainType,
} from "@/features/import/importFieldSchema";
import type { ImportJob } from "@/types/entities";

const requiredMappedFields = ["lastName", "firstName"] as const;
const identityAlternateFields = ["employeeCode", "medicalFileNumber"] as const;
const mainTypeLabels: Record<ImportFieldMainType, string> = {
  medicalFolder: "Dossier médical",
  medicalVisit: "Visite médicale",
};

const statusToneMap: Record<ImportJob["status"], string> = {
  pending: "pending",
  validated: "reviewed",
  completed: "completed",
  failed: "failed",
};

const legendItems = [
  { tone: "slate", label: "Ignoré", icon: CircleDashed },
  { tone: "emerald", label: "Valide", icon: CheckCircle2 },
  { tone: "amber", label: "Conversion", icon: AlertCircle },
  { tone: "rose", label: "Dupliqué", icon: AlertCircle },
] as const;

const toneClasses: Record<string, string> = {
  slate: "border-slate-200 bg-slate-50 text-slate-500",
  emerald: "border-emerald-200 bg-emerald-50 text-emerald-700",
  amber: "border-amber-200 bg-amber-50 text-amber-700",
  rose: "border-rose-200 bg-rose-50 text-rose-700",
};

export const CampaignWorkspaceImportPage = () => {
  const navigate = useNavigate();
  const { currentCampaign } = useCampaignWorkspace();
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [history, setHistory] = useState<ImportJob[]>([]);
  const [activeImport, setActiveImport] = useState<ImportJob | null>(null);
  const [previewRows, setPreviewRows] = useState<ImportPreviewRow[]>([]);
  const [mapping, setMapping] = useState<Record<string, string>>({});
  const [mappingTypes, setMappingTypes] = useState<Record<string, ImportFieldMainType>>({});
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [processing, setProcessing] = useState<"mapping" | "validating" | "confirming" | null>(null);

  useEffect(() => {
    let cancelled = false;
    const loadHistory = async () => {
      try {
        const rows = await importsApi.history();
        if (!cancelled) {
          setHistory(rows.slice(0, 8));
        }
      } catch {
        if (!cancelled) {
          setHistory([]);
        }
      }
    };
    void loadHistory();
    return () => {
      cancelled = true;
    };
  }, []);

  const helperText = useMemo(() => {
    if (!currentCampaign) return "";
    return `Importer la liste nominative pour ${currentCampaign.site_name || currentCampaign.branch_name}. Les travailleurs créés seront rattachés à cette campagne.`;
  }, [currentCampaign]);

  const previewColumns = useMemo(() => {
    const firstRow = previewRows[0]?.raw_data_json;
    return firstRow ? Object.keys(firstRow) : [];
  }, [previewRows]);

  const sampleRows = useMemo(() => previewRows.slice(0, 5), [previewRows]);

  const requiredMappingsComplete = useMemo(
    () =>
      requiredMappedFields.every((field) => Object.values(mapping).includes(field)) &&
      identityAlternateFields.some((field) => Object.values(mapping).includes(field)),
    [mapping],
  );

  const hasDuplicateMappedTargets = useMemo(() => {
    const selectedTargets = Object.values(mapping).filter(Boolean);
    const scalarTargets = selectedTargets.filter((target) => !target.includes("[]"));
    return new Set(scalarTargets).size !== scalarTargets.length;
  }, [mapping]);

  const mappedCount = useMemo(() => Object.values(mapping).filter(Boolean).length, [mapping]);

  const requiredFieldStatus = useMemo(
    () =>
      [...requiredMappedFields, "employeeCode | medicalFileNumber"].map((field) => {
        const mapped =
          field === "employeeCode | medicalFileNumber"
            ? identityAlternateFields.some((candidate) => Object.values(mapping).includes(candidate))
            : Object.values(mapping).includes(field);

        return {
          key: field,
          label:
            field === "firstName"
              ? "Prénom"
              : field === "lastName"
                ? "Nom"
                : "Matricule",
          mapped,
        };
      }),
    [mapping],
  );

  const optionalMappedCount = useMemo(() => {
    const requiredTargets = [...requiredMappedFields, ...identityAlternateFields];
    return Object.values(mapping).filter((value) => value && !requiredTargets.includes(value as (typeof requiredTargets)[number]))
      .length;
  }, [mapping]);

  const getRowState = (columnName: string) => {
    const path = mapping[columnName] || "";
    if (!path) {
      return { tone: "slate" as const, label: "Ignoré" };
    }

    const field = importFieldLookup.get(path);
    const isDuplicate =
      !path.includes("[]") &&
      Object.entries(mapping).some(
        ([otherColumn, otherPath]) => otherColumn !== columnName && otherPath === path,
      );

    if (isDuplicate) {
      return { tone: "rose" as const, label: "Dupliqué" };
    }

    if (field && ["date", "number", "boolean", "enum"].includes(field.type)) {
      return { tone: "amber" as const, label: "À vérifier" };
    }

    return { tone: "emerald" as const, label: "Valide" };
  };

  const loadPreview = async (importJobId: number, savedMapping?: Record<string, string> | null) => {
    const rows = await importsApi.preview(importJobId);
    setPreviewRows(rows);
    const firstRow = rows[0]?.raw_data_json;
    if (!firstRow) {
      setMapping({});
      setMappingTypes({});
      return;
    }
    setMapping(() => {
      const next = { ...(savedMapping || {}) };
      Object.keys(firstRow).forEach((columnName) => {
        if (!(columnName in next)) {
          next[columnName] = "";
        }
      });
      return next;
    });
    setMappingTypes((current) => {
      const next = { ...current };
      Object.keys(firstRow).forEach((columnName) => {
        const mappedPath = savedMapping?.[columnName];
        const inferredType = mappedPath ? importFieldLookup.get(mappedPath)?.mainType : null;
        if (!(columnName in next)) {
          next[columnName] = inferredType || "medicalFolder";
        }
      });
      return next;
    });
  };

  const handleUpload = async () => {
    if (!selectedFile || !currentCampaign) {
      setError("Sélectionnez un fichier avant de lancer l'import.");
      return;
    }
    setUploading(true);
    setError(null);
    setNotice(null);
    try {
      const result = await importsApi.upload(selectedFile, {
        campaignId: currentCampaign.id,
        companyId: currentCampaign.company_id,
      });
      setActiveImport(result);
      setHistory((current) => [result, ...current.filter((item) => item.id !== result.id)].slice(0, 8));
      await loadPreview(result.id, result.mapping_json);
      setNotice("Fichier chargé. Mappez maintenant les colonnes Excel vers les champs d'import.");
      setSelectedFile(null);
    } catch (uploadError) {
      console.error("[Import][upload error]", uploadError);
      const apiMessage = isAxiosError<{ message?: string; details?: Record<string, unknown> }>(uploadError)
        ? uploadError.response?.data?.message
        : null;
      setError(apiMessage || "Impossible d'importer ce fichier pour la campagne en cours.");
    } finally {
      setUploading(false);
    }
  };

  const handleValidateImport = async () => {
    if (!activeImport) return;
    if (!requiredMappingsComplete) {
      setError("Le mapping doit contenir firstName, lastName et employeeCode ou medicalFileNumber.");
      return;
    }
    if (hasDuplicateMappedTargets) {
      setError("Chaque champ scalaire ne peut être mappé qu'une seule fois.");
      return;
    }
    setProcessing("validating");
    setError(null);
    setNotice(null);
    try {
      const mappedImport = await importsApi.mapFields(activeImport.id, mapping);
      const validated = await importsApi.validate(activeImport.id);
      const nextImport = { ...validated, mapping_json: mappedImport.mapping_json };
      setActiveImport(nextImport);
      setHistory((current) => current.map((item) => (item.id === nextImport.id ? nextImport : item)));
      await loadPreview(nextImport.id, nextImport.mapping_json);
      setNotice("Le fichier a été validé. Vous pouvez maintenant confirmer l'import en base.");
    } catch {
      setError("Impossible de valider le mapping de ce fichier.");
    } finally {
      setProcessing(null);
    }
  };

  const handleConfirmImport = async () => {
    if (!activeImport || !currentCampaign) return;
    setProcessing("confirming");
    setError(null);
    setNotice(null);
    try {
      const confirmed = await importsApi.confirm(activeImport.id, currentCampaign.id);
      setActiveImport(confirmed);
      setHistory((current) => current.map((item) => (item.id === confirmed.id ? confirmed : item)));
      await loadPreview(confirmed.id, activeImport.mapping_json);
      window.sessionStorage.setItem(
        `campaign-workers-import-notice.${currentCampaign.id}`,
        "Les travailleurs importés ont été ajoutés à la campagne avec le statut En attente.",
      );
      setNotice(
        "Import confirmé. Les travailleurs valides ont été ajoutés en base et rattachés à cette campagne pour les tests.",
      );
      navigate(`/app/workspace/${currentCampaign.id}/workers`);
    } catch {
      setError("Impossible de confirmer cet import.");
    } finally {
      setProcessing(null);
    }
  };

  if (!currentCampaign) {
    return null;
  }

  return (
    <div className="space-y-6">
      <SectionHeader
        eyebrow="Import nominatif"
        title="Importer la liste nominative"
        description="Chargez le fichier Excel, mappez les colonnes vers les champs du dossier médical et confirmez la création des données."
      />

      {/* Upload */}
      <Card className="rounded-2xl p-6">
        <div className="flex flex-col gap-5 lg:flex-row lg:items-center lg:justify-between">
          <div className="flex items-start gap-4">
            <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-[#0085A3]/10 text-[#0085A3]">
              <UploadCloud className="h-5 w-5" />
            </div>
            <div className="max-w-xl">
              <h2 className="text-lg font-semibold text-slate-900">Flux d'import des travailleurs</h2>
              <p className="mt-1 text-sm leading-6 text-slate-500">{helperText}</p>
            </div>
          </div>

          <div className="flex w-full flex-col gap-3 sm:flex-row lg:w-auto">
            <label className="flex-1 lg:w-72">
              <span className="sr-only">Fichier Excel ou CSV</span>
              <input
                type="file"
                accept=".xlsx,.xls,.csv"
                className="block w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2.5 text-sm text-slate-600 file:mr-3 file:rounded-lg file:border-0 file:bg-[#0085A3]/10 file:px-3 file:py-1.5 file:text-sm file:font-medium file:text-[#0085A3]"
                onChange={(event) => setSelectedFile(event.target.files?.[0] || null)}
              />
            </label>
            <Button onClick={handleUpload} loading={uploading} icon={UploadCloud}>
              Importer
            </Button>
          </div>
        </div>

        {notice ? (
          <div className="mt-4 flex items-start gap-2 rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm font-medium text-emerald-700">
            <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0" />
            <span>{notice}</span>
          </div>
        ) : null}

        {error ? (
          <div className="mt-4 flex items-start gap-2 rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm font-medium text-rose-700">
            <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
            <span>{error}</span>
          </div>
        ) : null}
      </Card>

      {activeImport ? (
        <Card className="overflow-visible rounded-2xl p-4 sm:p-5 xl:p-6">
          {/* Top stat strip */}
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <div className="rounded-xl border border-slate-200 bg-slate-50/60 p-4">
              <p className="text-xs font-medium uppercase tracking-wide text-slate-400">Fichier actif</p>
              <p className="mt-2 truncate text-sm font-semibold text-slate-900">{activeImport.filename}</p>
            </div>
            <div className="rounded-xl border border-slate-200 bg-slate-50/60 p-4">
              <p className="text-xs font-medium uppercase tracking-wide text-slate-400">Statut</p>
              <div className="mt-2">
                <Badge tone={statusToneMap[activeImport.status]}>{activeImport.status}</Badge>
              </div>
            </div>
            <div className="rounded-xl border border-slate-200 bg-slate-50/60 p-4">
              <p className="text-xs font-medium uppercase tracking-wide text-slate-400">Lignes détectées</p>
              <p className="mt-2 text-xl font-semibold text-slate-900">{activeImport.imported_rows}</p>
            </div>
            <div className="rounded-xl border border-slate-200 bg-slate-50/60 p-4">
              <p className="text-xs font-medium uppercase tracking-wide text-slate-400">Erreurs de validation</p>
              <p className="mt-2 text-xl font-semibold text-slate-900">{activeImport.validation_errors}</p>
            </div>
          </div>

          <div className="mt-6 grid gap-6 xl:grid-cols-[240px_1fr]">
            {/* Sidebar — one consolidated summary card */}
            <div className="xl:sticky xl:top-6 xl:self-start">
              <Card className="rounded-2xl border border-slate-200 p-5 shadow-none">
                <div className="flex items-center gap-2.5">
                  <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-[#0085A3]/10 text-[#0085A3]">
                    <Link2 className="h-4 w-4" />
                  </div>
                  <div>
                    <h3 className="text-sm font-semibold text-slate-900">Résumé du mapping</h3>
                    <p className="text-xs text-slate-500">Associez chaque colonne à un champ</p>
                  </div>
                </div>

                {/* Progress */}
                <div className="mt-5">
                  <div className="h-1.5 overflow-hidden rounded-full bg-slate-100">
                    <div
                      className="h-full rounded-full bg-[#0085A3] transition-all duration-300"
                      style={{
                        width: `${previewColumns.length ? (mappedCount / previewColumns.length) * 100 : 0}%`,
                      }}
                    />
                  </div>
                  <p className="mt-2 text-xs font-medium text-slate-500">
                    {mappedCount} / {previewColumns.length} colonnes mappées
                  </p>
                </div>

                {/* Mini stats */}
                <div className="mt-5 grid grid-cols-2 gap-2">
                  <div className="flex items-center gap-2 rounded-lg bg-slate-50 px-3 py-2.5">
                    <Rows3 className="h-3.5 w-3.5 text-slate-400" />
                    <div>
                      <p className="text-sm font-semibold text-slate-900">{previewColumns.length}</p>
                      <p className="text-[11px] text-slate-500">Colonnes</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-2 rounded-lg bg-slate-50 px-3 py-2.5">
                    <Sparkles className="h-3.5 w-3.5 text-slate-400" />
                    <div>
                      <p className="text-sm font-semibold text-slate-900">{optionalMappedCount}</p>
                      <p className="text-[11px] text-slate-500">Optionnelles</p>
                    </div>
                  </div>
                </div>

                {/* Required fields checklist */}
                <div className="mt-5 border-t border-slate-100 pt-4">
                  <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">Champs requis</p>
                  <div className="mt-3 space-y-1.5">
                    {requiredFieldStatus.map((field) => (
                      <div key={field.key} className="flex items-center justify-between rounded-lg px-2.5 py-1.5">
                        <span className="text-xs font-medium text-slate-600">{field.label}</span>
                        {field.mapped ? (
                          <CheckCircle2 className="h-4 w-4 text-emerald-600" />
                        ) : (
                          <AlertCircle className="h-4 w-4 text-amber-500" />
                        )}
                      </div>
                    ))}
                  </div>
                </div>

                {/* Validation state */}
                <div
                  className={`mt-4 flex items-start gap-2 rounded-lg border px-3 py-2.5 text-xs font-medium ${
                    hasDuplicateMappedTargets
                      ? "border-amber-200 bg-amber-50 text-amber-800"
                      : "border-emerald-200 bg-emerald-50 text-emerald-800"
                  }`}
                >
                  {hasDuplicateMappedTargets ? (
                    <AlertCircle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                  ) : (
                    <CheckCircle2 className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                  )}
                  <span>
                    {hasDuplicateMappedTargets
                      ? "Un champ scalaire est sélectionné plusieurs fois."
                      : "Aucun doublon scalaire détecté."}
                  </span>
                </div>

                {/* Legend */}
                <div className="mt-5 border-t border-slate-100 pt-4">
                  <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">Légende</p>
                  <div className="mt-3 flex flex-wrap gap-1.5">
                    {legendItems.map(({ tone, label, icon: Icon }) => (
                      <span
                        key={label}
                        className={`inline-flex items-center gap-1 rounded-full border px-2.5 py-1 text-[11px] font-semibold ${toneClasses[tone]}`}
                      >
                        <Icon className="h-3 w-3" />
                        {label}
                      </span>
                    ))}
                  </div>
                </div>

                {/* Actions */}
                <div className="mt-5 flex gap-2 border-t border-slate-100 pt-4">
                  <Button variant="secondary" size="sm" disabled icon={Sparkles} className="flex-1">
                    Auto
                  </Button>
                  <Button variant="ghost" size="sm" disabled icon={RefreshCcw} className="flex-1">
                    Reset
                  </Button>
                </div>
              </Card>
            </div>

            {/* Main mapping table */}
            <div className="min-w-0">
              <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white">
                <div className="flex items-center gap-3 border-b border-slate-200 px-5 py-4">
                  <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-[#0085A3]/10 text-[#0085A3]">
                    <FileSearch className="h-4 w-4" />
                  </div>
                  <div>
                    <h3 className="text-sm font-semibold text-slate-900">Mapper les colonnes Excel</h3>
                    <p className="text-xs text-slate-500">Type, champ applicatif et statut par colonne</p>
                  </div>
                </div>

                {previewColumns.length ? (
                  <>
                    <div className="max-h-[70vh] overflow-auto">
                      <table className="w-full min-w-[950px] border-separate border-spacing-0">
                        <thead className="sticky top-0 z-20">
                          <tr className="bg-slate-50 text-left">
                            <th className="sticky left-0 z-30 w-[22%] border-b border-r border-slate-200 bg-slate-50 px-5 py-3 text-[11px] font-semibold uppercase tracking-wide text-slate-400">
                              Colonne Excel
                            </th>
                            <th className="w-[18%] border-b border-slate-200 px-5 py-3 text-[11px] font-semibold uppercase tracking-wide text-slate-400">
                              Type
                            </th>
                            <th className="w-[28%] border-b border-slate-200 px-5 py-3 text-[11px] font-semibold uppercase tracking-wide text-slate-400">
                              Champ applicatif
                            </th>
                            <th className="w-[16%] border-b border-slate-200 px-5 py-3 text-[11px] font-semibold uppercase tracking-wide text-slate-400">
                              Requis
                            </th>
                            <th className="w-[16%] border-b border-slate-200 px-5 py-3 text-[11px] font-semibold uppercase tracking-wide text-slate-400">
                              Statut
                            </th>
                          </tr>
                        </thead>
                        <tbody>
                          {previewColumns.map((columnName) => {
                            const currentMapping = mapping[columnName] || "";
                            const requiredLabel =
                              currentMapping === "firstName"
                                ? "Prénom"
                                : currentMapping === "lastName"
                                  ? "Nom"
                                  : identityAlternateFields.includes(
                                        currentMapping as (typeof identityAlternateFields)[number],
                                      )
                                    ? "Matricule"
                                    : "";

                            return (
                              <tr key={columnName} className="group transition-colors hover:bg-slate-50/70">
                                <td className="sticky left-0 z-10 border-b border-r border-slate-100 bg-white px-5 py-4 align-top group-hover:bg-[#F6FBFD]">
                                  <p className="text-sm font-semibold text-slate-900">{columnName}</p>
                                  <p className="mt-1 truncate text-xs text-slate-400">
                                    Ex : {String(previewRows[0]?.raw_data_json[columnName] ?? "") || "—"}
                                  </p>
                                </td>
                                <td className="border-b border-slate-100 px-5 py-4 align-top">
                                  <select
                                    value={mappingTypes[columnName] || "medicalFolder"}
                                    className="w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm font-medium text-slate-800 outline-none transition focus:border-[#0085A3]/40 focus:bg-white focus:ring-4 focus:ring-[#0085A3]/10"
                                    onChange={(event) => {
                                      const nextType = event.target.value as ImportFieldMainType;
                                      setMappingTypes((current) => ({
                                        ...current,
                                        [columnName]: nextType,
                                      }));
                                      const currentField = importFieldLookup.get(mapping[columnName] || "");
                                      if (currentField && currentField.mainType !== nextType) {
                                        setMapping((current) => ({
                                          ...current,
                                          [columnName]: "",
                                        }));
                                      }
                                    }}
                                  >
                                    {Object.entries(mainTypeLabels).map(([value, label]) => (
                                      <option key={value} value={value}>
                                        {label}
                                      </option>
                                    ))}
                                  </select>
                                </td>
                                <td className="border-b border-slate-100 px-5 py-4 align-top">
                                  <ImportFieldAutocomplete
                                    value={mapping[columnName] || ""}
                                    fields={importFieldSchema}
                                    mainType={mappingTypes[columnName] || "medicalFolder"}
                                    placeholder="Rechercher un champ"
                                    error={
                                      mapping[columnName] &&
                                      !mapping[columnName].includes("[]") &&
                                      Object.entries(mapping).some(
                                        ([otherColumn, target]) =>
                                          otherColumn !== columnName && target && target === mapping[columnName],
                                      )
                                        ? "Champ déjà mappé ailleurs"
                                        : null
                                    }
                                    onChange={(nextValue) =>
                                      setMapping((current) => ({
                                        ...current,
                                        [columnName]: nextValue,
                                      }))
                                    }
                                  />
                                  {mapping[columnName] && importFieldLookup.get(mapping[columnName]) ? (
                                    <p className="mt-1.5 flex items-center gap-1 text-xs text-slate-400">
                                      <Layers className="h-3 w-3" />
                                      {importFieldLookup.get(mapping[columnName])?.sectionFr} · {mapping[columnName]}
                                    </p>
                                  ) : null}
                                </td>
                                <td className="border-b border-slate-100 px-5 py-4 align-top">
                                  {requiredLabel ? (
                                    <span className="inline-flex items-center gap-1 rounded-full border border-[#0085A3]/20 bg-[#0085A3]/10 px-2.5 py-1 text-[11px] font-semibold text-[#0085A3]">
                                      <CheckCircle2 className="h-3.5 w-3.5" />
                                      {requiredLabel}
                                    </span>
                                  ) : (
                                    <span className="inline-flex items-center gap-1 rounded-full border border-slate-200 bg-slate-50 px-2.5 py-1 text-[11px] font-semibold text-slate-500">
                                      <CircleDashed className="h-3.5 w-3.5" />
                                      Optionnel
                                    </span>
                                  )}
                                </td>
                                <td className="border-b border-slate-100 px-5 py-4 align-top">
                                  {(() => {
                                    const state = getRowState(columnName);
                                    return (
                                      <span
                                        className={`inline-flex rounded-full border px-2.5 py-1 text-[11px] font-semibold ${toneClasses[state.tone]}`}
                                      >
                                        {state.label}
                                      </span>
                                    );
                                  })()}
                                </td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    </div>

                    <div className="sticky bottom-0 z-20 border-t border-slate-200 bg-white/95 px-5 py-4 backdrop-blur">
                      <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
                        <p className="text-xs text-slate-500">
                          Validez le mapping avant de lancer l'import en base.
                        </p>
                        <div className="flex gap-2">
                          <Button
                            variant="secondary"
                            onClick={handleValidateImport}
                            loading={processing === "validating" || processing === "mapping"}
                            disabled={!previewColumns.length}
                          >
                            Valider le mapping
                          </Button>
                          <Button
                            onClick={handleConfirmImport}
                            loading={processing === "confirming"}
                            disabled={activeImport.status !== "validated"}
                          >
                            Lancer l'import
                          </Button>
                        </div>
                      </div>
                    </div>
                  </>
                ) : (
                  <div className="p-6">
                    <EmptyState
                      title="Aperçu indisponible"
                      description="Chargez un fichier valide pour afficher les colonnes à mapper."
                    />
                  </div>
                )}
              </div>
            </div>
          </div>
        </Card>
      ) : null}

      {sampleRows.length ? (
        <Card className="rounded-2xl p-6">
          <h3 className="text-sm font-semibold text-slate-900">Aperçu des données importées</h3>
          <p className="mt-1 text-xs text-slate-500">Extrait de 5 lignes avec erreurs éventuelles.</p>
          <div className="mt-4 overflow-x-auto">
            <table className="min-w-full border-separate border-spacing-0">
              <thead>
                <tr className="bg-slate-50">
                  <th className="border-b border-slate-200 px-4 py-2.5 text-left text-[11px] font-semibold uppercase tracking-wide text-slate-400">
                    Ligne
                  </th>
                  {previewColumns.map((columnName) => (
                    <th
                      key={columnName}
                      className="border-b border-slate-200 px-4 py-2.5 text-left text-[11px] font-semibold uppercase tracking-wide text-slate-400"
                    >
                      {columnName}
                    </th>
                  ))}
                  <th className="border-b border-slate-200 px-4 py-2.5 text-left text-[11px] font-semibold uppercase tracking-wide text-slate-400">
                    Erreurs
                  </th>
                </tr>
              </thead>
              <tbody>
                {sampleRows.map((row) => (
                  <tr key={row.id} className="hover:bg-slate-50/70">
                    <td className="border-b border-slate-100 px-4 py-2.5 text-sm font-medium text-slate-700">
                      {row.row_number}
                    </td>
                    {previewColumns.map((columnName) => (
                      <td
                        key={`${row.id}-${columnName}`}
                        className="border-b border-slate-100 px-4 py-2.5 text-sm text-slate-700"
                      >
                        {String(row.raw_data_json[columnName] ?? "")}
                      </td>
                    ))}
                    <td className="border-b border-slate-100 px-4 py-2.5 text-sm text-rose-600">
                      {(row.errors_json?.errors || []).join(", ")}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      ) : null}

      <DataTable
        rows={history}
        getRowKey={(row) => row.id}
        emptyState={
          <EmptyState
            title="Aucun import"
            description="Importez la première liste nominative pour commencer."
          />
        }
        columns={[
          {
            key: "file",
            title: "Fichier",
            render: (row) => (
              <div className="flex items-center gap-3">
                <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-slate-100 text-slate-500">
                  <FileUp className="h-4 w-4" />
                </div>
                <span className="text-sm font-medium text-slate-800">{row.filename}</span>
              </div>
            ),
          },
          {
            key: "status",
            title: "Statut",
            render: (row) => <Badge tone={statusToneMap[row.status]}>{row.status}</Badge>,
          },
          {
            key: "rows",
            title: "Lignes",
            render: (row) => row.imported_rows,
          },
          {
            key: "validation",
            title: "Erreurs",
            render: (row) => row.validation_errors,
          },
          {
            key: "action",
            title: "Action",
            render: (row) => (
              <Button
                variant="ghost"
                size="sm"
                onClick={() => {
                  setActiveImport(row);
                  setNotice(null);
                  setError(null);
                  void loadPreview(row.id, row.mapping_json);
                }}
              >
                Ouvrir
              </Button>
            ),
          },
        ]}
      />
    </div>
  );
};