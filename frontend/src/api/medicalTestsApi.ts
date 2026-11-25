import apiClient from "./axios";
import type { ApiListResponse, PaginationParams } from "@/types/common";
import { normalizeListResponse } from "./normalizeListResponse";
import type { MedicalTest } from "@/types/entities";

type MedicalTestsListParams = PaginationParams & {
  active?: boolean;
};

const normalizeMedicalTest = (item: unknown): MedicalTest => {
  const source = item as Record<string, unknown>;

  const name = String(source.name || source.label || source.code || "Examen médical");
  const section = String(source.section || source.category || "Examen clinique");
  const isActive = Boolean(source.is_active ?? source.active ?? true);

  return {
    ...(source as unknown as MedicalTest),
    name,
    label: name,
    section,
    category: section,
    active: isActive,
    status: isActive ? "active" : "inactive",
    updated_at: String(source.updated_at || source.created_at || new Date().toISOString()),
  };
};
export const medicalTestsApi = {
  list: async (params?: MedicalTestsListParams) => {
    const { data } = await apiClient.get<ApiListResponse<MedicalTest> | MedicalTest[]>("/medical-tests", {
      params,
    });

    const response = normalizeListResponse(data, params);
    return {
      ...response,
      items: response.items.map((item) => normalizeMedicalTest(item)),
    };
  },

  get: async (id: number | string) => {
    const { data } = await apiClient.get<MedicalTest>(`/medical-tests/${id}`);
    return normalizeMedicalTest(data);
  },

  create: async (payload: Partial<MedicalTest>) => {
    const { data } = await apiClient.post<MedicalTest>("/medical-tests", {
      ...payload,
      active: payload.active ?? true,
    });
    return normalizeMedicalTest(data);
  },

  update: async (id: number | string, payload: Partial<MedicalTest>) => {
    const { data } = await apiClient.put<MedicalTest>(`/medical-tests/${id}`, payload);
    return normalizeMedicalTest(data);
  },

  remove: async (id: number | string, payload?: Record<string, unknown>) => {
    const { data } = await apiClient.delete<MedicalTest>(
      `/medical-tests/${id}`,
      payload ? { data: payload } : undefined,
    );
    return normalizeMedicalTest(data);
  },
};
