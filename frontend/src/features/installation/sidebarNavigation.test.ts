import test from "node:test";
import assert from "node:assert/strict";

import {
  buildNavigationDiagnostics,
  canDisplayNavigationItem,
  filterNavigationItems,
  flattenNavigationItems,
  SIDEBAR_NAVIGATION,
  type NavigationItem,
} from "./sidebarNavigation.js";

const adminUser = {
  role: "Admin" as const,
  permissions: ["users:manage", "users.view_permissions", "reports:read", "campaigns:manage", "settings:manage"],
};

const doctorUser = {
  role: "Doctor" as const,
  permissions: ["campaigns:read", "reports:read"],
};

const assistantUser = {
  role: "Assistant" as const,
  permissions: ["campaigns:manage", "workers:create", "workers:edit_basic", "sync:manage"],
};

const centralCapabilities = {
  central_authority: true,
  run_mission_server: false,
  run_mission_client: false,
  manage_registered_devices: true,
  receive_mission_submissions: true,
  provide_device_bootstrap: true,
  create_central_backups: true,
  perform_mission_copy: false,
  push_to_central: true,
  pull_from_central: true,
};

const mobileCapabilities = {
  central_authority: false,
  run_mission_server: true,
  run_mission_client: true,
  manage_registered_devices: false,
  receive_mission_submissions: false,
  provide_device_bootstrap: false,
  create_central_backups: false,
  perform_mission_copy: true,
  push_to_central: true,
  pull_from_central: true,
};

const labels = (items: NavigationItem[]) => flattenNavigationItems(items).map((item) => item.label);

