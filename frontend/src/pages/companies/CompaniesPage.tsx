import { Fragment, useCallback, useEffect, useMemo, useState } from "react";
import axios from "axios";
import {
  Building2,
  ChevronDown,
  ChevronUp,
  Globe,
  Mail,
  MapPin,
  Pencil,
  Phone,
  Plus,
  Trash2,
  Users,
} from "lucide-react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { branchesApi } from "@/api/branchesApi";
import { companiesApi } from "@/api/companiesApi";
import { drillingSitesApi } from "@/api/drillingSitesApi";
import { workersApi } from "@/api/workersApi";
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
import type { Branch, Company, DrillingSite, Worker } from "@/types/entities";
import { hasValidContractDateRange } from "@/utils/contractDates";
import { formatDisplayDate } from "@/utils/date";
import { mockCompanies } from "@/utils/mockData";
import { isSafetySuspension } from "@/services/syncSafety";

type CompanyFormState = Partial<Company>;
type BranchFormState = Partial<Branch>;
type SiteFormState = Partial<DrillingSite>;
type BranchDraft = {
  id: string;
  name: string;
  address: string;
  location: string;
};

const defaultForm: CompanyFormState = {
  name: "",
  code: "",
  phone: "",
  email: "",
  address: "",
  contract_start_date: "",
  contract_end_date: "",
};

const defaultBranchForm: BranchFormState = {
  name: "",
  company_id: undefined,
  manager_name: "",
  address: "",
  location: "",
};

const defaultSiteForm: SiteFormState = {
  name: "",
  company_id: undefined,
  branch_id: undefined,
  location: "",
  status: "active",
};

