import apiClient from "./axios";
import { mutationHeaders } from "./localMutation";
import type { ApiListResponse, PaginationParams } from "@/types/common";
import type { Campaign, Worker, WorkerTest } from "@/types/entities";

type WorkerApiRecord = Partial<Worker> & {
  employee_number?: string;
  employee_code?: string;
  national_id?: string | null;
  medical_file_data?: object | null;
  medical_file_status?: string | null;
  full_name?: string;
  job_title?: string | null;
  position?: string | null;
  birth_date?: string | null;
  birth_wilaya?: string | null;
  marital_status?: string | null;
  blood_group?: string | null;
  phone?: string | null;
  address?: string | null;
  department?: string | null;
  medical_status?: string | null;
  etat_actual?: Worker["etat_actual"];
  is_active?: boolean | null;
};

const normalizeGender = (gender?: string | null) => {
  if (!gender) return undefined;
  const normalized = gender.trim().toLowerCase();
  if (normalized === "m" || normalized === "male" || normalized === "homme" || normalized === "masculin") {
    return "Masculin";
  }
  if (normalized === "f" || normalized === "female" || normalized === "femme" || normalized === "feminin" || normalized === "féminin") {
    return "Feminin";
  }
  return gender;
};

const normalizeWorker = (worker: WorkerApiRecord) =>
  ({
    ...worker,
    employee_code: worker.employee_code || worker.employee_number || "",
    employee_number: worker.employee_number || worker.employee_code || "",
    full_name:
      worker.full_name ||
      `${worker.first_name || ""} ${worker.last_name || ""}`.trim() ||
      "Worker",
    position: worker.position || worker.job_title || "",
    job_title: worker.job_title || worker.position || null,
    gender: normalizeGender(worker.gender),
    status:
      worker.status ||
      (typeof worker.is_active === "boolean"
        ? worker.is_active
          ? "active"
          : "inactive"
        : "active"),
    is_active:
      typeof worker.is_active === "boolean"
        ? worker.is_active
        : (worker.status || "active") !== "inactive",
    etat_actual: worker.etat_actual || "present",
    medical_file_status: worker.medical_file_status || null,
  }) as Worker;

const toWorkerPayload = (payload: WorkerApiRecord) => ({
  company_id: payload.company_id,
  branch_id: payload.branch_id,
  drilling_site_id: payload.drilling_site_id ?? null,
  employee_number: payload.employee_code || "",
  national_id: payload.national_id ?? null,
  first_name: payload.first_name || "",
  last_name: payload.last_name || "",
  gender: normalizeGender(payload.gender) ?? null,
  birth_date: payload.birth_date ?? null,
  birth_wilaya: payload.birth_wilaya ?? null,
  marital_status: payload.marital_status ?? null,
  blood_group: payload.blood_group ?? null,
  phone: payload.phone ?? null,
  address: payload.address ?? null,
  job_title: payload.position || null,
  department: payload.department ?? null,
  medical_status: payload.medical_status ?? null,
  medical_file_status: payload.medical_file_status ?? null,
  etat_actual: payload.etat_actual ?? "present",
  medical_file_data: payload.medical_file_data ?? null,
  is_active: payload.status ? payload.status === "active" : true,
});

