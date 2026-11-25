import { Navigate } from "react-router-dom";

import { Card } from "@/components/common/Card";
import { MOBILE_HOME_ROUTE } from "@/features/mobile/mobileDeviceFlow";
import { useSystemBackups } from "@/hooks/useCentralInstallation";
import { useInstallationProfile } from "@/hooks/useInstallationProfile";

export const CentralBackupsPage = () => {
  const { isCentralServer } = useInstallationProfile();
  const { data: backups } = useSystemBackups(isCentralServer);

  if (!isCentralServer) {
    return <Navigate to={MOBILE_HOME_ROUTE} replace />;
  }

  return (
    <Card className="rounded-[2rem] p-6">
      <h1 className="text-2xl font-black text-slate-950">Sauvegardes</h1>
      <p className="mt-2 text-sm text-slate-600">Chemin, date, taille et statut des sauvegardes disponibles.</p>
      <div className="mt-5 space-y-3">
        {backups.map((backup) => (
          <div key={`${backup.filename}-${backup.created_at}`} className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3">
            <p className="font-semibold text-slate-900">{backup.filename}</p>
            <p className="mt-1 text-xs text-slate-500">{backup.path || "-"}</p>
            <p className="mt-1 text-xs text-slate-500">
              {backup.created_at || "-"} · {backup.size_bytes ?? 0} octets · {backup.status || "-"}
            </p>
          </div>
        ))}
      </div>
    </Card>
  );
};
