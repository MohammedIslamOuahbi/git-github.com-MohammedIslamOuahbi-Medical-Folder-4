import { useEffect, useState } from "react";
import { importsApi } from "@/api/importsApi";
import { Badge } from "@/components/common/Badge";
import { SectionHeader } from "@/components/common/SectionHeader";
import { DataTable } from "@/components/tables/DataTable";
import type { ImportJob } from "@/types/entities";
import { mockImportJobs } from "@/utils/mockData";

export const ImportHistoryPage = () => {
  const [items, setItems] = useState<ImportJob[]>(mockImportJobs);

  useEffect(() => {
    void (async () => {
      try {
        setItems(await importsApi.history());
      } catch {
        setItems(mockImportJobs);
      }
    })();
  }, []);

  return (
    <div className="space-y-6">
      <SectionHeader
        eyebrow="Import audit"
        title="Import History"
        description="Review completed and failed uploads with validation and duplicate row insight."
      />
      <DataTable
        columns={[
          { key: "file", title: "File", render: (row: ImportJob) => row.filename },
          { key: "status", title: "Status", render: (row: ImportJob) => <Badge tone={row.status}>{row.status}</Badge> },
          { key: "rows", title: "Imported Rows", render: (row: ImportJob) => row.imported_rows },
          { key: "errors", title: "Validation Errors", render: (row: ImportJob) => row.validation_errors },
        ]}
        data={items}
        uidScope="import-job"
      />
    </div>
  );
};
