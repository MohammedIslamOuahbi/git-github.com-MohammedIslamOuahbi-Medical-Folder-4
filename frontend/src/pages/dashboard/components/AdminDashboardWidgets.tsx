import { useMemo, useState } from "react";
import {
  Activity,
  AlertTriangle,
  ArrowUpRight,
  Building,
  Building2,
  CheckCircle,
  ChevronDown,
  ChevronUp,
  Clock,
  Copy,
  ClipboardList,
  Database,
  FileText,
  FileBarChart2,
  FlaskConical,
  FolderClock,
  HardHat,
  LockKeyhole,
  LogIn,
  Download,
  Lock,
  MapPin,
  Pencil,
  PlusCircle,
  RefreshCw,
  Settings,
  ShieldCheck,
  Stethoscope,
  TestTube2,
  Trash2,
  Upload,
  User,
  UserRoundCog,
  Users,
} from "lucide-react";
import { Badge } from "@/components/common/Badge";
import { Card } from "@/components/common/Card";
import { Input } from "@/components/common/Input";
import { Select } from "@/components/common/Select";
import type { AuthUser } from "@/types/auth";
import type { Role } from "@/types/common";
import type {
  AdminDashboardData,
  DashboardAuditItem,
  DashboardCampaignItem,
  DashboardImportItem,
} from "@/types/dashboard";
import { formatDisplayDateTime } from "@/utils/date";
import { formatDateTime, formatNumber } from "@/utils/format";
import { hasPermission } from "@/utils/permissions";

export const buildMetricCards = (data: AdminDashboardData) => [
  {
    key: "total_users",
    label: "Total Users",
    value: data.total_users,
    icon: Users,
  },
  {
    key: "total_doctors",
    label: "Doctors",
    value: data.total_doctors,
    icon: Stethoscope,
  },
  {
    key: "total_assistants",
    label: "Assistants",
    value: data.total_assistants,
    icon: UserRoundCog,
  },
  {
    key: "total_companies",
    label: "Entreprises",
    value: data.total_companies,
    icon: Building2,
  },
  {
    key: "total_branches",
    label: "Filiales",
    value: data.total_branches,
    icon: Building,
  },
  {
    key: "total_drilling_sites",
    label: "Sites de forage",
    value: data.total_drilling_sites,
    icon: HardHat,
  },
  {
    key: "total_workers",
    label: "Travailleurs",
    value: data.total_workers,
    icon: Users,
  },
  {
    key: "total_campaigns",
    label: "Campagnes médicales",
    value: data.total_campaigns,
    icon: ClipboardList,
  },
  {
    key: "active_campaigns",
    label: "Active Campaigns",
    value: data.active_campaigns,
    icon: Activity,
  },
  {
    key: "completed_campaigns",
    label: "Completed Campaigns",
    value: data.completed_campaigns,
    icon: ShieldCheck,
  },
  {
    key: "total_medical_tests",
    label: "Examens médicaux",
    value: data.total_medical_tests,
    icon: FlaskConical,
  },
  {
    key: "total_worker_tests",
    label: "Résultats médicaux",
    value: data.total_worker_tests,
    icon: TestTube2,
  },
  {
    key: "abnormal_results",
    label: "Abnormal Results",
    value: data.abnormal_results,
    icon: AlertTriangle,
  },
  {
    key: "pending_imports",
    label: "Pending Imports",
    value: data.pending_imports,
    icon: FolderClock,
  },
];

export const DashboardMetricGrid = ({ data }: { data: AdminDashboardData }) => (
  <div className="grid gap-4 grid-cols-2 grid-cols-4 grid-cols-5">
    {buildMetricCards(data).map((item) => (
      <Card
        key={item.key}
        className="bg-gradient-to-br from-white to-brand-50/40"
      >
        <div className="flex items-start justify-between gap-4">
          <div className="min-w-0">
            <p className="text-sm font-medium text-ink-500">{item.label}</p>
            <p className="mt-3 truncate text-3xl font-semibold text-ink-900">
              {formatNumber(item.value)}
            </p>
          </div>
          <div className="rounded-2xl bg-brand-100 p-3 text-brand-700 shadow-soft">
            <item.icon className="h-5 w-5" />
          </div>
        </div>
      </Card>
    ))}
  </div>
);

type AccessAction = {
  label: string;
  description: string;
  path: string;
  icon: typeof Users;
  permission?: string;
  actions: Array<{
    label: string;
    description: string;
    path?: string;
  }>;
};

const adminRoleActions: AccessAction[] = [
  {
    label: "Manage Users",
    description: "Create, update, and control platform user access.",
    path: "/users",
    icon: Users,
    permission: "users:manage",
    actions: [
      {
        label: "Create User",
        description: "Open the create user form.",
        path: "/users?action=create",
      },
      {
        label: "Edit User",
        description: "Select a user first, then edit the user information.",
        path: "/users?action=edit",
      },
      {
        label: "Deactivate User",
        description: "Manage active and inactive users.",
        path: "/users",
      },
      {
        label: "Assign Role",
        description: "Open user management to update roles.",
        path: "/users",
      },
      {
        label: "Reset Password",
        description: "Open user management for account recovery tasks.",
        path: "/users",
      },
      {
        label: "Review User Access",
        description: "Inspect user roles and access state.",
        path: "/users",
      },
    ],
  },
  {
    label: "Manage Campaigns",
    description: "Plan, lock, unlock, and supervise field campaigns.",
    path: "/campaigns",
    icon: ClipboardList,
    permission: "campaigns:manage",
    actions: [
      {
        label: "Create Campaign",
        description: "Open the create campaign workspace.",
        path: "/campaigns/create",
      },
      {
        label: "Edit Campaign",
        description: "Open the campaigns page to update existing campaigns.",
        path: "/campaigns",
      },
      {
        label: "Lock Campaign",
        description: "Open campaigns and lock completed campaigns.",
        path: "/campaigns",
      },
      {
        label: "Unlock Campaign",
        description: "Open campaigns and unlock completed campaigns.",
        path: "/campaigns",
      },
      {
        label: "Assign Doctor",
        description: "Open campaigns to assign doctors.",
        path: "/campaigns",
      },
      {
        label: "Assign Assistants",
        description: "Open campaigns to assign assistants.",
        path: "/campaigns",
      },
      {
        label: "Attach Workers and Tests",
        description: "Open campaigns to manage worker and test coverage.",
        path: "/campaigns",
      },
      {
        label: "Remove Campaign",
        description:
          "Open campaigns to remove a campaign with password confirmation.",
        path: "/campaigns",
      },
    ],
  },
  {
    label: "Run Reports",
    description: "Open campaign, workforce, and medical reporting tools.",
    path: "/reports",
    icon: FileBarChart2,
    permission: "reports:view",
    actions: [
      {
        label: "View Campaign Summary",
        description: "Open reporting for campaign summaries.",
        path: "/reports",
      },
      {
        label: "View Abnormal Results",
        description: "Open abnormal results report.",
        path: "/reports",
      },
      {
        label: "View Company Workers",
        description: "Open company workers reporting.",
        path: "/reports",
      },
      {
        label: "View Worker History",
        description: "Open worker medical history reporting.",
        path: "/reports",
      },
      {
        label: "Export Reports",
        description: "Open reports page and prepare export-ready data.",
        path: "/reports",
      },
    ],
  },
  {
    label: "Review Audit Logs",
    description: "Track every action performed across the system.",
    path: "/app/audit-logs",
    icon: LockKeyhole,
    permission: "audit_logs:view",
    actions: [
      {
        label: "View Latest Logs",
        description: "Open the audit log page.",
        path: "/app/audit-logs",
      },
      {
        label: "Track User Actions",
        description: "Review all recent user actions.",
        path: "/app/audit-logs",
      },
      {
        label: "Review Entity History",
        description: "Inspect entity-level changes and activity.",
        path: "/app/audit-logs",
      },
      {
        label: "Monitor IP Activity",
        description: "Review origin IPs for tracked actions.",
        path: "/app/audit-logs",
      },
    ],
  },
  {
    label: "Monitor Sync",
    description: "Check sync status, queue, and pending conflicts.",
    path: "/sync/status",
    icon: RefreshCw,
    permission: "sync:manage",
    actions: [
      {
        label: "Check Sync Status",
        description: "Open sync status view.",
        path: "/sync/status",
      },
      {
        label: "Run Sync Now",
        description: "Open sync controls and run synchronization.",
        path: "/sync/status",
      },
      {
        label: "Review Conflicts",
        description: "Open sync conflict resolution.",
        path: "/sync/conflicts",
      },
      {
        label: "Monitor Pending Queue",
        description: "Inspect pending sync work.",
        path: "/sync/status",
      },
    ],
  },
  {
    label: "Update Settings",
    description: "Adjust settings, permissions, and admin preferences.",
    path: "/settings",
    icon: Settings,
    permission: "settings:manage",
    actions: [
      {
        label: "Open Settings",
        description: "Go to the settings page.",
        path: "/settings",
      },
      {
        label: "Manage Permissions",
        description: "Open permission settings.",
        path: "/permissions",
      },
      {
        label: "Update Profile",
        description: "Open your profile settings.",
        path: "/profile",
      },
      {
        label: "Review System Preferences",
        description: "Review configurable application options.",
        path: "/settings",
      },
    ],
  },
];

const roleActions: Record<Role, AccessAction[]> = {
  "Super Admin": adminRoleActions,
  Admin: adminRoleActions,
  Doctor: [
    {
      label: "Review Worker Tests",
      description: "Open pending, completed, and reviewed worker tests.",
      path: "/worker-tests",
      icon: TestTube2,
      actions: [
        {
          label: "Review Pending Tests",
          description: "Open the worker tests page.",
          path: "/worker-tests",
        },
        {
          label: "Complete Test Result",
          description: "Open worker tests and update a result.",
          path: "/worker-tests",
        },
        {
          label: "Mark Abnormal Result",
          description: "Open worker tests and flag abnormal findings.",
          path: "/worker-tests",
        },
        {
          label: "Finalize Medical Review",
          description: "Open worker tests for final review steps.",
          path: "/worker-tests",
        },
      ],
    },
    {
      label: "View Campaigns",
      description: "Inspect assigned campaigns and worker coverage.",
      path: "/campaigns",
      icon: ClipboardList,
      actions: [
        {
          label: "Open Assigned Campaign",
          description: "Open campaign assignments.",
          path: "/campaigns",
        },
        {
          label: "Review Campaign Workers",
          description: "Inspect workers linked to campaigns.",
          path: "/campaigns",
        },
        {
          label: "Review Campaign Tests",
          description: "Inspect tests linked to campaigns.",
          path: "/campaigns",
        },
        {
          label: "Track Completion State",
          description: "Review campaign progress and status.",
          path: "/campaigns",
        },
      ],
    },
    {
      label: "Open Reports",
      description: "Inspect medical summaries and abnormal results.",
      path: "/reports",
      icon: FileBarChart2,
      actions: [
        {
          label: "View Medical Reports",
          description: "Open the reports workspace.",
          path: "/reports",
        },
        {
          label: "Open Abnormal Result Report",
          description: "Open reports for abnormal cases.",
          path: "/reports",
        },
        {
          label: "Review Worker History",
          description: "Open reports for worker history.",
          path: "/reports",
        },
      ],
    },
  ],
  Assistant: [
    {
      label: "Manage Imports",
      description: "Upload and validate worker and campaign import files.",
      path: "/imports",
      icon: FolderClock,
      actions: [
        {
          label: "Upload Import File",
          description: "Open the imports page to upload a file.",
          path: "/imports",
        },
        {
          label: "Validate File Rows",
          description: "Open imports to review validation.",
          path: "/imports",
        },
        {
          label: "Review Duplicates",
          description: "Open imports to inspect duplicate rows.",
          path: "/imports/history",
        },
        {
          label: "Confirm Import Batch",
          description: "Open imports and confirm prepared data.",
          path: "/imports",
        },
      ],
    },
    {
      label: "Open Campaigns",
      description: "Prepare campaign workers, tests, and logistics.",
      path: "/campaigns",
      icon: ClipboardList,
      actions: [
        {
          label: "Prepare Campaign",
          description: "Open campaign preparation.",
          path: "/campaigns",
        },
        {
          label: "Attach Workers",
          description: "Open campaigns and assign workers.",
          path: "/campaigns",
        },
        {
          label: "Attach Tests",
          description: "Open campaigns and assign tests.",
          path: "/campaigns",
        },
        {
          label: "Review Campaign Readiness",
          description: "Open campaigns to review readiness.",
          path: "/campaigns",
        },
      ],
    },
    {
      label: "Check Sync Status",
      description: "Monitor synchronization and pending offline changes.",
      path: "/sync/status",
      icon: RefreshCw,
      actions: [
        {
          label: "Check Device Sync",
          description: "Open sync status.",
          path: "/sync/status",
        },
        {
          label: "Review Offline Queue",
          description: "Open sync status for pending changes.",
          path: "/sync/status",
        },
        {
          label: "Open Sync Conflicts",
          description: "Open conflict resolution.",
          path: "/sync/conflicts",
        },
      ],
    },
  ],
};

