import { Activity, AlertTriangle, ClipboardCheck, Users } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Card } from "@/components/common/Card";
import { EmptyState } from "@/components/common/EmptyState";
import { SectionHeader } from "@/components/common/SectionHeader";
import { Spinner } from "@/components/common/Spinner";
import { useCampaignWorkspace } from "@/context/CampaignWorkspaceContext";
import { campaignsApi } from "@/api/campaignsApi";
import { workerTestsApi } from "@/api/workerTestsApi";
import { useSync } from "@/hooks/useSync";
import type { Worker, WorkerTest } from "@/types/entities";
import { formatDisplayDate } from "@/utils/date";

export const CampaignWorkspaceDashboardPage = () => {
  const { currentCampaign } = useCampaignWorkspace();
  const { conflicts } = useSync();
  const [workers, setWorkers] = useState<Worker[]>([]);
  const [workerTests, setWorkerTests] = useState<WorkerTest[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!currentCampaign) return;

    let cancelled = false;

    const load = async () => {
      setLoading(true);
      try {
        const [campaignWorkers, testsResponse] = await Promise.all([
          campaignsApi.workers(currentCampaign.id),
          workerTestsApi.list({ page_size: 1000 }),
        ]);

        if (cancelled) return;

        setWorkers(campaignWorkers);
        setWorkerTests(
          testsResponse.items.filter(
            (item) => Number(item.campaign_id) === Number(currentCampaign.id),
          ),
        );
      } catch {
        if (cancelled) return;
        setWorkers([]);
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

  const stats = useMemo(
    () => [
      {
        label: "Total Workers",
        value: workers.length,
        icon: Users,
        tone: "from-[#0085A3]/14 to-[#0085A3]/5",
      },
      {
        label: "Completed Tests",
        value: workerTests.filter((item) => item.status !== "pending").length,
        icon: ClipboardCheck,
        tone: "from-emerald-100 to-white",
      },
      {
        label: "Pending Tests",
        value: workerTests.filter((item) => item.status === "pending").length,
        icon: Activity,
        tone: "from-amber-100 to-white",
      },
      {
        label: "Sync Conflicts",
        value: conflicts.length,
        icon: AlertTriangle,
        tone: "from-rose-100 to-white",
      },
    ],
    [conflicts.length, workerTests, workers.length],
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
        eyebrow="Workspace overview"
        title="Campaign Dashboard"
        description="Track the operational readiness of the selected campaign workspace."
      />

      <div className="grid gap-4 grid-cols-2 grid-cols-4">
        {stats.map((stat) => (
          <Card
            key={stat.label}
            className={`rounded-[1.8rem] bg-gradient-to-br ${stat.tone} p-5`}
          >
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="text-xs font-bold uppercase tracking-[0.16em] text-slate-500">
                  {stat.label}
                </p>
                <p className="mt-3 text-3xl font-black tracking-tight text-slate-950">
                  {stat.value}
                </p>
              </div>
              <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-white/80 text-[#0085A3] shadow-sm">
                <stat.icon className="h-5 w-5" />
              </div>
            </div>
          </Card>
        ))}
      </div>

      <div className="grid gap-4 grid-cols-[1.4fr_0.9fr]">
        <Card className="p-6">
          <p className="text-[10px] font-black uppercase tracking-[0.24em] text-[#0085A3]">
            Campaign scope
          </p>
          <h2 className="mt-3 text-xl font-black text-slate-950">
            {currentCampaign.company_name}
          </h2>
          <div className="mt-4 grid gap-4 grid-cols-3">
            <div>
              <p className="text-xs font-bold uppercase tracking-[0.16em] text-slate-400">
                Branch
              </p>
              <p className="mt-2 text-sm font-semibold text-slate-700">
                {currentCampaign.branch_name}
              </p>
            </div>
            <div>
              <p className="text-xs font-bold uppercase tracking-[0.16em] text-slate-400">
                Site
              </p>
              <p className="mt-2 text-sm font-semibold text-slate-700">
                {currentCampaign.site_name}
              </p>
            </div>
            <div>
              <p className="text-xs font-bold uppercase tracking-[0.16em] text-slate-400">
                Window
              </p>
              <p className="mt-2 text-sm font-semibold text-slate-700">
                {formatDisplayDate(currentCampaign.start_date)} to {formatDisplayDate(currentCampaign.end_date)}
              </p>
            </div>
          </div>
        </Card>

        <Card className="p-6">
          <p className="text-[10px] font-black uppercase tracking-[0.24em] text-[#0085A3]">
            Completion pulse
          </p>
          {workerTests.length ? (
            <div className="mt-5 space-y-4">
              <div className="rounded-3xl bg-slate-50 p-4">
                <div className="h-3 overflow-hidden rounded-full bg-slate-200">
                  <div
                    className="h-full rounded-full bg-[#0085A3]"
                    style={{
                      width: `${Math.min(
                        100,
                        Math.round(
                          (workerTests.filter((item) => item.status !== "pending").length /
                            workerTests.length) *
                            100,
                        ),
                      )}%`,
                    }}
                  />
                </div>
                <p className="mt-3 text-sm font-semibold text-slate-700">
                  {workerTests.filter((item) => item.status !== "pending").length} of{" "}
                  {workerTests.length} worker tests processed
                </p>
              </div>
            </div>
          ) : (
            <EmptyState
              title="No worker tests yet"
              description="Worker test records will appear here once testing begins inside this campaign workspace."
            />
          )}
        </Card>
      </div>
    </div>
  );
};

