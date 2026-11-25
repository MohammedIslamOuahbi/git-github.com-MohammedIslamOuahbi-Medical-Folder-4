import { useMemo, useState } from "react";
import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  Clipboard,
  Database,
  Laptop2,
  RefreshCw,
  Server,
  ShieldAlert,
  ShieldCheck,
  Unplug,
} from "lucide-react";
import { useNavigate } from "react-router-dom";

import { Badge } from "@/components/common/Badge";
import { Button } from "@/components/common/Button";
import { Card } from "@/components/common/Card";
import { Modal } from "@/components/common/Modal";
import { SectionHeader } from "@/components/common/SectionHeader";
import { useAuth } from "@/hooks/useAuth";
import { useMissionOperations } from "@/hooks/useMissionOperations";
import { useMissionRuntime } from "@/hooks/useMissionRuntime";
import type { MissionChangeRecord, MissionParticipant } from "@/types/mission";
import { hasPermission } from "@/utils/permissions";

const formatDateTime = (value: string | null | undefined) => {
  if (!value) return "-";
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? value
    : new Intl.DateTimeFormat("fr-FR", { dateStyle: "short", timeStyle: "short" }).format(date);
};

const shortId = (value: string | null | undefined) => (value ? `${value.slice(0, 8)}...${value.slice(-4)}` : "-");

const statusLabelMap: Record<string, string> = {
  preparing: "Preparation",
  active: "Active",
  finalizing: "Finalisation",
  finalized: "Finalisee",
  central_pending: "En attente du serveur central",
  centralizing: "Centralisation en cours",
  centralized: "Centralisee",
  aborted: "Annulee",
  failed: "Echec",
  invited: "Invite",
  connected: "Connecte",
  syncing: "Synchronisation",
  copied: "Copiee",
  disconnected: "Deconnecte",
  revoked: "Revoque",
  completed: "Terminee",
  copying: "Copie en cours",
  failed_copy: "Echec",
  not_started: "Non demarree",
};

const entityLabelMap: Record<string, string> = {
  workers: "Travailleur",
  medical_visits: "Visite medicale",
  worker_tests: "Resultat d'examen",
  prescriptions: "Ordonnance",
  aptitude_certificates: "Certificat",
  orientation_certificates: "Certificat",
  companies: "Entreprise",
  medical_campaigns: "Campagne",
};

const operationLabelMap: Record<string, string> = {
  insert: "Creation",
  update: "Modification",
  delete: "Suppression",
};

const toneForStatus = (status: string) => {
  if (["active", "connected", "completed", "centralized", "finalized", "copied"].includes(status)) {
    return "active";
  }
  if (["failed", "failed_copy", "revoked", "aborted", "disconnected"].includes(status)) {
    return "failed";
  }
  if (["finalizing", "syncing", "copying", "central_pending", "centralizing"].includes(status)) {
    return "pending";
  }
  return "inactive";
};

const buildReference = (change: MissionChangeRecord) => {
  const payloadName =
    (typeof change.payload?.name === "string" && change.payload.name) ||
    (typeof change.payload?.mission_name === "string" && change.payload.mission_name) ||
    (typeof change.payload?.first_name === "string" && change.payload.first_name);
  return payloadName || shortId(change.entity_uuid);
};

