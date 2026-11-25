import apiClient from "./axios";
import { createEntityApi } from "./entityFactory";
import type { ApiListResponse, PaginationParams } from "@/types/common";
import type { User } from "@/types/entities";

const base = createEntityApi<User>("/users");

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

export const usersApi = {
  ...base,
  doctors: async (params?: PaginationParams) => {
    const { data } = await apiClient.get<ApiListResponse<User> | User[]>("/users/doctors", { params });
    if (Array.isArray(data)) return normalizeUsers(data);
    return normalizeUsers(data.items);
  },
  createDoctor: async (payload: Partial<User>) => {
    const { data } = await apiClient.post<User>("/users/doctors", payload);
    return data;
  },
  assistants: async (params?: PaginationParams) => {
    const { data } = await apiClient.get<ApiListResponse<User> | User[]>("/users/assistants", { params });
    if (Array.isArray(data)) return normalizeUsers(data);
    return normalizeUsers(data.items);
  },
  createAssistant: async (payload: Partial<User>) => {
    const { data } = await apiClient.post<User>("/users/assistants", payload);
    return data;
  },
};
