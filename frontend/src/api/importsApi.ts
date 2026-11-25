import apiClient from "./axios";
import type { ImportJob } from "@/types/entities";

type ImportJobApiRecord = {
  id: number;
  file_name?: string;
  original_file_name?: string;
  status?: string;
  total_rows?: number;
  valid_rows?: number;
  invalid_rows?: number;
  duplicate_rows?: number;
  mapping_json?: Record<string, string> | null;
  uploaded_by?: number | string | null;
  created_at: string;
  updated_at: string;
  deleted_at?: string | null;
  local_id?: string | null;
  sync_status?: ImportJob["sync_status"];
};

export type ImportPreviewRow = {
  id: number;
  import_job_id: number;
  row_number: number;
  raw_data_json: Record<string, string | number | null>;
  validation_status: string;
  errors_json?: { errors?: string[] } | null;
  matched_worker_id?: number | null;
  created_at: string;
  updated_at: string;
};

const normalizeImportStatus = (status?: string): ImportJob["status"] => {
  if (status === "validated") return "validated";
  if (status === "confirmed") return "completed";
  if (status === "failed") return "failed";
  return "pending";
};

const normalizeImportJob = (job: ImportJobApiRecord): ImportJob => ({
  id: job.id,
  filename: job.original_file_name || job.file_name || `import-${job.id}`,
  status: normalizeImportStatus(job.status),
  imported_rows: job.total_rows || 0,
  validation_errors: job.invalid_rows || 0,
  duplicate_rows: job.duplicate_rows || 0,
  uploaded_by:
    job.uploaded_by === null || job.uploaded_by === undefined ? undefined : String(job.uploaded_by),
  mapping_json: job.mapping_json || null,
  created_at: job.created_at,
  updated_at: job.updated_at,
  deleted_at: job.deleted_at,
  local_id: job.local_id,
  sync_status: job.sync_status,
});

export const importsApi = {
  upload: async (
    file: File,
    options?: { campaignId?: number; companyId?: number | null },
  ) => {
    const formData = new FormData();
    formData.append("file", file);
    if (options?.campaignId) {
      formData.append("campaign_id", String(options.campaignId));
    }
    if (options?.companyId) {
      formData.append("company_id", String(options.companyId));
    }
    const { data } = await apiClient.post<ImportJobApiRecord>("/imports/upload", formData, {
      headers: { "Content-Type": "multipart/form-data" },
    });
    return normalizeImportJob(data);
  },
  preview: async (importJobId: number) => {
    const { data } = await apiClient.get<ImportPreviewRow[]>(`/imports/${importJobId}/preview`);
    return data;
  },
  mapFields: async (importJobId: number, mapping: Record<string, string>) => {
    const { data } = await apiClient.post<ImportJobApiRecord>(`/imports/${importJobId}/map-fields`, {
      mapping,
    });
    return normalizeImportJob(data);
  },
  validate: async (importJobId: number) => {
    const { data } = await apiClient.post<ImportJobApiRecord>(`/imports/${importJobId}/validate`);
    return normalizeImportJob(data);
  },
  confirm: async (importJobId: number, campaignId?: number) => {
    const { data } = await apiClient.post<ImportJobApiRecord>(`/imports/${importJobId}/confirm`, {
      campaign_id: campaignId ?? null,
    });
    return normalizeImportJob(data);
  },
  history: async () => {
    const { data } = await apiClient.get<ImportJobApiRecord[]>("/imports/history");
    return data.map(normalizeImportJob);
  },
};
