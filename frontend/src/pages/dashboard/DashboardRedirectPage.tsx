import { Navigate } from "react-router-dom";
import { Spinner } from "@/components/common/Spinner";
import { CENTRAL_HOME_ROUTE } from "@/features/central/centralServerFlow";
import { MOBILE_HOME_ROUTE } from "@/features/mobile/mobileDeviceFlow";
import { useAuth } from "@/hooks/useAuth";
import { useInstallationProfile } from "@/hooks/useInstallationProfile";
import { buildUserDashboardUid } from "@/utils/uid";

export const DashboardRedirectPage = () => {
  const { hasStoredSession, profileResolved, user } = useAuth();
  const { isCentralServer, profile } = useInstallationProfile();
  if (hasStoredSession && (!profileResolved || !user)) {
    return (
      <div className="flex min-h-[40vh] items-center justify-center">
        <Spinner />
      </div>
    );
  }
  if (!user) return <Navigate to="/login" replace />;
  if (isCentralServer) {
    return <Navigate to={CENTRAL_HOME_ROUTE} replace />;
  }
  if (profile === "mobile_device") {
    return <Navigate to={MOBILE_HOME_ROUTE} replace />;
  }
  return <Navigate to={`/dashboard/${buildUserDashboardUid(user)}`} replace />;
};
