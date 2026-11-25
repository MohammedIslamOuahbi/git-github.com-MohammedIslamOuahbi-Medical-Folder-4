import { isSafetySuspension, suspendedSyncError } from "../services/syncSafety";
import axios from "axios";

import apiClient, { getApiBaseUrl, setApiBaseUrl } from "@/api/axios";
import { apiRootFromBase, LOCAL_SERVER_API_BASE_URL, normalizeApiBaseUrl } from "@/config/runtime";
import type {
  DeviceUpdatePayload,
  MissionChangesResponse,
  MissionCopyApplyPayload,
  MissionCopyState,
  MissionFinalizeManifest,
  MissionJoinPayload,
  MissionJoinResponse,
  MissionParticipant,
  MissionServerInfo,
  MissionSessionSummary,
  MissionSessionCreatePayload,
  RuntimeStatusPayload,
} from "@/types/mission";
import { missionStorage, tokenStorage } from "@/utils/storage";

const directClient = (baseUrl: string, includeMissionCredential = true) =>
  axios.create({
    baseURL: normalizeApiBaseUrl(baseUrl),
    headers: {
      "Content-Type": "application/json",
      ...(tokenStorage.getAccessToken() ? { Authorization: `Bearer ${tokenStorage.getAccessToken()}` } : {}),
      ...(includeMissionCredential && missionStorage.getCredential()
        ? { "X-Mission-Device-Credential": missionStorage.getCredential() }
        : {}),
    },
  });

const withEnvelope = async <T>(promise: Promise<{ data: T }>) => {
  const response = await promise.catch((error: unknown) => {
    if (isSafetySuspension(error)) throw suspendedSyncError();
    throw error;
  });
  return response.data;
};

export const missionApi = {
  async getServerInfo(baseUrl?: string) {
    const client = baseUrl ? directClient(baseUrl) : apiClient;
    const data = await withEnvelope(client.get<MissionServerInfo>("/mission/server-info"));
    if (!baseUrl) {
      missionStorage.setCachedDevice(data);
    }
    return data;
  },

  async getCurrentMission() {
    return withEnvelope(apiClient.get<MissionSessionSummary | null>("/mission/sessions/current"));
  },

  async createMission(payload: MissionSessionCreatePayload) {
    return withEnvelope(apiClient.post<{ uuid: string; status: string }>("/mission/sessions", payload));
  },

  async activateMission(missionUuid: string) {
    return withEnvelope(apiClient.post<{ uuid: string; status: string }>(`/mission/sessions/${missionUuid}/activate`));
  },

  async finalizeMission(missionUuid: string) {
    return withEnvelope(apiClient.post<MissionFinalizeManifest>(`/mission/sessions/${missionUuid}/finalize`));
  },

  async getMissionDevices(missionUuid: string) {
    return withEnvelope(apiClient.get<MissionParticipant[]>(`/mission/sessions/${missionUuid}/devices`));
  },

  async disconnectMissionDevice(missionUuid: string, deviceUuid: string) {
    return withEnvelope(apiClient.post<{ device_uuid: string; status: string }>(`/mission/sessions/${missionUuid}/devices/${deviceUuid}/disconnect`));
  },

  async revokeMissionDevice(missionUuid: string, deviceUuid: string) {
    return withEnvelope(apiClient.post<{ device_uuid: string; status: string }>(`/mission/sessions/${missionUuid}/devices/${deviceUuid}/revoke`));
  },

  async pullMissionChanges(missionUuid: string, afterSequence = 0, limit = 100) {
    return withEnvelope(
      apiClient.get<MissionChangesResponse>("/mission-sync/pull", {
        params: {
          mission_uuid: missionUuid,
          after_sequence: Math.max(0, afterSequence),
          limit,
        },
      }),
    );
  },

  async joinMission(missionUuid: string, payload: MissionJoinPayload, baseUrl?: string) {
    const client = baseUrl ? directClient(baseUrl) : apiClient;
    const response = await withEnvelope(client.post<MissionJoinResponse>(`/mission/sessions/${missionUuid}/join`, payload));
    missionStorage.setCredential(response.credential.access_token);
    return response;
  },

  async updateCurrentDevice(payload: DeviceUpdatePayload) {
    return withEnvelope(apiClient.patch<MissionServerInfo>("/device/current", payload));
  },

  async getCurrentDevice() {
    const device = await withEnvelope(apiClient.get<MissionServerInfo>("/device/current"));
    missionStorage.setCachedDevice(device);
    return device;
  },

  async getRuntimeStatus() {
    return withEnvelope(apiClient.get<RuntimeStatusPayload>("/runtime/status"));
  },

  async switchToMissionServer(missionPayload: MissionSessionCreatePayload) {
    const created = await this.createMission(missionPayload);
    await this.activateMission(created.uuid);
    setApiBaseUrl(LOCAL_SERVER_API_BASE_URL);
    return created;
  },

  async switchToMissionClient(params: { baseUrl: string; missionUuid: string; joinPayload: MissionJoinPayload }) {
    const normalizedBase = normalizeApiBaseUrl(params.baseUrl);
    const joined = await this.joinMission(params.missionUuid, params.joinPayload, normalizedBase);
    setApiBaseUrl(normalizedBase);
    return joined;
  },

  async switchToStandalone(force = false, reason?: string) {
    missionStorage.clearCredential();
    const response = await withEnvelope(
      apiClient.post<{ runtime_mode: string }>("/runtime/switch-to-standalone", {
        force,
        reason: reason || null,
      }),
    );
    setApiBaseUrl(LOCAL_SERVER_API_BASE_URL);
    return response;
  },

  async testMissionServer(baseUrl: string) {
    const normalizedBase = normalizeApiBaseUrl(baseUrl);
    const client = directClient(normalizedBase);
    const health = await withEnvelope(client.get<{ status: string }>(`${apiRootFromBase(normalizedBase)}/health`));
    const serverInfo = await withEnvelope(client.get<MissionServerInfo>("/mission/server-info"));
    return { health, serverInfo, baseUrl: normalizedBase };
  },

  async getMissionCopyStatus(params: {
    missionUuid: string;
    missionServerUuid?: string | null;
    missionServerUrl?: string | null;
  }) {
    const client = directClient(LOCAL_SERVER_API_BASE_URL, false);
    return withEnvelope(
      client.get<MissionCopyState | null>("/mission-sync/status", {
        params: {
          mission_uuid: params.missionUuid,
          mission_server_uuid: params.missionServerUuid || undefined,
          mission_server_url: params.missionServerUrl || undefined,
        },
      }),
    );
  },

  async applyMissionChangesLocally(payload: MissionCopyApplyPayload) {
    const client = directClient(LOCAL_SERVER_API_BASE_URL, false);
    return withEnvelope(client.post<MissionCopyState>("/mission-sync/apply", payload));
  },

  async getMissionCopyRun(runUuid: string) {
    const client = directClient(LOCAL_SERVER_API_BASE_URL, false);
    return withEnvelope(client.get<MissionCopyState | null>(`/mission-sync/runs/${runUuid}`));
  },
};
