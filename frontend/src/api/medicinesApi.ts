import apiClient from "./axios";
import type { MedicineImportPreview, MedicineImportRecord, MedicineSearchResponse } from "@/types/medicine";
import { searchMedicines } from "@/services/medicineApi";

export const medicinesApi = {
  search: async (q: string, limit = 20, signal?: AbortSignal) =>
    searchMedicines(q, { limit, signal, activeOnly: true }),
  listImports: async () => {
    const { data } = await apiClient.get<MedicineImportRecord[]>("/medicine-imports");
    return data;
  },
  getImport: async (id: number | string) => {
    const { data } = await apiClient.get<MedicineImportRecord>(`/medicine-imports/${id}`);
    return data;
  },
  uploadImport: async (payload: {
    file: File;
    source_name: string;
    source_version?: string;
    import_mode: string;
    notes?: string;
  }) => {
    const formData = new FormData();
    formData.append("file", payload.file);
    formData.append("source_name", payload.source_name);
    formData.append("import_mode", payload.import_mode);
    if (payload.source_version) formData.append("source_version", payload.source_version);
    if (payload.notes) formData.append("notes", payload.notes);
    const { data } = await apiClient.post<MedicineImportRecord>("/medicine-imports/upload", formData);
    return data;
  },
  previewImport: async (id: number | string, mapping?: Record<string, string>) => {
    const { data } = await apiClient.post<MedicineImportPreview>(`/medicine-imports/${id}/preview`, {
      mapping: mapping || null,
    });
    return data;
  },
  confirmImport: async (
    id: number | string,
    payload: {
      source_name: string;
      source_version?: string;
      publication_date?: string;
      import_mode: string;
      notes?: string;
      mapping?: Record<string, string>;
      force_reimport?: boolean;
    },
  ) => {
    const { data } = await apiClient.post<MedicineImportRecord>(`/medicine-imports/${id}/confirm`, payload);
    return data;
  },
  cancelImport: async (id: number | string) => {
    const { data } = await apiClient.post<MedicineImportRecord>(`/medicine-imports/${id}/cancel`);
    return data;
  },
  exportErrors: async (id: number | string) => {
    const response = await apiClient.get<Blob>(`/medicine-imports/${id}/errors/export`, {
      responseType: "blob",
    });
    return response.data;
  },
};
