const ACCESS_KEY = "clinic_access_token";
const REFRESH_KEY = "clinic_refresh_token";
const USER_KEY = "clinic_auth_user";
const WORKSPACE_ACCESS_KEY = "clinic_workspace_access";
const SYNC_QUEUE_KEY = "clinic_sync_queue";
const SYNC_META_KEY = "clinic_sync_meta";
const NETWORK_SERVER_KEY = "clinic_network_server";
const NETWORK_DEVICE_NAME_KEY = "clinic_network_device_name";
const MISSION_DEVICE_CREDENTIAL_KEY = "clinic_mission_device_credential";
const LOCAL_DEVICE_CACHE_KEY = "clinic_local_device_identity";
const CENTRAL_SERVER_IDENTITY_KEY = "clinic_central_server_identity";
const CENTRAL_SYNC_RUNS_KEY = "clinic_central_sync_runs";
const CENTRAL_INFRA_HISTORY_KEY = "clinic_central_infrastructure_history";
const CENTRAL_SYNC_CURSOR_KEY = "clinic_central_sync_cursor";
const CENTRAL_SYNC_SECRET_KEY = "clinic_central_device_secret";

const readJsonStorage = <T>(key: string, fallback: T): T => {
  const raw = localStorage.getItem(key);
  if (!raw) {
    return fallback;
  }

  try {
    return JSON.parse(raw) as T;
  } catch {
    localStorage.removeItem(key);
    return fallback;
  }
};

export const tokenStorage = {
  getAccessToken: () => localStorage.getItem(ACCESS_KEY),
  getRefreshToken: () => localStorage.getItem(REFRESH_KEY),
  setTokens: (access: string, refresh: string) => {
    localStorage.setItem(ACCESS_KEY, access);
    localStorage.setItem(REFRESH_KEY, refresh);
  },
  clear: () => {
    localStorage.removeItem(ACCESS_KEY);
    localStorage.removeItem(REFRESH_KEY);
  },
};

export const userStorage = {
  get: <T>() => readJsonStorage<T | null>(USER_KEY, null),
  set: (value: unknown) => localStorage.setItem(USER_KEY, JSON.stringify(value)),
  clear: () => localStorage.removeItem(USER_KEY),
};

export const workspaceStorage = {
  get: <T>() => readJsonStorage<T | null>(WORKSPACE_ACCESS_KEY, null),
  set: (value: unknown) => localStorage.setItem(WORKSPACE_ACCESS_KEY, JSON.stringify(value)),
  clear: () => localStorage.removeItem(WORKSPACE_ACCESS_KEY),
};

export const syncStorage = {
  getQueue: <T>() => readJsonStorage<T | null>(SYNC_QUEUE_KEY, null),
  setQueue: (value: unknown) =>
    localStorage.setItem(SYNC_QUEUE_KEY, JSON.stringify(value)),
  getMeta: <T>() => readJsonStorage<T | null>(SYNC_META_KEY, null),
  setMeta: (value: unknown) =>
    localStorage.setItem(SYNC_META_KEY, JSON.stringify(value)),
};

export const networkStorage = {
  getServer: <T>() => readJsonStorage<T | null>(NETWORK_SERVER_KEY, null),
  setServer: (value: unknown) =>
    localStorage.setItem(NETWORK_SERVER_KEY, JSON.stringify(value)),
  clearServer: () => localStorage.removeItem(NETWORK_SERVER_KEY),
  getDeviceName: () => localStorage.getItem(NETWORK_DEVICE_NAME_KEY),
  setDeviceName: (value: string) =>
    localStorage.setItem(NETWORK_DEVICE_NAME_KEY, value),
  clearDeviceName: () => localStorage.removeItem(NETWORK_DEVICE_NAME_KEY),
};

export const missionStorage = {
  getCredential: () => localStorage.getItem(MISSION_DEVICE_CREDENTIAL_KEY),
  setCredential: (value: string) => localStorage.setItem(MISSION_DEVICE_CREDENTIAL_KEY, value),
  clearCredential: () => localStorage.removeItem(MISSION_DEVICE_CREDENTIAL_KEY),
  getCachedDevice: <T>() => readJsonStorage<T | null>(LOCAL_DEVICE_CACHE_KEY, null),
  setCachedDevice: (value: unknown) => localStorage.setItem(LOCAL_DEVICE_CACHE_KEY, JSON.stringify(value)),
};

export const centralSyncStorage = {
  getServerIdentity: <T>() => readJsonStorage<T | null>(CENTRAL_SERVER_IDENTITY_KEY, null),
  setServerIdentity: (value: unknown) => localStorage.setItem(CENTRAL_SERVER_IDENTITY_KEY, JSON.stringify(value)),
  clearServerIdentity: () => localStorage.removeItem(CENTRAL_SERVER_IDENTITY_KEY),
  getRuns: <T>() => readJsonStorage<T>(CENTRAL_SYNC_RUNS_KEY, [] as T),
  setRuns: (value: unknown) => localStorage.setItem(CENTRAL_SYNC_RUNS_KEY, JSON.stringify(value)),
  getInfrastructureHistory: <T>() => readJsonStorage<T>(CENTRAL_INFRA_HISTORY_KEY, [] as T),
  setInfrastructureHistory: (value: unknown) => localStorage.setItem(CENTRAL_INFRA_HISTORY_KEY, JSON.stringify(value)),
  getCursor: () => {
    const raw = localStorage.getItem(CENTRAL_SYNC_CURSOR_KEY);
    return raw ? Number(raw) || 0 : 0;
  },
  setCursor: (value: number) => localStorage.setItem(CENTRAL_SYNC_CURSOR_KEY, String(value)),
  getDeviceSecret: () => localStorage.getItem(CENTRAL_SYNC_SECRET_KEY),
  setDeviceSecret: (value: string) => localStorage.setItem(CENTRAL_SYNC_SECRET_KEY, value),
  clearDeviceSecret: () => localStorage.removeItem(CENTRAL_SYNC_SECRET_KEY),
};
