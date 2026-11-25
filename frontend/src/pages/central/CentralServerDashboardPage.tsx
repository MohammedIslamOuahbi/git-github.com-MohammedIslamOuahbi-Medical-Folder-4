import { Activity, Archive, HardDriveDownload, Network, ShieldCheck, Smartphone } from "lucide-react";
import { Navigate } from "react-router-dom";

import { Card } from "@/components/common/Card";
import { buildCentralDashboardSnapshot } from "@/features/central/centralServerFlow";
import { MOBILE_HOME_ROUTE } from "@/features/mobile/mobileDeviceFlow";
import {
  useCentralServerInfo,
  useInstallationStatus,
  useMissionSubmissions,
  useRegisteredDevices,
  useSystemBackups,
} from "@/hooks/useCentralInstallation";
import { useInstallationProfile } from "@/hooks/useInstallationProfile";

const SectionTitle = ({ title, subtitle }: { title: string; subtitle: string }) => (
  <div className="space-y-1">
    <h2 className="text-xl font-black text-slate-950">{title}</h2>
    <p className="text-sm text-slate-600">{subtitle}</p>
  </div>
);

export const CentralServerDashboardPage = () => {
  const { isCentralServer } = useInstallationProfile();
  const { status } = useInstallationStatus();
  const { data: serverInfo } = useCentralServerInfo(isCentralServer);
  const { data: devices } = useRegisteredDevices(isCentralServer);
  const { data: submissions } = useMissionSubmissions(isCentralServer);
  const { data: backups } = useSystemBackups(isCentralServer);
  const snapshot = buildCentralDashboardSnapshot({ status, serverInfo, devices, submissions, backups });

  if (!isCentralServer) {
    return <Navigate to={MOBILE_HOME_ROUTE} replace />;
  }

  return (
    <div className="space-y-6">
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        {[
          { label: "Identité centrale", value: snapshot.identityLabel, icon: ShieldCheck },
          { label: "Séquence centrale", value: snapshot.centralSequence, icon: Activity },
          { label: "Appareils mobiles", value: String(snapshot.registeredDevices), icon: Smartphone },
          { label: "Soumissions en attente", value: String(snapshot.pendingSubmissions), icon: Network },
          { label: "Conflits centraux", value: String(snapshot.conflicts), icon: ShieldCheck },
          { label: "Sauvegardes", value: String(snapshot.latestBackups), icon: Archive },
          { label: "Révision schéma", value: snapshot.schemaRevision, icon: HardDriveDownload },
          { label: "Protocole sync", value: snapshot.syncProtocolVersion, icon: Activity },
        ].map((item) => (
          <Card key={item.label} className="rounded-[1.75rem] p-5">
            <div className="flex items-center justify-between gap-3">
              <div>
                <p className="text-xs font-bold uppercase tracking-[0.16em] text-slate-500">{item.label}</p>
                <p className="mt-3 text-2xl font-black text-slate-950">{item.value}</p>
              </div>
              <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-[#0085A3]/10 text-[#0085A3]">
                <item.icon className="h-5 w-5" />
              </div>
            </div>
          </Card>
        ))}
      </div>

      <div className="grid gap-6 xl:grid-cols-2">
        <Card className="rounded-[2rem] p-6">
          <SectionTitle
            title="Appareils enregistrés"
            subtitle="Nom, code, UUID, dernière connexion, dernière synchronisation, version, schéma et état."
          />
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
          <p className="mt-4 text-xs text-slate-500">Actions disponibles: Afficher, Renommer, Révoquer, Réactiver, Préparer un bootstrap.</p>
        </Card>

        <Card className="rounded-[2rem] p-6">
          <SectionTitle
            title="Soumissions de mission"
            subtitle="Code mission, poste source, séquence finale, changements soumis, acceptés, conflits et statut."
          />
          <div className="mt-5 overflow-x-auto">
            <table className="min-w-full text-sm">
              <thead className="text-left text-xs uppercase tracking-[0.14em] text-slate-500">
                <tr>
                  <th className="pb-3">Mission</th>
                  <th className="pb-3">Poste mission</th>
                  <th className="pb-3">Séquence finale</th>
                  <th className="pb-3">Changements</th>
                  <th className="pb-3">Acceptés</th>
                  <th className="pb-3">Conflits</th>
                  <th className="pb-3">Statut</th>
                </tr>
              </thead>
              <tbody>
                {submissions.map((submission) => (
                  <tr key={submission.uuid} className="border-t border-slate-100">
                    <td className="py-3 font-semibold text-slate-900">{submission.mission_code}</td>
                    <td className="py-3">{submission.mission_server_device || "-"}</td>
                    <td className="py-3">{submission.final_mission_sequence ?? "-"}</td>
                    <td className="py-3">{submission.submitted_changes}</td>
                    <td className="py-3">{submission.accepted}</td>
                    <td className="py-3">{submission.conflicts}</td>
                    <td className="py-3">{submission.status}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      </div>

      <div className="grid gap-6 xl:grid-cols-3">
        <Card className="rounded-[2rem] p-6">
          <SectionTitle title="Santé" subtitle="État opérationnel de l’instance centrale." />
          <dl className="mt-5 space-y-3 text-sm">
            <div className="flex justify-between gap-3">
              <dt className="text-slate-500">Health</dt>
              <dd className="font-semibold text-slate-900">{snapshot.health}</dd>
            </div>
            <div className="flex justify-between gap-3">
              <dt className="text-slate-500">Schéma</dt>
              <dd className="font-semibold text-slate-900">{snapshot.schemaRevision}</dd>
            </div>
            <div className="flex justify-between gap-3">
              <dt className="text-slate-500">Protocole</dt>
              <dd className="font-semibold text-slate-900">{snapshot.syncProtocolVersion}</dd>
            </div>
          </dl>
        </Card>

        <Card className="rounded-[2rem] p-6">
          <SectionTitle title="Identité centrale" subtitle="UUID et informations de génération du serveur." />
          <dl className="mt-5 space-y-3 text-sm">
            <div>
              <dt className="text-slate-500">Server UUID</dt>
              <dd className="mt-1 break-all font-mono text-xs text-slate-900">{serverInfo?.server_uuid || status?.server_uuid || "-"}</dd>
            </div>
            <div>
              <dt className="text-slate-500">Generation UUID</dt>
              <dd className="mt-1 break-all font-mono text-xs text-slate-900">{serverInfo?.server_generation_uuid || status?.generation_uuid || "-"}</dd>
            </div>
          </dl>
        </Card>

        <Card className="rounded-[2rem] p-6">
          <SectionTitle title="Dernières sauvegardes" subtitle="Historique des sauvegardes système." />
          <div className="mt-5 space-y-3">
            {backups.slice(0, 5).map((backup) => (
              <div key={`${backup.filename}-${backup.created_at}`} className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3">
                <p className="font-semibold text-slate-900">{backup.filename}</p>
                <p className="mt-1 text-xs text-slate-500">{backup.created_at || "-"} · {backup.status || "-"}</p>
              </div>
            ))}
          </div>
        </Card>
      </div>
    </div>
  );
};
