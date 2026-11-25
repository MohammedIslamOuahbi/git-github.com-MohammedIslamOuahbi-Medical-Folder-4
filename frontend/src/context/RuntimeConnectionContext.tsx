import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";

import { setApiBaseUrl } from "@/api/axios";
import {
  isRenderableConnectionState,
  runtimeConnectionService,
  type ConnectionSnapshot,
  type ConnectionValidationResult,
} from "@/services/runtimeConnectionService";

type RuntimeConnectionContextValue = ConnectionSnapshot & {
  loading: boolean;
  validateConnection: (
    mode: "server" | "client",
    serverUrl: string,
    options?: { persist?: boolean; signal?: AbortSignal },
  ) => Promise<ConnectionValidationResult>;
  refreshConnection: (signal?: AbortSignal) => Promise<void>;
  notifySetupCompleted: () => Promise<void>;
};

const RuntimeConnectionContext = createContext<RuntimeConnectionContextValue | undefined>(undefined);
let sharedInitializationPromise: Promise<ConnectionSnapshot> | null = null;

export const RuntimeConnectionProvider = ({ children }: { children: ReactNode }) => {
  const [snapshot, setSnapshot] = useState<ConnectionSnapshot>(runtimeConnectionService.defaultSnapshot());
  const [loading, setLoading] = useState(true);
  const initializationAbortRef = useRef<AbortController | null>(null);
  const backgroundValidationAbortRef = useRef<AbortController | null>(null);

  const runBackgroundValidation = useCallback(async (nextSnapshot: ConnectionSnapshot, signal?: AbortSignal) => {
    if (!nextSnapshot.mode || !nextSnapshot.apiBaseUrl || !isRenderableConnectionState(nextSnapshot.state)) {
      return;
    }

    backgroundValidationAbortRef.current?.abort();
    const controller = new AbortController();
    backgroundValidationAbortRef.current = controller;

    if (signal) {
      if (signal.aborted) {
        controller.abort();
      } else {
        signal.addEventListener("abort", () => controller.abort(), { once: true });
      }
    }

    const result = await runtimeConnectionService.validateConnectedSnapshot({
      mode: nextSnapshot.mode,
      rawUrl: nextSnapshot.apiBaseUrl,
      signal: controller.signal,
      persist: true,
      deploymentState: nextSnapshot.deploymentState,
    });

    if (controller.signal.aborted) {
      return;
    }

    if (result.success && result.apiBaseUrl) {
      setApiBaseUrl(result.apiBaseUrl);
    }

    setSnapshot((current) => runtimeConnectionService.applyBackgroundValidationResult(current, result));
  }, []);

  const refreshConnection = useCallback(async (signal?: AbortSignal) => {
    setLoading(true);
    if (!sharedInitializationPromise) {
      sharedInitializationPromise = runtimeConnectionService.initializeConnection(signal).finally(() => {
        sharedInitializationPromise = null;
      });
    }

    const nextSnapshot = await sharedInitializationPromise;
    setSnapshot(nextSnapshot);
    if (nextSnapshot.apiBaseUrl) {
      setApiBaseUrl(nextSnapshot.apiBaseUrl);
    }
    setLoading(false);

    if (isRenderableConnectionState(nextSnapshot.state)) {
      void runBackgroundValidation(nextSnapshot, signal);
    }
  }, []);

  useEffect(() => {
    initializationAbortRef.current?.abort();
    const controller = new AbortController();
    initializationAbortRef.current = controller;
    void refreshConnection(controller.signal);
    return () => {
      controller.abort();
      backgroundValidationAbortRef.current?.abort();
    };
  }, [refreshConnection, runBackgroundValidation]);

  const validateConnection = useCallback(
    async (mode: "server" | "client", serverUrl: string, options?: { persist?: boolean; signal?: AbortSignal }) => {
      setSnapshot((current) => ({
        ...current,
        state: "validating",
        message: null,
        errorCode: null,
      }));

      const result = await runtimeConnectionService.validateConnection({
        mode,
        rawUrl: serverUrl,
        persist: options?.persist ?? true,
        signal: options?.signal,
      });

      if (result.success && result.apiBaseUrl) {
        const validatedApiBaseUrl = result.apiBaseUrl;
        setApiBaseUrl(validatedApiBaseUrl);
        setSnapshot((current) => ({
          ...current,
          state: "connected",
          mode,
          apiBaseUrl: validatedApiBaseUrl,
          serverRootUrl: validatedApiBaseUrl.replace(/\/api\/v1\/?$/, ""),
          message: mode === "server" ? "Serveur valide." : "Connexion validee.",
          warning: result.warning || null,
          errorCode: null,
          lastValidatedAt: new Date().toISOString(),
        }));
      } else {
        setSnapshot((current) => ({
          ...current,
          state: "connection_error",
          mode,
          message: result.message || null,
          warning: result.warning || null,
          errorCode: result.errorCode || null,
        }));
      }

      return result;
    },
    [],
  );

  const notifySetupCompleted = useCallback(async () => {
    await refreshConnection();
  }, [refreshConnection]);

  const value = useMemo<RuntimeConnectionContextValue>(
    () => ({
      ...snapshot,
      loading,
      validateConnection,
      refreshConnection,
      notifySetupCompleted,
    }),
    [loading, notifySetupCompleted, refreshConnection, snapshot, validateConnection],
  );

  return <RuntimeConnectionContext.Provider value={value}>{children}</RuntimeConnectionContext.Provider>;
};

export const useRuntimeConnectionContext = () => {
  const context = useContext(RuntimeConnectionContext);
  if (!context) {
    throw new Error("useRuntimeConnectionContext must be used within RuntimeConnectionProvider");
  }
  return context;
};
