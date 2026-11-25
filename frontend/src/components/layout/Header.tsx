import { useEffect, useMemo, useRef, useState } from "react";
import {
  AlertTriangle,
  Database,
  LogOut,
  Monitor,
  PanelLeftClose,
  PanelLeftOpen,
  RefreshCw,
  Server,
  Settings,
  type LucideIcon,
  UserCircle2,
} from "lucide-react";
import { Link, useLocation, useNavigate } from "react-router-dom";

import { useSync } from "@/hooks/useSync";
import type { AuthUser } from "@/types/auth";
import type { RuntimeMode, RuntimeStatus } from "@/types/mission";
import { cn } from "@/utils/cn";
import { translateUiText } from "@/utils/uiText";

const getSettingsShortcutPath = (currentUser: AuthUser | null) =>
  currentUser?.role === "Super Admin" ? "/settings" : "/profile";

const connectionModes: Record<RuntimeMode, { label: string; Icon: LucideIcon }> = {
  standalone: { label: "Serveur local", Icon: Database },
  mission_server: { label: "Serveur central", Icon: Server },
  mission_client: { label: "Client", Icon: Monitor },
};

const pageTitles: Array<{ pattern: RegExp; title: string }> = [
  { pattern: /^\/dashboard\/[^/]+$/, title: "Tableau de bord personnel" },
  { pattern: /^\/dashboard$/, title: "Tableau de bord" },
  { pattern: /^\/users$/, title: "Utilisateurs" },
  { pattern: /^\/companies$/, title: "Enterprise" },
  { pattern: /^\/branches$/, title: "Enterprise" },
  { pattern: /^\/drilling-sites$/, title: "Enterprise" },
  { pattern: /^\/workers\/[^/]+$/, title: "Profil du travailleur" },
  { pattern: /^\/workers$/, title: "Travailleurs" },
  { pattern: /^\/campaigns\/[^/]+$/, title: "Détails de la campagne" },
  { pattern: /^\/campaigns$/, title: "Campagnes médicales" },
  { pattern: /^\/medical-tests$/, title: "Examens médicaux" },
  { pattern: /^\/imports$/, title: "Importations" },
  { pattern: /^\/reports$/, title: "Rapports" },
  { pattern: /^\/app\/audit-logs$/, title: "Journal d'audit" },
  { pattern: /^\/settings$/, title: "Paramètres" },
  { pattern: /^\/profile$/, title: "Profil" },
];

const prettifySegment = (segment: string) =>
  segment
    .split("-")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");

interface HeaderProps {
  currentUser: AuthUser | null;
  onlineStatus: boolean;
  isCollapsed: boolean;
  onCollapseToggle: () => void;
  onLogout: () => void;
  runtimeStatus?: RuntimeStatus | null;
  onRetryMissionConnection?: () => void;
}

