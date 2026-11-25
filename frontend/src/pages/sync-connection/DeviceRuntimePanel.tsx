import { useEffect, useMemo, useState } from "react";
import {
  CheckCircle2,
  Clipboard,
  Edit3,
  Laptop2,
  Link2,
  LoaderCircle,
  MonitorSmartphone,
  QrCode,
  RefreshCw,
  Server,
  ShieldAlert,
  ShieldCheck,
} from "lucide-react";

import { Badge } from "@/components/common/Badge";
import { Button } from "@/components/common/Button";
import { Card } from "@/components/common/Card";
import { Input } from "@/components/common/Input";
import { Modal } from "@/components/common/Modal";
import { useMissionRuntime } from "@/hooks/useMissionRuntime";
import type { AuthUser } from "@/types/auth";
import type { MissionServerInfo } from "@/types/mission";
import { hasPermission } from "@/utils/permissions";

type WizardStep = 1 | 2 | 3 | 4 | 5;

const formatDateTime = (value: string | null | undefined) => {
  if (!value) return "-";
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? value
    : new Intl.DateTimeFormat("fr-FR", { dateStyle: "short", timeStyle: "short" }).format(date);
};

const modeMeta = {
  standalone: {
    title: "Mode autonome",
    description: "Ce poste travaille sur sa base PostgreSQL locale.",
    badge: "active",
    icon: ShieldCheck,
  },
  mission_server: {
    title: "Serveur de mission",
    description: "Les appareils de la mission travaillent actuellement sur la base de ce poste.",
    badge: "reviewed",
    icon: Server,
  },
  mission_client: {
    title: "Client de mission",
    description: "Ce poste utilise actuellement la base du serveur de mission. La base locale n'est pas utilisee pour les ecritures pendant la mission.",
    badge: "pending",
    icon: Laptop2,
  },
} as const;

const buildSuggestedMissionCode = () => {
  const now = new Date();
  const date = now.toISOString().slice(0, 10);
  return `MISSION-HMD-${date}`;
};

