import test from "node:test";
import assert from "node:assert/strict";

import {
  buildDiagnosticsSnapshot,
  buildProfileNavigation,
  buildRecoveryActions,
  buildUpgradeSteps,
  createBackendUnavailableWarning,
  createInstallationProfileState,
  evaluateCapabilityAccess,
  getProductIdentity,
  getUpgradeMessage,
  isFirstRunRequired,
  redactDiagnosticEntries,
  resolveEffectiveProfile,
  shouldSkipFirstRun,
} from "./profileInfrastructure.js";
import type { InstallationProfilePayload } from "@/types/installation";

const centralPayload: InstallationProfilePayload = {
  profile: "central_server",
  provisioning_status: "central_configuration_required",
  capabilities: {
    central_authority: true,
    manage_registered_devices: true,
    provide_device_bootstrap: true,
    receive_mission_submissions: true,
    run_mission_server: false,
    run_mission_client: false,
  },
  device: {
    uuid: "device-central",
    code: "CENTRAL-SERVER",
    name: "Serveur central",
  },
};

const mobilePayload: InstallationProfilePayload = {
  profile: "mobile_device",
  provisioning_status: "bootstrap_required",
  capabilities: {
    central_authority: false,
    manage_registered_devices: false,
    provide_device_bootstrap: false,
    receive_mission_submissions: false,
    run_mission_server: true,
    run_mission_client: true,
  },
  device: {
    uuid: "device-mobile",
    code: "PC-01",
    name: "PC Medecin 01",
  },
};

test("Profile context central.", () => {
  const state = createInstallationProfileState({
    payload: centralPayload,
    status: null,
    loading: false,
    error: null,
  });

  assert.equal(state.profile, "central_server");
  assert.equal(state.capabilities.central_authority, true);
  assert.equal(state.deviceIdentity.code, "CENTRAL-SERVER");
});

test("Profile context mobile.", () => {
  const state = createInstallationProfileState({
    payload: mobilePayload,
    status: null,
    loading: false,
    error: null,
  });

  assert.equal(state.profile, "mobile_device");
  assert.equal(state.capabilities.run_mission_server, true);
  assert.equal(state.deviceIdentity.code, "PC-01");
});

test("Effective profile precedence keeps last known good before packaged fallback.", () => {
  assert.deepEqual(
    resolveEffectiveProfile({
      backendProfile: "central_server",
      lastKnownGoodProfile: "mobile_device",
      packagedProfile: "mobile_device",
    }),
    { profile: "central_server", source: "backend" },
  );

  assert.deepEqual(
    resolveEffectiveProfile({
      backendProfile: null,
      lastKnownGoodProfile: "mobile_device",
      packagedProfile: "central_server",
    }),
    { profile: "mobile_device", source: "last_known_good" },
  );

  assert.deepEqual(
    resolveEffectiveProfile({
      backendProfile: null,
      lastKnownGoodProfile: null,
      packagedProfile: "central_server",
    }),
    { profile: "central_server", source: "packaged" },
  );

  assert.deepEqual(
    resolveEffectiveProfile({
      backendProfile: null,
      lastKnownGoodProfile: null,
      packagedProfile: null,
    }),
    { profile: null, source: "none" },
  );
});

test("Backend unavailable warning stays explicit.", () => {
  assert.deepEqual(createBackendUnavailableWarning(), {
    code: "INSTALLATION_PROFILE_BACKEND_UNAVAILABLE",
    message: "Le profil local temporaire est utilise car le backend local ne repond pas.",
  });
});

test("Central navigation.", () => {
  const items = buildProfileNavigation("central_server", {
    central_authority: true,
    manage_registered_devices: true,
    provide_device_bootstrap: true,
    receive_mission_submissions: true,
    run_mission_server: false,
    run_mission_client: false,
    create_central_backups: true,
    perform_mission_copy: false,
    push_to_central: true,
    pull_from_central: true,
  });

  assert.deepEqual(items.map((item) => item.label), [
    "Tableau de bord",
    "Utilisateurs",
    "Entreprises",
    "Travailleurs",
    "Campagnes",
    "Dossiers medicaux",
    "Examens medicaux",
    "Imports",
    "Rapports",
    "Journal d'audit",
    "Sync & Connection",
    "Parametres",
    "A propos",
    "Serveur central",
    "Appareils enregistres",
    "Missions recues",
    "Synchronisations",
    "Conflits centraux",
    "Bootstrap des appareils",
    "Sauvegardes",
    "Infrastructure",
  ]);
});

test("Mobile navigation.", () => {
  const items = buildProfileNavigation("mobile_device", {
    central_authority: false,
    manage_registered_devices: false,
    provide_device_bootstrap: false,
    receive_mission_submissions: false,
    run_mission_server: true,
    run_mission_client: true,
    create_central_backups: false,
    perform_mission_copy: true,
    push_to_central: true,
    pull_from_central: true,
  });

  assert.deepEqual(items.map((item) => item.label), [
    "Tableau de bord",
    "Utilisateurs",
    "Entreprises",
    "Travailleurs",
    "Campagnes",
    "Dossiers medicaux",
    "Examens medicaux",
    "Imports",
    "Rapports",
    "Journal d'audit",
    "Sync & Connection",
    "Parametres",
    "A propos",
    "Poste mobile",
    "Missions",
    "Synchronisation centrale",
    "Copie locale de mission",
    "Infrastructure",
  ]);
});

test("Central route guard.", () => {
  const decision = evaluateCapabilityAccess({
    profile: "central_server",
    capabilities: {
      central_authority: true,
      manage_registered_devices: true,
      provide_device_bootstrap: true,
      receive_mission_submissions: true,
      run_mission_server: false,
      run_mission_client: false,
    },
    user: { role: "Admin", permissions: ["users:manage"] },
    requiredProfile: "central_server",
    requiredCapability: "manage_registered_devices",
  } as never);

  assert.equal(decision.allowed, true);
});

