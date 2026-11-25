import test from "node:test";
import assert from "node:assert/strict";

import {
  BROWSER_AVAILABLE_MODES,
  BROWSER_SERVER_START_COMMANDS,
  BROWSER_SERVER_UNAVAILABLE_MESSAGE,
  TAURI_AVAILABLE_MODES,
  buildBrowserStatusPanel,
  canNavigateToLoginAfterValidation,
  canProvisionServer,
  deriveApiBaseUrl,
  deriveServerRootUrl,
  getStatusLabel,
  isLocalhostHostname,
  mapValidationStateToHealthStatuses,
  resolveSetupConnectionPolicy,
  resolveSetupStrategy,
  resolveRuntimePlatform,
  shouldRequireModeChangeConfirmation,
} from "./setupFlow.js";

test("browser and tauri both expose server and client mode cards", () => {
  assert.deepEqual(BROWSER_AVAILABLE_MODES, ["server", "client"]);
  assert.deepEqual(TAURI_AVAILABLE_MODES, ["server", "client"]);
});

test("browser server mode defaults derive 127.0.0.1:8000 and canonical api base", () => {
  const serverRoot = deriveServerRootUrl("127.0.0.1", "8000", "");
  assert.equal(serverRoot, "http://127.0.0.1:8000");
  assert.equal(deriveApiBaseUrl(serverRoot), "http://127.0.0.1:8000/api/v1");
});

test("browser server mode accepts localhost inputs", () => {
  assert.equal(isLocalhostHostname("127.0.0.1"), true);
  assert.equal(isLocalhostHostname("localhost"), true);
  assert.equal(
    deriveServerRootUrl("localhost", "8000", ""),
    "http://localhost:8000",
  );
});

test("no validation result is shown before submission", () => {
  const panel = buildBrowserStatusPanel({
    mode: "server",
    usedUrl: "http://127.0.0.1:8000",
    validationState: "idle",
    canProvision: false,
  });

  assert.equal(panel.apiStatus, "idle");
  assert.equal(panel.databaseStatus, "idle");
  assert.equal(getStatusLabel(panel.apiStatus), "Non verifiee");
});

test("health status mapping distinguishes api and database failures", () => {
  assert.deepEqual(mapValidationStateToHealthStatuses("api_unavailable"), {
    apiStatus: "unavailable",
    databaseStatus: "idle",
  });
  assert.deepEqual(mapValidationStateToHealthStatuses("database_unavailable"), {
    apiStatus: "available",
    databaseStatus: "unavailable",
  });
  assert.deepEqual(mapValidationStateToHealthStatuses("connected"), {
    apiStatus: "available",
    databaseStatus: "available",
  });
});

test("browser server mode shows manual start message when backend is unavailable", () => {
  const panel = buildBrowserStatusPanel({
    mode: "server",
    usedUrl: "http://127.0.0.1:8000",
    validationState: "api_unavailable",
    canProvision: false,
  });

  assert.equal(panel.manualStartMessage, BROWSER_SERVER_UNAVAILABLE_MESSAGE);
  assert.equal(panel.selectedModeLabel, "Serveur");
  assert.equal(BROWSER_SERVER_START_COMMANDS[2], "python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload");
});

test("browser runtime never provisions the server", () => {
  assert.equal(resolveRuntimePlatform(false), "browser");
  assert.equal(canProvisionServer("browser"), false);
  assert.equal(resolveSetupStrategy("browser", "server"), "browser-server-manual-validation");
});

test("tauri server mode uses the existing provisioning strategy", () => {
  assert.equal(resolveRuntimePlatform(true), "tauri");
  assert.equal(canProvisionServer("tauri"), true);
  assert.equal(resolveSetupStrategy("tauri", "server"), "tauri-server-provisioning");
});

test("browser client and server derived urls never fall back to localhost", () => {
  assert.equal(
    deriveServerRootUrl("192.168.1.10", "8000", ""),
    "http://192.168.1.10:8000",
  );
  assert.equal(
    deriveServerRootUrl("192.168.1.10", "8000", "http://10.0.0.5:8010"),
    "http://10.0.0.5:8010",
  );
});

test("remote FastAPI URLs normalize once whether or not /api/v1 is entered", () => {
  assert.equal(deriveApiBaseUrl("http://192.168.1.10:8000"), "http://192.168.1.10:8000/api/v1");
  assert.equal(deriveApiBaseUrl("http://192.168.1.10:8000/api/v1"), "http://192.168.1.10:8000/api/v1");
});

test("SERVER_PC alone resolves the local API; CLIENT and SERVER require remote URLs", () => {
  const localUrl = "http://127.0.0.1:8000";

  assert.deepEqual(resolveSetupConnectionPolicy("CLIENT", localUrl), {
    requiresRemoteServerUrl: true,
    resolvedServerRootUrl: null,
  });
  assert.deepEqual(resolveSetupConnectionPolicy("SERVER_PC", localUrl), {
    requiresRemoteServerUrl: false,
    resolvedServerRootUrl: localUrl,
  });
  assert.deepEqual(resolveSetupConnectionPolicy("SERVER", localUrl), {
    requiresRemoteServerUrl: true,
    resolvedServerRootUrl: null,
  });
});

test("navigation to login requires successful validation", () => {
  assert.equal(canNavigateToLoginAfterValidation({ success: true }), true);
  assert.equal(canNavigateToLoginAfterValidation({ success: false }), false);
});

test("mode switch confirmation is required when an existing configuration is present", () => {
  assert.equal(
    shouldRequireModeChangeConfirmation({
      currentMode: "client",
      nextMode: "server",
      hasExistingConfiguration: true,
    }),
    true,
  );

  assert.equal(
    shouldRequireModeChangeConfirmation({
      currentMode: "server",
      nextMode: "server",
      hasExistingConfiguration: true,
    }),
    false,
  );
});
