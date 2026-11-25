import { MonitorCog, ShieldCheck } from "lucide-react";
import { Link } from "react-router-dom";

import { useInstallationProfile } from "@/hooks/useInstallationProfile";

export const InstallationProfileBadge = () => {
  const { profile, deviceIdentity } = useInstallationProfile();

  if (!profile) {
    return null;
  }

  const isCentral = profile === "central_server";

  return (
    <Link
      to={isCentral ? "/app/infrastructure/central" : "/app/infrastructure/mobile"}
      className={`inline-flex items-center gap-2 rounded-2xl border px-3 py-2 text-left transition ${
        isCentral
          ? "border-emerald-200 bg-emerald-50 text-emerald-800 hover:bg-emerald-100"
          : "border-sky-200 bg-sky-50 text-sky-800 hover:bg-sky-100"
      }`}
    >
      {isCentral ? <ShieldCheck className="h-4 w-4" /> : <MonitorCog className="h-4 w-4" />}
      <span className="flex flex-col">
        <span className="text-[10px] font-bold uppercase tracking-[0.16em]">
          {isCentral ? "Serveur central" : "Poste mobile"}
        </span>
        <span className="text-xs font-semibold">{deviceIdentity.code || (isCentral ? "CENTRAL-SERVER" : "PC-01")}</span>
      </span>
    </Link>
  );
};
