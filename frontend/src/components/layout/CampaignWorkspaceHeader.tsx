import { Wifi, WifiOff, LogOut, ShieldCheck, UserRound } from "lucide-react";
import { Button } from "@/components/common/Button";
import type { AuthUser } from "@/types/auth";
import type { Workspace, WorkspaceCampaign } from "@/types/workspace";
import { cn } from "@/utils/cn";

interface CampaignWorkspaceHeaderProps {
  campaign: WorkspaceCampaign;
  workspace: Workspace | null;
  currentUser: AuthUser | null;
  online: boolean;
  onExit: () => void;
}

export function CampaignWorkspaceHeader({
  campaign,
  workspace,
  currentUser,
  online,
  onExit,
}: CampaignWorkspaceHeaderProps) {
  return (
    <header className="sticky top-0 z-30 h-16 border-b border-slate-200 bg-cyan-200/30">
      <div className="flex h-full items-center justify-between px-6">
        {/* Campaign */}
        <div className="min-w-0">
          <h1 className="truncate text-lg font-bold text-slate-900">
            {workspace?.campaign_name || campaign.title || campaign.name}
          </h1>

          <p className="truncate text-sm font-bold text-slate-500">
            {workspace?.company_name || campaign.company_name}
            {" • "}
            {workspace?.drilling_site_name ||
              campaign.site_name ||
              campaign.branch_name}
          </p>
        </div>

        {/* Right Side */}
        <div className="flex items-center gap-4">
          {/* Connection */}
          <div
            className={cn(
              "inline-flex items-center gap-2 rounded-full border px-3 py-2.5 text-xs font-semibold",
              online
                ? "border-emerald-200 bg-emerald-50 text-emerald-700"
                : "border-red-200 bg-red-50 text-red-700"
            )}
          >
            {online ? (
              <Wifi className="h-3.5 w-3.5" />
            ) : (
              <WifiOff className="h-3.5 w-3.5" />
            )}

            {online ? "En ligne" : "Hors ligne"}
          </div>

          {/* User */}
         <div className="flex items-center gap-3 border-l border-slate-200 pl-4">
          <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-gradient-to-br from-cyan-600 to-cyan-700 text-white shadow-md">
            <span className="text-sm font-bold">
              {(currentUser?.first_name?.[0] ?? "") +
                (currentUser?.last_name?.[0] ?? "") || "U"}
            </span>
          </div>

          <div className="hidden md:block">
            <div className="flex items-center gap-2">
              <UserRound className="h-3.5 w-3.5 text-slate-400" />

              <p className="text-sm font-semibold text-slate-900">
                {currentUser
                  ? `${currentUser.first_name ?? ""} ${currentUser.last_name ?? ""}`.trim()
                  : "Utilisateur"}
              </p>
            </div>

            <div className="mt-0.5 flex items-center gap-1.5">
              <ShieldCheck className="h-3.5 w-3.5 text-cyan-600" />

              <p className="text-xs font-medium text-slate-500">
                {currentUser?.role || "Médecin"}
              </p>
            </div>
          </div>
        </div>
          {/* Exit */}
          <Button
            variant="ghost"
            size="sm"
            onClick={onExit}
            className="gap-2 text-slate-600 bg-red-100 hover:bg-red-100 hover:text-red-700"
          >
            <LogOut className="h-4 w-4" />
            Quitter
          </Button>
        </div>
      </div>
    </header>
  );
}