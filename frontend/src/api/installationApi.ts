import axios from "axios";

import apiClient from "@/api/axios";
import { LOCAL_SERVER_API_BASE_URL, normalizeApiBaseUrl } from "@/config/runtime";
import type {
  BackupRecord,
  CentralCompletePayload,
  CentralCompleteResponse,
  CentralProvisionPayload,
  CentralProvisionResponse,
  DeviceRegistrationPayload,
  DeviceRegistrationResponse,
  InstallationProfilePayload,
  InstallationStatusPayload,
  MobileProvisionPayload,
  MobileProvisionResponse,
  MissionSubmissionRecord,
  RegisteredDeviceRecord,
} from "@/types/installation";
import type { CentralServerInfo } from "@/types/centralSync";

const withData = async <T>(promise: Promise<{ data: T }>) => {
  const response = await promise;
  const payload = response.data as { data?: T } | T;
  if (payload && typeof payload === "object" && "data" in payload) {
    return (payload as { data: T }).data;
  }
  return payload as T;
};

const localTrustedClient = axios.create({
  baseURL: normalizeApiBaseUrl(LOCAL_SERVER_API_BASE_URL),
  headers: {
    "Content-Type": "application/json",
  },
});

export const installationApi = {
  getProfile: async () => withData(localTrustedClient.get<InstallationProfilePayload>("/installation/profile")),
  getStatus: async () => withData(localTrustedClient.get<InstallationStatusPayload>("/installation/status")),
  provisionCentral: async (payload: CentralProvisionPayload) =>
    withData(localTrustedClient.post<CentralProvisionResponse>("/installation/central/provision", payload)),
  completeCentral: async (payload: CentralCompletePayload) =>
    withData(localTrustedClient.post<CentralCompleteResponse>("/installation/central/complete", payload)),
  provisionMobile: async (payload: MobileProvisionPayload) =>
    withData(localTrustedClient.post<MobileProvisionResponse>("/installation/mobile/provision", payload)),
  getCentralServerInfo: async () => withData(apiClient.get<CentralServerInfo>("/central/server-info")),
  getRegisteredDevices: async () => withData(apiClient.get<RegisteredDeviceRecord[]>("/sync/devices")),
  getMissionSubmissions: async () => withData(apiClient.get<MissionSubmissionRecord[]>("/central-sync/submissions")),
  getBackups: async () => withData(apiClient.get<BackupRecord[]>("/system/backups")),
  registerDeviceOnCentral: async (serverUrl: string, payload: DeviceRegistrationPayload) =>
    withData(
      axios.create({
        baseURL: normalizeApiBaseUrl(serverUrl),
        headers: { "Content-Type": "application/json" },
      }).post<DeviceRegistrationResponse>("/central/register-device", payload),
    ),
};
