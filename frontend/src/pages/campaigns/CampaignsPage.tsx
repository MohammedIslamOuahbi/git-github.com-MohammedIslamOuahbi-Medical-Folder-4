import { Fragment, useCallback, useEffect, useMemo, useState } from "react";
import axios from "axios";
import {
  ChevronDown,
  ChevronUp,
  FolderOpen,
  Lock,
  Pencil,
  Plus,
  Trash2,
  Unlock,
  UserPlus,
  Users,
  UserRoundCog,
  FlaskConical,
  Stethoscope,
} from "lucide-react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { branchesApi } from "@/api/branchesApi";
import { campaignsApi } from "@/api/campaignsApi";
import { companiesApi } from "@/api/companiesApi";
import { drillingSitesApi } from "@/api/drillingSitesApi";
import { fetchAllPages } from "@/api/fetchAllPages";
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
import { DataTable } from "@/components/tables/DataTable";
import { Spinner } from "@/components/common/Spinner";
import { useAuth } from "@/hooks/useAuth";
import { usePaginatedResource } from "@/hooks/usePaginatedResource";
import type { Branch, Campaign, Company, DrillingSite, MedicalTest, User, Worker } from "@/types/entities";
import { getTodayYmd, isCompanyContractValidOnDate } from "@/utils/contractDates";
import { formatDisplayDate } from "@/utils/date";
import { hasPermission, hasRole } from "@/utils/permissions";
import { mockCampaigns } from "@/utils/mockData";

type CampaignFormState = Partial<Campaign> & {
  title?: string;
  description?: string | null;
};

type NoticeState = {
  type: "success" | "error";
  message: string;
} | null;

type ConfirmState =
  | { kind: "campaign-delete"; campaign: Campaign }
  | { kind: "doctor-remove"; campaign: Campaign; user: User }
  | { kind: "assistant-remove"; campaign: Campaign; user: User }
  | { kind: "worker-remove"; campaign: Campaign; worker: Worker }
  | { kind: "test-remove"; campaign: Campaign; test: MedicalTest };

const defaultForm: CampaignFormState = {
  status: "draft",
  description: "",
};

const emptyStateBox =
  "rounded-xl border border-dashed border-slate-200/80 bg-slate-50/70 px-4 py-6 text-sm text-ink-500";

const normalizeCampaign = (campaign: Partial<Campaign>) =>
  ({
    ...campaign,
    name: campaign.name || campaign.title || "Campaign",
    title: campaign.title || campaign.name || "Campaign",
    description: campaign.description || "",
  }) as Campaign;

const normalizeWorker = (worker: Record<string, unknown>) =>
  ({
    ...worker,
    employee_code: worker.employee_code || worker.employee_number || "",
    full_name:
      worker.full_name ||
      `${String(worker.first_name || "")} ${String(worker.last_name || "")}`.trim(),
    position: worker.position || worker.job_title || "",
    status: worker.status || ((worker.is_active as boolean | undefined) ? "active" : "inactive"),
  }) as Worker;

const normalizeTest = (test: Record<string, unknown>) =>
  ({
    ...test,
    code: test.code || test.name || "",
    status: test.status || ((test.is_active as boolean | undefined) ? "active" : "inactive"),
  }) as MedicalTest;

const normalizeUser = (user: Partial<User>) =>
  ({
    ...user,
    full_name:
      user.full_name || `${user.first_name || ""} ${user.last_name || ""}`.trim() || "Medical User",
    status: user.status || "active",
  }) as User;

const invalidCompanyContractMessage =
  "Le contrat de cette entreprise est invalide ou expiré. Impossible de créer la campagne.";

