import { SYNC_SAFETY_MESSAGE } from "@/services/syncSafety";
import { Button } from "@/components/common/Button";
import { Card } from "@/components/common/Card";
import { SectionHeader } from "@/components/common/SectionHeader";
import { useSync } from "@/hooks/useSync";

export const SyncStatusPage = () => {
  const { online, syncing, status, conflicts, queue, syncNow } = useSync();
  return (
    <div className="space-y-6">
      <p role="status" className="rounded border border-amber-200 bg-amber-50 p-4">{SYNC_SAFETY_MESSAGE}</p>
      <SectionHeader
        eyebrow="Offline sync"
        title="Sync Status"
        description="Modifications en file d'attente Moniaur, horodatages de synchronisation du serveur et nombre de conflits."
      />
      <div className="grid gap-6 grid-cols-2 grid-cols-4">
        <Card>
          <p className="text-sm text-ink-500">Connection</p>
          <p className="mt-3 text-2xl font-semibold text-ink-900">{online ? "Online" : "Offline"}</p>
        </Card>
        <Card>
          <p className="text-sm text-ink-500">Dernière synchronisation</p>
          <p className="mt-3 text-sm font-semibold text-ink-900">{status?.last_sync_at || "Not synced"}</p>
        </Card>
        <Card>
          <p className="text-sm text-ink-500">Pending Push</p>
          <p className="mt-3 text-2xl font-semibold text-ink-900">{status?.pending_push_count ?? 0}</p>
        </Card>
        <Card>
          <p className="text-sm text-ink-500">Conflicts</p>
          <p className="mt-3 text-2xl font-semibold text-ink-900">{status?.conflict_count ?? conflicts.length}</p>
        </Card>
      </div>
      <Card>
        <div className="flex items-center justify-between">
          <h3 className="text-lg font-semibold text-ink-900">Queued Local Changes</h3>
          <Button variant="secondary" disabled onClick={() => void syncNow().catch(() => undefined)} loading={syncing}>
            Push changes
          </Button>
        </div>
        <pre className="mt-4 overflow-auto rounded-2xl bg-ink-950 p-5 text-sm text-brand-100">
          {JSON.stringify(queue, null, 2)}
        </pre>
      </Card>
    </div>
  );
};
