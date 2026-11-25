import type { Campaign } from "./entities";
import type { Worker } from "./entities";

export interface WorkspaceCampaign extends Campaign {
  company_name?: string;
  branch_name?: string;
  site_name?: string;
}

export type WorkspaceSettings = Record<string, unknown>;

export interface Workspace {
  id: number;
  name: string;
  campaign_id: number;
  company_id: number;
  branch_id: number;
  drilling_site_id?: number | null;
  workspace_code: string;
  start_date: string;
  end_date: string;
  status: string;
  is_locked: boolean;
  sync_status?: string;
  created_at: string;
  updated_at: string;
  campaign_name?: string;
  campaignName?: string;
  company_name?: string;
  companyName?: string;
  branch_name?: string;
  branchName?: string;
  drilling_site_name?: string;
  drillingSiteName?: string;
  settings_json?: WorkspaceSettings | null;
}

export interface WorkspaceSession {
  workspace: Workspace;
  access_granted: boolean;
}

export interface ClinicalExam {
  ophthalmology: {
    observations: string;
  };
  ent: {
    nose: string;
    ears: string;
    throat: string;
  };
  stomatology: {
    teeth: string;
    others: string;
  };
  cardiovascular: {
    bloodPressure: string;
    dyspnea: string;
  };
  respiratory: {
    chronicCough: string;
    asthma: string;
  };
  digestive: {
    ulcer: string;
    colopathy: string;
    hemorrhoids: string;
    others: string;
  };
  urogenital: {
    dysuria: string;
    impotence: string;
    others: string;
  };
  endocrine: {
    diabetes: string;
    thyroid: string;
    others: string;
  };
  hematology: {
    hemostasis: string;
    adenopathy: string;
    others: string;
  };
  neuroPsychiatric: {
    headachesVertigo: string;
    neurologicalSigns: string;
    personalityDisorders: string;
    others: string;
  };
  osteoArticular: {
    polyarthralgia: string;
  };
  dermatology: {
    lesions: string;
    skinAllergies: string;
    urticaria: string;
  };
  doctorGeneralObservations: {
    comments: string;
    recommendations: string;
  };
}

export interface ComplementaryExams {
  cardiology: {
    ecg: string;
  };
  audiology: {
    audiogram: string;
  };
  respiratory: {
    efr: string;
  };
  biology: {
    glycemia: string;
    hba1c: string;
    urea: string;
    creatinine: string;
    cholesterol: string;
    triglycerides: string;
    hdlLdl: string;
    urineChemistry: string;
  };
  hematology: {
    gr: string;
    gb: string;
    hb: string;
    ht: string;
    vgm: string;
    ccmh: string;
    plt: string;
    pn: string;
    lymphocytes: string;
    bem: string;
    vs: string;
  };
  parasitology: {
    stoolExam: string;
  };
  radiology: {
    chestXray: string;
    others: string;
  };
  otherExams: {
    freeText: string;
  };
}

export interface MedicalDecision {
  orientation: {
    specialistAdvice: boolean;
    specialistAdviceDetails: string;
    treatment: boolean;
    treatmentDetails: string;
    hospitalization: boolean;
    hospitalizationDetails: string;
    specialty: string;
  };
  specialistResponse: {
    response: string;
    socialService: string;
    employmentService: string;
  };
  cat: {
    conduct: string;
  };
  aptitude:
    | "apte"
    | "apte_with_restrictions"
    | "temporarily_unfit"
    | "definitively_unfit"
    | "";
  restrictions: {
    professionalRestrictions: string;
  };
  interpretation: {
    decisionInterpretation: string;
  };
  recommendations: {
    doctorRecommendations: string;
  };
  nextVisit: {
    nextVisitSchedule: string;
    nextVisitCustomMonths: string;
    nextVisitDate: string;
  };
  validation: {
    validatingDoctor: string;
    validationDate: string;
    electronicSignature: string;
    includeValidatorSignature: boolean;
    includeDoctorSignature?: boolean;
    includeWorkspaceSignature?: boolean;
    validatorId?: number | null;
    validatorName?: string | null;
    validatorRole?: string | null;
    validatedAt?: string | null;
  };
}
  

