import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import vm from "node:vm";
import { webcrypto } from "node:crypto";
import ts from "typescript";

const source = fs.readFileSync(new URL("../src/api/localMutation.ts", import.meta.url), "utf8");
const code = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;

function context() {
  const content = new Map();
  const exports = {};
  const localStorage = {
    getItem: (key) => content.get(key) ?? null,
    setItem: (key, value) => content.set(key, value),
    removeItem: (key) => content.delete(key),
  };
  vm.runInNewContext(code, { exports, crypto: webcrypto, TextEncoder, window: { localStorage } });
  return { mutationHeaders: exports.mutationHeaders, content };
}

test("same request keeps operation UUID after a lost response; changed request rotates it", async () => {
  const { mutationHeaders, content } = context();
  const first = await mutationHeaders(7, "update", 2, { doctor_notes: "synthetic note" });
  const repeated = await mutationHeaders(7, "update", 2, { doctor_notes: "synthetic note" });
  const changed = await mutationHeaders(7, "update", 2, { doctor_notes: "different note" });
  assert.equal(first.headers["X-Operation-UUID"], repeated.headers["X-Operation-UUID"]);
  assert.notEqual(first.headers["X-Operation-UUID"], changed.headers["X-Operation-UUID"]);
  assert.equal(first.headers["X-Expected-Version"], "2");
  assert.ok(!JSON.stringify([...content]).includes("synthetic note"));
});

test("missing version is rejected before network work", async () => {
  const { mutationHeaders, content } = context();
  await assert.rejects(mutationHeaders(7, "update", undefined, {}), /EXPECTED_VERSION_REQUIRED/);
  assert.equal(content.size, 0);
});
