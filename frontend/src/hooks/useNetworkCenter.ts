import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { networkApi } from "@/api/networkApi";
import { getApiBaseUrl, setApiBaseUrl } from "@/api/axios";
import { useAuth } from "@/context/AuthContext";
import { useSyncStore } from "@/store/syncStore";
import type {
  DiscoveredServerSummary,
  MissionServerSummary,
  NetworkStatusResponse,
  SystemLogEntry,
} from "@/types/network";
import { networkStorage } from "@/utils/storage";

const wsUrlFromApiBase = (baseUrl: string) => {
  const url = new URL(baseUrl);
  const protocol = url.protocol === "https:" ? "wss:" : "ws:";
  const apiRoot = url.pathname.replace(/\/api\/v1\/?$/, "");
  return `${protocol}//${url.host}${apiRoot}/api/v1/network/ws`;
};

const defaultDeviceName = (userName: string, deviceId: string) =>
  networkStorage.getDeviceName() || `${userName || "Device"}-${deviceId.slice(-6)}`;

export const useNetworkCenter = () => {
  const { user, accessToken, isAuthenticated, loading: authLoading } = useAuth();
  const deviceId = useSyncStore((state) => state.deviceId);
  const initialServer = networkStorage.getServer<DiscoveredServerSummary>();

  const [deviceName, setDeviceName] = useState(() =>
    defaultDeviceName([user?.first_name, user?.last_name].filter(Boolean).join(" ").trim(), deviceId),
  );
  const [status, setStatus] = useState<NetworkStatusResponse | null>(null);
  const [discoveredServers, setDiscoveredServers] = useState<DiscoveredServerSummary[]>(() =>
    initialServer ? [initialServer] : [],
  );
  const [selectedServer, setSelectedServer] = useState<DiscoveredServerSummary | null>(initialServer);
  const [logs, setLogs] = useState<SystemLogEntry[]>([]);
  const [missionServer, setMissionServer] = useState<MissionServerSummary | null>(null);
  const [loading, setLoading] = useState(false);
  const [wsConnected, setWsConnected] = useState(false);
  const [latencyMs, setLatencyMs] = useState<number | null>(null);
  const websocketRef = useRef<WebSocket | null>(null);
  const heartbeatRef = useRef<number | null>(null);
  const selectedServerRef = useRef<DiscoveredServerSummary | null>(initialServer);
  const canUseProtectedNetworkApi = Boolean(accessToken && user && isAuthenticated && !authLoading);

  useEffect(() => {
    networkStorage.setDeviceName(deviceName);
  }, [deviceName]);

  useEffect(() => {
    selectedServerRef.current = selectedServer;
    if (selectedServer) {
      networkStorage.setServer(selectedServer);
      setApiBaseUrl(selectedServer.api_base_url);
    }
  }, [selectedServer]);

  const mergeStatus = useCallback((nextStatus: NetworkStatusResponse) => {
    setStatus(nextStatus);
    setMissionServer(nextStatus.mission_server);
    setDiscoveredServers(nextStatus.discovered_servers || []);
    setLogs(nextStatus.realtime_logs || []);
    if (nextStatus.selected_server) {
      setSelectedServer((current) => {
        if (
          current &&
          current.api_base_url === nextStatus.selected_server?.api_base_url &&
          current.ip_address === nextStatus.selected_server?.ip_address &&
          current.server_name === nextStatus.selected_server?.server_name
        ) {
          return current;
        }
        return nextStatus.selected_server;
      });
    }
  }, []);

  const refreshStatus = useCallback(async () => {
    const next = await networkApi.getStatus();
    mergeStatus(next);
    return next;
  }, [mergeStatus]);

  const refreshLogs = useCallback(async () => {
    const nextLogs = await networkApi.getLogs();
    setLogs(nextLogs);
    return nextLogs;
  }, []);

  const scanNetwork = useCallback(async () => {
    setLoading(true);
    try {
      const next = await networkApi.discover();
      setDiscoveredServers(next);
      return next;
    } finally {
      setLoading(false);
    }
  }, []);

  const connectToServer = useCallback(
    async (server: DiscoveredServerSummary) => {
      const startedAt = performance.now();
      const next = await networkApi.connect({
        server_ip: server.ip_address,
        server_name: server.server_name,
        api_base_url: server.api_base_url,
        device_name: deviceName,
        latency_ms: null,
      });
      setLatencyMs(Math.max(1, Math.round(performance.now() - startedAt)));
      setSelectedServer(server);
      mergeStatus(next);
      await refreshLogs();
      return next;
    },
    [deviceName, mergeStatus, refreshLogs],
  );

  const heartbeat = useCallback(async () => {
    const startedAt = performance.now();
    const next = await networkApi.heartbeat({
      device_name: deviceName,
      latency_ms: Math.max(1, Math.round(performance.now() - startedAt)),
    });
    mergeStatus(next);
    return next;
  }, [deviceName, mergeStatus]);

  const startMissionServer = useCallback(async () => {
    const next = await networkApi.startMissionServer({
      server_name: `${deviceName} Mission Server`,
      device_name: deviceName,
    });
    mergeStatus(next);
    await refreshLogs();
    return next;
  }, [deviceName, mergeStatus, refreshLogs]);

  const stopMissionServer = useCallback(
    async (reason?: string) => {
      const next = await networkApi.stopMissionServer({ reason });
      mergeStatus(next);
      await refreshLogs();
      return next;
    },
    [mergeStatus, refreshLogs],
  );

  useEffect(() => {
    const deviceLabel = defaultDeviceName([user?.first_name, user?.last_name].filter(Boolean).join(" ").trim(), deviceId);
    setDeviceName((current: string) => current || deviceLabel);
  }, [deviceId, user?.first_name, user?.last_name]);

  useEffect(() => {
    if (!canUseProtectedNetworkApi) {
      setStatus(null);
      setMissionServer(null);
      setLogs([]);
      return () => {
        // no-op cleanup
      };
    }

    let cancelled = false;
    void (async () => {
      try {
        const next = await refreshStatus();
        if (cancelled) return;
        if (next.selected_server && !selectedServerRef.current) {
          setSelectedServer(next.selected_server);
        }
      } catch {
        if (cancelled) return;
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [canUseProtectedNetworkApi, refreshStatus]);

  useEffect(() => {
    if (!canUseProtectedNetworkApi) {
      setWsConnected(false);
      if (websocketRef.current) {
        websocketRef.current.close();
        websocketRef.current = null;
      }
      return () => {
        // no-op cleanup
      };
    }

    const baseUrl = selectedServer?.api_base_url || getApiBaseUrl();
    const wsUrl = wsUrlFromApiBase(baseUrl);
    const websocket = new WebSocket(wsUrl);
    websocketRef.current = websocket;

    websocket.onopen = () => setWsConnected(true);
    websocket.onclose = () => setWsConnected(false);
    websocket.onerror = () => setWsConnected(false);
    websocket.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data) as { event_type?: string; payload?: NetworkStatusResponse };
        if (payload.payload) {
          mergeStatus(payload.payload);
        }
      } catch {
        return;
      }
    };

    return () => {
      websocket.close();
      websocketRef.current = null;
    };
  }, [canUseProtectedNetworkApi, mergeStatus, selectedServer?.api_base_url]);

  useEffect(() => {
    if (!canUseProtectedNetworkApi) {
      if (heartbeatRef.current) {
        window.clearInterval(heartbeatRef.current);
      }
      heartbeatRef.current = null;
      return () => {
        // no-op cleanup
      };
    }

    void heartbeat().catch(() => undefined);
    if (heartbeatRef.current) {
      window.clearInterval(heartbeatRef.current);
    }
    heartbeatRef.current = window.setInterval(() => {
      void heartbeat().catch(() => undefined);
    }, 30_000);

    return () => {
      if (heartbeatRef.current) {
        window.clearInterval(heartbeatRef.current);
      }
      heartbeatRef.current = null;
    };
  }, [canUseProtectedNetworkApi, heartbeat]);

  const currentConnectionState = status?.current_connection_state || (selectedServer ? "Connected" : "Disconnected");
  const wifiConnectionStatus = status?.wifi_connection_status || (navigator.onLine ? "Connected" : "Disconnected");
  const localIpAddress = status?.local_ip_address || "0.0.0.0";
  const connectedDevices = status?.connected_devices || [];
  const databaseStatus = status?.database_status || null;

  return useMemo(
    () => ({
      deviceId,
      deviceName,
      setDeviceName,
      status,
      missionServer,
      discoveredServers,
      selectedServer,
      logs,
      loading,
      wsConnected,
      latencyMs,
      refreshStatus,
      refreshLogs,
      scanNetwork,
      connectToServer,
      startMissionServer,
      stopMissionServer,
      heartbeat,
      currentConnectionState,
      wifiConnectionStatus,
      localIpAddress,
      connectedDevices,
      databaseStatus,
    }),
    [
      connectToServer,
      connectedDevices,
      currentConnectionState,
      databaseStatus,
      deviceId,
      deviceName,
      discoveredServers,
      heartbeat,
      latencyMs,
      loading,
      localIpAddress,
      logs,
      missionServer,
      refreshLogs,
      refreshStatus,
      scanNetwork,
      selectedServer,
      setDeviceName,
      startMissionServer,
      status,
      stopMissionServer,
      wsConnected,
      wifiConnectionStatus,
    ],
  );
};
