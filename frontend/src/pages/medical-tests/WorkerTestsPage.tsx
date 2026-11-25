import { useCallback, useMemo } from "react";
import { workerTestsApi } from "@/api/workerTestsApi";
import { Badge } from "@/components/common/Badge";
import { Pagination } from "@/components/common/Pagination";
import { SearchInput } from "@/components/common/SearchInput";
import { SectionHeader } from "@/components/common/SectionHeader";
import { DataTable } from "@/components/tables/DataTable";
import { usePaginatedResource } from "@/hooks/usePaginatedResource";
import type { WorkerTest } from "@/types/entities";
import { mockWorkerTests } from "@/utils/mockData";

export const WorkerTestsPage = () => {
  const { items, total, page, pageSize, search, loading, error, setPage, setSearch } =
    usePaginatedResource<WorkerTest>(useCallback(workerTestsApi.list, []), mockWorkerTests);

  const columns = useMemo(
    () => [
      { key: "worker", title: "Worker", render: (row: WorkerTest) => row.worker_name || row.worker_id },
      { key: "test", title: "Test", render: (row: WorkerTest) => row.test_name || row.medical_test_id },
      { key: "result", title: "Result", render: (row: WorkerTest) => row.result || "En attente" },
      {
        key: "status",
        title: "Status",
        render: (row: WorkerTest) => (
          <Badge tone={row.abnormal ? "abnormal" : row.status}>
            {row.abnormal ? "abnormal" : row.status}
          </Badge>
        ),
      },
    ],
    [],
  );

  return (
    <div className="space-y-6">
      <SectionHeader
        eyebrow="Clinical results"
        title="Résultats médicaux"
        description={error || "Review per-worker test outcomes, pending items, and abnormal findings."}
      />
      <SearchInput value={search} onChange={setSearch} placeholder="Search worker tests..." />
      <DataTable columns={columns} data={items} loading={loading} uidScope="worker-test" />
      <Pagination page={page} total={total} pageSize={pageSize} onPageChange={setPage} />
    </div>
  );
};
