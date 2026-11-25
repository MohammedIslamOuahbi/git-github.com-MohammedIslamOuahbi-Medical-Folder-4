import {
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  ChevronUp,
  Eye,
  Filter,
  MoreHorizontal,
  Pencil,
  Plus,
  RefreshCw,
  Search,
  Trash2,
  UserCheck,
  UserRoundX,
  Users,
  X,
} from "lucide-react";
import {
  Fragment,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { Link, useLocation, useNavigate, useSearchParams } from "react-router-dom";

import { branchesApi } from "@/api/branchesApi";
import { campaignsApi } from "@/api/campaignsApi";
import { companiesApi } from "@/api/companiesApi";
import { drillingSitesApi } from "@/api/drillingSitesApi";
import { fetchAllPages } from "@/api/fetchAllPages";
import { workersApi } from "@/api/workersApi";
import { savedConflictMessage } from "@/api/localMutation";
import { Badge } from "@/components/common/Badge";
import { Button } from "@/components/common/Button";
import { Card } from "@/components/common/Card";
import { EmptyState } from "@/components/common/EmptyState";
import { Input } from "@/components/common/Input";
import { Modal } from "@/components/common/Modal";
import { SearchInput } from "@/components/common/SearchInput";
import { Select } from "@/components/common/Select";
import type { Option } from "@/types/common";
import type { Branch, Campaign, Company, DrillingSite, Worker } from "@/types/entities";
import { cn } from "@/utils/cn";

type WorkerSortField = "name" | "employee_number" | "medical_status" | "created_at";
type SortOrder = "asc" | "desc";
type FilterState = {
  companyId: string;
  branchId: string;
  drillingSiteId: string;
  department: string;
  medicalStatus: string;
  presence: string;
  activity: string;
};
type WorkerFormState = {
  first_name: string;
  last_name: string;
  employee_code: string;
  national_id: string;
  company_id: string;
  branch_id: string;
  drilling_site_id: string;
  position: string;
  department: string;
  phone: string;
  medical_status: string;
  status: "active" | "inactive";
  etat_actual: string;
};
type NoticeState = {
  tone: "success" | "error";
  message: string;
} | null;

const PAGE_SIZE_OPTIONS = [10, 25, 50, 100];
const SORT_OPTIONS: Array<{ value: WorkerSortField; label: string }> = [
  { value: "created_at", label: "Date de creation" },
  { value: "name", label: "Nom du travailleur" },
  { value: "employee_number", label: "Matricule" },
  { value: "medical_status", label: "Statut medical" },
];
const PRESENCE_OPTIONS: Option[] = [
  { value: "", label: "Tous les etats" },
  { value: "present", label: "Present" },
  { value: "absence", label: "Absent" },
  { value: "sick_leave", label: "Conge maladie" },
  { value: "recovery", label: "Recuperation" },
  { value: "mission", label: "Mission" },
  { value: "work_accident", label: "Accident de travail" },
  { value: "annual_leave", label: "Conge annuel" },
  { value: "unpaid_leave", label: "Conge sans solde" },
  { value: "maternity_leave", label: "Conge maternite" },
  { value: "paternity_leave", label: "Conge paternite" },
  { value: "retired", label: "Retraite" },
  { value: "suspended", label: "Suspendu" },
  { value: "terminated", label: "Fin de contrat" },
];
const ACTIVITY_OPTIONS: Option[] = [
  { value: "", label: "Tous les statuts" },
  { value: "active", label: "Actif" },
  { value: "inactive", label: "Inactif" },
];
const STATUS_OPTIONS: Option[] = [
  { value: "active", label: "Actif" },
  { value: "inactive", label: "Inactif" },
];

const DEFAULT_FORM_STATE: WorkerFormState = {
  first_name: "",
  last_name: "",
  employee_code: "",
  national_id: "",
  company_id: "",
  branch_id: "",
  drilling_site_id: "",
  position: "",
  department: "",
  phone: "",
  medical_status: "",
  status: "active",
  etat_actual: "present",
};

const normalizeQueryNumber = (value: string | null, fallback: number) => {
  const parsed = Number(value || fallback);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : fallback;
};

const humanizeToken = (value: string | null | undefined, fallback = "Non renseigne") => {
  if (!value) {
    return fallback;
  }

  return value
    .replace(/[_-]+/g, " ")
    .replace(/\s+/g, " ")
    .trim()
    .replace(/\b\w/g, (char) => char.toUpperCase());
};

const normalizeText = (value: string | null | undefined) => (value || "").trim();

const formatMedicalStatusLabel = (value: string | null | undefined) => {
  if (!value) {
    return "Non renseigne";
  }

  const normalized = value.trim().toLowerCase();
  const mapping: Record<string, string> = {
    fit: "Apte",
    apte: "Apte",
    "apte avec reserve": "Apte avec reserve",
    reserve: "Apte avec reserve",
    unfit: "Inapte",
    inapte: "Inapte",
    pending: "A examiner",
    "a examiner": "A examiner",
    "a reevaluer": "A reevaluer",
  };

  return mapping[normalized] || humanizeToken(value);
};

const getMedicalStatusTone = (value: string | null | undefined) => {
  const normalized = (value || "").trim().toLowerCase();

  if (!normalized) return "inactive";
  if (normalized.includes("inapt") || normalized.includes("unfit")) return "failed";
  if (normalized.includes("reserve") || normalized.includes("restr")) return "pending";
  if (normalized.includes("exam") || normalized.includes("pending") || normalized.includes("attente")) return "completed";
  if (normalized.includes("apte") || normalized.includes("fit")) return "active";
  return "inactive";
};

const formatPresenceLabel = (value: string | null | undefined) => {
  const normalized = (value || "").trim().toLowerCase();
  const mapping: Record<string, string> = {
    present: "Present",
    absence: "Absent",
    absent: "Absent",
    sick_leave: "Conge maladie",
    recovery: "Recuperation",
    mission: "Mission",
    work_accident: "Accident de travail",
    annual_leave: "Conge annuel",
    unpaid_leave: "Conge sans solde",
    maternity_leave: "Conge maternite",
    paternity_leave: "Conge paternite",
    retired: "Retraite",
    suspended: "Suspendu",
    terminated: "Fin de contrat",
  };

  return mapping[normalized] || humanizeToken(value, "Etat inconnu");
};

const getPresenceTone = (value: string | null | undefined) => {
  const normalized = (value || "").trim().toLowerCase();
  if (normalized === "present") return "active";
  if (normalized === "absence" || normalized === "absent" || normalized === "terminated") return "failed";
  if (normalized.includes("leave") || normalized === "mission" || normalized === "recovery") return "pending";
  return "inactive";
};

const resolveWorkerIsActive = (worker: Worker) =>
  typeof worker.is_active === "boolean" ? worker.is_active : worker.status !== "inactive";

const buildWorkerFormState = (worker?: Worker | null): WorkerFormState => ({
  first_name: worker?.first_name || "",
  last_name: worker?.last_name || "",
  employee_code: worker?.employee_code || worker?.employee_number || "",
  national_id: worker?.national_id || "",
  company_id: worker?.company_id ? String(worker.company_id) : "",
  branch_id: worker?.branch_id ? String(worker.branch_id) : "",
  drilling_site_id: worker?.drilling_site_id ? String(worker.drilling_site_id) : "",
  position: worker?.position || worker?.job_title || "",
  department: worker?.department || "",
  phone: worker?.phone || "",
  medical_status: worker?.medical_status || "",
  status: resolveWorkerIsActive(worker || ({} as Worker)) ? "active" : "inactive",
  etat_actual: worker?.etat_actual || "present",
});

const toWorkerPayload = (form: WorkerFormState): Partial<Worker> => ({
  first_name: normalizeText(form.first_name),
  last_name: normalizeText(form.last_name),
  employee_code: normalizeText(form.employee_code),
  national_id: normalizeText(form.national_id) || null,
  company_id: Number(form.company_id),
  branch_id: Number(form.branch_id),
  drilling_site_id: form.drilling_site_id ? Number(form.drilling_site_id) : null,
  position: normalizeText(form.position),
  department: normalizeText(form.department) || null,
  phone: normalizeText(form.phone) || null,
  medical_status: normalizeText(form.medical_status) || null,
  status: form.status,
  etat_actual: form.etat_actual as Worker["etat_actual"],
});

const WorkerAvatar = ({ worker }: { worker: Worker }) => {
  const initials = `${worker.last_name?.[0] || ""}${worker.first_name?.[0] || ""}`.trim().toUpperCase() || "TR";

  return (
    <div className="relative flex h-11 w-11 shrink-0 items-center justify-center overflow-hidden rounded-xl border border-slate-200 bg-slate-100 text-sm font-black text-slate-700">
      <span>{initials}</span>
      {worker.photo ? (
        <img
          src={worker.photo}
          alt={`${worker.last_name || ""} ${worker.first_name || ""}`.trim()}
          className="absolute inset-0 h-full w-full object-cover"
          onError={(event) => {
            event.currentTarget.style.display = "none";
          }}
        />
      ) : null}
    </div>
  );
};

const MedicalStatusBadge = ({ value }: { value: string | null | undefined }) => (
  <Badge tone={getMedicalStatusTone(value)}>{formatMedicalStatusLabel(value)}</Badge>
);

const PresenceStatusBadge = ({ value }: { value: string | null | undefined }) => (
  <Badge tone={getPresenceTone(value)}>{formatPresenceLabel(value)}</Badge>
);

const WorkersTableSkeleton = () => (
  <div className="overflow-hidden rounded-[0.75rem] border border-slate-200 bg-white">
    <div className="hidden md:block">
      <div className="grid grid-cols-[2.1fr_1fr_1.45fr_1.25fr_1.1fr_1fr_0.85fr_72px] gap-3 border-b border-slate-200 bg-slate-50 px-5 py-4">
        {Array.from({ length: 8 }).map((_, index) => (
          <div key={`workers-header-skeleton-${index}`} className="h-3 animate-pulse rounded bg-slate-200" />
        ))}
      </div>
      <div className="divide-y divide-slate-100">
        {Array.from({ length: 8 }).map((_, rowIndex) => (
          <div
            key={`workers-row-skeleton-${rowIndex}`}
            className="grid grid-cols-[2.1fr_1fr_1.45fr_1.25fr_1.1fr_1fr_0.85fr_72px] gap-3 px-5 py-4"
          >
            <div className="flex items-center gap-3">
              <div className="h-11 w-11 animate-pulse rounded-xl bg-slate-200" />
              <div className="flex-1 space-y-2">
                <div className="h-3 w-32 animate-pulse rounded bg-slate-200" />
                <div className="h-3 w-20 animate-pulse rounded bg-slate-100" />
              </div>
            </div>
            {Array.from({ length: 7 }).map((_, colIndex) => (
              <div key={`workers-cell-skeleton-${rowIndex}-${colIndex}`} className="space-y-2">
                <div className="h-3 animate-pulse rounded bg-slate-200" />
                <div className="h-3 w-3/4 animate-pulse rounded bg-slate-100" />
              </div>
            ))}
          </div>
        ))}
      </div>
    </div>

    <div className="space-y-3 p-4 md:hidden">
      {Array.from({ length: 5 }).map((_, index) => (
        <div key={`worker-card-skeleton-${index}`} className="rounded-xl border border-slate-200 p-4">
          <div className="flex items-start gap-3">
            <div className="h-12 w-12 animate-pulse rounded-xl bg-slate-200" />
            <div className="flex-1 space-y-2">
              <div className="h-3 w-32 animate-pulse rounded bg-slate-200" />
              <div className="h-3 w-20 animate-pulse rounded bg-slate-100" />
              <div className="h-3 w-full animate-pulse rounded bg-slate-100" />
            </div>
          </div>
        </div>
      ))}
    </div>
  </div>
);

const WorkerActionsMenu = ({
  worker,
  onView,
  onEdit,
  onAssignCampaign,
  onToggleStatus,
  onDelete,
}: {
  worker: Worker;
  onView: (worker: Worker) => void;
  onEdit: (worker: Worker) => void;
  onAssignCampaign: (worker: Worker) => void;
  onToggleStatus: (worker: Worker) => void;
  onDelete: (worker: Worker) => void;
}) => {
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!open) {
      return;
    }

    const handlePointerDown = (event: MouseEvent) => {
      const target = event.target as Node;
      if (containerRef.current && !containerRef.current.contains(target)) {
        setOpen(false);
      }
    };

    const handleEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setOpen(false);
      }
    };

    document.addEventListener("mousedown", handlePointerDown);
    document.addEventListener("keydown", handleEscape);
    return () => {
      document.removeEventListener("mousedown", handlePointerDown);
      document.removeEventListener("keydown", handleEscape);
    };
  }, [open]);

  const isActive = resolveWorkerIsActive(worker);
  const items = [
    {
      label: "Voir le dossier",
      icon: Eye,
      onSelect: () => onView(worker),
      destructive: false,
    },
    {
      label: "Modifier",
      icon: Pencil,
      onSelect: () => onEdit(worker),
      destructive: false,
    },
    {
      label: "Ajouter a une campagne",
      icon: Plus,
      onSelect: () => onAssignCampaign(worker),
      destructive: false,
    },
    {
      label: isActive ? "Desactiver" : "Activer",
      icon: isActive ? UserRoundX : UserCheck,
      onSelect: () => onToggleStatus(worker),
      destructive: false,
    },
    {
      label: "Supprimer",
      icon: Trash2,
      onSelect: () => onDelete(worker),
      destructive: true,
    },
  ];

  return (
    <div ref={containerRef} className="relative flex justify-end">
      <button
        type="button"
        aria-label={`Actions pour ${worker.last_name || ""} ${worker.first_name || ""}`.trim()}
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={() => setOpen((current) => !current)}
        className="inline-flex h-9 w-9 items-center justify-center rounded-lg border border-slate-200 bg-white text-slate-500 transition hover:border-slate-300 hover:bg-slate-50 hover:text-slate-950"
      >
        <MoreHorizontal className="h-4 w-4" />
      </button>

      {open ? (
        <div
          role="menu"
          className="absolute right-0 top-11 z-20 min-w-[220px] overflow-hidden rounded-xl border border-slate-200 bg-white p-1 shadow-lg shadow-slate-950/10"
        >
          {items.map((item, index) => (
            <Fragment key={item.label}>
              {index === items.length - 1 ? <div className="my-1 border-t border-slate-100" /> : null}
              <button
                type="button"
                role="menuitem"
                onClick={() => {
                  setOpen(false);
                  item.onSelect();
                }}
                className={cn(
                  "flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-sm font-medium transition",
                  item.destructive
                    ? "text-rose-700 hover:bg-rose-50"
                    : "text-slate-700 hover:bg-slate-50 hover:text-slate-950",
                )}
              >
                <item.icon className="h-4 w-4 shrink-0" />
                <span>{item.label}</span>
              </button>
            </Fragment>
          ))}
        </div>
      ) : null}
    </div>
  );
};

