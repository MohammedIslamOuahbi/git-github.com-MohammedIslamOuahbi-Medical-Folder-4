import type { ReactNode } from "react";
import { Navigate } from "react-router-dom";

import { Spinner } from "@/components/common/Spinner";
import { useAuth } from "@/hooks/useAuth";
import { useRuntimeConnection } from "@/hooks/useRuntimeConnection";
import { isRenderableConnectionState } from "@/services/runtimeConnectionService";
import type { Role } from "@/types/common";
import { buildUserDashboardUid } from "@/utils/uid";

const roleRouteMap: Record<Role, string> = {
  "Super Admin": "/dashboard",
  Admin: "/dashboard",
  Doctor: "/dashboard",
  Assistant: "/dashboard",
};

export const ConnectionLoginRoute = ({ children }: { children: ReactNode }) => {
  const { user, hasStoredSession, isAuthenticated, loading, profileResolved } = useAuth();
  const runtimeConnection = useRuntimeConnection();
  const runtimeReady = isRenderableConnectionState(runtimeConnection.state);

  if ((loading && !hasStoredSession) || ((runtimeConnection.loading || runtimeConnection.state === "loading") && !runtimeReady)) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <Spinner />
      </div>
    );
  }

  if (!runtimeReady) {
    return <Navigate to="/setup" replace />;
  }

  if (hasStoredSession && !profileResolved) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <Spinner />
      </div>
    );
  }

  if (isAuthenticated && user) {
    return <Navigate to={`${roleRouteMap[user.role]}/${buildUserDashboardUid(user)}`} replace />;
  }

  return <>{children}</>;
};
