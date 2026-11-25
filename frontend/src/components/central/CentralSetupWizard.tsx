import { CheckCircle2, Circle, LoaderCircle, ShieldAlert } from "lucide-react";

import { Button } from "@/components/common/Button";
import { Card } from "@/components/common/Card";
import { Input } from "@/components/common/Input";
import { Textarea } from "@/components/common/Textarea";
import {
  CENTRAL_WIZARD_STEPS,
  buildFinalVerificationItems,
  normalizeProvisioningStages,
  normalizeReadinessChecks,
  validateBackupDraft,
  validateSuperAdminDraft,
  type CentralWizardDraft,
  type CentralWizardStepId,
} from "@/features/central/centralServerFlow";
import type { CentralServerInfo } from "@/types/centralSync";
import type { InstallationStatusPayload } from "@/types/installation";

type CentralSetupWizardProps = {
  status: InstallationStatusPayload | null;
  serverInfo: CentralServerInfo | null;
  draft: CentralWizardDraft;
  activeStep: CentralWizardStepId;
  submitting: boolean;
  onDraftChange: (draft: CentralWizardDraft) => void;
  onStepChange: (step: CentralWizardStepId) => void;
  onRefreshStatus: () => void;
  onProvision: () => void;
  onComplete: () => void;
};

const StepIcon = ({ state }: { state: "active" | "done" | "todo" }) => {
  if (state === "done") {
    return <CheckCircle2 className="h-5 w-5 text-emerald-600" />;
  }
  if (state === "active") {
    return <LoaderCircle className="h-5 w-5 animate-spin text-[#0085A3]" />;
  }
  return <Circle className="h-5 w-5 text-slate-300" />;
};

