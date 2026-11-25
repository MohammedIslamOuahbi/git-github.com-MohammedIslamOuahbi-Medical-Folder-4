import { ShieldCheck } from "lucide-react";
import { Link } from "react-router-dom";

import { CENTRAL_HOME_ROUTE } from "@/features/central/centralServerFlow";

export const CentralProfileBadge = () => (
  <Link
    to={CENTRAL_HOME_ROUTE}
    className="inline-flex items-center gap-2 rounded-2xl border border-emerald-200 bg-emerald-50 px-3 py-2 text-left text-emerald-800 transition hover:bg-emerald-100"
  >
    <ShieldCheck className="h-4 w-4" />
    <span className="flex flex-col">
      <span className="text-[10px] font-bold uppercase tracking-[0.16em]">Serveur central</span>
      <span className="text-xs font-semibold">CENTRAL-SERVER</span>
    </span>
  </Link>
);