export const DashboardAccessSection = ({
  user,
  onNavigate,
}: {
  user: AuthUser | null;
  onNavigate: (path: string) => void;
}) => {
  const resolvedRole: Role = user?.role || "Admin";
  const actions = roleActions[resolvedRole];
  return (
    <Card>
      <div className="mb-5 flex items-start justify-between gap-4">
        <p></p>
      </div>
      {/** 
      <div className="mb-5 flex items-start justify-between gap-4">
        <div>
          <h3 className="text-xl font-semibold text-navy-900">Actions d'accès par rôle</h3>
          <p className="mt-1 text-sm text-ink-500">
            Available actions for {resolvedRole} based on role access and granted permissions.
          </p>
        </div>
        <Badge tone="active">{resolvedRole}</Badge>
      </div>
      <div className="grid gap-4 grid-cols-2 grid-cols-3">
        {actions.map((action) => {
          const isGranted = !action.permission || hasPermission(user, action.permission);
          return (
            <div
              key={action.label}
              className="rounded-2xl border border-slate-200/80 bg-white/70 p-4 shadow-soft"
            >
              <div className="flex items-start justify-between gap-3">
                <div className="rounded-xl bg-brand-50 p-2.5 text-brand-700">
                  <action.icon className="h-4 w-4" />
                </div>
                <Badge tone={isGranted ? "active" : "inactive"}>
                  {isGranted ? "Allowed" : "Restricted"}
                </Badge>
              </div>
              <h4 className="mt-4 text-sm font-semibold text-navy-900">{action.label}</h4>
              <p className="mt-1 text-xs text-ink-500">{action.description}</p>
              <div className="mt-4 space-y-2">
                {action.actions.slice(0, 3).map((item) => (
                  <button
                    key={item.label}
                    type="button"
                    onClick={() => {
                      if (isGranted && item.path) {
                        onNavigate(item.path);
                      }
                    }}
                    disabled={!isGranted}
                    className="block w-full rounded-xl border border-slate-200/80 bg-white/80 px-3 py-3 text-left transition hover:border-brand-200 hover:bg-brand-50 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <p className="text-sm font-semibold text-navy-900">{item.label}</p>
                        <p className="mt-1 text-xs text-ink-500">{item.description}</p>
                      </div>
                      <ArrowUpRight className="mt-0.5 h-3.5 w-3.5 shrink-0 text-ink-400" />
                    </div>
                  </button>
                ))}
              </div>
            </div>
          );
        })}
      </div>
      */}
    </Card>
  );
};

const getActivityLabel = (action: string) => {
  const normalized = action.toLowerCase();

  if (normalized.includes("create") || normalized.includes("add"))
    return "Création";
  if (normalized.includes("update") || normalized.includes("edit"))
    return "Mise à jour";
  if (normalized.includes("delete") || normalized.includes("remove"))
    return "Suppression";
  if (normalized.includes("assign")) return "Affectation";
  if (
    normalized.includes("login") ||
    normalized.includes("auth") ||
    normalized.includes("access")
  ) {
    return "Accès";
  }
  if (
    normalized.includes("sync") ||
    normalized.includes("import") ||
    normalized.includes("export")
  ) {
    return "Synchronisation";
  }
  if (
    normalized.includes("warning") ||
    normalized.includes("error") ||
    normalized.includes("fail")
  ) {
    return "Alerte";
  }
  return action || "Activité";
};

const getActivityTone = (action: string) => {
  const normalized = action.toLowerCase();

  if (normalized.includes("create") || normalized.includes("add")) {
    return {
      accent: "border-l-emerald-500",
      iconWrap: "border-emerald-100 bg-emerald-50 text-emerald-600",
      badgeTone: "active",
      dot: "bg-emerald-500",
      ring: "shadow-[0_0_0_6px_rgba(16,185,129,0.12)]",
      hover: "hover:border-emerald-200",
    };
  }
  if (
    normalized.includes("update") ||
    normalized.includes("edit") ||
    normalized.includes("assign")
  ) {
    return {
      accent: "border-l-sky-500",
      iconWrap: "border-sky-100 bg-sky-50 text-sky-600",
      badgeTone: "completed",
      dot: "bg-sky-500",
      ring: "shadow-[0_0_0_6px_rgba(14,165,233,0.12)]",
      hover: "hover:border-sky-200",
    };
  }
  if (normalized.includes("delete") || normalized.includes("remove")) {
    return {
      accent: "border-l-rose-500",
      iconWrap: "border-rose-100 bg-rose-50 text-rose-600",
      badgeTone: "failed",
      dot: "bg-rose-500",
      ring: "shadow-[0_0_0_6px_rgba(244,63,94,0.12)]",
      hover: "hover:border-rose-200",
    };
  }
  if (
    normalized.includes("login") ||
    normalized.includes("auth") ||
    normalized.includes("access")
  ) {
    return {
      accent: "border-l-violet-500",
      iconWrap: "border-violet-100 bg-violet-50 text-violet-600",
      badgeTone: "admin",
      dot: "bg-violet-500",
      ring: "shadow-[0_0_0_6px_rgba(139,92,246,0.12)]",
      hover: "hover:border-violet-200",
    };
  }
  if (
    normalized.includes("sync") ||
    normalized.includes("import") ||
    normalized.includes("export")
  ) {
    return {
      accent: "border-l-cyan-500",
      iconWrap: "border-cyan-100 bg-cyan-50 text-cyan-600",
      badgeTone: "assistant",
      dot: "bg-cyan-500",
      ring: "shadow-[0_0_0_6px_rgba(6,182,212,0.12)]",
      hover: "hover:border-cyan-200",
    };
  }
  if (
    normalized.includes("warning") ||
    normalized.includes("error") ||
    normalized.includes("fail")
  ) {
    return {
      accent: "border-l-orange-500",
      iconWrap: "border-orange-100 bg-orange-50 text-orange-600",
      badgeTone: "offline",
      dot: "bg-orange-500",
      ring: "shadow-[0_0_0_6px_rgba(249,115,22,0.12)]",
      hover: "hover:border-orange-200",
    };
  }
  return {
    accent: "border-l-slate-400",
    iconWrap: "border-slate-200 bg-slate-50 text-slate-600",
    badgeTone: "inactive",
    dot: "bg-slate-400",
    ring: "shadow-[0_0_0_6px_rgba(148,163,184,0.12)]",
    hover: "hover:border-slate-300",
  };
};

const getActivityIcon = (action: string) => {
  const normalized = action.toLowerCase();

  if (normalized.includes("create") || normalized.includes("add"))
    return PlusCircle;
  if (normalized.includes("update") || normalized.includes("edit"))
    return Pencil;
  if (normalized.includes("delete") || normalized.includes("remove"))
    return Trash2;
  if (
    normalized.includes("login") ||
    normalized.includes("auth") ||
    normalized.includes("access")
  ) {
    return LogIn;
  }
  if (normalized.includes("sync")) return RefreshCw;
  if (normalized.includes("import")) return Upload;
  if (normalized.includes("export")) return Download;
  if (
    normalized.includes("warning") ||
    normalized.includes("error") ||
    normalized.includes("fail")
  ) {
    return AlertTriangle;
  }
  return ShieldCheck;
};

const formatMetadata = (metadata?: string | null) => {
  const raw = (metadata || "").trim();
  const empty = {
    preview: "",
    device: "",
    source: "",
    oldValue: "",
    newValue: "",
    notes: [] as string[],
  };

  if (!raw) return empty;

  try {
    const parsed = JSON.parse(raw) as Record<string, unknown>;
    const oldValue = parsed.old_value ?? parsed.oldValue;
    const newValue = parsed.new_value ?? parsed.newValue;
    const source = parsed.source ?? parsed.origin;
    const device = parsed.device ?? parsed.user_agent;

    return {
      preview:
        String(
          parsed.summary ?? parsed.message ?? parsed.description ?? raw,
        ).trim() || raw,
      device: String(device || "").trim(),
      source: String(source || "").trim(),
      oldValue:
        typeof oldValue === "string"
          ? oldValue
          : oldValue
            ? JSON.stringify(oldValue)
            : "",
      newValue:
        typeof newValue === "string"
          ? newValue
          : newValue
            ? JSON.stringify(newValue)
            : "",
      notes: Object.entries(parsed)
        .filter(
          ([key]) =>
            ![
              "summary",
              "message",
              "description",
              "old_value",
              "oldValue",
              "new_value",
              "newValue",
              "source",
              "origin",
              "device",
              "user_agent",
            ].includes(key),
        )
        .map(
          ([key, value]) =>
            `${key}: ${typeof value === "string" ? value : JSON.stringify(value)}`,
        ),
    };
  } catch {
    const lines = raw
      .split(/\r?\n|\s\|\s|\s·\s/)
      .map((line) => line.trim())
      .filter(Boolean);

    const extractValue = (pattern: RegExp) => {
      const line = lines.find((entry) => pattern.test(entry));
      return line ? line.replace(pattern, "").trim() : "";
    };

    return {
      preview: lines[0] || raw,
      device: extractValue(/^(device|appareil)\s*:\s*/i),
      source: extractValue(/^(source|origine)\s*:\s*/i),
      oldValue: extractValue(/^(old value|ancienne valeur)\s*:\s*/i),
      newValue: extractValue(/^(new value|nouvelle valeur)\s*:\s*/i),
      notes: lines,
    };
  }
};

type DiffChange = {
  path: string;
  oldValue: unknown;
  newValue: unknown;
};

