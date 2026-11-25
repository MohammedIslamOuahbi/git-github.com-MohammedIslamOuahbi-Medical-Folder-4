import apiClient from "./axios";
import type { ApiListResponse, PaginationParams } from "@/types/common";

export const createEntityApi = <T, P = Partial<T>>(resource: string) => ({
  list: async (params?: PaginationParams) => {
    const { data } = await apiClient.get<ApiListResponse<T> | T[]>(resource, {
      params,
    });
    if (Array.isArray(data)) {
      const requestedPageSize = params?.limit || params?.page_size;
      return {
        items: data,
        total: data.length,
        page: params?.page || 1,
        page_size: requestedPageSize || data.length,
      };
    }
    return {
      items: data.items,
      total: data.total ?? data.meta?.total ?? data.items.length,
      page: data.page ?? data.meta?.page ?? params?.page ?? 1,
      page_size: data.page_size ?? data.meta?.limit ?? params?.limit ?? params?.page_size ?? data.items.length,
    };
  },
  get: async (id: number | string) => {
    const { data } = await apiClient.get<T>(`${resource}/${id}`);
    return data;
  },
  create: async (payload: P, headers?: Record<string, string>) => {
    const { data } = await apiClient.post<T>(resource, payload, headers ? { headers } : undefined);
    return data;
  },
  update: async (id: number | string, payload: P, headers?: Record<string, string>) => {
    const { data } = await apiClient.put<T>(`${resource}/${id}`, payload, headers ? { headers } : undefined);
    return data;
  },
  remove: async (id: number | string, payload?: Record<string, unknown>) => {
    const { data } = await apiClient.delete(`${resource}/${id}`, payload ? { data: payload } : undefined);
    return data;
  },
});
