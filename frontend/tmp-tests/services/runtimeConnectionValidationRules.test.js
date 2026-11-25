import test from "node:test";
import assert from "node:assert/strict";
import { shouldRequireDatabaseHealth } from "./runtimeConnectionValidationRules.js";
test("database health is required only for server mode", () => {
    assert.equal(shouldRequireDatabaseHealth("server"), true);
    assert.equal(shouldRequireDatabaseHealth("client"), false);
});
