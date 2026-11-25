import { suspendedSyncError } from "./syncSafety";
import type { SyncResolvePayload } from "@/types/sync";
import { syncStorage } from "@/utils/storage";

export const syncService = {
  getLastSyncAt: () => syncStorage.getMeta<{ last_sync_at: string | null }>()?.last_sync_at || null,
  saveLastSyncAt: (value: string | null) => {
    const meta = syncStorage.getMeta<Record<string, unknown>>() || {};
    syncStorage.setMeta({ ...meta, last_sync_at: value });
  },
  syncNow: async (): Promise<never> => {
    // Never acknowledge or clear the legacy queue; no timer/network event lifts this barrier.
    throw suspendedSyncError();
  },
  resolveConflict: async (_payload: SyncResolvePayload): Promise<never> => {
    throw suspendedSyncError();
  },
};
