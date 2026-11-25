import { Navigate, Outlet, useParams } from "react-router-dom";

export const CampaignWorkspaceGuard = () => {
  const { campaignId } = useParams();

  if (!campaignId) {
    return <Navigate to="/campaigns" replace />;
  }

  return <Outlet />;
};