export const Header = ({
  currentUser,
  onlineStatus,
  isCollapsed,
  onCollapseToggle,
  onLogout,
  runtimeStatus,
  onRetryMissionConnection,
}: HeaderProps) => {
  const location = useLocation();
  const navigate = useNavigate();
  const { syncNow, syncing } = useSync();
  const profileMenuRef = useRef<HTMLDivElement | null>(null);
  const [profileOpen, setProfileOpen] = useState(false);

  useEffect(() => {
    const handlePointerDown = (event: MouseEvent) => {
      const target = event.target as Node;
      if (profileMenuRef.current && !profileMenuRef.current.contains(target)) {
        setProfileOpen(false);
      }
    };

    document.addEventListener("mousedown", handlePointerDown);
    return () => document.removeEventListener("mousedown", handlePointerDown);
  }, []);

  const pageTitle = useMemo(() => {
    if (/^\/dashboard\/[^/]+$/.test(location.pathname)) {
      return currentUser ? `${translateUiText(currentUser.role)} - Tableau de bord` : "Tableau de bord personnel";
    }

    const match = pageTitles.find((item) => item.pattern.test(location.pathname));
    if (match) return match.title;

    return prettifySegment(location.pathname.split("/").filter(Boolean).pop() || "Tableau de bord");
  }, [currentUser, location.pathname]);

  const breadcrumb = useMemo(
    () => location.pathname.split("/").filter(Boolean).map(prettifySegment),
    [location.pathname],
  );

  const handleLogout = () => {
    onLogout();
    navigate("/login");
  };

  const settingsShortcutPath = getSettingsShortcutPath(currentUser);
  const connectionMode = runtimeStatus ? connectionModes[runtimeStatus.runtimeMode] : null;
  const missionDisconnected =
    runtimeStatus?.runtimeMode === "mission_client" && runtimeStatus.connectionState === "disconnected";
  const initials =
    [currentUser?.first_name, currentUser?.last_name]
      .filter(Boolean)
      .map((part) => part![0])
      .join("")
      .toUpperCase() || "MF";

  return (
    <header className="sticky top-0 z-30">
      <div className="flex h-[4.5rem] items-center justify-between gap-4 border-b border-slate-200 bg-white/90 px-6 backdrop-blur-xl">
        <div className="flex min-w-0 items-center gap-3">
          <button
            type="button"
            onClick={onCollapseToggle}
            className="shrink-0 rounded-lg p-2 text-slate-400 transition hover:bg-slate-100 hover:text-slate-700"
            aria-label={isCollapsed ? "Developper la barre laterale" : "Reduire la barre laterale"}
          >
            {isCollapsed ? <PanelLeftOpen className="h-4 w-4" /> : <PanelLeftClose className="h-4 w-4" />}
          </button>

          <div className="min-w-0">
            <div className="flex items-center gap-1.5 text-[11px] text-gray-400">
              {breadcrumb.length > 0 ? (
                breadcrumb.map((item, index) => (
                  <span key={`${item}-${index}`} className="flex items-center gap-1.5">
                    {index > 0 && <span className="text-gray-300">/</span>}
                    <span className={index === breadcrumb.length - 1 ? "text-teal-700" : ""}>{item}</span>
                  </span>
                ))
              ) : (
                <span className="text-teal-700">Tableau de bord</span>
              )}
            </div>
            <p className="truncate text-base font-extrabold tracking-tight text-slate-900">{pageTitle}</p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {connectionMode ? (
            <>
              <div className="flex items-center gap-2 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2">
                <connectionMode.Icon className="h-4 w-4 text-[#0085A3]" />
                <span className="text-xs font-semibold text-slate-700">{connectionMode.label}</span>
              </div>
              <div className="h-7 border-l border-slate-200" aria-hidden="true" />
            </>
          ) : null}

          <button
            type="button"
            onClick={() => void syncNow().catch(() => undefined)}
            title="Synchronisation suspendue pour protection; le retour du reseau ne la reactive pas."
            disabled={true}
            className="flex items-center gap-1.5 rounded-md border-l-2 border-transparent px-2.5 py-1.5 text-[13px] font-medium text-gray-500 transition-colors hover:bg-gray-50 hover:text-gray-900 disabled:cursor-not-allowed disabled:opacity-60"
          >
            <RefreshCw className={cn("h-4 w-4 shrink-0", syncing && "animate-spin")} />
            <span>{syncing ? "Synchronisation..." : "Synchroniser"}</span>
          </button>

          <div className="flex items-center gap-1.5 px-1 text-[11px] font-medium text-gray-400">
            <span className={cn("h-2 w-2 shrink-0 rounded-full", onlineStatus ? "bg-emerald-500" : "bg-gray-300")} />
            <span>{onlineStatus ? "En ligne" : "Hors ligne"}</span>
          </div>

          <div className="h-7 border-l border-slate-200" aria-hidden="true" />

          <div className="relative" ref={profileMenuRef}>
            <button
              type="button"
              onClick={() => setProfileOpen((value) => !value)}
              className="relative flex h-8 w-8 items-center justify-center rounded-full bg-gray-100 text-xs font-semibold text-gray-700 transition hover:bg-gray-200"
              aria-label="Menu utilisateur"
            >
              {initials}
              <span
                className={cn(
                  "absolute -bottom-0.5 -right-0.5 h-2.5 w-2.5 rounded-full border-2 border-white",
                  onlineStatus ? "bg-emerald-500" : "bg-gray-300",
                )}
              />
            </button>

            <div
              className={cn(
                "absolute right-0 top-[calc(100%+0.5rem)] z-50 w-60 origin-top-right rounded-md border border-gray-200 bg-white p-1 shadow-sm transition-all duration-150",
                profileOpen ? "visible translate-y-0 opacity-100" : "invisible -translate-y-1 opacity-0",
              )}
            >
              <div className="flex items-center gap-2.5 border-b border-gray-100 px-2.5 py-2.5">
                <div className="relative flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-gray-100 text-xs font-semibold text-gray-700">
                  {initials}
                  <span
                    className={cn(
                      "absolute -bottom-0.5 -right-0.5 h-2.5 w-2.5 rounded-full border-2 border-white",
                      onlineStatus ? "bg-emerald-500" : "bg-gray-300",
                    )}
                  />
                </div>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-[13px] font-medium text-gray-900">
                    {currentUser?.first_name && currentUser?.last_name
                      ? `${currentUser.first_name} ${currentUser.last_name}`
                      : currentUser?.first_name || "Utilisateur medical"}
                  </p>
                  <p className="truncate text-[11px] text-gray-400">{currentUser?.email || "Aucun e-mail"}</p>
                </div>
              </div>

              <div className="mt-1 space-y-0.5">
                <Link
                  to="/profile"
                  className="flex items-center gap-2.5 rounded-md border-l-2 border-transparent px-2.5 py-2 text-[13px] font-medium text-gray-500 transition-colors hover:bg-gray-50 hover:text-gray-900"
                >
                  <UserCircle2 className="h-4 w-4 shrink-0" />
                  <span>Profil</span>
                </Link>
                <Link
                  to={settingsShortcutPath}
                  className="flex items-center gap-2.5 rounded-md border-l-2 border-transparent px-2.5 py-2 text-[13px] font-medium text-gray-500 transition-colors hover:bg-gray-50 hover:text-gray-900"
                >
                  <Settings className="h-4 w-4 shrink-0" />
                  <span>Paramètres</span>
                </Link>
                <button
                  type="button"
                  onClick={handleLogout}
                  className="flex w-full items-center gap-2.5 rounded-md border-l-2 border-transparent px-2.5 py-2 text-left text-[13px] font-medium text-gray-500 transition-colors hover:bg-rose-50 hover:text-rose-600"
                >
                  <LogOut className="h-4 w-4 shrink-0" />
                  <span>Déconnexion</span>
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>

      {missionDisconnected ? (
        <div className="flex flex-col gap-2.5 border-b border-rose-200 bg-rose-50 px-5 py-2.5 text-[13px] text-rose-700 lg:flex-row lg:items-center lg:justify-between">
          <div className="flex items-start gap-2">
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-rose-500" />
            <div>
              <p className="font-medium text-rose-800">Connexion au serveur de mission perdue.</p>
              <p className="text-rose-600">
                Les modifications sont temporairement desactivees afin d'eviter des divergences de donnees.
              </p>
            </div>
          </div>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={onRetryMissionConnection}
              className="rounded-md border border-rose-200 bg-white px-3 py-1.5 font-medium text-rose-700 transition hover:bg-rose-100"
            >
              Reessayer
            </button>
            <Link
              to="/sync/mission"
              className="rounded-md bg-rose-600 px-3 py-1.5 font-medium text-white transition hover:bg-rose-700"
            >
              Ouvrir la mission
            </Link>
          </div>
        </div>
      ) : null}
    </header>
  );
};
