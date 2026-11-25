import test from "node:test";
import assert from "node:assert/strict";

import {
  CENTRAL_HOME_ROUTE,
  MOBILE_RUNTIME_LABELS,
  buildCentralDashboardSnapshot,
  buildFinalVerificationItems,
  defaultCentralWizardDraft,
  detectProfileMismatch,
  getCentralRestrictionDecision,
  getCentralSetupEntry,
  normalizeProvisioningStages,
  normalizeReadinessChecks,
  shouldHideMobileModeSelection,
  validateBackupDraft,
  validateSuperAdminDraft,
} from "./centralServerFlow.js";

test("Central profile detected and mobile mode selection hidden", () => {
  assert.equal(
    shouldHideMobileModeSelection({
      profile: "central_server",
      provisioning_status: "provisioning",
      capabilities: {},
      device: null,
    }),
    true,
  );
  assert.deepEqual(MOBILE_RUNTIME_LABELS, ["Mode autonome", "Serveur de mission", "Client de mission"]);
});

test("Central setup entry opens for backend trusted central profile", () => {
  assert.equal(
    getCentralSetupEntry({ profile: "central_server", provisioningStatus: "provisioning" }),
    true,
  );
  assert.equal(
    getCentralSetupEntry({ profile: "mobile_device", provisioningStatus: "provisioning" }),
    false,
  );
});

test("PostgreSQL readiness display falls back to concrete checks", () => {
  const checks = normalizeReadinessChecks(undefined);
  assert.equal(checks.length, 5);
  assert.equal(checks[0]?.label, "Service PostgreSQL");
  assert.equal(checks[4]?.label, "Permissions du schéma");
});

test("Provisioning progress falls back to real central stages", () => {
  const stages = normalizeProvisioningStages(undefined);
  assert.equal(stages.length, 5);
  assert.equal(stages[0]?.label, "Création de la base");
  assert.equal(stages[4]?.label, "Initialisation de la séquence centrale");
});

test("First super admin validation rejects incomplete and mismatched passwords", () => {
  const errors = validateSuperAdminDraft({
    firstName: "",
    lastName: "",
    email: "bad",
    password: "short",
    confirmation: "different",
  });

  assert.equal(Boolean(errors.firstName), true);
  assert.equal(Boolean(errors.lastName), true);
  assert.equal(Boolean(errors.email), true);
  assert.equal(Boolean(errors.password), true);
  assert.equal(Boolean(errors.confirmation), true);
});

test("Backup configuration requires a directory", () => {
  assert.deepEqual(validateBackupDraft({ directory: "", retentionPolicy: "30 jours" }), {
    directory: "Le dossier de sauvegarde est requis.",
  });
});

test("Final verification maps the six required checks", () => {
  const items = buildFinalVerificationItems({
    profile: "central_server",
    provisioning_status: "provisioning",
    app_version: "1.0.2",
    schema_revision: "20260722_03",
    sync_protocol_version: "1",
    server_uuid: null,
    generation_uuid: null,
    central_sequence: null,
    checks: [],
    provisioning_stages: [],
    postgres_ready: true,
    central_database_ready: true,
    migrations_up_to_date: true,
    fastapi_ready: true,
    admin_created: false,
    backup_configured: true,
    backup_directory: "D:/Backups",
    backup_status: "enabled",
    retention_policy: "30 jours",
    available_disk_space: "100 GB",
    network: {
      lan_ip: "192.168.1.10",
      api_url: "http://192.168.1.10:8000",
      health_status: "ok",
      firewall_status: "configured",
      network_interface: "Ethernet",
    },
    identity: {
      server_name: "Srv",
      server_code: "CENTRAL-SERVER",
      description: null,
      api_port: 8000,
    },
  });
  assert.equal(items.length, 6);
  assert.equal(items[4]?.passed, false);
});

