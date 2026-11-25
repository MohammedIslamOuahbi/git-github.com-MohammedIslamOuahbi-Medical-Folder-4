import { useMemo, useState } from "react";
import { Navigate, useNavigate } from "react-router-dom";

import { MobileSetupWizard } from "@/components/mobile/MobileSetupWizard";
import {
  MOBILE_HOME_ROUTE,
  buildBootstrapStageStates,
  buildMobileCompletionSummary,
  buildMobileRegistrationSummary,
  defaultMobileWizardDraft,
  shouldShowMobileProvisioning,
  type MobileWizardStepId,
} from "@/features/mobile/mobileDeviceFlow";
import { setStoredSetupCompleted } from "@/config/runtime";
import { useCentralServerInfo, useInstallationStatus } from "@/hooks/useCentralInstallation";
import { useInstallationProfile } from "@/hooks/useInstallationProfile";
import {
  useDeviceRegistration,
  useMobileBootstrap,
  useMobileProvisioning,
  useMobileRuntimeStatus,
} from "@/hooks/useMobileInstallation";

export const MobileDeviceSetupPage = () => {
  const navigate = useNavigate();
  const { profile, mismatchError, isCentralServer } = useInstallationProfile();
  const { status } = useInstallationStatus();
  const { data: serverInfo } = useCentralServerInfo(false);
  const { provision, result: provisionResult, loading: provisioning } = useMobileProvisioning();
  const { register, result: registrationResult, loading: registering } = useDeviceRegistration();
  const { start, complete, manifest, loading: bootstrapping } = useMobileBootstrap();
  const { status: runtimeStatus } = useMobileRuntimeStatus();
  const [activeStep, setActiveStep] = useState<MobileWizardStepId>("welcome");
  const [draft, setDraft] = useState(() => defaultMobileWizardDraft(status));
  const [selectedRuntimeMode, setSelectedRuntimeMode] = useState("Mode autonome");
  const [bootstrapInterrupted, setBootstrapInterrupted] = useState(false);
  const [checksumFailed, setChecksumFailed] = useState(false);

  const busy = provisioning || registering || bootstrapping;
  const showMobile = shouldShowMobileProvisioning({
    profile,
    provisioningStatus: status?.provisioning_status,
  });

  const registrationSummary = buildMobileRegistrationSummary({
    draft,
    serverName: serverInfo?.status || "Serveur central",
    registration: registrationResult,
  });
  const bootstrapStates = buildBootstrapStageStates({
    manifest,
    checksumFailed,
    interrupted: bootstrapInterrupted,
  });
  const completion = buildMobileCompletionSummary({ manifest, provision: provisionResult });

  const centralServerSummary = useMemo(
    () => ({
      "central server name": serverInfo?.status || "Serveur central",
      UUID: serverInfo?.server_uuid || null,
      "generation UUID": serverInfo?.server_generation_uuid || null,
      "schema revision": serverInfo?.schema_revision || null,
      "protocol version": serverInfo?.protocol_version || null,
      "connection status": serverInfo ? "Connecté" : "À tester",
    }),
    [serverInfo],
  );

  if (mismatchError || isCentralServer) {
    return <Navigate to="/setup" replace />;
  }

  if (!showMobile && status?.provisioning_status === "configured") {
    return <Navigate to={MOBILE_HOME_ROUTE} replace />;
  }

  const handleProvision = async () => {
    await provision({
      device_name: draft.identity.deviceName,
      device_code: draft.identity.deviceCode,
      description: draft.identity.description || null,
      central_server_url: draft.connection.centralServerUrl,
    });
  };

  const handleRegister = async () => {
    if (!provisionResult?.device_uuid) {
      await handleProvision();
    }
    await register(draft.connection.centralServerUrl, {
      device_uuid: provisionResult?.device_uuid || status?.server_uuid || "",
      device_secret: draft.identity.deviceCode,
      app_version: status?.app_version,
      schema_revision: status?.schema_revision,
      protocol_version: status?.sync_protocol_version,
    });
  };

  const handleBootstrap = async () => {
    setBootstrapInterrupted(false);
    setChecksumFailed(false);
    try {
      const boot = await start(provisionResult?.device_uuid || status?.server_uuid || "");
      if (boot.download.checksum !== boot.manifest.checksum) {
        setChecksumFailed(true);
        return;
      }
      await complete("Bootstrap mobile initial");
    } catch {
      setBootstrapInterrupted(true);
    }
  };

  const handleComplete = () => {
    setStoredSetupCompleted(true);
    void runtimeStatus;
    navigate("/login", { replace: true });
  };

  return (
    <div className="min-h-screen bg-[radial-gradient(circle_at_top,_rgba(0,133,163,0.12),_transparent_32%),linear-gradient(180deg,_#f8fbfd,_#eef4f7)] px-6 py-10">
      <div className="mx-auto max-w-7xl">
        <MobileSetupWizard
          status={status}
          activeStep={activeStep}
          draft={draft}
          deviceUuid={provisionResult?.device_uuid || status?.server_uuid || null}
          centralServerSummary={centralServerSummary}
          registrationSummary={registrationSummary}
          manifest={manifest}
          bootstrapStates={bootstrapStates}
          selectedRuntimeMode={selectedRuntimeMode}
          onRuntimeModeChange={setSelectedRuntimeMode}
          onDraftChange={setDraft}
          onStepChange={setActiveStep}
          onProvision={() => {
            void handleProvision();
          }}
          onRegister={() => {
            void handleRegister();
          }}
          onBootstrap={() => {
            void handleBootstrap();
          }}
          onComplete={handleComplete}
          busy={busy}
        />
        <div className="mt-6 flex flex-wrap gap-2 text-xs text-slate-500">
          <span>Poste configuré: {completion.configured ? "oui" : "non"}</span>
          <span>Données locales: {completion.localDataAvailable ? "disponibles" : "indisponibles"}</span>
          <span>Dernière séquence centrale: {completion.lastCentralSequence}</span>
        </div>
      </div>
    </div>
  );
};
