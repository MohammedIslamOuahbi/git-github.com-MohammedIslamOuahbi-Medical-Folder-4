export type ConnectionMode = "CLIENT" | "SERVER_PC" | "SERVER";

const connectionModeLabels: Record<ConnectionMode, string> = {
  CLIENT: "Client",
  SERVER_PC: "Poste serveur medical",
  SERVER: "Serveur central",
};

export const getConnectionModeLabel = (mode: ConnectionMode | null | undefined) =>
  mode ? connectionModeLabels[mode] : "Configuration validee";
