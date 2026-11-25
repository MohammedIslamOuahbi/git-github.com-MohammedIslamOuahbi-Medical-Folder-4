import {
  FileUp,
  FlaskConical,
  LayoutDashboard,
  LogOut,
  RefreshCcw,
  Settings,
  Users,
} from "lucide-react";
import { NavLink } from "react-router-dom";
import { Button } from "@/components/common/Button";
import { useAuth } from "@/hooks/useAuth";
import type { Role } from "@/types/common";
import type { Workspace } from "@/types/workspace";
import { cn } from "@/utils/cn";
import { hasAnyPermission, hasRole } from "@/utils/permissions";

interface CampaignWorkspaceSidebarProps {
  campaignId: string;
  workspace: Workspace | null;
  online: boolean;
  onExit: () => void;
}

const buildItems = (campaignId: string) => [
  {
    label: "Tableau de bord",
    path: `/app/workspace/${campaignId}/dashboard`,
    icon: LayoutDashboard,
  },
  {
    label: "Examens médicaux",
    path: `/app/workspace/${campaignId}/tests`,
    icon: FlaskConical,
  },
  {
    label: "Travailleurs",
    path: `/app/workspace/${campaignId}/workers`,
    icon: Users,
  },
  {
    label: "Import nominatif",
    path: `/app/workspace/${campaignId}/import`,
    icon: FileUp,
    permissions: ["imports:manage"],
    roles: ["Doctor", "Assistant"] as Role[],
  },
  {
    label: "Synchronisation",
    path: `/app/workspace/${campaignId}/sync`,
    icon: RefreshCcw,
  },
  {
    label: "Paramètres",
    path: `/app/workspace/${campaignId}/settings`,
    icon: Settings,
    permissions: ["workspaces:manage", "campaigns:manage"],
  },
];

export function CampaignWorkspaceSidebar({
  campaignId,
  workspace,
  online,
  onExit,
}: CampaignWorkspaceSidebarProps) {
  const { user } = useAuth();

  const items = buildItems(campaignId).filter((item) =>
    item.permissions || item.roles
      ? Boolean(
          (item.permissions && hasAnyPermission(user, item.permissions)) ||
            (item.roles && hasRole(user, item.roles)),
        )
      : true,
  );

  return (
    <aside className="sticky top-0 flex h-screen w-64 shrink-0 flex-col border-r border-slate-200 bg-white">
      {/* Header */}
     <div className="border-b border-slate-200 bg-slate-50 px-4 py-4">
      <div className="rounded-lg border border-slate-200 bg-white p-4">
        <div className="flex items-center justify-between gap-3">
              <p className="text-[10px] font-extrabold uppercase tracking-[0.14em] text-blue-700">
                Espace de travail
              </p>

              <span
                className={cn(
                  "h-2.5 w-2.5 rounded-full",
                  online ? "bg-emerald-500" : "bg-red-500",
                )}
              />
            </div>

            <p className="mt-2 truncate text-sm font-bold text-slate-900">
              {workspace?.company_name || "Entreprise"}
            </p>

            <p className="mt-1 truncate text-xs font-medium text-slate-500">
              {workspace?.drilling_site_name || "Site médical"}
            </p>
          </div>
        </div>

          {/* Navigation */}
          <nav className="flex-1 space-y-1 overflow-y-auto px-3 py-4">
            {items.map(({ icon: Icon, label, path }) => (
              <NavLink
                key={path}
                to={path}
                className={({ isActive }) =>
                  cn(
                    "flex items-center gap-3 rounded-lg border border-transparent px-3 py-2.5 text-sm font-semibold text-slate-500 transition hover:bg-slate-100 hover:text-slate-900",
                    isActive && "border-blue-200 bg-blue-50 text-blue-800",
                  )
                }
              >
                <Icon className="h-4 w-4 shrink-0" />
                <span className="truncate">{label}</span>
              </NavLink>
            ))}
          </nav>

          {/* Exit */}
          <div className="border-t border-slate-200 bg-slate-50 p-3">
            <Button
              variant="ghost"
              size="md"
              className="w-full justify-start gap-2 bg-white text-slate-600 hover:bg-rose-50 hover:text-rose-700"
              onClick={onExit}
            >
              <LogOut className="h-4 w-4" />
              Quitter
            </Button>
          </div>
        </aside>
  );
}
