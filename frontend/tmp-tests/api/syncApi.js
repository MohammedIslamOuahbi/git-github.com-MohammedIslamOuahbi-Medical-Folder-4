import apiClient from "./axios";
export const syncApi = {
    push: async (payload) => {
        const { data } = await apiClient.post("/sync/push", payload);
        return data;
    },
    pull: async (device_id, last_sync_at) => {
        const { data } = await apiClient.get("/sync/pull", {
            params: { device_id, last_sync_at },
        });
        return data;
    },
    resolveConflict: async (payload) => {
        const { data } = await apiClient.post("/sync/resolve-conflict", payload);
        return data;
    },
    getStatus: async () => {
        const { data } = await apiClient.get("/sync/status");
        return data;
    },
};