type MedicalFieldEntry = {
  path: string;
  label: string;
  section: (typeof medicalSections)[number];
  oldValue: unknown;
  newValue: unknown;
  changed: boolean;
  kind: "primitive" | "array";
};

type MedicalFileSummary = {
  rawLine: string;
  oldData: Record<string, unknown>;
  newData: Record<string, unknown>;
  changes: DiffChange[];
  fieldEntries: MedicalFieldEntry[];
  rawOldText: string;
  rawNewText: string;
};

const medicalFieldLabels: Record<string, string> = {
  medicalFileNumber: "N° dossier médical",
  employeeCode: "Code employé",
  nationalId: "N° identification nationale",
  lastName: "Nom",
  firstName: "Prénom",
  sex: "Sexe",
  dateOfBirth: "Date de naissance",
  birthPlace: "Lieu de naissance",
  familySituation: "Situation familiale",
  phone: "Téléphone",
  originAddress: "Adresse d'origine",
  professionalAddress: "Adresse professionnelle",
  companyName: "Société",
  siteName: "Site",
  direction: "Direction",
  position: "Poste",
  department: "Département",
  service: "Service",
  workshop: "Atelier",
  schoolEducation: "Niveau scolaire",
  professionalTraining: "Formation professionnelle",
  professionalQualification: "Qualification professionnelle",
  nationalServiceStatus: "Service national",
  nationalServiceNotes: "Notes service national",
  chronicDiseaseNotes: "Maladies chroniques",
  bloodGroup: "Groupe sanguin / Rhésus",
  congenitalDiseases: "Maladies congénitales",
  generalDiseases: "Maladies générales",
  surgicalInterventions: "Interventions chirurgicales",
  accidents: "Accidents",
  intoxications: "Intoxications",
  tobacco: "Tabac",
  chewingTobacco: "Tabac à chiquer",
  alcoholism: "Alcool",
  otherIntoxications: "Autres intoxications",
  familyHistoryFather: "Père",
  familyHistoryMother: "Mère",
  familyHistorySisters: "Sœurs",
  familyHistoryBrothers: "Frères",
  familyHistorySpouse: "Conjoint",
  familyHistoryChildrenBoys: "Garçons",
  familyHistoryChildrenGirls: "Filles",
  professionalDiseaseNotes: "Risques professionnels",
  professionalHistory: "Historique professionnel",
  "professionalHistory.occupiedPosition": "Poste occupé",
  "professionalHistory.fromDate": "Du",
  "professionalHistory.toDate": "Au",
  "professionalHistory.workplaceAndRisks": "Lieu de travail et risques",
  vaccinations: "Vaccinations",
  "vaccinations.vaccineName": "Vaccin",
  "vaccinations.firstDose": "1ère dose",
  "vaccinations.secondDose": "2ème dose",
  "vaccinations.firstBooster": "1er rappel",
  "vaccinations.secondBooster": "2ème rappel",
  workAccidents: "Accidents de travail",
  "workAccidents.date": "Date",
  "workAccidents.place": "Lieu",
  "workAccidents.consequences": "Conséquences",
  occupationalDiseases: "Maladies professionnelles",
  "occupationalDiseases.date": "Date",
  "occupationalDiseases.place": "Lieu",
  "occupationalDiseases.exposedProducts": "Produits exposés",
  "occupationalDiseases.symptoms": "Symptômes",
  "occupationalDiseases.tmpNumber": "N° TMP",
  "occupationalDiseases.ipp": "IPP",
  spontaneousConsultations: "Consultations",
  "spontaneousConsultations.date": "Date",
  "spontaneousConsultations.observation": "Observation",
  internalVisitDate: "Date de visite",
  internalVisitDoctor: "Médecin",
  internalVisitWeightKg: "Poids",
  internalVisitHeightCm: "Taille",
  internalVisitTa: "TA",
  internalVisitFc: "FC",
  internalVisitHire: "Visite d'embauche",
  internalVisitPeriodic: "Visite périodique",
  internalVisitDistanceOdSc: "OD SC",
  internalVisitDistanceOdAc: "OD AC",
  internalVisitDistanceOgSc: "OG SC",
  internalVisitDistanceOgAc: "OG AC",
  internalVisitDistanceOdg: "ODG",
  clinicalExam: "Examen clinique",
  complementaryExams: "Examens complémentaires",
  medicalDecision: "Décision médicale",
  auditTrail: "Historique d'activité",
  confirmationDate: "Date de confirmation",
  confirmationDoctor: "Médecin confirmateur",
  confirmationSignature: "Signature",
  isLocked: "Dossier verrouillé",
  confirmationStatus: "Statut de confirmation",
  "auditTrail.action": "Action",
  "auditTrail.actor": "Acteur",
  "auditTrail.at": "Date",
};

const medicalSegmentLabels: Record<string, string> = {
  clinicalExam: "Examen clinique",
  complementaryExams: "Examens complémentaires",
  medicalDecision: "Décision médicale",
  ophthalmology: "Ophtalmologie",
  ent: "ORL",
  stomatology: "Stomatologie",
  cardiovascular: "Cardiovasculaire",
  respiratory: "Respiratoire",
  digestive: "Digestif",
  urogenital: "Urogénital",
  endocrine: "Endocrinien",
  hematology: "Hématologie",
  neuroPsychiatric: "Neuro-psychiatrique",
  osteoArticular: "Ostéo-articulaire",
  dermatology: "Dermatologie",
  doctorGeneralObservations: "Observations du médecin",
  cardiology: "Cardiologie",
  audiology: "Audiologie",
  biology: "Biologie",
  parasitology: "Parasitologie",
  radiology: "Radiologie",
  otherExams: "Autres examens",
  orientation: "Orientation",
  specialistResponse: "Réponse spécialiste",
  cat: "CAT",
  restrictions: "Restrictions",
  interpretation: "Interprétation",
  recommendations: "Recommandations",
  nextVisit: "Prochaine visite",
  validation: "Validation",
  observations: "Observations",
  nose: "Nez",
  ears: "Oreilles",
  throat: "Gorge",
  teeth: "Dents",
  others: "Autres",
  bloodPressure: "Tension artérielle",
  dyspnea: "Dyspnée",
  chronicCough: "Toux chronique",
  asthma: "Asthme",
  ulcer: "Ulcère",
  colopathy: "Colopathie",
  hemorrhoids: "Hémorroïdes",
  dysuria: "Dysurie",
  impotence: "Impuissance",
  diabetes: "Diabète",
  thyroid: "Thyroïde",
  hemostasis: "Hémostase",
  adenopathy: "Adénopathie",
  headachesVertigo: "Céphalées / vertiges",
  neurologicalSigns: "Signes neurologiques",
  personalityDisorders: "Troubles de la personnalité",
  polyarthralgia: "Polyarthralgie",
  lesions: "Lésions",
  skinAllergies: "Allergies cutanées",
  urticaria: "Urticaire",
  comments: "Commentaires",
  ecg: "ECG",
  audiogram: "Audiogramme",
  efr: "EFR",
  glycemia: "Glycémie",
  hba1c: "HbA1c",
  urea: "Urée",
  creatinine: "Créatinine",
  cholesterol: "Cholestérol",
  triglycerides: "Triglycérides",
  hdlLdl: "HDL / LDL",
  urineChemistry: "Chimie des urines",
  gr: "GR",
  gb: "GB",
  hb: "HB",
  ht: "HT",
  vgm: "VGM",
  ccmh: "CCMH",
  plt: "PLT",
  pn: "PN",
  lymphocytes: "Lymphocytes",
  bem: "BEM",
  vs: "VS",
  stoolExam: "Examen des selles",
  chestXray: "Radiographie thoracique",
  freeText: "Texte libre",
  specialistAdvice: "Avis spécialiste",
  specialistAdviceDetails: "Détails avis spécialiste",
  treatment: "Traitement",
  treatmentDetails: "Détails traitement",
  hospitalization: "Hospitalisation",
  hospitalizationDetails: "Détails hospitalisation",
  specialty: "Spécialité",
  response: "Réponse",
  socialService: "Service social",
  employmentService: "Service emploi",
  conduct: "Conduite à tenir",
  aptitude: "Aptitude",
  professionalRestrictions: "Restrictions professionnelles",
  decisionInterpretation: "Interprétation de la décision",
  doctorRecommendations: "Recommandations du médecin",
  nextVisitSchedule: "Périodicité",
  nextVisitCustomMonths: "Nombre de mois",
  nextVisitDate: "Date prochaine visite",
  validatingDoctor: "Médecin validateur",
  validationDate: "Date de validation",
  electronicSignature: "Signature électronique",
  includeValidatorSignature: "Inclure la signature du validateur",
};

const medicalSections = [
  "Identité",
  "Informations professionnelles",
  "Antécédents médicaux",
  "Antécédents familiaux",
  "Risques professionnels",
  "Consultations",
  "Fiche interne de visite médicale",
  "Examen clinique",
  "Examens complémentaires",
  "Décision médicale",
  "Aperçu et validation",
] as const;

type MedicalSectionName = (typeof medicalSections)[number];

type MedicalSchemaField = {
  path: string;
  kind?: "primitive" | "array";
};