const createEmptyBranchDraft = (): BranchDraft => ({
  id: `branch-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
  name: "",
  address: "",
  location: "",
});

const generateCompanyCode = (name: string) => {
  const compact = name
    .trim()
    .toUpperCase()
    .replace(/[^A-Z0-9 ]/g, "")
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 3)
    .map((part) => part.slice(0, 3))
    .join("");

  return compact ? `CMP-${compact}` : "CMP-AUTO";
};

const formatDate = (value?: string) => {
  return formatDisplayDate(value) || "No update";
};

const normalizeCompany = (company: Partial<Company>) =>
  ({
    ...company,
    name: company.name || "Medical Company",
    code: company.code || `CMP-${company.id || "NEW"}`,
    phone: company.phone || "",
    email: company.email || "",
    address: company.address || "",
    contract_start_date: company.contract_start_date || "",
    contract_end_date: company.contract_end_date || "",
    worker_count: company.worker_count || 0,
  }) as Company;

export const CompaniesPage = () => {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const loader = useCallback(companiesApi.list, []);
  const { items, total, page, pageSize, search, loading, error, setPage, setSearch, setItems } =
    usePaginatedResource<Company>(loader, mockCompanies);

  const [modalOpen, setModalOpen] = useState(false);
  const [detailOpen, setDetailOpen] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<Company | null>(null);
  const [deletePassword, setDeletePassword] = useState("");
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [selectedCompany, setSelectedCompany] = useState<Company | null>(null);
  const [expandedCompanyId, setExpandedCompanyId] = useState<number | null>(null);
  const [expandedHierarchyCompanyId, setExpandedHierarchyCompanyId] = useState<number | null>(null);
  const [expandedHierarchyBranchId, setExpandedHierarchyBranchId] = useState<number | null>(null);
  const [form, setForm] = useState<CompanyFormState>(defaultForm);
  const [branchModalOpen, setBranchModalOpen] = useState(false);
  const [siteModalOpen, setSiteModalOpen] = useState(false);
  const [branchForm, setBranchForm] = useState<BranchFormState>(defaultBranchForm);
  const [siteForm, setSiteForm] = useState<SiteFormState>(defaultSiteForm);
  const [editingBranchId, setEditingBranchId] = useState<number | null>(null);
  const [editingSiteId, setEditingSiteId] = useState<number | null>(null);
  const [branchSearch, setBranchSearch] = useState("");
  const [siteSearch, setSiteSearch] = useState("");
  const [branchDrafts, setBranchDrafts] = useState<BranchDraft[]>([]);
  const [allBranches, setAllBranches] = useState<Branch[]>([]);
  const [allSites, setAllSites] = useState<DrillingSite[]>([]);
  const [allWorkers, setAllWorkers] = useState<Worker[]>([]);
  const [formErrors, setFormErrors] = useState<
    Partial<Record<"name" | "code" | "email" | "contract_start_date" | "contract_end_date", string>>
  >({});
  const [contactFilter] = useState<"all" | "has-email" | "missing-email">("all");
  const [saveError, setSaveError] = useState<string | null>(null);
  const [branchSaveError, setBranchSaveError] = useState<string | null>(null);
  const [siteSaveError, setSiteSaveError] = useState<string | null>(null);

  useEffect(() => {
    if (searchParams.get("action") === "create") {
      setEditingId(null);
      setForm(defaultForm);
      setBranchDrafts([createEmptyBranchDraft()]);
      setFormErrors({});
      setSaveError(null);
      setModalOpen(true);
      setSearchParams({}, { replace: true });
    }
  }, [searchParams, setSearchParams]);

  useEffect(() => {
    const loadSupportData = async () => {
      try {
        const [branchesResponse, sitesResponse, workersResponse] = await Promise.all([
          branchesApi.list({ page_size: 1000 }),
          drillingSitesApi.list({ page_size: 1000 }),
          workersApi.list({ page_size: 2000 }),
        ]);
        setAllBranches(branchesResponse.items);
        setAllSites(sitesResponse.items);
        setAllWorkers(workersResponse.items);
      } catch {
        setAllBranches([]);
        setAllSites([]);
        setAllWorkers([]);
      }
    };

    void loadSupportData();
  }, []);

  const branchCountByCompany = useMemo(() => {
    const counts = new Map<number, number>();
    for (const branch of allBranches) {
      counts.set(branch.company_id, (counts.get(branch.company_id) || 0) + 1);
    }
    return counts;
  }, [allBranches]);

  const workerCountByCompany = useMemo(() => {
    const counts = new Map<number, number>();
    for (const worker of allWorkers) {
      counts.set(worker.company_id, (counts.get(worker.company_id) || 0) + 1);
    }
    return counts;
  }, [allWorkers]);

  const siteCountByBranch = useMemo(() => {
    const counts = new Map<number, number>();
    for (const site of allSites) {
      counts.set(site.branch_id, (counts.get(site.branch_id) || 0) + 1);
    }
    return counts;
  }, [allSites]);

  const normalizedItems = useMemo(
    () =>
      items.map((item) =>
        normalizeCompany({
          ...item,
          worker_count: workerCountByCompany.get(item.id) ?? item.worker_count ?? 0,
        }),
      ),
    [items, workerCountByCompany],
  );

  const filteredItems = useMemo(
    () =>
      normalizedItems.filter((item) => {
        if (contactFilter === "has-email") return Boolean(item.email);
        if (contactFilter === "missing-email") return !item.email;
        return true;
      }),
    [contactFilter, normalizedItems],
  );

  const overview = useMemo(
    () => [
      {
        label: "Total Companies",
        value: normalizedItems.length,
        icon: Building2,
      },
      {
        label: "With Email",
        value: normalizedItems.filter((item) => Boolean(item.email)).length,
        icon: Mail,
      },
      {
        label: "With Phone",
        value: normalizedItems.filter((item) => Boolean(item.phone)).length,
        icon: Phone,
      },
      {
        label: "Workers Covered",
        value: allWorkers.length,
        icon: Users,
      },
      {
        label: "Total Branches",
        value: allBranches.length,
        icon: Globe,
      },
      {
        label: "Sites de forage",
        value: allSites.length,
        icon: MapPin,
      },
    ],
    [allBranches.length, allSites.length, allWorkers.length, normalizedItems],
  );

  const hierarchyRows = useMemo(
    () =>
      filteredItems.slice(0, 8).map((company) => {
        const branches = allBranches.filter((branch) => branch.company_id === company.id);
        return {
          company,
          branches: branches.map((branch) => ({
            ...branch,
            sites: allSites.filter((site) => site.branch_id === branch.id),
          })),
        };
      }),
    [allBranches, allSites, filteredItems],
  );

  const filteredBranches = useMemo(
    () =>
      allBranches.filter((branch) =>
        `${branch.name} ${branch.company_name || ""} ${branch.manager_name || ""} ${branch.address || ""}`
          .toLowerCase()
          .includes(branchSearch.toLowerCase()),
      ),
    [allBranches, branchSearch],
  );

  const filteredSites = useMemo(
    () =>
      allSites.filter((site) =>
        `${site.name} ${site.branch_name || ""} ${site.company_name || ""} ${site.location || ""} ${site.status}`
          .toLowerCase()
          .includes(siteSearch.toLowerCase()),
      ),
    [allSites, siteSearch],
  );

  const getBranchName = (branchId?: number | null) => {
    if (!branchId) return "";
    return allBranches.find((branch) => String(branch.id) === String(branchId))?.name || "";
  };

  const getCompanyName = (companyId?: number | null) => {
    if (!companyId) return "";
    return normalizedItems.find((company) => String(company.id) === String(companyId))?.name || "";
  };

  const companyOptions = useMemo(
    () => [
      { label: "Selectionner une entreprise", value: "" },
      ...normalizedItems.map((company) => ({ label: company.name, value: String(company.id) })),
    ],
    [normalizedItems],
  );

  const branchOptionsForSite = useMemo(() => {
    const relatedBranches = siteForm.company_id
      ? allBranches.filter((branch) => branch.company_id === siteForm.company_id)
      : [];

    return [
      { label: siteForm.company_id ? "Selectionner une filiale" : "Selectionner une entreprise d'abord", value: "" },
      ...relatedBranches.map((branch) => ({ label: branch.name, value: String(branch.id) })),
    ];
  }, [allBranches, siteForm.company_id]);

  const resetEditor = () => {
    setEditingId(null);
    setForm(defaultForm);
    setBranchDrafts([]);
    setFormErrors({});
    setSaveError(null);
    setModalOpen(false);
  };

  const openCreateModal = () => {
    setEditingId(null);
    setForm(defaultForm);
    setBranchDrafts([createEmptyBranchDraft()]);
    setFormErrors({});
    setSaveError(null);
    setModalOpen(true);
  };

  const openCreateBranchModal = (company?: Company) => {
    setBranchSaveError(null);
    setEditingBranchId(null);
    setBranchForm({
      ...defaultBranchForm,
      company_id: company?.id,
      company_name: company?.name,
    });
    setBranchModalOpen(true);
  };

  const openEditBranchModal = (branch: Branch) => {
    setBranchSaveError(null);
    setEditingBranchId(branch.id);
    setBranchForm(branch);
    setBranchModalOpen(true);
  };

  const openCreateSiteModal = (company?: Company, branch?: Branch) => {
    setSiteSaveError(null);
    setEditingSiteId(null);
    setSiteForm({
      ...defaultSiteForm,
      company_id: company?.id,
      company_name: company?.name,
      branch_id: branch?.id,
      branch_name: branch?.name,
    });
    setSiteModalOpen(true);
  };

  const openEditSiteModal = (site: DrillingSite) => {
    setSiteSaveError(null);
    setEditingSiteId(site.id);
    setSiteForm(site);
    setSiteModalOpen(true);
  };

  const openEditModal = (company: Company) => {
    setEditingId(company.id);
    setForm(normalizeCompany(company));
    setBranchDrafts([createEmptyBranchDraft()]);
    setFormErrors({});
    setSaveError(null);
    setModalOpen(true);
  };

  const openDetails = (company: Company) => {
    setSelectedCompany(normalizeCompany(company));
    setDetailOpen(true);
  };

  const validateForm = () => {
    const nextErrors: Partial<Record<"name" | "code" | "email" | "contract_start_date" | "contract_end_date", string>> = {};
    if (!form.name?.trim()) nextErrors.name = "Company name is required.";
    if (!generateCompanyCode(form.name || "").trim()) nextErrors.code = "Company code is required.";
    if (form.email?.trim() && !/\S+@\S+\.\S+/.test(form.email.trim())) {
      nextErrors.email = "Enter a valid email address.";
    }
    if (!form.contract_start_date) {
      nextErrors.contract_start_date = "La date de debut du contrat est obligatoire.";
    }
    if (!form.contract_end_date) {
      nextErrors.contract_end_date = "La date de fin du contrat est obligatoire.";
    }
    if (
      form.contract_start_date &&
      form.contract_end_date &&
      !hasValidContractDateRange(form.contract_start_date, form.contract_end_date)
    ) {
      nextErrors.contract_end_date = "La date de fin du contrat doit etre posterieure ou egale a la date de debut.";
    }
    setFormErrors(nextErrors);
    return Object.keys(nextErrors).length === 0;
  };

  const save = async () => {
    if (!validateForm()) return;
    setSaveError(null);
    const preparedForm = {
      ...form,
      code: generateCompanyCode(form.name || ""),
    };
    const validBranchDrafts = branchDrafts.filter((branch) => branch.name.trim());

    try {
      if (editingId) {
        const updated = normalizeCompany(await companiesApi.update(editingId, preparedForm));
        setItems((current) =>
          current.map((item) => (item.id === editingId ? updated : item)),
        );
        if (validBranchDrafts.length) {
          await Promise.all(
            validBranchDrafts.map((branch) =>
              branchesApi.create({
                company_id: editingId,
                name: branch.name,
                address: branch.address || undefined,
                location: branch.location || undefined,
              }),
            ),
          );
        }
      } else {
        const created = normalizeCompany(await companiesApi.create(preparedForm));
        if (validBranchDrafts.length) {
          await Promise.all(
            validBranchDrafts.map((branch) =>
              branchesApi.create({
                company_id: created.id,
                name: branch.name,
                address: branch.address || undefined,
                location: branch.location || undefined,
              }),
            ),
          );
        }
        setItems((current) => [created, ...current]);
      }
      const branchesResponse = await branchesApi.list({ page_size: 1000 });
      setAllBranches(branchesResponse.items);
      resetEditor();
    } catch (requestError) {
      const response = axios.isAxiosError(requestError) ? requestError.response : undefined;
      if (isSafetySuspension(requestError)) setSaveError("Création temporairement suspendue pour la sécurité des données.");
      else if (response?.status === 403) setSaveError("Vous n’avez pas les droits nécessaires pour cette opération.");
      else if (response?.status === 422) {
        const errors: unknown = response.data?.details?.errors;
        if (Array.isArray(errors) && errors.some((error) =>
          Array.isArray(error?.loc) && error.loc[0] === "body" && error.loc[1] === "email",
        )) {
          setFormErrors((current) => ({ ...current, email: "Saisissez une adresse e-mail valide." }));
        }
        setSaveError("Les données saisies sont invalides. Vérifiez les champs du formulaire.");
      }
      else setSaveError("Impossible d’enregistrer l’entreprise.");
    }
  };

  const removeCompany = async () => {
    if (!deleteTarget) return;
    if (!deletePassword.trim()) {
      setDeleteError("Please enter your password to remove this company.");
      return;
    }
    try {
      await companiesApi.remove(deleteTarget.id, { password: deletePassword });
    } catch {
      setDeleteError("Unable to remove this company. Please check your password and try again.");
      return;
    }
    setItems((current) => current.filter((item) => item.id !== deleteTarget.id));
    setExpandedCompanyId((current) => (current === deleteTarget.id ? null : current));
    setDeleteTarget(null);
    setDeletePassword("");
    setDeleteError(null);
  };

  const existingBranchesForEditing = useMemo(
    () => (editingId ? allBranches.filter((branch) => branch.company_id === editingId) : []),
    [allBranches, editingId],
  );

  const saveBranch = async () => {
    setBranchSaveError(null);
    try {
      if (editingBranchId) {
        const updated = await branchesApi.update(editingBranchId, branchForm);
        setAllBranches((current) => current.map((item) => (item.id === editingBranchId ? updated : item)));
      } else {
        const created = await branchesApi.create(branchForm);
        setAllBranches((current) => [created, ...current]);
      }
      setBranchModalOpen(false);
      setBranchForm(defaultBranchForm);
      setEditingBranchId(null);
    } catch (requestError) {
      if (isSafetySuspension(requestError)) setBranchSaveError("Création temporairement suspendue pour la sécurité des données.");
      else if (axios.isAxiosError(requestError) && requestError.response?.status === 403) setBranchSaveError("Vous n’avez pas les droits nécessaires pour cette opération.");
      else setBranchSaveError("Impossible d’enregistrer la filiale.");
    }
  };

  const saveSite = async () => {
    setSiteSaveError(null);
    try {
      if (editingSiteId) {
        const updated = await drillingSitesApi.update(editingSiteId, siteForm);
        setAllSites((current) => current.map((item) => (item.id === editingSiteId ? updated : item)));
      } else {
        const created = await drillingSitesApi.create(siteForm);
        setAllSites((current) => [created, ...current]);
      }
      setSiteModalOpen(false);
      setSiteForm(defaultSiteForm);
      setEditingSiteId(null);
    } catch (requestError) {
      if (isSafetySuspension(requestError)) setSiteSaveError("Création temporairement suspendue pour la sécurité des données.");
      else if (axios.isAxiosError(requestError) && requestError.response?.status === 403) setSiteSaveError("Vous n’avez pas les droits nécessaires pour cette opération.");
      else setSiteSaveError("Impossible d’enregistrer le site.");
    }
  };

  return (
    <div className="space-y-6">
      <SectionHeader
        eyebrow="Organization management"
        title="Enterprise"
        description={
          error ||
          "Gérer l'ensemble des entreprises clientes, mettre à jour les informations de contact, examiner la couverture opérationnelle et tenir à jour les dossiers de l'organisation."
        }
        actionLabel="New Record"
        actionIcon={Plus}
        onAction={openCreateModal}
      />

      <div className="grid gap-4 grid-cols-2 grid-cols-4">
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
          </Card>
        ))}
      </div>

      <Card className="space-y-4 p-4">
        <div className="flex flex-col gap-2 flex-row items-start justify-between">
          <div>
            <h2 className="text-lg font-semibold text-navy-900">Structure opérationnelle</h2>
            <p className="text-sm text-ink-500">
              Company hierarchy from organization to branches and drilling sites.
            </p>
          </div>
          <Badge tone="active">{hierarchyRows.length} organizations shown</Badge>
        </div>

        {hierarchyRows.length ? (
          <div className="space-y-4">
            {hierarchyRows.map(({ company, branches }) => (
              <div
                key={company.id}
                className="rounded-2xl border border-slate-200/80 bg-white/80 p-4 shadow-soft"
              >
                <button
                  type="button"
                  onClick={() => {
                    setExpandedHierarchyCompanyId((current) =>
                      current === company.id ? null : company.id,
                    );
                    setExpandedHierarchyBranchId(null);
                  }}
                  className="flex w-full items-start justify-between gap-3 text-left"
                >
                  <div className="flex items-start gap-3">
                    <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-brand-50 text-brand-700">
                      <Building2 className="h-5 w-5" />
                    </div>
                    <div>
                      <p className="text-sm font-semibold text-navy-900">{company.name}</p>
                      <p className="mt-1 text-xs text-ink-500">{company.code}</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="rounded-full bg-brand-50 px-2.5 py-1 text-[11px] font-semibold text-brand-700">
                      {branches.length} branches
                    </span>
                    <span className="rounded-full bg-slate-100 px-2.5 py-1 text-[11px] font-semibold text-slate-700">
                      {workerCountByCompany.get(company.id) || 0} workers
                    </span>
                    <span className="inline-flex h-9 w-9 items-center justify-center rounded-xl border border-slate-200 bg-white text-ink-500">
                      {expandedHierarchyCompanyId === company.id ? (
                        <ChevronUp className="h-4 w-4" />
                      ) : (
                        <ChevronDown className="h-4 w-4" />
                      )}
                    </span>
                  </div>
                </button>

                {expandedHierarchyCompanyId === company.id ? (
                  <div className="mt-4 space-y-3 border-l-2 border-brand-100 pl-4">
                    {branches.length ? (
                      branches.map((branch) => (
                        <div key={branch.id} className="relative rounded-2xl bg-slate-50/70 p-3">
                          <span className="absolute -left-[1.1rem] top-5 h-2.5 w-2.5 rounded-full bg-brand-500" />
                          <button
                            type="button"
                            onClick={() =>
                              setExpandedHierarchyBranchId((current) =>
                                current === branch.id ? null : branch.id,
                              )
                            }
                            className="flex w-full items-start justify-between gap-3 text-left"
                          >
                            <div>
                              <p className="text-sm font-semibold text-navy-900">{branch.name}</p>
                              <p className="mt-1 text-xs text-ink-500">
                                {branch.location || branch.address || "Branch location not set"}
                              </p>
                            </div>
                            <div className="flex items-center gap-2">
                              <span className="rounded-full bg-white px-2.5 py-1 text-[11px] font-semibold text-slate-700">
                                {siteCountByBranch.get(branch.id) || 0} sites
                              </span>
                              <span className="inline-flex h-8 w-8 items-center justify-center rounded-lg border border-slate-200 bg-white text-ink-500">
                                {expandedHierarchyBranchId === branch.id ? (
                                  <ChevronUp className="h-4 w-4" />
                                ) : (
                                  <ChevronDown className="h-4 w-4" />
                                )}
                              </span>
                            </div>
                          </button>

                          {expandedHierarchyBranchId === branch.id ? (
                            <div className="mt-3 flex flex-wrap gap-2 border-l-2 border-slate-200 pl-4">
                              {branch.sites.length ? (
                                branch.sites.map((site) => (
                                  <div
                                    key={site.id}
                                    className="inline-flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-3 py-2 text-[11px] font-medium text-ink-700 shadow-sm"
                                  >
                                    <MapPin className="h-3.5 w-3.5 text-brand-600" />
                                    {site.name}
                                  </div>
                                ))
                              ) : (
                                <span className="rounded-xl border border-dashed border-slate-200 px-3 py-2 text-[11px] text-ink-400">
                                  No drilling sites linked
                                </span>
                              )}
                            </div>
                          ) : null}
                        </div>
                      ))
                    ) : (
                      <div className="rounded-2xl border border-dashed border-slate-200 px-4 py-4 text-sm text-ink-400">
                        No branches linked to this organization yet.
                      </div>
                    )}
                  </div>
                ) : null}
              </div>
            ))}
          </div>
        ) : (
          <EmptyState
            title="No structure available"
            description="Add organizations, branches, and drilling sites to display the operations graph."
          />
        )}
      </Card>

      <Card className="space-y-4 p-4">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h2 className="text-lg font-semibold text-navy-900">Répertoire des organisations</h2>
            <p className="text-sm text-ink-500">
              Review company records, contacts, and coverage from one workspace.
            </p>
          </div>
          <div className="flex gap-3">
            <SearchInput
              value={search}
              onChange={setSearch}
              placeholder="Search company, code, phone, or email..."
            />
            <Button icon={Plus} onClick={openCreateModal}>
              Nouvelle entreprise
            </Button>
          </div>
        </div>

        {filteredItems.length ? (
          <div className="overflow-hidden rounded-2xl border border-slate-200/80">
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-ink-100 bg-white">
                <thead className="bg-ink-50">
                  <tr>
                    {["Name", "Contact", "Location", "Filiales", "Travailleurs", "Last Update", ""].map((label) => (
                      <th
                        key={label || "toggle"}
                        className="px-4 py-3 text-left text-[11px] font-semibold uppercase tracking-[0.18em] text-ink-500"
                      >
                        {label}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-ink-100">
                  {loading ? (
                    <tr>
                      <td colSpan={7} className="px-4 py-10 text-center text-sm text-ink-500">
                        Loading companies...
                      </td>
                    </tr>
                  ) : (
                    filteredItems.map((row) => {
                      const isExpanded = expandedCompanyId === row.id;
                      return (
                        <Fragment key={row.id}>
                          <tr
                            className="cursor-pointer transition hover:bg-ink-50/70"
                            onClick={() =>
                              setExpandedCompanyId((current) => (current === row.id ? null : row.id))
                            }
                          >
                            <td className="px-4 py-3">
                              <button
                                type="button"
                                onClick={(event) => {
                                  event.stopPropagation();
                                  openDetails(row);
                                }}
                                className="text-left transition hover:text-brand-700"
                              >
                                <p className="font-semibold text-navy-900">{row.name}</p>
                                <p className="mt-0.5 text-[11px] text-ink-400">{row.code}</p>
                              </button>
                            </td>
                            <td className="px-4 py-3">
                              <div className="space-y-1 text-[12px] text-ink-600">
                                <p>{row.phone || "No phone"}</p>
                                <p>{row.email || "No email"}</p>
                              </div>
                            </td>
                            <td className="px-4 py-3 text-[12px] text-ink-600">
                              {row.address || "No address"}
                            </td>
                            <td className="px-4 py-3">
                              <span className="inline-flex min-w-[52px] justify-center rounded-full bg-slate-100 px-2.5 py-1 text-[11px] font-semibold text-slate-700">
                                {branchCountByCompany.get(row.id) || 0}
                              </span>
                            </td>
                            <td className="px-4 py-3">
                              <span className="inline-flex min-w-[52px] justify-center rounded-full bg-brand-50 px-2.5 py-1 text-[11px] font-semibold text-brand-700">
                                {workerCountByCompany.get(row.id) || 0}
                              </span>
                            </td>
                            <td className="px-4 py-3 text-[12px] text-ink-500">
                              {formatDate(row.updated_at)}
                            </td>
                            <td className="px-4 py-3 text-right">
                              <span className="inline-flex h-8 w-8 items-center justify-center rounded-lg border border-slate-200 bg-white text-ink-500">
                                {isExpanded ? (
                                  <ChevronUp className="h-4 w-4" />
                                ) : (
                                  <ChevronDown className="h-4 w-4" />
                                )}
                              </span>
                            </td>
                          </tr>
                          {isExpanded ? (
                            <tr className="bg-slate-50/70">
                              <td colSpan={7} className="px-4 py-4">
                                <div className="flex flex-wrap gap-2">
                                  <Button variant="secondary" size="sm" icon={Pencil} onClick={() => openEditModal(row)}>
                                    Edit Company
                                  </Button>
                                  <Button
                                    variant="ghost"
                                    size="sm"
                                    icon={Plus}
                                    onClick={() => openCreateBranchModal(row)}
                                  >
                                    Add Branch
                                  </Button>
                                  <Button
                                    variant="ghost"
                                    size="sm"
                                    icon={Users}
                                    onClick={() => navigate(`/reports?company_id=${row.id}`)}
                                  >
                                    View Workers
                                  </Button>
                                  <Button
                                    variant="ghost"
                                    size="sm"
                                    icon={Globe}
                                    onClick={() => openCreateSiteModal(row)}
                                  >
                                    Add Site
                                  </Button>
                                  <Button variant="ghost" size="sm" icon={Building2} onClick={() => openDetails(row)}>
                                    View Details
                                  </Button>
                                  <Button
                                    variant="ghost"
                                    size="sm"
                                    icon={Mail}
                                    onClick={() => row.email && window.open(`mailto:${row.email}`, "_self")}
                                    disabled={!row.email}
                                  >
                                    Email
                                  </Button>
                                  <Button
                                    variant="ghost"
                                    size="sm"
                                    icon={Phone}
                                    onClick={() => row.phone && window.open(`tel:${row.phone}`, "_self")}
                                    disabled={!row.phone}
                                  >
                                    Call
                                  </Button>
                                  <Button
                                    variant="ghost"
                                    size="sm"
                                    icon={Trash2}
                                    onClick={() => {
                                      setDeleteTarget(row);
                                      setDeletePassword("");
                                      setDeleteError(null);
                                    }}
                                  >
                                    Remove
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
          </div>
        ) : (
          <EmptyState
            title="No companies match these filters"
            description="Try another search term, reset the contact filter, or add a new company."
            actionLabel="Add Record"
            onAction={openCreateModal}
          />
        )}
      </Card>

      <div className="space-y-6">
        <Card className="space-y-4 p-4">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <h2 className="text-lg font-semibold text-navy-900">Filiales</h2>
              <p className="text-sm text-ink-500">Consultez et gerez toutes les filiales depuis cette page.</p>
            </div>
            <div className="flex gap-3">
              <SearchInput
                value={branchSearch}
                onChange={setBranchSearch}
                placeholder="Rechercher une filiale..."
              />
              <Button icon={Plus} onClick={() => openCreateBranchModal()}>
                Nouvelle filiale
              </Button>
            </div>
          </div>

          <div className="overflow-hidden rounded-2xl border border-slate-200/80">
            <div className="overflow-x-auto bg-white">
              <table className="min-w-full divide-y divide-ink-100">
                <thead className="bg-ink-50">
                  <tr>
                    {["Filiale", "Entreprise", "Adresse", ""].map((label) => (
                      <th key={label || "branch-actions"} className="px-4 py-3 text-left text-[11px] font-semibold uppercase tracking-[0.18em] text-ink-500">
                        {label}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-ink-100">
                  {filteredBranches.length ? (
                    filteredBranches.slice(0, 12).map((branch) => (
                      <tr key={branch.id} className="hover:bg-ink-50/60">
                        <td className="px-4 py-3">
                          <p className="font-semibold text-navy-900">{branch.name}</p>
                          <p className="text-[11px] text-ink-400">{branch.location || "No location"}</p>
                        </td>
                        <td className="px-4 py-3 text-sm text-ink-700">
                          {branch.company_name || getCompanyName(branch.company_id) || "-"}
                        </td>
                        <td className="px-4 py-3 text-sm text-ink-700">{branch.address || "-"}</td>
                        <td className="px-4 py-3 text-right">
                          <div className="flex justify-end gap-2">
                            <Button variant="ghost" size="sm" icon={Pencil} onClick={() => openEditBranchModal(branch)}>
                              Edit
                            </Button>
                            <Button variant="ghost" size="sm" icon={Plus} onClick={() => openCreateSiteModal(normalizedItems.find((item) => item.id === branch.company_id), branch)}>
                              Site
                            </Button>
                          </div>
                        </td>
                      </tr>
                    ))
                  ) : (
                    <tr>
                      <td colSpan={5} className="px-4 py-8 text-center text-sm text-ink-500">
                        Aucune filiale a afficher.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </Card>

        <Card className="space-y-4 p-4">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <h2 className="text-lg font-semibold text-navy-900">Sites de forage</h2>
              <p className="text-sm text-ink-500">Visualisez et ajoutez les sites operationnels depuis la meme page.</p>
            </div>
            <div className="flex gap-3">
              <SearchInput
                value={siteSearch}
                onChange={setSiteSearch}
                placeholder="Rechercher un site..."
              />
              <Button icon={Plus} onClick={() => openCreateSiteModal()}>
                Nouveau site
              </Button>
            </div>
          </div>

          <div className="overflow-hidden rounded-2xl border border-slate-200/80">
            <div className="overflow-x-auto bg-white">
              <table className="min-w-full divide-y divide-ink-100">
                <thead className="bg-ink-50">
                  <tr>
                    {["Site", "Filiale", "Entreprise", "Etat", ""].map((label) => (
                      <th key={label || "site-actions"} className="px-4 py-3 text-left text-[11px] font-semibold uppercase tracking-[0.18em] text-ink-500">
                        {label}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-ink-100">
                  {filteredSites.length ? (
                    filteredSites.slice(0, 12).map((site) => (
                      <tr key={site.id} className="hover:bg-ink-50/60">
                        <td className="px-4 py-3">
                          <p className="font-semibold text-navy-900">{site.name}</p>
                          <p className="text-[11px] text-ink-400">{site.location || "No location"}</p>
                        </td>
                        <td className="px-4 py-3 text-sm text-ink-700">
                          {site.branch_name || getBranchName(site.branch_id) || "-"}
                        </td>
                        <td className="px-4 py-3 text-sm text-ink-700">
                          {site.company_name ||
                            getCompanyName(site.company_id) ||
                            getCompanyName(
                              allBranches.find((branch) => String(branch.id) === String(site.branch_id))?.company_id,
                            ) ||
                            "-"}
                        </td>
                        <td className="px-4 py-3">
                          <Badge tone={site.status}>{site.status}</Badge>
                        </td>
                        <td className="px-4 py-3 text-right">
                          <Button variant="ghost" size="sm" icon={Pencil} onClick={() => openEditSiteModal(site)}>
                            Edit
                          </Button>
                        </td>
                      </tr>
                    ))
                  ) : (
                    <tr>
                      <td colSpan={5} className="px-4 py-8 text-center text-sm text-ink-500">
                        Aucun site de forage a afficher.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </Card>
      </div>

      <Pagination page={page} total={total} pageSize={pageSize} onPageChange={setPage} />

      <Modal
        open={modalOpen}
        title={editingId ? "Edit Record" : "Create Record"}
        onClose={resetEditor}
      >
        <div className="space-y-4">
          {saveError ? (
            <div role="alert" className="rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm font-medium text-rose-700">
              {saveError}
            </div>
          ) : null}
          <div className="grid gap-3 grid-cols-2">
            <Input
              label="Name"
              error={formErrors.name || null}
              value={form.name || ""}
              onChange={(event) => {
                const nextName = event.target.value;
                setForm((current) => ({
                  ...current,
                  name: nextName,
                  code: generateCompanyCode(nextName),
                }));
              }}
            />
            <Input
              label="Code (Auto)"
              error={formErrors.code || null}
              value={generateCompanyCode(form.name || "")}
              readOnly
            />
            <Input
              label="Phone Number"
              value={form.phone || ""}
              onChange={(event) =>
                setForm((current) => ({ ...current, phone: event.target.value }))
              }
            />
            <Input
              label="Email"
              type="email"
              error={formErrors.email || null}
              value={form.email || ""}
              onChange={(event) =>
                setForm((current) => ({ ...current, email: event.target.value }))
              }
            />
            <Input
              label="Contrat valide du"
              type="date"
              error={formErrors.contract_start_date || null}
              value={form.contract_start_date || ""}
              onChange={(event) =>
                setForm((current) => ({ ...current, contract_start_date: event.target.value }))
              }
            />
            <Input
              label="Au"
              type="date"
              error={formErrors.contract_end_date || null}
              value={form.contract_end_date || ""}
              onChange={(event) =>
                setForm((current) => ({ ...current, contract_end_date: event.target.value }))
              }
            />
          </div>

          <label className="block space-y-2">
            <span className="text-sm font-semibold text-navy-800">Adresse</span>
            <textarea
              rows={3}
              value={form.address || ""}
              onChange={(event) =>
                setForm((current) => ({ ...current, address: event.target.value }))
              }
              className="w-full rounded-xl border border-slate-200/80 bg-white/[0.72] px-4 py-3 text-sm text-ink-800 outline-none backdrop-blur-sm transition-all duration-200 placeholder:text-slate-400 focus:border-brand-400 focus:bg-white focus:ring-4 focus:ring-brand-100/70"
            />
          </label>

          <div className="hidden space-y-3 rounded-2xl border border-slate-200/80 bg-slate-50/60 p-4">
            <div className="flex items-center justify-between gap-3">
              <div>
                <h3 className="text-sm font-semibold text-navy-900">Filiales liées à cet enregistrement</h3>
                <p className="mt-1 text-xs text-ink-500">
                  Add one or more branches while saving this organization.
                </p>
              </div>
              <Button
                variant="ghost"
                size="sm"
                icon={Plus}
                onClick={() =>
                  setBranchDrafts((current) => [...current, createEmptyBranchDraft()])
                }
              >
                Add Branch
              </Button>
            </div>

            {editingId && existingBranchesForEditing.length ? (
              <div className="space-y-2">
                <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-ink-400">
                  Existing Branches
                </p>
                <div className="flex flex-wrap gap-2">
                  {existingBranchesForEditing.map((branch) => (
                    <span
                      key={branch.id}
                      className="inline-flex rounded-full border border-slate-200 bg-white px-3 py-1 text-[11px] font-medium text-navy-900"
                    >
                      {branch.name}
                    </span>
                  ))}
                </div>
              </div>
            ) : null}

            <div className="space-y-3">
              {branchDrafts.map((branch, index) => (
                <div
                  key={branch.id}
                  className="grid gap-3 rounded-2xl border border-slate-200/80 bg-white/80 p-3 grid-cols-[minmax(0,1.2fr)_minmax(0,1fr)_minmax(0,1fr)_auto]"
                >
                  <Input
                    label={`Branch ${index + 1}`}
                    value={branch.name}
                    onChange={(event) =>
                      setBranchDrafts((current) =>
                        current.map((item) =>
                          item.id === branch.id ? { ...item, name: event.target.value } : item,
                        ),
                      )
                    }
                  />
                  <Input
                    label="Location"
                    value={branch.location}
                    onChange={(event) =>
                      setBranchDrafts((current) =>
                        current.map((item) =>
                          item.id === branch.id ? { ...item, location: event.target.value } : item,
                        ),
                      )
                    }
                  />
                  <Input
                    label="Address"
                    value={branch.address}
                    onChange={(event) =>
                      setBranchDrafts((current) =>
                        current.map((item) =>
                          item.id === branch.id ? { ...item, address: event.target.value } : item,
                        ),
                      )
                    }
                  />
                  <div className="flex items-end">
                    <Button
                      variant="ghost"
                      size="sm"
                      icon={Trash2}
                      onClick={() =>
                        setBranchDrafts((current) =>
                          current.length === 1
                            ? [createEmptyBranchDraft()]
                            : current.filter((item) => item.id !== branch.id),
                        )
                      }
                    >
                      Remove
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="flex justify-end gap-2">
            <Button variant="secondary" onClick={resetEditor}>
              Cancel
            </Button>
            <Button onClick={() => void save()}>
              {editingId ? "Update" : "Enregistrer"}
            </Button>
          </div>
        </div>
      </Modal>

      <Modal
        open={detailOpen}
        title={selectedCompany?.name || "Details"}
        onClose={() => setDetailOpen(false)}
      >
        {selectedCompany ? (
          <div className="space-y-4">
            <div className="flex flex-wrap items-center gap-2">
              <Badge tone="active">{selectedCompany.code}</Badge>
              <Badge tone="completed">
                {workerCountByCompany.get(selectedCompany.id) || 0} workers
              </Badge>
              <Badge tone="reviewed">
                {branchCountByCompany.get(selectedCompany.id) || 0} branches
              </Badge>
            </div>

            <div className="grid gap-3 grid-cols-2">
              {[
                {
                  label: "Phone",
                  value: selectedCompany.phone || "No phone registered",
                  icon: Phone,
                },
                {
                  label: "Email",
                  value: selectedCompany.email || "No email registered",
                  icon: Mail,
                },
                {
                  label: "Address",
                  value: selectedCompany.address || "No address registered",
                  icon: MapPin,
                },
                {
                  label: "Last Update",
                  value: formatDate(selectedCompany.updated_at),
                  icon: Globe,
                },
                {
                  label: "Contrat valide du",
                  value: selectedCompany.contract_start_date || "Non renseignee",
                  icon: Globe,
                },
                {
                  label: "Au",
                  value: selectedCompany.contract_end_date || "Non renseignee",
                  icon: Globe,
                },
                {
                  label: "Filiales",
                  value: `${branchCountByCompany.get(selectedCompany.id) || 0} active branches`,
                  icon: Building2,
                },
                {
                  label: "Travailleurs",
                  value: `${workerCountByCompany.get(selectedCompany.id) || 0} linked workers`,
                  icon: Users,
                },
              ].map((item) => (
                <Card key={item.label} className="p-4">
                  <div className="flex items-start gap-3">
                    <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-brand-50 text-brand-700">
                      <item.icon className="h-4 w-4" />
                    </div>
                    <div>
                      <p className="text-xs font-semibold uppercase tracking-[0.12em] text-ink-400">
                        {item.label}
                      </p>
                      <p className="mt-2 text-sm font-medium text-navy-900">{item.value}</p>
                    </div>
                  </div>
                </Card>
              ))}
            </div>

            <div className="flex justify-end gap-2">
              <Button
                variant="ghost"
                icon={Plus}
                onClick={() => openCreateBranchModal(selectedCompany)}
              >
                Add Branch
              </Button>
              <Button
                variant="secondary"
                icon={Pencil}
                onClick={() => {
                  setDetailOpen(false);
                  openEditModal(selectedCompany);
                }}
              >
                Edit
              </Button>
            </div>
          </div>
        ) : null}
      </Modal>

      <Modal
        open={branchModalOpen}
        title={editingBranchId ? "Edit Branch" : "Create Branch"}
        onClose={() => {
          setBranchModalOpen(false);
          setBranchForm(defaultBranchForm);
          setEditingBranchId(null);
        }}
      >
        <div className="space-y-4">
          {branchSaveError ? (
            <div role="alert" className="rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm font-medium text-rose-700">
              {branchSaveError}
            </div>
          ) : null}
          <div className="grid gap-3 grid-cols-2">
            <Select
              label="Entreprise"
              options={companyOptions}
              value={branchForm.company_id?.toString() || ""}
              onChange={(event) =>
                setBranchForm((current) => ({
                  ...current,
                  company_id: Number(event.target.value) || undefined,
                  company_name: normalizedItems.find((item) => item.id === Number(event.target.value))?.name,
                }))
              }
            />
            <Input
              label="Nom"
              value={branchForm.name || ""}
              onChange={(event) => setBranchForm((current) => ({ ...current, name: event.target.value }))}
            />
            <Input
              label="Manager"
              value={branchForm.manager_name || ""}
              onChange={(event) => setBranchForm((current) => ({ ...current, manager_name: event.target.value }))}
            />
            <Input
              label="Location"
              value={branchForm.location || ""}
              onChange={(event) => setBranchForm((current) => ({ ...current, location: event.target.value }))}
            />
          </div>
          <Input
            label="Adresse"
            value={branchForm.address || ""}
            onChange={(event) => setBranchForm((current) => ({ ...current, address: event.target.value }))}
          />
          <div className="flex justify-end">
            <Button onClick={() => void saveBranch()}>{editingBranchId ? "Update Branch" : "Save Branch"}</Button>
          </div>
        </div>
      </Modal>

      <Modal
        open={siteModalOpen}
        title={editingSiteId ? "Edit Drilling Site" : "Create Drilling Site"}
        onClose={() => {
          setSiteModalOpen(false);
          setSiteForm(defaultSiteForm);
          setEditingSiteId(null);
        }}
      >
        <div className="space-y-4">
          {siteSaveError ? (
            <div role="alert" className="rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm font-medium text-rose-700">
              {siteSaveError}
            </div>
          ) : null}
          <div className="grid gap-3 grid-cols-2">
            <Select
              label="Entreprise"
              options={companyOptions}
              value={siteForm.company_id?.toString() || ""}
              onChange={(event) =>
                setSiteForm((current) => ({
                  ...current,
                  company_id: Number(event.target.value) || undefined,
                  company_name: normalizedItems.find((item) => item.id === Number(event.target.value))?.name,
                  branch_id: undefined,
                }))
              }
            />
            <Select
              label="Filiale"
              options={branchOptionsForSite}
              value={siteForm.branch_id?.toString() || ""}
              disabled={!siteForm.company_id}
              onChange={(event) =>
                setSiteForm((current) => ({
                  ...current,
                  branch_id: Number(event.target.value) || undefined,
                  branch_name: allBranches.find((item) => item.id === Number(event.target.value))?.name,
                }))
              }
            />
            <Input
              label="Nom du site"
              value={siteForm.name || ""}
              onChange={(event) => setSiteForm((current) => ({ ...current, name: event.target.value }))}
            />
            <Input
              label="Location"
              value={siteForm.location || ""}
              onChange={(event) => setSiteForm((current) => ({ ...current, location: event.target.value }))}
            />
            <Select
              label="Etat"
              options={[
                { label: "Active", value: "active" },
                { label: "Inactive", value: "inactive" },
              ]}
              value={siteForm.status || "active"}
              onChange={(event) =>
                setSiteForm((current) => ({
                  ...current,
                  status: event.target.value as DrillingSite["status"],
                }))
              }
            />
          </div>
          <div className="flex justify-end">
            <Button onClick={() => void saveSite()}>{editingSiteId ? "Update Site" : "Save Site"}</Button>
          </div>
        </div>
      </Modal>

      <Modal
        open={Boolean(deleteTarget)}
        title={deleteTarget ? `Remove ${deleteTarget.name}` : "Remove Record"}
        onClose={() => {
          setDeleteTarget(null);
          setDeletePassword("");
          setDeleteError(null);
        }}
      >
        <div className="space-y-4">
          <p className="text-sm text-ink-600">
            Remove{" "}
            <span className="font-semibold text-navy-900">
              {deleteTarget?.name || "this company"}
            </span>{" "}
            from the directory?
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
            <Button variant="secondary" onClick={() => {
              setDeleteTarget(null);
              setDeletePassword("");
              setDeleteError(null);
            }}>
              Cancel
            </Button>
            <Button variant="danger" onClick={() => void removeCompany()}>
              Remove
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
};
