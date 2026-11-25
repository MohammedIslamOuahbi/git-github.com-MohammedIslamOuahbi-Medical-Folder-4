import { Navigate, Route, Routes } from "react-router-dom";
import { ProtectedRoute } from "./ProtectedRoute";
import { CampaignWorkspaceGuard } from "./CampaignWorkspaceGuard";
import { DashboardLayout } from "@/layouts/DashboardLayout";
import { CampaignWorkspaceShell } from "@/layouts/CampaignWorkspaceShell";
import { ConnectionLoginRoute } from "@/routes/ConnectionLoginRoute";
import { CapabilityRoute } from "@/routes/CapabilityRoute";
import { CentralOnlyRoute } from "@/routes/CentralOnlyRoute";
import { MobileOnlyRoute } from "@/routes/MobileOnlyRoute";
import { LoginPage } from "@/pages/auth/LoginPage";
import { SetupPage } from "@/pages/auth/Setup";
import { CentralBackupsPage } from "@/pages/central/CentralBackupsPage";
import { CentralMissionSubmissionsPage } from "@/pages/central/CentralMissionSubmissionsPage";
import { CentralRegisteredDevicesPage } from "@/pages/central/CentralRegisteredDevicesPage";
import { CentralServerDashboardPage } from "@/pages/central/CentralServerDashboardPage";
import { MobileDeviceDashboardPage } from "@/pages/mobile/MobileDeviceDashboardPage";
import { DashboardRedirectPage } from "@/pages/dashboard/DashboardRedirectPage";
import { PersonalDashboardPage } from "@/pages/dashboard/PersonalDashboardPage";
import { UsersPage } from "@/pages/users/UsersPage";
import { UserEditorPage } from "@/pages/users/UserEditorPage";
import { CompaniesPage } from "@/pages/companies/CompaniesPage";
import { WorkersPage } from "@/pages/workers/WorkersPage";
import { WorkerDetailsPage } from "@/pages/workers/WorkerDetailsPage";
import { CampaignsPage } from "@/pages/campaigns/CampaignsPage";
import { CampaignDetailsPage } from "@/pages/campaigns/CampaignDetailsPage";
import { CampaignEditorPage } from "@/pages/campaigns/CampaignEditorPage";
import { CampaignWorkspaceDashboardPage } from "@/pages/workspace/CampaignWorkspaceDashboardPage";
import { CampaignWorkspaceTestsPage } from "@/pages/workspace/CampaignWorkspaceTestsPage";
import { CampaignWorkspaceWorkersPage } from "@/pages/workspace/CampaignWorkspaceWorkersPage";
import { CampaignWorkspaceImportPage } from "@/pages/workspace/CampaignWorkspaceImportPage";
import { CampaignWorkspaceSyncPage } from "@/pages/workspace/CampaignWorkspaceSyncPage";
import { CampaignWorkspaceSettingsPage } from "@/pages/workspace/CampaignWorkspaceSettingsPage";
import { WorkerMedicalFilePage } from "@/pages/workspace/WorkerMedicalFilePage";
import { MedicalTestsPage } from "@/pages/medical-tests/MedicalTestsPage";
import { WorkerTestsPage } from "@/pages/medical-tests/WorkerTestsPage";
import { ImportsPage } from "@/pages/imports/ImportsPage";
import { ImportHistoryPage } from "@/pages/imports/ImportHistoryPage";
import { ReportsPage } from "@/pages/reports/ReportsPage";
import { AuditLogsPage } from "@/pages/audit/AuditLogsPage";
import { SettingsPage } from "@/pages/settings/SettingsPage";
import { MedicineCataloguePage } from "@/pages/settings/MedicineCataloguePage";
import { ProfilePage } from "@/pages/settings/ProfilePage";
import { PermissionsPage } from "@/pages/settings/PermissionsPage";
import { MissionOperationsPage } from "@/pages/sync/MissionOperationsPage";
import { CentralSyncPage } from "@/pages/sync/CentralSyncPage";
import { SyncConflictsPage } from "@/pages/sync/SyncConflictsPage";
import { SyncConnectionPage } from "@/pages/sync-connection/SyncConnectionPage";
import { AboutVersionPage } from "@/pages/system/AboutVersionPage";
import { InstallerDiagnosticsPage } from "@/pages/system/InstallerDiagnosticsPage";
import { UpgradeSafetyPage } from "@/pages/system/UpgradeSafetyPage";
import { NotFoundPage } from "@/pages/errors/NotFoundPage";

