import { isSafetySuspension, SYNC_SAFETY_MESSAGE } from "@/services/syncSafety";
import { useCallback, useEffect, useMemo, useState } from "react";

import { centralSyncApi } from "@/api/centralSyncApi";
import { missionApi } from "@/api/missionApi";
import type { AuthUser } from "@/types/auth";
import type {
  CentralApplyRequest,
  CentralBootstrapManifest,
  CentralCapabilities,
  CentralConflictRecord,
  CentralConflictResolutionType,
  CentralPulledChange,
  CentralReadiness,
  CentralServerInfo,
  CentralSyncCounts,
  CentralSyncRunRecord,
  CentralSyncState,
  CentralSyncSummary,
  DataIntegrityStatus,
  InfrastructureTimelineEvent,
  StoredCentralServerIdentity,
} from "@/types/centralSync";
import type { MissionChangesResponse, MissionFinalizeManifest, MissionSessionSummary, RuntimeStatus } from "@/types/mission";
import { centralSyncStorage } from "@/utils/storage";

const MANIFEST_STORAGE_KEY = "clinic_mission_manifest_cache";

const readManifestCache = (): Record<string, MissionFinalizeManifest> => {
  if (typeof window === "undefined") return {};
  try {
    const raw = window.localStorage.getItem(MANIFEST_STORAGE_KEY);
    return raw ? (JSON.parse(raw) as Record<string, MissionFinalizeManifest>) : {};
  } catch {
    return {};
  }
};

const readManifest = (missionUuid: string | null | undefined) =>
  missionUuid ? readManifestCache()[missionUuid] || null : null;

const createRunUuid = () =>
  typeof crypto !== "undefined" && typeof crypto.randomUUID === "function"
    ? crypto.randomUUID()
    : `central-run-${Date.now()}`;

const errorCodeMap: Array<[string, string]> = [
  ["CENTRAL_SERVER_UNREACHABLE", "Serveur central inaccessible."],
  ["CENTRAL_SERVER_IDENTITY_MISMATCH", "L'identite du serveur central ne correspond pas a celle deja approuvee."],
  ["CENTRAL_GENERATION_MISMATCH", "La generation du serveur central a change et doit etre reverifiee."],
  ["MISSION_NOT_FINALIZED", "La mission doit etre finalisee avant la centralisation."],
  ["MISSION_JOURNAL_INCOMPLETE", "Le journal de mission est incomplet."],
  ["SCHEMA_MISMATCH", "La revision de schema est incompatible avec le serveur central."],
  ["PROTOCOL_MISMATCH", "Le protocole de synchronisation n'est pas compatible."],
  ["DEVICE_REVOKED", "Cet appareil a ete revoque pour la centralisation."],
  ["UNSENT_CHANGES", "Des changements non centralises existent deja sur ce poste."],
  ["CONFLICT", "Des conflits de centralisation ont ete detectes."],
  ["PAYLOAD_REJECTED", "Une partie du contenu a ete rejetee par le serveur central."],
  ["CURSOR_INVALID", "Le curseur de synchronisation local est invalide."],
  ["BOOTSTRAP_CHECKSUM_FAILED", "Le checksum du bootstrap ne correspond pas."],
  ["BOOTSTRAP_RESTORE_FAILED", "La restauration du bootstrap a echoue."],
  ["DATA_INTEGRITY_FAILED", "Le controle d'integrite a echoue."],
];

const translateCentralError = (error: unknown) => {
  if (isSafetySuspension(error)) return SYNC_SAFETY_MESSAGE;
  const message =
    error instanceof Error
      ? error.message
      : typeof error === "string"
        ? error
        : "Operation impossible avec le serveur central.";
  const mapped = errorCodeMap.find(([code]) => message.includes(code));
  return mapped?.[1] || message;
};

const isMandatoryReadinessFailure = (key: string) =>
  !["required_files_present"].includes(key);

const buildEmptyCounts = (): CentralSyncCounts => ({
  pending: 0,
  sent: 0,
  accepted: 0,
  duplicates: 0,
  autoMerged: 0,
  conflicts: 0,
  rejected: 0,
  pulled: 0,
  applied: 0,
});

