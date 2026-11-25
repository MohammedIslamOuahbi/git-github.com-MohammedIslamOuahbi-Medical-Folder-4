import { useEffect, useMemo } from "react";
import { LogOut } from "lucide-react";
import { Link, NavLink } from "react-router-dom";

import { env } from "@/config/env";
import { readStoredConnectionMode } from "@/config/runtime";
import {
  buildNavigationDiagnostics,
  filterNavigationItems,
  flattenNavigationItems,
  resolveNavigationRoute,
  SIDEBAR_NAVIGATION,
} from "@/features/installation/sidebarNavigation";
import { getProductIdentity } from "@/features/installation/profileInfrastructure";
import { useInstallationProfile } from "@/hooks/useInstallationProfile";
import { cn } from "@/utils/cn";
import type { Role } from "@/types/common";
import type { AuthUser } from "@/types/auth";
import { translateUiText } from "@/utils/uiText";

const roleDotStyles: Record<Role, string> = {
  "Super Admin": "bg-emerald-500",
  Admin: "bg-cyan-500",
  Doctor: "bg-blue-500",
  Assistant: "bg-amber-500",
};

interface SidebarProps {
  currentUser: AuthUser | null;
  onlineStatus: boolean;
  isCollapsed: boolean;
  isCentralServer?: boolean;
  onLogout: () => void;
}

