import test from "node:test";
import assert from "node:assert/strict";

import { LOGIN_CONFIGURATION_PATH, buildLoginConnectionInfo } from "./loginConnectionInfo.js";

test("login displays the configured remote URL for CLIENT", () => {
  assert.deepEqual(buildLoginConnectionInfo("CLIENT", "http://192.168.1.20:8000/api/v1"), {
    modeLabel: "Client",
    apiLabel: "Serveur",
    apiBaseUrl: "http://192.168.1.20:8000/api/v1",
  });
});

test("login displays the resolved local URL for SERVER_PC", () => {
  assert.deepEqual(buildLoginConnectionInfo("SERVER_PC", "http://127.0.0.1:8000/api/v1"), {
    modeLabel: "Poste serveur medical",
    apiLabel: "Adresse API resolue",
    apiBaseUrl: "http://127.0.0.1:8000/api/v1",
  });
});

test("login displays the configured central URL for SERVER", () => {
  assert.deepEqual(buildLoginConnectionInfo("SERVER", "http://192.168.1.10:8000/api/v1"), {
    modeLabel: "Serveur central",
    apiLabel: "Serveur",
    apiBaseUrl: "http://192.168.1.10:8000/api/v1",
  });
});

test("the configuration action returns to setup", () => {
  assert.equal(LOGIN_CONFIGURATION_PATH, "/setup");
});
