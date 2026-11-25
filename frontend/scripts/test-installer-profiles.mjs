import assert from "node:assert/strict";
import { existsSync } from "node:fs";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const resolveScript = (relativePath) => path.resolve(__dirname, relativePath);

test("installer profile scripts are present", () => {
  assert.equal(existsSync(resolveScript("./build-installers.mjs")), true);
  assert.equal(existsSync(resolveScript("./build-tauri-profile.mjs")), true);
  assert.equal(existsSync(resolveScript("./create-tauri-release-manifest.mjs")), true);
});
