// Execute actual TypeScript modules with isolated storage/network/desktop substitutes.
import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import vm from "node:vm";
import ts from "typescript";

const src = new URL("../src/", import.meta.url);
function load(name, dependencies = {}, globals = {}) {
  const source = fs.readFileSync(new URL(name, src), "utf8");
  const code = ts.transpileModule(source, {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
  }).outputText;
  const exports = {};
  vm.runInNewContext(code, {
    exports,
    require: (key) => {
      assert.ok(key in dependencies, `Unexpected dependency: ${key}`);
      return dependencies[key];
    },
    ...globals,
  }, { filename: name });
  return exports;
}
const safety = load("services/syncSafety.ts");

test("legacy sync never sends or clears storage, including concurrent enqueue", async () => {
  let persistedQueue = { workers: [{ uuid: "original" }] };
  let writes = 0, sends = 0;
  const storage = { syncStorage: {
    getQueue: () => persistedQueue,
    getMeta: () => ({ device_id: "existing-device" }),
    setMeta: () => assert.fail("Existing device metadata must not change"),
    setQueue: (queue) => { writes++; persistedQueue = queue; },
  } };
  let state;
  load("store/syncStore.ts", {
    "zustand": { create: (initialize) => {
      state = initialize((next) => Object.assign(state, next), () => state);
      return { getState: () => state };
    } },
    "@/utils/storage": storage,
  }, { navigator: { onLine: true } });
  const service = load("services/syncService.ts", {
    "./syncSafety": safety,
    "@/utils/storage": storage,
    "@/api/syncApi": { syncApi: { push: async () => { sends++; return { success: true }; } } },
    "@/store/syncStore": { useSyncStore: { getState: () => state } },
  }).syncService;
  // No network/store dependency is allowed: a fake success cannot acknowledge anything.
  const attempt = service.syncNow();
  state.enqueue("workers", { uuid: "added-during-attempt" });
  await assert.rejects(attempt, (e) => e.code === safety.SYNC_SAFETY_CODE && e.retryable === false);
  await assert.rejects(service.syncNow(), (e) => e.code === safety.SYNC_SAFETY_CODE);
  await assert.rejects(service.resolveConflict({}), (e) => e.code === safety.SYNC_SAFETY_CODE);
  assert.equal(persistedQueue.workers.length, 2);
  assert.equal(persistedQueue.workers[0].uuid, "original");
  assert.equal(writes, 1); // Only the user's enqueue, never an automatic clear.
  assert.equal(sends, 0);
});

test("mount and network recovery only read status, never retry sync", async () => {
  const effects = [];
  const listeners = new Map();
  let sends = 0, reads = 0;
  const hook = load("hooks/useSync.ts", {
    react: { useEffect: (fn) => effects.push(fn) },
    "@/services/syncService": { syncService: { syncNow: () => sends++, resolveConflict: () => {} } },
    "@/api/syncApi": { syncApi: { getStatus: async () => { reads++; return {}; } } },
    "@/store/syncStore": { useSyncStore: (select) => select({ setOnline() {}, setStatus() {} }) },
  }, { window: { addEventListener: (name, fn) => listeners.set(name, fn), removeEventListener() {} } });
  hook.useSync();
  effects.forEach((effect) => effect());
  listeners.get("online")();
  listeners.get("offline")();
  listeners.get("online")();
  await Promise.resolve();
  assert.equal(sends, 0);
  assert.equal(reads, 1);
});

test("Tauri resolved command with success=false rejects before caller success/list update", async () => {
  let command;
  const desktop = load("desktop/tauriRuntime.ts", {
    "../services/syncSafety": safety,
    "@/api/axios": {},
    "@/config/runtime": { getTauriInvoke: () => async (name) => {
      command = name;
      return { success: false, operationState: safety.SYNC_SAFETY_CODE, message: "suspended", backup: null };
    } },
  }).tauriRuntime;
  let displayedSuccess = false;
  const validBackups = [];
  await assert.rejects(async () => {
    const result = await desktop.createPostgresBackup();
    displayedSuccess = true;
    validBackups.push(result.backup);
  }, (e) => e.code === safety.SYNC_SAFETY_CODE && e.retryable === false);
  assert.equal(command, "create_postgres_backup");
  assert.equal(displayedSuccess, false);
  assert.equal(validBackups.length, 0);
});

test("desktop failure/null and HTTP safety errors stay distinguishable from connectivity", () => {
  assert.throws(() => safety.requireSuccessfulDesktopOperation(null));
  assert.throws(() => safety.requireSuccessfulDesktopOperation({ success: false, message: "failed" }));
  const good = { success: true, message: "verified" };
  assert.equal(safety.requireSuccessfulDesktopOperation(good), good);
  assert.equal(safety.isSafetySuspension({ response: { data: { details: { code: safety.SYNC_SAFETY_CODE } } } }), true);
  assert.equal(safety.isSafetySuspension(new Error("Network error")), false);
});

test("Axios safety rejection bypasses refresh/retry even with a 401 transport status", async () => {
  let rejectHandler, retries = 0;
  const axios = {
    create: () => ({ interceptors: {
      request: { use() {} },
      response: { use(_ok, rejected) { rejectHandler = rejected; } },
    } }),
    post: () => { retries++; throw new Error("Unexpected retry"); },
  };
  load("api/axios.ts", {
    axios: { default: axios },
    "../services/syncSafety": safety,
    "@/config/env": { env: { apiBaseUrl: "http://unused.invalid" } },
    "@/config/runtime": {},
    "@/utils/storage": {},
  });
  await assert.rejects(rejectHandler({ config: {}, response: {
    status: 401, data: { details: { code: safety.SYNC_SAFETY_CODE } },
  } }), (e) => e.code === safety.SYNC_SAFETY_CODE && e.retryable === false);
  assert.equal(retries, 0);
});

test("direct central and mission clients preserve non-retryable suspension", async () => {
  let calls = 0;
  const dependencies = {
    "../services/syncSafety": safety,
    axios: { default: { create: () => ({ post: async () => {
      calls++;
      throw { response: { data: { details: { code: safety.SYNC_SAFETY_CODE } } } };
    } }) } },
    "@/api/axios": {},
    "@/config/runtime": { LOCAL_SERVER_API_BASE_URL: "http://unused.invalid", normalizeApiBaseUrl: (s) => s },
    "@/utils/storage": { tokenStorage: { getAccessToken: () => null }, missionStorage: { getCredential: () => null } },
  };
  const central = load("api/centralSyncApi.ts", dependencies).centralSyncApi;
  const mission = load("api/missionApi.ts", dependencies).missionApi;
  for (const operation of [() => central.applyCentralChanges({}), () => mission.applyMissionChangesLocally({})]) {
    await assert.rejects(operation, (e) => e.code === safety.SYNC_SAFETY_CODE && e.retryable === false);
  }
  assert.equal(calls, 2); // One request per explicit operation, no retry.
});
