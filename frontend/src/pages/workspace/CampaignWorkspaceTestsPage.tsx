import { useEffect, useMemo, useState } from "react";
import { FlaskConical } from "lucide-react";
import { campaignsApi } from "@/api/campaignsApi";
import { workerTestsApi } from "@/api/workerTestsApi";
import { Badge } from "@/components/common/Badge";
import { Card } from "@/components/common/Card";
import { DataTable } from "@/components/common/DataTable";
import { EmptyState } from "@/components/common/EmptyState";
import { SearchInput } from "@/components/common/SearchInput";
import { SectionHeader } from "@/components/common/SectionHeader";
import { Spinner } from "@/components/common/Spinner";
import { useCampaignWorkspace } from "@/context/CampaignWorkspaceContext";
import type { CampaignTestAssignment, WorkerTest } from "@/types/entities";
import { formatDisplayDate } from "@/utils/date";

export const CampaignWorkspaceTestsPage = () => {
  const { currentCampaign } = useCampaignWorkspace();
  const [search, setSearch] = useState("");
  const [assignedTests, setAssignedTests] = useState<CampaignTestAssignment[]>([]);
  const [workerTests, setWorkerTests] = useState<WorkerTest[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!currentCampaign) return;
    let cancelled = false;

    const load = async () => {
      setLoading(true);
      try {
        const [campaignTests, allWorkerTests] = await Promise.all([
          campaignsApi.tests(currentCampaign.id),
          workerTestsApi.list({ page_size: 1000 }),
        ]);

        if (cancelled) return;

        setAssignedTests(campaignTests);
        setWorkerTests(
          allWorkerTests.items.filter(
            (item) => Number(item.campaign_id) === Number(currentCampaign.id),
          ),
        );
      } catch {
        if (cancelled) return;
        setAssignedTests([]);
        setWorkerTests([]);
      } finally {
        if (!cancelled) setLoading(false);
      }
    };

    void load();

    return () => {
      cancelled = true;
    };
  }, [currentCampaign]);

  const filteredRows = useMemo(
    () =>
      workerTests.filter((row) =>
        `${row.worker_name || ""} ${row.test_name || ""} ${row.status} ${row.result || ""}`
          .toLowerCase()
          .includes(search.toLowerCase()),
      ),
    [search, workerTests],
  );

  if (!currentCampaign) {
    return null;
  }

  if (loading) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center">
        <Spinner />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <SectionHeader
        eyebrow="Campaign testing"
        title="All Tests"
        description="Review assigned medical tests and campaign-linked worker test records."
      />

      <div className="grid gap-4 lg:grid-cols-[0.85fr_1.15fr]">
        <Card className="p-5">
          <div className="flex items-center gap-3">
            <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-[#0085A3]/10 text-[#0085A3]">
              <FlaskConical className="h-5 w-5" />
            </div>
            <div>
              <p className="text-[10px] font-black uppercase tracking-[0.24em] text-[#0085A3]">
                Assigned Package
              </p>
              <h2 className="text-lg font-black text-slate-950">
                {assignedTests.length} medical tests
              </h2>
            </div>
          </div>

          <div className="mt-5 space-y-2">
            {assignedTests.length ? (
              assignedTests.map((assignment) => {
                const sectionLabel =
                  assignment.test?.section || assignment.test?.category || "Medical Test";
                const codeLabel = assignment.test?.code || assignment.test?.name || "";

                return (
                  <div
                    key={assignment.id}
                    className="rounded-2xl border border-slate-200/80 bg-slate-50/70 px-4 py-3"
                  >
                    <div className="flex items-center justify-between gap-3">
                      <p className="text-sm font-semibold text-slate-800">
                        {assignment.test?.name || `Test #${assignment.test_id}`}
                      </p>
                      <Badge tone={assignment.required ? "active" : "inactive"}>
                        {assignment.required ? "Obligatoire" : "Optionnel"}
                      </Badge>
                    </div>
                    <p className="mt-1 text-xs text-slate-500">
                      {sectionLabel}
                      {codeLabel ? ` · ${codeLabel}` : ""}
                    </p>
                  </div>
                );
              })
            ) : (
              <EmptyState
                title="No assigned tests"
                description="Assign medical tests to this campaign to start test execution tracking."
              />
            )}
          </div>
        </Card>

        <div className="space-y-4">
          <SearchInput
            value={search}
            onChange={setSearch}
            placeholder="Search worker tests..."
          />
          <DataTable
            rows={filteredRows}
            getRowKey={(row) => row.id}
            emptyState={
              <EmptyState
                title="No campaign test records"
                description="Worker test records for this campaign will appear here when the medical team starts entering results."
              />
            }
            columns={[
              {
                key: "worker",
                title: "Worker",
                render: (row) => row.worker_name || `Worker #${row.worker_id}`,
              },
              {
                key: "test",
                title: "Test",
                render: (row) => row.test_name || `Test #${row.medical_test_id}`,
              },
              {
                key: "status",
                title: "Status",
                render: (row) => <Badge tone={row.status}>{row.status}</Badge>,
              },
              {
                key: "result",
                title: "Result",
                render: (row) =>
                  row.result ? (
                    <Badge tone={row.abnormal ? "abnormal" : "normal"}>
                      {row.result}
                    </Badge>
                  ) : (
                    "-"
                  ),
              },
              {
                key: "date",
                title: "Tested At",
                render: (row) => formatDisplayDate(row.tested_at) || "-",
              },
            ]}
          />
        </div>
      </div>
    </div>
  );
};