export const CampaignsPage = () => {
  const navigate = useNavigate();
  const { user } = useAuth();
  const canManageCampaigns = hasPermission(user, "campaigns:manage");
  const canLockCampaigns = hasPermission(user, "campaigns:lock");
  const isDoctorLikeCampaignView = hasRole(user, ["Doctor", "Assistant"]);
  const canAdminManageCampaigns =
    canManageCampaigns && hasRole(user, ["Admin", "Super Admin"]);
  const [searchParams, setSearchParams] = useSearchParams();
  const fallbackCampaigns = useMemo(
    () =>
      hasRole(user, ["Admin", "Super Admin"])
        ? mockCampaigns.map(normalizeCampaign)
        : [],
    [user],
  );
  const { items, total, page, pageSize, search, loading, error, setPage, setSearch, setItems } =
    usePaginatedResource<Campaign>(useCallback(campaignsApi.list, []), fallbackCampaigns);

  const [open, setOpen] = useState(false);
  const [form, setForm] = useState<CampaignFormState>(defaultForm);
  const [editingCampaign, setEditingCampaign] = useState<Campaign | null>(null);
  const [editorLoading] = useState(false);
  const [savingCampaign, setSavingCampaign] = useState(false);
  const [notice, setNotice] = useState<NoticeState>(null);
  const [formErrors, setFormErrors] = useState<Record<string, string>>({});
  const [actionLoadingKey, setActionLoadingKey] = useState<string | null>(null);
  const [confirmState, setConfirmState] = useState<ConfirmState | null>(null);
  const [deletePassword, setDeletePassword] = useState("");
  const [expandedCampaignId, setExpandedCampaignId] = useState<number | null>(null);

  const [assignedDoctors, setAssignedDoctors] = useState<User[]>([]);
  const [assignedAssistants, setAssignedAssistants] = useState<User[]>([]);
  const [assignedWorkers, setAssignedWorkers] = useState<Worker[]>([]);
  const [assignedTests, setAssignedTests] = useState<MedicalTest[]>([]);
  const [availableCompanies, setAvailableCompanies] = useState<Company[]>([]);
  const [availableBranches, setAvailableBranches] = useState<Branch[]>([]);
  const [availableSites, setAvailableSites] = useState<DrillingSite[]>([]);

  const [availableDoctors, setAvailableDoctors] = useState<User[]>([]);
  const [availableAssistants, setAvailableAssistants] = useState<User[]>([]);
  const [availableWorkers, setAvailableWorkers] = useState<Worker[]>([]);
  const [availableTests, setAvailableTests] = useState<MedicalTest[]>([]);

  const [doctorSearch, setDoctorSearch] = useState("");
  const [assistantSearch, setAssistantSearch] = useState("");
  const [workerSearch, setWorkerSearch] = useState("");
  const [testSearch, setTestSearch] = useState("");

  const currentCampaign = editingCampaign;
  const isLocked = currentCampaign?.status === "completed";

  const canEditCampaign = Boolean(currentCampaign ? !isLocked : true);

  const clearEditorState = () => {
    setEditingCampaign(null);
    setForm(defaultForm);
    setFormErrors({});
    setAssignedDoctors([]);
    setAssignedAssistants([]);
    setAssignedWorkers([]);
    setAssignedTests([]);
    setAvailableDoctors([]);
    setAvailableAssistants([]);
    setAvailableWorkers([]);
    setAvailableTests([]);
    setDoctorSearch("");
    setAssistantSearch("");
    setWorkerSearch("");
    setTestSearch("");
    setActionLoadingKey(null);
  };

  const closeModal = () => {
    setOpen(false);
    clearEditorState();
  };

  const setSuccess = (message: string) => setNotice({ type: "success", message });
  const setFailure = (message: string) => setNotice({ type: "error", message });

  const validateForm = () => {
    const errors: Record<string, string> = {};
    if (!form.company_id) {
      errors.company_id = "Company is required.";
    }
    if (!form.branch_id) {
      errors.branch_id = "Branch is required.";
    }
    if (!form.drilling_site_id) {
      errors.drilling_site_id = "Drilling site is required.";
    }
    if (!form.start_date) {
      errors.start_date = "Start date is required.";
    }
    if (!form.end_date) {
      errors.end_date = "End date is required.";
    }
    if (form.start_date && form.end_date && form.end_date < form.start_date) {
      errors.end_date = "End date cannot be before start date.";
    }
    setFormErrors(errors);
    return Object.keys(errors).length === 0;
  };

  const assertCanMutate = (campaign: Campaign | null) => {
    if (!campaign) return true;
    if (campaign.status === "completed") {
      setFailure("This campaign is locked. Unlock it first to edit assignments or details.");
      return false;
    }
    return true;
  };

  useEffect(() => {
    const loadLocationOptions = async () => {
      try {
        const [companiesResponse, branchesResponse, sitesResponse] = await Promise.all([
          fetchAllPages(companiesApi),
          fetchAllPages(branchesApi),
          fetchAllPages(drillingSitesApi),
        ]);
        setAvailableCompanies(companiesResponse.items);
        setAvailableBranches(branchesResponse.items);
        setAvailableSites(sitesResponse.items);
      } catch {
        setAvailableCompanies([]);
        setAvailableBranches([]);
        setAvailableSites([]);
      }
    };

    void loadLocationOptions();
  }, []);

  const openCreateModal = () => {
    navigate("/campaigns/create");
  };

  const openEditModal = (campaign: Campaign) => {
    navigate(`/campaigns/${campaign.id}/edit`);
  };

  useEffect(() => {
    if (searchParams.get("action") === "create") {
      navigate("/campaigns/create", { replace: true });
      setSearchParams({}, { replace: true });
    }
  }, [navigate, searchParams, setSearchParams]);

  const saveCampaign = async () => {
    if (!validateForm()) return;
    if (editingCampaign && !assertCanMutate(editingCampaign)) return;
    if (!editingCampaign) {
      const selectedCompany =
        availableCompanies.find((item) => item.id === form.company_id) || null;
      if (!isCompanyContractValidOnDate(selectedCompany, getTodayYmd())) {
        setFailure(invalidCompanyContractMessage);
        return;
      }
    }

    setSavingCampaign(true);
    setNotice(null);
    try {
      if (editingCampaign) {
        const updated = await campaignsApi.update(editingCampaign.id, {
          ...form,
          name: form.title || form.name,
        });
        setItems((current) =>
          current.map((item) => (item.id === editingCampaign.id ? normalizeCampaign(updated) : item)),
        );
        setEditingCampaign(normalizeCampaign(updated));
        setForm((current) => ({
          ...current,
          ...normalizeCampaign(updated),
          title: updated.title || updated.name,
          description: updated.description || "",
          start_date: updated.start_date?.slice(0, 10),
          end_date: updated.end_date?.slice(0, 10),
        }));
        setSuccess("Campaign updated successfully.");
      } else {
        const created = await campaignsApi.create({
          ...form,
          name: form.title || form.name,
        });
        const normalizedCreated = normalizeCampaign(created);
        setItems((current) => [normalizedCreated, ...current]);
        setSuccess("Campaign created successfully.");
        closeModal();
      }
    } catch (requestError) {
      if (axios.isAxiosError(requestError)) {
        setFailure(
          (requestError.response?.data as { detail?: { message?: string } } | undefined)?.detail?.message ||
            "Unable to save campaign changes.",
        );
      } else {
        setFailure("Unable to save campaign changes.");
      }
    } finally {
      setSavingCampaign(false);
    }
  };

  const toggleLock = async (campaign: Campaign) => {
    if (!canLockCampaigns) {
      setFailure("Only Super Admin can lock or unlock campaigns.");
      return;
    }
    setActionLoadingKey(`lock-${campaign.id}`);
    setNotice(null);
    try {
      const updated = await campaignsApi.update(campaign.id, {
        status: campaign.status === "completed" ? "active" : "completed",
      });
      const normalizedUpdated = normalizeCampaign(updated);
      setItems((current) => current.map((item) => (item.id === campaign.id ? normalizedUpdated : item)));
      if (editingCampaign?.id === campaign.id) {
        setEditingCampaign(normalizedUpdated);
        setForm((current) => ({
          ...current,
          ...normalizedUpdated,
          title: normalizedUpdated.title || normalizedUpdated.name,
          description: normalizedUpdated.description || "",
          start_date: normalizedUpdated.start_date?.slice(0, 10),
          end_date: normalizedUpdated.end_date?.slice(0, 10),
        }));
      }
      setSuccess(campaign.status === "completed" ? "Campaign unlocked successfully." : "Campaign locked successfully.");
    } catch {
      setFailure("Unable to change campaign lock state.");
    } finally {
      setActionLoadingKey(null);
    }
  };

  const startCampaignDelete = (campaign: Campaign) => {
    setDeletePassword("");
    setConfirmState({ kind: "campaign-delete", campaign });
  };

  const confirmRemoveAssignment = (
    kind: ConfirmState["kind"],
    payload: Campaign | User | Worker | MedicalTest,
    extra?: User | Worker | MedicalTest,
  ) => {
    if (kind === "campaign-delete" || !currentCampaign) return;
    if (kind === "doctor-remove") setConfirmState({ kind, campaign: currentCampaign, user: payload as User });
    if (kind === "assistant-remove") setConfirmState({ kind, campaign: currentCampaign, user: payload as User });
    if (kind === "worker-remove") setConfirmState({ kind, campaign: currentCampaign, worker: payload as Worker });
    if (kind === "test-remove") setConfirmState({ kind, campaign: currentCampaign, test: payload as MedicalTest });
    void extra;
  };

  const performConfirmedAction = async () => {
    if (!confirmState) return;

    if (confirmState.kind === "campaign-delete") {
      if (!deletePassword) {
        setFailure("Please enter your password to remove this campaign.");
        return;
      }
      setActionLoadingKey(`delete-${confirmState.campaign.id}`);
      try {
        await campaignsApi.remove(confirmState.campaign.id, deletePassword);
        setItems((current) => current.filter((item) => item.id !== confirmState.campaign.id));
        setConfirmState(null);
        setDeletePassword("");
        setSuccess("Campaign removed successfully.");
      } catch {
        setFailure("Unable to remove campaign.");
      } finally {
        setActionLoadingKey(null);
      }
      return;
    }

    if (!currentCampaign || !assertCanMutate(currentCampaign)) {
      setConfirmState(null);
      return;
    }

    try {
      if (confirmState.kind === "doctor-remove") {
        setActionLoadingKey(`doctor-remove-${confirmState.user.id}`);
        await campaignsApi.removeDoctor(confirmState.campaign.id, confirmState.user.id);
        setAssignedDoctors((current) => current.filter((item) => item.id !== confirmState.user.id));
        setSuccess("Doctor removed from campaign.");
      }
      if (confirmState.kind === "assistant-remove") {
        setActionLoadingKey(`assistant-remove-${confirmState.user.id}`);
        await campaignsApi.removeAssistant(confirmState.campaign.id, confirmState.user.id);
        setAssignedAssistants((current) => current.filter((item) => item.id !== confirmState.user.id));
        setSuccess("Assistant removed from campaign.");
      }
      if (confirmState.kind === "worker-remove") {
        setActionLoadingKey(`worker-remove-${confirmState.worker.id}`);
        await campaignsApi.removeWorker(confirmState.campaign.id, confirmState.worker.id);
        setAssignedWorkers((current) => current.filter((item) => item.id !== confirmState.worker.id));
        setSuccess("Worker removed from campaign.");
      }
      if (confirmState.kind === "test-remove") {
        setActionLoadingKey(`test-remove-${confirmState.test.id}`);
        await campaignsApi.removeTest(confirmState.campaign.id, confirmState.test.id);
        setAssignedTests((current) => current.filter((item) => item.id !== confirmState.test.id));
        setSuccess("Medical test removed from campaign.");
      }
      setConfirmState(null);
    } catch {
      setFailure("Unable to remove this assignment.");
    } finally {
      setActionLoadingKey(null);
    }
  };

  const addDoctor = async (doctor: User) => {
    if (!currentCampaign || !assertCanMutate(currentCampaign)) return;
    setActionLoadingKey(`doctor-add-${doctor.id}`);
    try {
      const updated = await campaignsApi.addDoctors(currentCampaign.id, [doctor.id]);
      setAssignedDoctors(updated.map(normalizeUser));
      setSuccess("Doctor added to campaign.");
    } catch {
      setFailure("Unable to add doctor to campaign.");
    } finally {
      setActionLoadingKey(null);
    }
  };

  const addAssistant = async (assistant: User) => {
    if (!currentCampaign || !assertCanMutate(currentCampaign)) return;
    setActionLoadingKey(`assistant-add-${assistant.id}`);
    try {
      const updated = await campaignsApi.addAssistants(currentCampaign.id, [assistant.id]);
      setAssignedAssistants(updated.map(normalizeUser));
      setSuccess("Assistant added to campaign.");
    } catch {
      setFailure("Unable to add assistant to campaign.");
    } finally {
      setActionLoadingKey(null);
    }
  };

  const addWorker = async (worker: Worker) => {
    if (!currentCampaign || !assertCanMutate(currentCampaign)) return;
    setActionLoadingKey(`worker-add-${worker.id}`);
    try {
      const updated = await campaignsApi.addWorkers(currentCampaign.id, [worker.id]);
      setAssignedWorkers(updated.map((item) => normalizeWorker(item as unknown as Record<string, unknown>)));
      setSuccess("Worker added to campaign.");
    } catch {
      setFailure("Unable to add worker to campaign.");
    } finally {
      setActionLoadingKey(null);
    }
  };

  const addTest = async (test: MedicalTest) => {
    if (!currentCampaign || !assertCanMutate(currentCampaign)) return;
    setActionLoadingKey(`test-add-${test.id}`);
    try {
      await campaignsApi.addTests(currentCampaign.id, [{ test_id: test.id, required: false }]);
      setAssignedTests((current) =>
        current.some((item) => item.id === test.id) ? current : [...current, test],
      );
      setSuccess("Medical test added to campaign.");
    } catch {
      setFailure("Unable to add medical test to campaign.");
    } finally {
      setActionLoadingKey(null);
    }
  };

  const doctorCandidates = useMemo(() => {
    const assignedIds = new Set(assignedDoctors.map((item) => item.id));
    return availableDoctors.filter(
      (item) =>
        !assignedIds.has(item.id) &&
        `${item.full_name} ${item.email}`.toLowerCase().includes(doctorSearch.toLowerCase()),
    );
  }, [availableDoctors, assignedDoctors, doctorSearch]);

  const assistantCandidates = useMemo(() => {
    const assignedIds = new Set(assignedAssistants.map((item) => item.id));
    return availableAssistants.filter(
      (item) =>
        !assignedIds.has(item.id) &&
        `${item.full_name} ${item.email}`.toLowerCase().includes(assistantSearch.toLowerCase()),
    );
  }, [availableAssistants, assignedAssistants, assistantSearch]);

  const workerCandidates = useMemo(() => {
    const assignedIds = new Set(assignedWorkers.map((item) => item.id));
    return availableWorkers.filter(
      (item) =>
        !assignedIds.has(item.id) &&
        `${item.full_name} ${item.employee_code} ${item.position}`.toLowerCase().includes(workerSearch.toLowerCase()),
    );
  }, [availableWorkers, assignedWorkers, workerSearch]);

  const testCandidates = useMemo(() => {
    const assignedIds = new Set(assignedTests.map((item) => item.id));
    return availableTests.filter(
      (item) =>
        !assignedIds.has(item.id) &&
        `${item.name} ${item.category || ""}`.toLowerCase().includes(testSearch.toLowerCase()),
    );
  }, [availableTests, assignedTests, testSearch]);

  const companyOptions = useMemo(
    () => [
      { label: "Select company", value: "" },
      ...availableCompanies.map((company) => ({
        label: company.name,
        value: String(company.id),
      })),
    ],
    [availableCompanies],
  );

  const companyNameById = useMemo(
    () => new Map(availableCompanies.map((company) => [company.id, company.name])),
    [availableCompanies],
  );

  const branchNameById = useMemo(
    () => new Map(availableBranches.map((branch) => [branch.id, branch.name])),
    [availableBranches],
  );

  const siteNameById = useMemo(
    () => new Map(availableSites.map((site) => [site.id, site.name])),
    [availableSites],
  );

  const branchOptions = useMemo(() => {
    const selectedCompanyId = form.company_id;
    const filteredBranches = selectedCompanyId
      ? availableBranches.filter((branch) => branch.company_id === selectedCompanyId)
      : [];

    return [
      { label: selectedCompanyId ? "Select branch" : "Select company first", value: "" },
      ...filteredBranches.map((branch) => ({
        label: branch.name,
        value: String(branch.id),
      })),
    ];
  }, [availableBranches, form.company_id]);

  const siteOptions = useMemo(() => {
    const filteredSites =
      form.company_id && form.branch_id
        ? availableSites.filter(
            (site) => site.company_id === form.company_id && site.branch_id === form.branch_id,
          )
        : [];

    return [
      {
        label: form.branch_id ? "Select drilling site" : "Select company and branch first",
        value: "",
      },
      ...filteredSites.map((site) => ({
        label: site.name,
        value: String(site.id),
      })),
    ];
  }, [availableSites, form.branch_id, form.company_id]);

  useEffect(() => {
    if (!form.company_id || !form.branch_id) return;
    const branchBelongsToCompany = availableBranches.some(
      (branch) => branch.id === form.branch_id && branch.company_id === form.company_id,
    );
    if (!branchBelongsToCompany) {
      setForm((current) => ({ ...current, branch_id: undefined, drilling_site_id: undefined }));
    }
  }, [availableBranches, form.branch_id, form.company_id]);

  useEffect(() => {
    if (!form.drilling_site_id) return;
    const siteBelongsToSelection = availableSites.some(
      (site) =>
        site.id === form.drilling_site_id &&
        site.company_id === form.company_id &&
        site.branch_id === form.branch_id,
    );
    if (!siteBelongsToSelection) {
      setForm((current) => ({ ...current, drilling_site_id: undefined }));
    }
  }, [availableSites, form.branch_id, form.company_id, form.drilling_site_id]);

  useEffect(() => {
    if (!form.drilling_site_id) return;
    const selectedSite = availableSites.find((site) => site.id === form.drilling_site_id);
    if (!selectedSite) return;
    const autoTitle = `${selectedSite.name} - ${selectedSite.id}`;
    setForm((current) =>
      current.title === autoTitle && current.name === autoTitle
        ? current
        : { ...current, title: autoTitle, name: autoTitle },
    );
  }, [availableSites, form.drilling_site_id]);

  const columns = useMemo(
    () => [
      {
        key: "name",
        title: "Campaign",
        render: (row: Campaign) => (
          <div>
            <Link to={`/campaigns/${row.id}`} className="font-medium text-brand-700">
              {row.title || row.name}
            </Link>
            {row.description ? <p className="mt-1 text-xs text-ink-400">{row.description}</p> : null}
          </div>
        ),
      },
      {
        key: "company",
        title: "Company",
        render: (row: Campaign) => companyNameById.get(row.company_id) || `#${row.company_id}`,
      },
      {
        key: "branch",
        title: "Branch",
        render: (row: Campaign) => branchNameById.get(row.branch_id) || `#${row.branch_id}`,
      },
      {
        key: "drilling_site",
        title: "Drilling Site",
        render: (row: Campaign) =>
          row.drilling_site_id ? siteNameById.get(row.drilling_site_id) || `#${row.drilling_site_id}` : "-",
      },
      {
        key: "window",
        title: "Window",
        render: (row: Campaign) => `${formatDisplayDate(row.start_date)} to ${formatDisplayDate(row.end_date)}`,
      },
      {
        key: "status",
        title: "Status",
        render: (row: Campaign) => (
          <div className="flex items-center gap-2">
            <Badge tone={row.status}>{row.status}</Badge>
            <Badge tone={row.status === "completed" ? "completed" : "active"}>
              {row.status === "completed" ? "Locked" : "Unlocked"}
            </Badge>
          </div>
        ),
      },
    ],
    [branchNameById, companyNameById, siteNameById],
  );

  const assignedWorkerColumns = [
    { key: "worker", title: "Worker", render: (row: Worker) => row.full_name },
    { key: "code", title: "Code", render: (row: Worker) => row.employee_code },
    { key: "position", title: "Position", render: (row: Worker) => row.position || "-" },
    {
      key: "actions",
      title: "",
      render: (row: Worker) => (
        <Button
          variant="ghost"
          size="sm"
          icon={Trash2}
          loading={actionLoadingKey === `worker-remove-${row.id}`}
          disabled={!canEditCampaign}
          onClick={() => confirmRemoveAssignment("worker-remove", row)}
        >
          Remove
        </Button>
      ),
    },
  ];

  const assignedTestColumns = [
    { key: "test", title: "Medical Test", render: (row: MedicalTest) => row.name },
    { key: "category", title: "Category", render: (row: MedicalTest) => row.category || "-" },
    {
      key: "actions",
      title: "",
      render: (row: MedicalTest) => (
        <Button
          variant="ghost"
          size="sm"
          icon={Trash2}
          loading={actionLoadingKey === `test-remove-${row.id}`}
          disabled={!canEditCampaign}
          onClick={() => confirmRemoveAssignment("test-remove", row)}
        >
          Remove
        </Button>
      ),
    },
  ];

  return (
    <div className="space-y-6">
      <SectionHeader
        eyebrow="Field medicine"
        title="Campagnes médicales"
        description={
          error ||
          (isDoctorLikeCampaignView
            ? "Consultez uniquement les campagnes médicales qui vous sont affectées et ouvrez votre espace de travail."
            : "Plan and monitor medical campaigns across field locations.")
        }
        actionLabel={canAdminManageCampaigns ? "New Campaign" : undefined}
        actionIcon={canAdminManageCampaigns ? Plus : undefined}
        onAction={canAdminManageCampaigns ? openCreateModal : undefined}
      />

      {notice ? (
        <Card className={notice.type === "success" ? "border-brand-200 bg-brand-50/70" : "border-rose-200 bg-rose-50/70"}>
          <p className="text-sm font-medium text-ink-700">{notice.message}</p>
        </Card>
      ) : null}

      <SearchInput value={search} onChange={setSearch} placeholder="Search campaigns..." />
      <Card className="overflow-hidden p-0">
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-ink-100">
            <thead className="bg-ink-50">
              <tr>
                {columns.map((column) => (
                  <th
                    key={column.key}
                    className="px-3 py-2 text-left text-[11px] font-semibold uppercase tracking-[0.18em] text-ink-500"
                  >
                    {column.title}
                  </th>
                ))}
                <th className="w-12 px-2 py-2 text-right text-[11px] font-semibold uppercase tracking-[0.18em] text-ink-500">
                  Open
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-ink-100 bg-white">
              {loading ? (
                <tr>
                  <td colSpan={columns.length + 1} className="px-3 py-12 text-center">
                    <div className="flex justify-center">
                      <Spinner />
                    </div>
                  </td>
                </tr>
              ) : items.length === 0 ? (
                <tr>
                  <td colSpan={columns.length + 1} className="p-4">
                    <EmptyState
                      title="No campaigns found"
                      description="Try adjusting your search or create a new campaign."
                    />
                  </td>
                </tr>
              ) : (
                items.map((rawCampaign) => {
                  const campaign = normalizeCampaign(rawCampaign);
                  const isExpanded = expandedCampaignId === campaign.id;

                  return (
                    <Fragment key={campaign.id}>
                      <tr
                        className="cursor-pointer transition-colors hover:bg-ink-50/70"
                        onClick={() =>
                          setExpandedCampaignId((current) => (current === campaign.id ? null : campaign.id))
                        }
                      >
                        {columns.map((column) => (
                          <td key={column.key} className="px-3 py-2 text-sm text-ink-700">
                            {column.render(campaign)}
                          </td>
                        ))}
                        <td className="px-2 py-2 text-right">
                          <button
                            type="button"
                            className="inline-flex h-8 w-8 items-center justify-center rounded-lg bg-slate-100/80 text-slate-600 transition hover:bg-slate-200/80 hover:text-slate-900"
                            onClick={(event) => {
                              event.stopPropagation();
                              setExpandedCampaignId((current) => (current === campaign.id ? null : campaign.id));
                            }}
                            aria-label={isExpanded ? "Hide campaign actions" : "Show campaign actions"}
                          >
                            {isExpanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
                          </button>
                        </td>
                      </tr>
                      {isExpanded ? (
                        <tr className="bg-slate-50/80">
                          <td colSpan={columns.length + 1} className="px-3 py-2">
                            <div className="flex flex-wrap items-center gap-2">
                              <Button
                                variant="secondary"
                                size="sm"
                                icon={FolderOpen}
                                className="h-8 px-3 text-[11px]"
                                onClick={() => navigate(`/app/workspace/${campaign.id}/dashboard`)}
                              >
                                Open Workspace
                              </Button>
                              {canAdminManageCampaigns ? (
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  icon={Pencil}
                                  className="h-8 px-3 text-[11px]"
                                  onClick={() => openEditModal(campaign)}
                                >
                                  Edit
                                </Button>
                              ) : null}
                              {canLockCampaigns ? (
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  icon={campaign.status === "completed" ? Unlock : Lock}
                                  className="h-8 px-3 text-[11px]"
                                  loading={actionLoadingKey === `lock-${campaign.id}`}
                                  onClick={() => void toggleLock(campaign)}
                                >
                                  {campaign.status === "completed" ? "Unlock" : "Lock"}
                                </Button>
                              ) : null}
                              {canAdminManageCampaigns ? (
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  icon={Trash2}
                                  className="h-8 px-3 text-[11px]"
                                  onClick={() => startCampaignDelete(campaign)}
                                >
                                  Delete
                                </Button>
                              ) : null}
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

      <Modal open={open} title={editingCampaign ? "Edit Campaign" : "Create Campaign"} onClose={closeModal}>
        {editorLoading ? (
          <div className="flex min-h-[16rem] flex-col items-center justify-center gap-3">
            <Spinner />
            <p className="text-sm font-medium text-ink-500">Chargement de l'éditeur de campagne...</p>
          </div>
        ) : (
          <div className="space-y-5">
            {editingCampaign ? (
              <div className="flex flex-wrap items-center gap-2">
                <Badge tone={editingCampaign.status}>{editingCampaign.status}</Badge>
                <Badge tone={isLocked ? "completed" : "active"}>{isLocked ? "Locked" : "Unlocked"}</Badge>
                {isLocked ? (
                  <span className="text-xs font-medium text-rose-600">
                    Locked campaigns cannot be edited until a Super Admin unlocks them.
                  </span>
                ) : null}
              </div>
            ) : null}

            <div className="flex grid gap-3 grid-cols-4">
              <Input
                label="Campaign Title"
                value={form.title || form.name || ""}
                onChange={(event) => setForm((current) => ({ ...current, title: event.target.value, name: event.target.value }))}
                disabled={!canEditCampaign}
              />
              <Select
                label="Status"
                options={[
                  { label: "Draft", value: "draft" },
                  { label: "Active", value: "active" },
                  { label: "Terminée", value: "completed" },
                ]}
                value={form.status || "draft"}
                disabled={!canEditCampaign}
                onChange={(event) => setForm((current) => ({ ...current, status: event.target.value as Campaign["status"] }))}
              />
              <Select
                label="Company"
                options={companyOptions}
                error={formErrors.company_id || null}
                value={form.company_id?.toString() || ""}
                disabled={!canEditCampaign}
                onChange={(event) =>
                  setForm((current) => {
                    const nextCompanyId = Number(event.target.value) || undefined;
                    const selectedCompany =
                      availableCompanies.find((item) => item.id === nextCompanyId) || null;
                    if (!editingCampaign && nextCompanyId && !isCompanyContractValidOnDate(selectedCompany, getTodayYmd())) {
                      setFailure(invalidCompanyContractMessage);
                    }
                    return {
                      ...current,
                      company_id: nextCompanyId,
                      branch_id: undefined,
                    };
                  })
                }
              />
              <Select
                label="Branch"
                options={branchOptions}
                error={formErrors.branch_id || null}
                value={form.branch_id?.toString() || ""}
                disabled={!canEditCampaign || !form.company_id}
                onChange={(event) =>
                  setForm((current) => ({
                    ...current,
                    branch_id: Number(event.target.value) || undefined,
                    drilling_site_id: undefined,
                  }))
                }
              />
              <Select
                label="Drilling Site"
                options={siteOptions}
                error={formErrors.drilling_site_id || null}
                value={form.drilling_site_id?.toString() || ""}
                disabled={!canEditCampaign || !form.branch_id}
                onChange={(event) =>
                  setForm((current) => ({
                    ...current,
                    drilling_site_id: Number(event.target.value) || undefined,
                  }))
                }
              />
              <Input
                label="Start Date"
                type="date"
                error={formErrors.start_date || null}
                value={form.start_date?.slice(0, 10) || ""}
                disabled={!canEditCampaign}
                onChange={(event) => setForm((current) => ({ ...current, start_date: event.target.value }))}
              />
              <Input
                label="End Date"
                type="date"
                error={formErrors.end_date || null}
                value={form.end_date?.slice(0, 10) || ""}
                disabled={!canEditCampaign}
                onChange={(event) => setForm((current) => ({ ...current, end_date: event.target.value }))}
              />
            </div>

            <label className="block space-y-2">
              <span className="text-sm font-semibold text-navy-800">Description / Notes</span>
              <textarea
                value={form.description || ""}
                onChange={(event) => setForm((current) => ({ ...current, description: event.target.value }))}
                disabled={!canEditCampaign}
                rows={3}
                className="w-full rounded-xl border border-slate-200/80 bg-white/[0.72] px-4 py-3 text-sm text-ink-800 outline-none backdrop-blur-sm transition-all duration-200 placeholder:text-slate-400 focus:border-brand-400 focus:bg-white focus:ring-4 focus:ring-brand-100/70 disabled:cursor-not-allowed disabled:bg-slate-100/70"
              />
            </label>

            <div className="flex justify-end gap-2">
              <Button variant="ghost" onClick={closeModal}>
                Close
              </Button>
              <Button onClick={() => void saveCampaign()} loading={savingCampaign} disabled={!canEditCampaign}>
                {editingCampaign ? "Save Changes" : "Create Campaign"}
              </Button>
            </div>

            {editingCampaign ? (
              <div className="space-y-5 border-t border-slate-200/80 pt-5">
                <div className="grid gap-5 grid-cols-2">
                  <Card className="p-4">
                    <div className="flex items-center gap-2">
                      <Stethoscope className="h-4 w-4 text-brand-700" />
                      <h4 className="text-base font-semibold text-navy-900">Médecins affectés</h4>
                    </div>
                    <div className="mt-4 space-y-2">
                      {assignedDoctors.length ? assignedDoctors.map((doctor) => (
                        <div key={doctor.id} className="flex items-center justify-between rounded-xl border border-slate-200/80 bg-white/70 px-3 py-2">
                          <div>
                            <p className="text-sm font-medium text-navy-900">{doctor.full_name}</p>
                            <p className="text-xs text-ink-500">{doctor.email}</p>
                          </div>
                          <Button
                            variant="ghost"
                            size="sm"
                            icon={Trash2}
                            loading={actionLoadingKey === `doctor-remove-${doctor.id}`}
                            disabled={!canEditCampaign}
                            onClick={() => confirmRemoveAssignment("doctor-remove", doctor)}
                          >
                            Remove
                          </Button>
                        </div>
                      )) : <div className={emptyStateBox}>Aucun médecin affecté à cette campagne.</div>}
                    </div>
                    <div className="mt-4 space-y-3">
                      <SearchInput value={doctorSearch} onChange={setDoctorSearch} placeholder="Search doctors..." />
                      <div className="max-h-48 space-y-2 overflow-y-auto pr-1">
                        {doctorCandidates.length ? doctorCandidates.map((doctor) => (
                          <div key={doctor.id} className="flex items-center justify-between rounded-xl border border-slate-200/80 bg-slate-50/70 px-3 py-2">
                            <div>
                              <p className="text-sm font-medium text-navy-900">{doctor.full_name}</p>
                              <p className="text-xs text-ink-500">{doctor.email}</p>
                            </div>
                            <Button
                              variant="secondary"
                              size="sm"
                              icon={UserPlus}
                              loading={actionLoadingKey === `doctor-add-${doctor.id}`}
                              disabled={!canEditCampaign}
                              onClick={() => void addDoctor(doctor)}
                            >
                              Add
                            </Button>
                          </div>
                        )) : <div className={emptyStateBox}>Aucun médecin correspondant trouvé.</div>}
                      </div>
                    </div>
                  </Card>

                  <Card className="p-4">
                    <div className="flex items-center gap-2">
                      <UserRoundCog className="h-4 w-4 text-brand-700" />
                      <h4 className="text-base font-semibold text-navy-900">Assistants affectés</h4>
                    </div>
                    <div className="mt-4 space-y-2">
                      {assignedAssistants.length ? assignedAssistants.map((assistant) => (
                        <div key={assistant.id} className="flex items-center justify-between rounded-xl border border-slate-200/80 bg-white/70 px-3 py-2">
                          <div>
                            <p className="text-sm font-medium text-navy-900">{assistant.full_name}</p>
                            <p className="text-xs text-ink-500">{assistant.email}</p>
                          </div>
                          <Button
                            variant="ghost"
                            size="sm"
                            icon={Trash2}
                            loading={actionLoadingKey === `assistant-remove-${assistant.id}`}
                            disabled={!canEditCampaign}
                            onClick={() => confirmRemoveAssignment("assistant-remove", assistant)}
                          >
                            Remove
                          </Button>
                        </div>
                      )) : <div className={emptyStateBox}>Aucun assistant affecté à cette campagne.</div>}
                    </div>
                    <div className="mt-4 space-y-3">
                      <SearchInput value={assistantSearch} onChange={setAssistantSearch} placeholder="Search assistants..." />
                      <div className="max-h-48 space-y-2 overflow-y-auto pr-1">
                        {assistantCandidates.length ? assistantCandidates.map((assistant) => (
                          <div key={assistant.id} className="flex items-center justify-between rounded-xl border border-slate-200/80 bg-slate-50/70 px-3 py-2">
                            <div>
                              <p className="text-sm font-medium text-navy-900">{assistant.full_name}</p>
                              <p className="text-xs text-ink-500">{assistant.email}</p>
                            </div>
                            <Button
                              variant="secondary"
                              size="sm"
                              icon={UserPlus}
                              loading={actionLoadingKey === `assistant-add-${assistant.id}`}
                              disabled={!canEditCampaign}
                              onClick={() => void addAssistant(assistant)}
                            >
                              Add
                            </Button>
                          </div>
                        )) : <div className={emptyStateBox}>Aucun assistant correspondant trouvé.</div>}
                      </div>
                    </div>
                  </Card>
                </div>

                <Card className="p-4">
                  <div className="flex items-center gap-2">
                    <Users className="h-4 w-4 text-brand-700" />
                    <h4 className="text-base font-semibold text-navy-900">Travailleurs affectés</h4>
                  </div>
                  <div className="mt-4">
                    <DataTable
                      columns={assignedWorkerColumns}
                      data={assignedWorkers}
                      emptyTitle="No workers assigned"
                      emptyDescription="Add workers to include them in this campaign."
                    />
                  </div>
                  <div className="mt-4 space-y-3">
                    <SearchInput value={workerSearch} onChange={setWorkerSearch} placeholder="Search workers..." />
                    <div className="max-h-48 space-y-2 overflow-y-auto pr-1">
                      {workerCandidates.length ? workerCandidates.map((worker) => (
                        <div key={worker.id} className="flex items-center justify-between rounded-xl border border-slate-200/80 bg-slate-50/70 px-3 py-2">
                          <div>
                            <p className="text-sm font-medium text-navy-900">{worker.full_name}</p>
                            <p className="text-xs text-ink-500">{worker.employee_code} {worker.position ? `- ${worker.position}` : ""}</p>
                          </div>
                          <Button
                            variant="secondary"
                            size="sm"
                            icon={UserPlus}
                            loading={actionLoadingKey === `worker-add-${worker.id}`}
                            disabled={!canEditCampaign}
                            onClick={() => void addWorker(worker)}
                          >
                            Add
                          </Button>
                        </div>
                      )) : <div className={emptyStateBox}>Aucun travailleur correspondant trouvé.</div>}
                    </div>
                  </div>
                </Card>

                <Card className="p-4">
                  <div className="flex items-center gap-2">
                    <FlaskConical className="h-4 w-4 text-brand-700" />
                    <h4 className="text-base font-semibold text-navy-900">Examens médicaux affectés</h4>
                  </div>
                  <div className="mt-4">
                    <DataTable
                      columns={assignedTestColumns}
                      data={assignedTests}
                      emptyTitle="No medical tests assigned"
                      emptyDescription="Add tests to prepare this campaign package."
                    />
                  </div>
                  <div className="mt-4 space-y-3">
                    <SearchInput value={testSearch} onChange={setTestSearch} placeholder="Search medical tests..." />
                    <div className="max-h-48 space-y-2 overflow-y-auto pr-1">
                      {testCandidates.length ? testCandidates.map((test) => (
                        <div key={test.id} className="flex items-center justify-between rounded-xl border border-slate-200/80 bg-slate-50/70 px-3 py-2">
                          <div>
                            <p className="text-sm font-medium text-navy-900">{test.name}</p>
                            <p className="text-xs text-ink-500">{test.category || "Examen médical"}</p>
                          </div>
                          <Button
                            variant="secondary"
                            size="sm"
                            icon={UserPlus}
                            loading={actionLoadingKey === `test-add-${test.id}`}
                            disabled={!canEditCampaign}
                            onClick={() => void addTest(test)}
                          >
                            Add
                          </Button>
                        </div>
                      )) : <div className={emptyStateBox}>Aucun examen correspondant trouvé.</div>}
                    </div>
                  </div>
                </Card>
              </div>
            ) : null}
          </div>
        )}
      </Modal>

      <Modal
        open={Boolean(confirmState)}
        title="Confirm Action"
        onClose={() => {
          setConfirmState(null);
          setDeletePassword("");
        }}
      >
        <div className="space-y-4">
          <p className="text-sm text-ink-600">
            {confirmState?.kind === "campaign-delete"
              ? `Type your password to remove ${confirmState.campaign.title || confirmState.campaign.name}.`
              : "Please confirm that you want to remove this assignment from the campaign."}
          </p>
          {confirmState?.kind === "campaign-delete" ? (
            <Input
              label="Mot de passe"
              type="password"
              value={deletePassword}
              onChange={(event) => setDeletePassword(event.target.value)}
            />
          ) : null}
        </div>
        <div className="mt-6 flex justify-end gap-2">
          <Button variant="ghost" onClick={() => setConfirmState(null)}>
            Cancel
          </Button>
          <Button
            variant="danger"
            loading={
              confirmState?.kind === "campaign-delete"
                ? actionLoadingKey === `delete-${confirmState.campaign.id}`
                : false
            }
            onClick={() => void performConfirmedAction()}
          >
            Confirm Remove
          </Button>
        </div>
      </Modal>
    </div>
  );
};