const WorkersMobileCard = ({
  worker,
  companyLabel,
  branchLabel,
  siteLabel,
  onView,
  onEdit,
  onAssignCampaign,
  onToggleStatus,
  onDelete,
}: {
  worker: Worker;
  companyLabel: string;
  branchLabel: string;
  siteLabel: string;
  onView: (worker: Worker) => void;
  onEdit: (worker: Worker) => void;
  onAssignCampaign: (worker: Worker) => void;
  onToggleStatus: (worker: Worker) => void;
  onDelete: (worker: Worker) => void;
}) => {
  const fullName = `${worker.last_name || ""} ${worker.first_name || ""}`.trim() || worker.full_name || "Travailleur";
  const position = normalizeText(worker.position || worker.job_title) || "Non renseigne";
  const department = normalizeText(worker.department) || "Non renseigne";
  const primaryAssignment = branchLabel !== "Non renseigne" ? branchLabel : companyLabel;
  const statusLabel = resolveWorkerIsActive(worker) ? "Actif" : "Inactif";

  return (
    <Card className="rounded-xl p-4 md:hidden">
      <div className="flex items-start gap-3">
        <WorkerAvatar worker={worker} />
        <div className="min-w-0 flex-1">
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <button
                type="button"
                onClick={() => onView(worker)}
                className="truncate text-left text-base font-bold text-slate-950 transition hover:text-[#0085A3]"
              >
                {fullName}
              </button>
              <p className="mt-1 font-mono text-xs font-semibold text-slate-500">
                {worker.employee_code || worker.employee_number || "Non renseigne"}
              </p>
            </div>
            <WorkerActionsMenu
              worker={worker}
              onView={onView}
              onEdit={onEdit}
              onAssignCampaign={onAssignCampaign}
              onToggleStatus={onToggleStatus}
              onDelete={onDelete}
            />
          </div>

          <div className="mt-3 grid gap-3">
            <div>
              <p className="text-[11px] font-black uppercase tracking-[0.14em] text-slate-400">Affectation</p>
              <p className="mt-1 text-sm font-semibold text-slate-800">{primaryAssignment}</p>
              <p className="text-xs text-slate-500">{siteLabel}</p>
            </div>

            <div>
              <p className="text-[11px] font-black uppercase tracking-[0.14em] text-slate-400">Fonction</p>
              <p className="mt-1 text-sm font-semibold text-slate-800">{position}</p>
              <p className="text-xs text-slate-500">{department}</p>
            </div>

            <div className="flex flex-wrap gap-2">
              <MedicalStatusBadge value={worker.medical_status || worker.medical_file_status} />
              <PresenceStatusBadge value={worker.etat_actual} />
              <Badge tone={resolveWorkerIsActive(worker) ? "active" : "inactive"}>{statusLabel}</Badge>
            </div>
          </div>
        </div>
      </div>
    </Card>
  );
};

