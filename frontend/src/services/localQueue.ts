import { useSyncStore } from "@/store/syncStore";
import type { SyncChanges } from "@/types/sync";

export const queueOfflineChange = (
  entity: keyof SyncChanges,
  item: Record<string, unknown>,
) => {
  useSyncStore.getState().enqueue(entity, {
    ...item,
    local_id: item.local_id || crypto.randomUUID(),
    updated_at: new Date().toISOString(),
  });
};
