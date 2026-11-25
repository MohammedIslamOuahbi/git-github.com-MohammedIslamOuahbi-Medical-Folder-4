import { useEffect, useMemo, useState } from "react";
import axios from "axios";
import { ArrowLeft, FlaskConical, Lock, MapPinned, Trash2, Unlock, UserPlus, UserRoundCog, Users, Stethoscope } from "lucide-react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { branchesApi } from "@/api/branchesApi";
import { campaignsApi } from "@/api/campaignsApi";
import { companiesApi } from "@/api/companiesApi";
import { drillingSitesApi } from "@/api/drillingSitesApi";
import { fetchAllPages } from "@/api/fetchAllPages";
import { medicalTestsApi } from "@/api/medicalTestsApi";
import { usersApi } from "@/api/usersApi";
import { workersApi } from "@/api/workersApi";
import { Badge } from "@/components/common/Badge";
import { Button } from "@/components/common/Button";
import { Card } from "@/components/common/Card";
import { EmptyState } from "@/components/common/EmptyState";
import { Input } from "@/components/common/Input";
import { Modal } from "@/components/common/Modal";
import { SearchInput } from "@/components/common/SearchInput";
import { SectionHeader } from "@/components/common/SectionHeader";
import { Select } from "@/components/common/Select";
import { Spinner } from "@/components/common/Spinner";
import { DataTable } from "@/components/tables/DataTable";
import { useAuth } from "@/hooks/useAuth";
import type {
  Branch,
  Campaign,
  CampaignTestAssignment,
  Company,
  DrillingSite,
  MedicalTest,
  User,
  Worker,
} from "@/types/entities";
import { getTodayYmd, isCompanyContractValidOnDate } from "@/utils/contractDates";
import { hasPermission } from "@/utils/permissions";
import { mockCampaigns } from "@/utils/mockData";


type CampaignFormState = Partial<Campaign> & {
  title?: string;
  description?: string | null;
};

const medicalTestsLoadError = (error: unknown) =>
  axios.isAxiosError(error) && error.response?.status === 403
    ? "Vous n'avez pas l'autorisation de consulter les tests médicaux."
    : "Impossible de charger les tests médicaux. Vérifiez la connexion au serveur puis rechargez la page.";

type NoticeState = {
  type: "success" | "error";
  message: string;
} | null;