const initialSummary: CentralSyncSummary = {
  status: "never_submitted",
  firstCentralSequence: null,
  lastCentralSequence: null,
  centralizedAt: null,
  acceptedCount: 0,
  conflictCount: 0,
  rejectedCount: 0,
};

const initialBootstrapStages = [
  "Sauvegarde locale de securite",
  "Telechargement",
  "Validation du checksum",
  "Restauration temporaire",
  "Verification du schema",
  "Verification des UUID",
  "Verification des relations",
  "Activation de la base",
  "Telechargement des changements recents",
];

export const useCentralSync = (runtime: RuntimeStatus, currentUser: AuthUser | null) => {
  const [serverUrl, setServerUrl] = useState("");
  const [deviceSecret, setDeviceSecret] = useState(centralSyncStorage.getDeviceSecret() || "");
  const [remoteServerInfo, setRemoteServerInfo] = useState<CentralServerInfo | null>(null);
  const [remoteCapabilities, setRemoteCapabilities] = useState<CentralCapabilities | null>(null);
  const [localServerInfo, setLocalServerInfo] = useState<CentralServerInfo | null>(null);
  const [readiness, setReadiness] = useState<CentralReadiness | null>(null);
  const [integrity, setIntegrity] = useState<DataIntegrityStatus | null>(null);
  const [conflicts, setConflicts] = useState<CentralConflictRecord[]>([]);
  const [syncState, setSyncState] = useState<CentralSyncState>("idle");
  const [syncCounts, setSyncCounts] = useState<CentralSyncCounts>(buildEmptyCounts());
  const [syncSummary, setSyncSummary] = useState<CentralSyncSummary>(initialSummary);
  const [syncSteps, setSyncSteps] = useState<Record<string, "idle" | "running" | "completed" | "failed">>({
    server: "idle",
    auth: "idle",
    push: "idle",
    dedupe: "idle",
    conflict: "idle",
    pull: "idle",
    apply: "idle",
    verify: "idle",
  });
  const [syncError, setSyncError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [storedIdentity, setStoredIdentity] = useState<StoredCentralServerIdentity | null>(
    centralSyncStorage.getServerIdentity<StoredCentralServerIdentity>(),
  );
  const [pendingIdentity, setPendingIdentity] = useState<StoredCentralServerIdentity | null>(null);
  const [runs, setRuns] = useState<CentralSyncRunRecord[]>(
    centralSyncStorage.getRuns<CentralSyncRunRecord[]>(),
  );
  const [timeline, setTimeline] = useState<InfrastructureTimelineEvent[]>(
    centralSyncStorage.getInfrastructureHistory<InfrastructureTimelineEvent[]>(),
  );
  const [bootstrapManifest, setBootstrapManifest] = useState<CentralBootstrapManifest | null>(null);
  const [bootstrapUuid, setBootstrapUuid] = useState<string | null>(null);
  const [bootstrapStageStatuses, setBootstrapStageStatuses] = useState<Record<string, "idle" | "running" | "completed" | "failed" | "unavailable">>(
    Object.fromEntries(initialBootstrapStages.map((stage) => [stage, "idle"])),
  );
  const [bootstrapError, setBootstrapError] = useState<string | null>(null);
  const [lastContactAt, setLastContactAt] = useState<string | null>(null);
  const [currentMission, setCurrentMission] = useState<MissionSessionSummary | null>(null);
  const [missionManifest, setMissionManifest] = useState<MissionFinalizeManifest | null>(null);
  const [latestKnownCentralSequence, setLatestKnownCentralSequence] = useState<number>(centralSyncApi.getStoredCursor());

  const appendRun = useCallback((record: CentralSyncRunRecord) => {
    setRuns((current) => {
      const next = [record, ...current].slice(0, 30);
      centralSyncStorage.setRuns(next);
      return next;
    });
  }, []);

  const appendTimeline = useCallback((event: Omit<InfrastructureTimelineEvent, "id" | "occurred_at">) => {
    setTimeline((current) => {
      const nextEvent: InfrastructureTimelineEvent = {
        id: createRunUuid(),
        occurred_at: new Date().toISOString(),
        ...event,
      };
      const next = [nextEvent, ...current].slice(0, 40);
      centralSyncStorage.setInfrastructureHistory(next);
      return next;
    });
  }, []);

  const setStep = useCallback((key: keyof typeof syncSteps, value: "idle" | "running" | "completed" | "failed") => {
    setSyncSteps((current) => ({ ...current, [key]: value }));
  }, [syncSteps]);

  const refresh = useCallback(async () => {
    setRefreshing(true);
    setSyncError(null);
    try {
      const mission = await missionApi.getCurrentMission();
      setCurrentMission(mission);
      setMissionManifest(readManifest(mission?.uuid));

      const [localInfo, readinessResult, integrityResult, conflictsResult] = await Promise.all([
        centralSyncApi.getLocalServerInfo().catch(() => null),
        centralSyncApi.getReadiness().catch(() => null),
        centralSyncApi.getDataIntegrity().catch(() => null),
        centralSyncApi.listConflicts().catch(() => []),
      ]);
      setLocalServerInfo(localInfo);
      setReadiness(readinessResult);
      setIntegrity(integrityResult);
      setConflicts(conflictsResult);

      if (serverUrl.trim()) {
        const [serverInfo, capabilities] = await Promise.all([
          centralSyncApi.getRemoteServerInfo(serverUrl),
          centralSyncApi.getRemoteCapabilities(serverUrl),
        ]);
        setRemoteServerInfo(serverInfo);
        setRemoteCapabilities(capabilities);
        setLastContactAt(new Date().toISOString());

        if (
          storedIdentity &&
          (storedIdentity.serverUuid !== serverInfo.server_uuid || storedIdentity.generationUuid !== serverInfo.server_generation_uuid)
        ) {
          setPendingIdentity({
            serverUrl,
            serverUuid: serverInfo.server_uuid,
            generationUuid: serverInfo.server_generation_uuid,
            verifiedAt: new Date().toISOString(),
            verifiedByUserId: currentUser?.id || null,
          });
        }
      } else {
        setRemoteServerInfo(null);
        setRemoteCapabilities(null);
      }
    } catch (error) {
      setSyncError(translateCentralError(error));
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [currentUser?.id, serverUrl, storedIdentity]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  useEffect(() => {
    if (!serverUrl.trim()) return;
    const timeout = window.setTimeout(() => {
      void refresh();
    }, 200);
    return () => window.clearTimeout(timeout);
  }, [refresh, serverUrl]);

  const testConnection = useCallback(async () => {
    if (!serverUrl.trim()) {
      throw new Error("CENTRAL_SERVER_UNREACHABLE");
    }
    const [serverInfo, capabilities] = await Promise.all([
      centralSyncApi.getRemoteServerInfo(serverUrl),
      centralSyncApi.getRemoteCapabilities(serverUrl),
    ]);
    setRemoteServerInfo(serverInfo);
    setRemoteCapabilities(capabilities);
    setLastContactAt(new Date().toISOString());
    if (
      storedIdentity &&
      (storedIdentity.serverUuid !== serverInfo.server_uuid || storedIdentity.generationUuid !== serverInfo.server_generation_uuid)
    ) {
      setPendingIdentity({
        serverUrl,
        serverUuid: serverInfo.server_uuid,
        generationUuid: serverInfo.server_generation_uuid,
        verifiedAt: new Date().toISOString(),
        verifiedByUserId: currentUser?.id || null,
      });
      throw new Error("CENTRAL_GENERATION_MISMATCH");
    }
    return { serverInfo, capabilities };
  }, [currentUser?.id, serverUrl, storedIdentity]);

  const verifyServerIdentity = useCallback(() => {
    if (!remoteServerInfo) {
      throw new Error("CENTRAL_SERVER_IDENTITY_MISMATCH");
    }
    const nextIdentity: StoredCentralServerIdentity = {
      serverUrl,
      serverUuid: remoteServerInfo.server_uuid,
      generationUuid: remoteServerInfo.server_generation_uuid,
      verifiedAt: new Date().toISOString(),
      verifiedByUserId: currentUser?.id || null,
    };
    centralSyncStorage.setServerIdentity(nextIdentity);
    setStoredIdentity(nextIdentity);
    setPendingIdentity(null);
    appendTimeline({
      type: "server_identity_verified",
      title: "Identite du serveur central verifiee",
      description: `${remoteServerInfo.server_uuid.slice(0, 8)}...`,
      tone: "active",
    });
  }, [appendTimeline, currentUser?.id, remoteServerInfo, serverUrl]);

  const collectMissionChanges = useCallback(async (missionUuid: string) => {
    const collected: CentralPulledChange[] = [];
    let afterSequence = 0;
    let result: MissionChangesResponse | null = null;
    do {
      result = await missionApi.pullMissionChanges(missionUuid, afterSequence, 250);
      collected.push(
        ...result.changes.map((item) => ({
          change_uuid: item.change_uuid,
          entity_type: item.entity_type,
          entity_uuid: item.entity_uuid,
          operation: item.operation,
          base_version: Math.max(0, item.entity_version - 1),
          entity_version: item.entity_version,
          changed_fields: item.changed_fields || [],
          payload: item.payload,
          source_device_uuid: item.source_device_uuid,
          source_user_uuid: item.source_user_uuid,
          mission_session_uuid: item.mission_session_uuid,
          mission_sequence: item.mission_sequence,
          central_server_uuid: null,
          central_sequence: 0,
          central_status: null,
          central_finalized_at: null,
        })),
      );
      afterSequence = result.next_sequence;
    } while (result.has_more);
    return { changes: collected, manifestChecksum: result?.manifest_checksum || null };
  }, []);

  const pullAndApplyCentral = useCallback(async (runUuid: string, baseCursor?: number) => {
    if (!serverUrl.trim()) {
      throw new Error("CENTRAL_SERVER_UNREACHABLE");
    }
    const afterSequence = baseCursor ?? centralSyncApi.getStoredCursor();
    setSyncState("pulling");
    setStep("pull", "running");
    const pull = await centralSyncApi.pullCentralChanges(serverUrl, afterSequence, 500);
    setLatestKnownCentralSequence(pull.next_central_sequence);
    setSyncCounts((current) => ({ ...current, pulled: pull.changes.length }));
    setStep("pull", "completed");

    setSyncState("applying");
    setStep("apply", "running");
    const applyPayload: CentralApplyRequest = {
      central_server_uuid: pull.central_server_uuid,
      central_generation_uuid: pull.central_generation_uuid,
      changes: pull.changes,
      next_central_sequence: pull.next_central_sequence,
      final_central_sequence: pull.next_central_sequence,
      current_run_uuid: runUuid,
    };
    const applied = await centralSyncApi.applyCentralChanges(applyPayload);
    centralSyncApi.setStoredCursor(applied.last_pulled_sequence);
    setLatestKnownCentralSequence(applied.last_pulled_sequence);
    setSyncCounts((current) => ({ ...current, applied: pull.changes.length }));
    setStep("apply", "completed");
    return { pull, applied };
  }, [serverUrl, setStep]);

  const runCentralSynchronization = useCallback(async () => {
    const runUuid = createRunUuid();
    const startedAt = new Date().toISOString();
    setSyncError(null);
    setSyncCounts(buildEmptyCounts());
    setSyncSummary(initialSummary);
    setSyncSteps({
      server: "idle",
      auth: "idle",
      push: "idle",
      dedupe: "idle",
      conflict: "idle",
      pull: "idle",
      apply: "idle",
      verify: "idle",
    });

    try {
      setSyncState("checking");
      setStep("server", "running");
      await testConnection();
      setStep("server", "completed");

      if (pendingIdentity) {
        setSyncState("not_ready");
        throw new Error("CENTRAL_GENERATION_MISMATCH");
      }

      const readinessResult = await centralSyncApi.getReadiness();
      setReadiness(readinessResult);
      const blockingFailure = readinessResult.checks.some((check) => check.status === "failed" && isMandatoryReadinessFailure(check.key));
      if (blockingFailure) {
        setSyncState("not_ready");
        throw new Error("MISSION_NOT_FINALIZED");
      }

      if (!currentMission?.uuid) {
        throw new Error("MISSION_NOT_FINALIZED");
      }
      const manifest = readManifest(currentMission.uuid);
      if (!manifest?.checksum) {
        throw new Error("MISSION_JOURNAL_INCOMPLETE");
      }
      setMissionManifest(manifest);

      setStep("auth", "running");
      if (!deviceSecret.trim()) {
        throw new Error("DEVICE_REVOKED");
      }
      setStep("auth", "completed");

      const missionBatch = await collectMissionChanges(currentMission.uuid);
      setSyncCounts((current) => ({ ...current, pending: missionBatch.changes.length, sent: missionBatch.changes.length }));

      setSyncState("pushing");
      setStep("push", "running");
      const pushResult = await centralSyncApi.pushMission(
        serverUrl,
        {
          batch_uuid: runUuid,
          device_uuid: runtime.device?.device_uuid || "",
          mission_uuid: currentMission.uuid,
          mission_manifest_checksum: manifest.checksum,
          base_central_sequence: missionManifest?.base_central_sequence ?? 0,
          changes: missionBatch.changes.map((item) => ({
            change_uuid: item.change_uuid,
            mission_sequence: item.mission_sequence,
            entity_type: item.entity_type,
            entity_uuid: item.entity_uuid,
            operation: item.operation,
            base_version: item.base_version,
            entity_version: item.entity_version,
            changed_fields: item.changed_fields,
            source_device_uuid: item.source_device_uuid,
            source_user_uuid: item.source_user_uuid,
            payload: item.payload,
          })),
        },
        deviceSecret,
      );
      setStep("push", "completed");
      setStep("dedupe", "completed");
      setStep("conflict", pushResult.conflicts.length > 0 ? "failed" : "completed");
      setSyncCounts((current) => ({
        ...current,
        accepted: pushResult.accepted.length,
        duplicates: pushResult.duplicates.length,
        autoMerged: pushResult.auto_merged.length,
        conflicts: pushResult.conflicts.length,
        rejected: pushResult.rejected.length,
      }));

      const firstSequence = pushResult.central_sequence;
      const { pull } = await pullAndApplyCentral(runUuid);

      setSyncState(pushResult.conflicts.length > 0 ? "completed_with_conflicts" : "completed");
      setStep("verify", "running");
      const integrityResult = await centralSyncApi.getDataIntegrity();
      setIntegrity(integrityResult);
      setStep("verify", "completed");

      const completedAt = new Date().toISOString();
      setSyncSummary({
        status: pushResult.conflicts.length > 0 ? "centralized_with_conflicts" : "centralized",
        firstCentralSequence: firstSequence,
        lastCentralSequence: pull.next_central_sequence,
        centralizedAt: completedAt,
        acceptedCount: pushResult.accepted.length,
        conflictCount: pushResult.conflicts.length,
        rejectedCount: pushResult.rejected.length,
      });

      appendRun({
        uuid: runUuid,
        direction: "mission_to_central_push",
        status: pushResult.conflicts.length > 0 ? "completed_with_conflicts" : "completed",
        mission_uuid: currentMission.uuid,
        device_code: runtime.device?.device_code || null,
        started_at: startedAt,
        completed_at: completedAt,
        duration_ms: new Date(completedAt).getTime() - new Date(startedAt).getTime(),
        counts: {
          pending: missionBatch.changes.length,
          sent: missionBatch.changes.length,
          accepted: pushResult.accepted.length,
          duplicates: pushResult.duplicates.length,
          autoMerged: pushResult.auto_merged.length,
          conflicts: pushResult.conflicts.length,
          rejected: pushResult.rejected.length,
          pulled: pull.changes.length,
          applied: pull.changes.length,
        },
        cursor_start: missionManifest?.base_central_sequence ?? 0,
        cursor_end: pull.next_central_sequence,
        error_code: null,
        error_message: null,
        server_url: serverUrl,
      });
      appendTimeline({
        type: "mission_submitted_centrally",
        title: "Mission envoyee au serveur central",
        description: `${pushResult.accepted.length} changements acceptes`,
        tone: pushResult.conflicts.length > 0 ? "pending" : "active",
      });
      appendTimeline({
        type: "centralization_completed",
        title: pushResult.conflicts.length > 0 ? "Centralisation terminee avec conflits" : "Centralisation terminee",
        description: `Sequence finale ${pull.next_central_sequence}`,
        tone: pushResult.conflicts.length > 0 ? "pending" : "active",
      });
      await refresh();
    } catch (error) {
      const translated = translateCentralError(error);
      setSyncError(translated);
      setSyncState("failed");
      appendRun({
        uuid: runUuid,
        direction: "mission_to_central_push",
        status: "failed",
        mission_uuid: currentMission?.uuid || null,
        device_code: runtime.device?.device_code || null,
        started_at: startedAt,
        completed_at: new Date().toISOString(),
        duration_ms: null,
        counts: syncCounts,
        cursor_start: latestKnownCentralSequence,
        cursor_end: latestKnownCentralSequence,
        error_code: translated,
        error_message: translated,
        server_url: serverUrl,
      });
      throw error;
    }
  }, [
    appendRun,
    appendTimeline,
    collectMissionChanges,
    currentMission,
    deviceSecret,
    latestKnownCentralSequence,
    missionManifest?.base_central_sequence,
    pendingIdentity,
    pullAndApplyCentral,
    refresh,
    runtime.device?.device_code,
    runtime.device?.device_uuid,
    serverUrl,
    setStep,
    syncCounts,
    testConnection,
  ]);

  const updateFromCentral = useCallback(async () => {
    const runUuid = createRunUuid();
    const startedAt = new Date().toISOString();
    setSyncError(null);
    setSyncCounts(buildEmptyCounts());
    try {
      await testConnection();
      const { pull } = await pullAndApplyCentral(runUuid);
      setSyncState("completed");
      appendRun({
        uuid: runUuid,
        direction: "central_to_mobile_pull",
        status: "completed",
        mission_uuid: currentMission?.uuid || null,
        device_code: runtime.device?.device_code || null,
        started_at: startedAt,
        completed_at: new Date().toISOString(),
        duration_ms: null,
        counts: { ...buildEmptyCounts(), pulled: pull.changes.length, applied: pull.changes.length },
        cursor_start: latestKnownCentralSequence,
        cursor_end: pull.next_central_sequence,
        error_code: null,
        error_message: null,
        server_url: serverUrl,
      });
      appendTimeline({
        type: "centralization_completed",
        title: "Mise a jour locale depuis le central",
        description: `${pull.changes.length} changements appliques`,
        tone: "active",
      });
      await refresh();
    } catch (error) {
      setSyncState("failed");
      setSyncError(translateCentralError(error));
      throw error;
    }
  }, [appendRun, appendTimeline, currentMission?.uuid, latestKnownCentralSequence, pullAndApplyCentral, refresh, runtime.device?.device_code, serverUrl, testConnection]);

  const resolveConflict = useCallback(async (conflictUuid: string, resolutionType: CentralConflictResolutionType, resolvedPayload: Record<string, unknown> | null, reason?: string) => {
    const result = await centralSyncApi.resolveConflict(conflictUuid, resolutionType, resolvedPayload);
    appendTimeline({
      type: "conflict_resolved",
      title: "Conflit central resolu",
      description: reason || resolutionType,
      tone: "active",
    });
    await refresh();
    return result;
  }, [appendTimeline, refresh]);

  const runBootstrap = useCallback(async (allowOverwriteWithoutUnsentWork: boolean) => {
    if (!runtime.device?.device_uuid) {
      throw new Error("UNSENT_CHANGES");
    }
    setBootstrapError(null);
    setBootstrapStageStatuses(Object.fromEntries(initialBootstrapStages.map((stage) => [stage, "idle"])));

    const setBootstrapStage = (stage: string, status: "idle" | "running" | "completed" | "failed" | "unavailable") =>
      setBootstrapStageStatuses((current) => ({ ...current, [stage]: status }));

    try {
      const request = await centralSyncApi.requestBootstrap({
        device_uuid: runtime.device.device_uuid,
        allow_overwrite_without_unsent_work: allowOverwriteWithoutUnsentWork,
      });
      setBootstrapUuid(request.bootstrap_uuid);
      setBootstrapStage("Telechargement", "running");
      const manifest = await centralSyncApi.getBootstrapManifest(request.bootstrap_uuid);
      setBootstrapManifest(manifest);
      setBootstrapStage("Telechargement", "completed");

      setBootstrapStage("Validation du checksum", "running");
      const download = await centralSyncApi.downloadBootstrap(request.bootstrap_uuid);
      const checksumMatches = download.checksum === manifest.checksum;
      if (!checksumMatches) {
        setBootstrapStage("Validation du checksum", "failed");
        throw new Error("BOOTSTRAP_CHECKSUM_FAILED");
      }
      setBootstrapStage("Validation du checksum", "completed");

      ["Sauvegarde locale de securite", "Restauration temporaire", "Verification du schema", "Verification des UUID", "Verification des relations", "Activation de la base", "Telechargement des changements recents"].forEach(
        (stage) => setBootstrapStage(stage, "unavailable"),
      );
      await centralSyncApi.completeBootstrap(request.bootstrap_uuid, true, "Workflow UI execute.");
      appendRun({
        uuid: request.bootstrap_uuid,
        direction: "bootstrap",
        status: "completed",
        mission_uuid: currentMission?.uuid || null,
        device_code: runtime.device.device_code || null,
        started_at: new Date().toISOString(),
        completed_at: new Date().toISOString(),
        duration_ms: null,
        counts: buildEmptyCounts(),
        cursor_start: latestKnownCentralSequence,
        cursor_end: manifest.snapshot_central_sequence,
        error_code: null,
        error_message: null,
        server_url: serverUrl,
      });
      appendTimeline({
        type: "bootstrap_completed",
        title: "Bootstrap initialise",
        description: `Snapshot ${manifest.snapshot_central_sequence}`,
        tone: "active",
      });
      await refresh();
    } catch (error) {
      const translated = translateCentralError(error);
      setBootstrapError(translated);
      throw error;
    }
  }, [appendRun, appendTimeline, currentMission?.uuid, latestKnownCentralSequence, refresh, runtime.device?.device_code, runtime.device?.device_uuid, serverUrl]);

  const mandatoryReadinessFailures = useMemo(
    () => readiness?.checks.filter((check) => check.status === "failed" && isMandatoryReadinessFailure(check.key)) || [],
    [readiness],
  );

  return {
    serverUrl,
    setServerUrl,
    deviceSecret,
    setDeviceSecret: (value: string) => {
      setDeviceSecret(value);
      if (value.trim()) {
        centralSyncStorage.setDeviceSecret(value);
      } else {
        centralSyncStorage.clearDeviceSecret();
      }
    },
    remoteServerInfo,
    remoteCapabilities,
    localServerInfo,
    readiness,
    integrity,
    conflicts,
    syncState,
    syncCounts,
    syncSummary,
    syncSteps,
    syncError,
    loading,
    refreshing,
    storedIdentity,
    pendingIdentity,
    runs,
    timeline,
    bootstrapManifest,
    bootstrapUuid,
    bootstrapStageStatuses,
    bootstrapError,
    lastContactAt,
    currentMission,
    missionManifest,
    latestKnownCentralSequence,
    mandatoryReadinessFailures,
    refresh,
    testConnection,
    verifyServerIdentity,
    runCentralSynchronization,
    updateFromCentral,
    resolveConflict,
    runBootstrap,
  };
};
