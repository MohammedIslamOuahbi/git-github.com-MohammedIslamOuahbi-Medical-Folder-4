import { useCallback, useEffect, useState } from "react";

import { installationApi } from "@/api/installationApi";
import { useInstallationProfile } from "@/hooks/useInstallationProfile";
import type {
  BackupRecord,
  CentralCompletePayload,
  CentralCompleteResponse,
  CentralProvisionPayload,
  CentralProvisionResponse,
  MissionSubmissionRecord,
  RegisteredDeviceRecord,
} from "@/types/installation";
import type { CentralServerInfo } from "@/types/centralSync";

const useAsyncList = <T,>(loader: () => Promise<T[]>, enabled: boolean) => {
  const [data, setData] = useState<T[]>([]);
  const [loading, setLoading] = useState(enabled);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    if (!enabled) {
      setData([]);
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      setData(await loader());
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : "Une erreur est survenue.");
    } finally {
      setLoading(false);
    }
  }, [enabled, loader]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  return { data, loading, error, refresh };
};

export const useInstallationStatus = () => {
  const { installationStatus, refreshStatus, loading } = useInstallationProfile();
  return { status: installationStatus, refreshStatus, loading };
};

export const useCentralProvisioning = () => {
  const { refreshStatus, refreshProfile } = useInstallationProfile();
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState<CentralProvisionResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const provision = useCallback(
    async (payload: CentralProvisionPayload) => {
      setSubmitting(true);
      setError(null);
      try {
        const response = await installationApi.provisionCentral(payload);
        setResult(response);
        await Promise.all([refreshStatus(), refreshProfile()]);
        return response;
      } catch (nextError) {
        const message = nextError instanceof Error ? nextError.message : "Le provisionnement a échoué.";
        setError(message);
        throw nextError;
      } finally {
        setSubmitting(false);
      }
    },
    [refreshProfile, refreshStatus],
  );

  return { provision, submitting, result, error };
};

export const useCentralCompletion = () => {
  const { refreshStatus, refreshProfile } = useInstallationProfile();
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState<CentralCompleteResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const complete = useCallback(
    async (payload: CentralCompletePayload) => {
      setSubmitting(true);
      setError(null);
      try {
        const response = await installationApi.completeCentral(payload);
        setResult(response);
        await Promise.all([refreshStatus(), refreshProfile()]);
        return response;
      } catch (nextError) {
        const message = nextError instanceof Error ? nextError.message : "La finalisation a échoué.";
        setError(message);
        throw nextError;
      } finally {
        setSubmitting(false);
      }
    },
    [refreshProfile, refreshStatus],
  );

  return { complete, submitting, result, error };
};

export const useCentralServerInfo = (enabled = true) => {
  const [data, setData] = useState<CentralServerInfo | null>(null);
  const [loading, setLoading] = useState(enabled);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    if (!enabled) {
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      setData(await installationApi.getCentralServerInfo());
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : "Impossible de charger les informations du serveur.");
    } finally {
      setLoading(false);
    }
  }, [enabled]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  return { data, loading, error, refresh };
};

export const useRegisteredDevices = (enabled = true) =>
  useAsyncList<RegisteredDeviceRecord>(() => installationApi.getRegisteredDevices(), enabled);

export const useMissionSubmissions = (enabled = true) =>
  useAsyncList<MissionSubmissionRecord>(() => installationApi.getMissionSubmissions(), enabled);

export const useSystemBackups = (enabled = true) =>
  useAsyncList<BackupRecord>(() => installationApi.getBackups(), enabled);
