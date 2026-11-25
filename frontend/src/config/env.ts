const importMetaEnv = (import.meta as ImportMeta & { env?: Record<string, string | undefined> }).env;

export const env = {
  apiBaseUrl: importMetaEnv?.VITE_API_BASE_URL || importMetaEnv?.VITE_API_URL || "http://localhost:8000/api/v1",
  appName: importMetaEnv?.VITE_APP_NAME || "Medical Clinic Management System",
  appVersion: importMetaEnv?.VITE_APP_VERSION || "1.0.2",
  installationProfile:
    importMetaEnv?.VITE_INSTALLATION_PROFILE === "central_server" ||
    importMetaEnv?.VITE_INSTALLATION_PROFILE === "mobile_device"
      ? importMetaEnv.VITE_INSTALLATION_PROFILE
      : "mobile_device",
  buildId: importMetaEnv?.VITE_INSTALLER_BUILD_ID || null,
  packageLabel: importMetaEnv?.VITE_PACKAGE_LABEL || null,
  installerIdentifier: importMetaEnv?.VITE_INSTALLER_IDENTIFIER || null,
  schemaRevision: importMetaEnv?.VITE_SCHEMA_REVISION || null,
  syncProtocolVersion: importMetaEnv?.VITE_SYNC_PROTOCOL_VERSION || null,
};
