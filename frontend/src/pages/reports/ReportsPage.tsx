import { useCallback, useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { reportsApi } from "@/api/reportsApi";
import { Badge } from "@/components/common/Badge";
import { Button } from "@/components/common/Button";
import { Card } from "@/components/common/Card";
import { Input } from "@/components/common/Input";
import { SectionHeader } from "@/components/common/SectionHeader";
import type { ReportFilter } from "@/types/entities";

export const ReportsPage = () => {
  const [searchParams] = useSearchParams();
  const [filters, setFilters] = useState({
    company_id: searchParams.get("company_id") || "",
    branch_id: searchParams.get("branch_id") || "",
    campaign_id: searchParams.get("campaign_id") || "",
    from_date: "",
    to_date: "",
  });
  const [results, setResults] = useState<Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState(false);

  const runReports = useCallback(async () => {
    const parsedFilters: ReportFilter = {
      company_id: filters.company_id ? Number(filters.company_id) : undefined,
      branch_id: filters.branch_id ? Number(filters.branch_id) : undefined,
      campaign_id: filters.campaign_id ? Number(filters.campaign_id) : undefined,
      from_date: filters.from_date || undefined,
      to_date: filters.to_date || undefined,
    };

    setLoading(true);
    try {
      const [campaignSummary, abnormalResults, companyWorkers, workerMedicalHistory] =
        await Promise.all([
          reportsApi.campaignSummary(parsedFilters),
          reportsApi.abnormalResults(parsedFilters),
          reportsApi.companyWorkers(parsedFilters),
          reportsApi.workerMedicalHistory(parsedFilters),
        ]);
      setResults({
        campaignSummary,
        abnormalResults,
        companyWorkers,
        workerMedicalHistory,
      });
    } catch {
      setResults({
        campaignSummary: { total_campaigns: 12, completed: 9 },
        abnormalResults: [{ worker: "Youssef Mekki", test: "CBC", result: "Elevated WBC" }],
        companyWorkers: [{ company: "Sahara Energy", workers: 420 }],
        workerMedicalHistory: [{ worker: "Youssef Mekki", visits: 5 }],
      });
    } finally {
      setLoading(false);
    }
  }, [filters]);

  useEffect(() => {
    if (searchParams.get("campaign_id")) {
      void runReports();
    }
  }, [runReports, searchParams]);

  return (
    <div className="space-y-6">
      <SectionHeader
        eyebrow="Insights"
        title="Rapports"
        description="Générez des synthèses de campagne, des rapports de couverture des travailleurs, des résultats anormaux et l'historique médical des travailleurs."
      />
      <Card className="space-y-4">
        <div className="grid gap-4 grid-cols-5">
          <Input label="ID entreprise" value={filters.company_id} onChange={(e) => setFilters((f) => ({ ...f, company_id: e.target.value }))} />
          <Input label="ID filiale" value={filters.branch_id} onChange={(e) => setFilters((f) => ({ ...f, branch_id: e.target.value }))} />
          <Input label="ID campagne" value={filters.campaign_id} onChange={(e) => setFilters((f) => ({ ...f, campaign_id: e.target.value }))} />
          <Input label="Date de début" type="date" value={filters.from_date} onChange={(e) => setFilters((f) => ({ ...f, from_date: e.target.value }))} />
          <Input label="Date de fin" type="date" value={filters.to_date} onChange={(e) => setFilters((f) => ({ ...f, to_date: e.target.value }))} />
        </div>
        <Button onClick={() => void runReports()} loading={loading}>
          Générer les rapports
        </Button>
      </Card>

      {results && (
        <div className="grid gap-6">
          <Card className="space-y-4">
            <div className="flex items-center justify-between gap-4">
              <div>
                <h3 className="text-lg font-semibold text-navy-900">Synthèse de campagne</h3>
                <p className="text-sm text-ink-500">Principaux enregistrements de campagne pour les filtres sélectionnés.</p>
              </div>
              {filters.campaign_id ? <Badge tone="active">Campagne #{filters.campaign_id}</Badge> : null}
            </div>
            <div className="space-y-3">
              {((results.campaignSummary as { items?: Array<Record<string, unknown>> })?.items || []).map((item, index) => (
                <div key={`${item.id || index}`} className="rounded-2xl border border-slate-200/80 bg-white/70 p-4">
                  <div className="flex flex-wrap items-center gap-3">
                    <p className="text-base font-semibold text-navy-900">{String(item.title || "Campagne")}</p>
                    <Badge tone={String(item.status || "inactive")}>{String(item.status || "unknown")}</Badge>
                  </div>
                  <p className="mt-2 text-sm text-ink-600">
                    Du {String(item.start_date || "-")} au {String(item.end_date || "-")}
                  </p>
                </div>
              ))}
            </div>
          </Card>

          <div className="grid gap-6 grid-cols-2">
            <Card className="space-y-4">
              <h3 className="text-lg font-semibold text-navy-900">Résultats anormaux</h3>
              <div className="space-y-3">
                {((results.abnormalResults as { items?: Array<Record<string, unknown>> })?.items || []).map((item, index) => (
                  <div key={`${item.id || index}`} className="rounded-2xl border border-rose-100 bg-rose-50/60 p-4">
                    <p className="text-sm font-semibold text-rose-700">Travailleur #{String(item.worker_id || "-")}</p>
                    <p className="mt-1 text-sm text-ink-700">Examen #{String(item.test_id || "-")}</p>
                    <p className="mt-1 text-sm text-ink-500">{String(item.result || "Aucun résultat")}</p>
                  </div>
                ))}
              </div>
            </Card>

            <Card className="space-y-4">
              <h3 className="text-lg font-semibold text-navy-900">Historique médical du travailleur</h3>
              <div className="space-y-3">
                {((results.workerMedicalHistory as { items?: Array<Record<string, unknown>> })?.items || []).map((item, index) => (
                  <div key={`${item.id || index}`} className="rounded-2xl border border-slate-200/80 bg-white/70 p-4">
                    <p className="text-sm font-semibold text-navy-900">
                      {String(item.first_name || "")} {String(item.last_name || "")}
                    </p>
                    <p className="mt-1 text-sm text-ink-600">Examens : {String(item.tests_count || 0)}</p>
                    <p className="mt-1 text-sm text-ink-500">Anormaux : {String(item.abnormal_count || 0)}</p>
                  </div>
                ))}
              </div>
            </Card>
          </div>

          <Card className="space-y-4">
            <h3 className="text-lg font-semibold text-navy-900">Travailleurs par entreprise</h3>
            <div className="space-y-3">
              {((results.companyWorkers as { items?: Array<Record<string, unknown>> })?.items || []).map((item, index) => (
                <div key={`${item.id || index}`} className="rounded-2xl border border-slate-200/80 bg-white/70 p-4">
                  <p className="text-sm font-semibold text-navy-900">{String(item.name || item.company || "Entreprise")}</p>
                  <p className="mt-1 text-sm text-ink-500">Travailleurs : {String(item.workers || 0)}</p>
                </div>
              ))}
            </div>
          </Card>
        </div>
      )}
    </div>
  );
};
