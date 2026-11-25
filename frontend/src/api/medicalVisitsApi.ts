import apiClient from "./axios";
import type { MedicalVisit } from "@/types/entities";
import { mutationHeaders } from "./localMutation";

export const medicalVisitsApi = {
  create: async (payload: Partial<MedicalVisit>) => {
    const operation = await mutationHeaders(`new:${payload.worker_id ?? "unknown"}`, "create", 0, payload);
    const { data } = await apiClient.post<MedicalVisit>("/medical-visits", payload, { headers: operation.headers });
    window.localStorage.removeItem(operation.key);
    return data;
  },
  get: async (visitId: number | string) => {
    const { data } = await apiClient.get<MedicalVisit>(`/medical-visits/${visitId}`);
    return data;
  },
  downloadPdf: async (visitId: number | string, campaignId?: number | string) => {
    const response = await apiClient.get<Blob>(`/medical-visits/${visitId}/pdf`, {
      params: campaignId ? { campaign_id: campaignId } : undefined,
      responseType: "blob",
    });
    const disposition = response.headers["content-disposition"];
    const filenameMatch = disposition?.match(/filename="?([^"]+)"?/i);
    return {
      blob: response.data,
      filename: filenameMatch?.[1] || "Fiche interne de visite medicale.pdf",
    };
  },
  listByWorker: async (workerId: number | string) => {
    const { data } = await apiClient.get<MedicalVisit[]>(`/workers/${workerId}/visits`);
    return data;
  },
  duplicateVisit: async (
    workerId: number | string,
    visitId: number | string,
    payload: {
      campaign_id: number;
      company_name?: string | null;
      branch_name?: string | null;
      site_name?: string | null;
      campaign_name?: string | null;
    },
  ) => {
    const operation = await mutationHeaders(visitId, `duplicate:${workerId}`, 0, payload);
    const { data } = await apiClient.post<MedicalVisit>(
      `/workers/${workerId}/medical-visits/${visitId}/duplicate`,
      payload,
      { headers: operation.headers },
    );
    window.localStorage.removeItem(operation.key);
    return data;
  },
  update: async (visitId: number | string, payload: Partial<MedicalVisit>) => {
    const { version, ...body } = payload;
    const operation = await mutationHeaders(visitId, "update", version, body);
    const { data } = await apiClient.patch<MedicalVisit>(`/medical-visits/${visitId}`, body, { headers: operation.headers });
    window.localStorage.removeItem(operation.key);
    return data;
  },
  updateStatus: async (visitId: number | string, status: string, version: number) => {
    const operation = await mutationHeaders(visitId, "status", version, { status });
    const { data } = await apiClient.patch<MedicalVisit>(`/medical-visits/${visitId}/status`, { status }, { headers: operation.headers });
    window.localStorage.removeItem(operation.key);
    return data;
  },
  validate: async (visitId: number | string, payload?: Record<string, unknown>) => {
    const { version, ...body } = payload || {};
    const operation = await mutationHeaders(visitId, "validate", typeof version === "number" ? version : undefined, body);
    const { data } = await apiClient.post<MedicalVisit>(`/medical-visits/${visitId}/validate`, body, { headers: operation.headers });
    window.localStorage.removeItem(operation.key);
    return data;
  },
  validateVisit: async (visitId: number | string, payload?: Record<string, unknown>) => {
    return medicalVisitsApi.validate(visitId, payload);
  },
  reopen: async (visitId: number | string, version: number) => {
    const operation = await mutationHeaders(visitId, "reopen", version, {});
    const { data } = await apiClient.post<MedicalVisit>(`/medical-visits/${visitId}/reopen`, {}, { headers: operation.headers });
    window.localStorage.removeItem(operation.key);
    return data;
  },
  getTestResults: async (visitId: number | string) => {
    const { data } = await apiClient.get(`/medical-visits/${visitId}/test-results`);
    return data;
  },
  saveTestResults: async (visitId: number | string, payload: Record<string, unknown>, version: number) => {
    const operation = await mutationHeaders(visitId, "test_results", version, payload);
    const { data } = await apiClient.post(`/medical-visits/${visitId}/test-results`, payload, { headers: operation.headers });
    window.localStorage.removeItem(operation.key);
    return data;
  },
};
