import apiClient from "@/api/axios";
import type { MedicineSearchResponse } from "@/types/medicine";

export const searchMedicines = async (
  query: string,
  options?: {
    limit?: number;
    activeOnly?: boolean;
    signal?: AbortSignal;
  },
): Promise<MedicineSearchResponse> => {
  const trimmed = query.trim();
  if (trimmed.length < 2) {
    return { items: [], total: 0 };
  }

  const { data } = await apiClient.get<MedicineSearchResponse>("/medicines/search", {
    params: {
      q: trimmed,
      limit: Math.min(Math.max(options?.limit ?? 20, 1), 50),
      active_only: options?.activeOnly ?? true,
    },
    signal: options?.signal,
  });

  return data;
};
