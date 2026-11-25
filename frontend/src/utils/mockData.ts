import type {
  AuditLog,
  Branch,
  Campaign,
  Company,
  DrillingSite,
  ImportJob,
  MedicalTest,
  User,
  Worker,
  WorkerTest,
  OrientationCertificate,
} from "@/types/entities";
import type {
  AdminDashboardData,
  AssistantDashboardData,
  DoctorDashboardData,
} from "@/types/dashboard";

export const mockUsers: User[] = [
  {
    id: 1,
    first_name: "Amina",
    last_name: "Bensaid",
    full_name: "Amina Bensaid",
    email: "admin@ibnsina.com",
    phone: "+213555100100",
    role: "Admin",
    status: "active",
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  },
  {
    id: 2,
    first_name: "Samir",
    last_name: "Khelil",
    full_name: "Samir Khelil",
    email: "doctor@clinic.local",
    role: "Doctor",
    status: "active",
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  },
];

export const mockCompanies: Company[] = [
  {
    id: 1,
    name: "Sahara Energy",
    code: "SE-001",
    address: "Hassi Messaoud",
    phone: "+213555300300",
    contract_start_date: "2026-01-01",
    contract_end_date: "2026-12-31",
    worker_count: 420,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  },
];
export const mockOrientations: OrientationCertificate[] = [
  {
    id: 1,
    worker_id: 1,
    campaign_id: 1,
    doctor_id: 2,
    orientation_number: "OR-001",
    orientation_date: new Date().toISOString(),
    orientation_type: "Initial",
    orientation_details: "Orientation for new workers in Q2 campaign.",
    status: "signed",
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  },
];

export const mockBranches: Branch[] = [
  {
    id: 1,
    name: "South Operations",
    company_id: 1,
    company_name: "Sahara Energy",
    address: "Ouargla",
    manager_name: "Rachid Yahi",
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  },
];

export const mockSites: DrillingSite[] = [
  {
    id: 1,
    name: "Rig Alpha 7",
    company_id: 1,
    branch_id: 1,
    branch_name: "South Operations",
    company_name: "Sahara Energy",
    location: "Block 14",
    status: "active",
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  },
];

export const mockWorkers: Worker[] = [
  {
    id: 1,
    employee_code: "WK-1001",
    first_name: "Youssef",
    last_name: "Mekki",
    full_name: "Youssef Mekki",
    company_id: 1,
    branch_id: 1,
    drilling_site_id: 1,
    position: "Rig Operator",
    etat_actual: "present",
    gender: "Male",
    age: 34,
    status: "active",
    last_test_date: new Date().toISOString(),
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  },
];

export const mockCampaigns: Campaign[] = [
  {
    id: 1,
    name: "Q2 Desert Fitness Campaign",
    company_id: 1,
    branch_id: 1,
    drilling_site_id: 1,
    start_date: new Date().toISOString(),
    end_date: new Date(Date.now() + 7 * 86400000).toISOString(),
    status: "active",
    worker_count: 86,
    tests_count: 5,
    doctor_id: 2,
    assistant_id: 3,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  },
];

export const mockMedicalTests: MedicalTest[] = [
  {
    id: 1,
    name: "CBC",
    section: "Examens complémentaires",
    active: true,
    config_json: {
      fields: [
        {
          name: "observation",
          label: "Observation",
          type: "textarea",
          required: false,
        },
      ],
    },
    code: "CBC",
    category: "Laboratory",
    normal_range: "4.5-11.0",
    price: 15,
    status: "active",
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  },
];

export const mockWorkerTests: WorkerTest[] = [
  {
    id: 1,
    worker_id: 1,
    worker_name: "Youssef Mekki",
    campaign_id: 1,
    test_id: 1,
    medical_test_id: 1,
    test_name: "CBC",
    result: "Elevated WBC",
    values: {
      observation: "Elevated WBC",
    },
    status: "reviewed",
    abnormal: true,
    tested_at: new Date().toISOString(),
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  },
];

export const mockImportJobs: ImportJob[] = [
  {
    id: 1,
    filename: "workers_q2.xlsx",
    status: "completed",
    imported_rows: 126,
    validation_errors: 3,
    duplicate_rows: 1,
    uploaded_by: "Amina Bensaid",
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  },
];

export const mockAuditLogs: AuditLog[] = [
  {
    id: 1,
    action: "CREATE",
    entity_type: "campaign",
    entity_id: 1,
    actor_name: "Amina Bensaid",
    description: "Created campaign Q2 Desert Fitness Campaign",
    ip_address: "127.0.0.1",
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  },
];

export const mockAdminDashboard: AdminDashboardData = {
  total_users: 18,
  total_doctors: 6,
  total_assistants: 5,
  total_companies: 9,
  total_branches: 22,
  total_drilling_sites: 31,
  total_workers: 1480,
  total_campaigns: 44,
  active_campaigns: 8,
  completed_campaigns: 31,
  total_medical_tests: 25,
  total_worker_tests: 3400,
  abnormal_results: 73,
  pending_imports: 2,
  recent_campaigns: mockCampaigns,
  recent_imports: mockImportJobs,
  recent_audit_logs: mockAuditLogs,
};

export const mockDoctorDashboard: DoctorDashboardData = {
  assigned_campaigns: 4,
  active_campaigns: 2,
  pending_worker_tests: 19,
  completed_worker_tests: 164,
  abnormal_results: 7,
  workers_reviewed_today: 14,
  recent_worker_tests: mockWorkerTests,
  upcoming_campaigns: mockCampaigns,
};

export const mockAssistantDashboard: AssistantDashboardData = {
  assigned_campaigns: 3,
  pending_imports: 2,
  completed_imports: 14,
  failed_imports: 1,
  imported_workers: 820,
  validation_errors: 6,
  duplicate_rows: 4,
  recent_import_jobs: mockImportJobs,
  campaigns_ready_for_preparation: mockCampaigns,
};
