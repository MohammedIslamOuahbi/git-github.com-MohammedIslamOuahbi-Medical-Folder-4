import apiClient from "./axios";
import { mutationHeaders } from "./localMutation";
import type { ApiListResponse, PaginationParams } from "@/types/common";
import type {
  Campaign,
  CampaignTestAssignment,
  MedicalTest,
  User,
  Worker,
} from "@/types/entities";

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

const normalizeCampaign = (campaign: Partial<Campaign> & { title?: string; description?: string | null }) =>
  ({
    ...campaign,
    name: campaign.name || campaign.title || "Campaign",
    title: campaign.title || campaign.name || "Campaign",
    description: campaign.description || "",
  }) as Campaign;

const normalizeUsers = (items: Array<Partial<User> & { is_active?: boolean | null }>) =>
  items.map((item) => ({
    ...item,
    full_name:
      item.full_name ||
      `${item.first_name || ""} ${item.last_name || ""}`.trim() ||
      "Medical User",
    status:
      item.status ||
      (typeof item.is_active === "boolean" ? (item.is_active ? "active" : "inactive") : "inactive"),
  })) as User[];

const normalizeWorkers = (items: Array<Record<string, unknown>>) =>
  items.map((item) => ({
    ...item,
    employee_code: (item.employee_code || item.employee_number || "") as string,
    full_name:
      (item.full_name as string) ||
      `${String(item.first_name || "")} ${String(item.last_name || "")}`.trim(),
    position: (item.position || item.job_title || "") as string,
    gender: normalizeGender(item.gender as string | undefined),
    status:
      (item.campaign_status as string | undefined) ||
      (item.status as string) ||
      ((item.is_active as boolean | undefined) ? "active" : "inactive"),
    medical_file_status: (item.medical_file_status as string | undefined) || null,
    latest_visit_date: (item.latest_visit_date as string | undefined) || null,
    latest_visit_id:
      typeof item.latest_visit_id === "number" ? item.latest_visit_id : item.latest_visit_id ? Number(item.latest_visit_id) : null,
  })) as Worker[];

const normalizeTests = (items: Array<Record<string, unknown>>) =>
  items.map((item) => ({
    ...item,
    section: (item.section || item.category || "Examen clinique") as string,
    active:
      typeof item.active === "boolean"
        ? item.active
        : Boolean(item.is_active ?? true),
    category: (item.category || item.section || "Examen clinique") as string,
    code: (item.code || item.name || "") as string,
    status:
      (item.status as string) ||
      ((item.is_active as boolean | undefined) ? "active" : "inactive"),
  })) as MedicalTest[];

const normalizeCampaignTests = (items: Array<Record<string, unknown>>) =>
  items.map((item) => ({
    ...item,
    campaign_id: Number(item.campaign_id),
    campaign_test_id:
      typeof item.campaign_test_id === "number"
        ? item.campaign_test_id
        : Number(item.id),
    test_id: Number(item.test_id),
    name:
      typeof item.name === "string"
        ? item.name
        : typeof (item.test as Record<string, unknown> | null)?.name === "string"
          ? String((item.test as Record<string, unknown>).name)
          : null,
    description:
      typeof item.description === "string"
        ? item.description
        : typeof (item.test as Record<string, unknown> | null)?.description === "string"
          ? String((item.test as Record<string, unknown>).description)
          : null,
    type:
      typeof item.type === "string"
        ? item.type
        : typeof (item.test as Record<string, unknown> | null)?.category === "string"
          ? String((item.test as Record<string, unknown>).category)
          : typeof (item.test as Record<string, unknown> | null)?.section === "string"
            ? String((item.test as Record<string, unknown>).section)
            : null,
    required: Boolean(item.required),
    test: item.test
      ? normalizeTests([item.test as Record<string, unknown>])[0]
      : null,
  })) as CampaignTestAssignment[];

