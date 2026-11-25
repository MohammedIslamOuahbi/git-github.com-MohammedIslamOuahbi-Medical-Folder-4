import { useEffect, useState } from "react";
import { dashboardApi } from "@/api/dashboardApi";
import { Badge } from "@/components/common/Badge";
import { Card } from "@/components/common/Card";
import { DashboardIdentityCard } from "@/components/dashboard/DashboardIdentityCard";
import { SectionHeader } from "@/components/common/SectionHeader";
import { MetricBarChart } from "@/components/charts/DashboardCharts";
import { DataTable } from "@/components/tables/DataTable";
import type { AssistantDashboardData } from "@/types/dashboard";
import { mockAssistantDashboard } from "@/utils/mockData";

export const AssistantDashboardPage = () => {
  const [data, setData] = useState<AssistantDashboardData>(mockAssistantDashboard);

  useEffect(() => {
    void (async () => {
      try {
        setData(await dashboardApi.getAssistant());
      } catch {
        setData(mockAssistantDashboard);
      }
    })();
  }, []);

  return (
    <div className="space-y-6">
      <SectionHeader
        eyebrow="Assistant operations"
        title="Preparation Dashboard"
        description="Coordinate imports, campaign readiness, validation cleanup, and upload completion."
      />

      <DashboardIdentityCard />

      <div className="grid gap-4 grid-cols-2 grid-cols-4">
        {[
          ["Assigned Campaigns", data.assigned_campaigns],
          ["Pending Imports", data.pending_imports],
          ["Validation Errors", data.validation_errors],
          ["Duplicate Rows", data.duplicate_rows],
        ].map(([label, value]) => (
          <Card key={label}>
            <p className="text-sm text-ink-500">{label}</p>
            <p className="mt-3 text-3xl font-semibold text-ink-900">{value}</p>
          </Card>
        ))}
      </div>

      <MetricBarChart
        title="Import Throughput"
        xKey="name"
        dataKey="value"
        data={[
          { name: "En attente", value: data.pending_imports },
          { name: "Terminée", value: data.completed_imports },
          { name: "Failed", value: data.failed_imports },
          { name: "Travailleurs", value: data.imported_workers },
        ]}
      />

      <div className="grid gap-6 grid-cols-2">
        <DataTable
          columns={[
            { key: "file", title: "Recent Imports", render: (row) => row.filename },
            {
              key: "status",
              title: "Status",
              render: (row) => <Badge tone={row.status}>{row.status}</Badge>,
            },
            { key: "rows", title: "Rows", render: (row) => row.imported_rows },
          ]}
          data={data.recent_import_jobs}
          uidScope="import-job"
        />
        <DataTable
          columns={[
            { key: "name", title: "Ready Campaigns", render: (row) => row.name },
            { key: "status", title: "Status", render: (row) => <Badge tone={row.status}>{row.status}</Badge> },
            { key: "tests", title: "Tests", render: (row) => row.tests_count ?? 0 },
          ]}
          data={data.campaigns_ready_for_preparation}
          uidScope="campaign"
        />
      </div>
    </div>
  );
};
