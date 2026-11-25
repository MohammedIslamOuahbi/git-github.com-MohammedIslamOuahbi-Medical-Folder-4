import { CheckCircle2, Circle, LoaderCircle } from "lucide-react";

import { Button } from "@/components/common/Button";
import { Card } from "@/components/common/Card";
import { Input } from "@/components/common/Input";
import { Textarea } from "@/components/common/Textarea";
import {
  MOBILE_BOOTSTRAP_STAGES,
  MOBILE_RUNTIME_MODE_OPTIONS,
  MOBILE_WIZARD_STEPS,
  buildBootstrapReadiness,
  type MobileWizardDraft,
  type MobileWizardStepId,
} from "@/features/mobile/mobileDeviceFlow";
import type { CentralBootstrapManifest } from "@/types/centralSync";
import type { InstallationStatusPayload } from "@/types/installation";

const StepIcon = ({ active, done }: { active: boolean; done: boolean }) =>
  done ? (
    <CheckCircle2 className="h-5 w-5 text-emerald-600" />
  ) : active ? (
    <LoaderCircle className="h-5 w-5 animate-spin text-[#0085A3]" />
  ) : (
    <Circle className="h-5 w-5 text-slate-300" />
  );

export const MobileSetupWizard = ({
  status,
  activeStep,
  draft,
  deviceUuid,
  centralServerSummary,
  registrationSummary,
  manifest,
  bootstrapStates,
  selectedRuntimeMode,
  onRuntimeModeChange,
  onDraftChange,
  onStepChange,
  onProvision,
  onRegister,
  onBootstrap,
  onComplete,
  busy,
}: {
  status: InstallationStatusPayload | null;
  activeStep: MobileWizardStepId;
  draft: MobileWizardDraft;
  deviceUuid: string | null;
  centralServerSummary: Record<string, string | null>;
  registrationSummary: { deviceName: string; code: string; centralServer: string; authorized: boolean };
  manifest: CentralBootstrapManifest | null;
  bootstrapStates: Record<string, string>;
  selectedRuntimeMode: string;
  onRuntimeModeChange: (value: string) => void;
  onDraftChange: (draft: MobileWizardDraft) => void;
  onStepChange: (step: MobileWizardStepId) => void;
  onProvision: () => void;
  onRegister: () => void;
  onBootstrap: () => void;
  onComplete: () => void;
  busy: boolean;
}) => {
  const readiness = buildBootstrapReadiness(status);
  const currentIndex = MOBILE_WIZARD_STEPS.findIndex((step) => step.id === activeStep);

  return (
    <div className="grid gap-6 xl:grid-cols-[320px,1fr]">
      <Card className="rounded-[2rem] border-slate-200 bg-white p-6">
        <div className="space-y-3">
          <p className="text-xs font-bold uppercase tracking-[0.24em] text-[#0085A3]">Configuration du poste mobile</p>
          {MOBILE_WIZARD_STEPS.map((step, index) => (
            <button
              key={step.id}
              type="button"
              onClick={() => onStepChange(step.id)}
              className="flex w-full items-center gap-3 rounded-2xl border border-slate-200 px-4 py-3 text-left hover:bg-slate-50"
            >
              <StepIcon active={index === currentIndex} done={index < currentIndex} />
              <span className="text-sm font-semibold text-slate-900">{step.title}</span>
            </button>
          ))}
        </div>
      </Card>

      <Card className="rounded-[2rem] border-slate-200 bg-white p-8">
        {activeStep === "welcome" ? (
          <div className="space-y-4">
            <h1 className="text-3xl font-black text-slate-950">Configuration du poste mobile</h1>
            <p className="text-sm leading-7 text-slate-600">
              Ce poste peut fonctionner en mode autonome, serveur de mission ou client de mission.
            </p>
          </div>
        ) : null}

        {activeStep === "postgres" ? (
          <div className="space-y-4">
            <h2 className="text-2xl font-black text-slate-950">PostgreSQL local</h2>
            <div className="grid gap-3">
              {(status?.checks || []).map((check) => (
                <div key={check.key} className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-4">
                  <div className="flex items-center justify-between gap-3">
                    <p className="font-semibold text-slate-900">{check.label}</p>
                    <span className="text-xs font-bold uppercase tracking-[0.12em] text-slate-500">{check.status}</span>
                  </div>
                  <p className="mt-2 text-sm text-slate-600">{check.detail || "En attente du backend."}</p>
                </div>
              ))}
            </div>
            <Button type="button" loading={busy} onClick={onProvision}>Provisionner localement</Button>
          </div>
        ) : null}

        {activeStep === "identity" ? (
          <div className="space-y-4">
            <h2 className="text-2xl font-black text-slate-950">Identité de l’appareil</h2>
            <div className="grid gap-4 md:grid-cols-2">
              <Input label="Nom de l’appareil" value={draft.identity.deviceName} onChange={(event) => onDraftChange({ ...draft, identity: { ...draft.identity, deviceName: event.target.value } })} />
              <Input label="Code de l’appareil" value={draft.identity.deviceCode} onChange={(event) => onDraftChange({ ...draft, identity: { ...draft.identity, deviceCode: event.target.value } })} />
              <div className="md:col-span-2">
                <Textarea label="Description" value={draft.identity.description} onChange={(event) => onDraftChange({ ...draft, identity: { ...draft.identity, description: event.target.value } })} />
              </div>
            </div>
            <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-4">
              <p className="text-xs font-bold uppercase tracking-[0.16em] text-slate-500">UUID généré</p>
              <p className="mt-2 font-mono text-xs text-slate-900">{deviceUuid || "-"}</p>
            </div>
          </div>
        ) : null}

        {activeStep === "connection" ? (
          <div className="space-y-4">
            <h2 className="text-2xl font-black text-slate-950">Connexion au serveur central</h2>
            <Input
              label="Adresse du serveur central"
              value={draft.connection.centralServerUrl}
              onChange={(event) => onDraftChange({ ...draft, connection: { centralServerUrl: event.target.value } })}
              placeholder="http://192.168.1.5:8000"
            />
            <div className="grid gap-3 md:grid-cols-2">
              {Object.entries(centralServerSummary).map(([label, value]) => (
                <div key={label} className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-4">
                  <p className="text-xs font-bold uppercase tracking-[0.16em] text-slate-500">{label}</p>
                  <p className="mt-2 break-all text-sm font-semibold text-slate-900">{value || "-"}</p>
                </div>
              ))}
            </div>
            <div className="flex gap-2">
              <Button type="button" loading={busy} onClick={onRegister}>Tester la connexion</Button>
              <Button type="button" variant="secondary">Copier l’adresse</Button>
            </div>
          </div>
        ) : null}

        {activeStep === "registration" ? (
          <div className="space-y-4">
            <h2 className="text-2xl font-black text-slate-950">Enregistrement de l’appareil</h2>
            <div className="grid gap-3 md:grid-cols-2">
              {[
                ["Nom appareil", registrationSummary.deviceName],
                ["Code", registrationSummary.code],
                ["Serveur central", registrationSummary.centralServer],
                ["Autorisation", registrationSummary.authorized ? "Autorisée" : "En attente"],
              ].map(([label, value]) => (
                <div key={label} className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-4">
                  <p className="text-xs font-bold uppercase tracking-[0.16em] text-slate-500">{label}</p>
                  <p className="mt-2 text-sm font-semibold text-slate-900">{value}</p>
                </div>
              ))}
            </div>
          </div>
        ) : null}

        {activeStep === "readiness" ? (
          <div className="space-y-4">
            <h2 className="text-2xl font-black text-slate-950">Bootstrap readiness</h2>
            <div className="grid gap-3">
              {readiness.map((item) => (
                <div key={item.label} className="flex items-center justify-between rounded-2xl border border-slate-200 bg-slate-50 px-4 py-4">
                  <span className="text-sm font-semibold text-slate-900">{item.label}</span>
                  <span className="text-xs font-bold uppercase tracking-[0.12em] text-slate-500">{item.passed ? "OK" : "À vérifier"}</span>
                </div>
              ))}
            </div>
          </div>
        ) : null}

        {activeStep === "bootstrap" ? (
          <div className="space-y-4">
            <h2 className="text-2xl font-black text-slate-950">Bootstrap progress</h2>
            <div className="grid gap-3">
              {MOBILE_BOOTSTRAP_STAGES.map((stage) => (
                <div key={stage} className="flex items-center justify-between rounded-2xl border border-slate-200 bg-slate-50 px-4 py-4">
                  <span className="text-sm font-semibold text-slate-900">{stage}</span>
                  <span className="text-xs font-bold uppercase tracking-[0.12em] text-slate-500">{bootstrapStates[stage] || "pending"}</span>
                </div>
              ))}
            </div>
            <Button type="button" loading={busy} onClick={onBootstrap}>Démarrer le bootstrap</Button>
          </div>
        ) : null}

        {activeStep === "completion" ? (
          <div className="space-y-4">
            <h2 className="text-2xl font-black text-slate-950">Choisir le mode de fonctionnement</h2>
            <div className="grid gap-4 md:grid-cols-3">
              {MOBILE_RUNTIME_MODE_OPTIONS.map((label) => (
                <button
                  key={label}
                  type="button"
                  onClick={() => onRuntimeModeChange(label)}
                  className={`rounded-[1.75rem] border px-5 py-5 text-left ${selectedRuntimeMode === label ? "border-[#0085A3]/40 bg-[#0085A3]/8" : "border-slate-200 bg-slate-50/80"}`}
                >
                  <p className="text-lg font-black text-slate-950">{label}</p>
                </button>
              ))}
            </div>
            <div className="grid gap-3 md:grid-cols-2">
              <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-4">
                <p className="text-xs font-bold uppercase tracking-[0.16em] text-slate-500">Dernière séquence centrale</p>
                <p className="mt-2 text-sm font-semibold text-slate-900">{manifest?.snapshot_central_sequence ?? 0}</p>
              </div>
              <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-4">
                <p className="text-xs font-bold uppercase tracking-[0.16em] text-slate-500">Serveur central enregistré</p>
                <p className="mt-2 text-sm font-semibold text-slate-900">{centralServerSummary["central server name"] || "-"}</p>
              </div>
            </div>
            <Button type="button" onClick={onComplete}>Continuer vers la connexion</Button>
          </div>
        ) : null}
      </Card>
    </div>
  );
};
