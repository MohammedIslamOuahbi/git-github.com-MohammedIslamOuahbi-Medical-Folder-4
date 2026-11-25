import { useEffect, useState } from "react";
import { Navigate } from "react-router-dom";

import { Card } from "@/components/common/Card";
import { CentralSetupWizard } from "@/components/central/CentralSetupWizard";
import {
  CENTRAL_HOME_ROUTE,
  CENTRAL_WIZARD_STEPS,
  defaultCentralWizardDraft,
  type CentralWizardStepId,
} from "@/features/central/centralServerFlow";
import {
  useCentralCompletion,
  useCentralProvisioning,
  useCentralServerInfo,
  useInstallationStatus,
} from "@/hooks/useCentralInstallation";
import { useInstallationProfile } from "@/hooks/useInstallationProfile";

export const CentralServerSetupPage = () => {
  const { mismatchError, isCentralServer } = useInstallationProfile();
  const { status, refreshStatus } = useInstallationStatus();
  const { data: serverInfo } = useCentralServerInfo(isCentralServer);
  const { provision, submitting: provisioning } = useCentralProvisioning();
  const { complete, submitting: completing } = useCentralCompletion();
  const [activeStep, setActiveStep] = useState<CentralWizardStepId>("welcome");
  const [draft, setDraft] = useState(() => defaultCentralWizardDraft(status));

  const submitting = provisioning || completing;
  const setupComplete = status?.provisioning_status === "configured";

  useEffect(() => {
    setDraft(defaultCentralWizardDraft(status));
  }, [status]);

  if (mismatchError) {
    return (
      <div className="mx-auto max-w-3xl py-12">
        <Card className="rounded-[2rem] border-rose-200 bg-rose-50 p-8">
          <h1 className="text-2xl font-black text-rose-900">Erreur de configuration bloquante</h1>
          <p className="mt-3 text-sm text-rose-800">
            Le profil embarqué et le profil de l’installation locale ne correspondent pas. Code: {mismatchError}
          </p>
        </Card>
      </div>
    );
  }

  if (!isCentralServer) {
    return <Navigate to="/setup" replace />;
  }

  if (setupComplete) {
    return <Navigate to={CENTRAL_HOME_ROUTE} replace />;
  }

  const handleProvision = async () => {
    await provision({
      server_name: draft.identity.serverName,
      server_code: draft.identity.serverCode,
      description: draft.identity.description || null,
      api_port: Number(draft.identity.apiPort || 8000),
      backup_directory: draft.backup.directory || null,
      admin: {
        first_name: draft.admin.firstName,
        last_name: draft.admin.lastName,
        email: draft.admin.email,
        password: draft.admin.password,
      },
    });
  };

  const handleComplete = async () => {
    await complete({
      backup_directory: draft.backup.directory || null,
      retention_policy: draft.backup.retentionPolicy || null,
    });
  };

  return (
    <div className="min-h-screen bg-[radial-gradient(circle_at_top,_rgba(0,133,163,0.12),_transparent_32%),linear-gradient(180deg,_#f8fbfd,_#eef4f7)] px-6 py-10">
      <div className="mx-auto max-w-7xl">
        <CentralSetupWizard
          status={status}
          serverInfo={serverInfo}
          draft={draft}
          activeStep={activeStep}
          submitting={submitting}
          onDraftChange={setDraft}
          onStepChange={setActiveStep}
          onRefreshStatus={() => {
            void refreshStatus();
          }}
          onProvision={() => {
            void handleProvision();
          }}
          onComplete={() => {
            void handleComplete();
          }}
        />
        <div className="mt-6 flex flex-wrap gap-2">
          {CENTRAL_WIZARD_STEPS.map((step) => (
            <button
              key={step.id}
              type="button"
              onClick={() => setActiveStep(step.id)}
              className="rounded-full border border-slate-200 bg-white px-3 py-1 text-xs font-semibold text-slate-700 hover:bg-slate-50"
            >
              {step.title}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
};
