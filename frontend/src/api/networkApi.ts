import apiClient, { setApiBaseUrl } from "./axios";
import type {
  DiscoveredServerSummary,
  MissionServerStartPayload,
  MissionServerStopPayload,
  NetworkConnectPayload,
  NetworkHeartbeatPayload,
  NetworkStatusResponse,
  SystemLogEntry,
} from "@/types/network";

export const networkApi = {
  getStatus: async () => {
    const { data } = await apiClient.get<NetworkStatusResponse>("/network/status");
    return data;
  },
  discover: async () => {
    const { data } = await apiClient.get<DiscoveredServerSummary[]>("/network/discovery");
    return data;
  },
  startMissionServer: async (payload: MissionServerStartPayload) => {
    const { data } = await apiClient.post<NetworkStatusResponse>("/network/mission/start", payload);
    return data;
  },
  stopMissionServer: async (payload: MissionServerStopPayload) => {
    const { data } = await apiClient.post<NetworkStatusResponse>("/network/mission/stop", payload);
    return data;
  },
  connect: async (payload: NetworkConnectPayload) => {
    setApiBaseUrl(payload.api_base_url);
    const { data } = await apiClient.post<NetworkStatusResponse>("/network/connect", payload);
    return data;
  },
  heartbeat: async (payload: NetworkHeartbeatPayload) => {
    const { data } = await apiClient.post<NetworkStatusResponse>("/network/heartbeat", payload);
    return data;
  },
  getLogs: async () => {
    const { data } = await apiClient.get<SystemLogEntry[]>("/network/logs");
    return data;
  },
};