export const Sidebar = ({
  currentUser,
  onlineStatus,
  isCollapsed,
  onLogout,
}: SidebarProps) => {
  const {
    profile,
    backendProfile,
    packagedProfile,
    capabilities,
    deviceIdentity,
    status: profileStatus,
    mismatchError,
    refresh,
  } = useInstallationProfile();
  const identity = getProductIdentity({
    profile,
    version: env.appVersion,
    buildId: env.buildId,
    installerIdentifier: env.installerIdentifier,
  });

  const navigationContext = useMemo(
    () => ({
      profile,
      packagedProfile,
      backendProfile,
      capabilities,
      profileStatus,
      mismatchError,
      currentUser,
      connectionMode: readStoredConnectionMode(),
    }),
    [backendProfile, capabilities, currentUser, mismatchError, packagedProfile, profile, profileStatus],
  );

  const visibleItems = useMemo(
    () => flattenNavigationItems(filterNavigationItems(SIDEBAR_NAVIGATION, navigationContext)),
    [navigationContext],
  );

  useEffect(() => {
    if (!import.meta.env.DEV) {
      return;
    }
    // Safe local diagnostic for sidebar policy decisions.
    console.debug("sidebar.navigation", buildNavigationDiagnostics(SIDEBAR_NAVIGATION, navigationContext));
  }, [navigationContext]);

  const fullName =
    currentUser?.first_name && currentUser?.last_name
      ? `${currentUser.first_name} ${currentUser.last_name}`
      : currentUser?.first_name || "Utilisateur medical";

  const initials =
    currentUser?.first_name || currentUser?.last_name
      ? `${currentUser?.first_name?.[0] ?? ""}${currentUser?.last_name?.[0] ?? ""}`.toUpperCase()
      : "MF";

  const roleDotClass = currentUser?.role ? roleDotStyles[currentUser.role] : roleDotStyles.Assistant;
  const isProfileLoading = profileStatus === "idle" || profileStatus === "loading";
  const mismatchMessage =
    mismatchError === "INSTALLATION_PROFILE_MISMATCH"
      ? "Le profil du programme installe ne correspond pas a la configuration locale."
      : null;

  return (
    <aside className={cn("sticky top-0 h-screen shrink-0", isCollapsed ? "w-20" : "w-64")}>
      <div className="flex h-full flex-col overflow-hidden border-r border-slate-200 bg-white">
        <div className="flex h-16 shrink-0 items-center border-b border-slate-200 bg-slate-50 px-4">
        <div
          className={cn(
            "flex min-w-0 items-center gap-2.5",
            isCollapsed && "w-full justify-center",
          )}
        >
          <img
            src="/medical-folder-icon-transparent.png"
            alt="Logo Ibn Sina"
            className="h-10 w-10 shrink-0 object-contain"
          />

          {!isCollapsed && (
            <div className="min-w-0">
              <p className="truncate text-sm font-extrabold tracking-tight text-slate-900">
                {identity.productTitle}
              </p>
              <p className="truncate font-mono text-[10px] text-slate-500">
                {deviceIdentity.code || identity.buildId}
              </p>
            </div>
          )}
        </div>
      </div>

        <nav className="min-h-0 flex-1 overflow-y-auto px-3 py-5">
          {mismatchMessage ? (
            <div className="space-y-2.5 rounded-lg border border-rose-200 bg-rose-50 p-3 text-xs text-rose-700">
              <p className="font-medium">{mismatchMessage}</p>
              <div className="flex flex-col gap-1.5">
                <button
                  type="button"
                  onClick={() => {
                    void refresh();
                  }}
                  className="rounded-md border border-rose-200 bg-white px-2.5 py-1.5 text-left font-medium transition hover:bg-rose-100"
                >
                  Reessayer
                </button>
                <Link
                  to="/app/infrastructure/diagnostics"
                  className="rounded-md border border-rose-200 bg-white px-2.5 py-1.5 font-medium transition hover:bg-rose-100"
                >
                  Afficher le diagnostic
                </Link>
              </div>
            </div>
          ) : isProfileLoading && visibleItems.length === 0 ? (
            <div className="space-y-2">
              {Array.from({ length: 5 }).map((_, index) => (
                <div
                  key={`sidebar-skeleton-${index}`}
                  className="h-9 animate-pulse rounded-lg bg-slate-100"
                />
              ))}
            </div>
          ) : (
            <div className="space-y-1">
              {visibleItems.map((item) => (
                <NavLink
                  key={item.id}
                  to={resolveNavigationRoute(item, currentUser)}
                  title={isCollapsed ? item.label : undefined}
                  className={({ isActive }) =>
                    cn(
                      "group flex items-center gap-3 rounded-lg border px-3 py-2.5 text-[13px] font-semibold transition-all duration-150",
                      isCollapsed && "justify-center border-l-0 px-0",
                      isActive
                        ? "border-blue-200 bg-blue-50 text-blue-800 shadow-sm"
                        : "border-transparent text-slate-500 hover:bg-slate-100 hover:text-slate-900",
                    )
                  }
                >
                  <item.icon className="h-4 w-4 shrink-0" />
                  {!isCollapsed && <span className="truncate">{item.label}</span>}
                </NavLink>
              ))}
            </div>
          )}
        </nav>

        <div className="shrink-0 border-t border-slate-200 bg-slate-50 p-3">
  <div
    className={cn(
      "rounded-xl border border-slate-200 bg-white p-2.5",
      isCollapsed && "flex flex-col items-center gap-2 bg-transparent border-none p-0",
    )}
  >
    <div className={cn("flex items-center gap-2.5", isCollapsed && "justify-center")}>
      <div className="relative flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-blue-100 text-xs font-bold text-blue-800 ring-1 ring-blue-200">
        {initials}
        <span
          className={cn(
            "absolute -bottom-0.5 -right-0.5 h-2.5 w-2.5 rounded-full border-2 border-white",
            onlineStatus ? "bg-emerald-500" : "bg-slate-300",
          )}
        />
      </div>

      {!isCollapsed && (
        <div className="min-w-0 flex-1">
          <p className="truncate text-[13px] font-semibold text-slate-900">{fullName}</p>
          <span className="mt-0.5 inline-flex items-center gap-1 rounded-full bg-slate-100 px-1.5 py-0.5 text-[10px] font-medium text-slate-500 ring-1 ring-slate-200">
            <span className={cn("h-1.5 w-1.5 shrink-0 rounded-full", roleDotClass)} />
            {translateUiText(currentUser?.role || "Assistant")}
          </span>
        </div>
      )}

      {!isCollapsed && (
        <button
          type="button"
          onClick={onLogout}
          title="Deconnexion"
          className="shrink-0 rounded-lg p-1.5 text-slate-400 transition hover:bg-rose-50 hover:text-rose-600"
        >
          <LogOut className="h-4 w-4" />
        </button>
      )}
    </div>

    {isCollapsed && (
      <button
        type="button"
        onClick={onLogout}
        title="Deconnexion"
        className="flex w-9 items-center justify-center rounded-lg p-1.5 text-slate-400 transition hover:bg-rose-50 hover:text-rose-600"
      >
        <LogOut className="h-4 w-4" />
      </button>
    )}
  </div>
</div>
      </div>
    </aside>
  );
};
