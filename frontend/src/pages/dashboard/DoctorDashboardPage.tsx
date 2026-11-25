import { useEffect, useState } from "react";
import { dashboardApi } from "@/api/dashboardApi";
import { Badge } from "@/components/common/Badge";
import { Card } from "@/components/common/Card";
import { DashboardIdentityCard } from "@/components/dashboard/DashboardIdentityCard";
import { SectionHeader } from "@/components/common/SectionHeader";
import { MetricBarChart } from "@/components/charts/DashboardCharts";
import { DataTable } from "@/components/tables/DataTable";
import type { DoctorDashboardData } from "@/types/dashboard";
import { formatDisplayDate } from "@/utils/date";
import { mockDoctorDashboard } from "@/utils/mockData";

export const DoctorDashboardPage = () => {
  const [data, setData] = useState<DoctorDashboardData>(mockDoctorDashboard);

  useEffect(() => {
    void (async () => {
      try {
        setData(await dashboardApi.getDoctor());
      } catch {
        setData(mockDoctorDashboard);
      }
    })();
  }, []);

  return (
    <div className="space-y-6">
      <SectionHeader
        eyebrow="Doctor workspace"
        title="Clinical Dashboard"
        description="Monitor assigned campaigns, review abnormal results, and keep worker testing on schedule."
      />

      <DashboardIdentityCard />

      <div className="grid gap-4 grid-cols-2 grid-cols-4">
        {[
          ["Assigned Campaigns", data.assigned_campaigns],
          ["Pending Worker Tests", data.pending_worker_tests],
          ["Completed Tests", data.completed_worker_tests],
          ["Abnormal Results", data.abnormal_results],
        ].map(([label, value]) => (
          <Card key={label}>
            <p className="text-sm text-ink-500">{label}</p>
            <p className="mt-3 text-3xl font-semibold text-ink-900">{value}</p>
          </Card>
        ))}
      </div>

      

      <div className="grid gap-6 grid-cols-2">
        <DataTable
          columns={[
            { key: "worker", title: "Worker", render: (row) => row.worker_name },
            { key: "test", title: "Test", render: (row) => row.test_name },
            {
              key: "status",
              title: "Status",
              render: (row) => <Badge tone={row.abnormal ? "abnormal" : row.status}>{row.abnormal ? "abnormal" : row.status}</Badge>,
            },
          ]}
          data={data.recent_worker_tests}
          uidScope="worker-test"
        />
        <DataTable
          columns={[
            { key: "name", title: "Upcoming Campaigns", render: (row) => row.name },
            { key: "start", title: "Start", render: (row) => formatDisplayDate(row.start_date) },
            { key: "workers", title: "Travailleurs", render: (row) => row.worker_count ?? 0 },
          ]}
          data={data.upcoming_campaigns}
          uidScope="campaign"
        />
      </div>
    </div>
  );
};
