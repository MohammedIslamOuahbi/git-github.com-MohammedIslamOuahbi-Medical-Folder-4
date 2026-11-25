import { useEffect, useMemo, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import {
  AlertTriangle,
  ArrowRightLeft,
  Cable,
  ChevronDown,
  ChevronUp,
  Database,
  Monitor,
  MonitorUp,
  Network,
  Server,
  ShieldCheck,
} from "lucide-react";

import { Button } from "@/components/common/Button";
import { Card } from "@/components/common/Card";
import { Input } from "@/components/common/Input";
import { CentralServerSetupPage } from "@/pages/central/CentralServerSetupPage";
import { MobileDeviceSetupPage } from "@/pages/mobile/MobileDeviceSetupPage";
import { DesktopDeploymentGate } from "@/components/system/DesktopDeploymentGate";
import {
  detectTauriRuntime,
  getStoredServerUrl,
  getStoredSetupCompleted,
  connectionModeToOperationMode,
  readStoredConnectionMode,
  readStoredOperationMode,
  setStoredConnectionMode,
  LOCAL_SERVER_API_BASE_URL,
  LOCAL_SERVER_ROOT_URL,
  type ConnectionMode,
  type OperationMode,
} from "@/config/runtime";
import { useInstallationProfile } from "@/hooks/useInstallationProfile";
import { useRuntimeConnection } from "@/hooks/useRuntimeConnection";
import {
  BROWSER_SERVER_START_COMMANDS,
  buildBrowserStatusPanel,
  canProvisionServer,
  getStatusLabel,
  isLocalhostHostname,
  resolveSetupConnectionPolicy,
  resolveRuntimePlatform,
  shouldRequireModeChangeConfirmation,
  type SetupValidationState,
} from "@/pages/auth/setupFlow";

const modeCardClassName =
  "rounded-xl border px-4 py-4 text-left transition-colors focus:outline-none focus:ring-2 focus:ring-[#0085A3]/20";
const selectedModeCardClassName = "border-[#0085A3] bg-[#0085A3]/5";
const idleModeCardClassName = "border-slate-200 bg-white hover:border-slate-300";
type ValidationSnapshot = {
  serverRoot: string;
  apiBaseUrl: string;
};

const emptyValidationSnapshot = (serverRoot: string, apiBaseUrl: string): ValidationSnapshot => ({
  serverRoot,
  apiBaseUrl,
});

const mapValidationResultToState = ({
  success,
  healthOk,
  databaseOk,
}: {
  success: boolean;
  healthOk?: boolean;
  databaseOk?: boolean;
}): SetupValidationState => {
  if (success) {
    return "connected";
  }
  if (healthOk && !databaseOk) {
    return "database_unavailable";
  }
  return "api_unavailable";
};

const SetupForm = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const runtimeConnection = useRuntimeConnection();
  const isTauri = detectTauriRuntime();
  const runtimePlatform = resolveRuntimePlatform(isTauri);
  const isEditMode = Boolean((location.state as { edit?: boolean } | null)?.edit);
  const storedMode = readStoredOperationMode();
  const storedUrl = getStoredServerUrl();
  const hasExistingConfiguration = Boolean(storedMode && storedUrl && getStoredSetupCompleted());

  const initialConnectionMode = readStoredConnectionMode() || (storedMode === "client" ? "CLIENT" : "SERVER_PC");
  const [selectedConnectionMode, setSelectedConnectionMode] = useState<ConnectionMode>(initialConnectionMode);
  const [selectedMode, setSelectedMode] = useState<OperationMode>(connectionModeToOperationMode(initialConnectionMode));
  const [clientUrl, setClientUrl] = useState(storedMode === "client" ? storedUrl : "");
  const [validationState, setValidationState] = useState<SetupValidationState>("idle");
  const [error, setError] = useState<string | null>(null);
  const [warning, setWarning] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [pendingMode, setPendingMode] = useState<ConnectionMode | null>(null);
  const [showCommandPanel, setShowCommandPanel] = useState(false);
  const [validationSnapshot, setValidationSnapshot] = useState<ValidationSnapshot>(() => {
    return emptyValidationSnapshot(LOCAL_SERVER_ROOT_URL, LOCAL_SERVER_API_BASE_URL);
  });
  const abortRef = useRef<AbortController | null>(null);

  const connectionPolicy = resolveSetupConnectionPolicy(selectedConnectionMode, LOCAL_SERVER_ROOT_URL);
  const localServerRoot = connectionPolicy.resolvedServerRootUrl || LOCAL_SERVER_ROOT_URL;
  const displayedUrl = validationState === "connected" ? validationSnapshot.serverRoot : connectionPolicy.requiresRemoteServerUrl ? clientUrl : localServerRoot;
  const remoteServerLabel = selectedConnectionMode === "SERVER" ? "Adresse du serveur central" : "Adresse du serveur reseau";
  const remoteServerDescription =
    selectedConnectionMode === "SERVER"
      ? "Entrez l'adresse FastAPI du serveur central puis validez la connexion."
      : "Entrez l'adresse du serveur reseau puis validez la connexion.";

  useEffect(() => {
    if (!runtimeConnection.mode || pendingMode || storedMode || hasExistingConfiguration) {
      return;
    }
    setSelectedMode(runtimeConnection.mode);
  }, [hasExistingConfiguration, pendingMode, runtimeConnection.mode, storedMode]);

  useEffect(() => () => abortRef.current?.abort(), []);

  useEffect(() => {
    setValidationSnapshot((current) => ({
      ...current,
      serverRoot: connectionPolicy.requiresRemoteServerUrl ? clientUrl : localServerRoot,
      apiBaseUrl: connectionPolicy.requiresRemoteServerUrl ? current.apiBaseUrl : LOCAL_SERVER_API_BASE_URL,
    }));
  }, [clientUrl, connectionPolicy.requiresRemoteServerUrl, localServerRoot]);

  const resetValidationState = (nextState: SetupValidationState = "idle") => {
    setValidationState(nextState);
    setError(null);
    setWarning(null);
    if (nextState === "idle") {
      setShowCommandPanel(false);
    }
  };

  const browserServerWarning = useMemo(() => {
    if (!localServerRoot.trim()) {
      return null;
    }
    try {
      const parsed = new URL(localServerRoot);
      if (isLocalhostHostname(parsed.hostname)) {
        return "Cette adresse locale convient a un poste serveur local. Pour les autres postes du reseau, utilisez l'adresse LAN du serveur.";
      }
    } catch {
      return null;
    }
    return null;
  }, [localServerRoot]);

  const browserClientWarning = useMemo(() => {
    if (!clientUrl.trim()) {
      return null;
    }
    try {
      const parsed = new URL(/^https?:\/\//i.test(clientUrl) ? clientUrl : `http://${clientUrl}`);
      if (isLocalhostHostname(parsed.hostname)) {
        return "Cette adresse locale convient au developpement sur ce poste, mais elle ne convient pas a un client reseau distant.";
      }
    } catch {
      return null;
    }
    return null;
  }, [clientUrl]);

  const currentWarning = connectionPolicy.requiresRemoteServerUrl ? browserClientWarning : browserServerWarning;
  const browserStatusPanel = useMemo(
    () =>
      buildBrowserStatusPanel({
        mode: selectedMode,
        usedUrl: displayedUrl || localServerRoot || null,
        validationState,
        canProvision: canProvisionServer(runtimePlatform),
      }),
    [displayedUrl, localServerRoot, runtimePlatform, selectedMode, validationState],
  );

  const applySelectedMode = (nextConnectionMode: ConnectionMode) => {
    const nextMode = connectionModeToOperationMode(nextConnectionMode);
    if (
      shouldRequireModeChangeConfirmation({
        currentMode: storedMode,
        nextMode,
        hasExistingConfiguration,
      })
    ) {
      setPendingMode(nextConnectionMode);
      return;
    }

    setPendingMode(null);
    setSelectedConnectionMode(nextConnectionMode);
    setSelectedMode(nextMode);
    resetValidationState();
  };

  const handleConfirmModeSwitch = () => {
    if (!pendingMode) {
      return;
    }
    setSelectedConnectionMode(pendingMode);
    setSelectedMode(connectionModeToOperationMode(pendingMode));
    setPendingMode(null);
    resetValidationState();
  };

  const handleClientUrlChange = (value: string) => {
    abortRef.current?.abort();
    setClientUrl(value.trim());
    resetValidationState();
  };

  const handleValidate = async () => {
    if (connectionPolicy.requiresRemoteServerUrl && !clientUrl.trim()) {
      setValidationState("idle");
      setError(
        selectedConnectionMode === "SERVER"
          ? "L'adresse du serveur central est requise."
          : "L'adresse du serveur central est requise pour un poste client.",
      );
      return;
    }

    const rawUrl = connectionPolicy.resolvedServerRootUrl || clientUrl;

    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    setSubmitting(true);
    setValidationState("validating");
    setError(null);
    setWarning(null);

    try {
      const result = await runtimeConnection.validateConnection(selectedMode, rawUrl, {
        persist: false,
        signal: controller.signal,
      });

      if (!result.success) {
        setValidationState(mapValidationResultToState(result));
        setValidationSnapshot({
          serverRoot: result.apiBaseUrl ? result.apiBaseUrl.replace(/\/api\/v1\/?$/, "") : rawUrl,
          apiBaseUrl: result.apiBaseUrl || (connectionPolicy.requiresRemoteServerUrl ? "" : LOCAL_SERVER_API_BASE_URL),
        });
        setError(result.message || "La verification du serveur a echoue.");
        setWarning(result.warning || currentWarning);
        return;
      }

      const validatedApiBaseUrl = result.apiBaseUrl || LOCAL_SERVER_API_BASE_URL;
      setValidationSnapshot({
        serverRoot: validatedApiBaseUrl.replace(/\/api\/v1\/?$/, ""),
        apiBaseUrl: validatedApiBaseUrl,
      });
      setValidationState("connected");
      setWarning(result.warning || currentWarning);
    } catch (cause) {
      if (cause instanceof DOMException && cause.name === "AbortError") return;
      setValidationState("api_unavailable");
      setError(cause instanceof Error ? cause.message : "La verification de la connexion a echoue.");
    } finally {
      setSubmitting(false);
    }
  };

  const handleSaveAndContinue = async () => {
    if (validationState !== "connected") return;
    setSubmitting(true);
    setError(null);
    try {
      const result = await runtimeConnection.validateConnection(selectedMode, validationSnapshot.serverRoot, {
        persist: true,
      });
      if (!result.success) {
        setError(result.message || "La sauvegarde de la configuration a echoue.");
        return;
      }
      setStoredConnectionMode(selectedConnectionMode);
      await runtimeConnection.notifySetupCompleted();
      navigate("/login", { replace: true });
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "La sauvegarde de la configuration a echoue.");
    } finally {
      setSubmitting(false);
    }
  };

  if (isTauri) {
    return (
      <DesktopDeploymentGate
        forceOpen
        onReady={() => {
          void runtimeConnection.notifySetupCompleted().then(() => navigate("/login", { replace: true }));
        }}
      />
    );
  }

  return (
    <div className="min-h-screen bg-slate-50 px-4 py-8 text-slate-950 sm:px-6">
      <div className="mx-auto flex min-h-[calc(100vh-4rem)] max-w-3xl items-center">
        <div className="w-full">
          <Card className="rounded-2xl border-slate-200 bg-white p-6 shadow-sm sm:p-8">
            <div className="space-y-3">
              <p className="text-sm font-semibold text-[#0085A3]">Configuration réseau</p>
              <div>
                <h1 className="text-2xl font-bold tracking-tight text-slate-950">Connecter ce poste</h1>
                <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-600">
                  Choisissez le rôle de ce poste, puis vérifiez la connexion au serveur.
                </p>
              </div>
              {isEditMode ? (
                <div className="rounded-2xl border border-sky-200 bg-sky-50 px-4 py-3 text-sm font-medium text-sky-800">
                  Vous modifiez la configuration existante. Aucun changement n'est applique tant que la nouvelle connexion n'a pas ete validee.
                </div>
              ) : null}
              {pendingMode ? (
                <div className="rounded-2xl border border-amber-200 bg-amber-50 px-4 py-4 text-sm text-amber-900">
                  <p className="font-semibold">
                    Confirmez le changement vers le mode {pendingMode === "CLIENT" ? "Client" : pendingMode === "SERVER" ? "Serveur central" : "Poste serveur medical"}.
                  </p>
                  <p className="mt-2">
                    Une configuration existante est deja presente. Le mode ne changera pas tant que vous ne l'aurez pas confirme explicitement.
                  </p>
                  <div className="mt-4 flex flex-wrap gap-3">
                    <Button type="button" size="sm" icon={ArrowRightLeft} onClick={handleConfirmModeSwitch}>
                      Confirmer le changement
                    </Button>
                    <Button type="button" variant="secondary" size="sm" onClick={() => setPendingMode(null)}>
                      Annuler
                    </Button>
                  </div>
                </div>
              ) : null}
            </div>

            <div className="mt-6 grid gap-3 sm:grid-cols-3">
              <button
                type="button"
                onClick={() => applySelectedMode("SERVER")}
                className={`${modeCardClassName} ${selectedConnectionMode === "SERVER" ? selectedModeCardClassName : idleModeCardClassName}`}
              >
                <div className="flex items-center gap-3">
                  <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-[#0085A3]/10 text-[#0085A3]">
                    <Server className="h-5 w-5" />
                  </div>
                  <div>
                    <p className="font-semibold text-slate-950">Serveur central</p>
                    <p className="mt-1 text-sm leading-5 text-slate-500">
                      Ce poste héberge l'application et la base de données.
                    </p>
                  </div>
                </div>
              </button>

              <button
                type="button"
                onClick={() => applySelectedMode("SERVER_PC")}
                className={`${modeCardClassName} ${selectedConnectionMode === "SERVER_PC" ? selectedModeCardClassName : idleModeCardClassName}`}
              >
                <div className="flex items-center gap-3">
                  <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-[#0085A3]/10 text-[#0085A3]">
                    <MonitorUp className="h-5 w-5" />
                  </div>
                  <div>
                    <p className="font-semibold text-slate-950">Poste serveur medical</p>
                    <p className="mt-1 text-sm leading-5 text-slate-500">
                      Operations medicales locales sans administration globale.
                    </p>
                  </div>
                </div>
              </button>

              <button
                type="button"
                onClick={() => applySelectedMode("CLIENT")}
                className={`${modeCardClassName} ${selectedConnectionMode === "CLIENT" ? selectedModeCardClassName : idleModeCardClassName}`}
              >
                <div className="flex items-center gap-3">
                  <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-[#0085A3]/10 text-[#0085A3]">
                    <Monitor className="h-5 w-5" />
                  </div>
                  <div>
                    <p className="font-semibold text-slate-950">Client</p>
                    <p className="mt-1 text-sm leading-5 text-slate-500">
                      Ce poste se connecte à un serveur du réseau.
                    </p>
                  </div>
                </div>
              </button>
            </div>

            {!connectionPolicy.requiresRemoteServerUrl ? (
              <div className="mt-6 border-t border-slate-200 pt-6">
                <div className="mb-5 flex items-center gap-3">
                  <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-[#0085A3]/10 text-[#0085A3]">
                    <Server className="h-5 w-5" />
                  </div>
                  <div>
                    <h2 className="font-semibold text-slate-950">Backend local</h2>
                    <p className="text-sm text-slate-600">
                      Cette installation utilise automatiquement son backend FastAPI local et PostgreSQL.
                    </p>
                  </div>
                </div>

                <div className="rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-700">
                  <p className="text-xs font-semibold uppercase tracking-[0.12em] text-slate-500">Adresse API resolue</p>
                  <p className="mt-1 break-all font-mono text-xs text-slate-900">{LOCAL_SERVER_API_BASE_URL}</p>
                </div>
              </div>
            ) : (
              <div className="mt-6 border-t border-slate-200 pt-6">
                <div className="mb-5 flex items-center gap-3">
                  <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-[#0085A3]/10 text-[#0085A3]">
                    <Cable className="h-5 w-5" />
                  </div>
                  <div>
                    <h2 className="font-semibold text-slate-950">Adresse du serveur</h2>
                    <p className="text-sm text-slate-600">{remoteServerDescription}</p>
                  </div>
                </div>

                <Input
                  label={remoteServerLabel}
                  type="text"
                  value={clientUrl}
                  onChange={(event) => handleClientUrlChange(event.target.value)}
                  placeholder="http://192.168.1.10:8000"
                  autoComplete="url"
                  required
                />
              </div>
            )}

            {currentWarning || warning ? (
              <div className="mt-5 rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm font-medium text-amber-800">
                {warning || currentWarning}
              </div>
            ) : null}

            {error ? (
              <div className="mt-5 rounded-2xl border border-red-200 bg-red-50 px-4 py-4 text-sm text-red-700">
                <div className="flex items-start gap-3">
                  <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0" />
                  <div className="space-y-3">
                    <p className="font-semibold">
                      {!connectionPolicy.requiresRemoteServerUrl
                        ? "Le backend local ne repond pas."
                        : error}
                    </p>
                    {!connectionPolicy.requiresRemoteServerUrl ? (
                      <p>{error}</p>
                    ) : null}
                    {!connectionPolicy.requiresRemoteServerUrl ? (
                      <div className="flex flex-wrap gap-3">
                        <Button type="button" size="sm" variant="secondary" onClick={() => void handleValidate()}>
                          Reessayer
                        </Button>
                        <Button type="button" size="sm" variant="ghost" onClick={() => resetValidationState()}>
                          Reinitialiser
                        </Button>
                        <Button
                          type="button"
                          size="sm"
                          variant="ghost"
                          icon={showCommandPanel ? ChevronUp : ChevronDown}
                          onClick={() => setShowCommandPanel((current) => !current)}
                        >
                          Afficher les commandes de demarrage
                        </Button>
                      </div>
                    ) : null}
                  </div>
                </div>
              </div>
            ) : null}

            {!connectionPolicy.requiresRemoteServerUrl && showCommandPanel ? (
              <div className="mt-5 rounded-2xl border border-slate-200 bg-slate-950 px-4 py-4 text-sm text-slate-100">
                <p className="mb-3 font-semibold text-white">Commandes de demarrage backend</p>
                <pre className="overflow-x-auto whitespace-pre-wrap font-mono text-xs leading-6">
                  {BROWSER_SERVER_START_COMMANDS.join("\n")}
                </pre>
                <p className="mt-4 text-slate-300">
                  PostgreSQL doit etre demarre et DATABASE_URL doit pointer vers une base valide.
                </p>
              </div>
            ) : null}

            <div className="mt-6 flex flex-col-reverse gap-3 sm:flex-row sm:justify-end">
              <Button
                type="button"
                size="lg"
                icon={Network}
                loading={submitting || validationState === "validating"}
                onClick={() => void handleValidate()}
              >
                {connectionPolicy.requiresRemoteServerUrl ? "Se connecter au serveur" : "Verifier le backend local"}
              </Button>

              {validationState === "connected" ? (
                <Button
                  type="button"
                  variant="secondary"
                  size="lg"
                  icon={ShieldCheck}
                  onClick={() => void handleSaveAndContinue()}
                >
                  Enregistrer et continuer
                </Button>
              ) : null}
            </div>
          </Card>

          <Card className="hidden">
            <div className="space-y-5">
              <div className="flex items-center gap-3">
                <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-[#0085A3]/10 text-[#0085A3]">
                  <ShieldCheck className="h-5 w-5" />
                </div>
                <div>
                  <h2 className="text-lg font-black text-slate-950">Statut de la configuration</h2>
                  <p className="text-sm text-slate-600">L'acces a /login reste bloque tant que la verification requise n'a pas reussi.</p>
                </div>
              </div>

              <div className="space-y-3 text-sm text-slate-600">
                <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3">
                  <p className="text-xs font-black uppercase tracking-[0.16em] text-slate-500">Mode selectionne</p>
                  <p className="mt-2 font-semibold text-slate-900">{browserStatusPanel.selectedModeLabel}</p>
                </div>
                <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3">
                  <p className="text-xs font-black uppercase tracking-[0.16em] text-slate-500">API</p>
                  <p
                    className={`mt-2 font-semibold ${
                      browserStatusPanel.apiStatus === "available"
                        ? "text-emerald-700"
                        : browserStatusPanel.apiStatus === "unavailable"
                          ? "text-rose-700"
                          : "text-slate-700"
                    }`}
                  >
                    {getStatusLabel(browserStatusPanel.apiStatus)}
                  </p>
                </div>
                <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3">
                  <p className="text-xs font-black uppercase tracking-[0.16em] text-slate-500">Base PostgreSQL</p>
                  <p
                    className={`mt-2 font-semibold ${
                      browserStatusPanel.databaseStatus === "available"
                        ? "text-emerald-700"
                        : browserStatusPanel.databaseStatus === "unavailable"
                          ? "text-rose-700"
                          : "text-slate-700"
                    }`}
                  >
                    {getStatusLabel(browserStatusPanel.databaseStatus)}
                  </p>
                </div>
                <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3">
                  <p className="text-xs font-black uppercase tracking-[0.16em] text-slate-500">URL utilisee</p>
                  <p className="mt-2 break-all font-mono text-xs text-slate-700">
                    {browserStatusPanel.usedUrl || localServerRoot || "En attente"}
                  </p>
                </div>
                {!connectionPolicy.requiresRemoteServerUrl ? (
                  <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3">
                    <p className="text-xs font-black uppercase tracking-[0.16em] text-slate-500">URL API canonique</p>
                    <p className="mt-2 break-all font-mono text-xs text-slate-700">
                      {validationState === "connected" ? validationSnapshot.apiBaseUrl : LOCAL_SERVER_API_BASE_URL}
                    </p>
                  </div>
                ) : null}
                {browserStatusPanel.manualStartMessage ? (
                  <div className="rounded-2xl border border-amber-200 bg-amber-50 px-4 py-4 text-sm text-amber-900">
                    <div className="flex items-start gap-3">
                      <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0" />
                      <p>{browserStatusPanel.manualStartMessage}</p>
                    </div>
                  </div>
                ) : null}
              </div>

              <div className="space-y-3 text-sm text-slate-600">
                <p>Verification requise avant la connexion utilisateur :</p>
                <ul className="space-y-2">
                  <li className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3">
                    <span className="font-semibold text-slate-800">/health</span> doit repondre sur l'URL serveur.
                  </li>
                  <li className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3">
                    <span className="font-semibold text-slate-800">/health/database</span> doit confirmer rapidement que PostgreSQL repond.
                  </li>
                  <li className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3">
                    Les diagnostics detailles restent disponibles via <span className="font-semibold text-slate-800">/health/database/details</span> sans ralentir l'ecran de connexion.
                  </li>
                </ul>
              </div>

              <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-4 text-sm text-slate-600">
                <div className="mb-3 flex items-center gap-2 font-semibold text-slate-900">
                  <Database className="h-4 w-4" />
                  Resultats de validation PostgreSQL
                </div>
                <p>
                  {validationState === "idle"
                    ? "Aucune verification n'a encore ete lancee."
                    : browserStatusPanel.databaseStatus === "available"
                      ? "Base PostgreSQL disponible."
                      : browserStatusPanel.databaseStatus === "unavailable"
                        ? "Base PostgreSQL indisponible."
                        : "Verification PostgreSQL non effectuee."}
                </p>
              </div>
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
};

export const SetupPage = () => {
  const installation = useInstallationProfile();
  if (installation.loading) {
    return <div className="flex min-h-screen items-center justify-center bg-slate-50 text-sm text-slate-600">Chargement de la configuration…</div>;
  }
  if (installation.isCentralServer) return <CentralServerSetupPage />;
  if (installation.profile === "mobile_device") return <MobileDeviceSetupPage />;
  return <SetupForm />;
};