type AssignmentFeedbackState = {
  key: string;
  tone: "added" | "removed";
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
console.log("");
const emptyStateBox =
  "rounded-xl border border-dashed border-slate-200/80 bg-slate-50/70 px-4 py-6 text-sm text-ink-500";

const invalidCompanyContractMessage =
  "Le contrat de cette entreprise est invalide ou expiré. Impossible de créer la campagne.";

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

export const CampaignEditorPage = () => {
  const navigate = useNavigate();
  const { campaignId } = useParams();
  const { user } = useAuth();
  const canManageCampaigns = hasPermission(user, "campaigns:manage");
  const canLockCampaigns = hasPermission(user, "campaigns:lock");
  const isCreateMode = !campaignId || campaignId === "create";
  const fallbackCampaign = useMemo(
    () =>
      isCreateMode
        ? null
        : normalizeCampaign(
            mockCampaigns.find((item) => item.id === Number(campaignId)) || mockCampaigns[0],
          ),
    [campaignId, isCreateMode],
  );

  const [campaign, setCampaign] = useState<Campaign | null>(null);
  const [form, setForm] = useState<CampaignFormState>(defaultForm);
  const [loading, setLoading] = useState(true);
  const [savingCampaign, setSavingCampaign] = useState(false);
  const [notice, setNotice] = useState<NoticeState>(null);
  const [formErrors, setFormErrors] = useState<Record<string, string>>({});
  const [actionLoadingKey, setActionLoadingKey] = useState<string | null>(null);
  const [confirmState, setConfirmState] = useState<ConfirmState | null>(null);
  const [deletePassword, setDeletePassword] = useState("");
  const [assignmentFeedback, setAssignmentFeedback] = useState<AssignmentFeedbackState>(null);

  const [selectedTests, setSelectedTests] = useState<
    Array<{ test_id: number; required: boolean }>
  >([]);
  const [testsError, setTestsError] = useState("");
  const [testsLoadError, setTestsLoadError] = useState("");
  const [testsSuccess, setTestsSuccess] = useState("");

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

  const isLocked = campaign?.status === "completed";
  const canEditCampaign = Boolean(campaign && !isLocked);

  const setSuccess = (message: string) => setNotice({ type: "success", message });
  const setFailure = (message: string) => setNotice({ type: "error", message });

  const isTestSelected = (testId: number) => {
    return selectedTests.some((t) => t.test_id === testId);
  };

  const toggleTest = (testId: number) => {
    setSelectedTests((prev) => {
      const exists = prev.some((t) => t.test_id === testId);

      if (exists) {
        return prev.filter((t) => t.test_id !== testId);
      }

      return [...prev, { test_id: testId, required: false }];
    });
  };

  const toggleRequired = (testId: number) => {
    setSelectedTests((prev) =>
      prev.map((t) =>
        t.test_id === testId ? { ...t, required: !t.required } : t
      )
    );
  };

  const selectAllTests = () => {
    setSelectedTests(
      availableTests.map((test) => ({
        test_id: test.id,
        required: false,
      }))
    );
  };

  const clearAllTests = () => {
    setSelectedTests([]);
  };

  const getAssignmentRowClassName = (key: string, status: "assigned" | "available") => {
    const baseClassName =
      "flex items-center justify-between rounded-xl border px-3 py-2 transition-all duration-300";
    const defaultClassName =
      status === "assigned"
        ? `${baseClassName} border-emerald-200 bg-emerald-50/80`
        : `${baseClassName} border-rose-200 bg-rose-50/70`;
    if (assignmentFeedback?.key !== key) {
      return defaultClassName;
    }
    return assignmentFeedback.tone === "added"
      ? `${baseClassName} border-teal-300 bg-teal-50 ring-2 ring-teal-100`
      : `${baseClassName} border-amber-300 bg-amber-50 ring-2 ring-amber-100`;
  };

  const validateForm = () => {
    const errors: Record<string, string> = {};
    if (!form.company_id) errors.company_id = "Company is required.";
    if (!form.branch_id) errors.branch_id = "Branch is required.";
    if (!form.drilling_site_id) errors.drilling_site_id = "Drilling site is required.";
    if (!form.start_date) errors.start_date = "Start date is required.";
    if (!form.end_date) errors.end_date = "End date is required.";
    if (form.start_date && form.end_date && form.end_date < form.start_date) {
      errors.end_date = "End date cannot be before start date.";
    }
    setFormErrors(errors);
    return Object.keys(errors).length === 0;
  };

  const assertCanMutate = (currentCampaign: Campaign | null) => {
    if (!currentCampaign) return false;
    if (currentCampaign.status === "completed") {
      setFailure("This campaign is locked. Unlock it first to edit assignments or details.");
      return false;
    }
    return true;
  };

  useEffect(() => {
    const run = async () => {
      setLoading(true);
      setNotice(null);
      setTestsLoadError("");
      if (!canManageCampaigns) {
        setLoading(false);
        return;
      }
      if (isCreateMode) {
        const results = await Promise.allSettled([
          usersApi.doctors({ page_size: 500 }),
          usersApi.assistants({ page_size: 500 }),
          workersApi.list({ page_size: 500 }),
          fetchAllPages({ list: (params) => medicalTestsApi.list({ ...params, active: true }) }),
          fetchAllPages(companiesApi),
          fetchAllPages(branchesApi),
          fetchAllPages(drillingSitesApi),
        ]);

        const allDoctors = results[0].status === "fulfilled" ? results[0].value : [];
        const allAssistants = results[1].status === "fulfilled" ? results[1].value : [];
        const allWorkersResponse =
          results[2].status === "fulfilled" ? results[2].value : { items: [] as Worker[] };
        const allTestsResponse =
          results[3].status === "fulfilled" ? results[3].value : { items: [] as MedicalTest[] };
        if (results[3].status === "rejected") {
          setTestsLoadError(medicalTestsLoadError(results[3].reason));
        }
        const companiesResponse =
          results[4].status === "fulfilled" ? results[4].value : { items: [] as Company[] };
        const branchesResponse =
          results[5].status === "fulfilled" ? results[5].value : { items: [] as Branch[] };
        const sitesResponse =
          results[6].status === "fulfilled" ? results[6].value : { items: [] as DrillingSite[] };

        setCampaign(null);
        setForm(defaultForm);
        setAssignedDoctors([]);
        setAssignedAssistants([]);
        setAssignedWorkers([]);
        setAssignedTests([]);
        setSelectedTests([]);
        setTestsError("");
        setTestsSuccess("");
        setAvailableDoctors(allDoctors.map(normalizeUser));
        setAvailableAssistants(allAssistants.map(normalizeUser));
        setAvailableWorkers(
          allWorkersResponse.items.map((item) =>
            normalizeWorker(item as unknown as Record<string, unknown>),
          ),
        );
        setAvailableTests(
          allTestsResponse.items.map((item) =>
            normalizeTest(item as unknown as Record<string, unknown>),
          ),
        );
        setAvailableCompanies(companiesResponse.items);
        setAvailableBranches(branchesResponse.items);
        setAvailableSites(sitesResponse.items);

        if (results.some((item) => item.status === "rejected")) {
          setFailure("Some campaign editor data could not be loaded. Partial data is shown.");
        }
        setLoading(false);
        return;
      }

      const id = Number(campaignId);
      if (!id) {
        setLoading(false);
        setFailure("Campaign id is invalid.");
        return;
      }

      const results = await Promise.allSettled([
        campaignsApi.get(id),
        campaignsApi.doctors(id),
        campaignsApi.assistants(id),
        campaignsApi.workers(id),
        campaignsApi.tests(id),
        usersApi.doctors({ page_size: 500 }),
        usersApi.assistants({ page_size: 500 }),
        workersApi.list({ page_size: 500 }),
        fetchAllPages({ list: (params) => medicalTestsApi.list({ ...params, active: true }) }),
        fetchAllPages(companiesApi),
        fetchAllPages(branchesApi),
        fetchAllPages(drillingSitesApi),
      ]);

      const campaignDetails =
        results[0].status === "fulfilled"
          ? results[0].value
          : fallbackCampaign || mockCampaigns[0];
      const doctors = results[1].status === "fulfilled" ? results[1].value : [];
      const assistants = results[2].status === "fulfilled" ? results[2].value : [];
      const workers = results[3].status === "fulfilled" ? results[3].value : [];
      const tests = results[4].status === "fulfilled" ? results[4].value : [];
      const allDoctors = results[5].status === "fulfilled" ? results[5].value : [];
      const allAssistants = results[6].status === "fulfilled" ? results[6].value : [];
      const allWorkersResponse =
        results[7].status === "fulfilled" ? results[7].value : { items: [] as Worker[] };
      const allTestsResponse =
        results[8].status === "fulfilled" ? results[8].value : { items: [] as MedicalTest[] };
      if (results[8].status === "rejected") {
        setTestsLoadError(medicalTestsLoadError(results[8].reason));
      }
      const companiesResponse =
        results[9].status === "fulfilled" ? results[9].value : { items: [] as Company[] };
      const branchesResponse =
        results[10].status === "fulfilled" ? results[10].value : { items: [] as Branch[] };
      const sitesResponse =
        results[11].status === "fulfilled" ? results[11].value : { items: [] as DrillingSite[] };
      const campaignTestsResponse = tests as CampaignTestAssignment[];

      const normalizedAvailableTests = allTestsResponse.items.map((item) =>
        normalizeTest(item as unknown as Record<string, unknown>),
      );

      setAvailableTests(normalizedAvailableTests);

      setSelectedTests(
        campaignTestsResponse.map((item) => ({
          test_id: item.test_id,
          required: item.required,
        })),
      );

      setAssignedTests(
        normalizedAvailableTests.filter((test) =>
          campaignTestsResponse.some((item) => item.test_id === test.id),
        ),
      );

      const normalizedCampaign = normalizeCampaign(campaignDetails);
      setCampaign(normalizedCampaign);
      setForm({
        ...normalizedCampaign,
        title: normalizedCampaign.title || normalizedCampaign.name,
        description: normalizedCampaign.description || "",
        start_date: normalizedCampaign.start_date?.slice(0, 10),
        end_date: normalizedCampaign.end_date?.slice(0, 10),
      });
      setAssignedDoctors(doctors.map(normalizeUser));
      setAssignedAssistants(assistants.map(normalizeUser));
      setAssignedWorkers(workers.map((item) => normalizeWorker(item as unknown as Record<string, unknown>)));
      setAvailableDoctors(allDoctors.map(normalizeUser));
      setAvailableAssistants(allAssistants.map(normalizeUser));
      setAvailableWorkers(allWorkersResponse.items.map((item) => normalizeWorker(item as unknown as Record<string, unknown>)));

      setAvailableCompanies(companiesResponse.items);
      setAvailableBranches(branchesResponse.items);
      setAvailableSites(sitesResponse.items);

      if (results.some((item) => item.status === "rejected")) {
        setFailure("Some campaign editor data could not be loaded. Partial data is shown.");
      }
      setLoading(false);
    };

    void run();
  }, [campaignId, canManageCampaigns, fallbackCampaign, isCreateMode]);

  const saveCampaign = async () => {
  if (testsLoadError) {
    setFailure(testsLoadError);
    return;
  }
  if (!validateForm()) return;
  if (campaign && !assertCanMutate(campaign)) return;

  if (isCreateMode) {
    const selectedCompany =
      availableCompanies.find((item) => item.id === form.company_id) || null;

    if (!isCompanyContractValidOnDate(selectedCompany, getTodayYmd())) {
      setFailure(invalidCompanyContractMessage);
      return;
    }
  }

  setSavingCampaign(true);
  setNotice(null);
  setTestsError("");
  setTestsSuccess("");

  try {
    if (isCreateMode) {
      const created = await campaignsApi.create({
        ...form,
        name: form.title || form.name,
      });

      await campaignsApi.updateTests(created.id, selectedTests);

      setTestsSuccess("Tests médicaux enregistrés avec succès.");
      navigate(`/campaigns/${created.id}/edit`);
      return;
    }

    if (!campaign) return;

    const updated = await campaignsApi.update(campaign.id, {
      ...form,
      name: form.title || form.name,
    });

    await campaignsApi.updateTests(campaign.id, selectedTests);

    const normalizedUpdated = normalizeCampaign(updated);

    setCampaign(normalizedUpdated);
    setForm((current) => ({
      ...current,
      ...normalizedUpdated,
      title: normalizedUpdated.title || normalizedUpdated.name,
      description: normalizedUpdated.description || "",
      start_date: normalizedUpdated.start_date?.slice(0, 10),
      end_date: normalizedUpdated.end_date?.slice(0, 10),
    }));

    setTestsSuccess("Tests médicaux enregistrés avec succès.");
    setSuccess("Campaign updated successfully.");
  } catch (requestError) {
    if (axios.isAxiosError(requestError)) {
      const message =
        (requestError.response?.data as { message?: string } | undefined)?.message ||
        (requestError.response?.data as { detail?: { message?: string } } | undefined)?.detail?.message ||
        "Unable to save campaign changes.";

      setFailure(message);
      setTestsError(message);
    } else {
      setFailure("Unable to save campaign changes.");
      setTestsError("Erreur lors de l'enregistrement des tests médicaux.");
    }
  } finally {
    setSavingCampaign(false);
  }
};
  const toggleLock = async () => {
    if (!campaign) return;
    if (!canLockCampaigns) {
      setFailure("Only Super Admin can lock or unlock campaigns.");
      return;
    }
    setActionLoadingKey(`lock-${campaign.id}`);
    try {
      const updated = await campaignsApi.update(campaign.id, {
        status: campaign.status === "completed" ? "active" : "completed",
      });
      const normalizedUpdated = normalizeCampaign(updated);
      setCampaign(normalizedUpdated);
      setForm((current) => ({
        ...current,
        ...normalizedUpdated,
        title: normalizedUpdated.title || normalizedUpdated.name,
        description: normalizedUpdated.description || "",
        start_date: normalizedUpdated.start_date?.slice(0, 10),
        end_date: normalizedUpdated.end_date?.slice(0, 10),
      }));
      setSuccess(campaign.status === "completed" ? "Campaign unlocked successfully." : "Campaign locked successfully.");
    } catch {
      setFailure("Unable to change campaign lock state.");
    } finally {
      setActionLoadingKey(null);
    }
  };

  const startCampaignDelete = () => {
    if (!campaign) return;
    setDeletePassword("");
    setConfirmState({ kind: "campaign-delete", campaign });
  };

  const confirmRemoveAssignment = (
    kind: Exclude<ConfirmState["kind"], "campaign-delete">,
    payload: User | Worker | MedicalTest,
  ) => {
    if (!campaign) return;
    if (kind === "doctor-remove") setConfirmState({ kind, campaign, user: payload as User });
    if (kind === "assistant-remove") setConfirmState({ kind, campaign, user: payload as User });
    if (kind === "worker-remove") setConfirmState({ kind, campaign, worker: payload as Worker });
    if (kind === "test-remove") setConfirmState({ kind, campaign, test: payload as MedicalTest });
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
        navigate("/campaigns");
      } catch {
        setFailure("Unable to remove campaign.");
      } finally {
        setActionLoadingKey(null);
      }
      return;
    }
    if (!assertCanMutate(campaign)) {
      setConfirmState(null);
      return;
    }
    try {
      if (confirmState.kind === "doctor-remove") {
        setActionLoadingKey(`doctor-remove-${confirmState.user.id}`);
        await campaignsApi.removeDoctor(confirmState.campaign.id, confirmState.user.id);
        setAssignedDoctors((current) => current.filter((item) => item.id !== confirmState.user.id));
        setAssignmentFeedback({ key: `doctor-${confirmState.user.id}`, tone: "removed" });
        setSuccess("Doctor removed from campaign.");
      }
      if (confirmState.kind === "assistant-remove") {
        setActionLoadingKey(`assistant-remove-${confirmState.user.id}`);
        await campaignsApi.removeAssistant(confirmState.campaign.id, confirmState.user.id);
        setAssignedAssistants((current) => current.filter((item) => item.id !== confirmState.user.id));
        setAssignmentFeedback({ key: `assistant-${confirmState.user.id}`, tone: "removed" });
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
    if (!campaign || !assertCanMutate(campaign)) return;
    setActionLoadingKey(`doctor-add-${doctor.id}`);
    try {
      const updated = await campaignsApi.addDoctors(campaign.id, [doctor.id]);
      setAssignedDoctors(updated.map(normalizeUser));
      setAssignmentFeedback({ key: `doctor-${doctor.id}`, tone: "added" });
      setSuccess("Doctor added to campaign.");
    } catch {
      setFailure("Unable to add doctor to campaign.");
    } finally {
      setActionLoadingKey(null);
    }
  };

  const addAssistant = async (assistant: User) => {
    if (!campaign || !assertCanMutate(campaign)) return;
    setActionLoadingKey(`assistant-add-${assistant.id}`);
    try {
      const updated = await campaignsApi.addAssistants(campaign.id, [assistant.id]);
      setAssignedAssistants(updated.map(normalizeUser));
      setAssignmentFeedback({ key: `assistant-${assistant.id}`, tone: "added" });
      setSuccess("Assistant added to campaign.");
    } catch {
      setFailure("Unable to add assistant to campaign.");
    } finally {
      setActionLoadingKey(null);
    }
  };

  const addWorker = async (worker: Worker) => {
    if (!campaign || !assertCanMutate(campaign)) return;
    setActionLoadingKey(`worker-add-${worker.id}`);
    try {
      const updated = await campaignsApi.addWorkers(campaign.id, [worker.id]);
      setAssignedWorkers(updated.map((item) => normalizeWorker(item as unknown as Record<string, unknown>)));
      setSuccess("Worker added to campaign.");
    } catch {
      setFailure("Unable to add worker to campaign.");
    } finally {
      setActionLoadingKey(null);
    }
  };

  const addTest = (test: MedicalTest) => {
    if (!campaign || !assertCanMutate(campaign)) return;

    setAssignedTests((current) => {
      if (current.some((item) => item.id === test.id)) return current;
      return [...current, test];
    });

    setSelectedTests((current) => {
      if (current.some((item) => item.test_id === test.id)) return current;

      return [
        ...current,
        {
          test_id: test.id,
          required: false,
        },
      ];
    });

    setTestsSuccess("");
    setTestsError("");
  };
  const doctorCandidates = useMemo(
    () =>
      [...availableDoctors, ...assignedDoctors]
        .filter(
          (item, index, array) =>
            array.findIndex((entry) => entry.id === item.id) === index,
        )
        .filter((item) =>
        `${item.full_name} ${item.email}`.toLowerCase().includes(doctorSearch.toLowerCase()),
      ),
    [availableDoctors, assignedDoctors, doctorSearch],
  );

  const doctorAssignedCandidates = useMemo(
    () => doctorCandidates.filter((doctor) => assignedDoctors.some((item) => item.id === doctor.id)),
    [assignedDoctors, doctorCandidates],
  );

  const doctorAvailableCandidates = useMemo(
    () => doctorCandidates.filter((doctor) => !assignedDoctors.some((item) => item.id === doctor.id)),
    [assignedDoctors, doctorCandidates],
  );

  const assistantCandidates = useMemo(
    () =>
      [...availableAssistants, ...assignedAssistants]
        .filter(
          (item, index, array) =>
            array.findIndex((entry) => entry.id === item.id) === index,
        )
        .filter((item) =>
        `${item.full_name} ${item.email}`.toLowerCase().includes(assistantSearch.toLowerCase()),
      ),
    [availableAssistants, assignedAssistants, assistantSearch],
  );

  const assistantAssignedCandidates = useMemo(
    () => assistantCandidates.filter((assistant) => assignedAssistants.some((item) => item.id === assistant.id)),
    [assignedAssistants, assistantCandidates],
  );

  const assistantAvailableCandidates = useMemo(
    () => assistantCandidates.filter((assistant) => !assignedAssistants.some((item) => item.id === assistant.id)),
    [assignedAssistants, assistantCandidates],
  );

  const workerCandidates = useMemo(() => {
    const assignedIds = new Set(assignedWorkers.map((item) => item.id));
    return availableWorkers.filter(
      (item) =>
        !assignedIds.has(item.id) &&
        `${item.full_name} ${item.employee_code} ${item.position}`.toLowerCase().includes(workerSearch.toLowerCase()),
    );
  }, [availableWorkers, assignedWorkers, workerSearch]);

  const testCandidates = useMemo(() => {
    return availableTests.filter((item) =>
      `${item.label || item.name} ${item.section || item.category || ""}`
        .toLowerCase()
        .includes(testSearch.toLowerCase()),
    );
  }, [availableTests, testSearch]);

  const groupedTestCandidates = useMemo(() => {
    return testCandidates.reduce<Record<string, MedicalTest[]>>((groups, test) => {
      const section = test.section || test.category || "Examen médical";
      if (!groups[section]) {
        groups[section] = [];
      }
      groups[section].push(test);
      return groups;
    }, {});
  }, [testCandidates]);

  const selectedTestIds = useMemo(
    () => new Set(selectedTests.map((item) => item.test_id)),
    [selectedTests],
  );

  useEffect(() => {
    setAssignedTests(availableTests.filter((test) => selectedTestIds.has(test.id)));
  }, [availableTests, selectedTestIds]);

  const renderCampaignTestsSelector = (disabled: boolean) => (
    <div className="space-y-4 rounded-2xl border border-slate-200/80 bg-slate-50/60 px-4 py-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-sm font-semibold text-navy-900">Tests medicaux</p>
          <p className="text-xs text-ink-500">
            Selectionnez les tests de la campagne et cochez ceux qui sont obligatoires.
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="ghost" size="sm" onClick={clearAllTests} disabled={disabled}>
            Clear all
          </Button>
          <Button variant="secondary" size="sm" onClick={selectAllTests} disabled={disabled}>
            Select all
          </Button>
        </div>
      </div>

      <SearchInput
        value={testSearch}
        onChange={setTestSearch}
        placeholder="Search medical tests..."
      />

      {testsError ? (
        <p className="text-sm font-medium text-rose-600">{testsError}</p>
      ) : null}
      {testsSuccess ? (
        <p className="text-sm font-medium text-emerald-700">{testsSuccess}</p>
      ) : null}

      <div className="max-h-80 space-y-4 overflow-y-auto pr-1">
        {testCandidates.length ? (
          Object.entries(groupedTestCandidates).map(([section, tests]) => (
            <div key={section} className="space-y-3">
              <p className="text-xs font-bold uppercase tracking-wide text-ink-500">{section}</p>
              {tests.map((test) => {
                const selected = selectedTests.find((item) => item.test_id === test.id);

                return (
                  <div
                    key={test.id}
                    className="flex items-center justify-between gap-4 rounded-2xl border border-slate-200 bg-white px-4 py-3"
                  >
                    <label className="flex items-start gap-3">
                      <input
                        type="checkbox"
                        className="mt-1 h-4 w-4 rounded border-slate-300 text-brand-600 focus:ring-brand-500"
                        checked={selectedTestIds.has(test.id)}
                        disabled={disabled}
                        onChange={() => toggleTest(test.id)}
                      />
                      <div>
                        <p className="text-sm font-semibold text-navy-900">  {test.label || test.name}</p>
                        <p className="text-xs text-ink-500">
                          {test.section || test.category || "Examen medical"}
                        </p>
                      </div>
                    </label>

                    {selected ? (
                      <label className="flex items-center gap-2 text-sm font-medium text-ink-600">
                        <input
                          type="checkbox"
                          className="h-4 w-4 rounded border-slate-300 text-brand-600 focus:ring-brand-500"
                          checked={selected.required}
                          disabled={disabled}
                          onChange={() => toggleRequired(test.id)}
                        />
                        Obligatoire
                      </label>
                    ) : null}
                  </div>
                );
              })}
            </div>
          ))
        ) : (
          <div className={emptyStateBox} role={testsLoadError ? "alert" : undefined}>
            {testsLoadError || (availableTests.length
              ? "Aucun examen ne correspond à votre recherche."
              : "Aucun test médical actif n'est disponible. Ajoutez ou activez des examens dans Tests médicaux.")}
          </div>
        )}
      </div>
    </div>
  );

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
      key: "required",
      title: "Obligatoire",
      render: (row: MedicalTest) => {
        const selected = selectedTests.find((item) => item.test_id === row.id);

        return (
          <input
            type="checkbox"
            checked={selected?.required ?? false}
            disabled={!canEditCampaign}
            onChange={() => toggleRequired(row.id)}
          />
        );
      },
    },
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
          onClick={() => {
            setSelectedTests((current) =>
              current.filter((item) => item.test_id !== row.id),
            );
            setAssignedTests((current) =>
              current.filter((item) => item.id !== row.id),
            );
          }}
        >
          Remove
        </Button>
      ),
    },
  ];

  if (loading) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center">
        <div className="flex flex-col items-center gap-4">
          <Spinner />
          <p className="text-sm font-medium text-ink-500">Chargement de l'éditeur de campagne...</p>
        </div>
      </div>
    );
  }

  if (!canManageCampaigns) {
    return (
      <EmptyState
        title="Campaign editing is restricted"
        description="Only users with campaign management access can create, edit, or remove campaigns."
        actionLabel="Back to Campaigns"
        onAction={() => navigate("/campaigns")}
      />
    );
  }

  if (!campaign) {
    if (isCreateMode) {
      return (
        <div className="space-y-6">
          <SectionHeader
            eyebrow="Field medicine"
            title="Create Campaign"
            description="Create a full campaign record with organization, branch, drilling site, schedule, and operational notes."
          />

          <div className="flex flex-wrap gap-2">
            <Link to="/campaigns">
              <Button variant="ghost" icon={ArrowLeft}>Back</Button>
            </Link>
          </div>

          {notice ? (
            <Card className={notice.type === "success" ? "border-brand-200 bg-brand-50/70" : "border-rose-200 bg-rose-50/70"}>
              <p className="text-sm font-medium text-ink-700">{notice.message}</p>
            </Card>
          ) : null}

          <div className="grid gap-4 grid-cols-4">
            {[
              { label: "Company", value: form.company_id ? availableCompanies.find((item) => item.id === form.company_id)?.name || "Selected" : "Choose company" },
              { label: "Branch", value: form.branch_id ? availableBranches.find((item) => item.id === form.branch_id)?.name || "Selected" : "Choose branch" },
              { label: "Drilling Site", value: form.drilling_site_id ? availableSites.find((item) => item.id === form.drilling_site_id)?.name || "Selected" : "Choose site" },
              { label: "Schedule", value: form.start_date && form.end_date ? `${form.start_date} to ${form.end_date}` : "Set campaign window" },
            ].map((item) => (
              <Card key={item.label} className="bg-gradient-to-br from-white to-brand-50/40 p-4">
                <p className="text-xs font-semibold uppercase tracking-[0.14em] text-ink-400">{item.label}</p>
                <p className="mt-3 text-sm font-semibold text-navy-900">{item.value}</p>
              </Card>
            ))}
          </div>

          <Card className="space-y-5">
            <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-[1.3fr_0.8fr_1.4fr_1.4fr_1fr_1fr_1fr]">
              <Input
                label="Campaign Title"
                value={form.title || form.name || ""}
                onChange={(event) => setForm((current) => ({ ...current, title: event.target.value, name: event.target.value }))}
              />
              <Select
                label="Status"
                options={[
                  { label: "Draft", value: "draft" },
                  { label: "Active", value: "active" },
                  { label: "Terminée", value: "completed" },
                ]}
                value={form.status || "draft"}
                onChange={(event) => setForm((current) => ({ ...current, status: event.target.value as Campaign["status"] }))}
              />
              <Select
                label="Company"
                options={companyOptions}
                error={formErrors.company_id || null}
                value={form.company_id?.toString() || ""}
                onChange={(event) =>
                  setForm((current) => ({
                    ...current,
                    company_id: Number(event.target.value) || undefined,
                    branch_id: undefined,
                    drilling_site_id: undefined,
                  }))
                }
              />
              <Select
                label="Branch"
                options={branchOptions}
                error={formErrors.branch_id || null}
                value={form.branch_id?.toString() || ""}
                disabled={!form.company_id}
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
                disabled={!form.branch_id}
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
                onChange={(event) => setForm((current) => ({ ...current, start_date: event.target.value }))}
              />
              <Input
                label="End Date"
                type="date"
                error={formErrors.end_date || null}
                value={form.end_date?.slice(0, 10) || ""}
                onChange={(event) => setForm((current) => ({ ...current, end_date: event.target.value }))}
              />
            </div>

            <label className="block space-y-2">
              <span className="text-sm font-semibold text-navy-800">Description / Notes</span>
              <textarea
                value={form.description || ""}
                onChange={(event) => setForm((current) => ({ ...current, description: event.target.value }))}
                rows={4}
                className="w-full rounded-xl border border-slate-200/80 bg-white/[0.72] px-4 py-3 text-sm text-ink-800 outline-none backdrop-blur-sm transition-all duration-200 placeholder:text-slate-400 focus:border-brand-400 focus:bg-white focus:ring-4 focus:ring-brand-100/70"
              />
            </label>

            {renderCampaignTestsSelector(false)}

            <div className="flex justify-end gap-2">
              <Button variant="ghost" onClick={() => navigate("/campaigns")}>Annuler</Button>
              <Button onClick={() => void saveCampaign()} loading={savingCampaign}>
                Create Campaign
              </Button>
            </div>
          </Card>
        </div>
      );
    }

    return (
      <EmptyState
        title="Campaign not found"
        description="The campaign could not be loaded."
        actionLabel="Back to Campaigns"
        onAction={() => navigate("/campaigns")}
      />
    );
  }

  return (
    <div className="space-y-6">
      <SectionHeader
        eyebrow="Field medicine"
        title={campaign.title || campaign.name}
        description="Manage campaign details, assignments, lock state, and medical test coverage from a dedicated workspace."
      />

      <div className="flex flex-wrap gap-2">
        <Link to="/campaigns">
          <Button variant="ghost" icon={ArrowLeft}>Back</Button>
        </Link>
        {campaignId ? (
          <Button
            variant="secondary"
            icon={MapPinned}
            onClick={() => navigate(`/app/workspace/${campaignId}/dashboard`)}
          >
            Aller au camping
          </Button>
        ) : null}
        {canLockCampaigns ? (
          <Button
            variant="secondary"
            icon={campaign.status === "completed" ? Unlock : Lock}
            loading={actionLoadingKey === `lock-${campaign.id}`}
            onClick={() => void toggleLock()}
          >
            {campaign.status === "completed" ? "Unlock Campaign" : "Lock Campaign"}
          </Button>
        ) : null}
        <Button variant="danger" icon={Trash2} onClick={startCampaignDelete}>
          Remove Campaign
        </Button>
      </div>

      {notice ? (
        <Card className={notice.type === "success" ? "border-brand-200 bg-brand-50/70" : "border-rose-200 bg-rose-50/70"}>
          <p className="text-sm font-medium text-ink-700">{notice.message}</p>
        </Card>
      ) : null}

      <Card className="space-y-5">
        <div className="flex flex-wrap items-center gap-2">
          <Badge tone={campaign.status}>{campaign.status}</Badge>
          <Badge tone={isLocked ? "completed" : "active"}>{isLocked ? "Locked" : "Unlocked"}</Badge>
          {isLocked ? (
            <span className="text-xs font-medium text-rose-600">
              Locked campaigns cannot be edited until a Super Admin unlocks them.
            </span>
          ) : null}
        </div>

        <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-[1fr_1fr_1fr]">
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
                if (
                  isCreateMode &&
                  nextCompanyId &&
                  !isCompanyContractValidOnDate(selectedCompany, getTodayYmd())
                ) {
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
          <div className="flex flex-col-2 gap-2">
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

        {renderCampaignTestsSelector(!canEditCampaign)}

        <div className="flex justify-end gap-2">
          <Button variant="ghost" onClick={() => navigate("/campaigns")}>Close</Button>
          <Button onClick={() => void saveCampaign()} loading={savingCampaign} disabled={!canEditCampaign}>
            Save Changes
          </Button>
        </div>
      </Card>

      <div className="space-y-5">
        <div className="grid gap-5 grid-cols-2">
          <Card className="p-4">
            <div className="flex items-center gap-2">
              <Stethoscope className="h-4 w-4 text-brand-700" />
              <h4 className="text-base font-semibold text-navy-900">Médecins affectés</h4>
            </div>
            <div className="mt-4 space-y-2">
              {doctorAssignedCandidates.length ? doctorAssignedCandidates.map((doctor) => (
                <div key={doctor.id} className={getAssignmentRowClassName(`doctor-${doctor.id}`, "assigned")}>
                  <div>
                    <p className="text-sm font-medium text-navy-900">{doctor.full_name}</p>
                    <p className="text-xs text-ink-500">{doctor.email}</p>
                    <p className="mt-1 text-[11px] font-semibold text-emerald-700">Affecte a cette campagne</p>
                    {assignmentFeedback?.key === `doctor-${doctor.id}` ? (
                      <p
                        className={`mt-1 text-[11px] font-semibold ${
                          assignmentFeedback.tone === "added" ? "text-teal-700" : "text-amber-700"
                        }`}
                      >
                        {assignmentFeedback.tone === "added" ? "Affectation reussie" : "Retire de la campagne"}
                      </p>
                    ) : null}
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
                {doctorAvailableCandidates.length ? doctorAvailableCandidates.map((doctor) => (
                  <div key={doctor.id} className={getAssignmentRowClassName(`doctor-${doctor.id}`, "available")}>
                    <div>
                      <p className="text-sm font-medium text-navy-900">{doctor.full_name}</p>
                      <p className="text-xs text-ink-500">{doctor.email}</p>
                      <p className="mt-1 text-[11px] font-semibold text-rose-700">Non affecte</p>
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
              {assistantAssignedCandidates.length ? assistantAssignedCandidates.map((assistant) => (
                <div key={assistant.id} className={getAssignmentRowClassName(`assistant-${assistant.id}`, "assigned")}>
                  <div>
                    <p className="text-sm font-medium text-navy-900">{assistant.full_name}</p>
                    <p className="text-xs text-ink-500">{assistant.email}</p>
                    <p className="mt-1 text-[11px] font-semibold text-emerald-700">Affecte a cette campagne</p>
                    {assignmentFeedback?.key === `assistant-${assistant.id}` ? (
                      <p
                        className={`mt-1 text-[11px] font-semibold ${
                          assignmentFeedback.tone === "added" ? "text-teal-700" : "text-amber-700"
                        }`}
                      >
                        {assignmentFeedback.tone === "added" ? "Affectation reussie" : "Retire de la campagne"}
                      </p>
                    ) : null}
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
                {assistantAvailableCandidates.length ? assistantAvailableCandidates.map((assistant) => (
                  <div key={assistant.id} className={getAssignmentRowClassName(`assistant-${assistant.id}`, "available")}>
                    <div>
                      <p className="text-sm font-medium text-navy-900">{assistant.full_name}</p>
                      <p className="text-xs text-ink-500">{assistant.email}</p>
                      <p className="mt-1 text-[11px] font-semibold text-rose-700">Non affecte</p>
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

        <Card className="hidden p-4">
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
        

        <Card className="hidden p-4">
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
