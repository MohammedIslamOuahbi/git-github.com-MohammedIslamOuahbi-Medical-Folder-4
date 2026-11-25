import test from "node:test";
import assert from "node:assert/strict";

import {
  MOBILE_BOOTSTRAP_STAGES,
  MOBILE_HOME_ROUTE,
  MOBILE_RUNTIME_MODE_OPTIONS,
  buildBootstrapReadiness,
  buildBootstrapStageStates,
  buildMobileCompletionSummary,
  buildMobileRegistrationSummary,
  defaultMobileWizardDraft,
  detectMobileProfileMismatch,
  getMobileRestrictedCentralRoute,
  normalizeMobilePostgresChecks,
  shouldHideCentralSetup,
  shouldShowMobileProvisioning,
  validateCentralConnectionUrl,
  validateMobileIdentityDraft,
} from "./mobileDeviceFlow.js";

test("Mobile profile detected and central setup hidden", () => {
  assert.equal(
    shouldHideCentralSetup({
      profile: "mobile_device",
      provisioning_status: "provisioning",
      capabilities: {},
      device: null,
    }),
    true,
  );
});

test("PostgreSQL provisioning readiness list is present", () => {
  const checks = normalizeMobilePostgresChecks(undefined);
  assert.equal(checks.length, 5);
  assert.equal(checks[0]?.label, "Service PostgreSQL");
  assert.equal(checks[4]?.label, "Espace disque");
});

test("Device identity form validation requires name and code", () => {
  const errors = validateMobileIdentityDraft({
    deviceName: "",
    deviceCode: "",
    description: "",
  });
  assert.equal(Boolean(errors.deviceName), true);
  assert.equal(Boolean(errors.deviceCode), true);
});

test("Device UUID is treated as read-only completion data", () => {
  const completion = buildMobileCompletionSummary({
    manifest: null,
    provision: { provisioning_status: "configured", checks: [], device_uuid: "device-uuid-1" },
  });
  assert.equal(completion.serverRegistered, true);
});

test("Central connection success accepts a fully qualified URL", () => {
  assert.equal(validateCentralConnectionUrl("http://192.168.1.5:8000"), null);
});

test("Central connection failure rejects missing protocol", () => {
  assert.equal(
    validateCentralConnectionUrl("192.168.1.5:8000"),
    "L’adresse doit commencer par http:// ou https://",
  );
});

test("Registration summary reflects authorized device state", () => {
  const summary = buildMobileRegistrationSummary({
    draft: defaultMobileWizardDraft(null),
    serverName: "Central A",
    registration: { device_uuid: "dev-1" },
  });
  assert.equal(summary.authorized, true);
  assert.equal(summary.centralServer, "Central A");
});

test("Bootstrap readiness shows five checks", () => {
  const readiness = buildBootstrapReadiness({
    profile: "mobile_device",
    provisioning_status: "provisioning",
    app_version: "1.0.2",
    schema_revision: "20260722_03",
    sync_protocol_version: "1",
    server_uuid: "device-1",
    generation_uuid: null,
    central_sequence: null,
    checks: [],
    provisioning_stages: [],
    postgres_ready: true,
    central_database_ready: false,
    migrations_up_to_date: true,
    fastapi_ready: true,
    admin_created: false,
    backup_configured: false,
    backup_directory: null,
    backup_status: null,
    retention_policy: null,
    available_disk_space: "100 GB",
    network: {
      lan_ip: null,
      api_url: "http://192.168.1.5:8000",
      health_status: null,
      firewall_status: null,
      network_interface: null,
    },
    identity: {
      server_name: "PC Médecin 01",
      server_code: "PC-01",
      description: null,
      api_port: 8000,
    },
  });
  assert.equal(readiness.length, 5);
});

test("Bootstrap success marks manifest download complete", () => {
  const states = buildBootstrapStageStates({
    manifest: {
      bootstrap_uuid: "boot-1",
      checksum: "abc",
      central_server_uuid: "srv",
      central_generation_uuid: "gen",
      snapshot_central_sequence: 12,
      schema_revision: "20260722_03",
      protocol_version: "1",
      creation_time: "2026-07-22T00:00:00Z",
      entity_counts: {},
      file_metadata: {},
    },
    checksumFailed: false,
    interrupted: false,
  });
  assert.equal(states["Téléchargement du manifeste"], "completed");
});

test("Bootstrap interruption marks stages failed", () => {
  const states = buildBootstrapStageStates({
    manifest: null,
    checksumFailed: false,
    interrupted: true,
  });
  assert.equal(states[MOBILE_BOOTSTRAP_STAGES[0]], "failed");
});

test("Bootstrap checksum failure marks checksum stage failed", () => {
  const states = buildBootstrapStageStates({
    manifest: null,
    checksumFailed: true,
    interrupted: false,
  });
  assert.equal(states["Validation du checksum"], "failed");
});

test("Runtime mode selection appears with three mobile choices", () => {
  assert.deepEqual(MOBILE_RUNTIME_MODE_OPTIONS, [
    "Mode autonome",
    "Serveur de mission",
    "Client de mission",
  ]);
});

test("Central-authority route is hidden for mobile profile", () => {
  const decision = getMobileRestrictedCentralRoute("/app/infrastructure/central", "mobile_device");
  assert.equal(decision.allowed, false);
  if (!decision.allowed) {
    assert.equal(decision.redirectTo, MOBILE_HOME_ROUTE);
  }
});

test("Reload recovery rebuilds mobile defaults from backend status", () => {
  const draft = defaultMobileWizardDraft({
    profile: "mobile_device",
    provisioning_status: "provisioning",
    app_version: "1.0.2",
    schema_revision: "20260722_03",
    sync_protocol_version: "1",
    server_uuid: "device-uuid",
    generation_uuid: null,
    central_sequence: null,
    checks: [],
    provisioning_stages: [],
    postgres_ready: false,
    central_database_ready: false,
    migrations_up_to_date: false,
    fastapi_ready: false,
    admin_created: false,
    backup_configured: false,
    backup_directory: null,
    backup_status: null,
    retention_policy: null,
    available_disk_space: "50 GB",
    network: {
      lan_ip: null,
      api_url: "http://192.168.1.5:8000",
      health_status: null,
      firewall_status: null,
      network_interface: null,
    },
    identity: {
      server_name: "PC Médecin 01",
      server_code: "PC-01",
      description: "mobile",
      api_port: 8000,
    },
  });
  assert.equal(draft.identity.deviceName, "PC Médecin 01");
  assert.equal(draft.connection.centralServerUrl, "http://192.168.1.5:8000");
});

test("Mobile profile mismatch still raises the shared blocking error", () => {
  assert.equal(
    detectMobileProfileMismatch("mobile_device", "central_server"),
    "INSTALLATION_PROFILE_MISMATCH",
  );
});

test("Configured mobile profile stops provisioning flow", () => {
  assert.equal(
    shouldShowMobileProvisioning({ profile: "mobile_device", provisioningStatus: "configured" }),
    false,
  );
});
