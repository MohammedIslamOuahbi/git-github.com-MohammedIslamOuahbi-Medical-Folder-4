import { useMemo } from "react";
import { ArrowRight, CalendarDays, CheckCircle2, ClipboardList, MapPin, Plus, Sparkles } from "lucide-react";
import { Modal } from "@/components/common/Modal";
import { Badge } from "@/components/common/Badge";
import { Button } from "@/components/common/Button";
import type { Worker } from "@/types/entities";
import { formatDisplayDate } from "@/utils/date";

export type WorkerLookupHistory = {
  companies?: { id?: number; name: string }[];
  branches?: { id?: number; name: string }[];
  sites?: { id?: number; name: string }[];
  campaigns?: { id?: number; name: string }[];
  visits?: Array<{
    id: number;
    visit_date: string;
    status: string;
    company_name?: string | null;
    branch_name?: string | null;
    site_name?: string | null;
    campaign_name?: string | null;
    tests?: string[];
    summary?: Record<string, unknown>;
    medical_decision?: Record<string, unknown>;
  }>;
  total_medical_visits?: number;
  total_medical_tests?: number;
};

type Props = {
  open: boolean;
  worker: Worker | null;
  history: WorkerLookupHistory | null;
  currentCampaign?: { id?: number; company_name?: string; branch_name?: string; site_name?: string; title?: string } | null;
  onClose: () => void;
  onOpenVisit: (visitId: number) => void;
  onDuplicateVisit: (visitId: number) => void;
  onCreateNewVisit: () => void;
};

const formatDate = (value?: string | null) => formatDisplayDate(value) || "—";

export const WorkerAlreadyExistsModal = ({
  open,
  worker,
  history,
  currentCampaign,
  onClose,
  onOpenVisit,
  onDuplicateVisit,
  onCreateNewVisit,
}: Props) => {
  const workerName = `${worker?.first_name || ""} ${worker?.last_name || ""}`.trim();
  const stats = useMemo(
    () => [
      { label: "Entreprises", value: history?.companies?.length || 0 },
      { label: "Branches", value: history?.branches?.length || 0 },
      { label: "Sites", value: history?.sites?.length || 0 },
      { label: "Campagnes", value: history?.campaigns?.length || 0 },
      { label: "Visites", value: history?.total_medical_visits || 0 },
      { label: "Tests", value: history?.total_medical_tests || 0 },
    ],
    [history],
  );

  return (
    <Modal open={open} title="This worker is already registered" onClose={onClose}>
      <div className="space-y-6">
        <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
          <div className="flex items-center gap-3">
            <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-cyan-600 text-lg font-black text-white">
              {(worker?.first_name?.[0] || "").toUpperCase()}
              {(worker?.last_name?.[0] || "").toUpperCase()}
            </div>
            <div>
              <p className="text-lg font-black text-slate-950">{workerName || "—"}</p>
              <p className="text-sm text-slate-500">{formatDate(worker?.birth_date) || "—"} · {worker?.national_id || "—"}</p>
            </div>
          </div>
        </div>

        <div className="grid gap-3 md:grid-cols-3 xl:grid-cols-6">
          {stats.map((item) => (
            <div key={item.label} className="rounded-2xl border border-slate-200 bg-white p-3">
              <p className="text-xs font-bold uppercase tracking-[0.12em] text-slate-500">{item.label}</p>
              <p className="mt-2 text-2xl font-black text-slate-950">{item.value}</p>
            </div>
          ))}
        </div>

        <div className="space-y-3">
          <div className="flex items-center gap-2 text-sm font-bold text-slate-900">
            <CalendarDays className="h-4 w-4 text-cyan-600" />
            Historique des visites
          </div>
          <div className="space-y-3">
            {history?.visits?.length ? history.visits.map((visit) => (
              <div key={visit.id} className="rounded-2xl border border-slate-200 bg-white p-4">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <p className="font-black text-slate-950">{formatDate(visit.visit_date)}</p>
                    <p className="text-sm text-slate-500">
                      {visit.company_name || "—"} · {visit.branch_name || "—"} · {visit.site_name || "—"} · {visit.campaign_name || "—"}
                    </p>
                  </div>
                  <Badge tone={visit.status === "validated" ? "active" : visit.status === "needs_correction" ? "danger" : "pending"}>
                    {visit.status}
                  </Badge>
                </div>
                <div className="mt-3 flex flex-wrap gap-2 text-xs text-slate-600">
                  {(visit.tests || []).map((test) => (
                    <span key={test} className="rounded-full bg-slate-100 px-2 py-1 font-semibold">{test}</span>
                  ))}
                </div>
                <div className="mt-4 flex flex-wrap gap-2">
                  <Button
                    type="button"
                    size="sm"
                    variant="secondary"
                    icon={ArrowRight}
                    onClick={() => onOpenVisit(visit.id)}
                  >
                    Consulter
                  </Button>
                  <Button
                    type="button"
                    size="sm"
                    icon={Sparkles}
                    onClick={() => onDuplicateVisit(visit.id)}
                  >
                    Duplicate this visit
                  </Button>
                </div>
              </div>
            )) : <p className="text-sm text-slate-500">Aucun historique disponible.</p>}
          </div>
        </div>

        <div className="flex flex-wrap justify-end gap-3 border-t border-slate-200 pt-4">
          <Button type="button" variant="secondary" onClick={onClose}>
            Fermer
          </Button>
          <Button type="button" icon={Plus} onClick={onCreateNewVisit}>
            Create new visit for this campaign
          </Button>
        </div>
      </div>
    </Modal>
  );
};