test("Mobile route guard.", () => {
  const decision = evaluateCapabilityAccess({
    profile: "mobile_device",
    capabilities: {
      central_authority: false,
      manage_registered_devices: false,
      provide_device_bootstrap: false,
      receive_mission_submissions: false,
      run_mission_server: true,
      run_mission_client: true,
    },
    user: { role: "Doctor", permissions: ["campaigns:manage"] },
    requiredProfile: "mobile_device",
    requiredCapability: "run_mission_server",
  } as never);

  assert.equal(decision.allowed, true);
});

test("Capability and role combination.", () => {
  const denied = evaluateCapabilityAccess({
    profile: "mobile_device",
    capabilities: {
      central_authority: false,
      manage_registered_devices: false,
      provide_device_bootstrap: false,
      receive_mission_submissions: false,
      run_mission_server: true,
      run_mission_client: true,
    },
    user: { role: "Doctor", permissions: ["campaigns:view"] },
    requiredCapability: "run_mission_server",
    requiredPermissions: ["sync:manage"],
    requiredRoles: ["Admin", "Doctor"],
  } as never);

  assert.equal(denied.allowed, false);
  assert.equal(denied.reason, "missing_permission");
});

test("Route guard accessMode any matches audit sidebar visibility semantics.", () => {
  const decision = evaluateCapabilityAccess({
    profile: "mobile_device",
    capabilities: {
      central_authority: false,
      manage_registered_devices: false,
      provide_device_bootstrap: false,
      receive_mission_submissions: false,
      run_mission_server: true,
      run_mission_client: true,
    },
    user: { role: "Admin", permissions: ["users:view"] },
    requiredPermissions: ["audit_logs.view"],
    requiredRoles: ["Super Admin", "Admin"],
    accessMode: "any",
  } as never);

  assert.equal(decision.allowed, true);
});

test("Route guard accepts stored raw super_admin role values.", () => {
  const decision = evaluateCapabilityAccess({
    profile: "mobile_device",
    capabilities: {
      central_authority: false,
      manage_registered_devices: false,
      provide_device_bootstrap: false,
      receive_mission_submissions: false,
      run_mission_server: true,
      run_mission_client: true,
    },
    user: { role: "super_admin", permissions: [] },
    requiredPermissions: ["audit_logs.view"],
    requiredRoles: ["Super Admin", "Admin"],
    accessMode: "any",
  } as never);

  assert.equal(decision.allowed, true);
});

test("Upgrade profile mismatch.", () => {
  assert.equal(
    getUpgradeMessage("INSTALLATION_PROFILE_MISMATCH"),
    "Ce programme d'installation ne correspond pas au type de cette installation.",
  );
  assert.deepEqual(buildUpgradeSteps(), [
    "Sauvegarde de securite",
    "Arret du backend",
    "Application des migrations",
    "Redemarrage",
    "Verification",
  ]);
});

test("Diagnostics redaction.", () => {
  const snapshot = buildDiagnosticsSnapshot({
    profile: "central_server",
    status: {
      provisioning_status: "configured",
      fastapi_ready: true,
      network: { firewall_status: "configured" },
      backup_directory: "C:/backups",
    } as never,
    sidecarPath: "C:/Program Files/IbnSina/medical-backend-sidecar.exe",
    backendEnvPath: "DATABASE_URL=postgresql://postgres:secret@localhost:5432/medical_folder",
    databaseHost: "localhost",
    databaseName: "medical_folder",
    port: "8000",
    health: "ready",
    logPaths: ["C:/logs/central-provisioning.log"],
    migrationRevision: "2026072201",
  });
  const redacted = redactDiagnosticEntries(snapshot);

  assert.match(redacted.backendEnvPath || "", /\[redacted\]/);
  assert.equal(redacted.databaseName, "medical_folder");
});

test("Central recovery actions.", () => {
  const actions = buildRecoveryActions("central_server", "failed");
  assert.equal(actions[0]?.label, "Retry PostgreSQL provisioning");
  assert.equal(actions.at(-1)?.destructive, true);
});

test("Mobile recovery actions.", () => {
  const actions = buildRecoveryActions("mobile_device", "bootstrap_required");
  assert.equal(actions[0]?.label, "Retry local provisioning");
  assert.equal(actions.some((item) => item.label === "Reset runtime mode safely"), true);
});

test("Product title.", () => {
  assert.equal(
    getProductIdentity({
      profile: "central_server",
      version: "1.0.2",
      buildId: "1.0.2+central.20260722",
      installerIdentifier: null,
    }).productTitle,
    "Ibn Sina - Serveur central",
  );
  assert.equal(
    getProductIdentity({
      profile: "mobile_device",
      version: "1.0.2",
      buildId: "1.0.2+mobile.20260722",
      installerIdentifier: null,
    }).productTitle,
    "Ibn Sina - Poste mobile",
  );
});

test("Build identity.", () => {
  const central = getProductIdentity({
    profile: "central_server",
    version: "1.0.2",
    buildId: "1.0.2+central.20260722",
    installerIdentifier: "com.ibnsina.medicalclinic.central",
  });

  assert.equal(central.packageLabel, "Central Server");
  assert.equal(central.buildId, "1.0.2+central.20260722");
});

test("First-run reload recovery.", () => {
  assert.equal(isFirstRunRequired("bootstrap_required"), true);
  assert.equal(isFirstRunRequired("central_configuration_required"), true);
});

test("Existing configured installation skips first-run.", () => {
  assert.equal(shouldSkipFirstRun("configured"), true);
  assert.equal(shouldSkipFirstRun("bootstrap_required"), false);
});
