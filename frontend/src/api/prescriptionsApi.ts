import apiClient from "./axios";
import type { Prescription } from "@/types/entities";

type PrescriptionApiRecord = Prescription;
type PrescriptionCreatePayload = {
  worker_id: number;
  campaign_id: number;
  medical_visit_id?: number | null;
  doctor_id?: number | null;
  prescription_number?: string;
  prescription_date: string;
  diagnosis?: string;
  notes?: string;
  includeValidatorSignature?: boolean;
  status: Prescription["status"];
  items: Array<{
    medicine_id?: number | null;
    medication_name: string;
    brand_name?: string | null;
    generic_name?: string | null;
    strength?: string | null;
    pharmaceutical_form?: string | null;
    dosage?: string | null;
    dose_quantity?: string | null;
    dose_unit?: string | null;
    frequency?: string | null;
    frequency_custom?: string | null;
    duration?: string | null;
    duration_value?: string | null;
    duration_unit?: string | null;
    quantity?: string | null;
    number_of_boxes?: string | null;
    instructions?: string | null;
    sort_order?: number | null;
  }>;
};

type PrescriptionUpdatePayload = Partial<
  Omit<PrescriptionCreatePayload, "worker_id" | "campaign_id">
>;

export const prescriptionsApi = {
  list: async (params?: {
    worker_id?: number | string;
    campaign_id?: number | string;
    medical_visit_id?: number | string;
  }) => {
    const { data } = await apiClient.get<PrescriptionApiRecord[]>("/prescriptions", { params });
    return data;
  },
  listByWorker: async (workerId: number | string) => {
    const { data } = await apiClient.get<PrescriptionApiRecord[]>(`/workers/${workerId}/prescriptions`);
    return data;
  },
  get: async (id: number | string) => {
    const { data } = await apiClient.get<PrescriptionApiRecord>(`/prescriptions/${id}`);
    return data;
  },
  create: async (payload: PrescriptionCreatePayload) => {
    const { data } = await apiClient.post<PrescriptionApiRecord>("/prescriptions", payload);
    return data;
  },
  update: async (id: number | string, payload: PrescriptionUpdatePayload) => {
    const { data } = await apiClient.put<PrescriptionApiRecord>(`/prescriptions/${id}`, payload);
    return data;
  },
  remove: async (id: number | string) => {
    const { data } = await apiClient.delete<PrescriptionApiRecord>(`/prescriptions/${id}`);
    return data;
  },
  sign: async (id: number | string) => {
    const { data } = await apiClient.post<PrescriptionApiRecord>(`/prescriptions/${id}/sign`);
    return data;
  },
  validate: async (id: number | string) => {
    const { data } = await apiClient.post<PrescriptionApiRecord>(`/prescriptions/${id}/validate`);
    return data;
  },
  duplicate: async (id: number | string) => {
    const { data } = await apiClient.post<PrescriptionApiRecord>(`/prescriptions/${id}/duplicate`);
    return data;
  },
  cancel: async (id: number | string) => {
    const { data } = await apiClient.post<PrescriptionApiRecord>(`/prescriptions/${id}/cancel`);
    return data;
  },
  markPrinted: async (id: number | string) => {
    const { data } = await apiClient.post<PrescriptionApiRecord>(`/prescriptions/${id}/print`);
    return data;
  },
  downloadPdf: async (id: number | string, options?: { includeSignature?: boolean }) => {
    const response = await apiClient.get<Blob>(`/prescriptions/${id}/pdf`, {
      params:
        typeof options?.includeSignature === "boolean"
          ? { include_signature: options.includeSignature }
          : undefined,
      responseType: "blob",
    });
    const disposition = response.headers["content-disposition"];
    const filenameMatch = disposition?.match(/filename="?([^"]+)"?/i);
    return {
      blob: response.data,
      filename: filenameMatch?.[1] || "Ordonnance.pdf",
    };
  },
  previewPdf: async (id: number | string, options?: { includeSignature?: boolean }) => {
    const response = await apiClient.get<Blob>(`/prescriptions/${id}/preview`, {
      params:
        typeof options?.includeSignature === "boolean"
          ? { include_signature: options.includeSignature }
          : undefined,
      responseType: "blob",
    });
    return response.data;
  },
};
