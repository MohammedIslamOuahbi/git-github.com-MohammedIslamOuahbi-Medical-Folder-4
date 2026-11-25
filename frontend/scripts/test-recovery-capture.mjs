import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import vm from "node:vm";
import { webcrypto } from "node:crypto";
import ts from "typescript";

const source = fs.readFileSync(new URL("../src/services/legacyRecovery.ts", import.meta.url), "utf8");
const code = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;

function storage(initial) {
  const content = new Map(Object.entries(initial));
  let removals = 0;
  return {
    content,
    get length() { return content.size; },
    key: (index) => Array.from(content.keys())[index] || null,
    getItem: (key) => content.get(key) ?? null,
    setItem: (key, value) => content.set(key, value),
    removeItem: () => { removals++; },
    get removals() { return removals; },
  };
}

function moduleFor(localStorage, post) {
  const exports = {};
  vm.runInNewContext(code, {
    exports,
    crypto: webcrypto,
    TextEncoder,
    window: { localStorage },
    require: (name) => {
      assert.equal(name, "@/api/axios");
      return { default: { post, get: async () => ({ data: { sources: [], limited_to: 200 } }) } };
    },
  });
  return exports.legacyRecovery;
}

test("capture retries without touching original queue, drafts, credentials", async () => {
  const original = {
    clinic_sync_queue: JSON.stringify({ workers: [{ uuid: "a" }] }),
    "medical-folder.worker-medical-file.1.create.draft": JSON.stringify({ note: "synthetic" }),
    clinic_sync_meta: JSON.stringify({ device_id: "device-one" }),
    clinic_access_token: "synthetic-token",
  };
  const localStorage = storage(original);
  const payloads = [];
  let attempt = 0;
  const recovery = moduleFor(localStorage, async (_path, payload) => {
    payloads.push(payload);
    if (++attempt === 1) throw new Error("synthetic interruption");
    return { data: { uuid: "captured" } };
  });
  await assert.rejects(recovery.captureBrowser());
  await recovery.captureBrowser();
  assert.equal(payloads.length, 2);
  assert.equal(payloads[0].sha256, payloads[1].sha256);
  assert.equal(payloads[0].profile_id, payloads[1].profile_id);
  assert.equal(payloads[0].source_identity, "device-one");
  const entries = JSON.parse(payloads[0].raw_payload).entries;
  assert.equal(entries.clinic_sync_queue, original.clinic_sync_queue);
  assert.equal(entries["medical-folder.worker-medical-file.1.create.draft"], original["medical-folder.worker-medical-file.1.create.draft"]);
  assert.equal(entries.clinic_access_token, undefined);
  for (const [key, value] of Object.entries(original)) assert.equal(localStorage.getItem(key), value);
  assert.equal(localStorage.removals, 0);
});

test("changed source produces a new fingerprint with unchanged original keys", async () => {
  const localStorage = storage({ clinic_sync_queue: JSON.stringify({ workers: [{ uuid: "a" }] }) });
  const payloads = [];
  const recovery = moduleFor(localStorage, async (_path, payload) => {
    payloads.push(payload);
    return { data: { uuid: "captured" } };
  });
  await recovery.captureBrowser();
  localStorage.setItem("clinic_sync_queue", JSON.stringify({ workers: [{ uuid: "a" }, { uuid: "b" }] }));
  await recovery.captureBrowser();
  assert.notEqual(payloads[0].sha256, payloads[1].sha256);
  assert.equal(payloads[0].profile_id, payloads[1].profile_id);
  assert.equal(localStorage.removals, 0);
});

test("package capture preserves file bytes and marks declared server as a claim", async () => {
  const localStorage = storage({});
  const raw = JSON.stringify({ server_id: "server-one", data: { workers: [] } });
  const file = { name: "synthetic.sync", size: Buffer.byteLength(raw), text: async () => raw };
  let transmitted;
  const recovery = moduleFor(localStorage, async (_path, payload) => {
    transmitted = payload;
    return { data: { uuid: "captured" } };
  });
  await recovery.capturePackage(file);
  assert.equal(transmitted.raw_payload, raw);
  assert.equal(transmitted.source_identity, "claimed-package-server:server-one");
  assert.equal(await file.text(), raw);
  assert.equal(localStorage.removals, 0);
});

test("in-flight storage mutation aborts transmission but leaves all values", async () => {
  const localStorage = storage({ clinic_sync_queue: JSON.stringify({ workers: [{ uuid: "a" }] }) });
  let sent = 0;
  const recovery = moduleFor(localStorage, async () => { sent++; return { data: {} }; });
  const actualDigest = webcrypto.subtle.digest.bind(webcrypto.subtle);
  // Mutation during hashing can be simulated by a temporary digest wrapper.
  const first = localStorage.getItem("clinic_sync_queue");
  const altered = JSON.stringify({ workers: [{ uuid: "a" }, { uuid: "new" }] });
  const exports = {};
  vm.runInNewContext(code, {
    exports,
    crypto: { randomUUID: () => "profile", subtle: { digest: async (...args) => {
      localStorage.setItem("clinic_sync_queue", altered);
      return actualDigest(...args);
    } } },
    TextEncoder, window: { localStorage },
    require: () => ({ default: { post: async () => { sent++; } } }),
  });
  await assert.rejects(exports.legacyRecovery.captureBrowser(), /RECOVERY_SOURCE_CHANGED_DURING_CAPTURE/);
  assert.equal(sent, 0);
  assert.equal(first, JSON.stringify({ workers: [{ uuid: "a" }] }));
  assert.equal(localStorage.getItem("clinic_sync_queue"), altered);
  assert.equal(localStorage.removals, 0);
  assert.ok(recovery);
});
