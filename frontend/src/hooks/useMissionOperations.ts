import { useCallback, useEffect, useMemo, useState } from "react";

import { missionApi } from "@/api/missionApi";
import type {
  MissionChangeRecord,
  MissionCopyState,
  MissionFinalizeManifest,
  MissionParticipant,
  MissionSessionSummary,
  RuntimeStatus,
} from "@/types/mission";

const MANIFEST_STORAGE_KEY = "clinic_mission_manifest_cache";

type CopyRunState = {
  runUuid: string | null;
  status: "idle" | "running" | "interrupted" | "completed" | "failed";
  stage: string | null;
  appliedChanges: number;
  currentBatch: number;
  lastMissionSequence: number;
  finalMissionSequence: number | null;
  error: string | null;
};

const readManifestCache = (): Record<string, MissionFinalizeManifest> => {
  if (typeof window === "undefined") return {};
  try {
    const raw = window.localStorage.getItem(MANIFEST_STORAGE_KEY);
    return raw ? (JSON.parse(raw) as Record<string, MissionFinalizeManifest>) : {};
  } catch {
    return {};
  }
};

const writeManifestCache = (cache: Record<string, MissionFinalizeManifest>) => {
  if (typeof window !== "undefined") {
    window.localStorage.setItem(MANIFEST_STORAGE_KEY, JSON.stringify(cache));
  }
};

const persistManifest = (manifest: MissionFinalizeManifest) => {
  const nextCache = readManifestCache();
  nextCache[manifest.mission_uuid] = manifest;
  writeManifestCache(nextCache);
};

const readManifest = (missionUuid: string | null | undefined) =>
  missionUuid ? readManifestCache()[missionUuid] || null : null;

const fallbackRunUuid = () => `mission-run-${Date.now()}`;

