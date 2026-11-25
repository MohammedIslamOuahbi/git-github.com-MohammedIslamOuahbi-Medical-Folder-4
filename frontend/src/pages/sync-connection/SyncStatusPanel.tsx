import { SYNC_SAFETY_MESSAGE } from "@/services/syncSafety";
import { useState } from "react";
import {
  CheckCircle2,
  Clock3,
  CloudOff,
  RefreshCw,
  ShieldAlert,
  TimerReset,
} from "lucide-react";

import { Badge } from "@/components/common/Badge";
import { Button } from "@/components/common/Button";
import { Card } from "@/components/common/Card";

interface Props {
  pendingChanges: number;
  conflictCount: number;
  lastSyncedAt: string | null;
  serverTime: string | null;
  syncStatus: "offline" | "pending" | "synced" | "conflict" | "suspended";
  canSync: boolean;
  onSyncNow: () => Promise<void>;
}

const toneMap: Record<Props["syncStatus"], string> = {
  suspended: "pending",
  offline: "inactive",
  pending: "pending",
  synced: "active",
  conflict: "abnormal",
};

const labelMap: Record<Props["syncStatus"], string> = {
  suspended: "Suspendue pour protection",
  offline: "Hors ligne",
  pending: "En attente",
  synced: "Synchronisé",
  conflict: "Conflit",
};

const statusPresentation: Record<
  Props["syncStatus"],
  {
    title: string;
    description: string;
    icon: typeof RefreshCw;
    surfaceClassName: string;
    iconClassName: string;
  }
> = {
  suspended: { title: "Synchronisation suspendue", description: SYNC_SAFETY_MESSAGE, icon: ShieldAlert, surfaceClassName: "border-amber-200 bg-amber-50", iconClassName: "bg-amber-100 text-amber-700" },
  offline: {
    title: "Synchronisation indisponible",
    description: "La connexion réseau est nécessaire pour échanger les données avec le serveur.",
    icon: CloudOff,
    surfaceClassName: "border-slate-200 bg-slate-50",
    iconClassName: "bg-slate-200 text-slate-700",
  },
  pending: {
    title: "Données en attente",
    description: "Des modifications locales doivent encore être envoyées ou récupérées.",
    icon: RefreshCw,
    surfaceClassName: "border-amber-200 bg-amber-50",
    iconClassName: "bg-amber-100 text-amber-700",
  },
  synced: {
    title: "Données à jour",
    description: "Le poste est synchronisé avec le serveur principal.",
    icon: CheckCircle2,
    surfaceClassName: "border-emerald-200 bg-emerald-50",
    iconClassName: "bg-emerald-100 text-emerald-700",
  },
  conflict: {
    title: "Conflits à résoudre",
    description: "Certaines données nécessitent une vérification avant la prochaine synchronisation.",
    icon: ShieldAlert,
    surfaceClassName: "border-rose-200 bg-rose-50",
    iconClassName: "bg-rose-100 text-rose-700",
  },
};

