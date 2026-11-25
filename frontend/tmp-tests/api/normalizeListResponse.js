export function normalizeListResponse(data, params) {
    if (Array.isArray(data)) {
        return {
            items: data,
            total: data.length,
            page: params?.page || 1,
            page_size: params?.limit || params?.page_size || data.length,
        };
    }
    return {
        items: data.items,
        total: data.total ?? data.meta?.total ?? data.items.length,
        page: data.page ?? data.meta?.page ?? params?.page ?? 1,
        page_size: data.page_size ?? data.meta?.limit ?? params?.limit ?? params?.page_size ?? data.items.length,
    };
}
