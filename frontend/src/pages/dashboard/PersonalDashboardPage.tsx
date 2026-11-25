import { Navigate, useParams } from "react-router-dom";
import { useAuth } from "@/hooks/useAuth";
import { isMatchingDashboardUid, buildUserDashboardUid } from "@/utils/uid";
import { AdminDashboardPage } from "./AdminDashboardPage";
import { DoctorDashboardPage } from "./DoctorDashboardPage";
import { AssistantDashboardPage } from "./AssistantDashboardPage";

export const PersonalDashboardPage = () => {
  const { user } = useAuth();
  const { dashboardUid } = useParams();

  if (!user) {
    return <Navigate to="/login" replace />;
  }

  if (!isMatchingDashboardUid(dashboardUid, user)) {
    return <Navigate to={`/dashboard/${buildUserDashboardUid(user)}`} replace />;
  }

  if (user.role === "Super Admin" || user.role === "Admin") return <AdminDashboardPage />;
  if (user.role === "Doctor") return <DoctorDashboardPage />;
  return <AssistantDashboardPage />;
};
