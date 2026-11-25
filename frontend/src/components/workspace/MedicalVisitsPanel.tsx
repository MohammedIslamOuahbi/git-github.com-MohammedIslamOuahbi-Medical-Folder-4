import { useState } from "react";
import {
  CalendarDays,
  Building2,
  FileText,
  Plus,
  ChevronRight,
  ChevronDown,
  ChevronUp,
  CheckSquare,
  Info,
} from "lucide-react";

import { Button } from "@/components/common/Button";
import { Badge } from "@/components/common/Badge";
import { Card } from "@/components/common/Card";
import type { MedicalVisit } from "@/types/entities";
import { formatDisplayDate } from "@/utils/date";

interface Props {
  visits: MedicalVisit[];
  selectedVisitId?: number | null;
  companyName?: string;
  branchName?: string;
  siteName?: string;
  campaignName?: string;
  isCollapsible?: boolean;
  visitHistory?: Array<{
    visitId: number;
    visitDate: string;
    status: string;
    companyName?: string;
    branchName?: string;
    siteName?: string;
    campaignName?: string;
    validatedDoctor?: string;
    aptitude?: string;
    tests: string[];
  }>;

  onOpen: (visitId: number) => void;
  onCreateNew: () => void;
}

const STATUS_TONE: Record<string, "active" | "pending" | "danger"> = {
  validated: "active",
  pending: "pending",
  rejected: "danger",
};

const STATUS_LABEL: Record<string, string> = {
  validated: "Validée",
  pending: "En attente",
  rejected: "Rejetée",
};

function formatDate(iso?: string | null): string {
  return formatDisplayDate(iso) || "—";
}

function getTestNames(visitData: Record<string, unknown>): string[] {
  const source =
    (Array.isArray(visitData.selectedTests) && visitData.selectedTests) ||
    (Array.isArray(visitData.tests) && visitData.tests) ||
    (Array.isArray(visitData.campaignTests) && visitData.campaignTests) ||
    (Array.isArray(visitData.testResults) && visitData.testResults) ||
    (Array.isArray(
      (visitData.medicalDecision as Record<string, unknown> | undefined)?.tests,
    )
      ? ((visitData.medicalDecision as Record<string, unknown>).tests as unknown[])
      : []) ||
    (Array.isArray(
      (visitData.medicalDecision as Record<string, unknown> | undefined)
        ?.selectedTests,
    )
      ? ((visitData.medicalDecision as Record<string, unknown>)
          .selectedTests as unknown[])
      : []);

  return source
    .map((item) => {
      if (typeof item === "string") return item;

      if (typeof item === "object" && item && "name" in item) {
        return String((item as { name?: unknown }).name || "");
      }

      if (typeof item === "object" && item && "label" in item) {
        return String((item as { label?: unknown }).label || "");
      }

      if (typeof item === "object" && item && "test_name" in item) {
        return String((item as { test_name?: unknown }).test_name || "");
      }

      return "";
    })
    .filter(Boolean);
}

