import { useEffect, useState } from "react";
import { ShieldCheck } from "lucide-react";
import { useNavigate, useParams } from "react-router-dom";
import { Button } from "@/components/common/Button";
import { Card } from "@/components/common/Card";
import { EmptyState } from "@/components/common/EmptyState";
import { Spinner } from "@/components/common/Spinner";
import { useCampaignWorkspace } from "@/context/CampaignWorkspaceContext";
import { useCampaignWorkspaceCampaign } from "@/hooks/useCampaignWorkspaceCampaign";

export const CampaignWorkspaceEnterPage = () => {
  const navigate = useNavigate();
  const { campaignId } = useParams();
  const { hasWorkspaceAccess, unlockWorkspace } = useCampaignWorkspace();
  const { campaign, workspace, loading, error } = useCampaignWorkspaceCampaign(campaignId);
  const [errorMessage, setErrorMessage] = useState("");
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (campaignId && hasWorkspaceAccess(campaignId)) {
      navigate(`/app/workspace/${campaignId}/dashboard`, { replace: true });
    }
  }, [campaignId, hasWorkspaceAccess, navigate]);

  if (loading) {
    return (
      <div className="flex min-h-[70vh] items-center justify-center">
        <div className="flex flex-col items-center gap-3">
          <Spinner />
          <p className="text-sm font-semibold text-slate-500">
            Preparing workspace access...
          </p>
        </div>
      </div>
    );
  }

  if (!campaign || error || !campaignId) {
    return (
      <EmptyState
        title="Campaign not available"
        description={error || "We could not prepare workspace access for this campaign."}
        actionLabel="Back to Campaigns"
        onAction={() => navigate("/campaigns")}
      />
    );
  }

  const handleSubmit = async () => {
    if (!campaignId || !workspace?.workspace_code) {
      setErrorMessage("Workspace access is not available right now.");
      return;
    }
    try {
      setSubmitting(true);
      await unlockWorkspace(campaignId, workspace.workspace_code);
      navigate(`/app/workspace/${campaignId}/dashboard`);
    } catch {
      setErrorMessage("Access is not allowed for this workspace right now.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="flex min-h-[75vh] items-center justify-center">
      <Card className="w-full max-w-xl rounded-[2rem] p-8">
        <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-[1.7rem] bg-[#0085A3]/10 text-[#0085A3] shadow-sm">
          <ShieldCheck className="h-8 w-8" />
        </div>

        <div className="mt-6 text-center">
          <p className="text-[10px] font-black uppercase tracking-[0.24em] text-[#0085A3]">
            Secure Campaign Workspace
          </p>
          <h1 className="mt-3 text-3xl font-black tracking-tight text-slate-950">
            {workspace?.campaign_name || campaign.title || campaign.name}
          </h1>
          <p className="mt-2 text-sm text-slate-500">
            {workspace?.company_name || campaign.company_name} · {workspace?.branch_name || campaign.branch_name}
          </p>
          <p className="text-sm text-slate-400">{workspace?.drilling_site_name || campaign.site_name}</p>
        </div>

        <div className="mt-8 space-y-5">
          {errorMessage ? (
            <div className="rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
              {errorMessage}
            </div>
          ) : null}

          <Button className="w-full" onClick={handleSubmit} disabled={submitting}>
            {submitting ? "Ouverture..." : "Entrer dans l'espace de travail"}
          </Button>
        </div>
      </Card>
    </div>
  );
};
