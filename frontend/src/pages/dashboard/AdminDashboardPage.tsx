import { Fragment, useEffect, useState } from "react";
import { Eye, FileText, FlaskConical, Lock, Pencil, Trash2, Unlock, UserRoundCog, Users } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { campaignsApi } from "@/api/campaignsApi";
import { dashboardApi } from "@/api/dashboardApi";
import { Badge } from "@/components/common/Badge";
import { Button } from "@/components/common/Button";
import { Card } from "@/components/common/Card";
import { DashboardIdentityCard } from "@/components/dashboard/DashboardIdentityCard";
import { EmptyState } from "@/components/common/EmptyState";
import { Input } from "@/components/common/Input";
import { Modal } from "@/components/common/Modal";
import { SectionHeader } from "@/components/common/SectionHeader";
import { Spinner } from "@/components/common/Spinner";
import { useAuth } from "@/context/AuthContext";
import type { AdminDashboardData } from "@/types/dashboard";
import {
  DashboardAccessSection,
  DashboardMetricGrid,
  fallbackAdminDashboardData,
  normalizeCampaignStatusTone,
  type RecentCampaignRow,
} from "./components/AdminDashboardWidgets";
import { formatDisplayDate } from "@/utils/date";
import { formatNumber } from "@/utils/format";
import { hasPermission } from "@/utils/permissions";
import { cn } from "@/utils/cn";

const campaignStatusLabel: Record<string, string> = {
  active: "Active",
  completed: "Terminée",
  draft: "Brouillon",
  cancelled: "Annulée",
};

