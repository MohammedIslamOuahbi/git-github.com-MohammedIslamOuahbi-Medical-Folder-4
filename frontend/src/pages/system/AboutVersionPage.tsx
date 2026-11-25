import { Card } from "@/components/common/Card";
import { env } from "@/config/env";
import { buildAboutPanel, getProductIdentity } from "@/features/installation/profileInfrastructure";
import { useInstallationProfile } from "@/hooks/useInstallationProfile";

export const AboutVersionPage = () => {
  const { profile, installationStatus, deviceIdentity } = useInstallationProfile();
  const identity = getProductIdentity({
    profile,
    version: env.appVersion,
    buildId: env.buildId,
    installerIdentifier: env.installerIdentifier,
  });
  const items = buildAboutPanel({
    profile,
    status: installationStatus,
    deviceIdentity,
    productIdentity: identity,
  });

  return (
    <div className="space-y-6">
      <Card className="rounded-[2rem] p-6">
        <p className="text-xs font-bold uppercase tracking-[0.16em] text-slate-500">Produit</p>
        <h1 className="mt-3 text-3xl font-black text-slate-950">{identity.productTitle}</h1>
        <p className="mt-2 text-sm text-slate-600">
          Package: {identity.packageLabel} · Build: {identity.buildId}
        </p>
      </Card>

      <Card className="rounded-[2rem] p-6">
        <div className="grid gap-4 md:grid-cols-2">
          {items.map(([label, value]) => (
            <div key={label} className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3">
              <p className="text-xs font-bold uppercase tracking-[0.16em] text-slate-500">{label}</p>
              <p className="mt-2 break-all text-sm font-semibold text-slate-900">{value}</p>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
};