export const WorkersPage = () => {
  const location = useLocation();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const search = searchParams.get("q") || "";
  const page = normalizeQueryNumber(searchParams.get("page"), 1);
  const pageSize = PAGE_SIZE_OPTIONS.includes(normalizeQueryNumber(searchParams.get("pageSize"), 25))
    ? normalizeQueryNumber(searchParams.get("pageSize"), 25)
    : 25;
  const sortBy = (searchParams.get("sortBy") as WorkerSortField | null) || "created_at";
  const sortOrder = (searchParams.get("sortOrder") as SortOrder | null) || "desc";
  const filters: FilterState = {
    companyId: searchParams.get("company") || "",
    branchId: searchParams.get("branch") || "",
    drillingSiteId: searchParams.get("site") || "",
    department: searchParams.get("department") || "",
    medicalStatus: searchParams.get("medicalStatus") || "",
    presence: searchParams.get("presence") || "",
    activity: searchParams.get("activity") || "",
  };

  const [rows, setRows] = useState<Worker[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<NoticeState>(null);
  const [searchInput, setSearchInput] = useState(search);
  const [filtersExpanded, setFiltersExpanded] = useState(false);
  const [supportLoading, setSupportLoading] = useState(true);
  const [supportError, setSupportError] = useState<string | null>(null);
  const [companies, setCompanies] = useState<Company[]>([]);
  const [branches, setBranches] = useState<Branch[]>([]);
  const [drillingSites, setDrillingSites] = useState<DrillingSite[]>([]);
  const [retryToken, setRetryToken] = useState(0);

  const [formOpen, setFormOpen] = useState(false);
  const [editingWorkerId, setEditingWorkerId] = useState<number | null>(null);
  const [formState, setFormState] = useState<WorkerFormState>(DEFAULT_FORM_STATE);
  const [formError, setFormError] = useState<string | null>(null);
  const [saveLoading, setSaveLoading] = useState(false);

  const [deleteTarget, setDeleteTarget] = useState<Worker | null>(null);
  const [deletePassword, setDeletePassword] = useState("");
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [deleteLoading, setDeleteLoading] = useState(false);

  const [statusTarget, setStatusTarget] = useState<Worker | null>(null);
  const [statusLoading, setStatusLoading] = useState(false);

  const [campaignTarget, setCampaignTarget] = useState<Worker | null>(null);
  const [campaignOptions, setCampaignOptions] = useState<Campaign[]>([]);
  const [campaignLoading, setCampaignLoading] = useState(false);
  const [campaignSubmitting, setCampaignSubmitting] = useState(false);
  const [campaignError, setCampaignError] = useState<string | null>(null);
  const [selectedCampaignId, setSelectedCampaignId] = useState("");
  const returnTo = `${location.pathname}${location.search}`;

  const updateParams = useCallback(
    (updates: Record<string, string | null | undefined>, resetPage = false) => {
      setSearchParams((current) => {
        const next = new URLSearchParams(current);
        Object.entries(updates).forEach(([key, value]) => {
          if (!value) {
            next.delete(key);
          } else {
            next.set(key, value);
          }
        });
        if (resetPage) {
          next.set("page", "1");
        }
        return next;
      });
    },
    [setSearchParams],
  );

  useEffect(() => {
    setSearchInput(search);
  }, [search]);

  useEffect(() => {
    const timeoutId = window.setTimeout(() => {
      if (searchInput !== search) {
        updateParams({ q: searchInput || null }, true);
      }
    }, 350);

    return () => window.clearTimeout(timeoutId);
  }, [search, searchInput, updateParams]);

  useEffect(() => {
    let active = true;

    const loadSupportData = async () => {
      setSupportLoading(true);
      setSupportError(null);
      try {
        const [companiesResponse, branchesResponse, sitesResponse] = await Promise.all([
          fetchAllPages(companiesApi),
          fetchAllPages(branchesApi),
          fetchAllPages(drillingSitesApi),
        ]);

        if (!active) {
          return;
        }

        setCompanies(companiesResponse.items);
        setBranches(branchesResponse.items);
        setDrillingSites(sitesResponse.items);
      } catch {
        if (!active) {
          return;
        }
        setCompanies([]);
        setBranches([]);
        setDrillingSites([]);
        setSupportError("Impossible de charger les entreprises, filiales et sites. Vérifiez la connexion puis réessayez.");
      } finally {
        if (active) {
          setSupportLoading(false);
        }
      }
    };

    void loadSupportData();

    return () => {
      active = false;
    };
  }, [retryToken]);

  useEffect(() => {
    let active = true;

    const loadWorkers = async () => {
      setLoading(true);
      setError(null);

      try {
        const apiSortField: Record<WorkerSortField, string> = {
          name: "last_name",
          employee_number: "employee_number",
          medical_status: "medical_status",
          created_at: "created_at",
        };

        const response = await workersApi.list({
          page,
          limit: pageSize,
          search: search || undefined,
          sort_by: apiSortField[sortBy] || "created_at",
          sort_order: sortOrder,
        });

        if (!active) {
          return;
        }

        setRows(response.items);
        setTotal(response.total);
      } catch {
        if (!active) {
          return;
        }
        setRows([]);
        setTotal(0);
        setError("Impossible de charger les travailleurs pour le moment.");
      } finally {
        if (active) {
          setLoading(false);
        }
      }
    };

    void loadWorkers();

    return () => {
      active = false;
    };
  }, [page, pageSize, retryToken, search, sortBy, sortOrder]);

  useEffect(() => {
    if (!campaignTarget) {
      return;
    }

    let active = true;
    setCampaignLoading(true);
    setCampaignError(null);

    const loadCampaigns = async () => {
      try {
        const response = await campaignsApi.list({
          page: 1,
          limit: 100,
          sort_by: "start_date",
          sort_order: "desc",
        });

        if (!active) {
          return;
        }

        setCampaignOptions(response.items);
      } catch {
        if (!active) {
          return;
        }
        setCampaignOptions([]);
        setCampaignError("Impossible de charger les campagnes disponibles.");
      } finally {
        if (active) {
          setCampaignLoading(false);
        }
      }
    };

    void loadCampaigns();

    return () => {
      active = false;
    };
  }, [campaignTarget]);

  const companyMap = useMemo(
    () => new Map(companies.map((company) => [company.id, company])),
    [companies],
  );
  const branchMap = useMemo(
    () => new Map(branches.map((branch) => [branch.id, branch])),
    [branches],
  );
  const siteMap = useMemo(
    () => new Map(drillingSites.map((site) => [site.id, site])),
    [drillingSites],
  );

  const filteredRows = useMemo(() => {
    return rows.filter((worker) => {
      if (filters.companyId && String(worker.company_id) !== filters.companyId) return false;
      if (filters.branchId && String(worker.branch_id) !== filters.branchId) return false;
      if (filters.drillingSiteId && String(worker.drilling_site_id || "") !== filters.drillingSiteId) return false;
      if (filters.department && normalizeText(worker.department) !== filters.department) return false;
      if (filters.medicalStatus && normalizeText(worker.medical_status || worker.medical_file_status) !== filters.medicalStatus) return false;
      if (filters.presence && worker.etat_actual !== filters.presence) return false;
      if (filters.activity === "active" && !resolveWorkerIsActive(worker)) return false;
      if (filters.activity === "inactive" && resolveWorkerIsActive(worker)) return false;
      return true;
    });
  }, [filters.activity, filters.branchId, filters.companyId, filters.department, filters.drillingSiteId, filters.medicalStatus, filters.presence, rows]);

  const companyOptions = useMemo<Option[]>(
    () => [
      { value: "", label: "Toutes les entreprises" },
      ...companies.map((company) => ({ value: String(company.id), label: company.name })),
    ],
    [companies],
  );

  const branchOptions = useMemo<Option[]>(() => {
    const scopedBranches = filters.companyId
      ? branches.filter((branch) => String(branch.company_id) === filters.companyId)
      : branches;

    return [
      { value: "", label: "Toutes les branches" },
      ...scopedBranches.map((branch) => ({ value: String(branch.id), label: branch.name })),
    ];
  }, [branches, filters.companyId]);

  const siteOptions = useMemo<Option[]>(() => {
    const scopedSites = filters.branchId
      ? drillingSites.filter((site) => String(site.branch_id) === filters.branchId)
      : filters.companyId
        ? drillingSites.filter((site) => String(site.company_id) === filters.companyId)
        : drillingSites;

    return [
      { value: "", label: "Tous les sites" },
      ...scopedSites.map((site) => ({ value: String(site.id), label: site.name })),
    ];
  }, [drillingSites, filters.branchId, filters.companyId]);

  const departmentOptions = useMemo<Option[]>(() => {
    const uniqueDepartments = Array.from(
      new Set(rows.map((worker) => normalizeText(worker.department)).filter(Boolean)),
    ).sort((left, right) => left.localeCompare(right, "fr"));

    return [
      { value: "", label: "Tous les departements" },
      ...uniqueDepartments.map((department) => ({ value: department, label: department })),
    ];
  }, [rows]);

  const medicalStatusOptions = useMemo<Option[]>(() => {
    const uniqueStatuses = Array.from(
      new Set(rows.map((worker) => normalizeText(worker.medical_status || worker.medical_file_status)).filter(Boolean)),
    ).sort((left, right) => left.localeCompare(right, "fr"));

    return [
      { value: "", label: "Tous les statuts medicaux" },
      ...uniqueStatuses.map((status) => ({ value: status, label: formatMedicalStatusLabel(status) })),
    ];
  }, [rows]);

  const activeFilterChips = useMemo(() => {
    const chips: Array<{ key: string; label: string; value: string }> = [];

    if (search) {
      chips.push({ key: "q", label: "Recherche", value: search });
    }
    if (filters.companyId) {
      chips.push({
        key: "company",
        label: "Entreprise",
        value: companyMap.get(Number(filters.companyId))?.name || `Entreprise #${filters.companyId}`,
      });
    }
    if (filters.branchId) {
      chips.push({
        key: "branch",
        label: "Branch",
        value: branchMap.get(Number(filters.branchId))?.name || `Branch #${filters.branchId}`,
      });
    }
    if (filters.drillingSiteId) {
      chips.push({
        key: "site",
        label: "Site",
        value: siteMap.get(Number(filters.drillingSiteId))?.name || `Site #${filters.drillingSiteId}`,
      });
    }
    if (filters.department) {
      chips.push({ key: "department", label: "Departement", value: filters.department });
    }
    if (filters.medicalStatus) {
      chips.push({
        key: "medicalStatus",
        label: "Statut medical",
        value: formatMedicalStatusLabel(filters.medicalStatus),
      });
    }
    if (filters.presence) {
      chips.push({ key: "presence", label: "Etat actuel", value: formatPresenceLabel(filters.presence) });
    }
    if (filters.activity) {
      chips.push({
        key: "activity",
        label: "Statut",
        value: filters.activity === "active" ? "Actif" : "Inactif",
      });
    }

    return chips;
  }, [branchMap, companyMap, filters.activity, filters.branchId, filters.companyId, filters.department, filters.drillingSiteId, filters.medicalStatus, filters.presence, search, siteMap]);

  const activeAdvancedFilterCount = useMemo(
    () => activeFilterChips.filter((chip) => chip.key !== "q").length,
    [activeFilterChips],
  );

  const visibleActiveCount = useMemo(
    () => filteredRows.filter((worker) => resolveWorkerIsActive(worker)).length,
    [filteredRows],
  );
  const visiblePresentCount = useMemo(
    () => filteredRows.filter((worker) => worker.etat_actual === "present").length,
    [filteredRows],
  );

  const rangeStart = total === 0 ? 0 : (page - 1) * pageSize + 1;
  const rangeEnd = total === 0 ? 0 : rangeStart + rows.length - 1;
  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  const hasRows = filteredRows.length > 0;

  const handleResetAll = useCallback(() => {
    setSearchInput("");
    setSearchParams(new URLSearchParams());
  }, [setSearchParams]);

  const handleOpenCreate = useCallback(() => {
    setEditingWorkerId(null);
    setFormState(DEFAULT_FORM_STATE);
    setFormError(null);
    setFormOpen(true);
  }, []);

  const handleOpenEdit = useCallback((worker: Worker) => {
    setEditingWorkerId(worker.id);
    setFormState(buildWorkerFormState(worker));
    setFormError(null);
    setFormOpen(true);
  }, []);

  const handleSaveWorker = useCallback(async () => {
    if (!formState.first_name.trim() || !formState.last_name.trim() || !formState.employee_code.trim()) {
      setFormError("Le nom, le prenom et le matricule sont obligatoires.");
      return;
    }

    if (!formState.company_id || !formState.branch_id) {
      setFormError("Les identifiants d'entreprise et de branch sont obligatoires.");
      return;
    }

    setSaveLoading(true);
    setFormError(null);

    try {
      const payload = toWorkerPayload(formState);
      if (editingWorkerId) {
        const updated = await workersApi.update(editingWorkerId, { ...payload, sync_version: rows.find((item) => item.id === editingWorkerId)?.sync_version });
        setRows((current) => current.map((item) => (item.id === editingWorkerId ? updated : item)));
        setNotice({ tone: "success", message: "Le travailleur a ete mis a jour." });
      } else {
        const created = await workersApi.create(payload);
        setRows((current) => [created, ...current].slice(0, pageSize));
        setTotal((current) => current + 1);
        setNotice({ tone: "success", message: "Le travailleur a ete cree avec succes." });
      }
      setFormOpen(false);
      setEditingWorkerId(null);
      setFormState(DEFAULT_FORM_STATE);
    } catch (error) {
      setFormError(savedConflictMessage(error) || "Impossible d'enregistrer ce travailleur pour le moment.");
    } finally {
      setSaveLoading(false);
    }
  }, [editingWorkerId, formState, pageSize]);

  const handleDeleteWorker = useCallback(async () => {
    if (!deleteTarget) {
      return;
    }
    if (!deletePassword.trim()) {
      setDeleteError("Saisissez votre mot de passe pour confirmer la suppression.");
      return;
    }

    setDeleteLoading(true);
    setDeleteError(null);

    try {
      await workersApi.remove(deleteTarget.id, { password: deletePassword, sync_version: deleteTarget.sync_version });
      setRows((current) => current.filter((item) => item.id !== deleteTarget.id));
      setTotal((current) => Math.max(0, current - 1));
      setNotice({ tone: "success", message: "Le travailleur a ete supprime." });
      setDeleteTarget(null);
      setDeletePassword("");
    } catch (error) {
      setDeleteError(savedConflictMessage(error) || "Impossible de supprimer ce travailleur. Verifiez votre mot de passe.");
    } finally {
      setDeleteLoading(false);
    }
  }, [deletePassword, deleteTarget]);

  const handleToggleWorkerStatus = useCallback(async () => {
    if (!statusTarget) {
      return;
    }

    const nextStatus = resolveWorkerIsActive(statusTarget) ? "inactive" : "active";
    setStatusLoading(true);

    try {
      const updated = await workersApi.update(statusTarget.id, { ...statusTarget, status: nextStatus });
      setRows((current) => current.map((item) => (item.id === statusTarget.id ? updated : item)));
      setNotice({
        tone: "success",
        message: nextStatus === "active" ? "Le travailleur a ete reactive." : "Le travailleur a ete desactive.",
      });
      setStatusTarget(null);
    } catch (error) {
      setNotice({
        tone: "error",
        message: savedConflictMessage(error) || "Impossible de modifier le statut du travailleur pour le moment.",
      });
    } finally {
      setStatusLoading(false);
    }
  }, [statusTarget]);

  const handleAssignToCampaign = useCallback(async () => {
    if (!campaignTarget || !selectedCampaignId) {
      setCampaignError("Selectionnez une campagne avant de valider.");
      return;
    }

    setCampaignSubmitting(true);
    setCampaignError(null);

    try {
      await campaignsApi.addWorkers(Number(selectedCampaignId), [campaignTarget.id]);
      setNotice({ tone: "success", message: "Le travailleur a ete ajoute a la campagne selectionnee." });
      setCampaignTarget(null);
      setSelectedCampaignId("");
    } catch {
      setCampaignError("Impossible d'ajouter ce travailleur a la campagne selectionnee.");
    } finally {
      setCampaignSubmitting(false);
    }
  }, [campaignTarget, selectedCampaignId]);

  const handleRemoveFilterChip = useCallback(
    (key: string) => {
      const paramMap: Record<string, string> = {
        q: "q",
        company: "company",
        branch: "branch",
        site: "site",
        department: "department",
        medicalStatus: "medicalStatus",
        presence: "presence",
        activity: "activity",
      };

      if (key === "q") {
        setSearchInput("");
      }
      updateParams({ [paramMap[key] || key]: null }, true);
    },
    [updateParams],
  );

  const companyLabelFor = useCallback(
    (worker: Worker) => companyMap.get(worker.company_id)?.name || `Entreprise #${worker.company_id}`,
    [companyMap],
  );
  const branchLabelFor = useCallback(
    (worker: Worker) => branchMap.get(worker.branch_id)?.name || "Non renseigne",
    [branchMap],
  );
  const siteLabelFor = useCallback(
    (worker: Worker) =>
      worker.drilling_site_id
        ? siteMap.get(worker.drilling_site_id)?.name || `Site #${worker.drilling_site_id}`
        : "Non affecte",
    [siteMap],
  );

  const formBranchOptions = useMemo<Option[]>(() => {
    const scopedBranches = formState.company_id
      ? branches.filter((branch) => String(branch.company_id) === formState.company_id)
      : branches;

    return [
      { value: "", label: supportLoading ? "Chargement..." : scopedBranches.length ? "Selectionner une filiale" : "Aucune filiale disponible" },
      ...scopedBranches.map((branch) => ({ value: String(branch.id), label: branch.name })),
    ];
  }, [branches, formState.company_id, supportLoading]);

  const formSiteOptions = useMemo<Option[]>(() => {
    const scopedSites = formState.branch_id
      ? drillingSites.filter((site) => String(site.branch_id) === formState.branch_id)
      : formState.company_id
        ? drillingSites.filter((site) => String(site.company_id) === formState.company_id)
        : drillingSites;

    return [
      { value: "", label: supportLoading ? "Chargement..." : scopedSites.length ? "Aucun site" : "Aucun site disponible" },
      ...scopedSites.map((site) => ({ value: String(site.id), label: site.name })),
    ];
  }, [drillingSites, formState.branch_id, formState.company_id, supportLoading]);

  const campaignsSelectOptions = useMemo<Option[]>(
    () => [
      { value: "", label: "Selectionner une campagne" },
      ...campaignOptions.map((campaign) => ({
        value: String(campaign.id),
        label: campaign.title || campaign.name,
      })),
    ],
    [campaignOptions],
  );

  const tableColumns = useMemo(
    () => [
      {
        key: "name",
        title: "Travailleur",
      },
      {
        key: "employee_number",
        title: "Matricule",
      },
      {
        key: "assignment",
        title: "Affectation",
      },
      {
        key: "function",
        title: "Fonction",
      },
      {
        key: "medical_status",
        title: "Statut medical",
      },
      {
        key: "presence",
        title: "Etat actuel",
      },
      {
        key: "status",
        title: "Statut",
      },
      {
        key: "actions",
        title: "Actions",
      },
    ],
    [],
  );

  const handleSort = useCallback(
    (field: WorkerSortField) => {
      const nextOrder: SortOrder = sortBy === field && sortOrder === "asc" ? "desc" : "asc";
      updateParams(
        {
          sortBy: field,
          sortOrder: nextOrder,
        },
        true,
      );
    },
    [sortBy, sortOrder, updateParams],
  );

  const renderSortIcon = useCallback(
    (field: WorkerSortField) => {
      if (sortBy !== field) {
        return <ChevronDown className="h-3.5 w-3.5 text-slate-400" />;
      }
      return sortOrder === "asc" ? (
        <ChevronUp className="h-3.5 w-3.5 text-[#0085A3]" />
      ) : (
        <ChevronDown className="h-3.5 w-3.5 text-[#0085A3]" />
      );
    },
    [sortBy, sortOrder],
  );

  const visibleSortValue = SORT_OPTIONS.find((option) => option.value === sortBy)?.label || "Date de creation";

  return (
    <div className="space-y-5">
      <div className="flex flex-col gap-4 rounded-[0.75rem] border border-slate-200 bg-white px-5 py-5 shadow-sm">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div className="min-w-0">
            <div className="inline-flex items-center gap-2 rounded-full border border-[#0085A3]/15 bg-[#0085A3]/10 px-3 py-1 text-[11px] font-black uppercase tracking-[0.18em] text-[#0085A3]">
              <Users className="h-3.5 w-3.5" />
              <span>Travailleurs</span>
            </div>
            <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-2">
              <h1 className="text-2xl font-black tracking-tight text-slate-950">Travailleurs</h1>
              <span className="inline-flex items-center rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-sm font-semibold text-slate-700">
                {total} au total
              </span>
            </div>
            <p className="mt-2 max-w-3xl text-sm text-slate-600">
              Gerez les travailleurs et leurs dossiers medicaux.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <Button icon={Plus} onClick={handleOpenCreate}>
              Nouveau travailleur
            </Button>
          </div>
        </div>

        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
          <div className="rounded-[0.65rem] border border-slate-200 bg-slate-50 px-4 py-3">
            <p className="text-[11px] font-black uppercase tracking-[0.14em] text-slate-400">Total travailleurs</p>
            <p className="mt-2 text-xl font-black text-slate-950">{total}</p>
          </div>
          <div className="rounded-[0.65rem] border border-slate-200 bg-slate-50 px-4 py-3">
            <p className="text-[11px] font-black uppercase tracking-[0.14em] text-slate-400">Actifs affiches</p>
            <p className="mt-2 text-xl font-black text-slate-950">{visibleActiveCount}</p>
          </div>
          <div className="rounded-[0.65rem] border border-slate-200 bg-slate-50 px-4 py-3">
            <p className="text-[11px] font-black uppercase tracking-[0.14em] text-slate-400">Presents affiches</p>
            <p className="mt-2 text-xl font-black text-slate-950">{visiblePresentCount}</p>
          </div>
        </div>
      </div>

      {notice ? (
        <div
          className={cn(
            "flex items-start justify-between gap-3 rounded-[0.65rem] border px-4 py-3 text-sm",
            notice.tone === "success"
              ? "border-emerald-200 bg-emerald-50 text-emerald-900"
              : "border-rose-200 bg-rose-50 text-rose-900",
          )}
        >
          <p>{notice.message}</p>
          <button
            type="button"
            aria-label="Fermer le message"
            onClick={() => setNotice(null)}
            className="rounded-md p-1 transition hover:bg-black/5"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
      ) : null}

      <Card className="rounded-[0.75rem] px-4 py-4">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-center">
          <div className="min-w-0 flex-1">
            <label className="sr-only" htmlFor="workers-search">
              Rechercher un travailleur
            </label>
            <div id="workers-search">
              <SearchInput
                value={searchInput}
                onChange={setSearchInput}
                placeholder="Rechercher par nom, prenom, matricule ou N degre d'identification..."
              />
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <div className="hidden items-center gap-2 rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm font-semibold text-slate-700 lg:flex">
              <Search className="h-4 w-4 text-slate-400" />
              <span>Trier par {visibleSortValue}</span>
            </div>
            <Button
              type="button"
              variant="secondary"
              size="sm"
              icon={Filter}
              aria-label="Afficher les filtres"
              onClick={() => setFiltersExpanded((current) => !current)}
            >
              {activeAdvancedFilterCount > 0 ? `Filtres (${activeAdvancedFilterCount})` : "Filtres"}
            </Button>
            {(activeAdvancedFilterCount > 0 || search) ? (
              <Button type="button" variant="ghost" size="sm" onClick={handleResetAll}>
                Reinitialiser les filtres
              </Button>
            ) : null}
          </div>
        </div>

        <div className={cn("mt-4 gap-3", filtersExpanded ? "grid" : "hidden lg:grid", "sm:grid-cols-2 xl:grid-cols-6")}>
          <Select
            label="Entreprise"
            options={companyOptions}
            value={filters.companyId}
            onChange={(event) => updateParams({ company: event.target.value || null, branch: null, site: null }, true)}
          />
          <Select
            label="Branch"
            options={branchOptions}
            value={filters.branchId}
            onChange={(event) => updateParams({ branch: event.target.value || null, site: null }, true)}
          />
          <Select
            label="Site de forage"
            options={siteOptions}
            value={filters.drillingSiteId}
            onChange={(event) => updateParams({ site: event.target.value || null }, true)}
          />
          <Select
            label="Departement"
            options={departmentOptions}
            value={filters.department}
            onChange={(event) => updateParams({ department: event.target.value || null }, true)}
          />
          <Select
            label="Statut medical"
            options={medicalStatusOptions}
            value={filters.medicalStatus}
            onChange={(event) => updateParams({ medicalStatus: event.target.value || null }, true)}
          />
          <Select
            label="Etat actuel"
            options={PRESENCE_OPTIONS}
            value={filters.presence}
            onChange={(event) => updateParams({ presence: event.target.value || null }, true)}
          />
          <Select
            label="Statut"
            options={ACTIVITY_OPTIONS}
            value={filters.activity}
            onChange={(event) => updateParams({ activity: event.target.value || null }, true)}
          />
          <Select
            label="Tri"
            options={SORT_OPTIONS}
            value={sortBy}
            onChange={(event) => updateParams({ sortBy: event.target.value || "created_at" }, true)}
          />
          <Select
            label="Ordre"
            options={[
              { value: "desc", label: "Decroissant" },
              { value: "asc", label: "Croissant" },
            ]}
            value={sortOrder}
            onChange={(event) => updateParams({ sortOrder: event.target.value || "desc" }, true)}
          />
          <Select
            label="Taille de page"
            options={PAGE_SIZE_OPTIONS.map((value) => ({ value: String(value), label: `${value} lignes` }))}
            value={String(pageSize)}
            onChange={(event) => updateParams({ pageSize: event.target.value || "25" }, true)}
          />
        </div>

        {activeFilterChips.length > 0 ? (
          <div className="mt-4 flex flex-wrap gap-2">
            {activeFilterChips.map((chip) => (
              <button
                key={`${chip.key}-${chip.value}`}
                type="button"
                onClick={() => handleRemoveFilterChip(chip.key)}
                className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-slate-50 px-3 py-1.5 text-xs font-semibold text-slate-700 transition hover:border-slate-300 hover:bg-white"
              >
                <span>{chip.label}: {chip.value}</span>
                <X className="h-3.5 w-3.5" />
              </button>
            ))}
          </div>
        ) : null}

        {activeAdvancedFilterCount > 0 ? (
          <p className="mt-3 text-xs text-slate-500">
            Les filtres avances affinent les resultats charges par la page courante.
          </p>
        ) : null}
      </Card>

      {error ? (
        <Card className="rounded-[0.75rem] px-5 py-5">
          <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
            <div>
              <p className="text-base font-bold text-slate-950">Chargement impossible</p>
              <p className="mt-1 text-sm text-slate-600">{error}</p>
            </div>
            <Button variant="secondary" icon={RefreshCw} onClick={() => setRetryToken((current) => current + 1)}>
              Reessayer
            </Button>
          </div>
        </Card>
      ) : null}

      {!error ? (
        <>
          {loading ? (
            <WorkersTableSkeleton />
          ) : total === 0 ? (
            <EmptyState
              title="Aucun travailleur enregistre"
              description="Ajoutez votre premier travailleur pour commencer la gestion des dossiers medicaux et des affectations."
              actionLabel="Ajouter un travailleur"
              onAction={handleOpenCreate}
            />
          ) : !hasRows ? (
            <EmptyState
              title="Aucun travailleur ne correspond a vos criteres"
              description="Ajustez la recherche ou reinitialisez les filtres pour afficher de nouveaux resultats."
              actionLabel="Reinitialiser les filtres"
              onAction={handleResetAll}
            />
          ) : (
            <>
              <div className="hidden overflow-hidden rounded-[0.75rem] border border-slate-200 bg-white md:block">
                <div className="overflow-x-auto">
                  <table className="min-w-full border-separate border-spacing-0">
                    <thead>
                      <tr className="bg-slate-50">
                        {tableColumns.map((column) => {
                          const sortableField =
                            column.key === "name" ||
                            column.key === "employee_number" ||
                            column.key === "medical_status" ||
                            column.key === "created_at"
                              ? (column.key as WorkerSortField)
                              : null;

                          return (
                            <th
                              key={column.key}
                              className={cn(
                                "sticky top-0 z-10 border-b border-slate-200 px-5 py-4 text-left text-[11px] font-black uppercase tracking-[0.16em] text-slate-500",
                                column.key === "actions" ? "text-right" : "",
                              )}
                            >
                              {sortableField ? (
                                <button
                                  type="button"
                                  onClick={() => handleSort(sortableField)}
                                  className="inline-flex items-center gap-1 text-left transition hover:text-slate-900"
                                >
                                  <span>{column.title}</span>
                                  {renderSortIcon(sortableField)}
                                </button>
                              ) : (
                                <span>{column.title}</span>
                              )}
                            </th>
                          );
                        })}
                      </tr>
                    </thead>

                    <tbody>
                      {filteredRows.map((worker) => {
                        const companyLabel = companyLabelFor(worker);
                        const branchLabel = branchLabelFor(worker);
                        const siteLabel = siteLabelFor(worker);
                        const fullName = `${worker.last_name || ""} ${worker.first_name || ""}`.trim() || worker.full_name || "Travailleur";
                        const employeeCode = worker.employee_code || worker.employee_number || "Non renseigne";
                        const functionLabel = normalizeText(worker.position || worker.job_title) || "Non renseigne";
                        const departmentLabel = normalizeText(worker.department) || "Non renseigne";
                        const primaryAssignment = branchLabel !== "Non renseigne" ? branchLabel : companyLabel;

                        return (
                          <tr key={worker.id} className="group transition hover:bg-slate-50/70">
                            <td className="border-b border-slate-100 px-5 py-4 align-top">
                              <div className="flex items-start gap-3">
                                <WorkerAvatar worker={worker} />
                                <div className="min-w-0">
                                  <Link
                                    to={`/workers/${worker.id}`}
                                    state={{ returnTo }}
                                    className="text-sm font-bold text-slate-950 transition hover:text-[#0085A3]"
                                  >
                                    {fullName}
                                  </Link>
                                  <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-slate-500">
                                    <span>{worker.national_id || "Non renseigne"}</span>
                                    {worker.gender ? (
                                      <span className="inline-flex items-center rounded-full border border-slate-200 bg-slate-50 px-2 py-0.5 font-semibold text-slate-600">
                                        {worker.gender.startsWith("F") ? "F" : worker.gender.startsWith("M") ? "M" : humanizeToken(worker.gender, "N/A")}
                                      </span>
                                    ) : null}
                                  </div>
                                </div>
                              </div>
                            </td>
                            <td className="border-b border-slate-100 px-5 py-4 align-top">
                              <span className="inline-flex rounded-lg border border-slate-200 bg-slate-50 px-2.5 py-1 font-mono text-xs font-bold text-slate-800">
                                {employeeCode}
                              </span>
                            </td>
                            <td className="border-b border-slate-100 px-5 py-4 align-top text-sm text-slate-700">
                              <p className="font-semibold text-slate-900">{primaryAssignment}</p>
                              <p className="mt-1 text-xs text-slate-500">{siteLabel}</p>
                            </td>
                            <td className="border-b border-slate-100 px-5 py-4 align-top text-sm text-slate-700">
                              <p className="font-semibold text-slate-900">{functionLabel}</p>
                              <p className="mt-1 text-xs text-slate-500">{departmentLabel}</p>
                            </td>
                            <td className="border-b border-slate-100 px-5 py-4 align-top">
                              <MedicalStatusBadge value={worker.medical_status || worker.medical_file_status} />
                            </td>
                            <td className="border-b border-slate-100 px-5 py-4 align-top">
                              <PresenceStatusBadge value={worker.etat_actual} />
                            </td>
                            <td className="border-b border-slate-100 px-5 py-4 align-top">
                              <Badge tone={resolveWorkerIsActive(worker) ? "active" : "inactive"}>
                                {resolveWorkerIsActive(worker) ? "Actif" : "Inactif"}
                              </Badge>
                            </td>
                            <td className="border-b border-slate-100 px-5 py-4 align-top">
                              <WorkerActionsMenu
                                worker={worker}
                                onView={(currentWorker) => {
                                  navigate(`/workers/${currentWorker.id}`, {
                                    state: { returnTo },
                                  });
                                }}
                                onEdit={handleOpenEdit}
                                onAssignCampaign={(currentWorker) => {
                                  setCampaignTarget(currentWorker);
                                  setSelectedCampaignId("");
                                  setCampaignError(null);
                                }}
                                onToggleStatus={setStatusTarget}
                                onDelete={(currentWorker) => {
                                  setDeleteTarget(currentWorker);
                                  setDeletePassword("");
                                  setDeleteError(null);
                                }}
                              />
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </div>

              <div className="space-y-3 md:hidden">
                {filteredRows.map((worker) => (
                  <WorkersMobileCard
                    key={worker.id}
                    worker={worker}
                    companyLabel={companyLabelFor(worker)}
                    branchLabel={branchLabelFor(worker)}
                    siteLabel={siteLabelFor(worker)}
                    onView={(currentWorker) => {
                      navigate(`/workers/${currentWorker.id}`, {
                        state: { returnTo },
                      });
                    }}
                    onEdit={handleOpenEdit}
                    onAssignCampaign={(currentWorker) => {
                      setCampaignTarget(currentWorker);
                      setSelectedCampaignId("");
                      setCampaignError(null);
                    }}
                    onToggleStatus={setStatusTarget}
                    onDelete={(currentWorker) => {
                      setDeleteTarget(currentWorker);
                      setDeletePassword("");
                      setDeleteError(null);
                    }}
                  />
                ))}
              </div>

              <div className="flex flex-col gap-3 rounded-[0.75rem] border border-slate-200 bg-white px-4 py-4 shadow-sm lg:flex-row lg:items-center lg:justify-between">
                <div className="text-sm text-slate-600">
                  {activeAdvancedFilterCount > 0 ? (
                    <p>
                      {filteredRows.length} affiches sur {rows.length} charges. Total disponible: {total}.
                    </p>
                  ) : (
                    <p>
                      {rangeStart}-{rangeEnd} sur {total} travailleurs.
                    </p>
                  )}
                </div>

                <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
                  <div className="flex items-center gap-2">
                    <label htmlFor="workers-page-size" className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-400">
                      Taille
                    </label>
                    <select
                      id="workers-page-size"
                      value={String(pageSize)}
                      onChange={(event) => updateParams({ pageSize: event.target.value }, true)}
                      className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-semibold text-slate-700 outline-none transition focus:border-[#0085A3] focus:ring-4 focus:ring-[#0085A3]/10"
                    >
                      {PAGE_SIZE_OPTIONS.map((option) => (
                        <option key={option} value={option}>
                          {option}
                        </option>
                      ))}
                    </select>
                  </div>

                  <div className="flex items-center gap-2">
                    <Button
                      variant="secondary"
                      size="sm"
                      disabled={page <= 1}
                      onClick={() => updateParams({ page: String(page - 1) })}
                    >
                      <ChevronLeft className="h-4 w-4" />
                      Precedent
                    </Button>
                    <div className="inline-flex min-w-[88px] items-center justify-center rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm font-bold text-slate-700">
                      Page {page}/{totalPages}
                    </div>
                    <Button
                      variant="secondary"
                      size="sm"
                      disabled={page >= totalPages}
                      onClick={() => updateParams({ page: String(page + 1) })}
                    >
                      Suivant
                      <ChevronRight className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
              </div>
            </>
          )}
        </>
      ) : null}

      <Modal
        open={formOpen}
        title={editingWorkerId ? "Modifier le travailleur" : "Nouveau travailleur"}
        onClose={() => {
          setFormOpen(false);
          setFormError(null);
        }}
      >
        <div className="space-y-5">
          {formError ? (
            <div className="rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-800">
              {formError}
            </div>
          ) : null}

          <div className="grid gap-4 md:grid-cols-2">
            <Input
              label="Prenom"
              value={formState.first_name}
              onChange={(event) => setFormState((current) => ({ ...current, first_name: event.target.value }))}
            />
            <Input
              label="Nom"
              value={formState.last_name}
              onChange={(event) => setFormState((current) => ({ ...current, last_name: event.target.value }))}
            />
            <Input
              label="Matricule"
              value={formState.employee_code}
              onChange={(event) => setFormState((current) => ({ ...current, employee_code: event.target.value }))}
            />
            <Input
              label="Numero d'identification"
              value={formState.national_id}
              onChange={(event) => setFormState((current) => ({ ...current, national_id: event.target.value }))}
            />
            <Input
              label="Telephone"
              value={formState.phone}
              onChange={(event) => setFormState((current) => ({ ...current, phone: event.target.value }))}
            />
            <Input
              label="Statut medical"
              value={formState.medical_status}
              onChange={(event) => setFormState((current) => ({ ...current, medical_status: event.target.value }))}
            />
            <Select
              label="Entreprise"
              options={[
                { value: "", label: supportLoading ? "Chargement..." : companies.length ? "Selectionner une entreprise" : "Aucune entreprise disponible" },
                ...companies.map((company) => ({ value: String(company.id), label: company.name })),
              ]}
              value={formState.company_id}
              onChange={(event) =>
                setFormState((current) => ({
                  ...current,
                  company_id: event.target.value,
                  branch_id: "",
                  drilling_site_id: "",
                }))
              }
            />
            {supportError && (
              <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700" role="alert">
                {supportError}
                <button type="button" className="ml-2 underline" onClick={() => setRetryToken((value) => value + 1)}>
                  Réessayer
                </button>
              </div>
            )}
            <Select
              label="Branch"
              options={formBranchOptions}
              value={formState.branch_id}
              onChange={(event) =>
                setFormState((current) => ({
                  ...current,
                  branch_id: event.target.value,
                  drilling_site_id: "",
                }))
              }
            />
            <Select
              label="Site de forage"
              options={formSiteOptions}
              value={formState.drilling_site_id}
              onChange={(event) => setFormState((current) => ({ ...current, drilling_site_id: event.target.value }))}
            />
            <Input
              label="Fonction"
              value={formState.position}
              onChange={(event) => setFormState((current) => ({ ...current, position: event.target.value }))}
            />
            <Input
              label="Departement"
              value={formState.department}
              onChange={(event) => setFormState((current) => ({ ...current, department: event.target.value }))}
            />
            <Select
              label="Etat actuel"
              options={PRESENCE_OPTIONS.filter((option) => option.value !== "")}
              value={formState.etat_actual}
              onChange={(event) => setFormState((current) => ({ ...current, etat_actual: event.target.value }))}
            />
            <Select
              label="Statut"
              options={STATUS_OPTIONS}
              value={formState.status}
              onChange={(event) =>
                setFormState((current) => ({
                  ...current,
                  status: event.target.value === "inactive" ? "inactive" : "active",
                }))
              }
            />
          </div>

          <div className="flex justify-end gap-2">
            <Button variant="secondary" onClick={() => setFormOpen(false)}>
              Annuler
            </Button>
            <Button loading={saveLoading} onClick={() => void handleSaveWorker()}>
              {editingWorkerId ? "Enregistrer les modifications" : "Creer le travailleur"}
            </Button>
          </div>
        </div>
      </Modal>

      <Modal
        open={Boolean(statusTarget)}
        title={resolveWorkerIsActive(statusTarget || ({} as Worker)) ? "Desactiver le travailleur" : "Activer le travailleur"}
        onClose={() => setStatusTarget(null)}
      >
        <div className="space-y-5">
          <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
            {resolveWorkerIsActive(statusTarget || ({} as Worker))
              ? "La desactivation rendra ce travailleur inactif dans le registre courant, sans supprimer son historique medical."
              : "La reactivation remettra ce travailleur a disposition dans les listes et les flux de suivi."}
          </div>
          <div className="flex justify-end gap-2">
            <Button variant="secondary" onClick={() => setStatusTarget(null)}>
              Annuler
            </Button>
            <Button
              variant={resolveWorkerIsActive(statusTarget || ({} as Worker)) ? "secondary" : "primary"}
              loading={statusLoading}
              onClick={() => void handleToggleWorkerStatus()}
            >
              {resolveWorkerIsActive(statusTarget || ({} as Worker)) ? "Confirmer la desactivation" : "Confirmer l'activation"}
            </Button>
          </div>
        </div>
      </Modal>

      <Modal
        open={Boolean(deleteTarget)}
        title="Supprimer le travailleur"
        onClose={() => {
          setDeleteTarget(null);
          setDeletePassword("");
          setDeleteError(null);
        }}
      >
        <div className="space-y-5">
          <div className="rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-900">
            Cette suppression desactive egalement le travailleur et retire sa fiche des listes actives. L'historique associe ne doit pas etre supprime sans verification.
          </div>
          <p className="text-sm text-slate-700">
            Saisissez votre mot de passe pour confirmer la suppression de{" "}
            <span className="font-bold text-slate-950">
              {deleteTarget ? `${deleteTarget.last_name || ""} ${deleteTarget.first_name || ""}`.trim() : "ce travailleur"}
            </span>.
          </p>
          <Input
            label="Mot de passe"
            type="password"
            error={deleteError}
            value={deletePassword}
            onChange={(event) => {
              setDeletePassword(event.target.value);
              if (deleteError) {
                setDeleteError(null);
              }
            }}
          />
          <div className="flex justify-end gap-2">
            <Button
              variant="secondary"
              onClick={() => {
                setDeleteTarget(null);
                setDeletePassword("");
                setDeleteError(null);
              }}
            >
              Annuler
            </Button>
            <Button variant="danger" loading={deleteLoading} onClick={() => void handleDeleteWorker()}>
              Supprimer
            </Button>
          </div>
        </div>
      </Modal>

      <Modal
        open={Boolean(campaignTarget)}
        title="Ajouter a une campagne"
        onClose={() => {
          setCampaignTarget(null);
          setSelectedCampaignId("");
          setCampaignError(null);
        }}
      >
        <div className="space-y-5">
          {campaignError ? (
            <div className="rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-800">
              {campaignError}
            </div>
          ) : null}

          <p className="text-sm text-slate-700">
            Selectionnez une campagne existante pour y rattacher{" "}
            <span className="font-bold text-slate-950">
              {campaignTarget ? `${campaignTarget.last_name || ""} ${campaignTarget.first_name || ""}`.trim() : "ce travailleur"}
            </span>.
          </p>

          <Select
            label="Campagne"
            options={campaignsSelectOptions}
            value={selectedCampaignId}
            onChange={(event) => setSelectedCampaignId(event.target.value)}
          />

          {campaignLoading ? (
            <div className="flex items-center gap-2 rounded-lg border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-600">
              <RefreshCw className="h-4 w-4 animate-spin" />
              <span>Chargement des campagnes...</span>
            </div>
          ) : null}

          <div className="flex justify-end gap-2">
            <Button
              variant="secondary"
              onClick={() => {
                setCampaignTarget(null);
                setSelectedCampaignId("");
                setCampaignError(null);
              }}
            >
              Annuler
            </Button>
            <Button loading={campaignSubmitting} onClick={() => void handleAssignToCampaign()}>
              Ajouter a la campagne
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
};