export const CentralSetupWizard = ({
  status,
  serverInfo,
  draft,
  activeStep,
  submitting,
  onDraftChange,
  onStepChange,
  onRefreshStatus,
  onProvision,
  onComplete,
}: CentralSetupWizardProps) => {
  const adminErrors = validateSuperAdminDraft(draft.admin);
  const backupErrors = validateBackupDraft(draft.backup);
  const verificationItems = buildFinalVerificationItems(status);

  return (
    <div className="grid gap-6 xl:grid-cols-[320px,1fr]">
      <Card className="rounded-[2rem] border-slate-200 bg-white p-6">
        <div className="space-y-4">
          <p className="text-xs font-bold uppercase tracking-[0.24em] text-[#0085A3]">Configuration du serveur central</p>
          {CENTRAL_WIZARD_STEPS.map((step, index) => {
            const state =
              step.id === activeStep ? "active" : index < CENTRAL_WIZARD_STEPS.findIndex((item) => item.id === activeStep) ? "done" : "todo";
            return (
              <button
                key={step.id}
                type="button"
                onClick={() => onStepChange(step.id)}
                className="flex w-full items-start gap-3 rounded-2xl border border-slate-200 px-4 py-3 text-left transition hover:border-slate-300 hover:bg-slate-50"
              >
                <StepIcon state={state} />
                <span>
                  <span className="block text-sm font-bold text-slate-900">{step.title}</span>
                  <span className="mt-1 block text-xs text-slate-500">{step.description}</span>
                </span>
              </button>
            );
          })}
        </div>
      </Card>

      <Card className="rounded-[2rem] border-slate-200 bg-white p-8">
        {activeStep === "welcome" ? (
          <div className="space-y-5">
            <div>
              <h1 className="text-3xl font-black text-slate-950">Installation du serveur central Ibn Sina</h1>
              <p className="mt-3 text-sm leading-7 text-slate-600">
                Ce serveur conserve la version finale des données et reçoit les missions des postes mobiles.
              </p>
            </div>
            <div className="grid gap-4 md:grid-cols-2">
              {[
                ["Version application", status?.app_version || "-"],
                ["Révision du schéma", status?.schema_revision || serverInfo?.schema_revision || "-"],
                ["Version du protocole", status?.sync_protocol_version || serverInfo?.protocol_version || "-"],
                ["Profil d'installation", status?.profile || "central_server"],
              ].map(([label, value]) => (
                <div key={label} className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-4">
                  <p className="text-xs font-bold uppercase tracking-[0.16em] text-slate-500">{label}</p>
                  <p className="mt-2 text-sm font-semibold text-slate-900">{value}</p>
                </div>
              ))}
            </div>
          </div>
        ) : null}

        {activeStep === "postgres" ? (
          <div className="space-y-5">
            <div className="flex items-center justify-between gap-3">
              <div>
                <h2 className="text-2xl font-black text-slate-950">PostgreSQL readiness</h2>
                <p className="mt-2 text-sm text-slate-600">Les résultats affichés proviennent du backend local de confiance.</p>
              </div>
              <div className="flex gap-2">
                <Button type="button" variant="secondary" onClick={onRefreshStatus}>Vérifier</Button>
                <Button type="button" variant="secondary" onClick={onProvision}>Configurer PostgreSQL</Button>
                <Button type="button" onClick={onRefreshStatus}>Réessayer</Button>
              </div>
            </div>
            <div className="grid gap-3">
              {normalizeReadinessChecks(status?.checks).map((check) => (
                <div key={check.key} className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-4">
                  <div className="flex items-center justify-between gap-3">
                    <p className="font-semibold text-slate-900">{check.label}</p>
                    <span className="text-xs font-bold uppercase tracking-[0.12em] text-slate-500">{check.status}</span>
                  </div>
                  <p className="mt-2 text-sm text-slate-600">{check.detail || "En attente du backend."}</p>
                </div>
              ))}
            </div>
          </div>
        ) : null}

        {activeStep === "database" ? (
          <div className="space-y-5">
            <h2 className="text-2xl font-black text-slate-950">Provisionnement de la base centrale</h2>
            <div className="grid gap-3">
              {normalizeProvisioningStages(status?.provisioning_stages).map((stage) => (
                <div key={stage.key} className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-4">
                  <div className="flex items-center justify-between gap-3">
                    <p className="font-semibold text-slate-900">{stage.label}</p>
                    <span className="text-xs font-bold uppercase tracking-[0.12em] text-slate-500">{stage.status}</span>
                  </div>
                  <p className="mt-2 text-sm text-slate-600">{stage.detail || "Le backend n'a pas encore remonté de progression."}</p>
                </div>
              ))}
            </div>
            <Button type="button" loading={submitting} onClick={onProvision}>Lancer le provisionnement central</Button>
          </div>
        ) : null}

        {activeStep === "identity" ? (
          <div className="space-y-5">
            <h2 className="text-2xl font-black text-slate-950">Identité du serveur central</h2>
            <div className="grid gap-4 md:grid-cols-2">
              <Input label="Nom du serveur" value={draft.identity.serverName} onChange={(event) => onDraftChange({ ...draft, identity: { ...draft.identity, serverName: event.target.value } })} />
              <Input label="Code du serveur" value={draft.identity.serverCode} onChange={(event) => onDraftChange({ ...draft, identity: { ...draft.identity, serverCode: event.target.value } })} />
              <div className="md:col-span-2">
                <Textarea label="Description" value={draft.identity.description} onChange={(event) => onDraftChange({ ...draft, identity: { ...draft.identity, description: event.target.value } })} />
              </div>
              <Input label="Port API" value={draft.identity.apiPort} onChange={(event) => onDraftChange({ ...draft, identity: { ...draft.identity, apiPort: event.target.value } })} />
            </div>
            <div className="grid gap-4 md:grid-cols-2">
              <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-4">
                <p className="text-xs font-bold uppercase tracking-[0.16em] text-slate-500">Server UUID</p>
                <p className="mt-2 font-mono text-xs text-slate-900">{status?.server_uuid || serverInfo?.server_uuid || "-"}</p>
              </div>
              <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-4">
                <p className="text-xs font-bold uppercase tracking-[0.16em] text-slate-500">Generation UUID</p>
                <p className="mt-2 font-mono text-xs text-slate-900">{status?.generation_uuid || serverInfo?.server_generation_uuid || "-"}</p>
              </div>
            </div>
          </div>
        ) : null}

        {activeStep === "network" ? (
          <div className="space-y-5">
            <h2 className="text-2xl font-black text-slate-950">Paramètres réseau</h2>
            <div className="grid gap-4 md:grid-cols-2">
              {[
                ["LAN IP", status?.network.lan_ip || "-"],
                ["API URL", status?.network.api_url || "-"],
                ["Health status", status?.network.health_status || "-"],
                ["Firewall status", status?.network.firewall_status || "-"],
                ["Interface réseau", status?.network.network_interface || "-"],
              ].map(([label, value]) => (
                <div key={label} className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-4">
                  <p className="text-xs font-bold uppercase tracking-[0.16em] text-slate-500">{label}</p>
                  <p className="mt-2 text-sm font-semibold text-slate-900">{value}</p>
                </div>
              ))}
            </div>
            <div className="flex flex-wrap gap-2">
              <Button type="button" variant="secondary" onClick={onRefreshStatus}>Tester l’accès local</Button>
              <Button type="button" variant="secondary">Copier l’adresse</Button>
              <Button type="button">Configurer le pare-feu</Button>
            </div>
            <div className="rounded-2xl border border-amber-200 bg-amber-50 px-4 py-4 text-sm text-amber-900">
              Les clients mobiles ne doivent jamais accéder directement à PostgreSQL. Seule l’API FastAPI locale est exposée.
            </div>
          </div>
        ) : null}

        {activeStep === "admin" ? (
          <div className="space-y-5">
            <h2 className="text-2xl font-black text-slate-950">Premier super administrateur</h2>
            <div className="grid gap-4 md:grid-cols-2">
              <Input label="Prénom" value={draft.admin.firstName} onChange={(event) => onDraftChange({ ...draft, admin: { ...draft.admin, firstName: event.target.value } })} error={adminErrors.firstName} />
              <Input label="Nom" value={draft.admin.lastName} onChange={(event) => onDraftChange({ ...draft, admin: { ...draft.admin, lastName: event.target.value } })} error={adminErrors.lastName} />
              <Input label="Email" type="email" value={draft.admin.email} onChange={(event) => onDraftChange({ ...draft, admin: { ...draft.admin, email: event.target.value } })} error={adminErrors.email} />
              <Input label="Mot de passe" type="password" value={draft.admin.password} onChange={(event) => onDraftChange({ ...draft, admin: { ...draft.admin, password: event.target.value } })} error={adminErrors.password} />
              <Input label="Confirmation" type="password" value={draft.admin.confirmation} onChange={(event) => onDraftChange({ ...draft, admin: { ...draft.admin, confirmation: event.target.value } })} error={adminErrors.confirmation} />
            </div>
          </div>
        ) : null}

        {activeStep === "backup" ? (
          <div className="space-y-5">
            <h2 className="text-2xl font-black text-slate-950">Configuration des sauvegardes</h2>
            <div className="grid gap-4 md:grid-cols-2">
              <Input label="Dossier de sauvegarde" value={draft.backup.directory} onChange={(event) => onDraftChange({ ...draft, backup: { ...draft.backup, directory: event.target.value } })} error={backupErrors.directory} />
              <Input label="Politique de rétention" value={draft.backup.retentionPolicy} onChange={(event) => onDraftChange({ ...draft, backup: { ...draft.backup, retentionPolicy: event.target.value } })} />
              <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-4">
                <p className="text-xs font-bold uppercase tracking-[0.16em] text-slate-500">Statut automatique</p>
                <p className="mt-2 text-sm font-semibold text-slate-900">{status?.backup_status || "-"}</p>
              </div>
              <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-4">
                <p className="text-xs font-bold uppercase tracking-[0.16em] text-slate-500">Espace disque disponible</p>
                <p className="mt-2 text-sm font-semibold text-slate-900">{status?.available_disk_space || "-"}</p>
              </div>
            </div>
            <div className="flex gap-2">
              <Button type="button" variant="secondary">Choisir le dossier</Button>
              <Button type="button">Tester la sauvegarde</Button>
            </div>
          </div>
        ) : null}

        {activeStep === "verification" ? (
          <div className="space-y-5">
            <h2 className="text-2xl font-black text-slate-950">Vérification finale</h2>
            <div className="grid gap-3">
              {verificationItems.map((item) => (
                <div key={item.label} className="flex items-center gap-3 rounded-2xl border border-slate-200 bg-slate-50 px-4 py-4">
                  {item.passed ? (
                    <CheckCircle2 className="h-5 w-5 text-emerald-600" />
                  ) : (
                    <ShieldAlert className="h-5 w-5 text-amber-600" />
                  )}
                  <span className="text-sm font-semibold text-slate-900">{item.label}</span>
                </div>
              ))}
            </div>
            <Button type="button" loading={submitting} onClick={onComplete}>Terminer la configuration</Button>
          </div>
        ) : null}
      </Card>
    </div>
  );
};
