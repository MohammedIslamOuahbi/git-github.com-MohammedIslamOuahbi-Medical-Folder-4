import { useMemo, useState } from "react";
import { Clipboard, Database, FolderOpen, HeartPulse, RotateCcw, ShieldAlert } from "lucide-react";

import apiClient from "@/api/axios";
import { Button } from "@/components/common/Button";
import { Card } from "@/components/common/Card";
import { env } from "@/config/env";
import { getTauriInvoke } from "@/config/runtime";
import { buildDiagnosticsSnapshot, buildRecoveryActions, redactDiagnosticEntries } from "@/features/installation/profileInfrastructure";
import { useInstallationProfile } from "@/hooks/useInstallationProfile";

type TauriInspection = {
  runtime_config_path?: string;
  psql_path?: string | null;
  service_status?: string | null;
  local_ip_address?: string | null;
  message?: string | null;
};

export const InstallerDiagnosticsPage = () => {
  const { profile, installationStatus, provisioningStatus } = useInstallationProfile();
  const [inspection, setInspection] = useState<TauriInspection | null>(null);
  const [actionMessage, setActionMessage] = useState<string | null>(null);

  const logPaths = useMemo(
    () =>
      profile === "central_server"
        ? ["backend/.runtime/logs/central-provisioning.log", "backend/.runtime/logs/upgrade.log"]
        : ["backend/.runtime/logs/mobile-provisioning.log", "backend/.runtime/logs/upgrade.log"],
    [profile],
  );

  const diagnostics = redactDiagnosticEntries(
    buildDiagnosticsSnapshot({
      profile,
      status: installationStatus,
      sidecarPath: "frontend/src-tauri/target/release/medical-backend-sidecar.exe",
      backendEnvPath: "backend/.runtime/backend.env",
      databaseHost: installationStatus?.network.lan_ip || "localhost",
      databaseName: installationStatus?.identity.server_code || "medical_folder",
      port: String(installationStatus?.identity.api_port || 8000),
      health: installationStatus?.network.health_status || null,
      logPaths,
      migrationRevision: env.schemaRevision,
    }),
  );

  const recoveryActions = buildRecoveryActions(profile, provisioningStatus);

  const handleCopy = async () => {
    await navigator.clipboard.writeText(JSON.stringify(diagnostics, null, 2));
    setActionMessage("Diagnostic copié dans le presse-papiers.");
  };

  const handleOpenLogs = async () => {
    await navigator.clipboard.writeText(logPaths.join("\n"));
    setActionMessage("Chemins des journaux copiés.");
  };

  const handleVerifyPostgres = async () => {
    const invoke = getTauriInvoke();
    if (!invoke) {
      setActionMessage("Inspection PostgreSQL disponible dans l’application desktop.");
      return;
    }
    const result = await invoke<TauriInspection>("inspect_postgres_installation");
    setInspection(result);
    setActionMessage(result.message || "Inspection PostgreSQL terminée.");
  };

  const handleRestartBackend = async () => {
    const invoke = getTauriInvoke();
    if (!invoke) {
      setActionMessage("Redémarrage backend disponible dans l’application desktop.");
      return;
    }
    try {
      await invoke("stop_backend_sidecar");
    } catch {
      // Ignore stop failures and attempt a start.
    }
    await invoke("start_backend_sidecar");
    setActionMessage("Backend redémarré.");
  };

  const handleVerifyIntegrity = async () => {
    try {
      const result = await apiClient.get("/system/data-integrity");
      setActionMessage(`Vérification d’intégrité terminée: ${JSON.stringify(result.data).slice(0, 180)}...`);
    } catch {
      setActionMessage("Vérification d’intégrité indisponible pour ce profil ou cet utilisateur.");
    }
  };

  return (
    <div className="space-y-6">
      <Card className="rounded-[2rem] p-6">
        <h1 className="text-3xl font-black text-slate-950">Diagnostics installateur</h1>
        <p className="mt-3 text-sm text-slate-600">
          Détails techniques sûrs pour le support. Les secrets sont masqués automatiquement.
        </p>
      </Card>

      <Card className="rounded-[2rem] p-6">
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {Object.entries(diagnostics).map(([key, value]) => (
            <div key={key} className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3">
              <p className="text-xs font-bold uppercase tracking-[0.16em] text-slate-500">{key.replace(/_/g, " ")}</p>
              <p className="mt-2 break-all text-sm font-semibold text-slate-900">
                {Array.isArray(value) ? value.join(" · ") : String(value ?? "-")}
              </p>
            </div>
          ))}
        </div>
      </Card>

      <Card className="rounded-[2rem] p-6">
        <div className="flex flex-wrap gap-3">
          <Button type="button" variant="secondary" icon={Clipboard} onClick={() => void handleCopy()}>
            Copier le diagnostic
          </Button>
          <Button type="button" variant="secondary" icon={FolderOpen} onClick={() => void handleOpenLogs()}>
            Ouvrir le dossier des journaux
          </Button>
          <Button type="button" icon={RotateCcw} onClick={() => void handleRestartBackend()}>
            Redémarrer le backend
          </Button>
          <Button type="button" variant="secondary" icon={Database} onClick={() => void handleVerifyPostgres()}>
            Vérifier PostgreSQL
          </Button>
          <Button type="button" variant="secondary" icon={HeartPulse} onClick={() => void handleVerifyIntegrity()}>
            Vérifier l’intégrité
          </Button>
        </div>
        {actionMessage ? <p className="mt-4 text-sm text-slate-600">{actionMessage}</p> : null}
        {inspection ? (
          <div className="mt-4 rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-700">
            <p className="font-semibold text-slate-900">PostgreSQL</p>
            <p className="mt-2">PSQL: {inspection.psql_path || "-"}</p>
            <p>Service: {inspection.service_status || "-"}</p>
            <p>LAN: {inspection.local_ip_address || "-"}</p>
          </div>
        ) : null}
      </Card>

      <Card className="rounded-[2rem] p-6">
        <div className="flex items-start gap-3">
          <ShieldAlert className="mt-0.5 h-5 w-5 text-amber-600" />
          <div>
            <h2 className="text-xl font-black text-slate-950">Récupération</h2>
            <div className="mt-4 space-y-3">
              {recoveryActions.map((action) => (
                <div key={action.key} className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3">
                  <p className="text-sm font-semibold text-slate-900">{action.label}</p>
                  <p className="mt-1 text-sm text-slate-600">{action.description}</p>
                </div>
              ))}
            </div>
          </div>
        </div>
      </Card>
    </div>
  );
};
