import { useEffect, useState } from "react";
import { campaignsApi } from "@/api/campaignsApi";
import { workspacesApi } from "@/api/workspacesApi";
import type { Workspace, WorkspaceCampaign } from "@/types/workspace";

export const useCampaignWorkspaceCampaign = (campaignId?: string) => {
  const [campaign, setCampaign] = useState<WorkspaceCampaign | null>(null);
  const [workspace, setWorkspace] = useState<Workspace | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!campaignId) {
      setCampaign(null);
      setWorkspace(null);
      setLoading(false);
      setError("Campaign not found.");
      return;
    }

    let cancelled = false;

    const loadCampaign = async () => {
      setLoading(true);
      setError(null);

      try {
        const workspaceData = await workspacesApi.getByCampaign(campaignId);
        if (cancelled) return;

        let baseCampaign: WorkspaceCampaign | null = null;
        try {
          baseCampaign = await campaignsApi.get(campaignId);
        } catch {
          baseCampaign = null;
        }

        if (cancelled) return;

        setWorkspace(workspaceData);
        setCampaign({
          ...(baseCampaign || {
            id: Number(campaignId),
            name: workspaceData.campaign_name || "Campaign",
            title: workspaceData.campaign_name || "Campaign",
            company_id: workspaceData.company_id,
            branch_id: workspaceData.branch_id,
            drilling_site_id: workspaceData.drilling_site_id,
            start_date: String(workspaceData.start_date),
            end_date: String(workspaceData.end_date),
            status: workspaceData.status as WorkspaceCampaign["status"],
            created_at: workspaceData.created_at,
            updated_at: workspaceData.updated_at,
          }),
          company_name: workspaceData.company_name,
          branch_name: workspaceData.branch_name,
          site_name: workspaceData.drilling_site_name || "No site assigned",
        } as WorkspaceCampaign);
      } catch (caught) {
        if (cancelled) return;
        setCampaign(null);
        setWorkspace(null);
        const status = (caught as { response?: { status?: number } })?.response?.status;
        if (status === 403) {
          setError("Accès refusé à cet espace de travail.");
        } else if (status === 404) {
          setError("La campagne ou son espace de travail est introuvable.");
        } else {
          setError("Impossible de charger les détails de l’espace de travail.");
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    };

    void loadCampaign();

    return () => {
      cancelled = true;
    };
  }, [campaignId]);

  return { campaign, workspace, loading, error };
};
