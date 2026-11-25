import apiClient from "@/api/axios";

const PROFILE_KEY = "clinic_recovery_profile_uuid";
const DRAFT_PREFIX = "medical-folder.worker-medical-file.";
const BROWSER_KEYS = [
  "clinic_sync_queue", "clinic_sync_meta", "clinic_mission_manifest_cache",
  "clinic_central_sync_runs", "clinic_central_sync_cursor",
];
const MAX_CAPTURE_BYTES = 16 * 1024 * 1024;

export type RecoverySourceSummary = {
  uuid: string;
  source_kind: string;
  source_identity_present: boolean;
  format_version: number;
  sha256: string;
  byte_length: number;
  parent_source_uuid: string | null;
  state: "captured" | "recorded" | "needs_review";
  reason_code: string | null;
  item_count: number;
  materialized_count: number;
  captured_at: string;
};

const getProfileId = (): string => {
  const existing = window.localStorage.getItem(PROFILE_KEY);
  if (existing) return existing;
  const created = crypto.randomUUID();
  window.localStorage.setItem(PROFILE_KEY, created); // New recovery key; old keys stay untouched.
  return created;
};

export const readLegacyBrowserSnapshot = (storage: Storage) => {
  const entries: Record<string, string> = {};
  for (let index = 0; index < storage.length; index += 1) {
    const key = storage.key(index);
    if (!key || (key !== "clinic_sync_queue" && key !== "clinic_sync_meta" &&
                 !key.startsWith(DRAFT_PREFIX) && !key.startsWith("medical_visit_pending_operation:") && !BROWSER_KEYS.includes(key))) continue;
    const value = storage.getItem(key);
    if (value !== null) entries[key] = value;
  }
  return entries;
};

const sha256 = async (raw: string) => {
  const bytes = new TextEncoder().encode(raw);
  if (bytes.length > MAX_CAPTURE_BYTES) throw new Error("RECOVERY_CAPTURE_SIZE_INVALID");
  const hash = await crypto.subtle.digest("SHA-256", bytes);
  return Array.from(new Uint8Array(hash), (byte) => byte.toString(16).padStart(2, "0")).join("");
};

const deviceIdFrom = (entries: Record<string, string>): string | null => {
  try {
    const value = JSON.parse(entries.clinic_sync_meta || "null") as { device_id?: unknown } | null;
    return typeof value?.device_id === "string" ? value.device_id : null;
  } catch {
    return null;
  }
};

export const legacyRecovery = {
  async captureBrowser(): Promise<RecoverySourceSummary> {
    const profileId = getProfileId();
    const entries = readLegacyBrowserSnapshot(window.localStorage);
    if (!Object.keys(entries).length) throw new Error("RECOVERY_NO_BROWSER_SOURCE");
    const raw_payload = JSON.stringify({ entries });
    const source_identity = deviceIdFrom(entries);
    const hash = await sha256(raw_payload);
    const secondRead = readLegacyBrowserSnapshot(window.localStorage);
    if (JSON.stringify(secondRead) !== JSON.stringify(entries)) {
      throw new Error("RECOVERY_SOURCE_CHANGED_DURING_CAPTURE");
    }
    const { data } = await apiClient.post<RecoverySourceSummary>("/recovery/sources", {
      source_kind: "browser_local_storage", logical_key: "clinic-working-data",
      profile_id: profileId, source_identity, format_version: 1, sha256: hash, raw_payload,
    });
    return data;
  },
  async capturePackage(file: File): Promise<RecoverySourceSummary> {
    if (file.size > MAX_CAPTURE_BYTES) throw new Error("RECOVERY_CAPTURE_SIZE_INVALID");
    const raw_payload = await file.text();
    const hash = await sha256(raw_payload);
    let claimedSource: string | null = null;
    try {
      const parsed = JSON.parse(raw_payload) as { server_id?: unknown };
      if (typeof parsed.server_id === "string") claimedSource = `claimed-package-server:${parsed.server_id}`;
    } catch {
      // The original malformed file can still be captured for review.
    }
    // The package's public server ID is a claim, never proof of this device's identity.
    const { data } = await apiClient.post<RecoverySourceSummary>("/recovery/sources", {
      source_kind: "legacy_package", logical_key: file.name,
      profile_id: getProfileId(), source_identity: claimedSource,
      format_version: 1, sha256: hash, raw_payload,
    });
    return data;
  },
  async listSources() {
    const { data } = await apiClient.get<{ sources: RecoverySourceSummary[]; limited_to: number }>("/recovery/sources");
    return data;
  },
  async resume(sourceUuid: string) {
    const { data } = await apiClient.post<RecoverySourceSummary>(`/recovery/sources/${sourceUuid}/resume`);
    return data;
  },
  async listItemStatuses(sourceUuid: string, after = -1) {
    const { data } = await apiClient.get<{ source: RecoverySourceSummary; items: Array<{ ordinal: number; state: string; reason_code: string | null; entity_type: string | null }>; has_more: boolean }>(
      `/recovery/sources/${sourceUuid}/items`, { params: { after } },
    );
    return data;
  },
  async captureJournalPage(table: string, afterId = 0) {
    const { data } = await apiClient.post<{ captured: boolean; source?: RecoverySourceSummary; next_after_id: number; has_more: boolean }>(
      `/recovery/journals/${table}/capture`, null, { params: { after_id: afterId } },
    );
    return data;
  },
};
