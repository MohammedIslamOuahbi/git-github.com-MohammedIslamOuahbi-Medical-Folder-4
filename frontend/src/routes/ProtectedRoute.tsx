import { Navigate, Outlet, useLocation } from "react-router-dom";
import { useAuth } from "@/hooks/useAuth";
import { useRuntimeConnection } from "@/hooks/useRuntimeConnection";
import { Spinner } from "@/components/common/Spinner";
import { isRenderableConnectionState } from "@/services/runtimeConnectionService";

export const ProtectedRoute = () => {
  const { hasStoredSession, isAuthenticated, loading, profileResolved } = useAuth();
  const runtimeConnection = useRuntimeConnection();
  const location = useLocation();
  const runtimeReady = isRenderableConnectionState(runtimeConnection.state);

  if ((runtimeConnection.loading || runtimeConnection.state === "loading") && !runtimeReady) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <Spinner />
      </div>
    );
  }

  if (!runtimeReady) {
    return <Navigate to="/setup" replace state={{ from: location }} />;
  }

  if (!hasStoredSession && !isAuthenticated) {
    return <Navigate to="/login" replace state={{ from: location }} />;
  }

  if (loading && !profileResolved && hasStoredSession) {
    return <Outlet />;
  }

  return <Outlet />;
};
