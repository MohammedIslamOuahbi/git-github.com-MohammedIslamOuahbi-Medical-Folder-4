import type { BaseEntity } from "./common";

export interface User extends BaseEntity {
  first_name: string;
  last_name: string;
  full_name: string;
  email: string;
  phone?: string;
  qualification?: string | null;
  role: "Super Admin" | "Admin" | "Doctor" | "Assistant";
  status: "active" | "inactive";
  company_id?: number | null;
  branch_id?: number | null;
  permissions?: string[];
}

export interface Company extends BaseEntity {
  name: string;
  code: string;
  address?: string;
  phone?: string;
  email?: string;
  contract_start_date?: string | null;
  contract_end_date?: string | null;
  worker_count?: number;
}

export interface Branch extends BaseEntity {
  name: string;
  company_id: number;
  company_name?: string;
  location?: string;
  address?: string;
  manager_name?: string;
}

export interface DrillingSite extends BaseEntity {
  company_id: number;
  name: string;
  branch_id: number;
  branch_name?: string;
  company_name?: string;
  location: string;
  status: "active" | "inactive";
}

export interface Worker extends BaseEntity {
  employee_code: string;
  employee_number?: string;
  etat_actual:
    | "present"
    | "absence"
    | "sick_leave"
    | "recovery"
    | "mission"
    | "work_accident"
    | "annual_leave"
    | "unpaid_leave"
    | "maternity_leave"
    | "paternity_leave"
    | "retired"
    | "suspended"
    | "terminated";
  national_id?: string | null;
  medical_file_data?: object | null;
  first_name: string;
  last_name: string;
  full_name: string;
  company_id: number;
  branch_id: number;
  drilling_site_id?: number | null;
  position: string;
  job_title?: string | null;
  department?: string | null;
  gender?: string;
  birth_date?: string | null;
  birth_wilaya?: string | null;
  marital_status?: string | null;
  blood_group?: string | null;
  phone?: string | null;
  emergency_phone?: string | null;
  address?: string | null;
  hire_date?: string | null;
  age?: number;
  status: "active" | "inactive" | "pending";
  medical_status?: string | null;
  photo?: string | null;
  is_active?: boolean;
  campaign_status?: "pending" | "completed" | string | null;
  last_test_date?: string | null;
  medical_file_status?: string | null;
  latest_visit_date?: string | null;
  latest_visit_id?: number | null;
}

export type MedicalVisitStatus =
  | "draft"
  | "basic_info_completed"
  | "tests_in_progress"
  | "ready_for_doctor"
  | "validated"
  | "needs_correction"
  | "synced";

export interface MedicalVisit extends BaseEntity {
  uuid?: string;
  worker_id: number;
  worker_uuid?: string;
  campaign_id?: number | null;
  campaign_uuid?: string | null;
  visit_date: string;
  site_name?: string | null;
  status: MedicalVisitStatus;
  form_data?: Record<string, unknown> | null;
  created_by?: number | null;
  updated_by?: number | null;
  validated_by?: number | null;
  validated_at?: string | null;
  doctor_notes?: string | null;
  last_synced_at?: string | null;
  version?: number;
}

export interface PrescriptionItem {
  id: number;
  medicine_id?: number | null;
  medication_name: string;
  brand_name?: string | null;
  generic_name?: string | null;
  strength?: string | null;
  pharmaceutical_form?: string | null;
  dosage?: string | null;
  dose_quantity?: string | null;
  dose_unit?: string | null;
  frequency?: string | null;
  frequency_custom?: string | null;
  duration?: string | null;
  duration_value?: string | null;
  duration_unit?: string | null;
  quantity?: string | null;
  number_of_boxes?: string | null;
  instructions?: string | null;
  sort_order?: number | null;
  created_at: string;
  updated_at: string;
}

export interface Prescription {
  id: number;
  worker_id: number;
  campaign_id: number;
  medical_visit_id?: number | null;
  doctor_id?: number | null;
  prescription_number: string;
  prescription_date: string;
  diagnosis?: string | null;
  notes?: string | null;
  includeValidatorSignature?: boolean;
  validatorId?: number | null;
  validatorName?: string | null;
  validatorRole?: string | null;
  validatedAt?: string | null;
  validatorSignatureUrl?: string | null;
  validator_signature_url?: string | null;
  validator_signature_image_path?: string | null;
  status: "draft" | "signed" | "confirmed" | "validated" | "printed" | "cancelled";
  worker_name?: string | null;
  doctor_name?: string | null;
  items: PrescriptionItem[];
  created_at: string;
  updated_at: string;
  deleted_at?: string | null;
}




