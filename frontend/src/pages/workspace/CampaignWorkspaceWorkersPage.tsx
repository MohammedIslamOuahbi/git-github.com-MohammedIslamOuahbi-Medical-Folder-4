import { useEffect, useMemo, useState } from "react";
import {
  BriefcaseMedical,
  CalendarCheck,
  FileText,
  Plus,
  Search,
  UserCheck,
  Users,
} from "lucide-react";
import { useNavigate } from "react-router-dom";

import { campaignsApi } from "@/api/campaignsApi";
import { medicalVisitsApi } from "@/api/medicalVisitsApi";
import { Badge } from "@/components/common/Badge";
import { Button } from "@/components/common/Button";
import { Card } from "@/components/common/Card";
import { DataTable } from "@/components/common/DataTable";
import { EmptyState } from "@/components/common/EmptyState";
import { SearchInput } from "@/components/common/SearchInput";
import { SectionHeader } from "@/components/common/SectionHeader";
import { Spinner } from "@/components/common/Spinner";
import { WORKER_ETAT_ACTUAL_OPTIONS } from "@/constants/workerEtatActual";
import { formatDisplayDate } from "@/utils/date";
import { cn } from "@/utils/cn";
import { useCampaignWorkspace } from "@/context/CampaignWorkspaceContext";
import type { MedicalVisit, Worker } from "@/types/entities";

const StatCard = ({
  label,
  value,
  percentage,
  icon: Icon,
}: {
  label: string;
  value: number;
  percentage: number;
  icon: React.ElementType;
}) => (
  <Card className="p-5">
    <div className="flex items-start justify-between">
      <div>
        <p className="text-xs font-bold uppercase tracking-wide text-slate-500">
          {label}
        </p>

        <p className="mt-2 text-2xl font-black text-slate-950">
          {value}
        </p>

        <p className="mt-1 text-xs font-medium text-slate-500">
          {percentage}% du total
        </p>
      </div>

      <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-cyan-50 text-cyan-700">
        <Icon className="h-5 w-5" />
      </div>
    </div>

    <div className="mt-4 h-2 rounded-full bg-slate-100">
      <div
        className="h-2 rounded-full bg-cyan-600"
        style={{ width: `${percentage}%` }}
      />
    </div>
  </Card>
);

const ETAT_ACTUAL_LABELS = Object.fromEntries(
  WORKER_ETAT_ACTUAL_OPTIONS.map((option) => [option.value, option.label]),
) as Record<string, string>;

const normalizeWorkerEtatActual = (value: string) => {
  const normalized = value.trim().toLowerCase();

  if (normalized === "conge_maladie") return "sick_leave";
  if (normalized === "recuperation") return "recovery";
  if (normalized === "accident_travail") return "work_accident";
  if (normalized === "conge_sans_solde") return "unpaid_leave";

  return normalized;
};

const getWorkerEtatActual = (worker: Worker) => {
  const medicalFileData =
    worker.medical_file_data && typeof worker.medical_file_data === "object"
      ? (worker.medical_file_data as Record<string, unknown>)
      : null;
  const raw =
    worker.etat_actual ??
    medicalFileData?.etat_actual ??
    medicalFileData?.etat_actuale ??
    "present";

  return normalizeWorkerEtatActual(String(raw || "present"));
};

const getWorkerMedicalFolderStatus = (worker: Worker) => {
  const workerRecord = worker as Worker & {
    medical_file_status?: string | null;
    medicalFileStatus?: string | null;
  };
  const medicalFileData =
    worker.medical_file_data && typeof worker.medical_file_data === "object"
      ? (worker.medical_file_data as Record<string, unknown>)
      : null;
  const raw =
    workerRecord.medical_file_status ??
    workerRecord.medicalFileStatus ??
    medicalFileData?.confirmationStatus ??
    medicalFileData?.status ??
    medicalFileData?.validationStatus ??
    "";

  const normalized = String(raw).trim().toLowerCase();

  if (["validated", "confirmed", "validé", "valide"].includes(normalized)) {
    return "validated" as const;
  }

  if (["draft", "brouillon"].includes(normalized)) {
    return "draft" as const;
  }

  return "incomplete" as const;
};

const getWorkerLatestVisitDate = (worker: Worker) => {
  const workerRecord = worker as Worker & {
    medical_visits?: Array<{ visit_date?: string | null; visitDate?: string | null }> | null;
    medicalVisits?: Array<{ visit_date?: string | null; visitDate?: string | null }> | null;
    last_visit_date?: string | null;
    lastVisitDate?: string | null;
    latest_visit_date?: string | null;
  };

  const direct =
    workerRecord.latest_visit_date ??
    workerRecord.last_visit_date ??
    workerRecord.lastVisitDate;

  if (direct) return direct;

  const visits = workerRecord.medical_visits ?? workerRecord.medicalVisits ?? [];

  if (!Array.isArray(visits) || visits.length === 0) return "";

  const latest = visits
    .filter((visit) => visit.visit_date || visit.visitDate)
    .sort(
      (a, b) =>
        new Date(b.visit_date || b.visitDate || 0).getTime() -
        new Date(a.visit_date || a.visitDate || 0).getTime(),
    )[0];

  return latest?.visit_date ?? latest?.visitDate ?? "";
};