export const SyncStatusPanel = ({
  pendingChanges,
  conflictCount,
  lastSyncedAt,
  serverTime,
  syncStatus,
  canSync,
  onSyncNow,
}: Props) => {
  const [syncing, setSyncing] = useState(false);
  const presentation = statusPresentation["suspended"];
  const StatusIcon = presentation.icon;

  return (
    <Card className="overflow-hidden rounded-[1.75rem] border-slate-200 bg-white p-0 shadow-sm">
      <p role="status" className="border-b border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">{SYNC_SAFETY_MESSAGE}</p>
      <div className="relative overflow-hidden border-b border-slate-200 bg-slate-950 px-5 py-6 sm:px-6">
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_top_right,rgba(14,165,233,0.18),transparent_38%),radial-gradient(circle_at_bottom_left,rgba(16,185,129,0.12),transparent_34%)]" />

        <div className="relative flex flex-col gap-5 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <h3 className="text-xl font-black tracking-tight text-white">
                Synchronisation
              </h3>
              <Badge tone={toneMap[syncStatus]}>{labelMap[syncStatus]}</Badge>
            </div>

            <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-300">
              Suivez la file d’attente, les conflits, la dernière synchronisation et l’heure du
              serveur principal.
            </p>
          </div>

          <div className="rounded-2xl border border-white/10 bg-white/[0.06] p-3 text-sky-300 backdrop-blur">
            <RefreshCw className={`h-5 w-5 ${syncing ? "animate-spin" : ""}`} />
          </div>
        </div>
      </div>

      <div className="space-y-6 p-5 sm:p-6">
        <div className={`rounded-2xl border p-5 ${presentation.surfaceClassName}`}>
          <div className="flex items-start gap-4">
            <div className={`rounded-2xl p-3 ${presentation.iconClassName}`}>
              <StatusIcon className="h-5 w-5" />
            </div>

            <div className="min-w-0">
              <p className="text-base font-black text-slate-950">{presentation.title}</p>
              <p className="mt-1 text-sm leading-6 text-slate-600">
                {presentation.description}
              </p>
            </div>
          </div>
        </div>

        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <div className="rounded-2xl border border-slate-200 bg-slate-50/80 p-4">
            <div className="flex items-center justify-between gap-3">
              <p className="text-[11px] font-black uppercase tracking-[0.14em] text-slate-500">
                En attente
              </p>
              <RefreshCw className="h-4 w-4 text-sky-600" />
            </div>
            <p className="mt-3 text-2xl font-black text-slate-950">{pendingChanges}</p>
            <p className="mt-1 text-xs text-slate-500">Modification(s) locale(s)</p>
          </div>

          <div className="rounded-2xl border border-slate-200 bg-slate-50/80 p-4">
            <div className="flex items-center justify-between gap-3">
              <p className="text-[11px] font-black uppercase tracking-[0.14em] text-slate-500">
                Conflits
              </p>
              <ShieldAlert className="h-4 w-4 text-rose-600" />
            </div>
            <p className="mt-3 text-2xl font-black text-slate-950">{conflictCount}</p>
            <p className="mt-1 text-xs text-slate-500">Élément(s) à vérifier</p>
          </div>

          <div className="rounded-2xl border border-slate-200 bg-slate-50/80 p-4">
            <div className="flex items-center justify-between gap-3">
              <p className="text-[11px] font-black uppercase tracking-[0.14em] text-slate-500">
                Dernière synchro
              </p>
              <Clock3 className="h-4 w-4 text-violet-600" />
            </div>
            <p className="mt-3 break-words text-sm font-bold leading-6 text-slate-950">
              {lastSyncedAt || "Jamais synchronisé"}
            </p>
          </div>

          <div className="rounded-2xl border border-slate-200 bg-slate-50/80 p-4">
            <div className="flex items-center justify-between gap-3">
              <p className="text-[11px] font-black uppercase tracking-[0.14em] text-slate-500">
                Heure serveur
              </p>
              <TimerReset className="h-4 w-4 text-emerald-600" />
            </div>
            <p className="mt-3 break-words text-sm font-bold leading-6 text-slate-950">
              {serverTime || "Indisponible"}
            </p>
          </div>
        </div>

        <div className="border-t border-slate-200 pt-5">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <h4 className="text-sm font-black text-slate-950">
                Synchronisation manuelle
              </h4>
              <p className="mt-1 text-xs leading-5 text-slate-500">
                Lancez immédiatement l’échange des données avec le serveur principal.
              </p>
            </div>

            <Button
              icon={RefreshCw}
              loading={syncing}
              disabled={true}
              className="w-full justify-center sm:w-auto"
              onClick={async () => {
                setSyncing(true);
                try {
                  await onSyncNow();
                } finally {
                  setSyncing(false);
                }
              }}
            >
              Synchroniser maintenant
            </Button>
          </div>

          {!canSync ? (
            <div className="mt-4 flex items-start gap-3 rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-600">
              <CloudOff className="mt-0.5 h-4 w-4 shrink-0" />
              <p>La synchronisation sera disponible dès que la connexion réseau sera rétablie.</p>
            </div>
          ) : null}
        </div>
      </div>
    </Card>
  );
};