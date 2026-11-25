import { useEffect, useState } from "react";
import { Link, Outlet } from "react-router-dom";
import { env } from "@/config/env";
import { Header } from "@/components/layout/Header";
import { Sidebar } from "@/components/layout/Sidebar";
import { Button } from "@/components/common/Button";
import { getProductIdentity } from "@/features/installation/profileInfrastructure";
import { useAuth } from "@/hooks/useAuth";
import { useInstallationProfile } from "@/hooks/useInstallationProfile";
import { useMissionRuntime } from "@/hooks/useMissionRuntime";
import { useRuntimeConnection } from "@/hooks/useRuntimeConnection";
import { isRenderableConnectionState } from "@/services/runtimeConnectionService";

export const DashboardLayout = () => {
  const { profileResolved, profileWarning, user, logout } = useAuth();
  const {
    profile,
    isCentralServer,
    mismatchError,
    refresh: refreshInstallationProfile,
  } = useInstallationProfile();
  const runtimeConnection = useRuntimeConnection();
  const { runtime, refresh: refreshMissionRuntime } = useMissionRuntime({ autoRefresh: false });
  const [isCollapsed, setIsCollapsed] = useState(false);
  const [onlineStatus, setOnlineStatus] = useState(navigator.onLine);

  useEffect(() => {
    const identity = getProductIdentity({
      profile,
      version: env.appVersion,
      buildId: env.buildId,
      installerIdentifier: env.installerIdentifier,
    });
    document.title = identity.productTitle;
  }, [profile]);

  useEffect(() => {
    const handleOnline = () => setOnlineStatus(true);
    const handleOffline = () => setOnlineStatus(false);

    window.addEventListener("online", handleOnline);
    window.addEventListener("offline", handleOffline);

    return () => {
      window.removeEventListener("online", handleOnline);
      window.removeEventListener("offline", handleOffline);
    };
  }, []);

  const showProfileBlocker = Boolean(mismatchError);
  const showRuntimeBanner =
    isRenderableConnectionState(runtimeConnection.state) &&
    (runtimeConnection.state === "connected_pending_validation" ||
      Boolean(runtimeConnection.warning) ||
      Boolean(runtimeConnection.message));
  const runtimeBannerTone =
    runtimeConnection.state === "connected_pending_validation" ? "border-sky-200 bg-sky-50 text-sky-900" : "border-amber-200 bg-amber-50 text-amber-900";

  return (
    <div className="min-h-screen min-w-[1280px] bg-shell-glow">
      <div className="flex min-h-screen">
        <Sidebar
          currentUser={user}
          onlineStatus={onlineStatus}
          isCollapsed={isCollapsed}
          isCentralServer={isCentralServer}
          onLogout={() => void logout()}
        />

        <div className="flex min-h-screen min-w-0 flex-1 flex-col">
          <Header
            currentUser={user}
            onlineStatus={onlineStatus}
            isCollapsed={isCollapsed}
            onCollapseToggle={() => setIsCollapsed((value) => !value)}
            onLogout={() => void logout()}
            runtimeStatus={runtime}
            onRetryMissionConnection={() => {
              void refreshMissionRuntime();
            }}
          />
          <main className="flex-1 px-6 py-6">
            <div className="mx-auto w-full max-w-[1760px]">
              {showRuntimeBanner ? (
                <div className={`mb-4 rounded-2xl border px-4 py-3 text-sm ${runtimeBannerTone}`}>
                  <p className="font-semibold">
                    {runtimeConnection.state === "connected_pending_validation"
                      ? "Connexion verifiee rapidement. Les diagnostics complets continuent en arriere-plan."
                      : runtimeConnection.warning || runtimeConnection.message || "Verification reseau en cours."}
                  </p>
                  {runtimeConnection.state !== "connected_pending_validation" && runtimeConnection.message ? (
                    <p className="mt-1 opacity-80">{runtimeConnection.message}</p>
                  ) : null}
                </div>
              ) : null}
              {!profileResolved && user ? (
                <div className="mb-4 rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-700">
                  Actualisation du profil utilisateur en cours.
                </div>
              ) : null}
              {profileWarning ? (
                <div className="mb-4 rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
                  {profileWarning}
                </div>
              ) : null}
              {showProfileBlocker ? (
                <div className="rounded-[2rem] border border-amber-200 bg-white p-8 shadow-sm">
                  <h1 className="text-2xl font-black text-slate-950">
                    {mismatchError
                      ? "Le profil du programme installe ne correspond pas a la configuration locale."
                      : "Impossible de determiner le type de cette installation."}
                  </h1>
                  <p className="mt-3 text-sm text-slate-600">
                    {mismatchError
                      ? "Les fonctionnalites protegees restent bloquees tant que le profil backend et le profil embarque ne correspondent pas."
                      : "Le backend local n'a pas encore fourni un profil exploitable. Verifiez l'etat de l'installation ou relancez le backend local."}
                  </p>
                  <div className="mt-6 flex gap-3">
                    <Button
                      type="button"
                      onClick={() => {
                        void refreshInstallationProfile();
                      }}
                    >
                      Reessayer
                    </Button>
                    <Link
                      to="/app/infrastructure/diagnostics"
                      className="inline-flex items-center justify-center rounded-xl border border-slate-200 px-4 py-2 font-semibold text-slate-700 transition hover:bg-slate-50"
                    >
                      Afficher le diagnostic
                    </Link>
                  </div>
                </div>
              ) : (
                <Outlet />
              )}
            </div>
          </main>
        </div>
      </div>
    </div>
  );
};
