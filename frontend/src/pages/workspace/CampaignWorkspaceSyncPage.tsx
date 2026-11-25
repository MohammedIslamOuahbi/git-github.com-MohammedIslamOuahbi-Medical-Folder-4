import { AlertTriangle, RefreshCcw, Wifi, WifiOff } from "lucide-react";
import { useState } from "react";
import { Badge } from "@/components/common/Badge";
import { Button } from "@/components/common/Button";
import { Card } from "@/components/common/Card";
import { EmptyState } from "@/components/common/EmptyState";
import { SectionHeader } from "@/components/common/SectionHeader";
import { useCampaignWorkspace } from "@/context/CampaignWorkspaceContext";
import { useSync } from "@/hooks/useSync";

export const CampaignWorkspaceSyncPage = () => {
  const { currentCampaign } = useCampaignWorkspace();
  const { online, syncing, status, conflicts, queue, syncNow } = useSync();
  const [lastSyncAt, setLastSyncAt] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const pendingQueueCount = Object.values(queue).reduce(
    (total, items) => total + items.length,
    0,
  );

  if (!currentCampaign) {
    return null;
  }

  const handleSync = async () => {
    setError(null);
    try {
      await syncNow();
      setLastSyncAt(new Date().toISOString());
    } catch {
      setError("Unable to complete sync for this workspace right now.");
    }
  };

  return (
    <div className="space-y-6">
      <SectionHeader
        eyebrow="Workspace sync"
        title="Synchronisation"
        description="Monitor offline-first synchronization and resolve workspace delivery issues."
      />

      <div className="grid gap-4 grid-cols-2 grid-cols-4">
        <Card className="p-5">
          <p className="text-[10px] font-black uppercase tracking-[0.24em] text-[#0085A3]">
            Connectivity
          </p>
          <div className="mt-4 flex items-center gap-3">
            {online ? (
              <Wifi className="h-5 w-5 text-emerald-500" />
            ) : (
              <WifiOff className="h-5 w-5 text-rose-500" />
            )}
            <p className="text-lg font-black text-slate-950">
              {online ? "Online" : "Offline"}
            </p>
          </div>
        </Card>

        <Card className="p-5">
          <p className="text-[10px] font-black uppercase tracking-[0.24em] text-[#0085A3]">
            Queue Items
          </p>
          <p className="mt-4 text-3xl font-black text-slate-950">
            {pendingQueueCount}
          </p>
        </Card>

        <Card className="p-5">
          <p className="text-[10px] font-black uppercase tracking-[0.24em] text-[#0085A3]">
            Conflicts
          </p>
          <p className="mt-4 text-3xl font-black text-slate-950">{conflicts.length}</p>
        </Card>

        <Card className="p-5">
          <p className="text-[10px] font-black uppercase tracking-[0.24em] text-[#0085A3]">
            Last Sync
          </p>
          <p className="mt-4 text-sm font-semibold text-slate-700">
            {lastSyncAt ? lastSyncAt.slice(0, 19).replace("T", " ") : "Not synced yet"}
          </p>
        </Card>
      </div>

      <Card className="p-6">
        <div className="flex flex-col gap-4 flex-row items-center justify-between">
          <div>
            <p className="text-[10px] font-black uppercase tracking-[0.24em] text-[#0085A3]">
              Current status
            </p>
            <div className="mt-3 flex items-center gap-3">
              <Badge tone={status?.conflict_count ? "failed" : "synced"}>
                {syncing
                  ? "syncing"
                  : status?.conflict_count
                    ? "conflict"
                    : "synced"}
              </Badge>
              <span className="text-sm text-slate-500">
                Sync field data, worker tests, and offline changes for this workspace.
              </span>
            </div>
          </div>

          <Button icon={RefreshCcw} onClick={() => void handleSync()} loading={syncing}>
            Sync Now
          </Button>
        </div>

        {error ? (
          <div className="mt-4 rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm font-medium text-rose-700">
            {error}
          </div>
        ) : null}
      </Card>

      <Card className="p-6">
        <div className="flex items-center gap-3">
          <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-rose-50 text-rose-500">
            <AlertTriangle className="h-5 w-5" />
          </div>
          <div>
            <p className="text-[10px] font-black uppercase tracking-[0.24em] text-[#0085A3]">
              Conflict queue
            </p>
            <h2 className="text-lg font-black text-slate-950">Pending sync conflicts</h2>
          </div>
        </div>

        <div className="mt-5 space-y-3">
          {conflicts.length ? (
            conflicts.map((conflict, index) => (
              <div
                key={`${conflict.entity_type}-${conflict.entity_id}-${index}`}
                className="rounded-2xl border border-slate-200/80 bg-slate-50/70 px-4 py-3"
              >
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <p className="text-sm font-semibold text-slate-800">
                      {conflict.entity_type} · {conflict.entity_id}
                    </p>
                    <p className="mt-1 text-xs text-slate-500">
                      {conflict.reason ||
                        "Review this conflict in the main sync conflict center if manual resolution is required."}
                    </p>
                  </div>
                  <Badge tone="failed">Conflict</Badge>
                </div>
              </div>
            ))
          ) : (
            <EmptyState
              title="No sync conflicts"
              description="This workspace is clear. New sync conflicts will appear here if offline changes collide."
            />
          )}
        </div>
      </Card>
    </div>
  );
};
