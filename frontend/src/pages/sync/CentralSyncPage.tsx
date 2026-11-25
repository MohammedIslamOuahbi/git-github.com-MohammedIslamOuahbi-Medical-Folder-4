import { useMemo, useState } from "react";
import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  Clipboard,
  Database,
  HardDriveDownload,
  History,
  RefreshCw,
  Server,
  ShieldCheck,
  ShieldQuestion,
  Sparkles,
  Upload,
  Wifi,
} from "lucide-react";

import { Badge } from "@/components/common/Badge";
import { Button } from "@/components/common/Button";
import { Card } from "@/components/common/Card";
import { Modal } from "@/components/common/Modal";
import { SectionHeader } from "@/components/common/SectionHeader";
import { CentralEntityStatusBadge } from "@/components/sync/CentralEntityStatusBadge";
import { useAuth } from "@/hooks/useAuth";
import { useCentralSync } from "@/hooks/useCentralSync";
import { useMissionRuntime } from "@/hooks/useMissionRuntime";
import type { CentralConflictRecord, CentralConflictResolutionType } from "@/types/centralSync";
import { hasPermission } from "@/utils/permissions";

const formatDateTime = (value: string | null | undefined) => {
  if (!value) return "-";
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? value
    : new Intl.DateTimeFormat("fr-FR", { dateStyle: "short", timeStyle: "short" }).format(date);
};

const shortId = (value: string | null | undefined) => (value ? `${value.slice(0, 8)}...${value.slice(-4)}` : "-");

const syncStateLabel: Record<string, string> = {
  idle: "Jamais envoyee",
  checking: "Verification",
  not_ready: "Non prete",
  pushing: "Envoi mission -> central",
  processing: "Traitement",
  pulling: "Telechargement central",
  applying: "Application locale",
  completed: "Centralisee",
  completed_with_conflicts: "Centralisee avec conflits",
  failed: "Echec",
};

const readinessTone = (status: string) => {
  if (status === "passed") return "active";
  if (status === "warning") return "pending";
  return "failed";
};

const entityLabelMap: Record<string, string> = {
  workers: "Travailleur",
  medical_visits: "Visite medicale",
  worker_tests: "Examen",
  prescriptions: "Ordonnance",
  aptitude_certificates: "Certificat d'aptitude",
  orientation_certificates: "Certificat d'orientation",
  companies: "Entreprise",
  branches: "Branche",
  drilling_sites: "Site",
  medical_campaigns: "Campagne",
  users: "Utilisateur",
};

const isMedicalConflict = (entityType: string) =>
  ["medical_visits", "worker_tests", "prescriptions", "aptitude_certificates", "orientation_certificates"].includes(entityType);

const isImmutableSignedConflict = (conflict: CentralConflictRecord | null) =>
  Boolean(
    conflict &&
      ["prescriptions", "aptitude_certificates", "orientation_certificates", "medical_visits"].includes(conflict.entity_type) &&
      ((conflict.central_snapshot?.validated_at as string | undefined) ||
        (conflict.central_snapshot?.validator_name as string | undefined) ||
        (conflict.central_snapshot?.status as string | undefined) === "validated"),
  );

const copy = async (value: string) => {
  if (typeof navigator !== "undefined" && navigator.clipboard) {
    await navigator.clipboard.writeText(value);
  }
};