export interface MedicalAptitude {
  aptitude: "apte" | "apte_with_restrictions" | "temporarily_unfit" | "definitively_unfit" | "";
  professionalRestrictions: string;
  decisionInterpretation: string;
  doctorRecommendations: string;
  nextVisitSchedule: string;
  nextVisitCustomMonths: string;
  nextVisitDate: string;
  validatingDoctor: string;
  validationDate: string;
  electronicSignature: string;
  includeValidatorSignature: boolean;
  includeDoctorSignature?: boolean;
  includeWorkspaceSignature?: boolean;
  validatorId?: number | null;
  validatorName?: string | null;
  validatorRole?: string | null;
  validatedAt?: string | null;
}

export interface ProfilTaGlycemie {
  fullName: string;
  rows: Array<{
    id: string;
    date: string;
    rightArm: string;
    leftArm: string;
    time: string;
    glycemia: string;
    observation?: string;
  }>;
}

export interface WorkStoppageCertificate {
  doctorFullName: string;
  workerFullName: string;
  workerAge: string;
  position: string;
  workStopDuration: string;
  workStopExtensionDuration: string;
  returnToWork: boolean;
  startDate: string;
  endDate: string;
  issuedAt: string;
  status: "draft" | "validated";
  includeValidatorSignature: boolean;
}

export interface WorkerMedicalFileForm {
  medicalFileNumber: string;
  employeeCode: string;
  nationalId: string;
  lastName: string;
  firstName: string;
  sex: string;
  dateOfBirth: string;
  birthPlace: string;
  familySituation: string;
  phone: string;
  originAddress: string;
  professionalAddress: string;
  direction: string;
  position: string;
  etat_actual: Worker["etat_actual"];
  department: string;
  service: string;
  workshop: string;
  schoolEducation: string;
  professionalTraining: string;
  professionalQualification: string;
  nationalServiceStatus: string;
  nationalServiceNotes: string;
  chronicDiseaseNotes: string;
  bloodGroup: string;
  congenitalDiseases: string;
  generalDiseases: string;
  surgicalInterventions: string;
  accidents: string;
  intoxications: string;
  tobacco: string;
  chewingTobacco: string;
  alcoholism: string;
  otherIntoxications: string;
  familyHistoryFather: string;
  familyHistoryMother: string;
  familyHistorySisters: string;
  familyHistoryBrothers: string;
  familyHistorySpouse: string;
  familyHistoryChildrenBoys: string;
  familyHistoryChildrenGirls: string;
  professionalDiseaseNotes: string;
  companyName: string;
  siteName: string;
  professionalHistory: Array<{
    id: string;
    occupiedPosition: string;
    fromDate: string;
    toDate: string;
    workplaceAndRisks: string;
  }>;
  vaccinations: Array<{
    id: string;
    vaccineName: string;
    firstDose: string;
    secondDose: string;
    firstBooster: string;
    secondBooster: string;
  }>;
  workAccidents: Array<{
    id: string;
    date: string;
    place: string;
    consequences: string;
  }>;
  occupationalDiseases: Array<{
    id: string;
    date: string;
    place: string;
    exposedProducts: string;
    symptoms: string;
    tmpNumber: string;
    ipp: string;
  }>;
  spontaneousConsultations: Array<{
    id: string;
    date: string;
    observation: string;
  }>;
  internalVisitHire: boolean;
  internalVisitPeriodic: boolean;
  internalVisitDate: string;
  internalVisitDoctor: string;
  internalVisitWeightKg: string;
  internalVisitHeightCm: string;
  internalVisitTa: string;
  internalVisitFc: string;
  internalVisitDistanceOdSc: string;
  internalVisitDistanceOdAc: string;
  internalVisitDistanceOgSc: string;
  internalVisitDistanceOgAc: string;
  internalVisitDistanceOdg: string;
  clinicalExam: ClinicalExam;
  complementaryExams: ComplementaryExams;
  profilTaGlycemie: ProfilTaGlycemie;
  medicalDecision: MedicalDecision;
  workStoppageCertificate: WorkStoppageCertificate | null;
  confirmationStatus: "draft" | "confirmed";
  confirmationDoctor: string;
  confirmationDate: string;
  confirmationSignature: string;
  isLocked: boolean;
  auditTrail: Array<{
    id: string;
    action: string;
    actor: string;
    at: string;
  }>;
}