export const DeviceRuntimePanel = ({
  user,
  serverUrl,
  onServerUrlChange,
  onModeHintChange,
}: {
  user: AuthUser | null;
  serverUrl: string;
  onServerUrlChange: (value: string) => void;
  onModeHintChange?: (value: "server" | "client") => void;
}) => {
  const {
    runtime,
    loading,
    error,
    refresh,
    createMissionServer,
    joinMissionClient,
    switchToStandalone,
    testMissionServer,
    finalizeMission,
    getCurrentMission,
    updateCurrentDevice,
  } = useMissionRuntime();

  const [editingName, setEditingName] = useState(false);
  const [deviceNameDraft, setDeviceNameDraft] = useState(runtime.device?.device_name || "");
  const [savingName, setSavingName] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);

  const [createWizardOpen, setCreateWizardOpen] = useState(false);
  const [createStep, setCreateStep] = useState<WizardStep>(1);
  const [creatingMission, setCreatingMission] = useState(false);
  const [missionCode, setMissionCode] = useState(buildSuggestedMissionCode());
  const [missionName, setMissionName] = useState("Mission Hassi Messaoud");
  const [missionDescription, setMissionDescription] = useState("");
  const [createdMissionUuid, setCreatedMissionUuid] = useState<string | null>(null);

  const [joinWizardOpen, setJoinWizardOpen] = useState(false);
  const [joinStep, setJoinStep] = useState<1 | 2 | 3 | 4>(1);
  const [joinAddress, setJoinAddress] = useState(serverUrl);
  const [joinLoading, setJoinLoading] = useState(false);
  const [joinServerInfo, setJoinServerInfo] = useState<MissionServerInfo | null>(null);

  const canRenameDevice = hasPermission(user, "settings:manage") || ["Admin", "Super Admin"].includes(user?.role || "");
  const canStartMission = ["Admin", "Super Admin"].includes(user?.role || "");
  const canFinalizeMission = ["Admin", "Super Admin"].includes(user?.role || "");
  const canJoinMission = Boolean(user);

  const currentMode = modeMeta[runtime.runtimeMode];
  const CurrentModeIcon = currentMode.icon;

  useEffect(() => {
    setDeviceNameDraft(runtime.device?.device_name || "");
  }, [runtime.device?.device_name]);

  useEffect(() => {
    setJoinAddress(serverUrl);
  }, [serverUrl]);

  const readinessChecks = useMemo(
    () => [
      {
        label: "Identite de l'appareil valide",
        status: runtime.device?.device_uuid ? "success" : "failure",
      },
      {
        label: "Base PostgreSQL operationnelle",
        status: runtime.device?.database_health === "ok" ? "success" : "warning",
      },
      {
        label: "Backend local operationnel",
        status: error ? "warning" : "success",
      },
      {
        label: "Schema a jour",
        status: runtime.device?.schema_revision ? "success" : "warning",
      },
      {
        label: "Aucune mission active",
        status: runtime.runtimeMode === "standalone" ? "success" : "failure",
      },
      {
        label: "Donnees centrales de reference disponibles",
        status: runtime.device?.device_uuid ? "warning" : "failure",
      },
    ],
    [error, runtime],
  );

  const connectionTone =
    runtime.connectionState === "connected"
      ? "active"
      : runtime.connectionState === "disconnected"
        ? "failed"
        : "pending";

  const handleCopy = async (value: string | null | undefined, label: string) => {
    if (!value) return;
    try {
      await navigator.clipboard.writeText(value);
      setNotice(`${label} copie.`);
    } catch {
      setNotice(`Impossible de copier ${label.toLowerCase()}.`);
    }
  };

  const handleSaveDeviceName = async () => {
    setSavingName(true);
    setNotice(null);
    try {
      await updateCurrentDevice({ device_name: deviceNameDraft.trim() });
      setEditingName(false);
      setNotice("Nom de l'appareil mis a jour.");
      await refresh();
    } catch (nextError) {
      setNotice(nextError instanceof Error ? nextError.message : "Mise a jour indisponible.");
    } finally {
      setSavingName(false);
    }
  };

  const handleCreateMission = async () => {
    setCreatingMission(true);
    setNotice(null);
    try {
      const created = await createMissionServer({
        mission_code: missionCode,
        mission_name: missionName,
        description: missionDescription || null,
        expected_devices: [],
      });
      setCreatedMissionUuid(created.uuid);
      onModeHintChange?.("server");
      setCreateStep(5);
      setNotice("Mission active.");
    } catch (nextError) {
      setNotice(nextError instanceof Error ? nextError.message : "Impossible de creer la mission.");
    } finally {
      setCreatingMission(false);
    }
  };

  const handleTestMissionServer = async () => {
    setJoinLoading(true);
    setNotice(null);
    try {
      const result = await testMissionServer(joinAddress);
      setJoinServerInfo(result.serverInfo);
      onServerUrlChange(result.baseUrl);
      setJoinAddress(result.baseUrl);
      setJoinStep(2);
    } catch (nextError) {
      setNotice(nextError instanceof Error ? nextError.message : "Serveur inaccessible.");
    } finally {
      setJoinLoading(false);
    }
  };

  const handleJoinMission = async () => {
    if (!joinServerInfo?.active_mission || !runtime.device) return;
    setJoinLoading(true);
    setNotice(null);
    try {
      await joinMissionClient({
        baseUrl: joinAddress,
        missionUuid: joinServerInfo.active_mission.uuid,
        joinPayload: {
          device_uuid: runtime.device.device_uuid || "",
          device_code: runtime.device.device_code || "",
          device_name: runtime.device.device_name || "",
          installation_uuid: runtime.device.device_uuid || "",
          app_version: runtime.device.app_version,
          schema_revision: runtime.device.schema_revision,
          last_central_sequence: joinServerInfo.active_mission.base_central_sequence,
          protocol_version: "1",
        },
      });
      onModeHintChange?.("client");
      onServerUrlChange(joinAddress);
      setJoinStep(4);
      setNotice("Mission rejointe.");
    } catch (nextError) {
      setNotice(nextError instanceof Error ? nextError.message : "Impossible de rejoindre la mission.");
    } finally {
      setJoinLoading(false);
    }
  };

  const handleReturnToStandalone = async () => {
    try {
      await switchToStandalone(false);
      onModeHintChange?.("server");
      setNotice("Retour au mode autonome.");
    } catch (nextError) {
      setNotice(nextError instanceof Error ? nextError.message : "Retour au mode autonome refuse.");
    }
  };

  return (
    <>
      <section className="space-y-6">
        <Card className="rounded-[1.75rem] border-slate-200 bg-white p-6">
          <div className="flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
            <div>
              <p className="text-xs font-black uppercase tracking-[0.16em] text-[#0085A3]">
                Identite et mode de fonctionnement de l'appareil
              </p>
              <h2 className="mt-2 text-2xl font-black text-slate-950">Infrastructure de mission</h2>
              <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-500">
                Identite permanente du poste, mode d'execution actif et actions de mission.
              </p>
            </div>

            <div className="flex items-center gap-2">
              <Badge tone={currentMode.badge}>{currentMode.title}</Badge>
              <Badge tone={connectionTone}>{runtime.connectionState}</Badge>
              <Button variant="ghost" icon={RefreshCw} loading={loading} onClick={() => void refresh()}>
                Actualiser
              </Button>
            </div>
          </div>

          <div className="mt-6 grid gap-6 xl:grid-cols-[1.05fr_0.95fr]">
            <div className="rounded-3xl border border-slate-200 bg-slate-50/70 p-5">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <p className="text-[11px] font-black uppercase tracking-[0.14em] text-slate-500">Identite de l'appareil</p>
                  <h3 className="mt-2 text-xl font-black text-slate-950">Carte de l'appareil</h3>
                </div>
                <div className="rounded-2xl bg-white p-3 text-sky-700">
                  <MonitorSmartphone className="h-5 w-5" />
                </div>
              </div>

              <div className="mt-5 grid gap-3 sm:grid-cols-2">
                {[
                  ["Nom de l'appareil", runtime.device?.device_name || "-"],
                  ["Code de l'appareil", runtime.device?.device_code || "-"],
                  ["UUID de l'appareil", runtime.device?.device_uuid || "-"],
                  ["Nom Windows / hostname", runtime.device?.device_name || "-"],
                  ["Version de l'application", runtime.device?.app_version || "-"],
                  ["Revision de la base", runtime.device?.schema_revision || "-"],
                  ["Derniere activite", formatDateTime(runtime.device?.server_time)],
                ].map(([label, value]) => (
                  <div key={label} className="rounded-2xl border border-slate-200 bg-white p-4">
                    <p className="text-[11px] font-black uppercase tracking-[0.14em] text-slate-500">{label}</p>
                    <p className="mt-2 break-all text-sm font-bold text-slate-950">{value}</p>
                  </div>
                ))}
              </div>

              <div className="mt-4 flex flex-wrap gap-2">
                {canRenameDevice ? (
                  <Button variant="secondary" icon={Edit3} onClick={() => setEditingName(true)}>
                    Modifier le nom
                  </Button>
                ) : null}
                <Button variant="ghost" icon={Clipboard} onClick={() => void handleCopy(runtime.device?.device_code, "Code")}>
                  Copier le code
                </Button>
                <Button variant="ghost" icon={Clipboard} onClick={() => void handleCopy(runtime.device?.device_uuid, "UUID")}>
                  Copier l'UUID
                </Button>
              </div>
            </div>

            <div className="space-y-4">
              <div className="rounded-3xl border border-slate-200 bg-slate-950 p-5 text-white">
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <p className="text-[11px] font-black uppercase tracking-[0.14em] text-slate-400">Mode actuel</p>
                    <h3 className="mt-2 text-2xl font-black">{currentMode.title}</h3>
                    <p className="mt-2 text-sm leading-6 text-slate-300">{currentMode.description}</p>
                  </div>
                  <div className="rounded-2xl bg-white/10 p-3 text-sky-300">
                    <CurrentModeIcon className="h-5 w-5" />
                  </div>
                </div>

                <div className="mt-5 grid gap-3 sm:grid-cols-2">
                  {[
                    ["Source API active", runtime.activeApiSource],
                    ["Ecritures base locale", runtime.localDatabaseWriteEnabled ? "Activees" : "Desactivees"],
                    ["Mission active", runtime.activeMission?.code || "Aucune"],
                    ["Serveur de mission", runtime.missionServerName || "-"],
                  ].map(([label, value]) => (
                    <div key={label} className="rounded-2xl border border-white/10 bg-white/5 p-4">
                      <p className="text-[11px] font-black uppercase tracking-[0.14em] text-slate-400">{label}</p>
                      <p className="mt-2 break-all text-sm font-bold text-white">{value}</p>
                    </div>
                  ))}
                </div>
              </div>

              <div className="rounded-3xl border border-slate-200 bg-white p-5">
                <p className="text-[11px] font-black uppercase tracking-[0.14em] text-slate-500">Actions de mode</p>
                <div className="mt-4 flex flex-wrap gap-2">
                  {runtime.runtimeMode === "standalone" ? (
                    <>
                      <Button disabled={!canStartMission} icon={Server} onClick={() => setCreateWizardOpen(true)}>
                        Creer une mission et devenir serveur
                      </Button>
                      <Button variant="secondary" disabled={!canJoinMission} icon={Link2} onClick={() => setJoinWizardOpen(true)}>
                        Rejoindre une mission comme client
                      </Button>
                    </>
                  ) : null}

                  {runtime.runtimeMode === "mission_server" ? (
                    <>
                      <Button variant="secondary" icon={RefreshCw} onClick={() => void getCurrentMission()}>
                        Afficher la mission
                      </Button>
                      <Button
                        disabled={!canFinalizeMission || !runtime.activeMission}
                        icon={CheckCircle2}
                        onClick={() => {
                          if (!runtime.activeMission) return;
                          void finalizeMission(runtime.activeMission.uuid);
                        }}
                      >
                        Finaliser la mission
                      </Button>
                    </>
                  ) : null}

                  {runtime.runtimeMode === "mission_client" ? (
                    <>
                      <Button variant="secondary" icon={RefreshCw} onClick={() => void refresh()}>
                        Tester la connexion
                      </Button>
                      <Button variant="secondary" icon={Server} onClick={() => setJoinWizardOpen(true)}>
                        Afficher la mission
                      </Button>
                      <Button icon={ShieldAlert} onClick={() => void handleReturnToStandalone()}>
                        Retourner au mode autonome
                      </Button>
                    </>
                  ) : null}
                </div>
              </div>
            </div>
          </div>

          {notice ? (
            <div className="mt-4 rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm font-semibold text-slate-700">
              {notice}
            </div>
          ) : null}
        </Card>
      </section>

      <Modal open={editingName} title="Modifier le nom de l'appareil" onClose={() => setEditingName(false)}>
        <div className="space-y-4">
          <Input label="Nom de l'appareil" value={deviceNameDraft} onChange={(event) => setDeviceNameDraft(event.target.value)} />
          <div className="flex justify-end gap-3">
            <Button variant="secondary" onClick={() => setEditingName(false)}>Annuler</Button>
            <Button loading={savingName} onClick={() => void handleSaveDeviceName()}>Enregistrer</Button>
          </div>
        </div>
      </Modal>

      <Modal open={createWizardOpen} title="Creer une mission" onClose={() => setCreateWizardOpen(false)}>
        <div className="space-y-5">
          <div className="flex flex-wrap gap-2">
            {[1, 2, 3, 4, 5].map((step) => (
              <Badge key={step} tone={createStep === step ? "reviewed" : createStep > step ? "active" : "inactive"}>
                Etape {step}
              </Badge>
            ))}
          </div>

          {createStep === 1 ? (
            <div className="space-y-4">
              <Input label="Code de mission" value={missionCode} onChange={(event) => setMissionCode(event.target.value)} />
              <Input label="Nom de mission" value={missionName} onChange={(event) => setMissionName(event.target.value)} />
              <Input label="Description" value={missionDescription} onChange={(event) => setMissionDescription(event.target.value)} />
            </div>
          ) : null}

          {createStep === 2 ? (
            <div className="space-y-3">
              {readinessChecks.map((item) => (
                <div key={item.label} className="flex items-center justify-between rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3">
                  <span className="text-sm font-semibold text-slate-800">{item.label}</span>
                  <Badge tone={item.status === "success" ? "active" : item.status === "warning" ? "pending" : "failed"}>
                    {item.status === "success" ? "Reussi" : item.status === "warning" ? "Avertissement" : "Echec"}
                  </Badge>
                </div>
              ))}
            </div>
          ) : null}

          {createStep === 3 ? (
            <div className="grid gap-3 sm:grid-cols-2">
              {[
                ["URL du serveur local", runtime.activeApiSource],
                ["Adresse LAN", serverUrl || "http://localhost:8000"],
                ["Port API", "8000"],
                ["Etat reseau", runtime.connectionState],
              ].map(([label, value]) => (
                <div key={label} className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                  <p className="text-[11px] font-black uppercase tracking-[0.14em] text-slate-500">{label}</p>
                  <p className="mt-2 break-all text-sm font-bold text-slate-950">{value}</p>
                </div>
              ))}
            </div>
          ) : null}

          {createStep === 4 ? (
            <div className="rounded-2xl border border-amber-200 bg-amber-50 px-4 py-4 text-sm leading-6 text-amber-900">
              Pendant la mission, tous les appareils clients utiliseront la base PostgreSQL de ce poste.
            </div>
          ) : null}

          {createStep === 5 ? (
            <div className="space-y-4">
              <div className="rounded-2xl border border-emerald-200 bg-emerald-50 px-4 py-4">
                <p className="text-sm font-bold text-emerald-950">Mission active</p>
                <p className="mt-1 text-sm text-emerald-800">Serveur: {runtime.device?.device_code || "PC-01"}</p>
                <p className="mt-1 text-sm text-emerald-800">Adresse: {runtime.activeApiSource}</p>
              </div>
              <div className="flex flex-wrap gap-2">
                <Button variant="secondary" icon={Clipboard} onClick={() => void handleCopy(runtime.activeApiSource, "Adresse")}>
                  Copier l'adresse
                </Button>
                <Button variant="ghost" icon={QrCode} disabled>
                  QR code
                </Button>
              </div>
            </div>
          ) : null}

          <div className="flex justify-between gap-3">
            <Button variant="secondary" onClick={() => setCreateWizardOpen(false)}>Fermer</Button>
            <div className="flex gap-2">
              {createStep > 1 && createStep < 5 ? (
                <Button variant="ghost" onClick={() => setCreateStep((Math.max(1, createStep - 1) as WizardStep))}>
                  Retour
                </Button>
              ) : null}
              {createStep < 4 ? (
                <Button onClick={() => setCreateStep((createStep + 1) as WizardStep)}>Continuer</Button>
              ) : null}
              {createStep === 4 ? (
                <Button loading={creatingMission} onClick={() => void handleCreateMission()}>
                  Confirmer
                </Button>
              ) : null}
              {createStep === 5 && createdMissionUuid ? (
                <Button onClick={() => setCreateWizardOpen(false)}>Terminer</Button>
              ) : null}
            </div>
          </div>
        </div>
      </Modal>

      <Modal open={joinWizardOpen} title="Rejoindre une mission" onClose={() => setJoinWizardOpen(false)}>
        <div className="space-y-5">
          <div className="flex flex-wrap gap-2">
            {[1, 2, 3, 4].map((step) => (
              <Badge key={step} tone={joinStep === step ? "reviewed" : joinStep > step ? "active" : "inactive"}>
                Etape {step}
              </Badge>
            ))}
          </div>

          {joinStep === 1 ? (
            <div className="space-y-4">
              <Input label="Adresse du serveur de mission" value={joinAddress} onChange={(event) => setJoinAddress(event.target.value)} placeholder="http://192.168.1.10:8000" />
              <Button loading={joinLoading} icon={RefreshCw} onClick={() => void handleTestMissionServer()}>
                Tester la connexion
              </Button>
            </div>
          ) : null}

          {joinStep === 2 ? (
            <div className="grid gap-3 sm:grid-cols-2">
              {[
                ["Code serveur", joinServerInfo?.device_code || "-"],
                ["Nom serveur", joinServerInfo?.device_name || "-"],
                ["Nom mission", joinServerInfo?.active_mission?.name || "-"],
                ["Mission UUID", joinServerInfo?.active_mission?.uuid?.slice(0, 12) || "-"],
                ["Statut mission", joinServerInfo?.active_mission?.status || "-"],
                ["Revision schema", joinServerInfo?.schema_revision || "-"],
                ["Version protocole", joinServerInfo?.protocol_version || "-"],
                ["Sequence centrale de base", String(joinServerInfo?.active_mission?.base_central_sequence ?? "-")],
              ].map(([label, value]) => (
                <div key={label} className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                  <p className="text-[11px] font-black uppercase tracking-[0.14em] text-slate-500">{label}</p>
                  <p className="mt-2 break-all text-sm font-bold text-slate-950">{value}</p>
                </div>
              ))}
            </div>
          ) : null}

          {joinStep === 3 ? (
            <div className="rounded-2xl border border-amber-200 bg-amber-50 px-4 py-4 text-sm leading-6 text-amber-900">
              Pendant le mode client, cette application utilisera la base du serveur de mission. Les ecritures dans la base locale seront desactivees.
            </div>
          ) : null}

          {joinStep === 4 ? (
            <div className="rounded-2xl border border-emerald-200 bg-emerald-50 px-4 py-4 text-sm leading-6 text-emerald-900">
              Mission rejointe. Le contexte applicatif utilisera maintenant l'API du serveur de mission.
            </div>
          ) : null}

          <div className="flex justify-between gap-3">
            <Button variant="secondary" onClick={() => setJoinWizardOpen(false)}>Fermer</Button>
            <div className="flex gap-2">
              {joinStep > 1 && joinStep < 4 ? (
                <Button variant="ghost" onClick={() => setJoinStep((joinStep - 1) as 1 | 2 | 3 | 4)}>Retour</Button>
              ) : null}
              {joinStep === 2 ? <Button onClick={() => setJoinStep(3)}>Continuer</Button> : null}
              {joinStep === 3 ? (
                <Button loading={joinLoading} onClick={() => void handleJoinMission()}>
                  Rejoindre la mission
                </Button>
              ) : null}
            </div>
          </div>
        </div>
      </Modal>
    </>
  );
};