export const CentralSyncPage = () => {
  const { user } = useAuth();
  const missionRuntime = useMissionRuntime();
  const { runtime } = missionRuntime;
  const central = useCentralSync(runtime, user);

  const [selectedConflict, setSelectedConflict] = useState<CentralConflictRecord | null>(null);
  const [resolutionType, setResolutionType] = useState<CentralConflictResolutionType>("keep_central");
  const [resolutionReason, setResolutionReason] = useState("");
  const [manualPayload, setManualPayload] = useState("");
  const [filterMode, setFilterMode] = useState<"all" | "medical" | "administrative" | "pending" | "resolved">("all");
  const [bootstrapAllowOverwrite, setBootstrapAllowOverwrite] = useState(false);
  const [busyAction, setBusyAction] = useState<string | null>(null);

  const canStartSync =
    hasPermission(user, "sync:manage") || ["Super Admin", "Admin", "Doctor"].includes(user?.role || "");
  const canResolveAdministrative = ["Super Admin", "Admin"].includes(user?.role || "");
  const canResolveMedical = ["Super Admin", "Admin"].includes(user?.role || "");
  const canAcceptGeneration = ["Super Admin"].includes(user?.role || "");
  const canBootstrap = ["Super Admin"].includes(user?.role || "");
  const canViewTechnical = hasPermission(user, "sync:manage") || ["Super Admin", "Admin"].includes(user?.role || "");

  const filteredConflicts = useMemo(() => {
    return central.conflicts.filter((conflict) => {
      if (filterMode === "pending") return conflict.status === "pending";
      if (filterMode === "resolved") return conflict.status === "resolved";
      if (filterMode === "medical") return isMedicalConflict(conflict.entity_type);
      if (filterMode === "administrative") return !isMedicalConflict(conflict.entity_type);
      return true;
    });
  }, [central.conflicts, filterMode]);

  const currentConflictImmutable = isImmutableSignedConflict(selectedConflict);
  const resolutionOptions = [
    { value: "keep_central", label: "Conserver la version centrale", disabled: false },
    {
      value: "accept_mission",
      label: "Accepter la version de la mission",
      disabled: currentConflictImmutable,
    },
    { value: "manual_merge", label: "Fusionner manuellement", disabled: false },
    { value: "create_revision", label: "Creer une revision", disabled: false },
  ] as const;

  const handleSync = async () => {
    setBusyAction("sync");
    try {
      await central.runCentralSynchronization();
    } finally {
      setBusyAction(null);
    }
  };

  const handlePull = async () => {
    setBusyAction("pull");
    try {
      await central.updateFromCentral();
    } finally {
      setBusyAction(null);
    }
  };

  const handleResolveConflict = async () => {
    if (!selectedConflict) return;
    let payload: Record<string, unknown> | null = null;
    if (resolutionType === "manual_merge") {
      if (!manualPayload.trim()) return;
      payload = JSON.parse(manualPayload) as Record<string, unknown>;
    }
    if (["accept_mission", "manual_merge", "create_revision"].includes(resolutionType) && !resolutionReason.trim()) {
      return;
    }
    setBusyAction(`resolve:${selectedConflict.uuid}`);
    try {
      await central.resolveConflict(selectedConflict.uuid, resolutionType, payload, resolutionReason);
      setSelectedConflict(null);
      setResolutionReason("");
      setManualPayload("");
      setResolutionType("keep_central");
    } finally {
      setBusyAction(null);
    }
  };

  const handleBootstrap = async () => {
    setBusyAction("bootstrap");
    try {
      await central.runBootstrap(bootstrapAllowOverwrite);
    } finally {
      setBusyAction(null);
    }
  };

  const mandatoryFailure = central.mandatoryReadinessFailures.length > 0;
  const currentMissionCentralLabel =
    central.syncSummary.status === "centralized_with_conflicts"
      ? "Centralisee avec conflits"
      : central.syncSummary.status === "centralized"
        ? "Centralisee"
        : syncStateLabel[central.syncState];

  return (
    <div className="space-y-6 pb-10">
      <SectionHeader
        eyebrow="Infrastructure centrale"
        title="Synchronisation avec le serveur central"
        description="Centralisez une mission finalisee, verifiez l'identite du serveur central, traitez les conflits et pilotez le bootstrap de ce poste."
        actionLabel={central.refreshing ? "Actualisation..." : "Actualiser"}
        actionIcon={RefreshCw}
        onAction={() => void central.refresh()}
      />

      {central.syncError ? (
        <div className="rounded-2xl border border-rose-200 bg-rose-50 px-4 py-4 text-sm font-semibold text-rose-800">
          {central.syncError}
        </div>
      ) : null}

      <section className="grid gap-6 xl:grid-cols-[1.15fr_0.85fr]">
        <Card className="rounded-[1.75rem] p-6">
          <div className="flex items-start justify-between gap-4">
            <div>
              <p className="text-xs font-black uppercase tracking-[0.16em] text-[#0085A3]">Serveur central</p>
              <h2 className="mt-2 text-2xl font-black text-slate-950">Identite et connexion</h2>
              <p className="mt-1 text-sm leading-6 text-slate-500">
                Ce poste centralise les donnees vers l'autorite finale de l'organisation.
              </p>
            </div>
            <Badge tone={central.remoteServerInfo ? "active" : "inactive"}>
              {central.remoteServerInfo ? "Connecte" : "Non connecte"}
            </Badge>
          </div>

          <div className="mt-5 grid gap-3 md:grid-cols-2">
            <label className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
              <span className="text-[11px] font-black uppercase tracking-[0.14em] text-slate-500">Adresse du serveur central</span>
              <input
                value={central.serverUrl}
                onChange={(event) => central.setServerUrl(event.target.value)}
                placeholder="http://192.168.1.10:8000/api/v1"
                className="mt-3 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm font-semibold text-slate-900 outline-none ring-0 transition focus:border-[#0085A3]"
              />
            </label>
            <label className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
              <span className="text-[11px] font-black uppercase tracking-[0.14em] text-slate-500">Secret appareil</span>
              <input
                value={central.deviceSecret}
                onChange={(event) => central.setDeviceSecret(event.target.value)}
                placeholder="Secret de centralisation"
                className="mt-3 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm font-semibold text-slate-900 outline-none ring-0 transition focus:border-[#0085A3]"
              />
            </label>
          </div>

          <div className="mt-5 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            {[
              ["Nom serveur", central.remoteServerInfo?.status === "active" ? "Serveur central permanent" : "Serveur central"],
              ["Code appareil", central.remoteServerInfo?.device_uuid ? shortId(central.remoteServerInfo.device_uuid) : "-"],
              ["UUID serveur", shortId(central.remoteServerInfo?.server_uuid)],
              ["Generation UUID", shortId(central.remoteServerInfo?.server_generation_uuid)],
              ["Revision schema", central.remoteServerInfo?.schema_revision || "-"],
              ["Protocole", central.remoteServerInfo?.protocol_version || "-"],
              ["Dernier contact", formatDateTime(central.lastContactAt || central.remoteServerInfo?.last_health_check_at)],
              ["Sequence centrale", String(central.remoteServerInfo?.current_central_sequence ?? central.latestKnownCentralSequence)],
              ["Connexion", central.remoteServerInfo ? "Disponible" : "A verifier"],
            ].map(([label, value]) => (
              <div key={label} className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                <p className="text-[11px] font-black uppercase tracking-[0.14em] text-slate-500">{label}</p>
                <p className="mt-2 break-all text-sm font-bold text-slate-950">{value}</p>
              </div>
            ))}
          </div>

          <div className="mt-5 flex flex-wrap gap-2">
            <Button icon={Wifi} loading={busyAction === "test"} onClick={() => { setBusyAction("test"); void central.testConnection().finally(() => setBusyAction(null)); }}>
              Tester la connexion
            </Button>
            <Button variant="secondary" icon={Clipboard} onClick={() => void copy(central.serverUrl)} aria-label="Copier l'adresse du serveur central">
              Copier l'adresse
            </Button>
            <Button
              variant="secondary"
              icon={ShieldCheck}
              disabled={!central.remoteServerInfo || !canAcceptGeneration}
              onClick={() => central.verifyServerIdentity()}
            >
              Verifier l'identite du serveur
            </Button>
          </div>

          {central.storedIdentity ? (
            <div className="mt-4 rounded-2xl border border-emerald-200 bg-emerald-50 px-4 py-4 text-sm text-emerald-900">
              Identite approuvee: {shortId(central.storedIdentity.serverUuid)} / {shortId(central.storedIdentity.generationUuid)}
            </div>
          ) : null}
        </Card>

        <Card className="rounded-[1.75rem] p-6">
          <div className="flex items-start justify-between gap-4">
            <div>
              <p className="text-xs font-black uppercase tracking-[0.16em] text-[#0085A3]">Etat du poste</p>
              <h2 className="mt-2 text-2xl font-black text-slate-950">Appareil mobile</h2>
            </div>
            <Server className="h-5 w-5 text-slate-400" />
          </div>
          <div className="mt-5 grid gap-3">
            {[
              ["Nom appareil", runtime.device?.device_name || "-"],
              ["Code appareil", runtime.device?.device_code || "-"],
              ["Mode d'execution", runtime.runtimeMode],
              ["Curseur central local", String(central.latestKnownCentralSequence)],
              ["Derniere sequence connue", String(central.latestKnownCentralSequence)],
              ["Changements en attente", String(central.syncCounts.pending || central.currentMission?.mission_current_sequence || 0)],
              ["Conflits non resolus", String(central.conflicts.filter((item) => item.status === "pending").length)],
              ["Derniere sync centrale", formatDateTime(central.syncSummary.centralizedAt)],
              ["Mission en cours", central.currentMission?.mission_name || "-"],
              ["Etat mission", central.currentMission?.status || "-"],
              ["Sequence mission finale", String(central.missionManifest?.final_mission_sequence ?? central.currentMission?.mission_current_sequence ?? "-")],
            ].map(([label, value]) => (
              <div key={label} className="flex items-center justify-between gap-4 rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3">
                <span className="text-sm font-semibold text-slate-700">{label}</span>
                <span className="text-right text-sm font-bold text-slate-950">{value}</span>
              </div>
            ))}
          </div>
        </Card>
      </section>

      <section className="grid gap-6 xl:grid-cols-[1.1fr_0.9fr]">
        <Card className="rounded-[1.75rem] p-6">
          <div className="flex items-start justify-between gap-4">
            <div>
              <p className="text-xs font-black uppercase tracking-[0.16em] text-[#0085A3]">Controles prealables</p>
              <h2 className="mt-2 text-2xl font-black text-slate-950">Verification de readiness</h2>
            </div>
            <Badge tone={mandatoryFailure ? "failed" : central.readiness?.ready ? "active" : "pending"}>
              {mandatoryFailure ? "Bloquante" : central.readiness?.ready ? "Prete" : "A verifier"}
            </Badge>
          </div>
          <div className="mt-5 space-y-3">
            {(central.readiness?.checks || []).map((check) => (
              <div key={check.key} className="flex items-start justify-between gap-4 rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3">
                <div>
                  <p className="text-sm font-bold text-slate-900">{check.label}</p>
                  {check.detail ? <p className="mt-1 text-xs text-slate-500">{check.detail}</p> : null}
                </div>
                <Badge tone={readinessTone(check.status)}>
                  {check.status === "passed" ? "Reussi" : check.status === "warning" ? "Avertissement" : "Echec"}
                </Badge>
              </div>
            ))}
          </div>
        </Card>

        <Card className="rounded-[1.75rem] p-6">
          <div className="flex items-start justify-between gap-4">
            <div>
              <p className="text-xs font-black uppercase tracking-[0.16em] text-[#0085A3]">Action principale</p>
              <h2 className="mt-2 text-2xl font-black text-slate-950">Synchroniser avec le serveur central</h2>
            </div>
            <Activity className="h-5 w-5 text-slate-400" />
          </div>

          <div className="mt-5 space-y-3">
            {[
              ["Verification du serveur central", central.syncSteps.server],
              ["Authentification de l'appareil", central.syncSteps.auth],
              ["Envoi des changements de mission", central.syncSteps.push],
              ["Traitement des doublons", central.syncSteps.dedupe],
              ["Detection des conflits", central.syncSteps.conflict],
              ["Telechargement des decisions centrales", central.syncSteps.pull],
              ["Application locale", central.syncSteps.apply],
              ["Verification finale", central.syncSteps.verify],
            ].map(([label, status]) => (
              <div key={label} className="flex items-center justify-between gap-4 rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3">
                <span className="text-sm font-semibold text-slate-700">{label}</span>
                <Badge tone={status === "completed" ? "active" : status === "running" ? "pending" : status === "failed" ? "failed" : "inactive"}>
                  {status === "completed" ? "Reussi" : status === "running" ? "En cours" : status === "failed" ? "Echec" : "En attente"}
                </Badge>
              </div>
            ))}
          </div>

          <div className="mt-5 grid gap-3 sm:grid-cols-2">
            {[
              ["En attente", central.syncCounts.pending],
              ["Envoyes", central.syncCounts.sent],
              ["Acceptes", central.syncCounts.accepted],
              ["Doublons", central.syncCounts.duplicates],
              ["Auto-merge", central.syncCounts.autoMerged],
              ["Conflits", central.syncCounts.conflicts],
              ["Rejetes", central.syncCounts.rejected],
              ["Telecharges", central.syncCounts.pulled],
              ["Appliques", central.syncCounts.applied],
            ].map(([label, value]) => (
              <div key={label} className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3">
                <p className="text-[11px] font-black uppercase tracking-[0.14em] text-slate-500">{label}</p>
                <p className="mt-2 text-2xl font-black text-slate-950">{value}</p>
              </div>
            ))}
          </div>

          <div className="mt-5 flex flex-wrap gap-2">
            <Button icon={Upload} loading={busyAction === "sync"} disabled={!canStartSync || mandatoryFailure || Boolean(central.pendingIdentity)} onClick={() => void handleSync()}>
              Synchroniser avec le serveur central
            </Button>
            <Button variant="secondary" icon={HardDriveDownload} loading={busyAction === "pull"} disabled={Boolean(central.pendingIdentity)} onClick={() => void handlePull()}>
              Mettre a jour ce poste depuis le serveur central
            </Button>
          </div>
        </Card>
      </section>

      <section className="grid gap-6 xl:grid-cols-[0.95fr_1.05fr]">
        <Card className="rounded-[1.75rem] p-6">
          <div className="flex items-start justify-between gap-4">
            <div>
              <p className="text-xs font-black uppercase tracking-[0.16em] text-[#0085A3]">Etat de centralisation</p>
              <h2 className="mt-2 text-2xl font-black text-slate-950">Resume final</h2>
            </div>
            <CentralEntityStatusBadge centralSyncStatus={central.syncSummary.status === "centralized" ? "central_finalized" : central.syncSummary.status} />
          </div>
          <div className="mt-5 grid gap-3">
            {[
              ["Etat de centralisation", currentMissionCentralLabel],
              ["Premiere sequence centrale", String(central.syncSummary.firstCentralSequence ?? "-")],
              ["Derniere sequence centrale", String(central.syncSummary.lastCentralSequence ?? "-")],
              ["Date de centralisation", formatDateTime(central.syncSummary.centralizedAt)],
              ["Acceptes", String(central.syncSummary.acceptedCount)],
              ["Conflits", String(central.syncSummary.conflictCount)],
              ["Rejetes", String(central.syncSummary.rejectedCount)],
            ].map(([label, value]) => (
              <div key={label} className="flex items-center justify-between gap-4 rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3">
                <span className="text-sm font-semibold text-slate-700">{label}</span>
                <span className="text-right text-sm font-bold text-slate-950">{value}</span>
              </div>
            ))}
          </div>
          <div className="mt-5 rounded-2xl border border-slate-200 bg-slate-50 p-4">
            <p className="text-sm font-bold text-slate-900">Distinction des etats</p>
            <div className="mt-3 flex flex-wrap gap-2">
              <Badge tone="completed">Visite medicalement validee</Badge>
              <Badge tone="pending">Mission localement finalisee</Badge>
              <Badge tone="active">Finalise centralement</Badge>
            </div>
          </div>
        </Card>

        <Card className="rounded-[1.75rem] p-6">
          <div className="flex items-start justify-between gap-4">
            <div>
              <p className="text-xs font-black uppercase tracking-[0.16em] text-[#0085A3]">Conflits de centralisation</p>
              <h2 className="mt-2 text-2xl font-black text-slate-950">Revision et resolution</h2>
            </div>
            <Badge tone={central.conflicts.some((item) => item.status === "pending") ? "failed" : "active"}>
              {central.conflicts.filter((item) => item.status === "pending").length} en attente
            </Badge>
          </div>

          <div className="mt-5 flex flex-wrap gap-2">
            {[
              ["all", "Tous"],
              ["medical", "Medicaux"],
              ["administrative", "Administratifs"],
              ["pending", "En attente"],
              ["resolved", "Resolus"],
            ].map(([value, label]) => (
              <Button key={value} variant={filterMode === value ? "primary" : "secondary"} size="sm" onClick={() => setFilterMode(value as typeof filterMode)}>
                {label}
              </Button>
            ))}
          </div>

          <div className="mt-5 overflow-x-auto">
            <table className="min-w-full text-left text-sm">
              <thead className="text-xs uppercase tracking-[0.12em] text-slate-500">
                <tr>
                  {["Entite", "Mission", "Appareil", "Utilisateur", "Champs", "Detection", "Etat", "Action"].map((label) => (
                    <th key={label} className="px-3 py-3 font-black">{label}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {filteredConflicts.map((conflict) => (
                  <tr key={conflict.uuid} className="border-t border-slate-200">
                    <td className="px-3 py-3 font-semibold text-slate-900">{entityLabelMap[conflict.entity_type] || conflict.entity_type}</td>
                    <td className="px-3 py-3 text-slate-600">{shortId(conflict.mission_uuid)}</td>
                    <td className="px-3 py-3 text-slate-600">{shortId(conflict.source_device_uuid)}</td>
                    <td className="px-3 py-3 text-slate-600">{shortId(conflict.source_user_uuid)}</td>
                    <td className="px-3 py-3 text-slate-600">{conflict.conflicting_fields.join(", ") || "-"}</td>
                    <td className="px-3 py-3 text-slate-600">{formatDateTime(conflict.created_at)}</td>
                    <td className="px-3 py-3">
                      <Badge tone={conflict.status === "resolved" ? "active" : "failed"}>{conflict.status}</Badge>
                    </td>
                    <td className="px-3 py-3">
                      <Button variant="secondary" size="sm" onClick={() => setSelectedConflict(conflict)}>
                        Ouvrir
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      </section>

      <section className="grid gap-6 xl:grid-cols-[1fr_1fr]">
        <Card className="rounded-[1.75rem] p-6">
          <div className="flex items-start justify-between gap-4">
            <div>
              <p className="text-xs font-black uppercase tracking-[0.16em] text-[#0085A3]">Bootstrap</p>
              <h2 className="mt-2 text-2xl font-black text-slate-950">Initialisation d'un nouveau poste</h2>
            </div>
            <Sparkles className="h-5 w-5 text-slate-400" />
          </div>
          <div className="mt-5 grid gap-3 sm:grid-cols-2">
            {[
              ["Poste", runtime.device?.device_name || "-"],
              ["Code", runtime.device?.device_code || "-"],
              ["UUID", shortId(runtime.device?.device_uuid)],
              ["Version app", runtime.device?.app_version || "-"],
              ["Schema local", runtime.device?.schema_revision || "-"],
              ["Mission active", central.currentMission?.status || "Aucune"],
              ["Changements en attente", String(central.syncCounts.pending || 0)],
              ["Snapshot central", String(central.bootstrapManifest?.snapshot_central_sequence ?? "-")],
            ].map(([label, value]) => (
              <div key={label} className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                <p className="text-[11px] font-black uppercase tracking-[0.14em] text-slate-500">{label}</p>
                <p className="mt-2 text-sm font-bold text-slate-950">{value}</p>
              </div>
            ))}
          </div>
          <label className="mt-5 flex items-start gap-3 rounded-2xl border border-amber-200 bg-amber-50 px-4 py-4 text-sm text-amber-900">
            <input
              type="checkbox"
              checked={bootstrapAllowOverwrite}
              onChange={(event) => setBootstrapAllowOverwrite(event.target.checked)}
              className="mt-1"
            />
            <span>
              Autoriser le bootstrap uniquement si vous avez confirme qu'aucun travail local non envoye ne doit etre preserve.
            </span>
          </label>
          <div className="mt-5 flex flex-wrap gap-2">
            <Button icon={Database} loading={busyAction === "bootstrap"} disabled={!canBootstrap} onClick={() => void handleBootstrap()}>
              Demarrer le bootstrap
            </Button>
          </div>
          {central.bootstrapError ? (
            <div className="mt-4 rounded-2xl border border-rose-200 bg-rose-50 px-4 py-4 text-sm text-rose-800">
              {central.bootstrapError}
            </div>
          ) : null}
        </Card>

        <Card className="rounded-[1.75rem] p-6">
          <div className="flex items-start justify-between gap-4">
            <div>
              <p className="text-xs font-black uppercase tracking-[0.16em] text-[#0085A3]">Integrite et historique</p>
              <h2 className="mt-2 text-2xl font-black text-slate-950">Suivi infrastructure</h2>
            </div>
            <History className="h-5 w-5 text-slate-400" />
          </div>
          <div className="mt-5 space-y-3">
            {[
              ["Controle UUID", central.integrity?.null_uuid_issues.length ? "Echec" : "Valide"],
              ["Relations", central.integrity?.broken_uuid_relationships.length ? "Echec" : "Valide"],
              ["Journal", central.integrity?.duplicate_change_uuid_issues.length ? "Echec" : "Valide"],
              ["Curseurs", central.integrity?.invalid_cursor_issues.length ? "Echec" : "Valide"],
              ["Fichiers / signatures", central.integrity?.missing_signature_file_metadata.length ? "Echec" : "Valide"],
              ["Derniere verification", formatDateTime(central.lastContactAt)],
            ].map(([label, value]) => (
              <div key={label} className="flex items-center justify-between gap-4 rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3">
                <span className="text-sm font-semibold text-slate-700">{label}</span>
                <span className="text-right text-sm font-bold text-slate-950">{value}</span>
              </div>
            ))}
          </div>
          <div className="mt-5 flex flex-wrap gap-2">
            <Button variant="secondary" icon={ShieldQuestion} onClick={() => void central.refresh()}>
              Verifier l'integrite
            </Button>
          </div>
        </Card>
      </section>

      <section className="grid gap-6 xl:grid-cols-[1fr_1fr]">
        <Card className="rounded-[1.75rem] p-6">
          <div className="flex items-start justify-between gap-4">
            <div>
              <p className="text-xs font-black uppercase tracking-[0.16em] text-[#0085A3]">Historique des synchronisations</p>
              <h2 className="mt-2 text-2xl font-black text-slate-950">Runs de ce poste</h2>
            </div>
            <RefreshCw className="h-5 w-5 text-slate-400" />
          </div>
          <div className="mt-5 overflow-x-auto">
            <table className="min-w-full text-left text-sm">
              <thead className="text-xs uppercase tracking-[0.12em] text-slate-500">
                <tr>
                  {["Date", "Direction", "Statut", "Mission", "Envoyes", "Acceptes", "Conflits", "Telecharges", "Duree"].map((label) => (
                    <th key={label} className="px-3 py-3 font-black">{label}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {central.runs.map((run) => (
                  <tr key={run.uuid} className="border-t border-slate-200">
                    <td className="px-3 py-3 text-slate-600">{formatDateTime(run.started_at)}</td>
                    <td className="px-3 py-3 text-slate-600">
                      {run.direction === "mission_to_central_push"
                        ? "Mission vers central"
                        : run.direction === "central_to_mobile_pull"
                          ? "Central vers poste"
                          : "Bootstrap"}
                    </td>
                    <td className="px-3 py-3"><Badge tone={run.status.includes("failed") ? "failed" : run.status.includes("conflict") ? "pending" : "active"}>{run.status}</Badge></td>
                    <td className="px-3 py-3 text-slate-600">{shortId(run.mission_uuid)}</td>
                    <td className="px-3 py-3 text-slate-600">{run.counts.sent}</td>
                    <td className="px-3 py-3 text-slate-600">{run.counts.accepted}</td>
                    <td className="px-3 py-3 text-slate-600">{run.counts.conflicts}</td>
                    <td className="px-3 py-3 text-slate-600">{run.counts.pulled}</td>
                    <td className="px-3 py-3 text-slate-600">{run.duration_ms ? `${Math.round(run.duration_ms / 1000)} s` : "-"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>

        <Card className="rounded-[1.75rem] p-6">
          <div className="flex items-start justify-between gap-4">
            <div>
              <p className="text-xs font-black uppercase tracking-[0.16em] text-[#0085A3]">Chronologie infrastructure</p>
              <h2 className="mt-2 text-2xl font-black text-slate-950">Historique oriente audit</h2>
            </div>
            <Activity className="h-5 w-5 text-slate-400" />
          </div>
          <div className="mt-5 space-y-3">
            {central.timeline.map((event) => (
              <div key={event.id} className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-4">
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <p className="text-sm font-bold text-slate-950">{event.title}</p>
                    <p className="mt-1 text-sm text-slate-600">{event.description}</p>
                    <p className="mt-2 text-xs text-slate-500">{formatDateTime(event.occurred_at)}</p>
                  </div>
                  <Badge tone={event.tone}>{event.type}</Badge>
                </div>
              </div>
            ))}
          </div>
        </Card>
      </section>

      <Modal open={Boolean(central.pendingIdentity)} title="Generation du serveur central differente" onClose={() => undefined}>
        <div className="space-y-4">
          <div className="rounded-2xl border border-rose-200 bg-rose-50 px-4 py-4 text-sm leading-6 text-rose-900">
            Le serveur central detecte ne correspond pas a l'identite deja approuvee. La centralisation reste bloquee tant qu'une verification explicite n'a pas ete effectuee.
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
              <p className="text-xs font-black uppercase tracking-[0.14em] text-slate-500">Identite approuvee</p>
              <p className="mt-2 text-sm font-bold text-slate-950">{shortId(central.storedIdentity?.serverUuid)}</p>
              <p className="mt-1 text-xs text-slate-500">{shortId(central.storedIdentity?.generationUuid)}</p>
            </div>
            <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
              <p className="text-xs font-black uppercase tracking-[0.14em] text-slate-500">Identite detectee</p>
              <p className="mt-2 text-sm font-bold text-slate-950">{shortId(central.pendingIdentity?.serverUuid)}</p>
              <p className="mt-1 text-xs text-slate-500">{shortId(central.pendingIdentity?.generationUuid)}</p>
            </div>
          </div>
          <div className="flex justify-end gap-2">
            <Button variant="secondary" onClick={() => central.setServerUrl("")}>Annuler</Button>
            <Button disabled={!canAcceptGeneration} onClick={() => central.verifyServerIdentity()}>
              Accepter cette nouvelle generation
            </Button>
          </div>
        </div>
      </Modal>

      <Modal open={Boolean(selectedConflict)} title="Detail du conflit central" onClose={() => setSelectedConflict(null)}>
        <div className="space-y-4">
          <div className="grid gap-3 sm:grid-cols-2">
            {selectedConflict
              ? [
                  ["Entite", entityLabelMap[selectedConflict.entity_type] || selectedConflict.entity_type],
                  ["Mission", shortId(selectedConflict.mission_uuid)],
                  ["Appareil source", shortId(selectedConflict.source_device_uuid)],
                  ["Utilisateur source", shortId(selectedConflict.source_user_uuid)],
                  ["Version centrale", String(selectedConflict.central_version ?? "-")],
                  ["Version mission", String(selectedConflict.base_version ?? "-")],
                  ["Champs en conflit", selectedConflict.conflicting_fields.join(", ") || "-"],
                  ["Etat", selectedConflict.status],
                ].map(([label, value]) => (
                  <div key={label} className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                    <p className="text-[11px] font-black uppercase tracking-[0.14em] text-slate-500">{label}</p>
                    <p className="mt-2 break-all text-sm font-bold text-slate-950">{value}</p>
                  </div>
                ))
              : null}
          </div>

          {currentConflictImmutable ? (
            <div className="rounded-2xl border border-amber-200 bg-amber-50 px-4 py-4 text-sm leading-6 text-amber-900">
              Cet enregistrement medical valide ou signe est immuable. L'ecrasement direct de la version centrale n'est pas propose; privilegiez une revision ou une fusion manuelle documentee.
            </div>
          ) : null}

          <div className="grid gap-3">
            {resolutionOptions.map((option) => (
              <label key={option.value} className={`flex items-start gap-3 rounded-2xl border px-4 py-4 ${resolutionType === option.value ? "border-[#0085A3] bg-sky-50" : "border-slate-200 bg-slate-50"} ${option.disabled ? "opacity-50" : ""}`}>
                <input
                  type="radio"
                  name="resolutionType"
                  checked={resolutionType === option.value}
                  disabled={option.disabled}
                  onChange={() => setResolutionType(option.value)}
                  className="mt-1"
                />
                <span className="text-sm font-semibold text-slate-800">{option.label}</span>
              </label>
            ))}
          </div>

          {(resolutionType === "manual_merge" || resolutionType === "create_revision" || resolutionType === "accept_mission") ? (
            <label className="block">
              <span className="text-xs font-black uppercase tracking-[0.14em] text-slate-500">Motif de resolution</span>
              <textarea
                value={resolutionReason}
                onChange={(event) => setResolutionReason(event.target.value)}
                rows={3}
                className="mt-2 w-full rounded-2xl border border-slate-200 bg-white px-3 py-3 text-sm text-slate-900 outline-none focus:border-[#0085A3]"
                placeholder="Expliquez la decision prise."
              />
            </label>
          ) : null}

          {resolutionType === "manual_merge" ? (
            <label className="block">
              <span className="text-xs font-black uppercase tracking-[0.14em] text-slate-500">Payload fusionne (JSON)</span>
              <textarea
                value={manualPayload}
                onChange={(event) => setManualPayload(event.target.value)}
                rows={8}
                className="mt-2 w-full rounded-2xl border border-slate-200 bg-slate-950 px-3 py-3 text-sm text-slate-100 outline-none focus:border-[#0085A3]"
                placeholder='{"notes": "..."}'
              />
            </label>
          ) : null}

          {canViewTechnical && selectedConflict ? (
            <details className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
              <summary className="cursor-pointer text-sm font-bold text-slate-900">Details techniques</summary>
              <div className="mt-4 grid gap-3 lg:grid-cols-2">
                <pre className="overflow-auto rounded-2xl bg-slate-950 p-4 text-xs text-slate-100">
                  {JSON.stringify(selectedConflict.central_snapshot || {}, null, 2)}
                </pre>
                <pre className="overflow-auto rounded-2xl bg-slate-950 p-4 text-xs text-slate-100">
                  {JSON.stringify(selectedConflict.mission_snapshot || {}, null, 2)}
                </pre>
              </div>
            </details>
          ) : null}

          <div className="flex justify-end gap-2">
            <Button variant="secondary" onClick={() => setSelectedConflict(null)}>Fermer</Button>
            <Button
              disabled={
                !(isMedicalConflict(selectedConflict?.entity_type || "") ? canResolveMedical : canResolveAdministrative) ||
                (["accept_mission", "manual_merge", "create_revision"].includes(resolutionType) && !resolutionReason.trim()) ||
                (resolutionType === "manual_merge" && !manualPayload.trim())
              }
              loading={busyAction === `resolve:${selectedConflict?.uuid}`}
              onClick={() => void handleResolveConflict()}
            >
              Appliquer la resolution
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
};
