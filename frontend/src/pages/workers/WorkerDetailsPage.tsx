import {
  Activity,
  AlertCircle,
  ArrowLeft,
  Building2,
  ChevronDown,
  ClipboardList,
  Eye,
  FileHeart,
  FileStack,
  HeartPulse,
  MapPin,
  MoreHorizontal,
  Pencil,
  Pill,
  Plus,
  RefreshCw,
  Stethoscope,
  Trash2,
  UserCheck,
  UserRoundX,
  Users,
  type LucideIcon,
} from "lucide-react";
import { Fragment, useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { Link, useLocation, useNavigate, useParams } from "react-router-dom";

import { aptitudeCertificatesApi } from "@/api/aptitudeCertificatesApi";
import { branchesApi } from "@/api/branchesApi";
import { campaignsApi } from "@/api/campaignsApi";
import { companiesApi } from "@/api/companiesApi";
import { drillingSitesApi } from "@/api/drillingSitesApi";
import { fetchAllPages } from "@/api/fetchAllPages";
import { medicalTestsApi } from "@/api/medicalTestsApi";
import { medicalVisitsApi } from "@/api/medicalVisitsApi";
import { orientationsApi } from "@/api/orientationsApi";
import { prescriptionsApi } from "@/api/prescriptionsApi";
import { workerTestsApi } from "@/api/workerTestsApi";
import { workersApi } from "@/api/workersApi";
import { savedConflictMessage } from "@/api/localMutation";
import { Badge } from "@/components/common/Badge";
import { Button } from "@/components/common/Button";
import { Card } from "@/components/common/Card";
import { EmptyState } from "@/components/common/EmptyState";
import { Input } from "@/components/common/Input";
import { Modal } from "@/components/common/Modal";
import { Select } from "@/components/common/Select";
import { usePermissions } from "@/hooks/usePermissions";
import type { Option } from "@/types/common";
import type {
  AptitudeCertificate,
  Branch,
  Campaign,
  Company,
  DrillingSite,
  MedicalVisit,
  OrientationCertificate,
  Prescription,
  Worker,
  WorkerTest,
} from "@/types/entities";
import { cn } from "@/utils/cn";
import { formatDisplayDate, formatDisplayDateTime } from "@/utils/date";

type ProfileTab = "overview" | "campaigns" | "visits" | "tests" | "certificates" | "prescriptions";
type NoticeState =
  | {
      tone: "success" | "error";
      message: string;
    }
  | null;
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

const PRESENCE_OPTIONS: Option[] = [
  { value: "present", label: "Présent" },
  { value: "absence", label: "Absent" },
  { value: "sick_leave", label: "Congé maladie" },
  { value: "recovery", label: "Récupération" },
  { value: "mission", label: "Mission" },
  { value: "work_accident", label: "Accident de travail" },
  { value: "annual_leave", label: "Congé annuel" },
  { value: "unpaid_leave", label: "Congé sans solde" },
  { value: "maternity_leave", label: "Congé maternité" },
  { value: "paternity_leave", label: "Congé paternité" },
  { value: "retired", label: "Retraite" },
  { value: "suspended", label: "Suspendu" },
  { value: "terminated", label: "Fin de contrat" },
];

const STATUS_OPTIONS: Option[] = [
  { value: "active", label: "Actif" },
  { value: "inactive", label: "Inactif" },
];

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value !== null && !Array.isArray(value);

const normalizeText = (value: string | null | undefined) => (value || "").trim();

const humanizeToken = (value: string | null | undefined, fallback = "Non renseigné") => {
  if (!value) {
    return fallback;
  }

  return value
    .replace(/[_-]+/g, " ")
    .replace(/\s+/g, " ")
    .trim()
    .replace(/\b\w/g, (character) => character.toUpperCase());
};

const safeDate = (value: string | Date | null | undefined, fallback = "Non disponible") =>
  formatDisplayDate(value) || fallback;

const safeDateTime = (value: string | Date | null | undefined, fallback = "Non disponible") =>
  formatDisplayDateTime(value) || fallback;

const safeDateRange = (start: string | null | undefined, end: string | null | undefined) => {
  const startLabel = formatDisplayDate(start);
  const endLabel = formatDisplayDate(end);

  if (startLabel && endLabel) {
    return `${startLabel} – ${endLabel}`;
  }

  return startLabel || endLabel || "Non disponible";
};

const calculateAge = (birthDate: string | null | undefined) => {
  if (!birthDate) {
    return null;
  }

  const parts = birthDate.match(/^(\d{4})-(\d{2})-(\d{2})/);
  if (!parts) {
    return null;
  }

  const year = Number(parts[1]);
  const month = Number(parts[2]);
  const day = Number(parts[3]);

  if (!Number.isFinite(year) || !Number.isFinite(month) || !Number.isFinite(day)) {
    return null;
  }

  const today = new Date();
  let age = today.getFullYear() - year;
  const birthdayReached =
    today.getMonth() + 1 > month ||
    (today.getMonth() + 1 === month && today.getDate() >= day);

  if (!birthdayReached) {
    age -= 1;
  }

  return age >= 0 ? age : null;
};

const resolveWorkerIsActive = (worker: Worker | null | undefined) => {
  if (!worker) {
    return false;
  }

  return typeof worker.is_active === "boolean" ? worker.is_active : worker.status !== "inactive";
};

const formatWorkerStatusLabel = (worker: Worker | null | undefined) =>
  resolveWorkerIsActive(worker) ? "Actif" : "Inactif";

const getWorkerStatusTone = (worker: Worker | null | undefined) =>
  resolveWorkerIsActive(worker) ? "active" : "inactive";

const formatPresenceLabel = (value: string | null | undefined) => {
  const normalized = (value || "").trim().toLowerCase();
  const labels: Record<string, string> = {
    present: "Présent",
    absence: "Absent",
    absent: "Absent",
    leave: "En congé",
    sick_leave: "Congé maladie",
    recovery: "Récupération",
    mission: "Mission",
    work_accident: "Accident de travail",
    annual_leave: "Congé annuel",
    unpaid_leave: "Congé sans solde",
    maternity_leave: "Congé maternité",
    paternity_leave: "Congé paternité",
    retired: "Retraite",
    suspended: "Suspendu",
    terminated: "Fin de contrat",
  };

  return labels[normalized] || humanizeToken(value, "Non renseigné");
};

const getPresenceTone = (value: string | null | undefined) => {
  const normalized = (value || "").trim().toLowerCase();

  if (normalized === "present") {
    return "active";
  }
  if (normalized === "absence" || normalized === "absent" || normalized === "terminated") {
    return "failed";
  }
  if (normalized.includes("leave") || normalized === "mission" || normalized === "recovery") {
    return "pending";
  }
  return "inactive";
};

const formatGenderLabel = (value: string | null | undefined) => {
  const normalized = (value || "").trim().toLowerCase();
  const labels: Record<string, string> = {
    male: "Homme",
    masculin: "Homme",
    homme: "Homme",
    m: "Homme",
    female: "Femme",
    feminin: "Femme",
    féminine: "Femme",
    femme: "Femme",
    f: "Femme",
  };

  return labels[normalized] || humanizeToken(value);
};

const formatMedicalStatusLabel = (value: string | null | undefined) => {
  if (!value) {
    return "Non renseigné";
  }

  const normalized = value.trim().toLowerCase();
  const labels: Record<string, string> = {
    fit: "Apte",
    apte: "Apte",
    in_progress: "En cours",
    pending: "En attente",
    "a examiner": "À examiner",
    "à examiner": "À examiner",
    draft: "Brouillon",
    unfit: "Inapte",
    inapte: "Inapte",
    confirmed: "Confirmé",
    validated: "Validé",
    signed: "Signé",
  };

  return labels[normalized] || humanizeToken(value);
};

const getMedicalStatusTone = (value: string | null | undefined) => {
  const normalized = (value || "").trim().toLowerCase();

  if (!normalized) {
    return "inactive";
  }
  if (
    normalized.includes("inapt") ||
    normalized.includes("unfit") ||
    normalized.includes("abnormal") ||
    normalized.includes("anormal")
  ) {
    return "failed";
  }
  if (
    normalized.includes("reserve") ||
    normalized.includes("restriction") ||
    normalized.includes("progress") ||
    normalized.includes("pending") ||
    normalized.includes("attente")
  ) {
    return "pending";
  }
  if (normalized.includes("sign") || normalized.includes("valid") || normalized.includes("confirm")) {
    return "completed";
  }
  if (normalized.includes("apte") || normalized.includes("fit") || normalized.includes("normal")) {
    return "active";
  }
  return "inactive";
};

const formatCampaignStatusLabel = (value: string | null | undefined) => {
  const normalized = (value || "").trim().toLowerCase();
  const labels: Record<string, string> = {
    draft: "Brouillon",
    active: "Active",
    completed: "Terminée",
    pending: "En attente",
  };

  return labels[normalized] || humanizeToken(value);
};

const getCampaignStatusTone = (value: string | null | undefined) => {
  const normalized = (value || "").trim().toLowerCase();
  if (normalized === "active") return "active";
  if (normalized === "completed") return "completed";
  if (normalized === "pending") return "pending";
  return "inactive";
};

const formatMedicalVisitStatus = (value: string | null | undefined) => {
  const normalized = (value || "").trim().toLowerCase();
  const labels: Record<string, string> = {
    draft: "Brouillon",
    basic_info_completed: "Informations de base",
    tests_in_progress: "Examens en cours",
    ready_for_doctor: "Prêt pour le médecin",
    validated: "Validée",
    needs_correction: "Correction requise",
    synced: "Synchronisée",
  };

  return labels[normalized] || humanizeToken(value);
};

const getMedicalVisitTone = (value: string | null | undefined) => {
  const normalized = (value || "").trim().toLowerCase();
  if (normalized === "validated" || normalized === "synced") return "active";
  if (normalized === "needs_correction") return "failed";
  if (normalized === "draft") return "inactive";
  return "pending";
};

const formatCertificateStatusLabel = (value: string | null | undefined) => {
  const normalized = (value || "").trim().toLowerCase();
  const labels: Record<string, string> = {
    draft: "Brouillon",
    signed: "Signé",
    confirmed: "Confirmé",
    validated: "Validé",
    printed: "Imprimé",
    cancelled: "Annulé",
  };

  return labels[normalized] || humanizeToken(value);
};

const getCertificateTone = (value: string | null | undefined) => {
  const normalized = (value || "").trim().toLowerCase();
  if (normalized === "signed" || normalized === "validated") return "active";
  if (normalized === "confirmed" || normalized === "printed") return "completed";
  if (normalized === "cancelled") return "failed";
  if (normalized === "draft") return "inactive";
  return "pending";
};

const formatTestStatusLabel = (test: WorkerTest) => {
  if (test.abnormal || test.is_normal === false) {
    return "Anormal";
  }

  const normalized = (test.status || "").trim().toLowerCase();
  const labels: Record<string, string> = {
    pending: "En attente",
    completed: "Terminé",
    reviewed: "Relu",
    normal: "Normal",
  };

  return labels[normalized] || humanizeToken(test.status);
};

const getTestTone = (test: WorkerTest) => {
  if (test.abnormal || test.is_normal === false) {
    return "failed";
  }

  const normalized = (test.status || "").trim().toLowerCase();
  if (normalized === "reviewed") return "completed";
  if (normalized === "completed") return "active";
  if (normalized === "pending") return "pending";
  return "inactive";
};

const formatOrientationTypeLabel = (certificate: OrientationCertificate) => {
  const normalized = (certificate.orientation_type || "").trim().toLowerCase();
  const labels: Record<string, string> = {
    initial: "Initiale",
    avis_specialise: "Avis spécialisé",
    diagnostic_care: "Prise en charge diagnostique",
  };

  if (labels[normalized]) {
    return labels[normalized];
  }

  if (normalized === "other" && certificate.orientation_type_other) {
    return certificate.orientation_type_other;
  }

  return humanizeToken(certificate.orientation_type);
};

const formatAptitudeLabel = (value: string | null | undefined) => {
  const normalized = (value || "").trim().toLowerCase();
  const labels: Record<string, string> = {
    apte: "Apte",
    "en attente": "En attente",
    pending: "En attente",
    inapte: "Inapte",
  };

  return labels[normalized] || humanizeToken(value);
};

const readMedicalFileRecord = (worker: Worker | null) =>
  isRecord(worker?.medical_file_data) ? (worker.medical_file_data as Record<string, unknown>) : null;

const readMedicalFileStatus = (worker: Worker | null) => {
  const medicalFileRecord = readMedicalFileRecord(worker);
  const confirmationStatus = medicalFileRecord?.confirmationStatus;
  return typeof worker?.medical_file_status === "string"
    ? worker.medical_file_status
    : typeof confirmationStatus === "string"
      ? confirmationStatus
      : null;
};

const hasStructuredMedicalFile = (worker: Worker | null) => {
  const medicalFileRecord = readMedicalFileRecord(worker);
  return Boolean(medicalFileRecord && Object.keys(medicalFileRecord).length > 0);
};

const formatSynchronizationLabel = (value: string | null | undefined) => {
  const normalized = (value || "").trim().toLowerCase();
  const labels: Record<string, string> = {
    never_submitted: "Disponible localement uniquement",
    local_only: "Disponible localement uniquement",
    central_pending: "En attente de synchronisation centrale",
    synced: "Synchronisé",
    conflict: "Conflit de synchronisation",
  };

  return labels[normalized] || humanizeToken(value, "Non disponible");
};

const buildWorkerFormState = (worker: Worker | null): WorkerFormState => ({
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
  status: resolveWorkerIsActive(worker) ? "active" : "inactive",
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

const getWorkerDisplayName = (worker: Worker | null | undefined) =>
  [worker?.first_name, worker?.last_name].filter(Boolean).join(" ").trim() || worker?.full_name || "Travailleur";

const getWorkerInitials = (worker: Worker | null | undefined) =>
  `${worker?.first_name?.[0] || ""}${worker?.last_name?.[0] || ""}`.trim().toUpperCase() || "TR";

const normalizeWorkerTestRecord = (test: WorkerTest, medicalTestNames: Map<number, string>) =>
  ({
    ...test,
    test_name:
      test.test_name ||
      medicalTestNames.get(test.test_id || test.medical_test_id) ||
      `Examen #${test.test_id || test.medical_test_id || test.id}`,
    abnormal:
      typeof test.abnormal === "boolean"
        ? test.abnormal
        : test.is_normal === false,
    tested_at: test.tested_at || test.completed_at || test.created_at,
  }) as WorkerTest;

const isCampaignRecord = (value: unknown): value is Campaign =>
  isRecord(value) && typeof value.id === "number" && (typeof value.name === "string" || typeof value.title === "string");

const isWorkerTestRecord = (value: unknown): value is WorkerTest =>
  isRecord(value) && typeof value.id === "number" && (typeof value.test_id === "number" || typeof value.medical_test_id === "number");

const isOrientationRecord = (value: unknown): value is OrientationCertificate =>
  isRecord(value) && typeof value.id === "number" && typeof value.orientation_number === "string";

const isAptitudeRecord = (value: unknown): value is AptitudeCertificate =>
  isRecord(value) && typeof value.id === "number" && typeof value.certificate_number === "string";

const downloadBlob = (blob: Blob, filename: string) => {
  const objectUrl = window.URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = objectUrl;
  anchor.download = filename;
  anchor.click();
  window.URL.revokeObjectURL(objectUrl);
};

const sortByNewest = <T,>(items: T[], getValue: (item: T) => string | null | undefined) =>
  [...items].sort((left, right) => {
    const leftDate = getValue(left) ? Date.parse(String(getValue(left))) : 0;
    const rightDate = getValue(right) ? Date.parse(String(getValue(right))) : 0;
    return rightDate - leftDate;
  });

const WorkerAvatar = ({ worker }: { worker: Worker | null }) => (
  <div className="relative flex h-16 w-16 shrink-0 items-center justify-center overflow-hidden rounded-2xl border border-slate-200 bg-slate-100 text-lg font-black text-slate-700">
    <span>{getWorkerInitials(worker)}</span>
    {worker?.photo ? (
      <img
        src={worker.photo}
        alt={getWorkerDisplayName(worker)}
        className="absolute inset-0 h-full w-full object-cover"
        onError={(event) => {
          event.currentTarget.style.display = "none";
        }}
      />
    ) : null}
  </div>
);

const WorkerStatusBadge = ({ worker }: { worker: Worker | null }) => (
  <Badge tone={getWorkerStatusTone(worker)}>{formatWorkerStatusLabel(worker)}</Badge>
);

const MedicalStatusBadge = ({ value }: { value: string | null | undefined }) => (
  <Badge tone={getMedicalStatusTone(value)}>{formatMedicalStatusLabel(value)}</Badge>
);

const PresenceStatusBadge = ({ value }: { value: string | null | undefined }) => (
  <Badge tone={getPresenceTone(value)}>{formatPresenceLabel(value)}</Badge>
);

const ProfileSummaryCard = ({
  icon: Icon,
  label,
  value,
  detail,
}: {
  icon: LucideIcon;
  label: string;
  value: string;
  detail?: string | null;
}) => (
  <Card className="rounded-2xl p-4">
    <div className="flex items-start justify-between gap-3">
      <div>
        <p className="text-[11px] font-black uppercase tracking-[0.16em] text-slate-400">{label}</p>
        <p className="mt-2 text-lg font-black text-slate-950">{value}</p>
        {detail ? <p className="mt-1 text-sm text-slate-500">{detail}</p> : null}
      </div>
      <div className="rounded-xl border border-slate-200 bg-slate-50 p-2.5 text-slate-600">
        <Icon className="h-4 w-4" />
      </div>
    </div>
  </Card>
);

const DetailRow = ({
  label,
  value,
  mono,
}: {
  label: string;
  value: string;
  mono?: boolean;
}) => (
  <div className="flex items-start justify-between gap-4 border-b border-slate-100 py-3 first:pt-0 last:border-b-0 last:pb-0">
    <span className="text-sm text-slate-500">{label}</span>
    <span className={cn("max-w-[65%] text-right text-sm font-semibold text-slate-900", mono ? "font-mono" : "")}>
      {value}
    </span>
  </div>
);

const SectionEmptyState = ({
  title,
  description,
  action,
}: {
  title: string;
  description: string;
  action?: ReactNode;
}) => (
  <div className="rounded-2xl border border-dashed border-slate-200 bg-slate-50 px-5 py-8 text-center">
    <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl border border-slate-200 bg-white text-slate-500">
      <ClipboardList className="h-5 w-5" />
    </div>
    <h3 className="mt-4 text-base font-bold text-slate-950">{title}</h3>
    <p className="mt-2 text-sm text-slate-500">{description}</p>
    {action ? <div className="mt-4">{action}</div> : null}
  </div>
);

const ProfileLoadingSkeleton = () => (
  <div className="space-y-6">
    <Card className="rounded-2xl p-6">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="flex items-start gap-4">
          <div className="h-16 w-16 animate-pulse rounded-2xl bg-slate-200" />
          <div className="space-y-3">
            <div className="h-4 w-32 animate-pulse rounded bg-slate-200" />
            <div className="h-8 w-64 animate-pulse rounded bg-slate-200" />
            <div className="h-4 w-48 animate-pulse rounded bg-slate-100" />
          </div>
        </div>
        <div className="flex gap-2">
          <div className="h-10 w-32 animate-pulse rounded-xl bg-slate-200" />
          <div className="h-10 w-40 animate-pulse rounded-xl bg-slate-100" />
        </div>
      </div>
    </Card>

    <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
      {Array.from({ length: 4 }).map((_, index) => (
        <Card key={`worker-summary-skeleton-${index}`} className="rounded-2xl p-4">
          <div className="space-y-3">
            <div className="h-3 w-28 animate-pulse rounded bg-slate-100" />
            <div className="h-6 w-20 animate-pulse rounded bg-slate-200" />
            <div className="h-3 w-36 animate-pulse rounded bg-slate-100" />
          </div>
        </Card>
      ))}
    </div>

    <div className="grid gap-6 xl:grid-cols-[minmax(0,1.7fr)_minmax(320px,1fr)]">
      <Card className="rounded-2xl p-6">
        <div className="space-y-4">
          <div className="h-4 w-40 animate-pulse rounded bg-slate-200" />
          <div className="h-10 w-full animate-pulse rounded bg-slate-100" />
          <div className="h-56 w-full animate-pulse rounded-2xl bg-slate-100" />
        </div>
      </Card>
      <div className="space-y-4">
        {Array.from({ length: 3 }).map((_, index) => (
          <Card key={`worker-sidebar-skeleton-${index}`} className="rounded-2xl p-6">
            <div className="space-y-3">
              <div className="h-4 w-32 animate-pulse rounded bg-slate-200" />
              <div className="h-4 w-full animate-pulse rounded bg-slate-100" />
              <div className="h-4 w-full animate-pulse rounded bg-slate-100" />
              <div className="h-4 w-4/5 animate-pulse rounded bg-slate-100" />
            </div>
          </Card>
        ))}
      </div>
    </div>
  </div>
);

const WorkerActionsMenu = ({
  items,
}: {
  items: Array<{
    label: string;
    icon: LucideIcon;
    onSelect: () => void;
    destructive?: boolean;
  }>;
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

  if (items.length === 0) {
    return null;
  }

  return (
    <div ref={containerRef} className="relative">
      <button
        type="button"
        aria-label="Actions secondaires"
        aria-expanded={open}
        aria-haspopup="menu"
        onClick={() => setOpen((current) => !current)}
        className="inline-flex h-10 w-10 items-center justify-center rounded-xl border border-slate-200 bg-white text-slate-500 transition hover:border-slate-300 hover:bg-slate-50 hover:text-slate-950"
      >
        <MoreHorizontal className="h-4 w-4" />
      </button>

      {open ? (
        <div
          role="menu"
          className="absolute right-0 top-12 z-20 min-w-[220px] overflow-hidden rounded-2xl border border-slate-200 bg-white p-1 shadow-lg shadow-slate-950/10"
        >
          {items.map((item, index) => (
            <Fragment key={item.label}>
              {item.destructive && index > 0 ? <div className="my-1 border-t border-slate-100" /> : null}
              <button
                type="button"
                role="menuitem"
                onClick={() => {
                  setOpen(false);
                  item.onSelect();
                }}
                className={cn(
                  "flex w-full items-center gap-2 rounded-xl px-3 py-2 text-left text-sm font-medium transition",
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

async function hydrateReferenceList<T>(
  items: unknown[],
  isHydrated: (item: unknown) => item is T,
  getById: (id: number) => Promise<T>,
) {
  const resolved = await Promise.all(
    items.map(async (item) => {
      if (isHydrated(item)) {
        return item;
      }
      if (typeof item === "number") {
        try {
          return await getById(item);
        } catch {
          return null;
        }
      }
      if (isRecord(item) && typeof item.id === "number") {
        try {
          return await getById(item.id);
        } catch {
          return null;
        }
      }
      return null;
    }),
  );

  return resolved.flatMap((item) => (item === null ? [] : [item]));
}

export const WorkerDetailsPage = () => {
  const { workerId } = useParams();
  const navigate = useNavigate();
  const location = useLocation();
  const { can } = usePermissions();

  const [worker, setWorker] = useState<Worker | null>(null);
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [visits, setVisits] = useState<MedicalVisit[]>([]);
  const [tests, setTests] = useState<WorkerTest[]>([]);
  const [aptitudeCertificates, setAptitudeCertificates] = useState<AptitudeCertificate[]>([]);
  const [orientationCertificates, setOrientationCertificates] = useState<OrientationCertificate[]>([]);
  const [prescriptions, setPrescriptions] = useState<Prescription[]>([]);
  const [companies, setCompanies] = useState<Company[]>([]);
  const [branches, setBranches] = useState<Branch[]>([]);
  const [drillingSites, setDrillingSites] = useState<DrillingSite[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notFound, setNotFound] = useState(false);
  const [notice, setNotice] = useState<NoticeState>(null);
  const [activeTab, setActiveTab] = useState<ProfileTab>("overview");
  const [technicalExpanded, setTechnicalExpanded] = useState(false);

  const [formOpen, setFormOpen] = useState(false);
  const [formState, setFormState] = useState<WorkerFormState>(DEFAULT_FORM_STATE);
  const [formError, setFormError] = useState<string | null>(null);
  const [saveLoading, setSaveLoading] = useState(false);

  const [campaignTarget, setCampaignTarget] = useState<Worker | null>(null);
  const [campaignOptions, setCampaignOptions] = useState<Campaign[]>([]);
  const [campaignLoading, setCampaignLoading] = useState(false);
  const [campaignSubmitting, setCampaignSubmitting] = useState(false);
  const [campaignError, setCampaignError] = useState<string | null>(null);
  const [selectedCampaignId, setSelectedCampaignId] = useState("");

  const [statusTarget, setStatusTarget] = useState<Worker | null>(null);
  const [statusLoading, setStatusLoading] = useState(false);

  const [deleteTarget, setDeleteTarget] = useState<Worker | null>(null);
  const [deletePassword, setDeletePassword] = useState("");
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [deleteLoading, setDeleteLoading] = useState(false);

  const numericWorkerId = workerId && /^\d+$/.test(workerId) ? Number(workerId) : null;
  const returnTo =
    isRecord(location.state) && typeof location.state.returnTo === "string"
      ? location.state.returnTo
      : "/workers";

  const loadWorkerProfile = useCallback(async () => {
    if (!numericWorkerId) {
      setNotFound(true);
      setLoading(false);
      return;
    }

    setLoading(true);
    setError(null);
    setNotFound(false);

    try {
      const [
        workerResponse,
        campaignRefs,
        testRefs,
        visitsResponse,
        aptitudeRefs,
        orientationRefs,
        prescriptionsResponse,
        companiesResponse,
        branchesResponse,
        sitesResponse,
      ] = await Promise.all([
        workersApi.get(numericWorkerId),
        workersApi.campaigns(numericWorkerId) as Promise<unknown[]>,
        workersApi.tests(numericWorkerId) as Promise<unknown[]>,
        medicalVisitsApi.listByWorker(numericWorkerId),
        aptitudeCertificatesApi.listByWorker(numericWorkerId) as Promise<unknown[]>,
        orientationsApi.listByWorker(numericWorkerId) as Promise<unknown[]>,
        prescriptionsApi.listByWorker(numericWorkerId),
        fetchAllPages(companiesApi),
        fetchAllPages(branchesApi),
        fetchAllPages(drillingSitesApi),
      ]);

      const [hydratedCampaigns, hydratedTests, hydratedAptitudes, hydratedOrientations] = await Promise.all([
        hydrateReferenceList(campaignRefs, isCampaignRecord, (id) => campaignsApi.get(id)),
        hydrateReferenceList(testRefs, isWorkerTestRecord, (id) => workerTestsApi.get(id)),
        hydrateReferenceList(aptitudeRefs, isAptitudeRecord, (id) => aptitudeCertificatesApi.get(id)),
        hydrateReferenceList(orientationRefs, isOrientationRecord, (id) => orientationsApi.get(id)),
      ]);

      const uniqueMedicalTestIds = Array.from(
        new Set(
          hydratedTests
            .map((item) => item.test_id || item.medical_test_id)
            .filter((item): item is number => typeof item === "number"),
        ),
      );

      const medicalTestEntries = await Promise.all(
        uniqueMedicalTestIds.map(async (id) => {
          try {
            const test = await medicalTestsApi.get(id);
            return [id, test.name] as const;
          } catch {
            return null;
          }
        }),
      );

      const medicalTestNames = new Map<number, string>(
        medicalTestEntries.filter((entry): entry is readonly [number, string] => entry !== null),
      );

      setWorker(workerResponse);
      setCampaigns(sortByNewest(hydratedCampaigns, (item) => item.created_at || item.start_date));
      setTests(
        sortByNewest(
          hydratedTests.map((item) => normalizeWorkerTestRecord(item, medicalTestNames)),
          (item) => item.tested_at || item.completed_at || item.created_at,
        ),
      );
      setVisits(sortByNewest(visitsResponse, (item) => item.visit_date || item.created_at));
      setAptitudeCertificates(sortByNewest(hydratedAptitudes, (item) => item.issue_date || item.created_at));
      setOrientationCertificates(sortByNewest(hydratedOrientations, (item) => item.orientation_date || item.created_at));
      setPrescriptions(sortByNewest(prescriptionsResponse, (item) => item.prescription_date || item.created_at));
      setCompanies(companiesResponse.items);
      setBranches(branchesResponse.items);
      setDrillingSites(sitesResponse.items);
    } catch (loadError) {
      const status =
        isRecord(loadError) && isRecord(loadError.response) && typeof loadError.response.status === "number"
          ? loadError.response.status
          : null;

      if (status === 404) {
        setNotFound(true);
      } else {
        setError("Les informations de ce travailleur n'ont pas pu être récupérées.");
      }
    } finally {
      setLoading(false);
    }
  }, [numericWorkerId]);

  useEffect(() => {
    void loadWorkerProfile();
  }, [loadWorkerProfile]);

  useEffect(() => {
    if (!campaignTarget) {
      return;
    }

    void (async () => {
      setCampaignLoading(true);
      setCampaignError(null);
      try {
        const response = await campaignsApi.list({
          page: 1,
          limit: 200,
          sort_by: "created_at",
          sort_order: "desc",
        });
        setCampaignOptions(response.items);
      } catch {
        setCampaignError("Les campagnes n'ont pas pu être chargées.");
      } finally {
        setCampaignLoading(false);
      }
    })();
  }, [campaignTarget]);

  const companyMap = useMemo(() => new Map(companies.map((item) => [item.id, item.name])), [companies]);
  const branchMap = useMemo(() => new Map(branches.map((item) => [item.id, item.name])), [branches]);
  const siteMap = useMemo(() => new Map(drillingSites.map((item) => [item.id, item.name])), [drillingSites]);

  const companyLabel = worker
    ? companyMap.get(worker.company_id) ||
      (typeof readMedicalFileRecord(worker)?.companyName === "string"
        ? String(readMedicalFileRecord(worker)?.companyName)
        : "Non renseigné")
    : "Non renseigné";
  const branchLabel = worker ? branchMap.get(worker.branch_id) || "Non renseigné" : "Non renseigné";
  const siteLabel = worker
    ? siteMap.get(worker.drilling_site_id || -1) ||
      (typeof readMedicalFileRecord(worker)?.siteName === "string"
        ? String(readMedicalFileRecord(worker)?.siteName)
        : "Non affecté")
    : "Non affecté";

  const latestVisit = visits[0] || null;
  const latestTest = tests[0] || null;
  const latestOrientation = orientationCertificates[0] || null;
  const latestAptitude = aptitudeCertificates[0] || null;
  const latestCertificate =
    latestOrientation && latestAptitude
      ? Date.parse(String(latestOrientation.orientation_date)) >= Date.parse(String(latestAptitude.issue_date))
        ? latestOrientation
        : latestAptitude
      : latestOrientation || latestAptitude;
  const currentCampaign =
    campaigns.find((item) => (item.status || "").toLowerCase() === "active") || campaigns[0] || null;
  const medicalFileStatus = readMedicalFileStatus(worker);
  const medicalFileRecord = readMedicalFileRecord(worker);
  const personalPhone =
    worker?.phone || (typeof medicalFileRecord?.phone === "string" ? medicalFileRecord.phone : null);

  const summaryCards = [
    {
      icon: HeartPulse,
      label: "Dernier examen",
      value: latestTest ? safeDate(latestTest.tested_at || latestTest.completed_at || latestTest.created_at) : "Non disponible",
      detail: latestTest ? latestTest.test_name || latestTest.result || "Examen médical" : "Aucun examen enregistré",
    },
    {
      icon: Stethoscope,
      label: "Dernière visite",
      value: latestVisit ? safeDate(latestVisit.visit_date) : "Non disponible",
      detail: latestVisit ? formatMedicalVisitStatus(latestVisit.status) : "Aucune visite enregistrée",
    },
    {
      icon: ClipboardList,
      label: "Visites médicales",
      value: String(visits.length),
      detail: visits.length > 0 ? `${visits.filter((item) => item.status === "validated").length} validée(s)` : "Aucune visite",
    },
    {
      icon: FileStack,
      label: "Documents médicaux",
      value: String(aptitudeCertificates.length + orientationCertificates.length),
      detail:
        aptitudeCertificates.length + orientationCertificates.length > 0
          ? `${aptitudeCertificates.length} aptitude(s), ${orientationCertificates.length} orientation(s)`
          : "Non disponible",
    },
  ];

  const medicalAlerts = [
    medicalFileStatus && getMedicalStatusTone(medicalFileStatus) === "pending"
      ? "Le dossier médical est encore en cours de confirmation."
      : null,
    tests.some((item) => item.abnormal || item.is_normal === false)
      ? "Au moins un résultat d'examen demande une attention particulière."
      : null,
    !resolveWorkerIsActive(worker) ? "Le travailleur est actuellement inactif." : null,
  ].filter((item): item is string => Boolean(item));

  const structuredMedicalItems = [
    {
      label: "N° du dossier",
      value:
        typeof medicalFileRecord?.medicalFileNumber === "string"
          ? medicalFileRecord.medicalFileNumber
          : "Non renseigné",
    },
    {
      label: "Statut du dossier",
      value: formatCertificateStatusLabel(medicalFileStatus),
    },
    {
      label: "Médecin de confirmation",
      value:
        typeof medicalFileRecord?.confirmationDoctor === "string"
          ? medicalFileRecord.confirmationDoctor
          : "Non renseigné",
    },
    {
      label: "Date de confirmation",
      value:
        typeof medicalFileRecord?.confirmationDate === "string"
          ? safeDate(medicalFileRecord.confirmationDate)
          : "Non disponible",
    },
  ];

  const canEditWorker = can("workers.update");
  const canDeleteWorker = can("workers.delete");
  const canAssignCampaign = can("medical_campaigns.assign_workers") || can("medical_campaigns.update");
  const canViewCampaign = can("medical_campaigns.view");
  const canExportOrientation = can("orientation_certificates.export_pdf") || can("orientation_certificates.view");
  const canExportAptitude = can("aptitude_certificates.export_pdf") || can("aptitude_certificates.view");
  const canExportPrescription = can("prescriptions.export_pdf") || can("prescriptions.view");

  const actionMenuItems = [
    canEditWorker && worker
      ? {
          label: resolveWorkerIsActive(worker) ? "Désactiver" : "Activer",
          icon: resolveWorkerIsActive(worker) ? UserRoundX : UserCheck,
          onSelect: () => setStatusTarget(worker),
        }
      : null,
    canDeleteWorker && worker
      ? {
          label: "Supprimer",
          icon: Trash2,
          onSelect: () => {
            setDeleteTarget(worker);
            setDeletePassword("");
            setDeleteError(null);
          },
          destructive: true,
        }
      : null,
  ].filter(
    (
      item,
    ): item is {
      label: string;
      icon: LucideIcon;
      onSelect: () => void;
      destructive?: boolean;
    } => Boolean(item),
  );

  const formBranchOptions = useMemo(
    () => [
      { value: "", label: "Sélectionner une branche" },
      ...branches
        .filter((item) => !formState.company_id || String(item.company_id) === formState.company_id)
        .map((item) => ({ value: String(item.id), label: item.name })),
    ],
    [branches, formState.company_id],
  );

  const formSiteOptions = useMemo(
    () => [
      { value: "", label: "Aucun site" },
      ...drillingSites
        .filter((item) => !formState.branch_id || String(item.branch_id) === formState.branch_id)
        .map((item) => ({ value: String(item.id), label: item.name })),
    ],
    [drillingSites, formState.branch_id],
  );

  const campaignSelectOptions = useMemo(
    () => [
      { value: "", label: campaignLoading ? "Chargement..." : "Sélectionner une campagne" },
      ...campaignOptions.map((item) => ({
        value: String(item.id),
        label: item.name || item.title || `Campagne #${item.id}`,
      })),
    ],
    [campaignLoading, campaignOptions],
  );

  const tabItems: Array<{ id: ProfileTab; label: string; count?: number }> = [
    { id: "overview", label: "Vue d’ensemble" },
    { id: "campaigns", label: "Campagnes", count: campaigns.length },
    { id: "visits", label: "Visites médicales", count: visits.length },
    { id: "tests", label: "Examens et résultats", count: tests.length },
    { id: "certificates", label: "Certificats", count: aptitudeCertificates.length + orientationCertificates.length },
    { id: "prescriptions", label: "Prescriptions", count: prescriptions.length },
  ];

  const handleSaveWorker = useCallback(async () => {
    if (!worker) {
      return;
    }

    if (!formState.first_name.trim() || !formState.last_name.trim() || !formState.employee_code.trim()) {
      setFormError("Le prénom, le nom et le matricule sont requis.");
      return;
    }
    if (!formState.company_id || !formState.branch_id) {
      setFormError("L’entreprise et la branche sont requises.");
      return;
    }

    setSaveLoading(true);
    setFormError(null);

    try {
      const updated = await workersApi.update(worker.id, { ...toWorkerPayload(formState), sync_version: worker.sync_version });
      setWorker(updated);
      setFormOpen(false);
      setNotice({ tone: "success", message: "Le profil du travailleur a été mis à jour." });
    } catch (error) {
      setFormError(savedConflictMessage(error) || "La mise à jour du travailleur a échoué.");
    } finally {
      setSaveLoading(false);
    }
  }, [formState, worker]);

  const handleAssignToCampaign = useCallback(async () => {
    if (!campaignTarget || !selectedCampaignId) {
      setCampaignError("Sélectionnez une campagne avant de continuer.");
      return;
    }

    setCampaignSubmitting(true);
    setCampaignError(null);

    try {
      await campaignsApi.addWorkers(Number(selectedCampaignId), [campaignTarget.id]);
      setCampaignTarget(null);
      setSelectedCampaignId("");
      setNotice({ tone: "success", message: "Le travailleur a été ajouté à la campagne sélectionnée." });
      await loadWorkerProfile();
    } catch {
      setCampaignError("L’ajout à la campagne a échoué.");
    } finally {
      setCampaignSubmitting(false);
    }
  }, [campaignTarget, loadWorkerProfile, selectedCampaignId]);

  const handleToggleStatus = useCallback(async () => {
    if (!statusTarget) {
      return;
    }

    const nextStatus = resolveWorkerIsActive(statusTarget) ? "inactive" : "active";
    setStatusLoading(true);

    try {
      const updated = await workersApi.update(statusTarget.id, {
        ...statusTarget,
        status: nextStatus,
      });
      setWorker(updated);
      setStatusTarget(null);
      setNotice({
        tone: "success",
        message: nextStatus === "active" ? "Le travailleur a été réactivé." : "Le travailleur a été désactivé.",
      });
    } catch (error) {
      setNotice({
        tone: "error",
        message: savedConflictMessage(error) || "La mise à jour du statut du travailleur a échoué.",
      });
    } finally {
      setStatusLoading(false);
    }
  }, [statusTarget]);

  const handleDeleteWorker = useCallback(async () => {
    if (!deleteTarget) {
      return;
    }
    if (!deletePassword.trim()) {
      setDeleteError("Le mot de passe est requis.");
      return;
    }

    setDeleteLoading(true);
    setDeleteError(null);

    try {
      await workersApi.remove(deleteTarget.id, { password: deletePassword, sync_version: deleteTarget.sync_version });
      navigate(returnTo);
    } catch (error) {
      setDeleteError(savedConflictMessage(error) || "La suppression du travailleur a échoué.");
    } finally {
      setDeleteLoading(false);
    }
  }, [deletePassword, deleteTarget, navigate, returnTo]);

  const handleDownloadOrientation = useCallback(async (certificate: OrientationCertificate) => {
    try {
      const result = await orientationsApi.downloadPdf(certificate.id, false);
      downloadBlob(result.blob, result.filename);
    } catch {
      setNotice({ tone: "error", message: "Le téléchargement du certificat d’orientation a échoué." });
    }
  }, []);

  const handleDownloadAptitude = useCallback(async (certificate: AptitudeCertificate) => {
    try {
      const result = await aptitudeCertificatesApi.downloadPdf(certificate.id);
      downloadBlob(result.blob, result.filename);
    } catch {
      setNotice({ tone: "error", message: "Le téléchargement du certificat d’aptitude a échoué." });
    }
  }, []);

  const handleDownloadPrescription = useCallback(async (prescription: Prescription) => {
    try {
      const result = await prescriptionsApi.downloadPdf(prescription.id);
      downloadBlob(result.blob, result.filename);
    } catch {
      setNotice({ tone: "error", message: "Le téléchargement de l’ordonnance a échoué." });
    }
  }, []);

  const fullName = getWorkerDisplayName(worker);
  const titleLabel = normalizeText(worker?.job_title || worker?.position) || "Non renseigné";
  const departmentLabel = normalizeText(worker?.department) || "Non renseigné";
  const age = calculateAge(worker?.birth_date);

  if (loading) {
    return <ProfileLoadingSkeleton />;
  }

  if (notFound || !worker) {
    return (
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <button
            type="button"
            onClick={() => navigate(returnTo)}
            className="inline-flex items-center gap-2 text-sm font-semibold text-slate-600 transition hover:text-slate-950"
          >
            <ArrowLeft className="h-4 w-4" />
            Retour aux travailleurs
          </button>
        </div>

        <Card className="rounded-2xl p-8">
          <EmptyState
            title="Travailleur introuvable"
            description="Ce profil n’existe pas ou n’est plus disponible."
            actionLabel="Retour aux travailleurs"
            onAction={() => navigate(returnTo)}
          />
        </Card>
      </div>
    );
  }

  if (error) {
    return (
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <button
            type="button"
            onClick={() => navigate(returnTo)}
            className="inline-flex items-center gap-2 text-sm font-semibold text-slate-600 transition hover:text-slate-950"
          >
            <ArrowLeft className="h-4 w-4" />
            Retour aux travailleurs
          </button>
        </div>

        <Card className="rounded-2xl p-8">
          <div className="mx-auto max-w-lg text-center">
            <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl border border-rose-200 bg-rose-50 text-rose-700">
              <AlertCircle className="h-5 w-5" />
            </div>
            <h2 className="mt-4 text-xl font-black text-slate-950">Impossible de charger le profil</h2>
            <p className="mt-2 text-sm text-slate-500">{error}</p>
            <div className="mt-5">
              <Button icon={RefreshCw} onClick={() => void loadWorkerProfile()}>
                Réessayer
              </Button>
            </div>
          </div>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3">
        <div className="flex flex-wrap items-center gap-2 text-sm text-slate-500">
          <Link to="/workers" className="font-semibold text-slate-600 transition hover:text-slate-950">
            Travailleurs
          </Link>
          <span>/</span>
          <span className="font-semibold text-slate-950">Profil du travailleur</span>
        </div>

        <div className="flex flex-wrap items-center justify-between gap-3">
          <button
            type="button"
            onClick={() => navigate(returnTo)}
            className="inline-flex items-center gap-2 text-sm font-semibold text-slate-600 transition hover:text-slate-950"
          >
            <ArrowLeft className="h-4 w-4" />
            Retour aux travailleurs
          </button>

          <div className="text-xs text-slate-400">ID interne #{worker.id}</div>
        </div>
      </div>

      {notice ? (
        <div
          className={cn(
            "flex items-center justify-between gap-3 rounded-2xl border px-4 py-3 text-sm",
            notice.tone === "success"
              ? "border-emerald-200 bg-emerald-50 text-emerald-800"
              : "border-rose-200 bg-rose-50 text-rose-800",
          )}
        >
          <span>{notice.message}</span>
          <button type="button" onClick={() => setNotice(null)} className="font-semibold">
            Fermer
          </button>
        </div>
      ) : null}

      <Card className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
        <div className="flex flex-col gap-6 xl:flex-row xl:items-start xl:justify-between">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-start">
            <WorkerAvatar worker={worker} />

            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <h1 className="text-2xl font-black tracking-tight text-slate-950">{fullName}</h1>
                <WorkerStatusBadge worker={worker} />
                <PresenceStatusBadge value={worker.etat_actual} />
                <MedicalStatusBadge value={worker.medical_status || medicalFileStatus} />
              </div>

              <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-2 text-sm text-slate-600">
                <span className="rounded-lg border border-slate-200 bg-slate-50 px-2.5 py-1 font-mono font-bold text-slate-800">
                  {worker.employee_code || worker.employee_number || "Non renseigné"}
                </span>
                <span className="font-semibold text-slate-900">{titleLabel}</span>
                <span>{departmentLabel}</span>
              </div>

              <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-2 text-sm text-slate-500">
                <span className="inline-flex items-center gap-2">
                  <Building2 className="h-4 w-4" />
                  {companyLabel}
                </span>
                <span>{branchLabel}</span>
                <span className="inline-flex items-center gap-2">
                  <MapPin className="h-4 w-4" />
                  {siteLabel}
                </span>
              </div>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2 xl:justify-end">
            {canEditWorker ? (
              <Button
                variant="secondary"
                icon={Pencil}
                onClick={() => {
                  setFormState(buildWorkerFormState(worker));
                  setFormError(null);
                  setFormOpen(true);
                }}
              >
                Modifier
              </Button>
            ) : null}

            {canAssignCampaign ? (
              <Button
                icon={Plus}
                onClick={() => {
                  setCampaignTarget(worker);
                  setSelectedCampaignId("");
                  setCampaignError(null);
                }}
              >
                Ajouter à une campagne
              </Button>
            ) : null}

            <WorkerActionsMenu items={actionMenuItems} />
          </div>
        </div>
      </Card>

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        {summaryCards.map((item) => (
          <ProfileSummaryCard
            key={item.label}
            icon={item.icon}
            label={item.label}
            value={item.value}
            detail={item.detail}
          />
        ))}
      </div>

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1.7fr)_minmax(320px,1fr)]">
        <div className="space-y-6">
          <Card className="rounded-2xl p-2">
            <div role="tablist" aria-label="Sections du profil du travailleur" className="flex flex-wrap gap-2">
              {tabItems.map((tab) => {
                const selected = activeTab === tab.id;
                return (
                  <button
                    key={tab.id}
                    type="button"
                    role="tab"
                    aria-selected={selected}
                    className={cn(
                      "rounded-xl px-4 py-2 text-sm font-semibold transition",
                      selected
                        ? "bg-[#0085A3] text-white shadow-md shadow-[#0085A3]/20"
                        : "text-slate-600 hover:bg-slate-50 hover:text-slate-950",
                    )}
                    onClick={() => setActiveTab(tab.id)}
                  >
                    {tab.label}
                    {typeof tab.count === "number" ? ` (${tab.count})` : ""}
                  </button>
                );
              })}
            </div>
          </Card>

          <div role="tabpanel" className="space-y-6">
            {activeTab === "overview" ? (
              <Card className="rounded-2xl p-6">
                <div className="flex items-start gap-3">
                  <div className="rounded-2xl border border-slate-200 bg-slate-50 p-3 text-slate-600">
                    <Activity className="h-5 w-5" />
                  </div>
                  <div>
                    <h2 className="text-lg font-black text-slate-950">Vue d’ensemble médicale</h2>
                    <p className="mt-1 text-sm text-slate-500">
                      Dernière activité médicale, campagne courante et points de vigilance disponibles.
                    </p>
                  </div>
                </div>

                <div className="mt-5 grid gap-4 md:grid-cols-2">
                  <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                    <p className="text-[11px] font-black uppercase tracking-[0.14em] text-slate-400">Dernière visite</p>
                    <p className="mt-2 text-base font-bold text-slate-950">
                      {latestVisit ? safeDate(latestVisit.visit_date) : "Non disponible"}
                    </p>
                    <p className="mt-1 text-sm text-slate-500">
                      {latestVisit ? formatMedicalVisitStatus(latestVisit.status) : "Aucune visite enregistrée"}
                    </p>
                  </div>

                  <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                    <p className="text-[11px] font-black uppercase tracking-[0.14em] text-slate-400">Dernier examen</p>
                    <p className="mt-2 text-base font-bold text-slate-950">
                      {latestTest ? latestTest.test_name || "Examen médical" : "Non disponible"}
                    </p>
                    <p className="mt-1 text-sm text-slate-500">
                      {latestTest ? formatTestStatusLabel(latestTest) : "Aucun examen enregistré"}
                    </p>
                  </div>

                  <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                    <p className="text-[11px] font-black uppercase tracking-[0.14em] text-slate-400">Dernier certificat</p>
                    <p className="mt-2 text-base font-bold text-slate-950">
                      {latestCertificate
                        ? "orientation_number" in latestCertificate
                          ? latestCertificate.orientation_number
                          : latestCertificate.certificate_number
                        : "Non disponible"}
                    </p>
                    <p className="mt-1 text-sm text-slate-500">
                      {latestCertificate
                        ? "orientation_number" in latestCertificate
                          ? formatCertificateStatusLabel(latestCertificate.status)
                          : `${formatAptitudeLabel(latestCertificate.aptitude)} • ${formatCertificateStatusLabel(latestCertificate.status)}`
                        : "Aucun certificat disponible"}
                    </p>
                  </div>

                  <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                    <p className="text-[11px] font-black uppercase tracking-[0.14em] text-slate-400">Campagne en cours</p>
                    <p className="mt-2 text-base font-bold text-slate-950">
                      {currentCampaign ? currentCampaign.name || currentCampaign.title || `Campagne #${currentCampaign.id}` : "Non disponible"}
                    </p>
                    <p className="mt-1 text-sm text-slate-500">
                      {currentCampaign ? safeDateRange(currentCampaign.start_date, currentCampaign.end_date) : "Aucune campagne active"}
                    </p>
                  </div>
                </div>

                <div className="mt-5 space-y-3">
                  <h3 className="text-sm font-black uppercase tracking-[0.14em] text-slate-400">Alertes</h3>
                  {medicalAlerts.length > 0 ? (
                    medicalAlerts.map((alert) => (
                      <div
                        key={alert}
                        className="flex items-start gap-3 rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900"
                      >
                        <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
                        <span>{alert}</span>
                      </div>
                    ))
                  ) : (
                    <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-500">
                      Aucun signal d’attention exploitable n’est dérivable des données actuellement disponibles.
                    </div>
                  )}
                </div>

                {!hasStructuredMedicalFile(worker) ? (
                  <div className="mt-5 rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-500">
                    Aucune information médicale structurée n’est disponible pour ce travailleur.
                  </div>
                ) : null}
              </Card>
            ) : null}

            {activeTab === "campaigns" ? (
              <Card className="rounded-2xl p-0">
                <div className="border-b border-slate-200 px-6 py-5">
                  <div className="flex items-center gap-3">
                    <div className="rounded-2xl border border-slate-200 bg-slate-50 p-3 text-slate-600">
                      <Users className="h-5 w-5" />
                    </div>
                    <div>
                      <h2 className="text-lg font-black text-slate-950">Campagnes</h2>
                      <p className="text-sm text-slate-500">Campagnes rattachées à ce travailleur.</p>
                    </div>
                  </div>
                </div>

                <div className="p-6">
                  {campaigns.length === 0 ? (
                    <SectionEmptyState
                      title="Aucune campagne"
                      description="Ce travailleur n’est rattaché à aucune campagne pour le moment."
                    />
                  ) : (
                    <div className="overflow-x-auto">
                      <table className="min-w-full divide-y divide-slate-200">
                        <thead className="bg-slate-50">
                          <tr>
                            <th className="px-4 py-3 text-left text-xs font-black uppercase tracking-[0.16em] text-slate-500">Campagne</th>
                            <th className="px-4 py-3 text-left text-xs font-black uppercase tracking-[0.16em] text-slate-500">Statut</th>
                            <th className="px-4 py-3 text-left text-xs font-black uppercase tracking-[0.16em] text-slate-500">Travailleurs</th>
                            <th className="px-4 py-3 text-left text-xs font-black uppercase tracking-[0.16em] text-slate-500">Période</th>
                            <th className="px-4 py-3 text-right text-xs font-black uppercase tracking-[0.16em] text-slate-500">Actions</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-100 bg-white">
                          {campaigns.map((campaign) => (
                            <tr key={campaign.id} className="align-top">
                              <td className="px-4 py-4">
                                <p className="font-semibold text-slate-950">
                                  {campaign.name || campaign.title || `Campagne #${campaign.id}`}
                                </p>
                                <p className="mt-1 text-xs text-slate-500">ID interne #{campaign.id}</p>
                              </td>
                              <td className="px-4 py-4">
                                <Badge tone={getCampaignStatusTone(campaign.status)}>
                                  {formatCampaignStatusLabel(campaign.status)}
                                </Badge>
                              </td>
                              <td className="px-4 py-4 text-sm text-slate-700">
                                {typeof campaign.worker_count === "number" ? campaign.worker_count : "Non disponible"}
                              </td>
                              <td className="px-4 py-4 text-sm text-slate-700">
                                {safeDateRange(campaign.start_date, campaign.end_date)}
                              </td>
                              <td className="px-4 py-4 text-right">
                                {canViewCampaign ? (
                                  <Link
                                    to={`/campaigns/${campaign.id}`}
                                    className="inline-flex items-center gap-2 rounded-xl border border-slate-200 px-3 py-2 text-sm font-semibold text-slate-700 transition hover:bg-slate-50 hover:text-slate-950"
                                  >
                                    <Eye className="h-4 w-4" />
                                    Voir la campagne
                                  </Link>
                                ) : (
                                  <span className="text-sm text-slate-400">—</span>
                                )}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>
              </Card>
            ) : null}

            {activeTab === "visits" ? (
              <Card className="rounded-2xl p-0">
                <div className="border-b border-slate-200 px-6 py-5">
                  <div className="flex items-center gap-3">
                    <div className="rounded-2xl border border-slate-200 bg-slate-50 p-3 text-slate-600">
                      <Stethoscope className="h-5 w-5" />
                    </div>
                    <div>
                      <h2 className="text-lg font-black text-slate-950">Visites médicales</h2>
                      <p className="text-sm text-slate-500">Historique des visites médicales du travailleur.</p>
                    </div>
                  </div>
                </div>

                <div className="p-6">
                  {visits.length === 0 ? (
                    <SectionEmptyState
                      title="Aucune visite médicale"
                      description="Aucune visite médicale n’est encore enregistrée pour ce travailleur."
                    />
                  ) : (
                    <div className="overflow-x-auto">
                      <table className="min-w-full divide-y divide-slate-200">
                        <thead className="bg-slate-50">
                          <tr>
                            <th className="px-4 py-3 text-left text-xs font-black uppercase tracking-[0.16em] text-slate-500">Date</th>
                            <th className="px-4 py-3 text-left text-xs font-black uppercase tracking-[0.16em] text-slate-500">Site</th>
                            <th className="px-4 py-3 text-left text-xs font-black uppercase tracking-[0.16em] text-slate-500">Statut</th>
                            <th className="px-4 py-3 text-left text-xs font-black uppercase tracking-[0.16em] text-slate-500">Validation</th>
                            <th className="px-4 py-3 text-left text-xs font-black uppercase tracking-[0.16em] text-slate-500">Notes</th>
                            <th className="px-4 py-3 text-right text-xs font-black uppercase tracking-[0.16em] text-slate-500">Actions</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-100 bg-white">
                          {visits.map((visit) => (
                            <tr key={visit.id} className="align-top">
                              <td className="px-4 py-4">
                                <p className="font-semibold text-slate-950">{safeDate(visit.visit_date)}</p>
                                <p className="mt-1 text-xs text-slate-500">{visit.uuid ? `UUID ${visit.uuid}` : `ID #${visit.id}`}</p>
                              </td>
                              <td className="px-4 py-4 text-sm text-slate-700">{visit.site_name || siteLabel || "Non renseigné"}</td>
                              <td className="px-4 py-4">
                                <Badge tone={getMedicalVisitTone(visit.status)}>
                                  {formatMedicalVisitStatus(visit.status)}
                                </Badge>
                              </td>
                              <td className="px-4 py-4 text-sm text-slate-700">{safeDate(visit.validated_at)}</td>
                              <td className="px-4 py-4 text-sm text-slate-700">{visit.doctor_notes || "Non renseigné"}</td>
                              <td className="px-4 py-4 text-right">
                                <button
                                  type="button"
                                  onClick={() =>
                                    void workersApi
                                      .downloadMedicalVisitPdf(worker.id, visit.campaign_id ?? undefined, visit.id)
                                      .then((result) => downloadBlob(result.blob, result.filename))
                                      .catch(() => {
                                        setNotice({ tone: "error", message: "Le téléchargement de la fiche de visite a échoué." });
                                      })
                                  }
                                  className="inline-flex items-center gap-2 rounded-xl border border-slate-200 px-3 py-2 text-sm font-semibold text-slate-700 transition hover:bg-slate-50 hover:text-slate-950"
                                >
                                  <Eye className="h-4 w-4" />
                                  Télécharger
                                </button>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>
              </Card>
            ) : null}

            {activeTab === "tests" ? (
              <Card className="rounded-2xl p-0">
                <div className="border-b border-slate-200 px-6 py-5">
                  <div className="flex items-center gap-3">
                    <div className="rounded-2xl border border-slate-200 bg-slate-50 p-3 text-slate-600">
                      <HeartPulse className="h-5 w-5" />
                    </div>
                    <div>
                      <h2 className="text-lg font-black text-slate-950">Examens et résultats</h2>
                      <p className="text-sm text-slate-500">Résultats d’examens médicaux déjà liés à ce travailleur.</p>
                    </div>
                  </div>
                </div>

                <div className="p-6">
                  {tests.length === 0 ? (
                    <SectionEmptyState
                      title="Aucun résultat"
                      description="Aucun test ou résultat médical n’est encore rattaché à ce travailleur."
                    />
                  ) : (
                    <div className="overflow-x-auto">
                      <table className="min-w-full divide-y divide-slate-200">
                        <thead className="bg-slate-50">
                          <tr>
                            <th className="px-4 py-3 text-left text-xs font-black uppercase tracking-[0.16em] text-slate-500">Examen</th>
                            <th className="px-4 py-3 text-left text-xs font-black uppercase tracking-[0.16em] text-slate-500">Résultat</th>
                            <th className="px-4 py-3 text-left text-xs font-black uppercase tracking-[0.16em] text-slate-500">Statut</th>
                            <th className="px-4 py-3 text-left text-xs font-black uppercase tracking-[0.16em] text-slate-500">Date</th>
                            <th className="px-4 py-3 text-right text-xs font-black uppercase tracking-[0.16em] text-slate-500">Actions</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-100 bg-white">
                          {tests.map((test) => (
                            <tr key={test.id} className="align-top">
                              <td className="px-4 py-4">
                                <p className="font-semibold text-slate-950">{test.test_name || `Examen #${test.id}`}</p>
                                <p className="mt-1 text-xs text-slate-500">ID interne #{test.id}</p>
                              </td>
                              <td className="px-4 py-4 text-sm text-slate-700">{test.result || "En attente"}</td>
                              <td className="px-4 py-4">
                                <Badge tone={getTestTone(test)}>{formatTestStatusLabel(test)}</Badge>
                              </td>
                              <td className="px-4 py-4 text-sm text-slate-700">
                                {safeDate(test.tested_at || test.completed_at || test.created_at)}
                              </td>
                              <td className="px-4 py-4 text-right text-sm text-slate-400">—</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>
              </Card>
            ) : null}

            {activeTab === "certificates" ? (
              <div className="space-y-6">
                <Card className="rounded-2xl p-0">
                  <div className="border-b border-slate-200 px-6 py-5">
                    <div className="flex items-center gap-3">
                      <div className="rounded-2xl border border-slate-200 bg-slate-50 p-3 text-slate-600">
                        <FileHeart className="h-5 w-5" />
                      </div>
                      <div>
                        <h2 className="text-lg font-black text-slate-950">Certificats d’aptitude</h2>
                        <p className="text-sm text-slate-500">Certificats d’aptitude disponibles pour ce travailleur.</p>
                      </div>
                    </div>
                  </div>

                  <div className="p-6">
                    {aptitudeCertificates.length === 0 ? (
                      <SectionEmptyState
                        title="Aucun certificat d’aptitude"
                        description="Aucun certificat d’aptitude n’est disponible pour ce travailleur."
                      />
                    ) : (
                      <div className="overflow-x-auto">
                        <table className="min-w-full divide-y divide-slate-200">
                          <thead className="bg-slate-50">
                            <tr>
                              <th className="px-4 py-3 text-left text-xs font-black uppercase tracking-[0.16em] text-slate-500">N° du certificat</th>
                              <th className="px-4 py-3 text-left text-xs font-black uppercase tracking-[0.16em] text-slate-500">Date</th>
                              <th className="px-4 py-3 text-left text-xs font-black uppercase tracking-[0.16em] text-slate-500">Aptitude</th>
                              <th className="px-4 py-3 text-left text-xs font-black uppercase tracking-[0.16em] text-slate-500">Statut</th>
                              <th className="px-4 py-3 text-left text-xs font-black uppercase tracking-[0.16em] text-slate-500">Médecin</th>
                              <th className="px-4 py-3 text-right text-xs font-black uppercase tracking-[0.16em] text-slate-500">Actions</th>
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-slate-100 bg-white">
                            {aptitudeCertificates.map((certificate) => (
                              <tr key={certificate.id} className="align-top">
                                <td className="px-4 py-4">
                                  <p className="font-semibold text-slate-950">{certificate.certificate_number || `Certificat #${certificate.id}`}</p>
                                  <p className="mt-1 text-xs text-slate-500">ID interne #{certificate.id}</p>
                                </td>
                                <td className="px-4 py-4 text-sm text-slate-700">{safeDate(certificate.issue_date)}</td>
                                <td className="px-4 py-4 text-sm text-slate-700">{formatAptitudeLabel(certificate.aptitude)}</td>
                                <td className="px-4 py-4">
                                  <Badge tone={getCertificateTone(certificate.status)}>
                                    {formatCertificateStatusLabel(certificate.status)}
                                  </Badge>
                                </td>
                                <td className="px-4 py-4 text-sm text-slate-700">
                                  {certificate.doctor_name || certificate.validatedDoctorName || "Non renseigné"}
                                </td>
                                <td className="px-4 py-4 text-right">
                                  {canExportAptitude ? (
                                    <button
                                      type="button"
                                      onClick={() => void handleDownloadAptitude(certificate)}
                                      className="inline-flex items-center gap-2 rounded-xl border border-slate-200 px-3 py-2 text-sm font-semibold text-slate-700 transition hover:bg-slate-50 hover:text-slate-950"
                                    >
                                      <Eye className="h-4 w-4" />
                                      Télécharger
                                    </button>
                                  ) : (
                                    <span className="text-sm text-slate-400">—</span>
                                  )}
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    )}
                  </div>
                </Card>

                <Card className="rounded-2xl p-0">
                  <div className="border-b border-slate-200 px-6 py-5">
                    <div className="flex items-center gap-3">
                      <div className="rounded-2xl border border-slate-200 bg-slate-50 p-3 text-slate-600">
                        <FileStack className="h-5 w-5" />
                      </div>
                      <div>
                        <h2 className="text-lg font-black text-slate-950">Certificats d’orientation</h2>
                        <p className="text-sm text-slate-500">Orientations médicales rattachées à ce travailleur.</p>
                      </div>
                    </div>
                  </div>

                  <div className="p-6">
                    {orientationCertificates.length === 0 ? (
                      <SectionEmptyState
                        title="Aucun certificat d’orientation"
                        description="Aucune orientation médicale n’est encore disponible pour ce travailleur."
                      />
                    ) : (
                      <div className="overflow-x-auto">
                        <table className="min-w-full divide-y divide-slate-200">
                          <thead className="bg-slate-50">
                            <tr>
                              <th className="px-4 py-3 text-left text-xs font-black uppercase tracking-[0.16em] text-slate-500">N° du certificat</th>
                              <th className="px-4 py-3 text-left text-xs font-black uppercase tracking-[0.16em] text-slate-500">Date</th>
                              <th className="px-4 py-3 text-left text-xs font-black uppercase tracking-[0.16em] text-slate-500">Type</th>
                              <th className="px-4 py-3 text-left text-xs font-black uppercase tracking-[0.16em] text-slate-500">Statut</th>
                              <th className="px-4 py-3 text-left text-xs font-black uppercase tracking-[0.16em] text-slate-500">Médecin</th>
                              <th className="px-4 py-3 text-right text-xs font-black uppercase tracking-[0.16em] text-slate-500">Actions</th>
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-slate-100 bg-white">
                            {orientationCertificates.map((certificate) => (
                              <tr key={certificate.id} className="align-top">
                                <td className="px-4 py-4">
                                  <p className="font-semibold text-slate-950">{certificate.orientation_number || `Orientation #${certificate.id}`}</p>
                                  <p className="mt-1 text-xs text-slate-500">ID interne #{certificate.id}</p>
                                </td>
                                <td className="px-4 py-4 text-sm text-slate-700">{safeDate(certificate.orientation_date)}</td>
                                <td className="px-4 py-4 text-sm text-slate-700">{formatOrientationTypeLabel(certificate)}</td>
                                <td className="px-4 py-4">
                                  <Badge tone={getCertificateTone(certificate.status)}>
                                    {formatCertificateStatusLabel(certificate.status)}
                                  </Badge>
                                </td>
                                <td className="px-4 py-4 text-sm text-slate-700">{certificate.doctor_name || "Non renseigné"}</td>
                                <td className="px-4 py-4 text-right">
                                  {canExportOrientation ? (
                                    <button
                                      type="button"
                                      onClick={() => void handleDownloadOrientation(certificate)}
                                      className="inline-flex items-center gap-2 rounded-xl border border-slate-200 px-3 py-2 text-sm font-semibold text-slate-700 transition hover:bg-slate-50 hover:text-slate-950"
                                    >
                                      <Eye className="h-4 w-4" />
                                      Télécharger
                                    </button>
                                  ) : (
                                    <span className="text-sm text-slate-400">—</span>
                                  )}
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    )}
                  </div>
                </Card>
              </div>
            ) : null}

            {activeTab === "prescriptions" ? (
              <Card className="rounded-2xl p-0">
                <div className="border-b border-slate-200 px-6 py-5">
                  <div className="flex items-center gap-3">
                    <div className="rounded-2xl border border-slate-200 bg-slate-50 p-3 text-slate-600">
                      <Pill className="h-5 w-5" />
                    </div>
                    <div>
                      <h2 className="text-lg font-black text-slate-950">Prescriptions</h2>
                      <p className="text-sm text-slate-500">Ordonnances disponibles pour ce travailleur.</p>
                    </div>
                  </div>
                </div>

                <div className="p-6">
                  {prescriptions.length === 0 ? (
                    <SectionEmptyState
                      title="Aucune prescription"
                      description="Aucune prescription n’est actuellement disponible pour ce travailleur."
                    />
                  ) : (
                    <div className="overflow-x-auto">
                      <table className="min-w-full divide-y divide-slate-200">
                        <thead className="bg-slate-50">
                          <tr>
                            <th className="px-4 py-3 text-left text-xs font-black uppercase tracking-[0.16em] text-slate-500">Date</th>
                            <th className="px-4 py-3 text-left text-xs font-black uppercase tracking-[0.16em] text-slate-500">Prescription</th>
                            <th className="px-4 py-3 text-left text-xs font-black uppercase tracking-[0.16em] text-slate-500">Statut</th>
                            <th className="px-4 py-3 text-left text-xs font-black uppercase tracking-[0.16em] text-slate-500">Médecin</th>
                            <th className="px-4 py-3 text-right text-xs font-black uppercase tracking-[0.16em] text-slate-500">Actions</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-100 bg-white">
                          {prescriptions.map((prescription) => (
                            <tr key={prescription.id} className="align-top">
                              <td className="px-4 py-4 text-sm text-slate-700">{safeDate(prescription.prescription_date)}</td>
                              <td className="px-4 py-4">
                                <p className="font-semibold text-slate-950">{prescription.prescription_number || `Ordonnance #${prescription.id}`}</p>
                                <p className="mt-1 text-xs text-slate-500">
                                  {prescription.items.length > 0 ? `${prescription.items.length} médicament(s)` : "Aucun détail d’ordonnance"}
                                </p>
                              </td>
                              <td className="px-4 py-4">
                                <Badge tone={getCertificateTone(prescription.status)}>
                                  {formatCertificateStatusLabel(prescription.status)}
                                </Badge>
                              </td>
                              <td className="px-4 py-4 text-sm text-slate-700">{prescription.doctor_name || "Non renseigné"}</td>
                              <td className="px-4 py-4 text-right">
                                {canExportPrescription ? (
                                  <button
                                    type="button"
                                    onClick={() => void handleDownloadPrescription(prescription)}
                                    className="inline-flex items-center gap-2 rounded-xl border border-slate-200 px-3 py-2 text-sm font-semibold text-slate-700 transition hover:bg-slate-50 hover:text-slate-950"
                                  >
                                    <Eye className="h-4 w-4" />
                                    Télécharger
                                  </button>
                                ) : (
                                  <span className="text-sm text-slate-400">—</span>
                                )}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>
              </Card>
            ) : null}
          </div>
        </div>

        <div className="space-y-6">
          <Card className="rounded-2xl p-6">
            <div className="flex items-start gap-3">
              <div className="rounded-2xl border border-slate-200 bg-slate-50 p-3 text-slate-600">
                <Users className="h-5 w-5" />
              </div>
              <div>
                <h2 className="text-lg font-black text-slate-950">Informations personnelles</h2>
                <p className="mt-1 text-sm text-slate-500">Identité et coordonnées du travailleur.</p>
              </div>
            </div>

            <div className="mt-5">
              <DetailRow label="Nom complet" value={fullName} />
              <DetailRow label="Matricule" value={worker.employee_code || worker.employee_number || "Non renseigné"} mono />
              <DetailRow label="N° d’identification nationale" value={worker.national_id || "Non renseigné"} />
              <DetailRow label="Genre" value={formatGenderLabel(worker.gender)} />
              <DetailRow label="Date de naissance" value={safeDate(worker.birth_date)} />
              <DetailRow label="Âge" value={age !== null ? `${age} ans` : "Non renseigné"} />
              <DetailRow label="Wilaya de naissance" value={worker.birth_wilaya || "Non renseigné"} />
              <DetailRow label="Situation familiale" value={humanizeToken(worker.marital_status)} />
              <DetailRow label="Groupe sanguin" value={worker.blood_group || "Non renseigné"} />
              <DetailRow label="Téléphone" value={personalPhone || "Non renseigné"} />
              <DetailRow label="Téléphone d’urgence" value={worker.emergency_phone || "Non renseigné"} />
              <DetailRow label="Adresse" value={worker.address || "Non renseigné"} />
            </div>
          </Card>

          <Card className="rounded-2xl p-6">
            <div className="flex items-start gap-3">
              <div className="rounded-2xl border border-slate-200 bg-slate-50 p-3 text-slate-600">
                <Building2 className="h-5 w-5" />
              </div>
              <div>
                <h2 className="text-lg font-black text-slate-950">Informations professionnelles</h2>
                <p className="mt-1 text-sm text-slate-500">Données d’emploi et d’affectation.</p>
              </div>
            </div>

            <div className="mt-5">
              <DetailRow label="Fonction" value={titleLabel} />
              <DetailRow label="Département" value={departmentLabel} />
              <DetailRow label="Entreprise" value={companyLabel} />
              <DetailRow label="Branche" value={branchLabel} />
              <DetailRow label="Site de forage" value={siteLabel} />
              <DetailRow label="Date d’embauche" value={safeDate(worker.hire_date)} />
              <DetailRow label="État actuel" value={formatPresenceLabel(worker.etat_actual)} />
            </div>
          </Card>

          <Card className="rounded-2xl p-6">
            <div className="flex items-start gap-3">
              <div className="rounded-2xl border border-slate-200 bg-slate-50 p-3 text-slate-600">
                <FileHeart className="h-5 w-5" />
              </div>
              <div>
                <h2 className="text-lg font-black text-slate-950">Dossier médical</h2>
                <p className="mt-1 text-sm text-slate-500">Synthèse des éléments structurés disponibles.</p>
              </div>
            </div>

            <div className="mt-5">
              <DetailRow label="Statut médical" value={formatMedicalStatusLabel(worker.medical_status || medicalFileStatus)} />
              <DetailRow label="Dernier examen" value={latestTest ? safeDate(latestTest.tested_at || latestTest.completed_at || latestTest.created_at) : "Non disponible"} />
              <DetailRow label="Dernière visite" value={latestVisit ? safeDate(latestVisit.visit_date) : "Non disponible"} />
              <DetailRow label="Données structurées" value={hasStructuredMedicalFile(worker) ? "Disponibles" : "Non disponibles"} />
            </div>

            {hasStructuredMedicalFile(worker) ? (
              <div className="mt-5 space-y-3 rounded-2xl border border-slate-200 bg-slate-50 p-4">
                {structuredMedicalItems.map((item) => (
                  <div key={item.label} className="flex items-start justify-between gap-4">
                    <span className="text-sm text-slate-500">{item.label}</span>
                    <span className="max-w-[60%] text-right text-sm font-semibold text-slate-900">{item.value}</span>
                  </div>
                ))}
              </div>
            ) : null}
          </Card>

          <Card className="rounded-2xl p-6">
            <button
              type="button"
              onClick={() => setTechnicalExpanded((current) => !current)}
              className="flex w-full items-center justify-between gap-3 text-left"
            >
              <div>
                <h2 className="text-base font-black text-slate-950">Synchronisation</h2>
                <p className="mt-1 text-sm text-slate-500">
                  {`Synchronisation : ${formatSynchronizationLabel(worker.central_sync_status)}`}
                </p>
              </div>
              <ChevronDown className={cn("h-4 w-4 text-slate-400 transition", technicalExpanded ? "rotate-180" : "")} />
            </button>

            {technicalExpanded ? (
              <div className="mt-4 space-y-3 rounded-2xl border border-slate-200 bg-slate-50 p-4">
                <div className="flex items-start justify-between gap-4">
                  <span className="text-sm text-slate-500">Statut technique</span>
                  <span className="max-w-[60%] text-right text-sm font-semibold text-slate-900">
                    {formatSynchronizationLabel(worker.central_sync_status)}
                  </span>
                </div>
                <div className="flex items-start justify-between gap-4">
                  <span className="text-sm text-slate-500">Dernière session mission</span>
                  <span className="max-w-[60%] text-right text-sm font-semibold text-slate-900">
                    {worker.last_modified_mission_session_uuid ? String(worker.last_modified_mission_session_uuid) : "Non disponible"}
                  </span>
                </div>
                <div className="flex items-start justify-between gap-4">
                  <span className="text-sm text-slate-500">Dernière mise à jour</span>
                  <span className="max-w-[60%] text-right text-sm font-semibold text-slate-900">
                    {safeDateTime(worker.updated_at)}
                  </span>
                </div>
              </div>
            ) : null}
          </Card>
        </div>
      </div>

      <Modal
        open={formOpen}
        title="Modifier le travailleur"
        onClose={() => {
          setFormOpen(false);
          setFormError(null);
        }}
      >
        <div className="space-y-5">
          {formError ? (
            <div className="rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-800">
              {formError}
            </div>
          ) : null}

          <div className="grid gap-4 md:grid-cols-2">
            <Input label="Prénom" value={formState.first_name} onChange={(event) => setFormState((current) => ({ ...current, first_name: event.target.value }))} />
            <Input label="Nom" value={formState.last_name} onChange={(event) => setFormState((current) => ({ ...current, last_name: event.target.value }))} />
            <Input label="Matricule" value={formState.employee_code} onChange={(event) => setFormState((current) => ({ ...current, employee_code: event.target.value }))} />
            <Input label="N° d’identification" value={formState.national_id} onChange={(event) => setFormState((current) => ({ ...current, national_id: event.target.value }))} />
            <Input label="Téléphone" value={formState.phone} onChange={(event) => setFormState((current) => ({ ...current, phone: event.target.value }))} />
            <Input label="Statut médical" value={formState.medical_status} onChange={(event) => setFormState((current) => ({ ...current, medical_status: event.target.value }))} />
            <Select
              label="Entreprise"
              options={[
                { value: "", label: "Sélectionner une entreprise" },
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
            <Select
              label="Branche"
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
            <Input label="Fonction" value={formState.position} onChange={(event) => setFormState((current) => ({ ...current, position: event.target.value }))} />
            <Input label="Département" value={formState.department} onChange={(event) => setFormState((current) => ({ ...current, department: event.target.value }))} />
            <Select label="État actuel" options={PRESENCE_OPTIONS} value={formState.etat_actual} onChange={(event) => setFormState((current) => ({ ...current, etat_actual: event.target.value }))} />
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
              Enregistrer les modifications
            </Button>
          </div>
        </div>
      </Modal>

      <Modal
        open={Boolean(campaignTarget)}
        title="Ajouter à une campagne"
        onClose={() => {
          setCampaignTarget(null);
          setSelectedCampaignId("");
          setCampaignError(null);
        }}
      >
        <div className="space-y-5">
          {campaignError ? (
            <div className="rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-800">
              {campaignError}
            </div>
          ) : null}

          <p className="text-sm text-slate-700">
            Sélectionnez une campagne existante pour y rattacher{" "}
            <span className="font-bold text-slate-950">{campaignTarget ? getWorkerDisplayName(campaignTarget) : "ce travailleur"}</span>.
          </p>

          <Select label="Campagne" options={campaignSelectOptions} value={selectedCampaignId} onChange={(event) => setSelectedCampaignId(event.target.value)} />

          {campaignLoading ? (
            <div className="flex items-center gap-2 rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-600">
              <RefreshCw className="h-4 w-4 animate-spin" />
              <span>Chargement des campagnes...</span>
            </div>
          ) : null}

          <div className="flex justify-end gap-2">
            <Button variant="secondary" onClick={() => setCampaignTarget(null)}>
              Annuler
            </Button>
            <Button loading={campaignSubmitting} onClick={() => void handleAssignToCampaign()}>
              Ajouter à la campagne
            </Button>
          </div>
        </div>
      </Modal>

      <Modal
        open={Boolean(statusTarget)}
        title={resolveWorkerIsActive(statusTarget) ? "Désactiver le travailleur" : "Activer le travailleur"}
        onClose={() => setStatusTarget(null)}
      >
        <div className="space-y-5">
          <div className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
            {resolveWorkerIsActive(statusTarget)
              ? "La désactivation rendra ce travailleur inactif dans le registre, sans supprimer son historique médical."
              : "La réactivation remettra ce travailleur à disposition dans les listes et les suivis."}
          </div>

          <div className="flex justify-end gap-2">
            <Button variant="secondary" onClick={() => setStatusTarget(null)}>
              Annuler
            </Button>
            <Button loading={statusLoading} onClick={() => void handleToggleStatus()}>
              {resolveWorkerIsActive(statusTarget) ? "Confirmer la désactivation" : "Confirmer l’activation"}
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
          <div className="rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-900">
            Cette suppression désactive également le travailleur et retire sa fiche des listes actives. Son historique médical doit rester vérifié avant toute action complémentaire.
          </div>

          <p className="text-sm text-slate-700">
            Saisissez votre mot de passe pour confirmer la suppression de{" "}
            <span className="font-bold text-slate-950">{deleteTarget ? getWorkerDisplayName(deleteTarget) : "ce travailleur"}</span>.
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
            <Button variant="secondary" onClick={() => setDeleteTarget(null)}>
              Annuler
            </Button>
            <Button variant="danger" loading={deleteLoading} onClick={() => void handleDeleteWorker()}>
              Supprimer
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
};
