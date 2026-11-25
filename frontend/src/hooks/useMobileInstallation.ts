import { useCallback, useMemo, useState } from "react";

import { installationApi } from "@/api/installationApi";
import { centralSyncApi } from "@/api/centralSyncApi";
import { missionApi } from "@/api/missionApi";
import { useInstallationProfile } from "@/hooks/useInstallationProfile";
import type {
  DeviceRegistrationPayload,
  DeviceRegistrationResponse,
  MobileProvisionPayload,
  MobileProvisionResponse,
} from "@/types/installation";
import type { CentralBootstrapDownload, CentralBootstrapManifest } from "@/types/centralSync";

export const useMobileProvisioning = () => {
  const { refreshProfile, refreshStatus } = useInstallationProfile();
  const [result, setResult] = useState<MobileProvisionResponse | null>(null);
  const [loading, setLoading] = useState(false);

  const provision = useCallback(
    async (payload: MobileProvisionPayload) => {
      setLoading(true);
      try {
        const response = await installationApi.provisionMobile(payload);
        setResult(response);
        await Promise.all([refreshProfile(), refreshStatus()]);
        return response;
      } finally {
        setLoading(false);
      }
    },
    [refreshProfile, refreshStatus],
  );

  return { provision, result, loading };
};

export const useDeviceRegistration = () => {
  const [result, setResult] = useState<DeviceRegistrationResponse | null>(null);
  const [loading, setLoading] = useState(false);

  const register = useCallback(async (serverUrl: string, payload: DeviceRegistrationPayload) => {
    setLoading(true);
    try {
      const response = await installationApi.registerDeviceOnCentral(serverUrl, payload);
      setResult(response);
      return response;
    } finally {
      setLoading(false);
    }
  }, []);

  return { register, result, loading };
};

export const useMobileBootstrap = () => {
  const [manifest, setManifest] = useState<CentralBootstrapManifest | null>(null);
  const [download, setDownload] = useState<CentralBootstrapDownload | null>(null);
  const [bootstrapUuid, setBootstrapUuid] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const start = useCallback(async (deviceUuid: string) => {
    setLoading(true);
    try {
      const request = await centralSyncApi.requestBootstrap({
        device_uuid: deviceUuid,
        allow_overwrite_without_unsent_work: false,
      });
      setBootstrapUuid(request.bootstrap_uuid);
      const nextManifest = await centralSyncApi.getBootstrapManifest(request.bootstrap_uuid);
      setManifest(nextManifest);
      const nextDownload = await centralSyncApi.downloadBootstrap(request.bootstrap_uuid);
      setDownload(nextDownload);
      return { request, manifest: nextManifest, download: nextDownload };
    } finally {
      setLoading(false);
    }
  }, []);

  const complete = useCallback(async (notes?: string) => {
    if (!bootstrapUuid) {
      return null;
    }
    return centralSyncApi.completeBootstrap(bootstrapUuid, true, notes);
  }, [bootstrapUuid]);

  return { start, complete, manifest, download, bootstrapUuid, loading };
};

export const useMobileRuntimeStatus = () => {
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState<Awaited<ReturnType<typeof missionApi.getRuntimeStatus>> | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const result = await missionApi.getRuntimeStatus();
      setStatus(result);
      return result;
    } finally {
      setLoading(false);
    }
  }, []);

  return useMemo(() => ({ status, refresh, loading }), [loading, refresh, status]);
};
