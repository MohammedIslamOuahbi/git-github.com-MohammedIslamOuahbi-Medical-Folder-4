import type { PaginationParams, ResourceResponse } from "../types/common";

type ListApi<T> = {
  list: (params?: PaginationParams) => Promise<ResourceResponse<T>>;
};

/** Load complete lookup lists using the backend's supported pagination. */
export async function fetchAllPages<T>(api: ListApi<T>): Promise<{ items: T[] }> {
  const items: T[] = [];
  for (let page = 1; ; page += 1) {
    const response = await api.list({ page, limit: 100, sort_by: "id", sort_order: "asc" });
    items.push(...response.items);
    if (items.length >= response.total) return { items };
    if (response.items.length === 0) {
      throw new Error("The lookup list could not be fully loaded. Please reload the page.");
    }
  }
}
