import { create } from "zustand";
import type { SyncChanges, SyncConflict, SyncStatusResponse } from "@/types/sync";
import { syncStorage } from "@/utils/storage";

const emptyChanges: SyncChanges = {
  users: [],
  companies: [],
  branches: [],
  drilling_sites: [],
  workers: [],
  medical_campaigns: [],
  campaign_workers: [],
  medical_tests: [],
  campaign_tests: [],
  worker_tests: [],
  doctor_campaigns: [],
  assistant_campaigns: [],
  import_jobs: [],
  import_rows: [],
};

interface SyncState {
  queue: SyncChanges;
  status: SyncStatusResponse | null;
  conflicts: SyncConflict[];
  online: boolean;
  syncing: boolean;
  deviceId: string;
  setQueue: (queue: SyncChanges) => void;
  setStatus: (status: SyncStatusResponse | null) => void;
  setConflicts: (conflicts: SyncConflict[]) => void;
  setOnline: (online: boolean) => void;
  setSyncing: (syncing: boolean) => void;
  enqueue: (entity: keyof SyncChanges, item: Record<string, unknown>) => void;
  clearQueue: () => void;
}

const createDeviceId = () => {
  const existing = syncStorage.getMeta<{ device_id?: string }>();
  if (existing?.device_id) return existing.device_id;

  const randomId =
    globalThis.crypto?.randomUUID?.() ??
    `${Date.now()}-${Math.random().toString(36).slice(2)}-${Math.random()
      .toString(36)
      .slice(2)}`;

  const deviceId = `device-${randomId}`;

  syncStorage.setMeta({ device_id: deviceId, last_sync_at: null });
  return deviceId;
};

export const useSyncStore = create<SyncState>((set, get) => ({
  queue: syncStorage.getQueue<SyncChanges>() || emptyChanges,
  status: null,
  conflicts: [],
  online: navigator.onLine,
  syncing: false,
  deviceId: createDeviceId(),
  setQueue: (queue) => {
    syncStorage.setQueue(queue);
    set({ queue });
  },
  setStatus: (status) => set({ status }),
  setConflicts: (conflicts) => set({ conflicts }),
  setOnline: (online) => set({ online }),
  setSyncing: (syncing) => set({ syncing }),
  enqueue: (entity, item) => {
    const queue = get().queue;
    const next = { ...queue, [entity]: [...queue[entity], item] };
    syncStorage.setQueue(next);
    set({ queue: next });
  },
  clearQueue: () => {
    syncStorage.setQueue(emptyChanges);
    set({ queue: emptyChanges });
  },
}));
