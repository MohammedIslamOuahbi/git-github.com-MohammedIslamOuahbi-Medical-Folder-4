import { useCallback, useEffect, useMemo, useState } from "react";

import { getApiBaseUrl } from "@/api/axios";
import { missionApi } from "@/api/missionApi";
import { LOCAL_SERVER_API_BASE_URL } from "@/config/runtime";
import type {
  ConnectionState,
  MissionServerInfo,
  MissionSessionCreatePayload,
  MissionJoinPayload,
  RuntimeStatus,
  RuntimeStatusPayload,
} from "@/types/mission";
import { missionStorage } from "@/utils/storage";

const runtimeLabelFromError = (message: string): ConnectionState => {
  const normalized = message.toLowerCase();
  if (normalized.includes("revoked")) return "revoked";
  if (normalized.includes("schema") || normalized.includes("protocol") || normalized.includes("incompatible")) return "incompatible";
  return "disconnected";
};

const buildRuntimeStatus = (
  device: MissionServerInfo | null,
  runtimeData: RuntimeStatusPayload | null,
  connectionState: ConnectionState,
): RuntimeStatus => {
  const runtimeMode = runtimeData?.runtime_mode || device?.runtime_mode || "standalone";
  const activeMission = device?.active_mission || null;
  return {
    runtimeMode,
    activeApiSource: String(runtimeData?.active_api_url || getApiBaseUrl() || LOCAL_SERVER_API_BASE_URL),
    localDatabaseWriteEnabled:
      typeof runtimeData?.local_database_write_enabled === "boolean"
        ? Boolean(runtimeData.local_database_write_enabled)
        : runtimeMode !== "mission_client",
    missionServerName: runtimeMode === "mission_client" ? device?.device_name || null : device?.device_name || null,
    missionServerUrl: runtimeMode === "mission_client" ? getApiBaseUrl() : null,
    connectionState,
    activeMission,
    device: device
      ? {
          device_uuid: device.device_uuid,
          device_code: device.device_code,
          device_name: device.device_name,
          registered: device.registered,
          revoked: device.revoked,
          runtime_mode: device.runtime_mode,
          app_version: device.app_version,
          schema_revision: device.schema_revision,
          database_health: device.database_health,
          server_time: device.server_time,
        }
      : null,
  };
};

export const fetchMissionRuntimeSnapshot = async () =>
  Promise.all([missionApi.getCurrentDevice(), missionApi.getRuntimeStatus()]);

export const useMissionRuntime = (options?: { autoRefresh?: boolean }) => {
  const autoRefresh = options?.autoRefresh ?? true;
  const [runtime, setRuntime] = useState<RuntimeStatus>(() =>
    buildRuntimeStatus(missionStorage.getCachedDevice<MissionServerInfo>(), null, "unknown"),
  );
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [device, runtimeData] = await fetchMissionRuntimeSnapshot();
      setRuntime(buildRuntimeStatus(device, runtimeData, "connected"));
      return { device, runtimeData };
    } catch (nextError) {
      const message = nextError instanceof Error ? nextError.message : "Connexion au serveur de mission perdue.";
      setError(message);
      const cached = missionStorage.getCachedDevice<MissionServerInfo>();
      setRuntime((current) =>
        buildRuntimeStatus(
          cached,
          {
            runtime_mode: current.runtimeMode,
            active_api_url: current.activeApiSource,
            local_api_url: current.activeApiSource,
            local_database_write_enabled: current.localDatabaseWriteEnabled,
            active_mission_session_uuid: current.activeMission?.uuid || null,
            mission_server_url: current.missionServerUrl,
            mission_server_device_uuid: current.device?.device_uuid || null,
            local_device_registered: Boolean(current.device?.registered ?? current.device?.device_uuid),
            local_device_revoked: Boolean(current.device?.revoked),
            local_device_uuid: current.device?.device_uuid || null,
          },
          runtimeLabelFromError(message),
        ),
      );
      return null;
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!autoRefresh) {
      setLoading(false);
      return () => undefined;
    }
    void refresh();
    const interval = window.setInterval(() => {
      void refresh();
    }, 30000);
    return () => window.clearInterval(interval);
  }, [autoRefresh, refresh]);

  const createMissionServer = useCallback(async (payload: MissionSessionCreatePayload) => {
    const result = await missionApi.switchToMissionServer(payload);
    await refresh();
    return result;
  }, [refresh]);

  const joinMissionClient = useCallback(async (params: { baseUrl: string; missionUuid: string; joinPayload: MissionJoinPayload }) => {
    const result = await missionApi.switchToMissionClient(params);
    await refresh();
    return result;
  }, [refresh]);

  const switchToStandalone = useCallback(async (force = false, reason?: string) => {
    const result = await missionApi.switchToStandalone(force, reason);
    await refresh();
    return result;
  }, [refresh]);

  const value = useMemo(
    () => ({
      runtime,
      loading,
      error,
      refresh,
      createMissionServer,
      joinMissionClient,
      switchToStandalone,
      testMissionServer: missionApi.testMissionServer,
      finalizeMission: missionApi.finalizeMission,
      getCurrentMission: missionApi.getCurrentMission,
      updateCurrentDevice: missionApi.updateCurrentDevice,
    }),
    [createMissionServer, error, joinMissionClient, loading, refresh, runtime, switchToStandalone],
  );

  return value;
};
