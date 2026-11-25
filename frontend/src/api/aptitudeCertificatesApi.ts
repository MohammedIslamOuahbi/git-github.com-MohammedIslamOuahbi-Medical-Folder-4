import apiClient from "./axios";
import type { AptitudeCertificate } from "@/types/entities";

export interface AptitudeCertificateUpdatePayload {
  aptitude?: string;
  aptitude_interpretation?: string | null;
  doctor_recommendations?: string | null;
  visit_date?: string | null;
  next_visit_date?: string | null;
  includeValidatorSignature?: boolean;
  issue_date?: string | null;
  validatedDoctorId?: number | null;
  validatedDoctorName?: string | null;
  validatedDoctorRole?: string | null;
  validatedAt?: string | null;
  validatorSignatureUrl?: string | null;
  status?: "draft" | "confirmed" | "validated" | "signed" | "printed" | "cancelled";
}

export const aptitudeCertificatesApi = {
  listByWorker: async (workerId: number | string) => {
    const { data } = await apiClient.get<AptitudeCertificate[]>(
      `/workers/${workerId}/aptitude-certificates`,
    );
    return data;
  },

  get: async (id: number | string) => {
    const { data } = await apiClient.get<AptitudeCertificate>(`/aptitude-certificates/${id}`);
    return data;
  },

  update: async (id: number | string, payload: AptitudeCertificateUpdatePayload) => {
    const { data } = await apiClient.put<AptitudeCertificate>(
      `/aptitude-certificates/${id}`,
      payload,
    );
    return data;
  },

  downloadPdf: async (id: number | string, options?: { cacheBust?: boolean }) => {
    const response = await apiClient.get<Blob>(`/aptitude-certificates/${id}/pdf`, {
      params: options?.cacheBust ? { t: Date.now() } : undefined,
      responseType: "blob",
    });
    const disposition = response.headers["content-disposition"];
    const filenameMatch = disposition?.match(/filename="?([^"]+)"?/i);
    return {
      blob: response.data,
      filename: filenameMatch?.[1] || "Certificat d'aptitude.pdf",
    };
  },

  markPrinted: async (id: number | string) => {
    const { data } = await apiClient.post<AptitudeCertificate>(`/aptitude-certificates/${id}/print`);
    return data;
  },

  getByVisit: async (visitId: number | string) => {
    const { data } = await apiClient.get<AptitudeCertificate>(
      `/medical-visits/${visitId}/aptitude-certificate`,
    );
    return data;
  },

  updateByVisit: async (visitId: number | string, payload: AptitudeCertificateUpdatePayload) => {
    const { data } = await apiClient.put<AptitudeCertificate>(
      `/medical-visits/${visitId}/aptitude-certificate`,
      payload,
    );
    return data;
  },

  validateByVisit: async (visitId: number | string, payload: AptitudeCertificateUpdatePayload) => {
    const { data } = await apiClient.post<AptitudeCertificate>(
      `/medical-visits/${visitId}/aptitude-certificate/validate`,
      payload,
    );
    return data;
  },

  deleteByVisit: async (visitId: number | string) => {
    const { data } = await apiClient.delete<{ deleted: boolean }>(
      `/medical-visits/${visitId}/aptitude-certificate`,
    );
    return data;
  },

  downloadValidatorSignature: async (certificateId: number | string) => {
    const response = await apiClient.get<Blob>(
      `/aptitude-certificates/${certificateId}/validator-signature`,
      { responseType: "blob" },
    );
    return response.data;
  },
};