export const MedicalVisitsPanel = ({
  visits,
  selectedVisitId,
  companyName,
  isCollapsible = true,
  branchName,
  siteName,
  campaignName,
  visitHistory,
  onOpen,
  onCreateNew,
}: Props) => {
  const [detailsVisitId, setDetailsVisitId] = useState<number | null>(null);
  const [collapsed, setCollapsed] = useState(true);

  return (
    <Card className="overflow-hidden border border-slate-200 bg-white shadow-sm">
      <div className="border-b border-slate-100 px-4 py-3">
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-2.5">
            <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-blue-50 ring-1 ring-blue-100">
              <FileText className="h-4 w-4 text-blue-600" />
            </div>

            <div>
              <h3 className="text-sm font-bold tracking-tight text-slate-900">
                Historique des visites médicales
              </h3>

              <p className="mt-0.5 text-xs font-semibold text-slate-500">
                {visits.length > 0
                  ? `${visits.length} visite${visits.length > 1 ? "s" : ""} enregistrée${
                      visits.length > 1 ? "s" : ""
                    }`
                  : "Aucune visite enregistrée"}
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            {isCollapsible && (
              <Button
                variant="secondary"
                size="sm"
                onClick={() => setCollapsed((value) => !value)}
                className="flex h-8 items-center gap-1.5 px-2"
              >
                {collapsed ? (
                  <ChevronDown className="h-4 w-4" />
                ) : (
                  <ChevronUp className="h-4 w-4" />
                )}
              </Button>
            )}

            <Button
              onClick={onCreateNew}
              size="sm"
              className="flex items-center gap-1.5"
            >
              <Plus className="h-3.5 w-3.5" />
              Nouvelle
            </Button>
          </div>
        </div>
      </div>

      {(!isCollapsible || !collapsed) && (
        <div className="max-h-[430px] overflow-y-auto bg-slate-50/60 p-3">
          {visits.length ? (
            <div className="space-y-2">
              {visits.map((visit) => {
                const isSelected = selectedVisitId === visit.id;
                const historyItem = visitHistory?.find(
                  (item) => item.visitId === visit.id,
                );

                const visitData =
                  (visit.form_data as Record<string, unknown> | null) || {};

                const visitDecision =
                  (visitData.medicalDecision as
                    | Record<string, unknown>
                    | undefined) || {};

                const visitValidation =
                  (visitDecision.validation as
                    | Record<string, unknown>
                    | undefined) || {};

                const companyLabel =
                  String(
                    historyItem?.companyName ||
                      visitData.companyName ||
                      visitData.company_name ||
                      companyName ||
                      "-",
                  ).trim() || "-";

                const branchLabel =
                  String(
                    historyItem?.branchName ||
                      visitData.branchName ||
                      visitData.branch_name ||
                      branchName ||
                      "-",
                  ).trim() || "-";

                const siteLabel =
                  String(
                    historyItem?.siteName ||
                      visitData.siteName ||
                      visitData.site_name ||
                      siteName ||
                      "-",
                  ).trim() || "-";

                const campaignLabel =
                  String(
                    historyItem?.campaignName ||
                      visitData.campaignName ||
                      visitData.campaign_name ||
                      campaignName ||
                      "-",
                  ).trim() || "-";

                const testedNames = historyItem?.tests?.length
                  ? historyItem.tests
                  : getTestNames(visitData);

                const validatedDoctor =
                  String(
                    historyItem?.validatedDoctor ||
                      visitValidation.validatingDoctor ||
                      visitValidation.doctor ||
                      visitData.validatedDoctor ||
                      visitData.validateDoctor ||
                      "",
                  ).trim() || "-";

                const aptitude = String(
                  historyItem?.aptitude ||
                    visitDecision.aptitude ||
                    visitDecision.medicalAptitude ||
                    visitData.aptitude ||
                    "",
                ).trim();

                const aptitudeTone = aptitude.toLowerCase().includes("inapte")
                  ? "danger"
                  : aptitude.toLowerCase().includes("apte")
                    ? "active"
                    : "pending";

                return (
                  <div
                    key={visit.id}
                    onClick={() => onOpen(visit.id)}
                    className={`group cursor-pointer rounded-xl border px-3.5 py-3 transition-all duration-200 ${
                      isSelected
                        ? "border-emerald-200 border-l-4 border-l-emerald-600 bg-emerald-50 shadow-sm ring-1 ring-emerald-100"
                        : "border-slate-200 bg-white hover:-translate-y-0.5 hover:border-blue-200 hover:bg-blue-50/40 hover:shadow-sm"
                    }`}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="flex min-w-0 items-start gap-3">
                        <div
                          className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-lg transition-colors ${
                            isSelected
                              ? "bg-emerald-100"
                              : "bg-slate-100 group-hover:bg-blue-100"
                          }`}
                        >
                          <CalendarDays
                            className={`h-4 w-4 ${
                              isSelected
                                ? "text-emerald-700"
                                : "text-slate-500 group-hover:text-blue-600"
                            }`}
                          />
                        </div>

                        <div className="min-w-0">
                          <div className="flex flex-wrap items-center gap-2">
                            <h4
                              className={`truncate text-sm font-semibold ${
                                isSelected
                                  ? "text-emerald-800"
                                  : "text-slate-900"
                              }`}
                            >
                              {formatDate(visit.visit_date)}
                            </h4>

                            <Badge tone={STATUS_TONE[visit.status] ?? "pending"}>
                              {STATUS_LABEL[visit.status] ?? visit.status}
                            </Badge>
                          </div>

                          <div className="mt-1.5 flex min-w-0 items-center gap-1.5 text-xs text-slate-500">
                            <Building2 className="h-3.5 w-3.5 shrink-0 text-slate-400" />
                            <span className="truncate">
                              {companyLabel} · {branchLabel} · {siteLabel} ·{" "}
                              {campaignLabel}
                            </span>
                          </div>
                        </div>
                      </div>

                      <div className="flex shrink-0 items-center gap-2">
                        <Button
                          variant="secondary"
                          size="sm"
                          onClick={(event) => {
                            event.stopPropagation();
                            setDetailsVisitId(
                              detailsVisitId === visit.id ? null : visit.id,
                            );
                          }}
                          className="flex h-8 items-center gap-1.5 px-3 text-xs"
                        >
                          <Info className="h-3.5 w-3.5" />
                          Détail
                        </Button>

                        <Button
                          variant="secondary"
                          size="sm"
                          onClick={(event) => {
                            event.stopPropagation();
                            onOpen(visit.id);
                          }}
                          className={`flex h-8 shrink-0 items-center gap-1.5 px-3 text-xs transition-all ${
                            isSelected
                              ? "bg-emerald-600 text-white shadow-sm hover:bg-emerald-700"
                              : "opacity-70 group-hover:opacity-100"
                          }`}
                        >
                          Consulter
                          <ChevronRight className="h-3.5 w-3.5 transition-transform group-hover:translate-x-0.5" />
                        </Button>
                      </div>
                    </div>

                    {detailsVisitId === visit.id && (
                      <div className="mt-3 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-600">
                        <div className="flex flex-wrap items-center gap-1.5">
                          <FileText className="h-3.5 w-3.5 text-slate-400" />
                          <span className="font-semibold text-slate-700">
                            Médecin validateur:
                          </span>
                          <span>{validatedDoctor}</span>

                          {aptitude && (
                            <>
                              <span className="text-slate-300">·</span>
                              <Badge tone={aptitudeTone}>{aptitude}</Badge>
                            </>
                          )}
                        </div>

                        <div className="mt-2 flex items-start gap-1.5">
                          <CheckSquare className="mt-0.5 h-3.5 w-3.5 shrink-0 text-slate-400" />
                          <div>
                            <span className="font-semibold text-slate-700">
                              Tests:
                            </span>{" "}
                            {testedNames.length ? (
                              <span>{testedNames.join(", ")}</span>
                            ) : (
                              <span className="italic text-slate-400">
                                Tests non renseignés pour cette visite
                              </span>
                            )}
                          </div>
                        </div>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-slate-200 bg-white px-6 py-12 text-center">
              <div className="mb-3 flex h-14 w-14 items-center justify-center rounded-2xl bg-slate-100">
                <FileText className="h-6 w-6 text-slate-400" />
              </div>

              <h4 className="text-sm font-semibold text-slate-900">
                Aucune visite médicale
              </h4>

              <p className="mt-1 max-w-sm text-xs text-slate-500">
                Ce travailleur n&apos;a encore aucune visite médicale enregistrée.
              </p>

              <Button
                className="mt-5 flex items-center gap-2"
                onClick={onCreateNew}
              >
                <Plus className="h-4 w-4" />
                Créer la première visite
              </Button>
            </div>
          )}
        </div>
      )}
    </Card>
  );
};