export const campaignsApi = {
  list: async (params?: PaginationParams) => {
    const { data } = await apiClient.get<ApiListResponse<Campaign> | Campaign[]>("/campaigns", {
      params,
    });
    if (Array.isArray(data)) {
      const requestedPageSize = params?.limit || params?.page_size;
      return {
        items: data.map((item) => normalizeCampaign(item)),
        total: data.length,
        page: params?.page || 1,
        page_size: requestedPageSize || data.length,
      };
    }
    return {
      items: data.items.map((item) => normalizeCampaign(item)),
      total: data.total ?? data.meta?.total ?? data.items.length,
      page: data.page ?? data.meta?.page ?? params?.page ?? 1,
      page_size: data.page_size ?? data.meta?.limit ?? params?.limit ?? params?.page_size ?? data.items.length,
    };
  },
  get: async (id: number | string) => {
    const { data } = await apiClient.get<Campaign>(`/campaigns/${id}`);
    return normalizeCampaign(data);
  },
  create: async (payload: Partial<Campaign>) => {
    const requestPayload = {
      title: payload.title || payload.name,
      description: payload.description || null,
      company_id: payload.company_id,
      branch_id: payload.branch_id,
      drilling_site_id: payload.drilling_site_id || null,
      start_date: payload.start_date,
      end_date: payload.end_date,
      status: payload.status,
    };
    const operation = await mutationHeaders("new-campaign", "create", 0, requestPayload);
    const { data } = await apiClient.post<Campaign>("/campaigns", requestPayload, { headers: operation.headers });
    return normalizeCampaign(data);
  },
  update: async (id: number | string, payload: Partial<Campaign>) => {
    const requestPayload = {
      title: payload.title || payload.name,
      description: payload.description,
      company_id: payload.company_id,
      branch_id: payload.branch_id,
      drilling_site_id: payload.drilling_site_id,
      start_date: payload.start_date,
      end_date: payload.end_date,
      status: payload.status,
    };
    const { data } = await apiClient.put<Campaign>(`/campaigns/${id}`, requestPayload);
    return normalizeCampaign(data);
  },
  remove: async (id: number, password: string) => {
    const { data } = await apiClient.delete(`/campaigns/${id}`, {
      data: { password },
    });
    return data;
  },
  doctors: async (campaignId: number) => {
    const { data } = await apiClient.get<User[]>(`/campaigns/${campaignId}/doctors`);
    return normalizeUsers(data);
  },
  addDoctors: async (campaignId: number, doctor_ids: number[]) => {
    const { data } = await apiClient.post<User[]>(`/campaigns/${campaignId}/doctors`, {
      doctor_ids,
    });
    return normalizeUsers(data);
  },
  removeDoctor: async (campaignId: number, doctorId: number) => {
    const { data } = await apiClient.delete(`/campaigns/${campaignId}/doctors/${doctorId}`);
    return data;
  },
  assistants: async (campaignId: number) => {
    const { data } = await apiClient.get<User[]>(`/campaigns/${campaignId}/assistants`);
    return normalizeUsers(data);
  },
  addAssistants: async (campaignId: number, assistant_ids: number[]) => {
    const { data } = await apiClient.post<User[]>(`/campaigns/${campaignId}/assistants`, {
      assistant_ids,
    });
    return normalizeUsers(data);
  },
  removeAssistant: async (campaignId: number, assistantId: number) => {
    const { data } = await apiClient.delete(`/campaigns/${campaignId}/assistants/${assistantId}`);
    return data;
  },
  workers: async (campaignId: number) => {
    const { data } = await apiClient.get<Worker[]>(`/campaigns/${campaignId}/workers`);
    return normalizeWorkers(data as unknown as Array<Record<string, unknown>>);
  },
  addWorkers: async (campaignId: number, worker_ids: number[]) => {
    const { data } = await apiClient.post<Worker[]>(`/campaigns/${campaignId}/workers`, {
      worker_ids,
    });
    return normalizeWorkers(data as unknown as Array<Record<string, unknown>>);
  },
  removeWorker: async (campaignId: number, workerId: number) => {
    const { data } = await apiClient.delete(`/campaigns/${campaignId}/workers/${workerId}`);
    return data;
  },
  tests: async (campaignId: number) => {
    const { data } = await apiClient.get<CampaignTestAssignment[]>(
      `/campaigns/${campaignId}/tests`,
    );
    return normalizeCampaignTests(data as unknown as Array<Record<string, unknown>>);
  },
  addTests: async (
    campaignId: number,
    payload: Array<{ test_id: number; required: boolean }>,
  ) => {
    const { data } = await apiClient.post<CampaignTestAssignment[]>(
      `/campaigns/${campaignId}/tests`,
      payload,
    );
    return normalizeCampaignTests(data as unknown as Array<Record<string, unknown>>);
  },
  updateTests: async (
    campaignId: number,
    payload: Array<{ test_id: number; required: boolean }>,
  ) => {
    const operation = await mutationHeaders(`campaign-tests:${campaignId}`, "update", 1, payload);
    const { data } = await apiClient.put<CampaignTestAssignment[]>(
      `/campaigns/${campaignId}/tests`,
      payload,
      { headers: operation.headers },
    );
    return normalizeCampaignTests(data as unknown as Array<Record<string, unknown>>);
  },
  removeTest: async (campaignId: number, testId: number) => {
    const { data } = await apiClient.delete(`/campaigns/${campaignId}/tests/${testId}`);
    return data;
  },
};
