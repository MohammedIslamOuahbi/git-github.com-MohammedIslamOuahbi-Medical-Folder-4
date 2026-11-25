import { Navigate, Outlet, useLocation } from "react-router-dom";

import { Card } from "@/components/common/Card";
import { CENTRAL_HOME_ROUTE, getCentralRestrictionDecision } from "@/features/central/centralServerFlow";
import { useInstallationProfile } from "@/hooks/useInstallationProfile";

export const CentralProfileRoute = () => {
  const location = useLocation();
  const { profile } = useInstallationProfile();
  const decision = getCentralRestrictionDecision(location.pathname, profile);

  if (decision.allowed) {
    return <Outlet />;
  }

  if (location.pathname === CENTRAL_HOME_ROUTE) {
    return (
      <Card className="rounded-[2rem] border-amber-200 bg-amber-50 p-8">
        <h1 className="text-2xl font-black text-amber-900">Profil restreint</h1>
        <p className="mt-3 text-sm text-amber-800">{decision.message}</p>
      </Card>
    );
  }

  return <Navigate to={decision.redirectTo} replace state={{ restrictionMessage: decision.message }} />;
};