test("Central dashboard aggregates devices, submissions, conflicts and backups", () => {
  const snapshot = buildCentralDashboardSnapshot({
    status: {
      profile: "central_server",
      provisioning_status: "configured",
      app_version: "1.0.2",
      schema_revision: "20260722_03",
      sync_protocol_version: "1",
      server_uuid: "srv",
      generation_uuid: "gen",
      central_sequence: 18,
      checks: [],
      provisioning_stages: [],
      postgres_ready: true,
      central_database_ready: true,
      migrations_up_to_date: true,
      fastapi_ready: true,
      admin_created: true,
      backup_configured: true,
      backup_directory: "D:/Backups",
      backup_status: "enabled",
      retention_policy: "30 jours",
      available_disk_space: "100 GB",
      network: {
        lan_ip: null,
        api_url: null,
        health_status: null,
        firewall_status: null,
        network_interface: null,
      },
      identity: {
        server_name: "Central A",
        server_code: "CENTRAL-SERVER",
        description: null,
        api_port: 8000,
      },
    },
    serverInfo: {
      server_uuid: "srv",
      server_generation_uuid: "gen",
      device_uuid: null,
      status: "online",
      schema_revision: "20260722_03",
      protocol_version: "1",
      current_central_sequence: 22,
      activated_at: null,
      last_health_check_at: null,
    },
    devices: [
      {
        uuid: "1",
        name: "Tablet A",
        code: "DEV-A",
        last_connection_at: null,
        last_sync_at: null,
        version: "1.0.2",
        schema_revision: "20260722_03",
        status: "active",
        revoked: false,
      },
    ],
    submissions: [
      {
        uuid: "sub-1",
        mission_code: "MSN-1",
        mission_server_device: "DEV-A",
        final_mission_sequence: 9,
        submitted_changes: 12,
        accepted: 11,
        conflicts: 1,
        status: "En attente",
      },
    ],
    backups: [{ filename: "backup-1", path: null, created_at: null, size_bytes: 1000, status: "ok" }],
  });

  assert.equal(snapshot.registeredDevices, 1);
  assert.equal(snapshot.pendingSubmissions, 1);
  assert.equal(snapshot.conflicts, 1);
  assert.equal(snapshot.latestBackups, 1);
});

test("Profile mismatch raises the expected blocking error", () => {
  assert.equal(
    detectProfileMismatch("central_server", "mobile_device"),
    "INSTALLATION_PROFILE_MISMATCH",
  );
});

test("Restricted mobile route redirects central installs to the central dashboard", () => {
  const decision = getCentralRestrictionDecision("/sync/mission", "central_server");
  assert.equal(decision.allowed, false);
  if (!decision.allowed) {
    assert.equal(decision.redirectTo, CENTRAL_HOME_ROUTE);
  }
});

test("Header profile badge target remains the central infrastructure page", () => {
  assert.equal(CENTRAL_HOME_ROUTE, "/app/infrastructure/central");
});

test("Recovery after page reload rebuilds the default draft from backend status", () => {
  const draft = defaultCentralWizardDraft({
    profile: "central_server",
    provisioning_status: "provisioning",
    app_version: "1.0.2",
    schema_revision: "20260722_03",
    sync_protocol_version: "1",
    server_uuid: "srv",
    generation_uuid: "gen",
    central_sequence: 5,
    checks: [],
    provisioning_stages: [],
    postgres_ready: false,
    central_database_ready: false,
    migrations_up_to_date: false,
    fastapi_ready: false,
    admin_created: false,
    backup_configured: false,
    backup_directory: "D:/Backups",
    backup_status: "disabled",
    retention_policy: "14 jours",
    available_disk_space: "50 GB",
    network: {
      lan_ip: null,
      api_url: null,
      health_status: null,
      firewall_status: null,
      network_interface: null,
    },
    identity: {
      server_name: "Central Restored",
      server_code: "CENTRAL-SERVER",
      description: "Restored",
      api_port: 9000,
    },
  });

  assert.equal(draft.identity.serverName, "Central Restored");
  assert.equal(draft.identity.apiPort, "9000");
  assert.equal(draft.backup.directory, "D:/Backups");
});