const medicalSectionSchema: Array<{
  section: MedicalSectionName;
  fields: MedicalSchemaField[];
}> = [
  {
    section: "Identité",
    fields: [
      { path: "medicalFileNumber" },
      { path: "employeeCode" },
      { path: "nationalId" },
      { path: "lastName" },
      { path: "firstName" },
      { path: "sex" },
      { path: "dateOfBirth" },
      { path: "birthPlace" },
      { path: "familySituation" },
      { path: "phone" },
      { path: "originAddress" },
      { path: "professionalAddress" },
    ],
  },
  {
    section: "Informations professionnelles",
    fields: [
      { path: "companyName" },
      { path: "siteName" },
      { path: "direction" },
      { path: "position" },
      { path: "department" },
      { path: "service" },
      { path: "workshop" },
      { path: "schoolEducation" },
      { path: "professionalTraining" },
      { path: "professionalQualification" },
      { path: "nationalServiceStatus" },
      { path: "nationalServiceNotes" },
    ],
  },
  {
    section: "Antécédents médicaux",
    fields: [
      { path: "chronicDiseaseNotes" },
      { path: "bloodGroup" },
      { path: "congenitalDiseases" },
      { path: "generalDiseases" },
      { path: "surgicalInterventions" },
      { path: "accidents" },
      { path: "intoxications" },
      { path: "tobacco" },
      { path: "chewingTobacco" },
      { path: "alcoholism" },
      { path: "otherIntoxications" },
      { path: "vaccinations", kind: "array" },
    ],
  },
  {
    section: "Antécédents familiaux",
    fields: [
      { path: "familyHistoryFather" },
      { path: "familyHistoryMother" },
      { path: "familyHistorySisters" },
      { path: "familyHistoryBrothers" },
      { path: "familyHistorySpouse" },
      { path: "familyHistoryChildrenBoys" },
      { path: "familyHistoryChildrenGirls" },
    ],
  },
  {
    section: "Risques professionnels",
    fields: [
      { path: "professionalDiseaseNotes" },
      { path: "professionalHistory", kind: "array" },
      { path: "workAccidents", kind: "array" },
      { path: "occupationalDiseases", kind: "array" },
    ],
  },
  {
    section: "Consultations",
    fields: [{ path: "spontaneousConsultations", kind: "array" }],
  },
  {
    section: "Fiche interne de visite médicale",
    fields: [
      { path: "internalVisitHire" },
      { path: "internalVisitPeriodic" },
      { path: "internalVisitDate" },
      { path: "internalVisitDoctor" },
      { path: "internalVisitWeightKg" },
      { path: "internalVisitHeightCm" },
      { path: "internalVisitTa" },
      { path: "internalVisitFc" },
      { path: "internalVisitDistanceOdSc" },
      { path: "internalVisitDistanceOdAc" },
      { path: "internalVisitDistanceOgSc" },
      { path: "internalVisitDistanceOgAc" },
      { path: "internalVisitDistanceOdg" },
    ],
  },
  {
    section: "Examen clinique",
    fields: [
      { path: "clinicalExam.ophthalmology.observations" },
      { path: "clinicalExam.ent.nose" },
      { path: "clinicalExam.ent.ears" },
      { path: "clinicalExam.ent.throat" },
      { path: "clinicalExam.stomatology.teeth" },
      { path: "clinicalExam.stomatology.others" },
      { path: "clinicalExam.cardiovascular.bloodPressure" },
      { path: "clinicalExam.cardiovascular.dyspnea" },
      { path: "clinicalExam.respiratory.chronicCough" },
      { path: "clinicalExam.respiratory.asthma" },
      { path: "clinicalExam.digestive.ulcer" },
      { path: "clinicalExam.digestive.colopathy" },
      { path: "clinicalExam.digestive.hemorrhoids" },
      { path: "clinicalExam.digestive.others" },
      { path: "clinicalExam.urogenital.dysuria" },
      { path: "clinicalExam.urogenital.impotence" },
      { path: "clinicalExam.urogenital.others" },
      { path: "clinicalExam.endocrine.diabetes" },
      { path: "clinicalExam.endocrine.thyroid" },
      { path: "clinicalExam.endocrine.others" },
      { path: "clinicalExam.hematology.hemostasis" },
      { path: "clinicalExam.hematology.adenopathy" },
      { path: "clinicalExam.hematology.others" },
      { path: "clinicalExam.neuroPsychiatric.headachesVertigo" },
      { path: "clinicalExam.neuroPsychiatric.neurologicalSigns" },
      { path: "clinicalExam.neuroPsychiatric.personalityDisorders" },
      { path: "clinicalExam.neuroPsychiatric.others" },
      { path: "clinicalExam.osteoArticular.polyarthralgia" },
      { path: "clinicalExam.dermatology.lesions" },
      { path: "clinicalExam.dermatology.skinAllergies" },
      { path: "clinicalExam.dermatology.urticaria" },
      { path: "clinicalExam.doctorGeneralObservations.comments" },
      { path: "clinicalExam.doctorGeneralObservations.recommendations" },
    ],
  },
  {
    section: "Examens complémentaires",
    fields: [
      { path: "complementaryExams.cardiology.ecg" },
      { path: "complementaryExams.audiology.audiogram" },
      { path: "complementaryExams.respiratory.efr" },
      { path: "complementaryExams.biology.glycemia" },
      { path: "complementaryExams.biology.hba1c" },
      { path: "complementaryExams.biology.urea" },
      { path: "complementaryExams.biology.creatinine" },
      { path: "complementaryExams.biology.cholesterol" },
      { path: "complementaryExams.biology.triglycerides" },
      { path: "complementaryExams.biology.hdlLdl" },
      { path: "complementaryExams.biology.urineChemistry" },
      { path: "complementaryExams.hematology.gr" },
      { path: "complementaryExams.hematology.gb" },
      { path: "complementaryExams.hematology.hb" },
      { path: "complementaryExams.hematology.ht" },
      { path: "complementaryExams.hematology.vgm" },
      { path: "complementaryExams.hematology.ccmh" },
      { path: "complementaryExams.hematology.plt" },
      { path: "complementaryExams.hematology.pn" },
      { path: "complementaryExams.hematology.lymphocytes" },
      { path: "complementaryExams.hematology.bem" },
      { path: "complementaryExams.hematology.vs" },
      { path: "complementaryExams.parasitology.stoolExam" },
      { path: "complementaryExams.radiology.chestXray" },
      { path: "complementaryExams.radiology.others" },
      { path: "complementaryExams.otherExams.freeText" },
    ],
  },
  {
    section: "Décision médicale",
    fields: [
      { path: "medicalDecision.orientation.specialistAdvice" },
      { path: "medicalDecision.orientation.specialistAdviceDetails" },
      { path: "medicalDecision.orientation.treatment" },
      { path: "medicalDecision.orientation.treatmentDetails" },
      { path: "medicalDecision.orientation.hospitalization" },
      { path: "medicalDecision.orientation.hospitalizationDetails" },
      { path: "medicalDecision.orientation.specialty" },
      { path: "medicalDecision.specialistResponse.response" },
      { path: "medicalDecision.specialistResponse.socialService" },
      { path: "medicalDecision.specialistResponse.employmentService" },
      { path: "medicalDecision.cat.conduct" },
      { path: "medicalDecision.aptitude" },
      { path: "medicalDecision.restrictions.professionalRestrictions" },
      { path: "medicalDecision.interpretation.decisionInterpretation" },
      { path: "medicalDecision.recommendations.doctorRecommendations" },
      { path: "medicalDecision.nextVisit.nextVisitSchedule" },
      { path: "medicalDecision.nextVisit.nextVisitCustomMonths" },
      { path: "medicalDecision.nextVisit.nextVisitDate" },
      { path: "medicalDecision.validation.validatingDoctor" },
      { path: "medicalDecision.validation.validationDate" },
      { path: "medicalDecision.validation.electronicSignature" },
      { path: "medicalDecision.validation.includeValidatorSignature" },
    ],
  },
  {
    section: "Aperçu et validation",
    fields: [
      { path: "confirmationStatus" },
      { path: "confirmationDoctor" },
      { path: "confirmationDate" },
      { path: "confirmationSignature" },
      { path: "isLocked" },
      { path: "auditTrail", kind: "array" },
    ],
  },
];

const arrayFieldOrder: Record<string, string[]> = {
  professionalHistory: [
    "occupiedPosition",
    "fromDate",
    "toDate",
    "workplaceAndRisks",
  ],
  vaccinations: [
    "vaccineName",
    "firstDose",
    "secondDose",
    "firstBooster",
    "secondBooster",
  ],
  workAccidents: ["date", "place", "consequences"],
  occupationalDiseases: [
    "date",
    "place",
    "exposedProducts",
    "symptoms",
    "tmpNumber",
    "ipp",
  ],
  spontaneousConsultations: ["date", "observation"],
  auditTrail: ["action", "actor", "at"],
};

const sectionPrefixMap: Array<{ prefix: string; section: MedicalSectionName }> =
  [
    { prefix: "medicalFileNumber", section: "Identité" },
    { prefix: "employeeCode", section: "Identité" },
    { prefix: "nationalId", section: "Identité" },
    { prefix: "lastName", section: "Identité" },
    { prefix: "firstName", section: "Identité" },
    { prefix: "sex", section: "Identité" },
    { prefix: "dateOfBirth", section: "Identité" },
    { prefix: "birthPlace", section: "Identité" },
    { prefix: "familySituation", section: "Identité" },
    { prefix: "phone", section: "Identité" },
    { prefix: "originAddress", section: "Identité" },
    { prefix: "professionalAddress", section: "Identité" },
    { prefix: "companyName", section: "Informations professionnelles" },
    { prefix: "siteName", section: "Informations professionnelles" },
    { prefix: "direction", section: "Informations professionnelles" },
    { prefix: "position", section: "Informations professionnelles" },
    { prefix: "department", section: "Informations professionnelles" },
    { prefix: "service", section: "Informations professionnelles" },
    { prefix: "workshop", section: "Informations professionnelles" },
    { prefix: "schoolEducation", section: "Informations professionnelles" },
    {
      prefix: "professionalTraining",
      section: "Informations professionnelles",
    },
    {
      prefix: "professionalQualification",
      section: "Informations professionnelles",
    },
    { prefix: "congenitalDiseases", section: "Antécédents médicaux" },
    { prefix: "generalDiseases", section: "Antécédents médicaux" },
    { prefix: "surgicalInterventions", section: "Antécédents médicaux" },
    { prefix: "accidents", section: "Antécédents médicaux" },
    { prefix: "intoxications", section: "Antécédents médicaux" },
    { prefix: "tobacco", section: "Antécédents médicaux" },
    { prefix: "chewingTobacco", section: "Antécédents médicaux" },
    { prefix: "alcoholism", section: "Antécédents médicaux" },
    { prefix: "otherIntoxications", section: "Antécédents médicaux" },
    { prefix: "chronicDiseaseNotes", section: "Antécédents médicaux" },
    { prefix: "bloodGroup", section: "Antécédents médicaux" },
    { prefix: "familyHistory", section: "Antécédents familiaux" },
    { prefix: "professionalDiseaseNotes", section: "Risques professionnels" },
    { prefix: "professionalHistory", section: "Risques professionnels" },
    { prefix: "workAccidents", section: "Risques professionnels" },
    { prefix: "occupationalDiseases", section: "Risques professionnels" },
    { prefix: "spontaneousConsultations", section: "Consultations" },
    { prefix: "internalVisit", section: "Fiche interne de visite médicale" },
    { prefix: "clinicalExam", section: "Examen clinique" },
    { prefix: "complementaryExams", section: "Examens complémentaires" },
    { prefix: "medicalDecision", section: "Décision médicale" },
    { prefix: "confirmation", section: "Aperçu et validation" },
    { prefix: "isLocked", section: "Aperçu et validation" },
    { prefix: "auditTrail", section: "Aperçu et validation" },
  ];

const pythonLiteralToJson = (value: string) =>
  value
    .replace(/None/g, "null")
    .replace(/True/g, "true")
    .replace(/False/g, "false");

const parseQuotedString = (source: string, startIndex: number) => {
  const quote = source[startIndex];
  let index = startIndex + 1;
  let output = "";

  while (index < source.length) {
    const char = source[index];
    if (char === "\\") {
      const next = source[index + 1];
      if (next) {
        output += next;
        index += 2;
        continue;
      }
    }
    if (char === quote) {
      return { value: output, nextIndex: index + 1 };
    }
    output += char;
    index += 1;
  }

  return { value: output, nextIndex: index };
};

const splitTopLevelLiteral = (source: string, separator: string) => {
  const parts: string[] = [];
  let current = "";
  let depth = 0;
  let inString = false;
  let quote = "";

  for (let index = 0; index < source.length; index += 1) {
    const char = source[index];
    const nextSlice = source.slice(index, index + separator.length);

    if (inString) {
      current += char;
      if (char === "\\") {
        const next = source[index + 1];
        if (next) {
          current += next;
          index += 1;
        }
        continue;
      }
      if (char === quote) {
        inString = false;
        quote = "";
      }
      continue;
    }

    if (char === "'" || char === '"') {
      inString = true;
      quote = char;
      current += char;
      continue;
    }

    if (char === "{" || char === "[" || char === "(") depth += 1;
    if (char === "}" || char === "]" || char === ")") depth -= 1;

    if (depth === 0 && nextSlice === separator) {
      parts.push(current.trim());
      current = "";
      index += separator.length - 1;
      continue;
    }

    current += char;
  }

  if (current.trim()) {
    parts.push(current.trim());
  }

  return parts;
};