export const AdminDashboardPage = () => {
  const navigate = useNavigate();
  const { user } = useAuth();
  const canLockCampaigns = hasPermission(user, "campaigns:lock");
  const [data, setData] = useState<AdminDashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [usingFallback, setUsingFallback] = useState(false);
  const [actionLoadingId, setActionLoadingId] = useState<number | null>(null);
  const [expandedCampaignId, setExpandedCampaignId] = useState<number | null>(null);
  const [coverageModal, setCoverageModal] = useState<{
    title: string;
    items: string[];
  } | null>(null);
  const [deleteCampaignTarget, setDeleteCampaignTarget] = useState<RecentCampaignRow | null>(null);
  const [deletePassword, setDeletePassword] = useState("");
  const [deletingCampaign, setDeletingCampaign] = useState(false);

  const loadDashboard = async () => {
    setLoading(true);
    setError(null);
    setUsingFallback(false);

    try {
      const response = await dashboardApi.getAdmin();
      setData(response);
      return;
    } catch {
      setData(fallbackAdminDashboardData());
      setError("Les données en temps réel sont indisponibles. Les données de démonstration sont affichées.");
      setUsingFallback(true);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadDashboard();
  }, []);

  const openEditModal = (campaign: RecentCampaignRow) => {
    navigate(`/campaigns/${campaign.id}/edit`);
  };

  const removeCampaign = async () => {
    if (!deleteCampaignTarget) {
      return;
    }
    if (!deletePassword) {
      setError("Saisissez votre mot de passe pour supprimer cette campagne.");
      return;
    }
    setActionLoadingId(deleteCampaignTarget.id);
    setDeletingCampaign(true);
    setError(null);
    try {
      await campaignsApi.remove(deleteCampaignTarget.id, deletePassword);
      setDeleteCampaignTarget(null);
      setDeletePassword("");
      await loadDashboard();
    } catch {
      setError("Impossible de supprimer la campagne. Veuillez réessayer.");
    } finally {
      setDeletingCampaign(false);
      setActionLoadingId(null);
    }
  };

  const toggleCampaignLock = async (campaign: RecentCampaignRow) => {
    if (!canLockCampaigns) {
      setError("Seul le Super Administrateur peut verrouiller ou déverrouiller une campagne.");
      return;
    }
    setActionLoadingId(campaign.id);
    setError(null);
    try {
      await campaignsApi.update(campaign.id, {
        status: campaign.status === "completed" ? "active" : "completed",
      });
      await loadDashboard();
    } catch {
      setError("Impossible de modifier le statut de la campagne. Veuillez réessayer.");
    } finally {
      setActionLoadingId(null);
    }
  };

  const openCoverage = (title: string, items: string[]) => {
    setCoverageModal({ title, items });
  };

  const buildCoverageTitle = (row: RecentCampaignRow, label: string) =>
    `Campagne ${row.branch_name || row.title || row.name || `n° ${row.id}`} — ${label}`;

  const buildMissionGroup = (row: RecentCampaignRow) => [
    ...(row.doctor_names || []).map((name) => `Médecin : ${name}`),
    ...(row.assistant_names || []).map((name) => `Assistant : ${name}`),
  ];

  if (loading) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center">
        <div className="flex flex-col items-center gap-4">
          <Spinner />
          <p className="text-sm font-medium text-gray-500">Chargement du tableau de bord administrateur...</p>
        </div>
      </div>
    );
  }

  if (!data) {
    return (
      <EmptyState
        title="Tableau de bord indisponible"
        description="Le tableau de bord ne peut pas être chargé pour le moment."
        actionLabel="Réessayer"
        onAction={() => void loadDashboard()}
      />
    );
  }

  return (
    <div className="space-y-6 pb-6">
      <SectionHeader
        eyebrow="Administration"
        title="Tableau de bord"
        description="Une vue d'ensemble claire de l'activité médicale, des campagnes et des utilisateurs."
        actionLabel="Actualiser"
        onAction={() => void loadDashboard()}
      />

      {error && (
        <Card className={usingFallback ? "border-amber-200 bg-amber-50/80" : "border-rose-200 bg-rose-50/80"}>
          <div className="flex items-center justify-between gap-4">
            <p className="text-sm font-medium text-slate-700">{error}</p>
            <Button variant="secondary" size="sm" onClick={() => void loadDashboard()}>
              Reessayer
            </Button>
          </div>
        </Card>
      )}

      <DashboardIdentityCard />

      <DashboardMetricGrid data={data} />

      <Card className="overflow-hidden rounded-xl border-slate-200 bg-white p-0 shadow-sm shadow-slate-200/50">
        <div className="flex items-center justify-between gap-3 border-b border-slate-100 px-5 py-4">
          <div>
            <h2 className="text-[15px] font-semibold tracking-tight text-slate-900">Campagnes récentes</h2>
            <p className="mt-1 text-xs leading-5 text-slate-500">
              Sélectionnez une campagne pour afficher ses détails et ses actions.
            </p>
          </div>
        </div>
        <div className="overflow-x-auto bg-white">
          <table className="min-w-full divide-y divide-gray-100">
            <thead className="bg-slate-50/80">
              <tr>
                <th className="px-4 py-3 text-left text-[11px] font-semibold uppercase tracking-wider text-slate-500">Campagne</th>
                <th className="px-4 py-3 text-left text-[11px] font-semibold uppercase tracking-wider text-slate-500">Période</th>
                <th className="px-4 py-3 text-left text-[11px] font-semibold uppercase tracking-wider text-slate-500">Statut</th>
                <th className="px-4 py-3 text-left text-[11px] font-semibold uppercase tracking-wider text-slate-500">Affectations</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100 bg-white">
              {data.recent_campaigns.length === 0 ? (
                <tr>
                  <td colSpan={4} className="px-3 py-10 text-center text-[13px] text-gray-500">
                    Aucune campagne récente.
                  </td>
                </tr>
              ) : (
                data.recent_campaigns.map((row) => {
                  const expanded = expandedCampaignId === row.id;
                  const rowBusy = actionLoadingId === row.id;
                  const isLocked = row.status === "completed";

                  return (
                    <Fragment key={row.id}>
                      <tr
                        onClick={() => setExpandedCampaignId((current) => (current === row.id ? null : row.id))}
                        className={cn(
                          "cursor-pointer transition-colors hover:bg-sky-50/50",
                          expanded && "bg-sky-50/70",
                        )}
                      >
                        <td className="px-4 py-3.5">
                          <div>
                            <p className="text-sm font-semibold text-slate-900">{row.title || row.name}</p>
                            <p className="mt-1 text-xs text-slate-500">
                              {row.company_name || "Entreprise médicale"}
                              {row.branch_name ? ` - ${row.branch_name}` : ""}
                            </p>
                          </div>
                        </td>
                        <td className="px-4 py-3.5 text-xs leading-5 text-slate-500">
                          <span className="font-medium text-slate-700">Du :</span> {formatDisplayDate(row.start_date)}
                          <br />
                          <span className="font-medium text-slate-700">Au :</span> {formatDisplayDate(row.end_date)}
                        </td>
                        <td className="px-4 py-3.5">
                          <Badge
                            tone={normalizeCampaignStatusTone(row.status)}
                            className={
                              row.status === "completed"
                                ? "border-emerald-200 bg-emerald-50 text-emerald-700"
                                : row.status === "active"
                                  ? "border-sky-200 bg-sky-50 text-sky-700"
                                  : row.status === "draft"
                                    ? "border-amber-200 bg-amber-50 text-amber-700"
                                    : "border-rose-200 bg-rose-50 text-rose-700"
                            }
                          >
                            {campaignStatusLabel[row.status] || row.status}
                          </Badge>
                        </td>
                        <td className="px-4 py-3.5">
                          <div className="flex flex-wrap gap-1.5 text-xs">
                            <span className="inline-flex items-center gap-1.5 rounded-md bg-slate-100 px-2.5 py-1.5 text-[11px] font-medium text-slate-600">
                              <UserRoundCog className="h-3.5 w-3.5" />
                              {formatNumber((row.doctor_names || []).length + (row.assistant_names || []).length)} équipe
                            </span>
                            <span className="inline-flex items-center gap-1.5 rounded-md bg-slate-100 px-2.5 py-1.5 text-[11px] font-medium text-slate-600">
                              <Users className="h-3.5 w-3.5" />
                              {formatNumber(row.worker_count || 0)} travailleurs
                            </span>
                            <span className="inline-flex items-center gap-1.5 rounded-md bg-slate-100 px-2.5 py-1.5 text-[11px] font-medium text-slate-600">
                              <FlaskConical className="h-3.5 w-3.5" />
                              {formatNumber(row.tests_count || 0)} tests
                            </span>
                          </div>
                        </td>
                      </tr>
                      {expanded ? (
                        <tr className="bg-sky-50/40">
                          <td colSpan={4} className="border-t border-sky-100 px-4 py-4">
                            <div className="space-y-3">
                              <div className="flex flex-wrap items-center gap-2">
                                <Button
                                  variant="secondary"
                                  size="sm"
                                  icon={Eye}
                                  onClick={(event) => {
                                    event.stopPropagation();
                                    navigate(`/campaigns/${row.id}`);
                                  }}
                                >
                                  Ouvrir
                                </Button>
                                <Button
                                  variant="secondary"
                                  size="sm"
                                  icon={Pencil}
                                  onClick={(event) => {
                                    event.stopPropagation();
                                    openEditModal(row);
                                  }}
                                >
                                  Modifier
                                </Button>
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  icon={FileText}
                                  onClick={(event) => {
                                    event.stopPropagation();
                                    navigate(`/reports?campaign_id=${row.id}&company_id=${row.company_id || ""}&branch_id=${row.branch_id || ""}`);
                                  }}
                                >
                                  Rapport
                                </Button>
                                {canLockCampaigns ? (
                                  <Button
                                    variant="ghost"
                                    size="sm"
                                    icon={isLocked ? Unlock : Lock}
                                    loading={rowBusy}
                                    onClick={(event) => {
                                      event.stopPropagation();
                                      void toggleCampaignLock(row);
                                    }}
                                  >
                                    {isLocked ? "Deverrouiller" : "Verrouiller"}
                                  </Button>
                                ) : null}
                                <Button
                                  variant="danger"
                                  size="sm"
                                  icon={Trash2}
                                  loading={rowBusy && deletingCampaign}
                                  onClick={(event) => {
                                    event.stopPropagation();
                                    setDeleteCampaignTarget(row);
                                    setDeletePassword("");
                                  }}
                                >
                                  Supprimer
                                </Button>
                              </div>
                              <div className="flex flex-wrap items-center gap-2">
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  icon={UserRoundCog}
                                  onClick={(event) => {
                                    event.stopPropagation();
                                    openCoverage(buildCoverageTitle(row, "Équipe médicale"), buildMissionGroup(row));
                                  }}
                                >
                                  Équipe médicale
                                </Button>
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  icon={UserRoundCog}
                                  onClick={(event) => {
                                    event.stopPropagation();
                                    openCoverage(buildCoverageTitle(row, "Médecins"), row.doctor_names || []);
                                  }}
                                >
                                  Medecins
                                </Button>
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  icon={Users}
                                  onClick={(event) => {
                                    event.stopPropagation();
                                    openCoverage(buildCoverageTitle(row, "Travailleurs"), row.worker_names || []);
                                  }}
                                >
                                  Travailleurs
                                </Button>
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  icon={FlaskConical}
                                  onClick={(event) => {
                                    event.stopPropagation();
                                    openCoverage(buildCoverageTitle(row, "Tests"), row.test_names || []);
                                  }}
                                >
                                  Tests
                                </Button>
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  icon={UserRoundCog}
                                  onClick={(event) => {
                                    event.stopPropagation();
                                    openCoverage(buildCoverageTitle(row, "Assistants"), row.assistant_names || []);
                                  }}
                                >
                                  Assistants
                                </Button>
                              </div>
                            </div>
                          </td>
                        </tr>
                      ) : null}
                    </Fragment>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </Card>

      <DashboardAccessSection user={user} onNavigate={navigate} />
      <Modal
        open={Boolean(coverageModal)}
        title={coverageModal?.title || "Détails de la campagne"}
        onClose={() => setCoverageModal(null)}
      >
        {coverageModal?.items.length ? (
          <div className="max-h-[360px] space-y-1.5 overflow-y-auto">
            {coverageModal.items.map((item) => (
              <div
                key={item}
                className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2.5 text-sm text-slate-700"
              >
                {item}
              </div>
            ))}
          </div>
        ) : (
          <p className="text-sm text-slate-500">Aucun élément trouvé pour cette campagne.</p>
        )}
      </Modal>

      <Modal
        open={Boolean(deleteCampaignTarget)}
        title={deleteCampaignTarget ? `Supprimer la campagne n° ${deleteCampaignTarget.id}` : "Supprimer la campagne"}
        onClose={() => {
          setDeleteCampaignTarget(null);
          setDeletePassword("");
        }}
      >
        <div className="space-y-4">
          <p className="text-sm leading-6 text-slate-600">
            Saisissez votre mot de passe pour confirmer la suppression de{" "}
            <span className="font-semibold text-slate-900">
              {deleteCampaignTarget?.title || deleteCampaignTarget?.name || "this campaign"}
            </span>
            .
          </p>
          <Input
            label="Mot de passe"
            type="password"
            value={deletePassword}
            onChange={(event) => setDeletePassword(event.target.value)}
          />
        </div>
        <div className="mt-6 flex justify-end gap-3">
          <Button
            variant="secondary"
            onClick={() => {
              setDeleteCampaignTarget(null);
              setDeletePassword("");
            }}
            disabled={deletingCampaign}
          >
            Annuler
          </Button>
          <Button variant="danger" onClick={() => void removeCampaign()} disabled={deletingCampaign}>
            {deletingCampaign ? "Suppression..." : "Supprimer"}
          </Button>
        </div>
      </Modal>
    </div>
  );
};