import { Card } from "@/components/common/Card";
import { DeviceRuntimePanel } from "@/pages/sync-connection/DeviceRuntimePanel";
import { useAuth } from "@/hooks/useAuth";
import { useMissionRuntime } from "@/hooks/useMissionRuntime";

export const MobileDeviceDashboardPage = () => {
  const { user } = useAuth();
  const { runtime } = useMissionRuntime();

  return (
    <div className="space-y-6">
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        {[
          ["Identité appareil", runtime.device?.device_code || runtime.device?.device_name || "-"],
          ["Mode runtime", runtime.runtimeMode],
          ["Source de données", runtime.activeApiSource],
          ["Serveur central", runtime.missionServerUrl || "-"],
          ["Dernière sync centrale", runtime.device?.server_time || "-"],
          ["État base locale", runtime.device?.database_health || "-"],
          ["Pending mission copy", runtime.activeMission?.code || "Aucune"],
          ["Pending central changes", runtime.connectionState],
        ].map(([label, value]) => (
          <Card key={label} className="rounded-[1.75rem] p-5">
            <p className="text-xs font-bold uppercase tracking-[0.16em] text-slate-500">{label}</p>
            <p className="mt-3 text-xl font-black text-slate-950">{value}</p>
          </Card>
        ))}
      </div>

      <DeviceRuntimePanel user={user} serverUrl={runtime.missionServerUrl || ""} onServerUrlChange={() => undefined} />
    </div>
  );
};