export interface OrientationCertificate {
  id: number;
  worker_id: number;
  campaign_id: number;
  medical_visit_id?: number | null;
  doctor_id?: number | null;
  orientation_number: string;  // Format: OR-2026-0001
  orientation_date: string;
  orientation_type: string;
  orientation_types?: {
    specialistAdvice: boolean;
    diagnosticCare: boolean;
    other: boolean;
  } | null;
  orientationTypes?: {
    specialistAdvice: boolean;
    diagnosticCare: boolean;
    other: boolean;
  } | null;
  orientation_type_other?: string | null;
  orientationTypeOther?: string | null;
  orientation_details?: string | null;
  patient_name?: string | null;
  patientName?: string | null;
  includeValidatorSignature?: boolean;
  includeDoctorSignature?: boolean;
  includeWorkspaceSignature?: boolean;
  validatorId?: number | null;
  validatorName?: string | null;
  validatorRole?: string | null;
  validatedAt?: string | null;
  validatorSignatureUrl?: string | null;
  validator_signature_url?: string | null;
  validator_signature_image_path?: string | null;
  status: "draft" | "signed" | "confirmed" | "validated" | "printed" | "cancelled";
  worker_name?: string | null;
  doctor_name?: string | null;
  created_at: string;
  updated_at: string;
  deleted_at?: string | null;
}

export type AptitudeCertificateStatus = "draft" | "confirmed" | "validated";

export interface AptitudeCertificate {
  id: number;
  worker_id: number;
  campaign_id: number;
  medical_visit_id?: number | null;
  doctor_id?: number | null;
  certificate_number: string;  // Format: AP-2026-0001
  issue_date: string;
  visit_date?: string | null;
  aptitude: string;
  aptitude_interpretation?: string | null;
  doctor_recommendations?: string | null;
  next_visit_date?: string | null;
  includeValidatorSignature?: boolean;
  include_validator_signature?: boolean;
  includeDoctorSignature?: boolean;
  include_doctor_signature?: boolean;
  includeWorkspaceSignature?: boolean;
  include_workspace_signature?: boolean;
  validatorId?: number | null;
  validatedByUserId?: number | null;
  validated_by_user_id?: number | null;
  validatorName?: string | null;
  validator_name?: string | null;
  validatorRole?: string | null;
  validator_role?: string | null;
  validatedByRole?: string | null;
  validated_by_role?: string | null;
  validatedAt?: string | null;
  validated_at?: string | null;
  status: AptitudeCertificateStatus;
  medicalVisitId?: number | null;
  certificateNumber?: string;
  firstName?: string;
  lastName?: string;
  companyName?: string | null;
  jobTitle?: string | null;
  birthDate?: string | null;
  birthPlace?: string | null;
  bloodGroup?: string | null;
  validatedDoctorName?: string | null;
  validated_doctor_name?: string | null;
  validatorSignatureUrl?: string | null;
  validator_signature_url?: string | null;
  validatedDoctorSignatureUrl?: string | null;
  validated_doctor_signature_url?: string | null;
  signatureUrl?: string | null;
  signature_url?: string | null;
  validator?: {
    signatureUrl?: string | null;
    signature_url?: string | null;
    signature_path?: string | null;
  } | null;
  worker_full_name?: string | null;
  doctor_name?: string | null;
  created_at: string;
  updated_at: string;
  deleted_at?: string | null;
}

export interface Campaign extends BaseEntity {
  name: string;
  title?: string;
  description?: string | null;
  company_id: number;
  branch_id: number;
  drilling_site_id?: number | null;
  start_date: string;
  end_date: string;
  status: "draft" | "active" | "completed";
  doctor_id?: number | null;
  assistant_id?: number | null;
  worker_count?: number;
  tests_count?: number;
}

export interface MedicalTest extends BaseEntity {
  name: string;
  section: string;
  description?: string | null;
  label?: string;
  active: boolean;
  config_json?: unknown;
  code?: string;
  category?: string;
  normal_range?: string;
  price?: number;
  status?: "active" | "inactive";
}

export interface CampaignTestAssignment {
  id: number;
  campaign_test_id?: number;
  campaign_id: number;
  test_id: number;
  name?: string | null;
  description?: string | null;
  type?: string | null;
  required: boolean;
  test: MedicalTest | null;
  created_at: string;
  updated_at: string;
}

export interface WorkerTest extends BaseEntity {
  worker_id: number;
  worker_name?: string;
  campaign_id?: number | null;
  test_id?: number;
  medical_test_id: number;
  test_name?: string;
  result?: string;
  values?: Record<string, unknown>;
  status: "pending" | "completed" | "reviewed";
  abnormal: boolean;
  tested_at?: string | null;
  completed_at?: string | null;
  notes?: string | null;
  is_normal?: boolean | null;
}

export interface ImportJob extends BaseEntity {
  filename: string;
  status: "pending" | "validated" | "completed" | "failed";
  imported_rows: number;
  validation_errors: number;
  duplicate_rows: number;
  uploaded_by?: string;
  mapping_json?: Record<string, string> | null;
}

export interface AuditLog extends BaseEntity {
  action: string;
  entity_type: string;
  entity_id?: number | null;
  actor_name?: string | null;
  actor_email?: string | null;
  actor_role?: string | null;
  entity_name?: string | null;
  description?: string | null;
  details_summary?: string | null;
  ip_address?: string | null;
}

export interface ReportFilter {
  company_id?: number;
  branch_id?: number;
  campaign_id?: number;
  from_date?: string;
  to_date?: string;
}