const EtatActualBadge = ({ value }: { value: string }) => {
  const label = ETAT_ACTUAL_LABELS[value] || value || "Présent";
  const toneClassName =
    value === "present"
      ? "border-emerald-200 bg-emerald-50 text-emerald-700"
      : value === "absence" || value === "suspended" || value === "terminated"
        ? "border-rose-200 bg-rose-50 text-rose-700"
        : "border-amber-200 bg-amber-50 text-amber-700";

  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full border px-2.5 py-1 text-[10px] font-black uppercase tracking-[0.14em] shadow-sm",
        toneClassName,
      )}
    >
      {label}
    </span>
  );
};

const MedicalFolderStatusBadge = ({
  status,
}: {
  status: "validated" | "draft" | "incomplete";
}) => {
  const config =
    status === "validated"
      ? { label: "Validé", tone: "completed" }
      : status === "draft"
        ? { label: "Brouillon", tone: "draft" }
        : { label: "Incomplet", tone: "pending" };

  return <Badge tone={config.tone}>{config.label}</Badge>;
};

export const CampaignWorkspaceWorkersPage = () => {
  const navigate = useNavigate();
  const { currentCampaign } = useCampaignWorkspace();

  const [workers, setWorkers] = useState<Worker[]>([]);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [notice, setNotice] = useState<string | null>(null);
  const [openingWorkerId, setOpeningWorkerId] = useState<number | null>(null);

  useEffect(() => {
    const sampleWorker = workers[0];
    if (!sampleWorker) return;
    console.log("[Workers][row]", {
      id: sampleWorker.id,
      latest_visit_date: sampleWorker.latest_visit_date,
      medical_file_status: sampleWorker.medical_file_status,
      visits: (sampleWorker as Worker & { medical_visits?: unknown; medicalVisits?: unknown }).medical_visits ??
        (sampleWorker as Worker & { medical_visits?: unknown; medicalVisits?: unknown }).medicalVisits,
      medical_file_data: sampleWorker.medical_file_data,
    });
    console.log("[Workers][status debug]", {
      id: sampleWorker.id,
      medical_file_status: sampleWorker.medical_file_status,
      confirmationStatus:
        sampleWorker.medical_file_data && typeof sampleWorker.medical_file_data === "object"
          ? (sampleWorker.medical_file_data as Record<string, unknown>).confirmationStatus
          : undefined,
      medical_file_data: sampleWorker.medical_file_data,
    });
  }, [workers]);

  useEffect(() => {
    if (!currentCampaign) return;

    const noticeKey = `campaign-workers-import-notice.${currentCampaign.id}`;
    const importNotice = window.sessionStorage.getItem(noticeKey);
    if (importNotice) {
      setNotice(importNotice);
      window.sessionStorage.removeItem(noticeKey);
    }

    let cancelled = false;

    const load = async () => {
      setLoading(true);

      try {
        const campaignWorkers = await campaignsApi.workers(currentCampaign.id);

        if (!cancelled) {
          setWorkers(campaignWorkers);
        }
      } catch {
        if (!cancelled) {
          setWorkers([]);
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    };

    void load();

    return () => {
      cancelled = true;
    };
  }, [currentCampaign]);

  const filteredWorkers = useMemo(
    () =>
      workers.filter((worker) =>
        `${worker.full_name} ${worker.employee_code} ${worker.position} ${worker.status}`
          .toLowerCase()
          .includes(search.toLowerCase()),
      ),
    [search, workers],
  );

  const stats = useMemo(() => {
    const total = workers.length || 1;

    const active = workers.filter((worker) => worker.status === "active").length;
    const withLastTest = workers.filter((worker) => worker.last_test_date).length;
    const filtered = filteredWorkers.length;

    const percent = (value: number) => Math.round((value / total) * 100);

    return {
      totalWorkers: workers.length,
      active,
      withLastTest,
      filtered,
      activePercent: percent(active),
      testedPercent: percent(withLastTest),
      filteredPercent: percent(filtered),
    };
  }, [workers, filteredWorkers]);

  const openWorkerMedicalWorkflow = async (worker: Worker) => {
    if (!currentCampaign || openingWorkerId) return;

    setOpeningWorkerId(worker.id);
    setNotice(null);

    try {
      const visits = await medicalVisitsApi.listByWorker(worker.id);
      const normalizedVisits = Array.isArray(visits) ? visits : [];
      const latestVisit = normalizedVisits
        .slice()
        .sort((a, b) => {
          const aTime = new Date(
            (a as MedicalVisit).visit_date || (a as MedicalVisit).created_at || 0,
          ).getTime();
          const bTime = new Date(
            (b as MedicalVisit).visit_date || (b as MedicalVisit).created_at || 0,
          ).getTime();
          if (aTime !== bTime) return bTime - aTime;
          return Number((b as MedicalVisit).id) - Number((a as MedicalVisit).id);
        })[0];

      if (latestVisit?.id) {
        navigate(
          `/app/workspace/${currentCampaign.id}/workers/${worker.id}/medical-visits/${latestVisit.id}`,
        );
        return;
      }

      const createdVisit = await medicalVisitsApi.create({
        worker_id: worker.id,
        campaign_id: currentCampaign.id,
        visit_date: new Date().toISOString().slice(0, 10),
        status: "draft",
        form_data: {},
      });

      navigate(
        `/app/workspace/${currentCampaign.id}/workers/${worker.id}/medical-visits/${createdVisit.id}`,
      );
    } catch (error) {
      console.error("[OpenWorkerMedicalWorkflow] failed", error);
      setNotice("Impossible d'ouvrir le dossier medical pour le moment.");
    } finally {
      setOpeningWorkerId(null);
    }
  };

  if (!currentCampaign) return null;

  if (loading) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center">
        <Spinner />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <SectionHeader
        eyebrow="Espace campagne"
        title="Travailleurs sur site"
        description="Consultez les travailleurs affectés à cette campagne médicale."
        actionLabel="Ajouter un travailleur"
        actionIcon={Plus}
        onAction={() =>
          navigate(`/app/workspace/${currentCampaign.id}/workers/create`)
        }
      />

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <StatCard
          label="Travailleurs affectés"
          value={stats.totalWorkers}
          percentage={100}
          icon={Users}
        />

        <StatCard
          label="Travailleurs actifs"
          value={stats.active}
          percentage={stats.activePercent}
          icon={UserCheck}
        />

        <StatCard
          label="Dossiers examinés"
          value={stats.withLastTest}
          percentage={stats.testedPercent}
          icon={BriefcaseMedical}
        />

        <StatCard
          label="Résultats affichés"
          value={stats.filtered}
          percentage={stats.filteredPercent}
          icon={Search}
        />
      </div>

      <Card className="p-5">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div className="flex items-center gap-3">
            <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-cyan-50 text-cyan-700">
              <CalendarCheck className="h-5 w-5" />
            </div>

            <div>
              <p className="text-xs font-bold uppercase tracking-wide text-cyan-700">
                Liste active
              </p>
              <h2 className="text-lg font-black text-slate-950">
                {workers.length} travailleurs affectés
              </h2>
            </div>
          </div>

          <div className="w-full lg:max-w-sm">
            <SearchInput
              value={search}
              onChange={setSearch}
              placeholder="Rechercher un travailleur..."
            />
          </div>
        </div>
      </Card>

      {notice ? (
        <div className="rounded-2xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm font-medium text-emerald-700">
          {notice}
        </div>
      ) : null}

      <DataTable
        rows={filteredWorkers}
        getRowKey={(row) => row.id}
        emptyState={
          <EmptyState
            title="Aucun travailleur trouvé"
            description="Affectez des travailleurs à cette campagne pour gérer les examens médicaux sur site."
          />
        }
        columns={[
          {
            key: "name",
            title: "Travailleur",
            render: (row) => (
              <div>
                <p className="font-semibold text-slate-900">{row.full_name}</p>
                <p className="text-xs text-slate-500">{row.employee_code}</p>
              </div>
            ),
          },
          {
            key: "position",
            title: "Poste",
            render: (row) => row.position || "-",
          },
          {
            key: "etat_actual",
            title: "État actuel",
            render: (row) => <EtatActualBadge value={getWorkerEtatActual(row)} />,
          },
          {
            key: "last_test",
            title: "Dernier examen",
            render: (row) =>
              getWorkerLatestVisitDate(row)
                ? formatDisplayDate(getWorkerLatestVisitDate(row))
                : "Aucun examen",
          },
          {
            key: "status",
            title: "Statut",
            render: (row) => (
              <MedicalFolderStatusBadge status={getWorkerMedicalFolderStatus(row)} />
            ),
          },
          {
            key: "medical_file",
            title: "Dossier médical",
            render: (row) => (
              <Button
                variant="secondary"
                size="sm"
                icon={FileText}
                onClick={() => {
                  void openWorkerMedicalWorkflow(row);
                }}
                loading={openingWorkerId === row.id}
                disabled={openingWorkerId !== null}
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