const parsePythonLikeLiteral = (rawValue: string): unknown => {
  const source = pythonLiteralToJson(rawValue.trim());
  let index = 0;

  const skipWhitespace = () => {
    while (index < source.length && /\s/.test(source[index])) {
      index += 1;
    }
  };

  const parseValue = (): unknown => {
    skipWhitespace();
    const char = source[index];

    if (char === "{") {
      index += 1;
      const result: Record<string, unknown> = {};
      skipWhitespace();
      while (index < source.length && source[index] !== "}") {
        const key = parseValue();
        skipWhitespace();
        if (source[index] === ":") {
          index += 1;
        }
        const value = parseValue();
        result[String(key)] = value;
        skipWhitespace();
        if (source[index] === ",") {
          index += 1;
          skipWhitespace();
        }
      }
      if (source[index] === "}") {
        index += 1;
      }
      return result;
    }

    if (char === "[") {
      index += 1;
      const result: unknown[] = [];
      skipWhitespace();
      while (index < source.length && source[index] !== "]") {
        result.push(parseValue());
        skipWhitespace();
        if (source[index] === ",") {
          index += 1;
          skipWhitespace();
        }
      }
      if (source[index] === "]") {
        index += 1;
      }
      return result;
    }

    if (char === "'" || char === '"') {
      const parsed = parseQuotedString(source, index);
      index = parsed.nextIndex;
      return parsed.value;
    }

    const remainder = source.slice(index);
    if (remainder.startsWith("null")) {
      index += 4;
      return null;
    }
    if (remainder.startsWith("true")) {
      index += 4;
      return true;
    }
    if (remainder.startsWith("false")) {
      index += 5;
      return false;
    }

    const tokenMatch = remainder.match(/^[^,\]\}\s]+/);
    const token = tokenMatch?.[0] ?? "";
    index += token.length;

    if (/^-?\d+(\.\d+)?$/.test(token)) {
      return Number(token);
    }

    return token;
  };

  return parseValue();
};

