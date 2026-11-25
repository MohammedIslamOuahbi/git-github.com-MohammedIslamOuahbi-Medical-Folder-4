import { Card } from "@/components/common/Card";
import { EmptyState } from "@/components/common/EmptyState";
import { SectionHeader } from "@/components/common/SectionHeader";
import { useSync } from "@/hooks/useSync";
import { Button } from "@/components/common/Button";
import { buildEntityUid } from "@/utils/uid";

export const SyncConflictsPage = () => {
  const { conflicts, resolveConflict } = useSync();

  return (
    <div className="space-y-6">
      <SectionHeader
        eyebrow="Conflict resolution"
        title="Sync Conflicts"
        description="Resolve device and server data collisions with explicit merge strategy selection."
      />
      {conflicts.length === 0 ? (
        <EmptyState
          title="No conflicts detected"
          description="The local device queue and server state are currently aligned."
        />
      ) : (
        <div className="space-y-4">
          {conflicts.map((conflict) => (
            <Card key={`${conflict.entity_type}-${conflict.entity_id}`}>
              <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                <div>
                  <h3 className="text-lg font-semibold text-ink-900">
                    {conflict.entity_type} {buildEntityUid(conflict.entity_type, conflict.entity_id)}
                  </h3>
                  <p className="mt-2 text-sm text-ink-600">
                    {conflict.reason || "Local and server changes both modified this record."}
                  </p>
                </div>
                <div className="flex gap-2">
                  <Button
                    variant="secondary"
                    onClick={() =>
                      void resolveConflict({
                        entity_type: conflict.entity_type,
                        entity_id: Number(conflict.entity_id),
                        resolution: "server_wins",
                        merged_data: {},
                      })
                    }
                  >
                    Server wins
                  </Button>
                  <Button
                    onClick={() =>
                      void resolveConflict({
                        entity_type: conflict.entity_type,
                        entity_id: Number(conflict.entity_id),
                        resolution: "client_wins",
                        merged_data: conflict.local_data || {},
                      })
                    }
                  >
                    Client wins
                  </Button>
                </div>
              </div>
              <div className="mt-4 grid gap-4 lg:grid-cols-2">
                <pre className="overflow-auto rounded-2xl bg-ink-950 p-4 text-xs text-brand-100">
                  {JSON.stringify(conflict.local_data || {}, null, 2)}
                </pre>
                <pre className="overflow-auto rounded-2xl bg-ink-950 p-4 text-xs text-brand-100">
                  {JSON.stringify(conflict.server_data || {}, null, 2)}
                </pre>
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
};
