import apiClient from "./axios";
import type { Workspace, WorkspaceSession } from "@/types/workspace";

const normalizeWorkspace = (workspace: Workspace): Workspace => ({
  ...workspace,
  campaign_name: workspace.campaign_name || workspace.campaignName || "Campaign",
  company_name: workspace.company_name || workspace.companyName || "Company",
  branch_name: workspace.branch_name || workspace.branchName || "Branch",
  drilling_site_name:
    workspace.drilling_site_name || workspace.drillingSiteName || "Operational site",
});

export const workspacesApi = {
  getByCampaign: async (campaignId: number | string) => {
    const { data } = await apiClient.get<Workspace>(`/workspaces/by-campaign/${campaignId}`);
    return normalizeWorkspace(data);
  },
  accessByCampaign: async (campaignId: number | string, access_code: string) => {
    const { data } = await apiClient.post<WorkspaceSession>(`/workspaces/by-campaign/${campaignId}/access`, {
      access_code,
    });
    return {
      ...data,
      workspace: normalizeWorkspace(data.workspace),
    };
  },
  updateByCampaign: async (campaignId: number | string, payload: Partial<Workspace>) => {
    const { data } = await apiClient.put<Workspace>(`/workspaces/by-campaign/${campaignId}`, payload);
    return normalizeWorkspace(data);
  },
};
