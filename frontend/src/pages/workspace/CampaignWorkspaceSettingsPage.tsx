import { LockKeyhole, LogOut } from "lucide-react";
import { useNavigate, useParams } from "react-router-dom";
import { Badge } from "@/components/common/Badge";
import { Button } from "@/components/common/Button";
import { Card } from "@/components/common/Card";
import { SectionHeader } from "@/components/common/SectionHeader";
import { useCampaignWorkspace } from "@/context/CampaignWorkspaceContext";

export const CampaignWorkspaceSettingsPage = () => {
  const navigate = useNavigate();
  const { campaignId } = useParams();
  const { currentCampaign, currentWorkspace, hasWorkspaceAccess, exitWorkspace } = useCampaignWorkspace();

  if (!currentCampaign || !campaignId) {
    return null;
  }

  const unlocked = hasWorkspaceAccess(campaignId);

  const handleExit = () => {
    exitWorkspace(campaignId);
    navigate("/campaigns");
  };

  return (
    <div className="space-y-6">
      <SectionHeader
        eyebrow="Workspace controls"
        title="Parametres"
        description="Configurez l'acces du workspace. Les signatures PNG sont gerees dans le profil de chaque utilisateur."
      />

      <div className="grid gap-4">
        <Card className="p-6">
          <div className="flex items-center gap-3">
            <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-[#0085A3]/10 text-[#0085A3]">
              <LockKeyhole className="h-5 w-5" />
            </div>
            <div>
              <p className="text-[10px] font-black uppercase tracking-[0.24em] text-[#0085A3]">
                Workspace access
              </p>
              <h2 className="text-lg font-black text-slate-950">Access configuration</h2>
            </div>
          </div>

          <div className="mt-5 grid gap-4 grid-cols-2">
            <div className="rounded-2xl border border-slate-200/80 bg-slate-50/70 px-4 py-4">
              <p className="text-xs font-bold uppercase tracking-[0.16em] text-slate-400">
                Workspace State
              </p>
              <div className="mt-3">
                <Badge tone={unlocked ? "active" : "failed"}>
                  {unlocked ? "Unlocked" : "Locked"}
                </Badge>
              </div>
            </div>

            <div className="rounded-2xl border border-slate-200/80 bg-slate-50/70 px-4 py-4">
              <p className="text-xs font-bold uppercase tracking-[0.16em] text-slate-400">
                Access Code
              </p>
              <p className="mt-3 text-sm font-semibold text-slate-700">
                {currentWorkspace?.workspace_code || "Non disponible"}
              </p>
            </div>

            <div className="rounded-2xl border border-slate-200/80 bg-slate-50/70 px-4 py-4">
              <p className="text-xs font-bold uppercase tracking-[0.16em] text-slate-400">
                Campaign Status
              </p>
              <div className="mt-3">
                <Badge tone={currentCampaign.status}>{currentCampaign.status}</Badge>
              </div>
            </div>

            <div className="rounded-2xl border border-slate-200/80 bg-slate-50/70 px-4 py-4">
              <p className="text-xs font-bold uppercase tracking-[0.16em] text-slate-400">
                Active Site
              </p>
              <p className="mt-3 text-sm font-semibold text-slate-700">
                {currentCampaign.site_name || currentCampaign.branch_name}
              </p>
            </div>
          </div>
        </Card>

        <Card className="p-6">
          <p className="text-[10px] font-black uppercase tracking-[0.24em] text-[#0085A3]">
            Exit workspace
          </p>
          <h2 className="mt-3 text-xl font-black text-slate-950">Close secure access</h2>
          <p className="mt-3 text-sm leading-7 text-slate-500">
            Exiting the workspace clears campaign access for this browser and returns you to the main
            campaigns directory.
          </p>
          <Button className="mt-6 w-full" variant="secondary" icon={LogOut} onClick={handleExit}>
            Exit Workspace
          </Button>
        </Card>
      </div>
    </div>
  );
};
