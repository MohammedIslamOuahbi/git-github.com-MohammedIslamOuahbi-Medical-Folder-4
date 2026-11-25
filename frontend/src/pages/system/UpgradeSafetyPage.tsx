import { AlertTriangle, CheckCircle2 } from "lucide-react";

import { Card } from "@/components/common/Card";
import { getUpgradeMessage, getUpgradeTitle, buildUpgradeSteps } from "@/features/installation/profileInfrastructure";
import { useInstallationProfile } from "@/hooks/useInstallationProfile";

export const UpgradeSafetyPage = () => {
  const { profile, mismatchError } = useInstallationProfile();
  const mismatchMessage = getUpgradeMessage(mismatchError);
  const steps = buildUpgradeSteps();

  return (
    <div className="space-y-6">
      <Card className="rounded-[2rem] p-6">
        <h1 className="text-3xl font-black text-slate-950">{getUpgradeTitle(profile)}</h1>
        <p className="mt-3 text-sm text-slate-600">
          Cette page vérifie la sécurité de mise à jour de l’installation active avant toute opération.
        </p>
      </Card>

      {mismatchMessage ? (
        <Card className="rounded-[2rem] border-rose-200 bg-rose-50 p-6">
          <div className="flex items-start gap-3">
            <AlertTriangle className="mt-0.5 h-5 w-5 text-rose-600" />
            <div>
              <h2 className="text-lg font-black text-rose-900">Mise à jour bloquée</h2>
              <p className="mt-2 text-sm text-rose-800">{mismatchMessage}</p>
            </div>
          </div>
        </Card>
      ) : null}

      <Card className="rounded-[2rem] p-6">
        <h2 className="text-xl font-black text-slate-950">Étapes backend</h2>
        <div className="mt-5 space-y-3">
          {steps.map((step, index) => (
            <div key={step} className="flex items-center gap-3 rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3">
              <CheckCircle2 className="h-5 w-5 text-sky-700" />
              <div>
                <p className="text-xs font-bold uppercase tracking-[0.16em] text-slate-500">Étape {index + 1}</p>
                <p className="text-sm font-semibold text-slate-900">{step}</p>
              </div>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
};
