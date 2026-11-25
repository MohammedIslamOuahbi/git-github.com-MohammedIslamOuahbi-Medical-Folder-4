export interface DashboardCampaignItem {
  id: number;
  company_id?: number | null;
  branch_id?: number | null;
  title?: string;
  name?: string;
  doctor_name?: string | null;
  company_name?: string | null;
  branch_name?: string | null;
  status: string;
  start_date: string;
  end_date: string;
  doctors_count?: number;
  worker_count?: number;
  tests_count?: number;
  assistants_count?: number;
  doctor_names?: string[];
  worker_names?: string[];
  test_names?: string[];
  assistant_names?: string[];
}

export interface DashboardImportItem {
  id: number;
  file_name?: string;
  filename?: string;
  status: string;
  total_rows?: number;
  imported_rows?: number;
  created_at: string;
}

export interface DashboardAuditItem {
  id: number;
  action: string;
  actor_name?: string | null;
  actor_email?: string | null;
  actor_role?: string | null;
  entity_type: string;
  entity_id?: number | null;
  entity_name?: string | null;
  ip_address?: string | null;
  details_summary?: string | null;
  created_at: string;
}

export interface DashboardWorkerTestItem {
  id: number;
  worker_id: number;
  test_id?: number;
  medical_test_id?: number;
  status: string;
  is_normal?: boolean | null;
  abnormal?: boolean;
  worker_name?: string;
  test_name?: string;
  completed_at?: string | null;
}

export interface AdminDashboardData {
  total_users: number;
  total_doctors: number;
  total_assistants: number;
  total_companies: number;
  total_branches: number;
  total_drilling_sites: number;
  total_workers: number;
  total_campaigns: number;
  active_campaigns: number;
  completed_campaigns: number;
  total_medical_tests: number;
  total_worker_tests: number;
  abnormal_results: number;
  pending_imports: number;
  recent_campaigns: DashboardCampaignItem[];
  recent_imports: DashboardImportItem[];
  recent_audit_logs: DashboardAuditItem[];
}

export interface DoctorDashboardData {
  assigned_campaigns: number;
  active_campaigns: number;
  pending_worker_tests: number;
  completed_worker_tests: number;
  abnormal_results: number;
  workers_reviewed_today: number;
  recent_worker_tests: DashboardWorkerTestItem[];
  upcoming_campaigns: DashboardCampaignItem[];
}

export interface AssistantDashboardData {
  assigned_campaigns: number;
  pending_imports: number;
  completed_imports: number;
  failed_imports: number;
  imported_workers: number;
  validation_errors: number;
  duplicate_rows: number;
  recent_import_jobs: DashboardImportItem[];
  campaigns_ready_for_preparation: DashboardCampaignItem[];
}

export type DashboardMeData =
  | { role: "Admin"; data: AdminDashboardData }
  | { role: "Doctor"; data: DoctorDashboardData }
  | { role: "Assistant"; data: AssistantDashboardData };
