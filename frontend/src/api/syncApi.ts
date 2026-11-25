import apiClient from "./axios";
import type {
  SyncPullResponse,
  SyncPushPayload,
  SyncPushResponse,
  SyncResolvePayload,
  SyncStatusResponse,
} from "@/types/sync";

export const syncApi = {
  push: async (payload: SyncPushPayload) => {
    const { data } = await apiClient.post<SyncPushResponse>("/sync/push", payload);
    return data;
  },
  pull: async (device_id: string, last_sync_at: string | null) => {
    const { data } = await apiClient.get<SyncPullResponse>("/sync/pull", {
      params: { device_id, last_sync_at },
    });
    return data;
  },
  resolveConflict: async (payload: SyncResolvePayload) => {
    const { data } = await apiClient.post("/sync/resolve-conflict", payload);
    return data;
  },
  getStatus: async () => {
    const { data } = await apiClient.get<SyncStatusResponse>("/sync/status");
    return data;
  },
};
