import apiClient from "@/api/axios";
import { connectionModeToOperationMode, readStoredConnectionMode } from "@/config/runtime";

const canConfigureRuntime = (permissions: string[] | undefined) =>
  Boolean(permissions?.includes("settings.update"));

export const connectionModeApi = {
  async synchronizeLocalBackendMode(permissions: string[] | undefined) {
    const connectionMode = readStoredConnectionMode();
    if (!connectionMode || connectionModeToOperationMode(connectionMode) !== "server") {
      return;
    }
    if (!canConfigureRuntime(permissions)) {
      return;
    }

    await apiClient.put("/runtime/connection-mode", {
      connection_mode: connectionMode,
      connection_verified: true,
    });
  },
};