const isIsoDateLike = (value: string) =>
  /^\d{4}-\d{2}-\d{2}(?:[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?)?/.test(value);

const formatDate = (value: string) => {
  return formatDisplayDateTime(value) || value;
};

const formatValue = (value: unknown): string => {
  if (value === null || value === undefined || value === "") {
    return "Non renseigné";
  }
  if (typeof value === "boolean") {
    return value ? "Oui" : "Non";
  }
  if (typeof value === "string") {
    return isIsoDateLike(value) ? formatDate(value) : value;
  }
  if (typeof value === "number") {
    return String(value);
  }
  if (Array.isArray(value)) {
    return `${value.length} élément${value.length > 1 ? "s" : ""}`;
  }
  if (typeof value === "object") {
    return "Objet structuré";
  }
  return String(value);
};

const formatFieldLabel = (path: string) => {
  if (medicalFieldLabels[path]) {
    return medicalFieldLabels[path];
  }

  const normalizedPath = path.replace(/\.\d+(?=\.|$)/g, "");
  if (medicalFieldLabels[normalizedPath]) {
    return medicalFieldLabels[normalizedPath];
  }

  const leaf = normalizedPath.split(".").pop() || normalizedPath;
  return leaf
    .replace(/([a-z])([A-Z])/g, "$1 $2")
    .replace(/_/g, " ")
    .replace(/id/gi, "ID")
    .replace(/^./, (match) => match.toUpperCase());
};

const getSectionForPath = (path: string) => {
  const override = sectionPrefixMap.find(
    (item) => path === item.prefix || path.startsWith(`${item.prefix}.`),
  );
  return override?.section || "Aperçu et validation";
};

const areValuesEqual = (left: unknown, right: unknown) =>
  JSON.stringify(left) === JSON.stringify(right);

const deepDiff = (
  oldData: unknown,
  newData: unknown,
  basePath = "",
): DiffChange[] => {
  if (areValuesEqual(oldData, newData)) {
    return [];
  }

  if (Array.isArray(oldData) && Array.isArray(newData)) {
    return [{ path: basePath, oldValue: oldData, newValue: newData }];
  }

  if (
    oldData &&
    newData &&
    typeof oldData === "object" &&
    typeof newData === "object" &&
    !Array.isArray(oldData) &&
    !Array.isArray(newData)
  ) {
    const oldRecord = oldData as Record<string, unknown>;
    const newRecord = newData as Record<string, unknown>;
    const keys = new Set([
      ...Object.keys(oldRecord),
      ...Object.keys(newRecord),
    ]);
    return Array.from(keys).flatMap((key) =>
      deepDiff(
        oldRecord[key],
        newRecord[key],
        basePath ? `${basePath}.${key}` : key,
      ),
    );
  }

  return [{ path: basePath, oldValue: oldData, newValue: newData }];
};

const getChangedFields = (
  oldData: Record<string, unknown>,
  newData: Record<string, unknown>,
) => deepDiff(oldData, newData);

const extractMedicalFileLine = (detailsSummary?: string | null) => {
  if (!detailsSummary) return null;
  return (
    splitTopLevelLiteral(detailsSummary, " | ").find((segment) =>
      segment.toLowerCase().startsWith("medical file data:"),
    ) || null
  );
};

const extractMedicalFilePayload = (line: string) => {
  const marker = "Medical File Data:";
  const normalizedLine = line.trim();

  const payload = normalizedLine.toLowerCase().startsWith(marker.toLowerCase())
    ? normalizedLine.slice(marker.length).trim()
    : normalizedLine;

  const parts = splitTopLevelLiteral(payload, "->");

  if (parts.length < 2) {
    return null;
  }

  const oldRaw = parts[0]?.trim();
  const newRaw = parts.slice(1).join("->").trim();

  if (!oldRaw || !newRaw) {
    return null;
  }

  return {
    oldRaw,
    newRaw,
  };
};

const isPrimitiveLike = (value: unknown) =>
  value === null ||
  value === undefined ||
  typeof value !== "object" ||
  value instanceof Date;

const getValueAtPath = (source: unknown, path: string): unknown =>
  path.split(".").reduce<unknown>((current, key) => {
    if (current && typeof current === "object" && !Array.isArray(current)) {
      return (current as Record<string, unknown>)[key];
    }
    return undefined;
  }, source);

const flattenMedicalFields = (
  oldData: Record<string, unknown>,
  newData: Record<string, unknown>,
): MedicalFieldEntry[] => {
  const schemaEntries = medicalSectionSchema.flatMap(({ section, fields }) =>
    fields.map((field) => {
      const oldValue = getValueAtPath(oldData, field.path);
      const newValue = getValueAtPath(newData, field.path);
      return {
        path: field.path,
        label: formatFieldLabel(field.path),
        section,
        oldValue,
        newValue,
        changed: !areValuesEqual(oldValue, newValue),
        kind: field.kind === "array" ? "array" : "primitive",
      } satisfies MedicalFieldEntry;
    }),
  );

  const knownPaths = new Set(schemaEntries.map((entry) => entry.path));
  const collectExtraFields = (
    oldValue: unknown,
    newValue: unknown,
    basePath = "",
  ): MedicalFieldEntry[] => {
    const left = oldValue as Record<string, unknown> | undefined;
    const right = newValue as Record<string, unknown> | undefined;

    if (!basePath) {
      const keys = new Set<string>([
        ...Object.keys((left && typeof left === "object" ? left : {}) || {}),
        ...Object.keys((right && typeof right === "object" ? right : {}) || {}),
      ]);
      return Array.from(keys).flatMap((key) =>
        collectExtraFields(left?.[key], right?.[key], key),
      );
    }

    if (knownPaths.has(basePath)) {
      return [];
    }

    if (
      Array.isArray(oldValue) ||
      Array.isArray(newValue) ||
      (isPrimitiveLike(oldValue) && isPrimitiveLike(newValue))
    ) {
      return [
        {
          path: basePath,
          label: formatFieldLabel(basePath),
          section: getSectionForPath(basePath),
          oldValue,
          newValue,
          changed: !areValuesEqual(oldValue, newValue),
          kind:
            Array.isArray(oldValue) || Array.isArray(newValue)
              ? "array"
              : "primitive",
        },
      ];
    }

    const keys = new Set<string>([
      ...Object.keys((left && typeof left === "object" ? left : {}) || {}),
      ...Object.keys((right && typeof right === "object" ? right : {}) || {}),
    ]);

    return Array.from(keys).flatMap((key) =>
      collectExtraFields(left?.[key], right?.[key], `${basePath}.${key}`),
    );
  };

  return [...schemaEntries, ...collectExtraFields(oldData, newData)];
};

const buildMedicalFileSummary = (
  detailsSummary?: string | null,
): MedicalFileSummary | null => {
  const rawLine = extractMedicalFileLine(detailsSummary);
  if (!rawLine) {
    return null;
  }

  const payload = extractMedicalFilePayload(rawLine);
  if (!payload) {
    return null;
  }

  try {
    const oldData = parsePythonLikeLiteral(payload.oldRaw) as Record<
      string,
      unknown
    >;
    const newData = parsePythonLikeLiteral(payload.newRaw) as Record<
      string,
      unknown
    >;
    const changes = getChangedFields(oldData, newData);
    const fieldEntries = flattenMedicalFields(oldData, newData).filter(
      (entry) => entry.path,
    );

    return {
      rawLine,
      oldData,
      newData,
      changes,
      fieldEntries,
      rawOldText: payload.oldRaw,
      rawNewText: payload.newRaw,
    };
  } catch {
    return null;
  }
};

const truncateLongText = (value: string, maxLength = 120) =>
  value.length > maxLength ? `${value.slice(0, maxLength)}...` : value;

const isPlainRecord = (value: unknown): value is Record<string, unknown> =>
  Boolean(value) && typeof value === "object" && !Array.isArray(value);

const renderValueCell = (
  value: unknown,
  changed: boolean,
  tone: "old" | "new" | "neutral",
  path: string,
  expandedTextPaths: string[],
  toggleExpandedText: (path: string) => void,
) => {
  const text = formatValue(value);
  const isLong = text.length > 120;
  const isExpanded = expandedTextPaths.includes(path);
  const toneClass =
    !changed || tone === "neutral"
      ? "px-1 py-2 text-slate-700"
      : tone === "old"
        ? "rounded-2xl border border-rose-200 bg-rose-50 px-3 py-2 text-rose-900"
        : "rounded-2xl border border-emerald-200 bg-emerald-50 px-3 py-2 text-emerald-900";

  return (
    <div className={toneClass}>
      <p className="whitespace-pre-wrap break-words">
        {isLong && !isExpanded ? truncateLongText(text) : text}
      </p>
      {isLong ? (
        <button
          type="button"
          onClick={() => toggleExpandedText(path)}
          className="mt-2 text-xs font-semibold text-cyan-700 transition hover:text-cyan-800"
        >
          {isExpanded ? "Voir moins" : "Voir plus"}
        </button>
      ) : null}
    </div>
  );
};

const renderPrimitiveComparisonRow = (
  path: string,
  label: string,
  oldValue: unknown,
  newValue: unknown,
  expandedTextPaths: string[],
  toggleExpandedText: (path: string) => void,
) => {
  const changed = !areValuesEqual(oldValue, newValue);

  return (
    <div
      key={path}
      className={`grid grid-cols-[180px_1fr_1fr] gap-3 px-4 py-3 text-sm ${changed ? "border-l-4 border-l-sky-500 bg-sky-50/30" : "text-slate-700"}`}
    >
      <div className="font-semibold text-slate-900">{label}</div>
      {renderValueCell(
        oldValue,
        changed,
        "old",
        `${path}.old`,
        expandedTextPaths,
        toggleExpandedText,
      )}
      {renderValueCell(
        newValue,
        changed,
        "new",
        `${path}.new`,
        expandedTextPaths,
        toggleExpandedText,
      )}
    </div>
  );
};

const getArrayFieldKeys = (
  path: string,
  oldValue: unknown,
  newValue: unknown,
) => {
  const configuredKeys = arrayFieldOrder[path];
  if (configuredKeys) {
    return configuredKeys;
  }

  const oldKeys = isPlainRecord(oldValue) ? Object.keys(oldValue) : [];
  const newKeys = isPlainRecord(newValue) ? Object.keys(newValue) : [];
  return Array.from(new Set([...oldKeys, ...newKeys])).filter(
    (key) => key !== "id",
  );
};

const renderArrayTable = (
  path: string,
  oldArray: unknown[],
  newArray: unknown[],
  expandedTextPaths: string[],
  toggleExpandedText: (path: string) => void,
) => {
  const maxLength = Math.max(oldArray.length, newArray.length);

  return (
    <div className="space-y-3">
      <div className="grid gap-3 md:grid-cols-2">
        <div className="rounded-2xl border border-slate-200 bg-slate-50/70 px-4 py-3">
          <p className="text-[11px] font-black uppercase tracking-[0.12em] text-slate-500">
            Avant
          </p>
          <p className="mt-2 text-sm font-semibold text-slate-900">
            {oldArray.length} élément(s)
          </p>
        </div>
        <div className="rounded-2xl border border-emerald-200 bg-emerald-50/70 px-4 py-3">
          <p className="text-[11px] font-black uppercase tracking-[0.12em] text-emerald-600">
            Après
          </p>
          <p className="mt-2 text-sm font-semibold text-emerald-900">
            {newArray.length} élément(s)
          </p>
        </div>
      </div>

      {maxLength === 0 ? (
        <div className="rounded-2xl border border-dashed border-slate-200 bg-white px-4 py-4 text-sm text-slate-500">
          Non renseigné
        </div>
      ) : null}

      {Array.from({ length: maxLength }, (_, index) => {
        const oldValue = oldArray[index];
        const newValue = newArray[index];
        const changed = !areValuesEqual(oldValue, newValue);
        const itemPath = `${path}.${index}`;
        const itemKeys = getArrayFieldKeys(path, oldValue, newValue);

        if (!isPlainRecord(oldValue) && !isPlainRecord(newValue)) {
          return (
            <div
              key={itemPath}
              className={`overflow-hidden rounded-2xl border border-slate-200 bg-white ${changed ? "border-l-4 border-l-sky-500" : ""}`}
            >
              <div className="border-b border-slate-200 bg-slate-50/80 px-4 py-3 text-sm font-black text-slate-900">
                {path === "auditTrail"
                  ? `Activité ${index + 1}`
                  : `Élément ${index + 1}`}
              </div>
              <div className="divide-y divide-slate-100">
                {renderPrimitiveComparisonRow(
                  itemPath,
                  path === "auditTrail" ? "Activité" : "Valeur",
                  oldValue,
                  newValue,
                  expandedTextPaths,
                  toggleExpandedText,
                )}
              </div>
            </div>
          );
        }

        return (
          <div
            key={itemPath}
            className={`overflow-hidden rounded-2xl border border-slate-200 bg-white ${changed ? "border-l-4 border-l-sky-500" : ""}`}
          >
            <div className="flex items-center justify-between gap-3 border-b border-slate-200 bg-slate-50/80 px-4 py-3">
              <p className="text-sm font-black text-slate-900">
                {path === "auditTrail"
                  ? `Activité ${index + 1}`
                  : `Élément ${index + 1}`}
              </p>
              {changed ? (
                <Badge tone="active">Modifié</Badge>
              ) : (
                <span className="text-xs font-semibold text-slate-500">
                  Identique
                </span>
              )}
            </div>
            <div className="grid grid-cols-[180px_1fr_1fr] gap-3 border-b border-slate-200 bg-slate-50/70 px-4 py-3 text-[11px] font-black uppercase tracking-[0.12em] text-slate-500">
              <span>Champ</span>
              <span>Avant</span>
              <span>Après</span>
            </div>
            <div className="divide-y divide-slate-100">
              {itemKeys.length > 0 ? (
                itemKeys.map((key) =>
                  renderPrimitiveComparisonRow(
                    `${itemPath}.${key}`,
                    formatFieldLabel(`${path}.${key}`),
                    isPlainRecord(oldValue) ? oldValue[key] : undefined,
                    isPlainRecord(newValue) ? newValue[key] : undefined,
                    expandedTextPaths,
                    toggleExpandedText,
                  ),
                )
              ) : (
                <div className="px-4 py-4 text-sm text-slate-500">
                  Non renseigné
                </div>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
};

const renderFieldRow = (
  entry: MedicalFieldEntry,
  expandedTextPaths: string[],
  toggleExpandedText: (path: string) => void,
) => {
  const oldValue = entry.oldValue;
  const newValue = entry.newValue;

  if (Array.isArray(oldValue) || Array.isArray(newValue)) {
    return (
      <div
        key={entry.path}
        className={`rounded-2xl border border-slate-200 bg-white p-4 ${entry.changed ? "border-l-4 border-l-sky-500" : ""}`}
      >
        <p className="mb-3 text-sm font-black text-slate-900">{entry.label}</p>
        {renderArrayTable(
          entry.path,
          Array.isArray(oldValue) ? oldValue : [],
          Array.isArray(newValue) ? newValue : [],
          expandedTextPaths,
          toggleExpandedText,
        )}
      </div>
    );
  }

  return renderPrimitiveComparisonRow(
    entry.path,
    entry.label,
    oldValue,
    newValue,
    expandedTextPaths,
    toggleExpandedText,
  );
};

const renderMedicalFileSummary = (
  summary: MedicalFileSummary,
  expandedTextPaths: string[],
  toggleExpandedText: (path: string) => void,
) => {
  const workerName =
    `${String(summary.newData.firstName || summary.oldData.firstName || "").trim()} ${String(summary.newData.lastName || summary.oldData.lastName || "").trim()}`.trim() ||
    "Non renseigné";
  const fileNumber = String(
    summary.newData.medicalFileNumber ||
      summary.oldData.medicalFileNumber ||
      "Non renseigné",
  );
  const employeeCode = String(
    summary.newData.employeeCode ||
      summary.oldData.employeeCode ||
      "Non renseigné",
  );
  const companyName = String(
    summary.newData.companyName ||
      summary.oldData.companyName ||
      "Non renseigné",
  );
  const siteName = String(
    summary.newData.siteName || summary.oldData.siteName || "Non renseigné",
  );
  const doctorName = String(
    summary.newData.confirmationDoctor ||
      summary.newData.internalVisitDoctor ||
      summary.oldData.confirmationDoctor ||
      "Non renseigné",
  );
  const status = String(
    summary.newData.confirmationStatus ||
      summary.newData.status ||
      summary.oldData.confirmationStatus ||
      "Confirmée",
  );
  const locked = Boolean(summary.newData.isLocked ?? summary.oldData.isLocked);

  const sections = medicalSections.map((section) => {
    const rows = summary.fieldEntries.filter(
      (entry) => entry.section === section,
    );
    const changedCount = rows.filter((entry) => entry.changed).length;
    return { section, rows, changedCount };
  });

  const copyValue = async (value: string) => {
    if (navigator?.clipboard?.writeText) {
      await navigator.clipboard.writeText(value);
    }
  };

  return (
    <div className="space-y-4">
      <div className="rounded-3xl border border-slate-200 bg-white shadow-sm">
        <div className="rounded-t-3xl border-b border-slate-200 bg-gradient-to-r from-cyan-50 via-white to-emerald-50 px-5 py-4">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <div className="flex items-center gap-2">
                <FileText className="h-5 w-5 text-cyan-700" />
                <p className="text-base font-black text-slate-950">
                  Dossier médical modifié
                </p>
              </div>
              <p className="mt-2 text-sm font-semibold text-slate-700">
                {fileNumber} · {employeeCode}
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              <Badge tone="completed">
                {summary.changes.length} champs modifiés
              </Badge>
              <Badge tone={locked ? "completed" : "inactive"}>
                {locked ? "Dossier verrouillé" : "Dossier ouvert"}
              </Badge>
            </div>
          </div>
        </div>

        <div className="grid gap-3 px-5 py-5 md:grid-cols-2 xl:grid-cols-3">
          <div className="rounded-2xl border border-slate-200 bg-slate-50/70 px-4 py-3">
            <p className="flex items-center gap-2 text-sm font-semibold text-slate-900">
              <User className="h-4 w-4 text-cyan-700" />
              Travailleur
            </p>
            <p className="mt-2 text-sm text-slate-700">{workerName}</p>
          </div>
          <div className="rounded-2xl border border-slate-200 bg-slate-50/70 px-4 py-3">
            <p className="flex items-center gap-2 text-sm font-semibold text-slate-900">
              <Building2 className="h-4 w-4 text-cyan-700" />
              Entreprise
            </p>
            <p className="mt-2 text-sm text-slate-700">{companyName}</p>
          </div>
          <div className="rounded-2xl border border-slate-200 bg-slate-50/70 px-4 py-3">
            <p className="flex items-center gap-2 text-sm font-semibold text-slate-900">
              <MapPin className="h-4 w-4 text-cyan-700" />
              Site
            </p>
            <p className="mt-2 text-sm text-slate-700">{siteName}</p>
          </div>
          <div className="rounded-2xl border border-slate-200 bg-slate-50/70 px-4 py-3">
            <p className="flex items-center gap-2 text-sm font-semibold text-slate-900">
              <Stethoscope className="h-4 w-4 text-cyan-700" />
              Médecin
            </p>
            <p className="mt-2 text-sm text-slate-700">{doctorName}</p>
          </div>
          <div className="rounded-2xl border border-slate-200 bg-slate-50/70 px-4 py-3">
            <p className="flex items-center gap-2 text-sm font-semibold text-slate-900">
              <CheckCircle className="h-4 w-4 text-emerald-600" />
              Statut
            </p>
            <p className="mt-2 text-sm text-slate-700">{status}</p>
          </div>
          <div className="rounded-2xl border border-slate-200 bg-slate-50/70 px-4 py-3">
            <p className="flex items-center gap-2 text-sm font-semibold text-slate-900">
              <Lock className="h-4 w-4 text-slate-600" />
              Verrouillé
            </p>
            <p className="mt-2 text-sm text-slate-700">
              {locked ? "Oui" : "Non"}
            </p>
          </div>
        </div>

        <div className="flex flex-wrap gap-2 px-5 pb-5">
          <button
            type="button"
            onClick={() => void copyValue(fileNumber)}
            className="inline-flex items-center gap-2 rounded-2xl border border-slate-200 bg-white px-3 py-2 text-xs font-semibold text-slate-700 transition hover:border-cyan-200 hover:text-cyan-700"
          >
            <Copy className="h-3.5 w-3.5" />
            Copier N° dossier
          </button>
          <button
            type="button"
            onClick={() => void copyValue(employeeCode)}
            className="inline-flex items-center gap-2 rounded-2xl border border-slate-200 bg-white px-3 py-2 text-xs font-semibold text-slate-700 transition hover:border-cyan-200 hover:text-cyan-700"
          >
            <Copy className="h-3.5 w-3.5" />
            Copier code employé
          </button>
        </div>
      </div>

      {sections.map(({ section, rows, changedCount }) => (
        <details
          key={section}
          open
          className="rounded-3xl border border-slate-200 bg-white shadow-sm"
        >
          <summary className="cursor-pointer list-none rounded-t-3xl border-b border-slate-200 bg-slate-50/80 px-5 py-4 text-sm font-black text-slate-900">
            <div className="flex flex-wrap items-center gap-2">
              <span>▼ {section}</span>
              <span className="text-slate-500">· {rows.length} champs</span>
              <span className="text-cyan-700">· {changedCount} modifiés</span>
            </div>
          </summary>
          <div className="overflow-hidden">
            <div className="grid grid-cols-[180px_1fr_1fr] gap-3 border-b border-slate-200 bg-slate-50/70 px-4 py-3 text-[11px] font-black uppercase tracking-[0.12em] text-slate-500">
              <span>Champ</span>
              <span>Avant</span>
              <span>Après</span>
            </div>
            <div className="divide-y divide-slate-100">
              {rows.length > 0 ? (
                rows.map((entry) =>
                  renderFieldRow(entry, expandedTextPaths, toggleExpandedText),
                )
              ) : (
                <div className="px-4 py-4 text-sm text-slate-500">
                  Aucun champ disponible
                </div>
              )}
            </div>
          </div>
        </details>
      ))}
    </div>
  );
};

export const AuditActivityList = ({
  items,
}: {
  items: DashboardAuditItem[];
}) => {
  const entityLabelMap: Record<string, string> = {
    campaign: "Campagne",
    company: "Entreprise",
    branch: "Filiale",
    drilling_site: "Site de forage",
    user: "Administration",
    campaign_test: "Tests médicaux inclus dans la campagne",
    doctor: "Médecin",
    campaign_doctor: "Médecin",
    assistant: "Assistant",
    campaign_assistant: "Assistant",
    worker: "Travailleur",
    campaign_worker: "Travailleur",
    import_job: "Import nominatif",
  };

  const roleLabels: Record<string, string> = {
    Admin: "Administration",
    admin: "Administration",
    "Super Admin": "Administration",
    super_admin: "Administration",
    Doctor: "Médecin",
    doctor: "Médecin",
    Assistant: "Assistant",
    assistant: "Assistant",
  };

  const [searchFilter, setSearchFilter] = useState("");
  const [userFilter, setUserFilter] = useState("all");
  const [actionFilter, setActionFilter] = useState("all");
  const [dateFilter, setDateFilter] = useState("");
  const [expandedItemIds, setExpandedItemIds] = useState<number[]>([]);
  const [expandedTextPaths, setExpandedTextPaths] = useState<string[]>([]);

  const userOptions = useMemo(
    () => [
      { label: "Tous les utilisateurs", value: "all" },
      ...Array.from(
        new Set(
          items.map((item) => item.actor_name).filter(Boolean) as string[],
        ),
      ).map((name) => ({ label: name, value: name })),
    ],
    [items],
  );

  const actionOptions = useMemo(
    () => [
      { label: "Toutes les actions", value: "all" },
      ...Array.from(new Set(items.map((item) => item.action))).map(
        (action) => ({
          label: getActivityLabel(action),
          value: action,
        }),
      ),
    ],
    [items],
  );

  const filteredItems = useMemo(
    () =>
      items.filter((item) => {
        const actorName = item.actor_name || "Utilisateur système";
        const matchesUser = userFilter === "all" || actorName === userFilter;
        const matchesAction =
          actionFilter === "all" || item.action === actionFilter;
        const matchesDate =
          !dateFilter || item.created_at.slice(0, 10) === dateFilter;
        const searchableText = [
          item.actor_name,
          item.actor_role,
          item.entity_name,
          item.entity_type,
          item.action,
          item.details_summary,
          item.ip_address,
        ]
          .filter(Boolean)
          .join(" ")
          .toLowerCase();
        const matchesSearch =
          !searchFilter.trim() ||
          searchableText.includes(searchFilter.trim().toLowerCase());
        return matchesUser && matchesAction && matchesDate && matchesSearch;
      }),
    [actionFilter, dateFilter, items, searchFilter, userFilter],
  );

  const summary = useMemo(() => {
    const countBy = (keywords: string[]) =>
      items.filter((item) =>
        keywords.some((keyword) => item.action.toLowerCase().includes(keyword)),
      ).length;

    return {
      total: items.length,
      creates: countBy(["create", "add"]),
      updates: countBy(["update", "edit", "assign"]),
      deletes: countBy(["delete", "remove"]),
      syncs: countBy(["sync", "import", "export"]),
    };
  }, [items]);

  const toggleExpandedItem = (itemId: number) => {
    setExpandedItemIds((current) =>
      current.includes(itemId)
        ? current.filter((id) => id !== itemId)
        : [...current, itemId],
    );
  };

  const toggleExpandedText = (path: string) => {
    setExpandedTextPaths((current) =>
      current.includes(path)
        ? current.filter((item) => item !== path)
        : [...current, path],
    );
  };

  return (
    <Card className="h-full overflow-hidden border border-slate-200/80 bg-white/90 shadow-soft">
      <div className="border-b border-slate-200/80 bg-gradient-to-r from-white via-cyan-50/40 to-white px-5 py-5">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <h3 className="text-xl font-semibold text-navy-900">
              Journal d'activité
            </h3>
            <p className="mt-1 text-sm text-ink-500">
              Historique récent des actions administratives, médicales et
              système.
            </p>
          </div>
          <Badge tone="active">Suivi actif</Badge>
        </div>

        <div className="mt-5 grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-5">
          {[
            {
              label: "Total activités",
              value: summary.total,
              icon: Activity,
              iconClassName: "border-slate-200 bg-slate-100 text-slate-700",
              accentClassName: "from-slate-500 to-slate-700",
            },
            {
              label: "Créations",
              value: summary.creates,
              icon: PlusCircle,
              iconClassName:
                "border-emerald-100 bg-emerald-50 text-emerald-600",
              accentClassName: "from-emerald-400 to-emerald-600",
            },
            {
              label: "Modifications",
              value: summary.updates,
              icon: Pencil,
              iconClassName: "border-sky-100 bg-sky-50 text-sky-600",
              accentClassName: "from-sky-400 to-sky-600",
            },
            {
              label: "Suppressions",
              value: summary.deletes,
              icon: Trash2,
              iconClassName: "border-rose-100 bg-rose-50 text-rose-600",
              accentClassName: "from-rose-400 to-rose-600",
            },
            {
              label: "Synchronisations",
              value: summary.syncs,
              icon: RefreshCw,
              iconClassName: "border-cyan-100 bg-cyan-50 text-cyan-600",
              accentClassName: "from-cyan-400 to-cyan-600",
            },
          ].map((item) => (
            <div
              key={item.label}
              className="group relative overflow-hidden rounded-2xl border border-slate-200/80 bg-white p-4 shadow-sm transition duration-200 hover:-translate-y-0.5 hover:border-slate-300 hover:shadow-lg hover:shadow-slate-900/[0.06]"
            >
              <div
                className={`absolute inset-x-0 top-0 h-0.5 bg-gradient-to-r ${item.accentClassName}`}
              />

              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <p className="truncate text-[11px] font-bold uppercase tracking-[0.11em] text-slate-500">
                    {item.label}
                  </p>
                  <p className="mt-2 text-2xl font-black tracking-tight text-slate-950">
                    {formatNumber(item.value)}
                  </p>
                </div>

                <div
                  className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border transition duration-200 group-hover:scale-105 ${item.iconClassName}`}
                >
                  <item.icon className="h-[18px] w-[18px]" strokeWidth={2} />
                </div>
              </div>
            </div>
          ))}
        </div>

        <div className="mt-5 rounded-2xl border border-slate-200/80 bg-white/80 p-4 shadow-sm backdrop-blur-sm">
          <div className="mb-4 flex flex-col gap-1 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <h4 className="text-sm font-bold text-slate-900">
                Recherche et filtres
              </h4>
              <p className="mt-1 text-xs text-slate-500">
                Affinez l’historique par utilisateur, action, date ou mot-clé.
              </p>
            </div>
            <p className="text-xs font-semibold text-slate-500">
              {formatNumber(filteredItems.length)} résultat
              {filteredItems.length > 1 ? "s" : ""}
            </p>
          </div>

          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
            <Input
              label="Recherche"
              value={searchFilter}
              onChange={(event) => setSearchFilter(event.target.value)}
              placeholder="Utilisateur, entité, adresse IP..."
            />
            <Select
              label="Utilisateur"
              options={userOptions}
              value={userFilter}
              onChange={(event) => setUserFilter(event.target.value)}
            />
            <Select
              label="Action"
              options={actionOptions}
              value={actionFilter}
              onChange={(event) => setActionFilter(event.target.value)}
            />
            <Input
              label="Date"
              type="date"
              value={dateFilter}
              onChange={(event) => setDateFilter(event.target.value)}
              className="h-11"
            />
          </div>
        </div>
      </div>

      {filteredItems.length === 0 ? (
        <div className="px-5 py-8">
          <div className="rounded-[1.8rem] border border-slate-200 bg-white px-6 py-14 text-center shadow-xl shadow-slate-950/[0.03]">
            <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-[1.4rem] border border-cyan-100 bg-cyan-50 text-cyan-700 shadow-sm">
              <Database className="h-7 w-7" />
            </div>
            <h3 className="mt-6 text-2xl font-black tracking-tight text-slate-950">
              Aucune activité disponible
            </h3>
            <p className="mx-auto mt-3 max-w-md text-sm leading-7 text-slate-500">
              Les événements de sécurité, de synchronisation et d'administration
              apparaîtront ici dans un journal premium.
            </p>
          </div>
        </div>
      ) : (
        <div className="px-5 py-5">
          <div className="relative space-y-4 before:absolute before:bottom-3 before:left-[23px] before:top-3 before:w-px before:bg-gradient-to-b before:from-cyan-200 before:via-slate-200 before:to-slate-100">
            {filteredItems.map((item) => {
              const hasDetails = Boolean(item.details_summary);
              const isExpanded = expandedItemIds.includes(item.id);
              const metadata = formatMetadata(item.details_summary);
              const medicalFileSummary = buildMedicalFileSummary(
                item.details_summary,
              );
              const previewDetails = metadata.preview
                ? isExpanded || metadata.preview.length <= 160
                  ? metadata.preview
                  : `${metadata.preview.slice(0, 160)}...`
                : null;
              const tone = getActivityTone(item.action);
              const Icon = getActivityIcon(item.action);
              const actionLabel = getActivityLabel(item.action);
              const actorName = item.actor_name || "Utilisateur système";
              const actorRole =
                roleLabels[item.actor_role || ""] ||
                item.actor_role ||
                "Système";
              const entityLabel =
                entityLabelMap[item.entity_type] || item.entity_type;
              const entityName = item.entity_name || entityLabel;

              return (
                <div key={item.id} className="relative pl-14">
                  <div
                    className={`absolute left-0 top-5 flex h-11 w-11 items-center justify-center rounded-2xl border shadow-sm ${tone.iconWrap}`}
                  >
                    <Icon className="h-5 w-5" />
                  </div>
                  <div
                    className={`absolute left-[18px] top-[58px] h-3 w-3 rounded-full ${tone.dot} ${tone.ring}`}
                  />

                  <div
                    className={`rounded-3xl border border-slate-200/80 border-l-4 bg-white/95 px-5 py-4 shadow-sm transition duration-200 hover:-translate-y-0.5 hover:shadow-md ${tone.accent} ${tone.hover}`}
                  >
                    <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                      <div className="min-w-0">
                        <div className="flex flex-wrap items-center gap-2">
                          <Badge tone={tone.badgeTone}>{actionLabel}</Badge>
                          <span className="rounded-full bg-slate-100 px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.14em] text-ink-500">
                            {entityLabel}
                          </span>
                          <span className="rounded-full bg-slate-100 px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.14em] text-ink-500">
                            {actorRole}
                          </span>
                        </div>

                        <div className="mt-3 flex flex-wrap items-center gap-2 text-sm text-ink-600">
                          <span className="font-semibold text-navy-900">
                            {actorName}
                          </span>
                          <span className="text-slate-300">?</span>
                          <span className="font-medium text-slate-700">
                            {entityName}
                          </span>
                          {item.entity_id ? (
                            <span className="text-xs font-semibold uppercase tracking-[0.12em] text-slate-400">
                              #{item.entity_id}
                            </span>
                          ) : null}
                        </div>

                        <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-2 text-xs text-ink-400">
                          <span className="inline-flex items-center gap-1.5">
                            <Clock className="h-3.5 w-3.5" />
                            {formatDateTime(item.created_at)}
                          </span>
                          <span className="inline-flex items-center gap-1.5">
                            <User className="h-3.5 w-3.5" />
                            {actorRole}
                          </span>
                          {item.ip_address ? (
                            <span className="inline-flex items-center gap-1.5">
                              <ShieldCheck className="h-3.5 w-3.5" />
                              IP {item.ip_address}
                            </span>
                          ) : null}
                        </div>

                        {previewDetails && !medicalFileSummary ? (
                          <div className="mt-3 rounded-2xl border border-slate-200/80 bg-slate-50/80 px-3 py-3">
                            <p className="text-sm leading-6 text-ink-600">
                              {previewDetails}
                            </p>
                          </div>
                        ) : null}
                      </div>

                      <div className="flex items-center gap-2">
                        {hasDetails ? (
                          <button
                            type="button"
                            onClick={() => toggleExpandedItem(item.id)}
                            className="inline-flex items-center gap-1.5 rounded-2xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm font-semibold text-slate-700 transition hover:border-cyan-200 hover:bg-cyan-50 hover:text-cyan-700"
                          >
                            <span>Détails</span>
                            {isExpanded ? (
                              <ChevronUp className="h-4 w-4" />
                            ) : (
                              <ChevronDown className="h-4 w-4" />
                            )}
                          </button>
                        ) : null}
                      </div>
                    </div>

                    {hasDetails && isExpanded ? (
                      <div className="mt-4 rounded-3xl border border-slate-200 bg-slate-50/90 p-4">
                        {medicalFileSummary ? (
                          <>
                            <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
                              <Badge tone="completed">
                                Dossier médical modifié
                              </Badge>
                              <button
                                type="button"
                                onClick={() => toggleExpandedItem(item.id)}
                                className="text-xs font-semibold text-slate-600 transition hover:text-slate-900"
                              >
                                Masquer les détails
                              </button>
                            </div>
                            {renderMedicalFileSummary(
                              medicalFileSummary,
                              expandedTextPaths,
                              toggleExpandedText,
                            )}
                          </>
                        ) : (
                          <div className="space-y-3">
                            <div className="rounded-2xl border border-white bg-white px-4 py-3 shadow-sm">
                              <p className="text-[11px] font-black uppercase tracking-[0.12em] text-slate-500">
                                Contexte
                              </p>
                              <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-2 text-sm text-slate-600">
                                <p className="flex items-center gap-2">
                                  <User className="h-4 w-4 text-slate-400" />
                                  <span className="font-semibold text-slate-900">
                                    {actorName}
                                  </span>
                                </p>
                                {item.ip_address ? (
                                  <p className="flex items-center gap-2">
                                    <ShieldCheck className="h-4 w-4 text-slate-400" />
                                    <span>IP: {item.ip_address}</span>
                                  </p>
                                ) : null}
                                {item.entity_id ? (
                                  <p className="flex items-center gap-2">
                                    <Database className="h-4 w-4 text-slate-400" />
                                    <span>ID entité: {item.entity_id}</span>
                                  </p>
                                ) : null}
                                {metadata.source ? (
                                  <p className="flex items-center gap-2">
                                    <Activity className="h-4 w-4 text-slate-400" />
                                    <span>Source: {metadata.source}</span>
                                  </p>
                                ) : null}
                                {metadata.device ? (
                                  <p className="flex items-center gap-2">
                                    <Settings className="h-4 w-4 text-slate-400" />
                                    <span>Appareil: {metadata.device}</span>
                                  </p>
                                ) : null}
                              </div>
                            </div>

                            <div className="rounded-2xl border border-white bg-white px-4 py-3 shadow-sm">
                              <p className="text-[11px] font-black uppercase tracking-[0.12em] text-slate-500">
                                Détails
                              </p>
                              <div className="mt-3 space-y-3 text-sm text-slate-600">
                                {metadata.oldValue ? (
                                  <div>
                                    <p className="font-semibold text-slate-900">
                                      Ancienne valeur
                                    </p>
                                    <p className="mt-1 rounded-2xl bg-slate-50 px-3 py-2 text-xs text-slate-600">
                                      {metadata.oldValue}
                                    </p>
                                  </div>
                                ) : null}
                                {metadata.newValue ? (
                                  <div>
                                    <p className="font-semibold text-slate-900">
                                      Nouvelle valeur
                                    </p>
                                    <p className="mt-1 rounded-2xl bg-emerald-50 px-3 py-2 text-xs text-emerald-700">
                                      {metadata.newValue}
                                    </p>
                                  </div>
                                ) : null}
                                {!metadata.oldValue &&
                                !metadata.newValue &&
                                metadata.notes.length > 0 ? (
                                  <div className="space-y-2">
                                    {metadata.notes.map((line, index) => (
                                      <p
                                        key={`${item.id}-note-${index}`}
                                        className="rounded-2xl bg-slate-50 px-3 py-2 text-xs text-slate-600"
                                      >
                                        {line}
                                      </p>
                                    ))}
                                  </div>
                                ) : null}
                              </div>
                            </div>
                          </div>
                        )}
                      </div>
                    ) : null}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </Card>
  );
};

export const normalizeCampaignStatusTone = (status: string) => {
  if (status === "active") return "active";
  if (status === "completed") return "complété";
  if (status === "draft") return "brouillon";
  return "inactive";
};

export const normalizeImportStatusTone = (status: string) => {
  if (status === "uploaded" || status === "mapped" || status === "validated")
    return "pending";
  if (status === "confirmed" || status === "completed") return "completed";
  if (status === "failed") return "failed";
  return "inactive";
};

export const fallbackAdminDashboardData = (): AdminDashboardData => ({
  total_users: 13,
  total_doctors: 4,
  total_assistants: 8,
  total_companies: 10,
  total_branches: 100,
  total_drilling_sites: 200,
  total_workers: 500,
  total_campaigns: 30,
  active_campaigns: 7,
  completed_campaigns: 10,
  total_medical_tests: 10,
  total_worker_tests: 120,
  abnormal_results: 18,
  pending_imports: 3,
  recent_campaigns: [
    {
      id: 1,
      company_id: 1,
      branch_id: 1,
      title: "Demo Company 01 Occupational Campaign 1",
      doctor_name: "Dr. Sarah Hassan",
      company_name: "Demo Company 01",
      branch_name: "North Field Branch 01",
      status: "active",
      start_date: new Date().toISOString(),
      end_date: new Date(Date.now() + 5 * 86400000).toISOString(),
      doctors_count: 2,
      worker_count: 42,
      tests_count: 6,
      assistants_count: 2,
      doctor_names: ["Dr. Sarah Hassan", "Dr. Khaled Mansouri"],
      worker_names: [
        "Ali Mansour",
        "Karim Bensaid",
        "Yacine Farouk",
        "Samir Hadi",
      ],
      test_names: ["CBC", "Blood Pressure", "Blood Sugar", "ECG"],
      assistant_names: ["Assistant Demo 01", "Assistant Demo 02"],
    },
    {
      id: 2,
      company_id: 2,
      branch_id: 12,
      title: "Demo Company 02 Occupational Campaign 1",
      doctor_name: "Dr. Ahmed Karim",
      company_name: "Demo Company 02",
      branch_name: "South Operations Branch",
      status: "completed",
      start_date: new Date(Date.now() - 12 * 86400000).toISOString(),
      end_date: new Date(Date.now() - 6 * 86400000).toISOString(),
      doctors_count: 1,
      worker_count: 31,
      tests_count: 5,
      assistants_count: 1,
      doctor_names: ["Dr. Ahmed Karim"],
      worker_names: ["Nabil Rahal", "Sofiane Khelif", "Adel Mokrani"],
      test_names: ["Vision Test", "Audiometry", "Urinalysis"],
      assistant_names: ["Assistant Demo 03"],
    },
  ],
  recent_imports: [
    {
      id: 1,
      file_name: "workers-demo-batch.xlsx",
      status: "validated",
      total_rows: 250,
      created_at: new Date().toISOString(),
    },
    {
      id: 2,
      file_name: "campaign-participants.xlsx",
      status: "uploaded",
      total_rows: 120,
      created_at: new Date(Date.now() - 86400000).toISOString(),
    },
  ],
  recent_audit_logs: [
    {
      id: 1,
      action: "CREATE",
      actor_name: "Medical User",
      actor_email: "admin@ibnsina.com",
      actor_role: "admin",
      entity_type: "campaign",
      entity_id: 1,
      entity_name: "Demo Company 01 Occupational Campaign 1",
      ip_address: "127.0.0.1",
      details_summary: "Created new occupational campaign | Status: active",
      created_at: new Date().toISOString(),
    },
    {
      id: 2,
      action: "IMPORT",
      actor_name: "Assistant Demo 01",
      actor_email: "assistant1@demo.ibnsina.com",
      actor_role: "assistant",
      entity_type: "worker",
      entity_id: 2,
      ip_address: "127.0.0.1",
      details_summary: "Imported worker batch | Total Rows: 120",
      created_at: new Date(Date.now() - 2 * 3600000).toISOString(),
    },
  ],
});

export type RecentCampaignRow = DashboardCampaignItem;
export type RecentImportRow = DashboardImportItem;
