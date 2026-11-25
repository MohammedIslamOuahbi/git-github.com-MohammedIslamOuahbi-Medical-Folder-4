import { useEffect } from "react";
import { Navigate, Outlet, useNavigate, useParams } from "react-router-dom";
import { CampaignWorkspaceHeader } from "@/components/layout/CampaignWorkspaceHeader";
import { CampaignWorkspaceSidebar } from "@/components/layout/CampaignWorkspaceSidebar";
import { EmptyState } from "@/components/common/EmptyState";
import { Spinner } from "@/components/common/Spinner";
import { useCampaignWorkspace } from "@/context/CampaignWorkspaceContext";
import { useCampaignWorkspaceCampaign } from "@/hooks/useCampaignWorkspaceCampaign";
import { useAuth } from "@/hooks/useAuth";
import { useSync } from "@/hooks/useSync";

export const CampaignWorkspaceShell = () => {
  const navigate = useNavigate();
  const { campaignId } = useParams();
  const { user } = useAuth();
  const { setCurrentCampaign, setCurrentWorkspace, exitWorkspace } = useCampaignWorkspace();
  const { campaign, workspace, loading, error } = useCampaignWorkspaceCampaign(campaignId);
  const { online } = useSync();

  useEffect(() => {
    setCurrentCampaign(campaign);
    setCurrentWorkspace(workspace);
    return () => {
      setCurrentCampaign(null);
      setCurrentWorkspace(null);
    };
  }, [campaign, setCurrentCampaign, setCurrentWorkspace, workspace]);

  const handleExit = () => {
    if (!campaignId) return;
    exitWorkspace(campaignId);
    navigate("/campaigns");
  };

  if (!campaignId) {
    return <Navigate to="/campaigns" replace />;
  }

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-shell-glow">
        <div className="flex flex-col items-center gap-3">
          <Spinner />
          <p className="text-sm font-semibold text-slate-500">
            Chargement de l'espace de travail de la campagne...
          </p>
        </div>
      </div>
    );
  }

  if (!campaign || error) {
    return (
      <div className="min-h-screen bg-shell-glow px-4 py-8">
        <div className="mx-auto max-w-3xl">
          <EmptyState
            title="Espace de travail indisponible"
            description={error || "Impossible de charger les d?tails de l?espace de travail."}
            actionLabel="Retour aux campagnes m?dicales"
            onAction={() => navigate("/campaigns")}
          />
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-shell-glow">
      <div className="flex min-h-screen min-w-[1280px]">
        <CampaignWorkspaceSidebar
          campaignId={String(campaign.id)}
          workspace={workspace}
          online={online}
          onExit={handleExit}
        />

        <div className="flex min-w-0 flex-1 flex-col">
          <CampaignWorkspaceHeader
            campaign={campaign}
            workspace={workspace}
            currentUser={user}
            online={online}
            onExit={handleExit}
          />
          <main className="flex-1 px-6 py-6">
            <div className="mx-auto w-full max-w-[1760px]">
              <Outlet />
            </div>
          </main>
        </div>
      </div>
    </div>
  );
};