export const workersApi = {
  list: async (params?: PaginationParams) => {
    const { data } = await apiClient.get<ApiListResponse<WorkerApiRecord> | WorkerApiRecord[]>(
      "/workers",
      { params },
    );
    if (Array.isArray(data)) {
      const requestedPageSize = params?.limit || params?.page_size;
      return {
        items: data.map(normalizeWorker),
        total: data.length,
        page: params?.page || 1,
        page_size: requestedPageSize || data.length,
      };
    }
    return {
      items: data.items.map(normalizeWorker),
      total: data.total ?? data.meta?.total ?? data.items.length,
      page: data.page ?? data.meta?.page ?? params?.page ?? 1,
      page_size: data.page_size ?? data.meta?.limit ?? params?.limit ?? params?.page_size ?? data.items.length,
    };
  },
  get: async (id: number | string) => {
    const { data } = await apiClient.get<WorkerApiRecord>(`/workers/${id}`);
    return normalizeWorker(data);
  },
  lookupByIdentity: async (params: {
    first_name: string;
    last_name: string;
    birth_date: string;
    national_id: string;
  }) => {
    const { data } = await apiClient.get<WorkerApiRecord>("/workers/lookup", { params });
    return normalizeWorker(data);
  },
  lookupWithHistory: async (params: {
    first_name: string;
    last_name: string;
    birth_date: string;
    national_id: string;
  }) => {
    const { data } = await apiClient.get<{
      worker: WorkerApiRecord;
      history: Record<string, unknown>;
    }>("/workers/lookup-with-history", { params });
    return {
      worker: normalizeWorker(data.worker),
      history: data.history,
    };
  },
  create: async (payload: Partial<Worker>) => {
    const body = toWorkerPayload(payload);
    const operation = await mutationHeaders(`new-worker:${body.employee_number}`, "create", 0, body);
    const { data } = await apiClient.post<WorkerApiRecord>(
      "/workers",
      body,
      { headers: operation.headers },
    );
    window.localStorage.removeItem(operation.key);
    return normalizeWorker(data);
  },
  update: async (id: number | string, payload: Partial<Worker>) => {
    const body = toWorkerPayload(payload);
    const operation = await mutationHeaders(id, "worker:update", payload.sync_version, body);
    const { data } = await apiClient.put<WorkerApiRecord>(
      `/workers/${id}`,
      body,
      { headers: operation.headers },
    );
    window.localStorage.removeItem(operation.key);
    return normalizeWorker(data);
  },
  remove: async (id: number | string, payload?: Record<string, unknown>) => {
    const version = typeof payload?.sync_version === "number" ? payload.sync_version : undefined;
    const body = { password: payload?.password };
    const operation = await mutationHeaders(id, "worker:delete", version, { delete: true });
    const { data } = await apiClient.delete(`/workers/${id}`, { data: body, headers: operation.headers });
    window.localStorage.removeItem(operation.key);
    return data;
  },
  tests: async (workerId: number) => {
    const { data } = await apiClient.get<WorkerTest[]>(`/workers/${workerId}/tests`);
    return data;
  },
  campaigns: async (workerId: number) => {
    const { data } = await apiClient.get<Campaign[]>(`/workers/${workerId}/campaigns`);
    return data;
  },
  downloadOrientationPdf: async (workerId: number | string, campaignId?: number | string) => {
    const response = await apiClient.get<Blob>(`/orientation-certificates/${workerId}/pdf`, {
      params: campaignId ? { campaign_id: campaignId } : undefined,
      responseType: "blob",
    });
    const disposition = response.headers["content-disposition"];
    const filenameMatch = disposition?.match(/filename="?([^"]+)"?/i);
    return {
      blob: response.data,
      filename: filenameMatch?.[1] || "Attestation d'orientation.pdf",
    };
  },

  downloadMedicalVisitPdf: async (
    workerId: number | string,
    campaignId?: number | string,
    visitId?: number | string,
  ) => {
    const response = await apiClient.get<Blob>(`/workers/${workerId}/medical-visit-pdf`, {
      params: {
        ...(campaignId ? { campaign_id: campaignId } : {}),
        ...(visitId ? { visit_id: visitId } : {}),
      },
      responseType: "blob",
    });
    const disposition = response.headers["content-disposition"];
    const filenameMatch = disposition?.match(/filename="?([^"]+)"?/i);
    return {
      blob: response.data,
      filename: filenameMatch?.[1] || "Fich intern de visit Medicale.pdf",
    };
  },
  downloadMedicalFilePdf: async (workerId: number | string, campaignId?: number | string) => {
    const response = await apiClient.get<Blob>(`/workers/${workerId}/medical-file/pdf`, {
      params: campaignId ? { campaign_id: campaignId } : undefined,
      responseType: "blob",
    });
    const disposition = response.headers["content-disposition"];
    const filenameMatch = disposition?.match(/filename="?([^"]+)"?/i);
    return {
      blob: response.data,
      filename: filenameMatch?.[1] || "Dossier medical.pdf",
    };
  },
  downloadMedicalDossierPdf: async (workerId: number | string, campaignId?: number | string) => {
    const response = await apiClient.get<Blob>(`/workers/${workerId}/medical-dossier-pdf`, {
      params: campaignId ? { campaign_id: campaignId } : undefined,
      responseType: "blob",
    });
    const disposition = response.headers["content-disposition"];
    const filenameMatch = disposition?.match(/filename="?([^"]+)"?/i);
    return {
      blob: response.data,
      filename: filenameMatch?.[1] || "Dossier médical.pdf",
    };
  },
  
  getLastId: async (): Promise<number> => {
    const { data } = await apiClient.get<{ last_id: number }>("/workers/last_id");
    return data.last_id;
  },
  
};
