import { useEffect, useState } from "react";
import type { PaginationParams } from "@/types/common";

interface ResourceResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

export const usePaginatedResource = <T,>(
  loader: (params: PaginationParams) => Promise<ResourceResponse<T>>,
  fallback: T[],
) => {
  const [items, setItems] = useState<T[]>([]);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(10);
  const [search, setSearch] = useState("");
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const run = async () => {
      setLoading(true);
      setError(null);
      try {
        const response = await loader({
          page,
          page_size: pageSize,
          search,
        });
        setItems(response.items);
        setTotal(response.total);
      } catch {
        const filtered = fallback.filter((item) =>
          JSON.stringify(item).toLowerCase().includes(search.toLowerCase()),
        );
        const start = (page - 1) * pageSize;
        setItems(filtered.slice(start, start + pageSize));
        setTotal(filtered.length);
        setError("Live API unavailable. Showing local fallback data.");
      } finally {
        setLoading(false);
      }
    };
    void run();
  }, [fallback, loader, page, pageSize, search]);

  return {
    items,
    total,
    page,
    pageSize,
    search,
    loading,
    error,
    setPage,
    setSearch,
    setItems,
  };
};