export const AppRoutes = () => (
  <Routes>
    <Route path="/setup" element={<SetupPage />} />

    <Route
      path="/login"
      element={
        <ConnectionLoginRoute>
          <LoginPage />
        </ConnectionLoginRoute>
      }
    />

    <Route element={<ProtectedRoute />}>
      <Route element={<DashboardLayout />}>
        <Route path="/" element={<Navigate to="/dashboard" replace />} />
        <Route path="/dashboard" element={<DashboardRedirectPage />} />
        <Route path="/dashboard/:dashboardUid" element={<PersonalDashboardPage />} />
        <Route path="/dashboard/admin" element={<DashboardRedirectPage />} />
        <Route path="/dashboard/doctor" element={<DashboardRedirectPage />} />
        <Route path="/dashboard/assistant" element={<DashboardRedirectPage />} />
        <Route
          element={
            <CapabilityRoute
              permissions={["users.view"]}
              roles={["Super Admin", "Admin"]}
              allowWhenProfileUnresolved
            />
          }
        >
          <Route path="/users" element={<UsersPage />} />
          <Route path="/users/:userId/edit" element={<UserEditorPage />} />
          <Route path="/users/:userId/permissions" element={<UserEditorPage />} />
        </Route>
        <Route path="/companies" element={<CompaniesPage />} />
        <Route path="/branches" element={<Navigate to="/companies" replace />} />
        <Route path="/drilling-sites" element={<Navigate to="/companies" replace />} />
        <Route path="/workers" element={<WorkersPage />} />
        <Route path="/workers/:workerId" element={<WorkerDetailsPage />} />
        <Route path="/campaigns" element={<CampaignsPage />} />
        <Route path="/campaigns/create" element={<CampaignEditorPage />} />
        <Route path="/campaigns/:campaignId" element={<CampaignDetailsPage />} />
        <Route path="/campaigns/:campaignId/edit" element={<CampaignEditorPage />} />
        <Route path="/medical-tests" element={<MedicalTestsPage />} />
        <Route path="/worker-tests" element={<WorkerTestsPage />} />
        <Route path="/imports" element={<ImportsPage />} />
        <Route path="/imports/history" element={<ImportHistoryPage />} />
        <Route
          element={
            <CapabilityRoute
              permissions={["reports.view"]}
              roles={["Super Admin", "Admin", "Doctor"]}
              allowWhenProfileUnresolved
            />
          }
        >
          <Route path="/reports" element={<ReportsPage />} />
        </Route>
        <Route
          element={
            <CapabilityRoute
              permissions={["audit_logs.view"]}
              roles={["Super Admin", "Admin"]}
              accessMode="any"
              allowWhenProfileUnresolved
            />
          }
        >
          <Route path="/app/audit-logs" element={<AuditLogsPage />} />
        </Route>
        <Route
          element={
            <CapabilityRoute
              permissions={["settings.view"]}
              roles={["Super Admin", "Admin"]}
              allowWhenProfileUnresolved
            />
          }
        >
          <Route path="/settings" element={<SettingsPage />} />
          <Route path="/settings/medicines" element={<MedicineCataloguePage />} />
        </Route>
        <Route path="/profile" element={<ProfilePage />} />
        <Route
          element={
            <CapabilityRoute
              permissions={["roles.view", "users.view_permissions"]}
              roles={["Super Admin", "Admin"]}
              accessMode="all"
              allowWhenProfileUnresolved
            />
          }
        >
          <Route path="/permissions" element={<PermissionsPage />} />
        </Route>
        <Route path="/app/infrastructure/about" element={<AboutVersionPage />} />
        <Route path="/app/infrastructure/diagnostics" element={<InstallerDiagnosticsPage />} />
        <Route path="/app/infrastructure/upgrade" element={<UpgradeSafetyPage />} />
        <Route element={<CentralOnlyRoute />}>
          <Route path="/app/infrastructure/central" element={<CentralServerDashboardPage />} />
        </Route>
        <Route element={<MobileOnlyRoute />}>
          <Route path="/app/infrastructure/mobile" element={<MobileDeviceDashboardPage />} />
        </Route>
        <Route element={<CentralOnlyRoute />}>
          <Route path="/app/infrastructure/central/devices" element={<CentralRegisteredDevicesPage />} />
          <Route path="/app/infrastructure/central/submissions" element={<CentralMissionSubmissionsPage />} />
          <Route path="/app/infrastructure/backups" element={<CentralBackupsPage />} />
        </Route>
        <Route path="/sync/status" element={<SyncConnectionPage />} />
        <Route element={<CapabilityRoute capability="central_authority" roles={["Super Admin", "Admin", "Doctor", "Assistant"]} />}>
          <Route path="/sync/conflicts" element={<SyncConflictsPage />} />
        </Route>
        <Route path="/sync/central" element={<CentralSyncPage />} />
        <Route element={<CentralOnlyRoute />}>
          <Route path="/app/infrastructure/central-sync" element={<CentralSyncPage />} />
        </Route>
        <Route element={<MobileOnlyRoute />}>
          <Route path="/sync/mission" element={<MissionOperationsPage />} />
        </Route>
        <Route path="/sync/connection" element={<SyncConnectionPage />} />
      </Route>

      <Route element={<CampaignWorkspaceGuard />}>
        <Route element={<CampaignWorkspaceShell />}>
          <Route
            path="/app/workspace/:campaignId"
            element={<Navigate to="dashboard" replace />}
          />
          <Route
            path="/app/workspace/:campaignId/dashboard"
            element={<CampaignWorkspaceDashboardPage />}
          />
          <Route
            path="/app/workspace/:campaignId/tests"
            element={<CampaignWorkspaceTestsPage />}
          />
          <Route
            path="/app/workspace/:campaignId/medical-tests"
            element={<MedicalTestsPage />}
          />
          <Route
            path="/app/workspace/:campaignId/workers"
            element={<CampaignWorkspaceWorkersPage />}
          />
          <Route
            path="/app/workspace/:campaignId/workers/create"
            element={<WorkerMedicalFilePage />}
          />
          <Route
            path="/app/workspace/:campaignId/workers/:workerId"
            element={<WorkerMedicalFilePage />}
          />
          <Route
            path="/app/workspace/:campaignId/workers/:workerId/medical-file"
            element={<WorkerMedicalFilePage />}
          />
          <Route
            path="/app/workspace/:campaignId/workers/:workerId/medical-visits/:visitId"
            element={<WorkerMedicalFilePage />}
          />
          <Route
            path="/app/workspace/:campaignId/import"
            element={<CampaignWorkspaceImportPage />}
          />
          <Route
            path="/app/workspace/:campaignId/sync"
            element={<CampaignWorkspaceSyncPage />}
          />
          <Route
            path="/app/workspace/:campaignId/settings"
            element={<CampaignWorkspaceSettingsPage />}
          />
        </Route>
      </Route>
    </Route>

    <Route path="/404" element={<NotFoundPage />} />
    <Route path="*" element={<Navigate to="/404" replace />} />
  </Routes>
);
