const connectionModeLabels = {
    CLIENT: "Client",
    SERVER_PC: "Poste serveur medical",
    SERVER: "Serveur central",
};
export const getConnectionModeLabel = (mode) => mode ? connectionModeLabels[mode] : "Configuration validee";