export const useMissionOperations = (runtime: RuntimeStatus) => {
  const [mission, setMission] = useState<MissionSessionSummary | null>(null);
  const [devices, setDevices] = useState<MissionParticipant[]>([]);
  const [changes, setChanges] = useState<MissionChangeRecord[]>([]);
  const [manifest, setManifest] = useState<MissionFinalizeManifest | null>(null);
  const [copyState, setCopyState] = useState<MissionCopyState | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [copyRun, setCopyRun] = useState<CopyRunState>({
    runUuid: null,
    status: "idle",
    stage: null,
    appliedChanges: 0,
    currentBatch: 0,
    lastMissionSequence: 0,
    finalMissionSequence: null,
    error: null,
  });

  const refresh = useCallback(async () => {
    setRefreshing(true);
    setError(null);
    try {
      const currentMission = await missionApi.getCurrentMission();
      setMission(currentMission);
      setManifest(readManifest(currentMission?.uuid));

      if (!currentMission) {
        setDevices([]);
        setChanges([]);
        setCopyState(null);
        return null;
      }

      const [nextDevices, recentChanges, nextCopyState] = await Promise.all([
        missionApi.getMissionDevices(currentMission.uuid),
        missionApi.pullMissionChanges(
          currentMission.uuid,
          Math.max(0, currentMission.mission_current_sequence - 200),
          200,
        ),
        runtime.runtimeMode === "mission_client" && runtime.device?.device_uuid
          ? missionApi.getMissionCopyStatus({
              missionUuid: currentMission.uuid,
              missionServerUuid: runtime.device.device_uuid,
              missionServerUrl: runtime.activeApiSource,
            })
          : Promise.resolve(null),
      ]);

      setDevices(nextDevices);
      setChanges(recentChanges.changes);
      setCopyState(nextCopyState);
      return {
        mission: currentMission,
        devices: nextDevices,
        changes: recentChanges.changes,
        copyState: nextCopyState,
      };
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : "Impossible de charger la mission.");
      return null;
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [runtime.activeApiSource, runtime.device?.device_uuid, runtime.runtimeMode]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  useEffect(() => {
    if (runtime.runtimeMode === "standalone" && !mission) return;
    const intervalMs = copyRun.status === "running" ? 4000 : 10000;
    const interval = window.setInterval(() => {
      void refresh();
    }, intervalMs);
    return () => window.clearInterval(interval);
  }, [copyRun.status, mission, refresh, runtime.runtimeMode]);

  const finalizeMission = useCallback(
    async (missionUuid: string) => {
      const nextManifest = await missionApi.finalizeMission(missionUuid);
      persistManifest(nextManifest);
      setManifest(nextManifest);
      await refresh();
      return nextManifest;
    },
    [refresh],
  );

  const disconnectDevice = useCallback(
    async (missionUuid: string, deviceUuid: string) => {
      const result = await missionApi.disconnectMissionDevice(missionUuid, deviceUuid);
      await refresh();
      return result;
    },
    [refresh],
  );

  const revokeDevice = useCallback(
    async (missionUuid: string, deviceUuid: string) => {
      const result = await missionApi.revokeMissionDevice(missionUuid, deviceUuid);
      await refresh();
      return result;
    },
    [refresh],
  );

  const runLocalCopy = useCallback(async () => {
    if (!mission) {
      throw new Error("Aucune mission active.");
    }
    if (!runtime.device?.device_uuid) {
      throw new Error("Le serveur de mission n'est pas resolu.");
    }

    const runUuid =
      typeof crypto !== "undefined" && typeof crypto.randomUUID === "function"
        ? crypto.randomUUID()
        : fallbackRunUuid();

    let appliedChanges = 0;
    let currentBatch = 0;
    let lastSequence = copyState?.last_pulled_mission_sequence || 0;
    let finalSequence = copyState?.final_mission_sequence || mission.mission_current_sequence || null;

    setCopyRun({
      runUuid,
      status: "running",
      stage: "Connexion au serveur de mission",
      appliedChanges,
      currentBatch,
      lastMissionSequence: lastSequence,
      finalMissionSequence: finalSequence,
      error: null,
    });

    try {
      while (true) {
        currentBatch += 1;
        setCopyRun((current) => ({
          ...current,
          status: "running",
          stage: currentBatch === 1 ? "Lecture du manifeste" : "Telechargement des changements",
          currentBatch,
          lastMissionSequence: lastSequence,
          finalMissionSequence: finalSequence,
        }));

        const pulled = await missionApi.pullMissionChanges(mission.uuid, lastSequence, 100);
        finalSequence = pulled.final_sequence || finalSequence;

        setCopyRun((current) => ({
          ...current,
          stage: "Application dans PostgreSQL local",
          finalMissionSequence: finalSequence,
        }));

        const applied = await missionApi.applyMissionChangesLocally({
          mission_uuid: mission.uuid,
          mission_server_uuid: runtime.device.device_uuid,
          mission_server_url: runtime.activeApiSource,
          changes: pulled.changes,
          next_sequence: pulled.next_sequence,
          final_sequence: pulled.final_sequence,
          current_run_uuid: runUuid,
        });

        appliedChanges += pulled.changes.length;
        lastSequence = applied.last_pulled_mission_sequence;
        setCopyState(applied);
        setCopyRun((current) => ({
          ...current,
          stage:
            lastSequence >= (finalSequence || 0)
              ? "Verification finale"
              : "Mise a jour du curseur",
          appliedChanges,
          lastMissionSequence: lastSequence,
          finalMissionSequence: finalSequence,
        }));

        if (lastSequence >= (finalSequence || 0)) {
          break;
        }
      }

      setCopyRun((current) => ({
        ...current,
        status: "completed",
        stage: "Verification finale",
        error: null,
      }));
      await refresh();
    } catch (nextError) {
      const message = nextError instanceof Error ? nextError.message : "La copie a echoue.";
      setCopyRun((current) => ({
        ...current,
        status: current.lastMissionSequence > 0 ? "interrupted" : "failed",
        stage: "Telechargement des changements",
        error: message,
      }));
      throw nextError;
    }
  }, [copyState?.final_mission_sequence, copyState?.last_pulled_mission_sequence, mission, refresh, runtime.activeApiSource, runtime.device?.device_uuid]);

  const activityMetrics = useMemo(() => {
    const changesByDevice: Record<string, number> = {};
    const changesByUser: Record<string, number> = {};
    const entityCounts: Record<string, number> = {
      workers: 0,
      medical_visits: 0,
      worker_tests: 0,
      prescriptions: 0,
      aptitude_certificates: 0,
      orientation_certificates: 0,
    };

    changes.forEach((change) => {
      if (change.source_device_uuid) {
        changesByDevice[change.source_device_uuid] = (changesByDevice[change.source_device_uuid] || 0) + 1;
      }
      if (change.source_user_uuid) {
        changesByUser[change.source_user_uuid] = (changesByUser[change.source_user_uuid] || 0) + 1;
      }
      if (change.entity_type in entityCounts) {
        entityCounts[change.entity_type] += 1;
      }
    });

    return {
      workersCreated: changes.filter((item) => item.entity_type === "workers" && item.operation === "insert").length,
      visitsCreated: changes.filter((item) => item.entity_type === "medical_visits" && item.operation === "insert").length,
      testResultsUpdated: changes.filter((item) => item.entity_type === "worker_tests" && item.operation === "update").length,
      prescriptionsCreated: changes.filter((item) => item.entity_type === "prescriptions" && item.operation === "insert").length,
      certificatesCreated:
        changes.filter((item) => ["aptitude_certificates", "orientation_certificates"].includes(item.entity_type)).length,
      totalChanges: mission?.mission_current_sequence || changes.length,
      changesByDevice,
      changesByUser,
      latestActivityTime: changes[changes.length - 1]?.occurred_at || null,
      entityCounts,
    };
  }, [changes, mission?.mission_current_sequence]);

  return {
    mission,
    devices,
    changes,
    manifest,
    copyState,
    copyRun,
    activityMetrics,
    loading,
    refreshing,
    error,
    refresh,
    finalizeMission,
    disconnectDevice,
    revokeDevice,
    runLocalCopy,
  };
};
