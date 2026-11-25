import { Navigate } from "react-router-dom";

import { Card } from "@/components/common/Card";
import { MOBILE_HOME_ROUTE } from "@/features/mobile/mobileDeviceFlow";
import { useRegisteredDevices } from "@/hooks/useCentralInstallation";
import { useInstallationProfile } from "@/hooks/useInstallationProfile";

export const CentralRegisteredDevicesPage = () => {
  const { isCentralServer } = useInstallationProfile();
  const { data: devices } = useRegisteredDevices(isCentralServer);

  if (!isCentralServer) {
    return <Navigate to={MOBILE_HOME_ROUTE} replace />;
  }

  return (
    <Card className="rounded-[2rem] p-6">
      <h1 className="text-2xl font-black text-slate-950">Appareils</h1>
      <p className="mt-2 text-sm text-slate-600">Afficher, renommer, révoquer, réactiver et préparer un bootstrap.</p>
      <div className="mt-5 overflow-x-auto">
        <table className="min-w-full text-sm">
          <thead className="text-left text-xs uppercase tracking-[0.14em] text-slate-500">
            <tr>
              <th className="pb-3">Nom</th>
              <th className="pb-3">Code</th>
              <th className="pb-3">UUID</th>
              <th className="pb-3">Dernière connexion</th>
              <th className="pb-3">Dernière synchronisation</th>
              <th className="pb-3">Version</th>
              <th className="pb-3">Schéma</th>
              <th className="pb-3">État</th>
            </tr>
          </thead>
          <tbody>
            {devices.map((device) => (
              <tr key={device.uuid} className="border-t border-slate-100">
                <td className="py-3 font-semibold text-slate-900">{device.name}</td>
                <td className="py-3">{device.code}</td>
                <td className="py-3 font-mono text-xs">{device.uuid}</td>
                <td className="py-3">{device.last_connection_at || "-"}</td>
                <td className="py-3">{device.last_sync_at || "-"}</td>
                <td className="py-3">{device.version || "-"}</td>
                <td className="py-3">{device.schema_revision || "-"}</td>
                <td className="py-3">{device.status}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
};
