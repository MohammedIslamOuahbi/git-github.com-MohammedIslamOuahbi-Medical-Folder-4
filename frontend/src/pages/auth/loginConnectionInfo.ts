import { getConnectionModeLabel, type ConnectionMode } from "../../config/connectionModeDisplay.js";

export const LOGIN_CONFIGURATION_PATH = "/setup";

export const buildLoginConnectionInfo = (mode: ConnectionMode | null, apiBaseUrl: string | null) => ({
  modeLabel: getConnectionModeLabel(mode),
  apiLabel: mode === "SERVER_PC" ? "API" : "Serveur",
  apiBaseUrl: apiBaseUrl || "API indisponible",
});
