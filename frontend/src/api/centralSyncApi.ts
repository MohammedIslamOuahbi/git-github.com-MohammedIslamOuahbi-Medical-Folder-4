import { isSafetySuspension, suspendedSyncError } from "../services/syncSafety";
import axios from "axios";

import apiClient from "@/api/axios";
import { LOCAL_SERVER_API_BASE_URL, normalizeApiBaseUrl } from "@/config/runtime";
import type {
  CentralApplyRequest,
  CentralApplyResponse,
  CentralBootstrapDownload,
  CentralBootstrapManifest,
  CentralBootstrapRequestPayload,
  CentralBootstrapRequestResponse,
  CentralCapabilities,
  CentralConflictRecord,
  CentralConflictResolutionType,
  CentralPullResponse,
  CentralPushRequest,
  CentralPushResponse,
  CentralReadiness,
  CentralServerInfo,
  DataIntegrityStatus,
} from "@/types/centralSync";
import { centralSyncStorage, missionStorage, tokenStorage } from "@/utils/storage";

const directClient = (baseUrl: string, extraHeaders?: Record<string, string>) =>
  axios.create({
    baseURL: normalizeApiBaseUrl(baseUrl),
    headers: {
      "Content-Type": "application/json",
      ...(tokenStorage.getAccessToken() ? { Authorization: `Bearer ${tokenStorage.getAccessToken()}` } : {}),
      ...(missionStorage.getCredential() ? { "X-Mission-Device-Credential": missionStorage.getCredential() } : {}),
      ...(extraHeaders || {}),
    },
  });

const localInfraClient = () => directClient(LOCAL_SERVER_API_BASE_URL);

const withData = async <T>(promise: Promise<{ data: T }>) => {
  const response = await promise.catch((error: unknown) => {
    if (isSafetySuspension(error)) throw suspendedSyncError();
    throw error;
  });
  const payload = response.data as { success?: boolean; data?: T } | T;
  if (payload && typeof payload === "object" && "data" in payload) {
    return (payload as { data: T }).data;
  }
  return payload as T;
};

export const centralSyncApi = {
  async getRemoteServerInfo(serverUrl: string) {
    return withData(directClient(serverUrl).get<CentralServerInfo>("/central/server-info"));
  },

  async getRemoteCapabilities(serverUrl: string) {
    return withData(directClient(serverUrl).get<CentralCapabilities>("/central/capabilities"));
  },

  async getLocalServerInfo() {
    return withData(localInfraClient().get<CentralServerInfo>("/central/server-info"));
  },

  async getReadiness() {
    return withData(apiClient.get<CentralReadiness>("/central-sync/readiness"));
  },

  async pushMission(serverUrl: string, payload: CentralPushRequest, deviceSecret: string) {
    return withData(
      directClient(serverUrl, { "X-Central-Device-Secret": deviceSecret }).post<CentralPushResponse>("/central-sync/push", payload),
    );
  },

  async pullCentralChanges(serverUrl: string, afterCentralSequence: number, limit = 250) {
    return withData(
      directClient(serverUrl).get<CentralPullResponse>("/central-sync/pull", {
        params: { after_central_sequence: Math.max(0, afterCentralSequence), limit },
      }),
    );
  },

  async applyCentralChanges(payload: CentralApplyRequest) {
    return withData(localInfraClient().post<CentralApplyResponse>("/central-sync/apply", payload));
  },

  async listConflicts() {
    return withData(apiClient.get<CentralConflictRecord[]>("/central-sync/conflicts"));
  },

  async getConflict(conflictUuid: string) {
    return withData(apiClient.get<CentralConflictRecord>(`/central-sync/conflicts/${conflictUuid}`));
  },

  async resolveConflict(conflictUuid: string, resolutionType: CentralConflictResolutionType, resolvedPayload: Record<string, unknown> | null) {
    return withData(
      apiClient.post<{ uuid: string; status: string }>(`/central-sync/conflicts/${conflictUuid}/resolve`, {
        resolution_type: resolutionType,
        resolved_payload: resolvedPayload,
      }),
    );
  },

  async requestBootstrap(payload: CentralBootstrapRequestPayload) {
    return withData(apiClient.post<CentralBootstrapRequestResponse>("/central-sync/bootstrap/request", payload));
  },

  async getBootstrapManifest(bootstrapUuid: string) {
    return withData(apiClient.get<CentralBootstrapManifest>(`/central-sync/bootstrap/${bootstrapUuid}/manifest`));
  },

  async downloadBootstrap(bootstrapUuid: string) {
    return withData(apiClient.get<CentralBootstrapDownload>(`/central-sync/bootstrap/${bootstrapUuid}/download`));
  },

  async completeBootstrap(bootstrapUuid: string, appliedLocally: boolean, notes?: string) {
    return withData(
      apiClient.post<{ bootstrap_uuid: string; status: string }>(`/central-sync/bootstrap/${bootstrapUuid}/complete`, {
        applied_locally: appliedLocally,
        notes: notes || null,
      }),
    );
  },

  async getDataIntegrity() {
    return withData(apiClient.get<DataIntegrityStatus>("/system/data-integrity"));
  },

  getStoredCursor() {
    return centralSyncStorage.getCursor();
  },

  setStoredCursor(value: number) {
    centralSyncStorage.setCursor(value);
  },
};