test("mobile profile with admin shows mobile tabs and hides central tabs", () => {
  const items = filterNavigationItems(SIDEBAR_NAVIGATION, {
    profile: "mobile_device",
    packagedProfile: "mobile_device",
    backendProfile: "mobile_device",
    capabilities: mobileCapabilities,
    profileStatus: "ready",
    mismatchError: null,
    currentUser: adminUser as never,
  });

  assert.deepEqual(labels(items), [
    "Tableau de bord",
    "Utilisateurs",
    "Entreprises",
    "Travailleurs",
    "Campagnes",
    "Dossiers medicaux",
    "Examens medicaux",
    "Imports",
    "Permissions",
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

test("mobile profile with doctor keeps permitted medical tabs only", () => {
  const items = filterNavigationItems(SIDEBAR_NAVIGATION, {
    profile: "mobile_device",
    packagedProfile: "mobile_device",
    backendProfile: "mobile_device",
    capabilities: mobileCapabilities,
    profileStatus: "ready",
    mismatchError: null,
    currentUser: doctorUser as never,
  });

  assert.deepEqual(labels(items), [
    "Tableau de bord",
    "Entreprises",
    "Travailleurs",
    "Campagnes",
    "Dossiers medicaux",
    "Examens medicaux",
    "Imports",
    "Rapports",
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

test("mobile profile with assistant keeps permissions in fallback", () => {
  const items = filterNavigationItems(SIDEBAR_NAVIGATION, {
    profile: "mobile_device",
    packagedProfile: "mobile_device",
    backendProfile: null,
    capabilities: mobileCapabilities,
    profileStatus: "fallback",
    mismatchError: null,
    currentUser: assistantUser as never,
  });

  assert.equal(labels(items).includes("Utilisateurs"), false);
  assert.equal(labels(items).includes("Parametres"), false);
  assert.equal(labels(items).includes("Conflits centraux"), false);
  assert.equal(labels(items).includes("Travailleurs"), true);
});

test("central profile with admin shows central tabs and hides mobile mission tabs", () => {
  const items = filterNavigationItems(SIDEBAR_NAVIGATION, {
    profile: "central_server",
    packagedProfile: "central_server",
    backendProfile: "central_server",
    capabilities: centralCapabilities,
    profileStatus: "ready",
    mismatchError: null,
    currentUser: adminUser as never,
  });

  assert.deepEqual(labels(items), [
    "Tableau de bord",
    "Utilisateurs",
    "Entreprises",
    "Travailleurs",
    "Campagnes",
    "Dossiers medicaux",
    "Examens medicaux",
    "Imports",
    "Permissions",
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

test("central profile with restricted user removes admin tabs", () => {
  const items = filterNavigationItems(SIDEBAR_NAVIGATION, {
    profile: "central_server",
    packagedProfile: "central_server",
    backendProfile: "central_server",
    capabilities: centralCapabilities,
    profileStatus: "ready",
    mismatchError: null,
    currentUser: doctorUser as never,
  });

  assert.deepEqual(labels(items), [
    "Tableau de bord",
    "Entreprises",
    "Travailleurs",
    "Campagnes",
    "Dossiers medicaux",
    "Examens medicaux",
    "Imports",
    "Rapports",
    "Sync & Connection",
    "Parametres",
    "A propos",
    "Serveur central",
    "Synchronisations",
    "Conflits centraux",
    "Infrastructure",
  ]);
});

test("server PC shows user administration to an authorized Admin", () => {
  const items = filterNavigationItems(SIDEBAR_NAVIGATION, {
    profile: "mobile_device",
    packagedProfile: "mobile_device",
    backendProfile: "mobile_device",
    capabilities: mobileCapabilities,
    profileStatus: "ready",
    mismatchError: null,
    currentUser: adminUser as never,
    connectionMode: "SERVER_PC",
  });

  const visible = labels(items);
  assert.equal(visible.includes("Utilisateurs"), true);
  assert.equal(visible.includes("Sync & Connection"), false);
  assert.equal(visible.includes("Parametres"), false);
  assert.equal(visible.includes("Travailleurs"), true);
  assert.equal(visible.includes("Campagnes"), true);
});

test("permission administration is visible only to Admin and Super Admin users", () => {
  const item = SIDEBAR_NAVIGATION.find((candidate) => candidate.id === "shared-permissions");
  assert.ok(item);

  const context = {
    profile: "mobile_device" as const,
    packagedProfile: "mobile_device" as const,
    backendProfile: "mobile_device" as const,
    capabilities: mobileCapabilities,
    profileStatus: "ready" as const,
    mismatchError: null,
  };

  assert.equal(
    canDisplayNavigationItem(item, {
      ...context,
      currentUser: { role: "Admin", permissions: ["users.view_permissions"] } as never,
    }).allowed,
    true,
  );
  assert.equal(
    canDisplayNavigationItem(item, {
      ...context,
      currentUser: { role: "Super Admin", permissions: ["roles.view"] } as never,
    }).allowed,
    true,
  );
  assert.equal(
    canDisplayNavigationItem(item, {
      ...context,
      currentUser: doctorUser as never,
    }).allowed,
    false,
  );
  assert.equal(
    canDisplayNavigationItem(item, {
      ...context,
      currentUser: { role: "Admin", permissions: ["users.view_permissions"] } as never,
      connectionMode: "CLIENT",
    }).allowed,
    true,
  );
  assert.equal(
    canDisplayNavigationItem(item, {
      ...context,
      currentUser: { role: "Super Admin", permissions: ["roles.view"] } as never,
      connectionMode: "SERVER_PC",
    }).allowed,
    true,
  );
});

test("CLIENT shows only allowed worker, report, and connection navigation", () => {
  const items = filterNavigationItems(SIDEBAR_NAVIGATION, {
    profile: "mobile_device",
    packagedProfile: "mobile_device",
    backendProfile: "mobile_device",
    capabilities: mobileCapabilities,
    profileStatus: "ready",
    mismatchError: null,
    currentUser: {
      ...doctorUser,
      permissions: ["workers.view", "worker_tests.view", "reports.view", "local_network.view_status"],
    } as never,
    connectionMode: "CLIENT",
  });

  assert.deepEqual(labels(items), [
    "Tableau de bord",
    "Travailleurs",
    "Dossiers medicaux",
    "Rapports",
    "Sync & Connection",
  ]);
});

test("CLIENT navigation still requires the user's normal permissions", () => {
  const items = filterNavigationItems(SIDEBAR_NAVIGATION, {
    profile: "mobile_device",
    packagedProfile: "mobile_device",
    backendProfile: "mobile_device",
    capabilities: mobileCapabilities,
    profileStatus: "ready",
    mismatchError: null,
    currentUser: { ...adminUser, permissions: ["workers.view"] } as never,
    connectionMode: "CLIENT",
  });

  assert.deepEqual(labels(items), ["Travailleurs"]);
});

test("loading state renders shared safe navigation instead of only about", () => {
  const items = filterNavigationItems(SIDEBAR_NAVIGATION, {
    profile: null,
    packagedProfile: null,
    backendProfile: null,
    capabilities: null,
    profileStatus: "loading",
    mismatchError: null,
    currentUser: adminUser as never,
  });

  assert.deepEqual(labels(items), [
    "Tableau de bord",
    "Utilisateurs",
    "Entreprises",
    "Travailleurs",
    "Campagnes",
    "Dossiers medicaux",
    "Examens medicaux",
    "Imports",
    "Permissions",
    "Rapports",
    "Journal d'audit",
    "Sync & Connection",
    "Parametres",
    "A propos",
    "Infrastructure",
  ]);
});

test("mismatch blocks protected entries and keeps diagnostics available", () => {
  const items = filterNavigationItems(SIDEBAR_NAVIGATION, {
    profile: "mobile_device",
    packagedProfile: "central_server",
    backendProfile: "mobile_device",
    capabilities: mobileCapabilities,
    profileStatus: "ready",
    mismatchError: "INSTALLATION_PROFILE_MISMATCH",
    currentUser: adminUser as never,
  });

  assert.deepEqual(labels(items), ["A propos", "Infrastructure"]);
});

test("empty groups are removed after filtering children", () => {
  const items = filterNavigationItems(
    [
      {
        id: "group-empty",
        label: "Empty group",
        route: "/empty",
        icon: SIDEBAR_NAVIGATION[0]!.icon,
        children: [
          {
            id: "restricted",
            label: "Restricted child",
            route: "/restricted",
            icon: SIDEBAR_NAVIGATION[0]!.icon,
            requiredPermissions: ["users:manage"],
            roles: ["Super Admin", "Admin"],
          },
        ],
      },
      {
        id: "group-visible",
        label: "Visible group",
        route: "/visible",
        icon: SIDEBAR_NAVIGATION[0]!.icon,
        children: [
          {
            id: "safe-child",
            label: "Safe child",
            route: "/safe",
            icon: SIDEBAR_NAVIGATION[0]!.icon,
            allowWhenProfileUnresolved: true,
          },
        ],
      },
    ],
    {
      profile: null,
      packagedProfile: null,
      backendProfile: null,
      capabilities: null,
      profileStatus: "loading",
      mismatchError: null,
      currentUser: doctorUser as never,
    },
  );

  assert.deepEqual(items.map((item) => item.id), ["group-visible"]);
});

test("direct central route is blocked on mobile and direct mobile route is blocked on central", () => {
  const centralOnly = canDisplayNavigationItem(
    {
      id: "central-only",
      label: "Central only",
      route: "/app/infrastructure/central",
      icon: SIDEBAR_NAVIGATION[0]!.icon,
      profiles: ["central_server"],
    },
    {
      profile: "mobile_device",
      packagedProfile: "mobile_device",
      backendProfile: "mobile_device",
      capabilities: mobileCapabilities,
      profileStatus: "ready",
      mismatchError: null,
      currentUser: adminUser as never,
    },
  );

  const mobileOnly = canDisplayNavigationItem(
    {
      id: "mobile-only",
      label: "Mobile only",
      route: "/app/infrastructure/mobile",
      icon: SIDEBAR_NAVIGATION[0]!.icon,
      profiles: ["mobile_device"],
    },
    {
      profile: "central_server",
      packagedProfile: "central_server",
      backendProfile: "central_server",
      capabilities: centralCapabilities,
      profileStatus: "ready",
      mismatchError: null,
      currentUser: adminUser as never,
    },
  );

  assert.equal(centralOnly.allowed, false);
  assert.equal(mobileOnly.allowed, false);
});

test("navigation diagnostics remain safe and count visible items", () => {
  const diagnostics = buildNavigationDiagnostics(SIDEBAR_NAVIGATION, {
    profile: "mobile_device",
    packagedProfile: "mobile_device",
    backendProfile: null,
    capabilities: mobileCapabilities,
    profileStatus: "fallback",
    mismatchError: null,
    currentUser: assistantUser as never,
  });

  assert.equal(diagnostics.profileSource, "packaged");
  assert.equal(diagnostics.capabilitiesLoaded, false);
  assert.ok(diagnostics.visibleItems > 0);
  assert.equal("token" in diagnostics, false);
});
