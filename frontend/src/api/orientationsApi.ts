import type { ResourceResponse } from "@/types/common";
import apiClient from "./axios";
import type { OrientationCertificate } from "@/types/entities";

export interface OrientationListFilters {
  worker_id: number;
  campaign_id: number;
  medical_visit_id?: number;
}

export interface PaginatedResponse<T> {
  items: T[];
  page: number;
  per_page: number;
  total: number;
  total_pages: number;
}

export interface OrientationPayload {
  worker_id: number;
  campaign_id: number;
  medical_visit_id?: number | null;
  doctor_id?: number | null;
  orientation_number?: string;
  orientation_date: string;
  orientation_type: string;
  orientation_types?: {
    specialistAdvice: boolean;
    diagnosticCare: boolean;
    other: boolean;
  };
  orientationTypes?: {
    specialistAdvice: boolean;
    diagnosticCare: boolean;
    other: boolean;
  };
  orientation_type_other?: string | null;
  orientation_details?: string | null;
  worker_name?: string;
  doctor_name?: string;
  includeValidatorSignature?: boolean;
  status?: "draft" | "signed" | "confirmed" | "validated" | "printed" | "cancelled";
}

export interface OrientationPdfResponse {
  blob: Blob;
  filename: string;
}

export interface PasswordDeleteRequest {
  password: string;
}

const normalizeOrientationListResponse = (
  data: PaginatedResponse<OrientationCertificate> | OrientationCertificate[],
  filters?: OrientationListFilters,
): PaginatedResponse<OrientationCertificate> => {
  const response = Array.isArray(data)
    ? {
        items: data,
        total: data.length,
        page: 1,
        per_page: data.length || 1,
        total_pages: 1,
      }
    : data;

  const filteredItems = response.items.filter((item) => {
    const matchWorker = filters?.worker_id == null || item.worker_id === filters.worker_id;
    const matchCampaign = filters?.campaign_id == null || item.campaign_id === filters.campaign_id;
    return matchWorker && matchCampaign;
  });

  return {
    ...response,
    items: filteredItems,
    total: filteredItems.length,
    total_pages: Math.max(1, Math.ceil(filteredItems.length / Math.max(response.per_page || 1, 1))),
  };
};

export const orientationsApi = {
  list: async (filters: OrientationListFilters): Promise<PaginatedResponse<OrientationCertificate>> => {
    const { data } = await apiClient.get<PaginatedResponse<OrientationCertificate> | OrientationCertificate[]>(
      "/orientation-certificates",
      { params: filters },
    );

    return normalizeOrientationListResponse(data, filters);
  },

  listByWorker: async (workerId: number | string): Promise<OrientationCertificate[]> => {
    const { data } = await apiClient.get<OrientationCertificate[]>(`/workers/${workerId}/medical-orientations`);
    return data;
  },

  list_: async (filters: OrientationListFilters): Promise<ResourceResponse<OrientationCertificate>> => {
    const { data } = await apiClient.get<PaginatedResponse<OrientationCertificate> | OrientationCertificate[]>(
      "/orientation-certificates",
      { params: filters },
    );
    const normalized = normalizeOrientationListResponse(data, filters);

    return {
      items: normalized.items,
      total: normalized.total,
      page: normalized.page,
      page_size: normalized.per_page,
    };
  },

  get: async (id: number): Promise<OrientationCertificate> => {
    const { data } = await apiClient.get<OrientationCertificate>(`/orientation-certificates/${id}`);
    return data;
  },

  create: async (payload: OrientationPayload): Promise<OrientationCertificate> => {
    const { data } = await apiClient.post<OrientationCertificate>("/orientation-certificates", payload);
    return data;
  },

  update: async (id: number, payload: OrientationPayload): Promise<OrientationCertificate> => {
    const { data } = await apiClient.put<OrientationCertificate>(`/orientation-certificates/${id}`, payload);
    return data;
  },

  delete: async (id: number, password: string): Promise<void> => {
    await apiClient.delete(`/orientation-certificates/${id}`, {
      data: { password },
    });
  },

  generateNumber: async (campaignId: number): Promise<{ orientation_number: string }> => {
    const { data } = await apiClient.get<{ orientation_number: string }>(
      "/orientation-certificates/generate-number",
      {
        params: { campaign_id: campaignId },
      },
    );
    return data;
  },

  remove: async (id: number, body: PasswordDeleteRequest): Promise<void> => {
    await apiClient.delete(`/orientation-certificates/${id}`, { data: body });
  },

  sign: async (id: number): Promise<OrientationCertificate> => {
    const { data } = await apiClient.post<OrientationCertificate>(`/orientation-certificates/${id}/sign`);
    return data;
  },

  markPrinted: async (id: number): Promise<OrientationCertificate> => {
    const { data } = await apiClient.post<OrientationCertificate>(`/orientation-certificates/${id}/print`);
    return data;
  },

  downloadPdf: async (
    id: number,
    includeSignature?: boolean,
  ): Promise<{ blob: Blob; filename: string }> => {
    const response = await apiClient.get<Blob>(`/orientation-certificates/${id}/pdf`, {
      params: {
        include_signature: includeSignature ?? false,
      },
      responseType: "blob",
    });
    const disposition = response.headers["content-disposition"];
    const filenameMatch = disposition?.match(/filename="?([^"]+)"?/i);
    return {
      blob: response.data,
      filename: filenameMatch?.[1] || "Attestation d'orientation.pdf",
    };
  },

  getLastOrientationCertificateId: async (): Promise<{ last_id: number }> => {
    const { data } = await apiClient.get("/orientation-certificates/last_id");
    return data;
  },
};