export const MissionOperationsPage = () => {
  const navigate = useNavigate();
  const { user } = useAuth();
  const missionRuntime = useMissionRuntime();
  const { runtime, switchToStandalone } = missionRuntime;
  const {
    mission,
    devices,
    changes,
    manifest,
    copyState,
    copyRun,
    activityMetrics,
    loading,
    refreshing,
    error,
    refresh,
    finalizeMission,
    disconnectDevice,
    revokeDevice,
    runLocalCopy,
  } = useMissionOperations(runtime);

  const [busyAction, setBusyAction] = useState<string | null>(null);
  const [selectedChange, setSelectedChange] = useState<MissionChangeRecord | null>(null);
  const [confirmDeviceAction, setConfirmDeviceAction] = useState<{
    action: "disconnect" | "revoke";
    device: MissionParticipant;
  } | null>(null);
  const [showStandaloneWarning, setShowStandaloneWarning] = useState(false);

  const canFinalize =
    hasPermission(user, "sync:manage") || ["Admin", "Super Admin", "Doctor"].includes(user?.role || "");
  const canManageDevices =
    hasPermission(user, "sync:manage") || ["Admin", "Super Admin"].includes(user?.role || "");
  const canViewTechnicalDetails =
    hasPermission(user, "sync:manage") || ["Admin", "Super Admin"].includes(user?.role || "");

  const connectedClients = useMemo(
    () => devices.filter((item) => item.role === "mission_client" && item.is_connected).length,
    [devices],
  );

  const remainingChanges =
    runtime.runtimeMode === "mission_client" && mission
      ? Math.max(
          0,
          (copyState?.final_mission_sequence ?? mission.mission_current_sequence ?? 0) -
            (copyState?.last_pulled_mission_sequence ?? 0),
        )
      : 0;

  const missionReadyForStandalone =
    runtime.runtimeMode === "mission_client" &&
    mission &&
    (copyState?.last_pulled_mission_sequence ?? 0) >=
      (copyState?.final_mission_sequence ?? mission.mission_current_sequence ?? Number.MAX_SAFE_INTEGER);

  const handleFinalizeMission = async () => {
    if (!mission) return;
    setBusyAction("finalize");
    try {
      await finalizeMission(mission.uuid);
    } finally {
      setBusyAction(null);
    }
  };

  const handleConfirmedDeviceAction = async () => {
    if (!mission || !confirmDeviceAction) return;
    const actionKey = `${confirmDeviceAction.action}:${confirmDeviceAction.device.device_uuid}`;
    setBusyAction(actionKey);
    try {
      if (confirmDeviceAction.action === "disconnect") {
        await disconnectDevice(mission.uuid, confirmDeviceAction.device.device_uuid);
      } else {
        await revokeDevice(mission.uuid, confirmDeviceAction.device.device_uuid);
      }
      setConfirmDeviceAction(null);
    } finally {
      setBusyAction(null);
    }
  };

  const handleRunLocalCopy = async () => {
    setBusyAction("copy");
    try {
      await runLocalCopy();
    } finally {
      setBusyAction(null);
    }
  };

  const handleSwitchToStandalone = async () => {
    if (!missionReadyForStandalone) {
      setShowStandaloneWarning(true);
      return;
    }
    setBusyAction("standalone");
    try {
      await switchToStandalone(false);
    } finally {
      setBusyAction(null);
    }
  };

  const finalizeChecks = [
    ["Base de donnees operationnelle", runtime.connectionState === "connected" ? "success" : "warning"],
    ["Aucune transaction critique en cours", "warning"],
    ["Appareils participants connus", devices.length > 0 ? "success" : "warning"],
    ["Journal de mission valide", mission ? "success" : "failure"],
    ["UUID valides", mission?.uuid ? "success" : "failure"],
    ["Sequences valides", (mission?.mission_current_sequence ?? -1) >= 0 ? "success" : "failure"],
    ["Sauvegarde de securite disponible", "warning"],
  ] as const;

  return (
    <div className="space-y-6 pb-10">
      <SectionHeader
        eyebrow="Gestion de la mission"
        title="Gestion de la mission"
        description="Suivez la mission active, les appareils connectes, l'activite medicale agregee et la copie locale post-mission depuis une interface unique."
        actionLabel={refreshing ? "Actualisation..." : "Actualiser"}
        actionIcon={RefreshCw}
        onAction={() => void refresh()}
      />

      {runtime.runtimeMode === "mission_client" && runtime.connectionState === "disconnected" ? (
        <div className="flex items-start gap-3 rounded-2xl border border-amber-200 bg-amber-50 px-4 py-4 text-amber-900">
          <ShieldAlert className="mt-0.5 h-5 w-5 shrink-0" />
          <div className="flex-1">
            <p className="font-bold">Serveur de mission inaccessible - mode lecture seule</p>
            <p className="mt-1 text-sm">
              Les ecritures restent bloquees pour eviter toute divergence. La navigation reste disponible.
            </p>
          </div>
          <Button variant="secondary" onClick={() => void missionRuntime.refresh()}>
            Reessayer
          </Button>
          <Button variant="ghost" onClick={() => navigate("/sync/connection")}>
            Parametres reseau
          </Button>
        </div>
      ) : null}

      {error ? (
        <div className="rounded-2xl border border-rose-200 bg-rose-50 px-4 py-4 text-sm font-semibold text-rose-800">
          {error}
        </div>
      ) : null}

      {!mission && !loading ? (
        <Card className="rounded-[1.75rem] p-6">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
            <div>
              <p className="text-xs font-black uppercase tracking-[0.16em] text-[#0085A3]">Aucune mission active</p>
              <h2 className="mt-2 text-2xl font-black text-slate-950">Ce poste n'a pas de mission en cours</h2>
              <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-500">
                Utilisez la page de connexion et d'infrastructure pour creer une mission serveur ou rejoindre une mission cliente.
              </p>
            </div>
            <Button icon={Server} onClick={() => navigate("/sync/connection")}>
              Ouvrir Sync & Connection
            </Button>
          </div>
        </Card>
      ) : null}

      {mission ? (
        <>
          <section className="grid gap-6 xl:grid-cols-[1.2fr_0.8fr]">
            <Card className="rounded-[1.75rem] p-6">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <p className="text-xs font-black uppercase tracking-[0.16em] text-[#0085A3]">Mission overview</p>
                  <h2 className="mt-2 text-2xl font-black text-slate-950">{mission.mission_name}</h2>
                  <p className="mt-1 text-sm font-semibold text-slate-500">{mission.mission_code}</p>
                </div>
                <Badge tone={toneForStatus(mission.status)}>{statusLabelMap[mission.status] || mission.status}</Badge>
              </div>

              <div className="mt-6 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
                {[
                  ["Mission UUID", shortId(mission.uuid)],
                  ["Serveur de mission", runtime.device?.device_code || runtime.device?.device_name || "-"],
                  ["Debut", formatDateTime(runtime.activeMission ? runtime.device?.server_time : null)],
                  ["Sequence centrale de base", String(runtime.activeMission?.base_central_sequence ?? "-")],
                  ["Sequence mission courante", String(mission.mission_current_sequence ?? 0)],
                  ["Total changements", String(manifest?.change_count ?? mission.mission_current_sequence ?? changes.length)],
                  ["Clients connectes", String(connectedClients)],
                  ["Etat finalisation", mission.status === "finalized" ? "Finalisee" : "En cours"],
                  ["Etat central", mission.status.includes("central") ? statusLabelMap[mission.status] || mission.status : "Mission locale"],
                ].map(([label, value]) => (
                  <div key={label} className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                    <p className="text-[11px] font-black uppercase tracking-[0.14em] text-slate-500">{label}</p>
                    <p className="mt-2 break-all text-sm font-bold text-slate-950">{value}</p>
                  </div>
                ))}
              </div>
            </Card>

            <Card className="rounded-[1.75rem] p-6">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <p className="text-xs font-black uppercase tracking-[0.16em] text-[#0085A3]">
                    {runtime.runtimeMode === "mission_server" ? "Finaliser la mission" : "Etat de copie locale"}
                  </p>
                  <h2 className="mt-2 text-2xl font-black text-slate-950">
                    {runtime.runtimeMode === "mission_server" ? "Cloture protegee" : "Copie post-mission"}
                  </h2>
                </div>
                <div className="rounded-2xl bg-slate-100 p-3 text-slate-700">
                  {runtime.runtimeMode === "mission_server" ? <ShieldCheck className="h-5 w-5" /> : <Laptop2 className="h-5 w-5" />}
                </div>
              </div>

              {runtime.runtimeMode === "mission_server" ? (
                <>
                  <div className="mt-5 space-y-3">
                    {finalizeChecks.map(([label, status]) => (
                      <div key={label} className="flex items-center justify-between rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3">
                        <span className="text-sm font-semibold text-slate-800">{label}</span>
                        <Badge tone={status === "success" ? "active" : status === "warning" ? "pending" : "failed"}>
                          {status === "success" ? "Reussi" : status === "warning" ? "Avertissement" : "Echec"}
                        </Badge>
                      </div>
                    ))}
                  </div>

                  <div className="mt-5 rounded-2xl border border-amber-200 bg-amber-50 px-4 py-4 text-sm leading-6 text-amber-900">
                    Apres la finalisation, les nouvelles modifications seront bloquees jusqu'a la creation d'une nouvelle mission ou une reouverture autorisee.
                  </div>

                  <div className="mt-5 flex flex-wrap gap-2">
                    <Button
                      icon={CheckCircle2}
                      loading={busyAction === "finalize"}
                      disabled={!canFinalize || mission.status !== "active"}
                      onClick={() => void handleFinalizeMission()}
                    >
                      Finaliser la mission
                    </Button>
                    <Button variant="secondary" icon={Clipboard} onClick={() => void navigator.clipboard.writeText(mission.uuid)}>
                      Copier l'UUID
                    </Button>
                  </div>
                </>
              ) : (
                <>
                  <div className="mt-5 grid gap-3 sm:grid-cols-2">
                    {[
                      ["Serveur de mission", runtime.missionServerName || runtime.device?.device_code || "-"],
                      ["Etat connexion", runtime.connectionState],
                      ["Etat mission", statusLabelMap[mission.status] || mission.status],
                      ["Etat base locale", copyState?.copy_status || "not_started"],
                      ["Derniere sequence copiee", String(copyState?.last_pulled_mission_sequence ?? 0)],
                      ["Sequence finale mission", String(copyState?.final_mission_sequence ?? mission.mission_current_sequence ?? "-")],
                      ["Changements restants", String(remainingChanges)],
                      ["Tentatives", String(copyState?.retry_count ?? 0)],
                    ].map(([label, value]) => (
                      <div key={label} className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                        <p className="text-[11px] font-black uppercase tracking-[0.14em] text-slate-500">{label}</p>
                        <p className="mt-2 break-all text-sm font-bold text-slate-950">{value}</p>
                      </div>
                    ))}
                  </div>

                  <div className="mt-5 rounded-2xl border border-sky-200 bg-sky-50 px-4 py-4 text-sm leading-6 text-sky-900">
                    Cette operation copie les changements de la mission dans la base PostgreSQL locale de ce poste. Elle ne remplace pas toute la base et ne supprime pas les donnees locales existantes.
                  </div>

                  <div className="mt-5 flex flex-wrap gap-2">
                    <Button
                      icon={Database}
                      loading={busyAction === "copy"}
                      disabled={runtime.connectionState === "disconnected" || mission.status === "active"}
                      onClick={() => void handleRunLocalCopy()}
                    >
                      Copier les donnees de la mission sur ce poste
                    </Button>
                    <Button
                      variant="secondary"
                      icon={ShieldCheck}
                      loading={busyAction === "standalone"}
                      disabled={!missionReadyForStandalone}
                      onClick={() => void handleSwitchToStandalone()}
                    >
                      Retourner au mode autonome
                    </Button>
                  </div>

                  {mission.status === "finalized" && !missionReadyForStandalone ? (
                    <div className="mt-4 rounded-2xl border border-amber-200 bg-amber-50 px-4 py-4 text-sm font-semibold text-amber-900">
                      La mission est finalisee, mais ce poste n'a pas encore copie toutes les donnees.
                    </div>
                  ) : null}
                </>
              )}
            </Card>
          </section>

          <section className="grid gap-6 xl:grid-cols-[1.2fr_0.8fr]">
            <Card className="rounded-[1.75rem] p-6">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <p className="text-xs font-black uppercase tracking-[0.16em] text-[#0085A3]">Appareils connectes</p>
                  <h2 className="mt-2 text-2xl font-black text-slate-950">Participants de mission</h2>
                </div>
                <Badge tone="reviewed">{devices.length} appareils</Badge>
              </div>

              <div className="mt-5 overflow-x-auto">
                <table className="min-w-full text-left text-sm">
                  <thead className="text-xs uppercase tracking-[0.12em] text-slate-500">
                    <tr>
                      {["Nom appareil", "Code", "Role", "Etat", "Derniere activite", "Derniere sequence copiee", "Copie locale", "Actions"].map((label) => (
                        <th key={label} className="px-3 py-3 font-black">{label}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {devices.map((device) => (
                      <tr key={device.device_uuid} className="border-t border-slate-200">
                        <td className="px-3 py-3 font-semibold text-slate-900">{device.device_name_snapshot}</td>
                        <td className="px-3 py-3 text-slate-600">{device.device_code_snapshot}</td>
                        <td className="px-3 py-3 text-slate-600">{device.role === "mission_server" ? "Serveur" : "Client"}</td>
                        <td className="px-3 py-3">
                          <Badge tone={toneForStatus(device.status)}>{statusLabelMap[device.status] || device.status}</Badge>
                        </td>
                        <td className="px-3 py-3 text-slate-600">{formatDateTime(device.last_seen_at || device.joined_at)}</td>
                        <td className="px-3 py-3 text-slate-600">{device.last_pulled_mission_sequence ?? "-"}</td>
                        <td className="px-3 py-3 text-slate-600">
                          {device.local_copy_completed_at ? `Terminee ${formatDateTime(device.local_copy_completed_at)}` : "Non signalee"}
                        </td>
                        <td className="px-3 py-3">
                          <div className="flex flex-wrap gap-2">
                            <Button variant="ghost" size="sm" onClick={() => void navigator.clipboard.writeText(device.device_uuid)}>
                              Afficher
                            </Button>
                            <Button
                              variant="secondary"
                              size="sm"
                              disabled={!canManageDevices || device.role === "mission_server"}
                              onClick={() => setConfirmDeviceAction({ action: "disconnect", device })}
                            >
                              Deconnecter
                            </Button>
                            <Button
                              variant="danger"
                              size="sm"
                              disabled={!canManageDevices || device.role === "mission_server"}
                              onClick={() => setConfirmDeviceAction({ action: "revoke", device })}
                            >
                              Revoquer
                            </Button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Card>

            <Card className="rounded-[1.75rem] p-6">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <p className="text-xs font-black uppercase tracking-[0.16em] text-[#0085A3]">Mission activity metrics</p>
                  <h2 className="mt-2 text-2xl font-black text-slate-950">Activite medicale agregee</h2>
                </div>
                <Activity className="h-5 w-5 text-slate-400" />
              </div>

              <div className="mt-5 grid gap-3 sm:grid-cols-2">
                {[
                  ["Travailleurs crees", String(activityMetrics.workersCreated)],
                  ["Visites creees", String(activityMetrics.visitsCreated)],
                  ["Resultats modifies", String(activityMetrics.testResultsUpdated)],
                  ["Ordonnances creees", String(activityMetrics.prescriptionsCreated)],
                  ["Certificats crees", String(activityMetrics.certificatesCreated)],
                  ["Total changements", String(activityMetrics.totalChanges)],
                ].map(([label, value]) => (
                  <div key={label} className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                    <p className="text-[11px] font-black uppercase tracking-[0.14em] text-slate-500">{label}</p>
                    <p className="mt-2 text-2xl font-black text-slate-950">{value}</p>
                  </div>
                ))}
              </div>

              <div className="mt-5 space-y-3 rounded-2xl border border-slate-200 bg-slate-50 p-4">
                <div className="flex items-center justify-between gap-3">
                  <span className="text-sm font-semibold text-slate-700">Derniere activite</span>
                  <span className="text-sm font-bold text-slate-950">{formatDateTime(activityMetrics.latestActivityTime)}</span>
                </div>
                <div className="flex items-start justify-between gap-3">
                  <span className="text-sm font-semibold text-slate-700">Changements par appareil</span>
                  <span className="max-w-[60%] text-right text-sm text-slate-600">
                    {Object.entries(activityMetrics.changesByDevice).length
                      ? Object.entries(activityMetrics.changesByDevice)
                          .map(([key, value]) => `${shortId(key)}: ${value}`)
                          .join(" | ")
                      : "-"}
                  </span>
                </div>
                <div className="flex items-start justify-between gap-3">
                  <span className="text-sm font-semibold text-slate-700">Changements par utilisateur</span>
                  <span className="max-w-[60%] text-right text-sm text-slate-600">
                    {Object.entries(activityMetrics.changesByUser).length
                      ? Object.entries(activityMetrics.changesByUser)
                          .map(([key, value]) => `${shortId(key)}: ${value}`)
                          .join(" | ")
                      : "-"}
                  </span>
                </div>
              </div>
            </Card>
          </section>

          <section className="grid gap-6 xl:grid-cols-[1.15fr_0.85fr]">
            <Card className="rounded-[1.75rem] p-6">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <p className="text-xs font-black uppercase tracking-[0.16em] text-[#0085A3]">Recent mission changes</p>
                  <h2 className="mt-2 text-2xl font-black text-slate-950">Journal recent</h2>
                </div>
                <Badge tone="reviewed">{changes.length} lignes</Badge>
              </div>

              <div className="mt-5 overflow-x-auto">
                <table className="min-w-full text-left text-sm">
                  <thead className="text-xs uppercase tracking-[0.12em] text-slate-500">
                    <tr>
                      {["Sequence", "Date", "Appareil", "Utilisateur", "Entite", "Operation", "Reference", "Etat"].map((label) => (
                        <th key={label} className="px-3 py-3 font-black">{label}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {[...changes].reverse().map((change) => (
                      <tr
                        key={change.change_uuid}
                        className="cursor-pointer border-t border-slate-200 hover:bg-slate-50"
                        onClick={() => setSelectedChange(change)}
                      >
                        <td className="px-3 py-3 font-semibold text-slate-900">{change.mission_sequence}</td>
                        <td className="px-3 py-3 text-slate-600">{formatDateTime(change.occurred_at)}</td>
                        <td className="px-3 py-3 text-slate-600">{shortId(change.source_device_uuid)}</td>
                        <td className="px-3 py-3 text-slate-600">{shortId(change.source_user_uuid)}</td>
                        <td className="px-3 py-3 text-slate-600">{entityLabelMap[change.entity_type] || change.entity_type}</td>
                        <td className="px-3 py-3 text-slate-600">{operationLabelMap[change.operation] || change.operation}</td>
                        <td className="px-3 py-3 text-slate-600">{buildReference(change)}</td>
                        <td className="px-3 py-3">
                          <Badge tone="active">Valide</Badge>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Card>

            <Card className="rounded-[1.75rem] p-6">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <p className="text-xs font-black uppercase tracking-[0.16em] text-[#0085A3]">Mission manifest</p>
                  <h2 className="mt-2 text-2xl font-black text-slate-950">Manifeste technique</h2>
                </div>
                <Server className="h-5 w-5 text-slate-400" />
              </div>

              {manifest ? (
                <div className="mt-5 space-y-3">
                  {[
                    ["Mission UUID", shortId(manifest.mission_uuid)],
                    ["Serveur", shortId(manifest.server_device_uuid)],
                    ["Sequence centrale de base", String(manifest.base_central_sequence ?? "-")],
                    ["Sequence finale mission", String(manifest.final_mission_sequence)],
                    ["Total changements", String(manifest.change_count)],
                    ["Revision schema", manifest.schema_revision || "-"],
                    ["Checksum verification", shortId(manifest.checksum)],
                    ["Finalisation", formatDateTime(manifest.created_at)],
                  ].map(([label, value]) => (
                    <div key={label} className="flex items-center justify-between gap-3 rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3">
                      <span className="text-sm font-semibold text-slate-700">{label}</span>
                      <span className="text-sm font-bold text-slate-950">{value}</span>
                    </div>
                  ))}
                  <div className="flex flex-wrap gap-2">
                    <Button variant="secondary" icon={Clipboard} onClick={() => void navigator.clipboard.writeText(manifest.mission_uuid)}>
                      Copier mission UUID
                    </Button>
                    <Button variant="secondary" icon={Clipboard} onClick={() => void navigator.clipboard.writeText(manifest.checksum)}>
                      Copier checksum
                    </Button>
                  </div>
                </div>
              ) : (
                <div className="mt-5 rounded-2xl border border-slate-200 bg-slate-50 px-4 py-5 text-sm text-slate-600">
                  Le manifeste apparaitra ici apres la finalisation de la mission.
                </div>
              )}

              {runtime.runtimeMode === "mission_client" ? (
                <div className="mt-5 rounded-2xl border border-slate-200 bg-slate-50 p-4">
                  <p className="text-sm font-bold text-slate-900">
                    {copyRun.status === "completed"
                      ? "Copie locale terminee"
                      : copyRun.status === "interrupted"
                        ? "La copie a ete interrompue"
                        : "Progression de copie"}
                  </p>
                  <div className="mt-3 space-y-2 text-sm text-slate-600">
                    <p>Etape: {copyRun.stage || copyState?.copy_status || "Non demarree"}</p>
                    <p>Batch courant: {copyRun.currentBatch || 0}</p>
                    <p>Changements appliques: {copyRun.appliedChanges}</p>
                    <p>Derniere sequence mission: {copyRun.lastMissionSequence || copyState?.last_pulled_mission_sequence || 0}</p>
                    <p>Sequence finale mission: {copyRun.finalMissionSequence ?? copyState?.final_mission_sequence ?? mission.mission_current_sequence}</p>
                    <p>Changements restants: {remainingChanges}</p>
                    <p>Erreurs: {copyRun.error || copyState?.last_error_message || "-"}</p>
                    <p>Tentatives: {copyState?.retry_count ?? 0}</p>
                  </div>
                </div>
              ) : null}
            </Card>
          </section>
        </>
      ) : null}

      <Modal
        open={Boolean(confirmDeviceAction)}
        title={confirmDeviceAction?.action === "revoke" ? "Revoquer cet appareil" : "Deconnecter cet appareil"}
        onClose={() => setConfirmDeviceAction(null)}
      >
        <div className="space-y-4">
          <p className="text-sm leading-6 text-slate-600">
            {confirmDeviceAction?.action === "revoke"
              ? "Cet appareil ne pourra plus participer a la mission tant que le backend ne leve pas sa revocation."
              : "Cet appareil sera marque comme deconnecte de la mission."}
          </p>
          <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm font-semibold text-slate-800">
            {confirmDeviceAction?.device.device_name_snapshot} - {confirmDeviceAction?.device.device_code_snapshot}
          </div>
          <div className="flex justify-end gap-2">
            <Button variant="secondary" onClick={() => setConfirmDeviceAction(null)}>Annuler</Button>
            <Button
              variant={confirmDeviceAction?.action === "revoke" ? "danger" : "primary"}
              loading={
                busyAction ===
                `${confirmDeviceAction?.action}:${confirmDeviceAction?.device.device_uuid}`
              }
              onClick={() => void handleConfirmedDeviceAction()}
            >
              Confirmer
            </Button>
          </div>
        </div>
      </Modal>

      <Modal open={showStandaloneWarning} title="Copie locale incomplete" onClose={() => setShowStandaloneWarning(false)}>
        <div className="space-y-4">
          <div className="rounded-2xl border border-amber-200 bg-amber-50 px-4 py-4 text-sm leading-6 text-amber-900">
            La copie locale de la mission n'est pas terminee. Ce poste ne contient pas encore toutes les donnees de la mission.
          </div>
          <div className="flex justify-end gap-2">
            <Button variant="secondary" onClick={() => setShowStandaloneWarning(false)}>Annuler</Button>
            <Button onClick={() => { setShowStandaloneWarning(false); void handleRunLocalCopy(); }}>
              Continuer la copie
            </Button>
          </div>
        </div>
      </Modal>

      <Modal open={Boolean(selectedChange)} title="Detail du changement" onClose={() => setSelectedChange(null)}>
        <div className="space-y-4">
          <div className="grid gap-3 sm:grid-cols-2">
            {selectedChange
              ? [
                  ["Sequence", String(selectedChange.mission_sequence)],
                  ["Entite", entityLabelMap[selectedChange.entity_type] || selectedChange.entity_type],
                  ["Operation", operationLabelMap[selectedChange.operation] || selectedChange.operation],
                  ["Reference", buildReference(selectedChange)],
                  ["Appareil", shortId(selectedChange.source_device_uuid)],
                  ["Utilisateur", shortId(selectedChange.source_user_uuid)],
                ].map(([label, value]) => (
                  <div key={label} className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                    <p className="text-[11px] font-black uppercase tracking-[0.14em] text-slate-500">{label}</p>
                    <p className="mt-2 text-sm font-bold text-slate-950">{value}</p>
                  </div>
                ))
              : null}
          </div>
          {canViewTechnicalDetails && selectedChange ? (
            <pre className="max-h-[320px] overflow-auto rounded-2xl border border-slate-200 bg-slate-950 p-4 text-xs text-slate-100">
              {JSON.stringify(selectedChange.payload || {}, null, 2)}
            </pre>
          ) : (
            <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-4 text-sm text-slate-600">
              Les details techniques sont restreints.
            </div>
          )}
        </div>
      </Modal>
    </div>
  );
};
