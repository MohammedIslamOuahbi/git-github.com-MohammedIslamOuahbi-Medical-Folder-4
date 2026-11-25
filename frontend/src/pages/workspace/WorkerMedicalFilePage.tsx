import { useEffect, useMemo, useRef, useState } from "react";
import type { ChangeEvent, ReactNode } from "react";
import type { LucideIcon } from "lucide-react";
import {
  Activity,
  AlertCircle,
  AlertTriangle,
  BadgeCheck,
  BriefcaseMedical,
  Brain,
  Bone,
  Bug,
  CalendarDays,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  ClipboardCheck,
  ClipboardList,
  Download,
  FileDown,
  FileSpreadsheet,
  FileText,
  FlaskConical,
  HeartPulse,
  Droplet,
  Droplets,
  Ear,
  Eye,
  Microscope,
  Pill,
  Plus,
  Printer,
  Scan,
  ScanEye,
  ShieldCheck,
  ShieldPlus,
  Save,
  Smile,
  Stethoscope,
  TestTube,
  Volume2,
  Wind,
  Trash2,
  UserPlus,
  UserRound,
  Users,
  Pencil,
} from "lucide-react";
import { useLocation, useNavigate, useParams } from "react-router-dom";
import { campaignsApi } from "@/api/campaignsApi";
import { aptitudeCertificatesApi } from "@/api/aptitudeCertificatesApi";
import { medicalVisitsApi } from "@/api/medicalVisitsApi";
import { prescriptionsApi } from "@/api/prescriptionsApi";
import { workersApi } from "@/api/workersApi";
import { Button } from "@/components/common/Button";
import { Card } from "@/components/common/Card";
import { EmptyState } from "@/components/common/EmptyState";
import { Input } from "@/components/common/Input";
import { Modal } from "@/components/common/Modal";
import { Select } from "@/components/common/Select";
import { Spinner } from "@/components/common/Spinner";
import { Textarea } from "@/components/common/Textarea";
import { EditableMedicalTable } from "@/components/workspace/EditableMedicalTable";
import { MedicalVisitsPanel } from "@/components/workspace/MedicalVisitsPanel";
import { WorkerAlreadyExistsModal, type WorkerLookupHistory } from "@/components/workspace/WorkerAlreadyExistsModal";
import { MedicineAutocomplete } from "@/components/ordonnance/MedicineAutocomplete";
import { useAuth } from "@/hooks/useAuth";
import { useCampaignWorkspace } from "@/context/CampaignWorkspaceContext";
import { JOB_TITLES } from "@/data/jobTitles";
import type {
  AptitudeCertificate,
  Campaign,
  CampaignTestAssignment,
  MedicalVisit,
  OrientationCertificate,
  Prescription,
  Worker,
} from "@/types/entities";
import type {
  ClinicalExam,
  ComplementaryExams,
  MedicalDecision,
  WorkerMedicalFileForm,
} from "@/types/workspace";
import { orientationsApi } from "@/api/orientationsApi";
import { cn } from "@/utils/cn";
import SummaryCard from "@/components/medical-tests/SummaryCard";
import { PhoneInput } from "@/components/common/PhoneInput";
import { SectionHeader } from "@/components/common/SectionHeader";
import { WORKER_ETAT_ACTUAL_OPTIONS } from "@/constants/workerEtatActual";
import { formatDisplayDate, toIsoDate } from "@/utils/date";
import { buildPrescriptionPreviewText } from "@/utils/prescriptionFormatter";
import { getApiErrorMessage } from "@/services/syncConnectionApi";
import * as XLSX from "xlsx";
import type { MedicineSearchItem } from "@/types/medicine";

const algeriaWilayas = [
  "Adrar",
  "Chlef",
  "Laghouat",
  "Oum El Bouaghi",
  "Batna",
  "Bejaia",
  "Biskra",
  "Bechar",
  "Blida",
  "Bouira",
  "Tamanrasset",
  "Tebessa",
  "Tlemcen",
  "Tiaret",
  "Tizi Ouzou",
  "Algiers",
  "Djelfa",
  "Jijel",
  "Setif",
  "Saida",
  "Skikda",
  "Sidi Bel Abbes",
  "Annaba",
  "Guelma",
  "Constantine",
  "Medea",
  "Mostaganem",
  "MSila",
  "Mascara",
  "Ouargla",
  "Oran",
  "El Bayadh",
  "Illizi",
  "Bordj Bou Arreridj",
  "Boumerdes",
  "El Tarf",
  "Tindouf",
  "Tissemsilt",
  "El Oued",
  "Khenchela",
  "Souk Ahras",
  "Tipaza",
  "Mila",
  "Ain Defla",
  "Naama",
  "Ain Temouchent",
  "Ghardaia",
  "Relizane",
  "Timimoun",
  "Bordj Badji Mokhtar",
  "Ouled Djellal",
  "Beni Abbes",
  "In Salah",
  "In Guezzam",
  "Touggourt",
  "Djanet",
  "El MGhair",
  "El Meniaa",
] as const;


const textareaClassName =
  "w-full rounded-2xl border border-slate-200 bg-slate-50/80 px-3 py-3.5 text-sm font-medium text-slate-800 outline-none transition-all duration-200 focus:border-cyan-400/40 focus:bg-white focus:ring-4 focus:ring-cyan-500/10";

const hasSpecialtyInput = (specialty: string) => specialty.trim() !== "";

const normalizeInternalVisitType = (
  form: Pick<WorkerMedicalFileForm, "internalVisitHire" | "internalVisitPeriodic">,
) => {
  if (form.internalVisitHire) {
    return { internalVisitHire: true, internalVisitPeriodic: false };
  }

  if (form.internalVisitPeriodic) {
    return { internalVisitHire: false, internalVisitPeriodic: true };
  }

  return { internalVisitHire: false, internalVisitPeriodic: false };
};

const medicalFolderSectionDefinitions = [
  {
    id: "personal",
    label: "Identite",
    description: "Etat civil et coordonnees",
    icon: UserRound,
  },
  {
    id: "professional",
    label: "Informations professionnelles",
    description: "Affectation, parcours et qualification",
    icon: BriefcaseMedical,
  },
  {
    id: "medical",
    label: "Antecedents medicaux",
    description: "Historique medical et vaccination",
    icon: HeartPulse,
  },
  {
    id: "family",
    label: "Antecedents familiaux",
    description: "Contexte familial de sante",
    icon: Users,
  },
  {
    id: "risks",
    label: "Risques professionnels",
    description: "Expositions, accidents et maladies",
    icon: AlertTriangle,
  },
  {
    id: "consultations",
    label: "Consultations",
    description: "Suivi et observations",
    icon: ClipboardList,
  },
  {
    id: "pdfDossier",
    label: "PDF Dossier Medical",
    description: "Visualisation du dossier medical genere",
    icon: FileDown,
  },
] as const;

const medicalVisitSectionDefinitions = [
  {
    id: "internalVisit",
    label: "Fich intern de visit Medicale",
    description: "Synthese de visite et constantes",
    icon: FileDown,
  },
  {
    id: "clinicalExam",
    label: "Examen clinique",
    description: "Evaluation clinique detaillee",
    icon: Stethoscope,
  },
  {
    id: "complementaryExams",
    label: "Examens complementaires",
    description: "Biologie et examens associes",
    icon: FlaskConical,
  },
  {
    id: "medicalDecision",
    label: "Decision medicale",
    description: "Orientation, aptitude et validation",
    icon: BadgeCheck,
  },
  {
    id:"medicalOrientation",
    label: "C-Medical d'orientation",
    description: "Document de synthese pour orientation specialisee",
    icon: FileDown,
  },
  {
    id:"medicalAptitude",
    label: "C-Medical d'aptitude",
    description: "Document de synthese pour aptitude professionnelle",
    icon: FileDown,
  },
   {
    id:"profilTaGlycemie",
    label: "Profil TA et Glycemie",
    description: "Document de suivi des constantes TA et Glycemie",
    icon: FileDown,
  },
 
  {
    id: "pdfViewer",
    label: "PDF Fich Intern ",
    description: "Visualisation du PDF genere",
    icon: FileDown,
  },
  
  {
    id: "ordonnance",
    label: "Ordonnance",
    description: "Prescription, signature et impression",
    icon: Pill,
  },
   {
    id:"medicalArretTravail",
    label: "CM d'arret de travail",
    description: "Document de synthese pour arret de travail",
    icon: FileDown,
  },
] as const;

const sectionDefinitions = [
  ...medicalFolderSectionDefinitions,
  ...medicalVisitSectionDefinitions,
] as const;


type TabId = (typeof sectionDefinitions)[number]["id"];

interface WorkerDocumentItem {
  id: number;
  date?: string;
  title?: string;
  doctor?: string;
  status?: string;
  pdfAvailable?: boolean;
}

type PrescriptionFormItem = {
  id: string;
  medicine_id?: number | null;
  medication_name: string;
  brand_name: string;
  generic_name: string;
  strength: string;
  pharmaceutical_form: string;
  packaging: string;
  laboratory: string;
  dosage: string;
  dose_quantity: string;
  dose_unit: string;
  frequency: string;
  frequency_custom: string;
  duration: string;
  duration_value: string;
  duration_unit: string;
  quantity: string;
  number_of_boxes: string;
  instructions: string;
  sort_order: number;
};

type PrescriptionFormState = {
  id?: number;
  medical_visit_id?: number | null;
  prescription_number: string;
  prescription_date: string;
  patient_name: string;
  age: string;
  doctor_name: string;
  diagnosis: string;
  notes: string;
  status: Prescription["status"];
  includeValidatorSignature: boolean;
  items: PrescriptionFormItem[];
};

type MedicalOrientationFormState = {
  id?: number;
  medical_visit_id?: number | null;
  orientation_number: string;
  orientation_date: string;
  patient_name: string;
  age: string;
  doctor_name: string;
  orientationTypes: {
    specialistAdvice: boolean;
    diagnosticCare: boolean;
    other: boolean;
  };
  orientationTypeOther: string;
  orientation_details: string;
  status: OrientationCertificate["status"];
  includeValidatorSignature: boolean;
  validatorId?: number | null;
  validatorName?: string | null;
  validatorRole?: string | null;
  validatedAt?: string | null;
  validatorSignatureUrl?: string | null;
};

type MedicalAptitudeFormState = {
  aptitudeId: number;
  medicalVisitId: number;
  workerId: number;
  certificateNumber: string;
  firstName: string;
  lastName: string;
  companyName: string;
  jobTitle: string;
  birthDate: string;
  birthPlace: string;
  bloodGroup: string;
  aptitude: string;
  aptitudeInterpretation: string;
  visitDate: string;
  doctorRecommendations: string;
  issueDate: string;
  validatedDoctorName: string;
  validatedByUserId?: number | null;
  validatorRole?: string | null;
  validatorSignatureUrl?: string | null;
  includeValidatorSignature: boolean;
  validatedAt?: string | null;
  status: "draft" | "confirmed";
  campaignId: number;
};

const createId = () =>
  `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;

const createProfessionalHistoryRow = () => ({
  id: createId(),
  occupiedPosition: "",
  fromDate: "",
  toDate: "",
  workplaceAndRisks: "",
});

const createVaccinationRow = () => ({
  id: createId(),
  vaccineName: "",
  firstDose: "",
  secondDose: "",
  firstBooster: "",
  secondBooster: "",
});

const createWorkAccidentRow = () => ({
  id: createId(),
  date: "",
  place: "",
  consequences: "",
});



const createOccupationalDiseaseRow = () => ({
  id: createId(),
  date: "",
  place: "",
  exposedProducts: "",
  symptoms: "",
  tmpNumber: "",
  ipp: "",
});

const createConsultationRow = () => ({
  id: createId(),
  date: "",
  observation: "",
});

const formatTA = (value: string) => {
  // remove non digits and slash
  const cleaned = value.replace(/[^\d]/g, "");

  // first 3 digits = systolic
  const part1 = cleaned.slice(0, 3);
  const part2 = cleaned.slice(3, 5);

  if (cleaned.length <= 3) {
    return part1;
  }

  return `${part1}/${part2}`;
};

const createPrescriptionItemRow = (): PrescriptionFormItem => ({
  id: createId(),
  medicine_id: null,
  medication_name: "",
  brand_name: "",
  generic_name: "",
  strength: "",
  pharmaceutical_form: "",
  packaging: "",
  laboratory: "",
  dosage: "",
  dose_quantity: "",
  dose_unit: "comprimé",
  frequency: "",
  frequency_custom: "",
  duration: "",
  duration_value: "",
  duration_unit: "jours",
  quantity: "",
  number_of_boxes: "",
  instructions: "",
  sort_order: 0,
});

const calculateAgeFromDate = (dateOfBirth?: string | null) => {
  if (!dateOfBirth) return "";
  const birthDate = new Date(dateOfBirth);
  if (Number.isNaN(birthDate.getTime())) return "";
  const today = new Date();
  let age = today.getFullYear() - birthDate.getFullYear();
  const monthDelta = today.getMonth() - birthDate.getMonth();
  if (monthDelta < 0 || (monthDelta === 0 && today.getDate() < birthDate.getDate())) {
    age -= 1;
  }
  return age >= 0 ? String(age) : "";
};

const formatWorkerFullName = (firstName?: string | null, lastName?: string | null) =>
  [firstName?.trim(), lastName?.trim()].filter(Boolean).join(" ").trim();


const createEmptyPrescriptionForm = (
  workerRecord: Worker | null,
  doctorName?: string,
): PrescriptionFormState => ({
  medical_visit_id: null,
  prescription_number: "",
  prescription_date: new Date().toISOString().slice(0, 10),
  patient_name: workerRecord?.full_name || "",
  age: calculateAgeFromDate(workerRecord?.birth_date),
  doctor_name: doctorName || "",
  diagnosis: "",
  notes: "",
  status: "draft",
  includeValidatorSignature: false,
  items: [createPrescriptionItemRow()],
});

const PRESCRIPTION_FREQUENCY_OPTIONS = [
  "1 fois par jour",
  "2 fois par jour",
  "3 fois par jour",
  "Matin",
  "Midi",
  "Soir",
  "Matin et soir",
  "Toutes les 8 heures",
  "Toutes les 12 heures",
  "Toutes les 24 heures",
  "Si besoin",
  "Autre...",
] as const;

const PRESCRIPTION_DOSE_UNIT_OPTIONS = [
  "comprimé",
  "gélule",
  "sachet",
  "ml",
  "goutte",
  "ampoule",
  "injection",
  "application",
  "bouffée",
  "suppositoire",
] as const;

const PRESCRIPTION_DURATION_UNIT_OPTIONS = ["jours", "semaines", "mois"] as const;

const normalizePrescriptionText = (value?: string | null) => (value || "").trim();

const buildPrescriptionLegacyDosage = (item: PrescriptionFormItem) =>
  [normalizePrescriptionText(item.dose_quantity), normalizePrescriptionText(item.dose_unit)]
    .filter(Boolean)
    .join(" ");

const buildPrescriptionLegacyDuration = (item: PrescriptionFormItem) =>
  [normalizePrescriptionText(item.duration_value), normalizePrescriptionText(item.duration_unit)]
    .filter(Boolean)
    .join(" ");

const hasStructuredPrescriptionItemContent = (item: PrescriptionFormItem) =>
  Boolean(
    normalizePrescriptionText(item.brand_name || item.medication_name || item.generic_name) ||
      normalizePrescriptionText(item.dose_quantity) ||
      normalizePrescriptionText(item.frequency_custom || item.frequency) ||
      normalizePrescriptionText(item.duration_value) ||
      normalizePrescriptionText(item.instructions) ||
      normalizePrescriptionText(item.number_of_boxes),
  );

const hasCompletePrescriptionItemForValidation = (item: PrescriptionFormItem) =>
  Boolean(
    normalizePrescriptionText(item.brand_name || item.medication_name || item.generic_name) &&
      normalizePrescriptionText(item.dose_quantity) &&
      normalizePrescriptionText(item.frequency_custom || item.frequency) &&
      normalizePrescriptionText(item.duration_value),
  );



const mapOrientationToForm = (
  cert: OrientationCertificate,
  workerRecord: Worker | null,
  doctorName?: string,
): MedicalOrientationFormState => {
  const legacyOrientationType = cert.orientation_type || "";
  const orientationTypesSource =
    (cert as OrientationCertificate & {
      orientationTypes?: Partial<MedicalOrientationFormState["orientationTypes"]>;
      orientation_types?: Partial<MedicalOrientationFormState["orientationTypes"]>;
    }).orientationTypes ||
    (cert as OrientationCertificate & {
      orientation_types?: Partial<MedicalOrientationFormState["orientationTypes"]>;
    }).orientation_types;

  return {
    id: cert.id,
    medical_visit_id: cert.medical_visit_id ?? null,
    orientation_number: cert.orientation_number || "",
    orientation_date: cert.orientation_date || "",
    patient_name:
      cert.patient_name ||
      (cert as OrientationCertificate & { patientName?: string }).patientName ||
      cert.worker_name ||
      workerRecord?.full_name ||
      "",
    age: calculateAgeFromDate(workerRecord?.birth_date),
    doctor_name: cert.doctor_name || doctorName || "",
    orientationTypes: {
      specialistAdvice:
        orientationTypesSource?.specialistAdvice ??
        (
          legacyOrientationType === "avis_specialise" ||
          legacyOrientationType === "cardiologie" ||
          legacyOrientationType === "ophtalmologie" ||
          Boolean((cert as OrientationCertificate & { specialistAdvice?: boolean }).specialistAdvice)
        ),
      diagnosticCare:
        orientationTypesSource?.diagnosticCare ??
        (
          legacyOrientationType === "prise_en_charge_diagnostic" ||
          Boolean((cert as OrientationCertificate & { diagnosticCare?: boolean }).diagnosticCare)
        ),
      other:
        orientationTypesSource?.other ??
        (
          legacyOrientationType === "autre" ||
          Boolean((cert as OrientationCertificate & { other?: boolean }).other)
        ),
    },
    orientationTypeOther:
      (cert as OrientationCertificate & { orientationTypeOther?: string }).orientationTypeOther ||
      cert.orientation_type_other ||
      "",
    validatorId:
      cert.validatorId ?? (cert as OrientationCertificate & { validator_id?: number | null }).validator_id ?? null,
    validatorName:
      cert.validatorName ?? (cert as OrientationCertificate & { validator_name?: string | null }).validator_name ?? "",
    validatorRole:
      cert.validatorRole ?? (cert as OrientationCertificate & { validator_role?: string | null }).validator_role ?? "",
    validatedAt:
      cert.validatedAt ?? (cert as OrientationCertificate & { validated_at?: string | null }).validated_at ?? null,
    validatorSignatureUrl:
      cert.validatorSignatureUrl ??
      cert.validator_signature_url ??
      (cert as OrientationCertificate & { validator_signature_image_path?: string | null }).validator_signature_image_path ??
      null,
    orientation_details: cert.orientation_details || "",
    status: cert.status || "draft",
    includeValidatorSignature:
      cert.includeValidatorSignature ?? cert.includeDoctorSignature ?? cert.includeWorkspaceSignature ?? false,
  };
};

const mapPrescriptionToForm = (
  prescription: Prescription,
  workerRecord: Worker | null,
  doctorName?: string,
): PrescriptionFormState => ({
  id: prescription.id,
  medical_visit_id: prescription.medical_visit_id ?? null,
  prescription_number: prescription.prescription_number,
  prescription_date: prescription.prescription_date,
  patient_name: prescription.worker_name || workerRecord?.full_name || "",
  age: calculateAgeFromDate(workerRecord?.birth_date),
  doctor_name: prescription.doctor_name || doctorName || "",
  diagnosis: prescription.diagnosis || "",
  notes: prescription.notes || "",
  status: prescription.status,
  includeValidatorSignature: prescription.includeValidatorSignature ?? false,
  items:
    prescription.items.length > 0
      ? prescription.items.map((item) => ({
          id: String(item.id),
          medicine_id: item.medicine_id ?? null,
          medication_name: item.medication_name || "",
          brand_name: item.brand_name || item.medication_name || "",
          generic_name: item.generic_name || "",
          strength: item.strength || "",
          pharmaceutical_form: item.pharmaceutical_form || "",
          packaging: "",
          laboratory: "",
          dosage: item.dosage || "",
          dose_quantity: item.dose_quantity || "",
          dose_unit: item.dose_unit || "comprimé",
          frequency: item.frequency || "",
          frequency_custom: item.frequency_custom || "",
          duration: item.duration || "",
          duration_value: item.duration_value || "",
          duration_unit: item.duration_unit || "jours",
          quantity: item.quantity || "",
          number_of_boxes: item.number_of_boxes || item.quantity || "",
          instructions: item.instructions || "",
          sort_order: item.sort_order || 0,
        }))
      : [createPrescriptionItemRow()],
});

const createEmptyClinicalExam = (): ClinicalExam => ({
  ophthalmology: { observations: "" },
  ent: { nose: "", ears: "", throat: "" },
  stomatology: { teeth: "", others: "" },
  cardiovascular: { bloodPressure: "", dyspnea: "" },
  respiratory: { chronicCough: "", asthma: "" },
  digestive: { ulcer: "", colopathy: "", hemorrhoids: "", others: "" },
  urogenital: { dysuria: "", impotence: "", others: "" },
  endocrine: { diabetes: "", thyroid: "", others: "" },
  hematology: { hemostasis: "", adenopathy: "", others: "" },
  neuroPsychiatric: {
    headachesVertigo: "",
    neurologicalSigns: "",
    personalityDisorders: "",
    others: "",
  },
  osteoArticular: { polyarthralgia: "" },
  dermatology: { lesions: "", skinAllergies: "", urticaria: "" },
  doctorGeneralObservations: { comments: "", recommendations: "" },
});

const createEmptyComplementaryExams = (): ComplementaryExams => ({
  cardiology: { ecg: "" },
  audiology: { audiogram: "" },
  respiratory: { efr: "" },
  biology: {
    glycemia: "",
    hba1c: "",
    urea: "",
    creatinine: "",
    cholesterol: "",
    triglycerides: "",
    hdlLdl: "",
    urineChemistry: "",
  },
  hematology: {
    gr: "",
    gb: "",
    hb: "",
    ht: "",
    vgm: "",
    ccmh: "",
    plt: "",
    pn: "",
    lymphocytes: "",
    bem: "",
    vs: "",
  },
  parasitology: { stoolExam: "" },
  radiology: { chestXray: "", others: "" },
  otherExams: { freeText: "" },
});

const createProfilTaGlycemieRow = () => ({
  id:
    typeof globalThis.crypto?.randomUUID === "function"
      ? globalThis.crypto.randomUUID()
      : createId(),
  date: "",
  rightArm: "",
  leftArm: "",
  time: "",
  glycemia: "",
  observation: "",
});

const createEmptyProfilTaGlycemie = (fullName = "") => ({
  fullName,
  rows: [createProfilTaGlycemieRow()],
});

const PROFIL_TEMPLATE_HEADERS = [
  "Date",
  "Avant le petit-déjeuner",
  "Avant le déjeuner",
  "Avant le dîner",
] as const;
const PROFIL_EXPORT_FILENAME = "Profil TA et Glycemie.xlsx";
const PROFIL_EXPORT_SHEET_NAME = "Profil Tensionnel";

type ProfilImportPreviewRow = {
  date: string;
  beforeBreakfast: number | null;
  beforeLunch: number | null;
  beforeDinner: number | null;
};

type ProfilImportIgnoredRow = {
  rowNumber: number;
  reason: string;
  values: Partial<Record<(typeof PROFIL_TEMPLATE_HEADERS)[number], string | null>>;
};

const normalizeTemplateToken = (value: string) =>
  value
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "")
    .trim();

const getCellText = (value: unknown): string | null => {
  if (value === null || value === undefined) return null;

  if (value instanceof Date) {
    return Number.isNaN(value.getTime()) ? null : value.toISOString();
  }

  if (typeof value === "number") {
    return Number.isFinite(value) ? String(value) : null;
  }

  if (typeof value === "string") {
    const trimmed = value.trim();
    return trimmed ? trimmed : null;
  }

  if (typeof value === "boolean") {
    return value ? "true" : "false";
  }

  return null;
};

const parseExcelDate = (value: unknown): string | null => {
  if (value instanceof Date) {
    return toIsoDate(value) || null;
  }

  if (typeof value === "number" && Number.isFinite(value)) {
    const parsed = XLSX.SSF.parse_date_code(value);
    if (!parsed) return null;

    return toIsoDate(new Date(parsed.y, parsed.m - 1, parsed.d)) || null;
  }

  if (typeof value === "string") {
    return toIsoDate(value) || null;
  }

  return null;
};

const parseExcelNumber = (value: unknown): number | null => {
  if (value === null || value === undefined) return null;

  if (typeof value === "number") {
    return Number.isFinite(value) ? value : null;
  }

  if (typeof value === "string") {
    const normalized = value.trim().replace(",", ".");
    if (!normalized) return null;

    const parsed = Number(normalized);
    return Number.isFinite(parsed) ? parsed : null;
  }

  return null;
};

const validateTemplate = (worksheet: XLSX.WorkSheet) => {
  const rows = XLSX.utils.sheet_to_json<(string | number | Date | null)[]>(worksheet, {
    header: 1,
    raw: true,
    defval: null,
  });

  const headerRow = rows.find((row) =>
    row.some((cell) => {
      const cellValue = getCellText(cell);
      return Boolean(cellValue);
    }),
  );

  if (!headerRow) {
    return { valid: false, headerIndexes: null as Record<string, number> | null, rows, headerRow: null };
  }

  const normalizedHeader = headerRow.map((cell) => normalizeTemplateToken(getCellText(cell) || ""));
  const headerIndexes = PROFIL_TEMPLATE_HEADERS.reduce<Record<string, number>>((accumulator, header) => {
    accumulator[header] = normalizedHeader.indexOf(normalizeTemplateToken(header));
    return accumulator;
  }, {});

  return {
    valid: Object.values(headerIndexes).every((index) => index >= 0),
    headerIndexes,
    rows,
    headerRow,
  };
};

const parseWorksheet = (
  worksheet: XLSX.WorkSheet,
  existingRows: WorkerMedicalFileForm["profilTaGlycemie"]["rows"],
) => {
  const validation = validateTemplate(worksheet);

  if (!validation.valid || !validation.headerRow || !validation.headerIndexes) {
    return null;
  }

  const headerRowIndex = validation.rows.indexOf(validation.headerRow);
  const existingSignatures = new Set(
    existingRows.map((row) =>
      [
        row.date.trim(),
        row.rightArm.trim(),
        row.leftArm.trim(),
        row.time.trim(),
      ].join("|"),
    ),
  );
  const importSignatures = new Set<string>();
  const previewRows: ProfilImportPreviewRow[] = [];
  const ignoredRows: ProfilImportIgnoredRow[] = [];

  validation.rows.slice(headerRowIndex + 1).forEach((row, index) => {
    const rowNumber = headerRowIndex + index + 2;
    const values = {
      Date: getCellText(row[validation.headerIndexes.Date]) || null,
      "Avant le petit-déjeuner":
        getCellText(row[validation.headerIndexes["Avant le petit-déjeuner"]]) || null,
      "Avant le déjeuner":
        getCellText(row[validation.headerIndexes["Avant le déjeuner"]]) || null,
      "Avant le dîner":
        getCellText(row[validation.headerIndexes["Avant le dîner"]]) || null,
    };

    if (Object.values(values).every((value) => value === null)) {
      return;
    }

    const parsedRow: ProfilImportPreviewRow = {
      date: parseExcelDate(row[validation.headerIndexes.Date]) || "",
      beforeBreakfast: parseExcelNumber(
        row[validation.headerIndexes["Avant le petit-déjeuner"]],
      ),
      beforeLunch: parseExcelNumber(row[validation.headerIndexes["Avant le déjeuner"]]),
      beforeDinner: parseExcelNumber(row[validation.headerIndexes["Avant le dîner"]]),
    };

    if (!parsedRow.date) {
      ignoredRows.push({
        rowNumber,
        reason: "Date invalide",
        values,
      });
      return;
    }

    const signature = [
      parsedRow.date,
      parsedRow.beforeBreakfast === null ? "" : String(parsedRow.beforeBreakfast),
      parsedRow.beforeLunch === null ? "" : String(parsedRow.beforeLunch),
      parsedRow.beforeDinner === null ? "" : String(parsedRow.beforeDinner),
    ].join("|");

    if (existingSignatures.has(signature) || importSignatures.has(signature)) {
      ignoredRows.push({
        rowNumber,
        reason: "Doublon detecte",
        values,
      });
      return;
    }

    importSignatures.add(signature);
    previewRows.push(parsedRow);
  });

  return {
    previewRows,
    ignoredRows,
  };
};

const downloadTemplate = (
  fullName: string,
  rows: WorkerMedicalFileForm["profilTaGlycemie"]["rows"],
) => {
  const exportRows = rows.filter((row) =>
    [row.date, row.rightArm, row.leftArm, row.time].some(
      (value) => value.trim() !== "",
    ),
  );

  const worksheetRows = [
    [...PROFIL_TEMPLATE_HEADERS],
    ...exportRows.map((row) => [
      row.date || "",
      row.rightArm || "",
      row.leftArm || "",
      row.time || "",
    ]),
  ];

  const worksheet = XLSX.utils.aoa_to_sheet(worksheetRows);
  worksheet["!cols"] = [
    { wch: 14 },
    { wch: 24 },
    { wch: 20 },
    { wch: 18 },
  ];

  const applyCellStyle = (address: string, style: Record<string, unknown>) => {
    if (!worksheet[address]) return;
    worksheet[address].s = style;
  };

  ["A1", "B1", "C1", "D1"].forEach((address) =>
    applyCellStyle(address, {
      font: { bold: true, color: { rgb: "0F172A" } },
      fill: { fgColor: { rgb: "DBEAFE" } },
    }),
  );

  const workbook = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(workbook, worksheet, PROFIL_EXPORT_SHEET_NAME);
  XLSX.writeFile(workbook, PROFIL_EXPORT_FILENAME);
};

const createEmptyWorkStoppageCertificate = (
  doctorFullName?: string,
  workerFullName?: string,
  workerAge?: string,
  position?: string,
) => ({
  doctorFullName: doctorFullName || "",
  workerFullName: workerFullName || "",
  workerAge: workerAge || "",
  position: position || "",
  workStopDuration: "",
  workStopExtensionDuration: "",
  returnToWork: false,
  startDate: "",
  endDate: "",
  issuedAt: new Date().toISOString().slice(0, 10),
  status: "draft" as const,
  includeValidatorSignature: false,
});

const createEmptyMedicalDecision = (doctorName?: string): MedicalDecision => ({
  orientation: {
    specialistAdvice: false,
    specialistAdviceDetails: "",
    treatment: false,
    treatmentDetails: "",
    hospitalization: false,
    hospitalizationDetails: "",
    specialty: "",
  },
  specialistResponse: {
    response: "",
    socialService: "",
    employmentService: "",
  },
  cat: { conduct: "" },
  aptitude: "",
  restrictions: { professionalRestrictions: "" },
  interpretation: { decisionInterpretation: "" },
  recommendations: { doctorRecommendations: "" },
  nextVisit: { nextVisitSchedule: "", nextVisitCustomMonths: "", nextVisitDate: "" },
    validation: {
      validatingDoctor: doctorName || "",
      validationDate: new Date().toISOString().slice(0, 10),
      electronicSignature: "",
      includeValidatorSignature: false,
    },
  });



const calculateNextVisitDate = (baseDate: string, schedule: string, customMonths?: string) => {
  if (!baseDate || !schedule) return "";
  if (schedule === "a_convoquer") return "";

  const date = new Date(`${baseDate}T00:00:00`);
  if (Number.isNaN(date.getTime())) return "";

  if (schedule === "6_mois") {
    date.setMonth(date.getMonth() + 6);
  } else if (schedule === "12_mois") {
    date.setFullYear(date.getFullYear() + 1);
  } else if (schedule === "specific") {
    const months = Number.parseInt(customMonths || "", 10);
    if (!Number.isFinite(months) || months <= 0) return "";
    date.setMonth(date.getMonth() + months);
  } else {
    return "";
  }

  return date.toISOString().slice(0, 10);
};

const createEmptyMedicalOrientationForm = (
  workerRecord: Worker | null,
  doctorName?: string,
): MedicalOrientationFormState => ({
  medical_visit_id: null,
  orientation_number: "",
  orientation_date: new Date().toISOString().slice(0, 10),
  patient_name: workerRecord?.full_name || "",
  age: calculateAgeFromDate(workerRecord?.birth_date),
  doctor_name: doctorName || "",
  orientation_details: "",
  orientationTypes: {
    specialistAdvice: false,
    diagnosticCare: false,
    other: false,
  },
  status: "draft",
  includeValidatorSignature: false,
  orientationTypeOther: "",
  validatorId: null,
  validatorName: "",
  validatorRole: "",
  validatedAt: null,
  validatorSignatureUrl: null,
});

const getOrientationTypesFromCertificate = (
  orientation: OrientationCertificate,
): MedicalOrientationFormState["orientationTypes"] => {
  const source =
    (orientation as OrientationCertificate & {
      orientationTypes?: MedicalOrientationFormState["orientationTypes"];
      orientation_types?: MedicalOrientationFormState["orientationTypes"];
    }).orientationTypes ||
    (orientation as OrientationCertificate & {
      orientation_types?: MedicalOrientationFormState["orientationTypes"];
    }).orientation_types;

  if (source) {
    return {
      specialistAdvice: Boolean(source.specialistAdvice),
      diagnosticCare: Boolean(source.diagnosticCare),
      other: Boolean(source.other),
    };
  }

  return {
    specialistAdvice:
      orientation.orientation_type === "avis_specialise" ||
      orientation.orientation_type === "cardiologie" ||
      orientation.orientation_type === "ophtalmologie",
    diagnosticCare: orientation.orientation_type === "prise_en_charge_diagnostic",
    other: orientation.orientation_type === "autre",
  };
};

const formatOrientationTypesLabel = (orientation: OrientationCertificate) => {
  const orientationTypes = getOrientationTypesFromCertificate(orientation);
  const labels: string[] = [];

  if (orientationTypes.specialistAdvice) labels.push("Avis Spécialisé");
  if (orientationTypes.diagnosticCare) labels.push("Pris en charge diagnostic");
  if (orientationTypes.other) labels.push("Autres");

  const otherText =
    (orientation as OrientationCertificate & { orientationTypeOther?: string }).orientationTypeOther ||
    orientation.orientation_type_other ||
    "";

  if (!labels.length) {
    return otherText ? `Autres — ${otherText}` : "Aucun type renseigné";
  }

  return `${labels.join(" • ")}${orientationTypes.other && otherText ? ` — ${otherText}` : ""}`;
};

const normalizeOrientationCertificateForUi = (
  orientation: OrientationCertificate,
): OrientationCertificate => ({
  ...orientation,
  orientationTypes: getOrientationTypesFromCertificate(orientation),
  orientationTypeOther:
    (orientation as OrientationCertificate & { orientationTypeOther?: string }).orientationTypeOther ||
    orientation.orientation_type_other ||
    "",
  patient_name:
    orientation.patient_name ||
    (orientation as OrientationCertificate & { patientName?: string }).patientName ||
    orientation.worker_name ||
    null,
  orientation_type: formatOrientationTypesLabel(orientation),
  orientation_type_other: null,
});


type AptitudeNormalizeContext = {
  workerRecord: Worker | null;
  campaignId: number;
  medicalVisitId: number;
  doctorName?: string;
  currentCampaign?: Campaign | null;
  medicalVisit?: MedicalVisit | null;
  form?: WorkerMedicalFileForm;
};

const normalizeAptitudeCertificate = (
  source: AptitudeCertificate | null | undefined,
  context: AptitudeNormalizeContext,
): MedicalAptitudeFormState => {
  const today = new Date().toISOString().slice(0, 10);
  const sourceRecord = source ?? null;
  const sourceAny = (sourceRecord || {}) as Record<string, unknown>;
  const workerRecord = context.workerRecord;
  const normalizeText = (value: unknown) => (typeof value === "string" ? value.trim() : "");
  const sourceString = (...values: unknown[]) => values.map(normalizeText).find((value) => value) || "";
  const validatedByUserIdRaw = sourceAny.validatedByUserId ?? sourceAny.validated_by_user_id ?? null;
  const validatedByUserId =
    typeof validatedByUserIdRaw === "number"
      ? validatedByUserIdRaw
      : typeof validatedByUserIdRaw === "string" && validatedByUserIdRaw.trim()
        ? Number(validatedByUserIdRaw)
        : null;
  const validatedAt = sourceString(sourceAny.validatedAt, sourceAny.validated_at) || null;
  const normalizedStatus = normalizeText(sourceAny.status).toLowerCase();
  const status =
    normalizedStatus === "validated" ||
    normalizedStatus === "confirmed" ||
    normalizedStatus === "valide" ||
    normalizedStatus === "validé" ||
    Boolean(validatedAt) ||
    Boolean(validatedByUserId)
      ? "confirmed"
      : "draft";
  const includeValidatorSignature =
    Boolean(
      sourceRecord?.includeValidatorSignature ??
        sourceAny.include_validator_signature ??
        sourceAny.includeDoctorSignature ??
        sourceAny.include_doctor_signature ??
        sourceAny.includeWorkspaceSignature ??
        sourceAny.include_workspace_signature ??
        false,
    );
  const validatedDoctorNameFromSource = sourceString(
    sourceAny.validatorName,
    sourceAny.validator_name,
    sourceAny.validatedDoctorName,
    sourceAny.validated_doctor_name,
    sourceAny.validatedDoctor,
    sourceAny.validated_doctor,
  );
  const validatedDoctorName =
    status === "confirmed"
      ? validatedDoctorNameFromSource
      : sourceString(validatedDoctorNameFromSource, context.doctorName);
  const validatorRole = sourceString(
    sourceAny.validatorRole,
    sourceAny.validator_role,
    sourceAny.validatedByRole,
    sourceAny.validated_by_role,
  );
  const validatorSignatureUrl =
    sourceString(
      sourceAny.validatorSignatureUrl,
      sourceAny.validator_signature_url,
      sourceAny.validatedDoctorSignatureUrl,
      sourceAny.validated_doctor_signature_url,
      sourceAny.signatureUrl,
      sourceAny.signature_url,
      (sourceAny.validator as Record<string, unknown> | undefined)?.signatureUrl,
      (sourceAny.validator as Record<string, unknown> | undefined)?.signature_url,
      (sourceAny.validator as Record<string, unknown> | undefined)?.signature_path,
    ) || null;

  return {
    aptitudeId: sourceRecord?.id ?? 0,
    campaignId: context.campaignId,
    medicalVisitId: sourceRecord?.medicalVisitId ?? sourceRecord?.medical_visit_id ?? context.medicalVisitId,
    workerId: workerRecord?.id ?? 0,
    certificateNumber: sourceString(
      sourceRecord?.certificateNumber,
      sourceRecord?.certificate_number,
    ),
    firstName: sourceString(sourceRecord?.firstName, workerRecord?.first_name),
    lastName: sourceString(sourceRecord?.lastName, workerRecord?.last_name),
    companyName: sourceString(
      sourceRecord?.companyName,
      sourceAny.CompanyName,
      (context.currentCampaign as Record<string, unknown> | null)?.company_name,
      (context.currentCampaign as Record<string, unknown> | null)?.companyName,
    ),
    jobTitle: sourceString(sourceRecord?.jobTitle, workerRecord?.position),
    birthDate: sourceString(sourceRecord?.birthDate, workerRecord?.birth_date),
    birthPlace: sourceString(sourceRecord?.birthPlace, workerRecord?.birth_wilaya),
    bloodGroup: sourceString(
      sourceRecord?.bloodGroup,
      sourceAny.Groupage,
      sourceAny.Rhesus,
      workerRecord?.medical_file_data &&
        typeof workerRecord.medical_file_data === "object" &&
        "bloodGroup" in workerRecord.medical_file_data
        ? (workerRecord.medical_file_data as Record<string, unknown>).bloodGroup
        : "",
    ),
    aptitude: sourceString(
      context.form?.medicalDecision?.aptitude,
      sourceRecord?.aptitude,
    ),
    aptitudeInterpretation: sourceString(
      context.form?.medicalDecision?.interpretation?.decisionInterpretation,
      sourceAny.aptitudeInterpretation,
      sourceAny.DoctorInterpritation,
      sourceAny.doctorInterpretation,
      sourceAny.aptitude_interpretation,
    ),
    doctorRecommendations: sourceString(
      sourceAny.doctorRecommendations,
      sourceAny.doctor_recommendations,
      context.form?.medicalDecision?.recommendations?.doctorRecommendations,
    ),
    visitDate:
      sourceString(
        sourceAny.visitDate,
        sourceAny.DateDeVisite,
        context.medicalVisit?.visit_date,
        context.form?.internalVisitDate,
      ) || today,
    validatedDoctorName,
    validatedByUserId,
    validatorRole,
    validatorSignatureUrl,
    issueDate: sourceString(sourceAny.issueDate, sourceAny.issue_date) || today,
    validatedAt,
    includeValidatorSignature,
    status,
  };
};

const createEmptyMedicalAptitudeFormState = (
  aptitude: AptitudeCertificate | null,
  workerRecord: Worker | null,
  campaignId: number,
  medicalVisitId: number,
  doctorName?: string,
  currentCampaign?: Campaign | null,
  medicalVisit?: MedicalVisit | null,
  form?: WorkerMedicalFileForm,
): MedicalAptitudeFormState =>
  normalizeAptitudeCertificate(aptitude, {
    workerRecord,
    campaignId,
    medicalVisitId,
    doctorName,
    currentCampaign,
    medicalVisit,
    form,
  });

const MEDICAL_FILE_STORAGE_PREFIX = "medical-folder.worker-medical-file.";

const buildWorkerMedicalFileRoute = (campaignId: string | number, workerId: string | number) =>
  `/app/workspace/${campaignId}/workers/${workerId}/medical-file`;

const buildWorkerMedicalVisitRoute = (
  campaignId: string | number,
  workerId: string | number,
  visitId: string | number,
) => `/app/workspace/${campaignId}/workers/${workerId}/medical-visits/${visitId}`;

const collectUniqueSuggestions = (values: Array<string | null | undefined>) =>
  Array.from(
    new Set(
      values
        .map((value) => value?.trim())
        .filter((value): value is string => Boolean(value)),
    ),
  );

const getStoredMedicalFileDrafts = () => {
  if (typeof window === "undefined") return [];

  const drafts: Array<WorkerMedicalFileForm & { mission?: string }> = [];

  for (let index = 0; index < window.localStorage.length; index += 1) {
    const key = window.localStorage.key(index);
    if (!key?.startsWith(MEDICAL_FILE_STORAGE_PREFIX)) continue;

    const rawValue = window.localStorage.getItem(key);
    if (!rawValue) continue;

    try {
      drafts.push(JSON.parse(rawValue) as WorkerMedicalFileForm & { mission?: string });
    } catch {
      // Ignore malformed local drafts.
    }
  }

  return drafts;
};

const mergeMedicalFileForm = (
  defaultForm: WorkerMedicalFileForm,
  parsed?:
    | (Partial<WorkerMedicalFileForm> & {
        mission?: string;
        validation?: Partial<WorkerMedicalFileForm["medicalDecision"]["validation"]>;
        dynamicMedicalTests?: Record<string, DynamicMedicalTestValue>;
        workerSnapshot?: Record<string, unknown>;
        visitData?: Record<string, unknown>;
      })
    | null,
): WorkerMedicalFileForm => ({
  ...defaultForm,
  ...(parsed || {}),
  clinicalExam: {
    ...defaultForm.clinicalExam,
    ...parsed?.clinicalExam,
    ophthalmology: {
      ...defaultForm.clinicalExam.ophthalmology,
      ...parsed?.clinicalExam?.ophthalmology,
    },
    ent: {
      ...defaultForm.clinicalExam.ent,
      ...parsed?.clinicalExam?.ent,
    },
    stomatology: {
      ...defaultForm.clinicalExam.stomatology,
      ...parsed?.clinicalExam?.stomatology,
    },
    cardiovascular: {
      ...defaultForm.clinicalExam.cardiovascular,
      ...parsed?.clinicalExam?.cardiovascular,
    },
    respiratory: {
      ...defaultForm.clinicalExam.respiratory,
      ...parsed?.clinicalExam?.respiratory,
    },
    digestive: {
      ...defaultForm.clinicalExam.digestive,
      ...parsed?.clinicalExam?.digestive,
    },
    urogenital: {
      ...defaultForm.clinicalExam.urogenital,
      ...parsed?.clinicalExam?.urogenital,
    },
    endocrine: {
      ...defaultForm.clinicalExam.endocrine,
      ...parsed?.clinicalExam?.endocrine,
    },
    hematology: {
      ...defaultForm.clinicalExam.hematology,
      ...parsed?.clinicalExam?.hematology,
    },
    neuroPsychiatric: {
      ...defaultForm.clinicalExam.neuroPsychiatric,
      ...parsed?.clinicalExam?.neuroPsychiatric,
    },
    osteoArticular: {
      ...defaultForm.clinicalExam.osteoArticular,
      ...parsed?.clinicalExam?.osteoArticular,
    },
    dermatology: {
      ...defaultForm.clinicalExam.dermatology,
      ...parsed?.clinicalExam?.dermatology,
    },
    doctorGeneralObservations: {
      ...defaultForm.clinicalExam.doctorGeneralObservations,
      ...parsed?.clinicalExam?.doctorGeneralObservations,
    },
  },
  complementaryExams: {
    ...defaultForm.complementaryExams,
    ...parsed?.complementaryExams,
    cardiology: {
      ...defaultForm.complementaryExams.cardiology,
      ...parsed?.complementaryExams?.cardiology,
    },
    audiology: {
      ...defaultForm.complementaryExams.audiology,
      ...parsed?.complementaryExams?.audiology,
    },
    respiratory: {
      ...defaultForm.complementaryExams.respiratory,
      ...parsed?.complementaryExams?.respiratory,
    },
    biology: {
      ...defaultForm.complementaryExams.biology,
      ...parsed?.complementaryExams?.biology,
    },
    hematology: {
      ...defaultForm.complementaryExams.hematology,
      ...parsed?.complementaryExams?.hematology,
    },
    parasitology: {
      ...defaultForm.complementaryExams.parasitology,
      ...parsed?.complementaryExams?.parasitology,
    },
    radiology: {
      ...defaultForm.complementaryExams.radiology,
      ...parsed?.complementaryExams?.radiology,
    },
    otherExams: {
      ...defaultForm.complementaryExams.otherExams,
      ...parsed?.complementaryExams?.otherExams,
    },
  },
  profilTaGlycemie: {
    ...defaultForm.profilTaGlycemie,
    ...((parsed?.profilTaGlycemie as WorkerMedicalFileForm["profilTaGlycemie"] | undefined) || {}),
    rows:
      (parsed?.profilTaGlycemie as WorkerMedicalFileForm["profilTaGlycemie"] | undefined)?.rows?.length
        ? (parsed?.profilTaGlycemie as WorkerMedicalFileForm["profilTaGlycemie"]).rows
        : defaultForm.profilTaGlycemie.rows,
  },
  medicalDecision: {
    ...defaultForm.medicalDecision,
    ...parsed?.medicalDecision,
    orientation: {
      ...defaultForm.medicalDecision.orientation,
      ...parsed?.medicalDecision?.orientation,
    },
   

    specialistResponse: {
      ...defaultForm.medicalDecision.specialistResponse,
      ...parsed?.medicalDecision?.specialistResponse,
    },
    cat: {
      ...defaultForm.medicalDecision.cat,
      ...parsed?.medicalDecision?.cat,
    },
    restrictions: {
      ...defaultForm.medicalDecision.restrictions,
      ...parsed?.medicalDecision?.restrictions,
    },
    recommendations: {
      ...defaultForm.medicalDecision.recommendations,
      ...parsed?.medicalDecision?.recommendations,
    },
    nextVisit: {
      ...defaultForm.medicalDecision.nextVisit,
      ...parsed?.medicalDecision?.nextVisit,
    },
    validation: {
      ...defaultForm.medicalDecision.validation,
      ...(parsed?.medicalDecision?.validation || parsed?.validation),
      validatingDoctor:
        parsed?.medicalDecision?.validation?.validatingDoctor ||
        parsed?.validation?.validatingDoctor ||
        defaultForm.medicalDecision.validation.validatingDoctor,
      validationDate:
        parsed?.medicalDecision?.validation?.validationDate ||
        parsed?.validation?.validationDate ||
        defaultForm.medicalDecision.validation.validationDate,
    },
  },
  auditTrail: parsed?.auditTrail ?? defaultForm.auditTrail,
  workStoppageCertificate:
    parsed?.workStoppageCertificate === null
      ? null
      : {
          ...(defaultForm.workStoppageCertificate || createEmptyWorkStoppageCertificate()),
          ...((parsed?.workStoppageCertificate as WorkerMedicalFileForm["workStoppageCertificate"]) || {}),
          doctorFullName:
            (parsed?.workStoppageCertificate as Record<string, unknown> | undefined)?.doctorFullName as string ||
            (parsed?.workStoppageCertificate as Record<string, unknown> | undefined)?.doctorName as string ||
            (defaultForm.workStoppageCertificate?.doctorFullName || ""),
          workStopDuration:
            (parsed?.workStoppageCertificate as Record<string, unknown> | undefined)?.workStopDuration as string ||
            (parsed?.workStoppageCertificate as Record<string, unknown> | undefined)?.days as string ||
            (defaultForm.workStoppageCertificate?.workStopDuration || ""),
        },
  direction: parsed?.direction ?? parsed?.mission ?? defaultForm.direction,
  ...normalizeInternalVisitType({
    internalVisitHire: Boolean(parsed?.internalVisitHire),
    internalVisitPeriodic: Boolean(parsed?.internalVisitPeriodic),
  }),
});

const parseMedicalVisitFormData = (
  raw: unknown,
): WorkerMedicalVisitFormData | Record<string, unknown> | null => {
  if (!raw) return null;
  if (typeof raw === "string") {
    try {
      const parsed = JSON.parse(raw);
      return parsed && typeof parsed === "object"
        ? (parsed as WorkerMedicalVisitFormData | Record<string, unknown>)
        : null;
    } catch {
      return null;
    }
  }
  return typeof raw === "object" ? (raw as WorkerMedicalVisitFormData | Record<string, unknown>) : null;
};

const normalizeMedicalVisitFormData = (
  raw: unknown,
): Record<string, unknown> => {
  const parsed = parseMedicalVisitFormData(raw);
  const container = (parsed || {}) as Record<string, unknown>;
  const data =
    container.visitData && typeof container.visitData === "object"
      ? (container.visitData as Record<string, unknown>)
      : container;

  const orientationCertificates = Array.isArray(data.orientationCertificates)
    ? data.orientationCertificates.filter((item): item is Record<string, unknown> => Boolean(item && typeof item === "object"))
    : data.orientationCertificate && typeof data.orientationCertificate === "object"
      ? [data.orientationCertificate as Record<string, unknown>]
      : [];
  const ordonnances = Array.isArray(data.ordonnances)
    ? data.ordonnances.filter((item): item is Record<string, unknown> => Boolean(item && typeof item === "object"))
    : data.ordonnance && typeof data.ordonnance === "object"
      ? [data.ordonnance as Record<string, unknown>]
      : [];
  const profilTaGlycemie =
    data.profilTaGlycemie && typeof data.profilTaGlycemie === "object"
      ? (data.profilTaGlycemie as Record<string, unknown>)
      : {};
  const workStoppageCertificate =
    data.workStoppageCertificate && typeof data.workStoppageCertificate === "object"
      ? (data.workStoppageCertificate as Record<string, unknown>)
      : null;

  return {
    internalVisit: data.internalVisit && typeof data.internalVisit === "object" ? data.internalVisit : {},
    clinicalExam: data.clinicalExam && typeof data.clinicalExam === "object" ? data.clinicalExam : {},
    complementaryExams:
      data.complementaryExams && typeof data.complementaryExams === "object" ? data.complementaryExams : {},
    medicalDecision: data.medicalDecision && typeof data.medicalDecision === "object" ? data.medicalDecision : {},
    dynamicMedicalTests:
      data.dynamicMedicalTests && typeof data.dynamicMedicalTests === "object" ? data.dynamicMedicalTests : {},
    profilTaGlycemie: {
      fullName: typeof profilTaGlycemie.fullName === "string" ? profilTaGlycemie.fullName : "",
      rows:
        Array.isArray(profilTaGlycemie.rows) && profilTaGlycemie.rows.length > 0
          ? profilTaGlycemie.rows
              .filter((item): item is Record<string, unknown> => Boolean(item && typeof item === "object"))
              .map((row) => ({
                id: typeof row.id === "string" && row.id.trim() ? row.id : createId(),
                date: typeof row.date === "string" ? row.date : "",
                rightArm: typeof row.rightArm === "string" ? row.rightArm : "",
                leftArm: typeof row.leftArm === "string" ? row.leftArm : "",
                time: typeof row.time === "string" ? row.time : "",
                glycemia: typeof row.glycemia === "string" ? row.glycemia : "",
                observation: typeof row.observation === "string" ? row.observation : "",
              }))
          : [
              {
                id: createId(),
                date: "",
                rightArm: "",
                leftArm: "",
                time: "",
                glycemia: "",
                observation: "",
              },
            ],
    },
    aptitudeCertificate:
      data.aptitudeCertificate && typeof data.aptitudeCertificate === "object" ? data.aptitudeCertificate : {},
    orientationCertificates,
    workStoppageCertificate: workStoppageCertificate
      ? {
          doctorFullName:
            typeof workStoppageCertificate.doctorFullName === "string"
              ? workStoppageCertificate.doctorFullName
              : typeof workStoppageCertificate.doctorName === "string"
                ? workStoppageCertificate.doctorName
                : "",
          workerFullName: typeof workStoppageCertificate.workerFullName === "string" ? workStoppageCertificate.workerFullName : "",
          workerAge: typeof workStoppageCertificate.workerAge === "string" ? workStoppageCertificate.workerAge : "",
          position: typeof workStoppageCertificate.position === "string" ? workStoppageCertificate.position : "",
          workStopDuration:
            typeof workStoppageCertificate.workStopDuration === "string"
              ? workStoppageCertificate.workStopDuration
              : typeof workStoppageCertificate.days === "string"
                ? workStoppageCertificate.days
                : "",
          workStopExtensionDuration:
            typeof workStoppageCertificate.workStopExtensionDuration === "string"
              ? workStoppageCertificate.workStopExtensionDuration
              : "",
          returnToWork: Boolean(workStoppageCertificate.returnToWork),
          startDate: typeof workStoppageCertificate.startDate === "string" ? workStoppageCertificate.startDate : "",
          endDate: typeof workStoppageCertificate.endDate === "string" ? workStoppageCertificate.endDate : "",
          issuedAt: typeof workStoppageCertificate.issuedAt === "string" ? workStoppageCertificate.issuedAt : "",
          status: workStoppageCertificate.status === "validated" ? "validated" : "draft",
          includeValidatorSignature: Boolean(workStoppageCertificate.includeValidatorSignature),
        }
      : null,
    ordonnances,
    validation: data.validation && typeof data.validation === "object" ? data.validation : {},
    auditTrail: Array.isArray(data.auditTrail)
      ? data.auditTrail
      : Array.isArray(container.auditTrail)
        ? container.auditTrail
        : [],
  };
};

const hydrateFormFromMedicalVisit = (
  defaultForm: WorkerMedicalFileForm,
  rawFormData: unknown,
): WorkerMedicalFileForm => {
  const parsedFormData = parseMedicalVisitFormData(rawFormData);
  const source = (parsedFormData || {}) as Record<string, unknown>;
  const normalizedVisitData = normalizeMedicalVisitFormData(parsedFormData);
  const workerSnapshot =
    source.workerSnapshot && typeof source.workerSnapshot === "object"
      ? (source.workerSnapshot as Record<string, unknown>)
      : {};
  const internalVisit =
    normalizedVisitData.internalVisit && typeof normalizedVisitData.internalVisit === "object"
      ? (normalizedVisitData.internalVisit as Record<string, unknown>)
      : {};

  const hydratedForm = mergeMedicalFileForm(defaultForm, {
    ...source,
    medicalFileNumber:
      (source.medicalFileNumber as string | undefined) ||
      (workerSnapshot.medicalFileNumber as string | undefined) ||
      defaultForm.medicalFileNumber,
    employeeCode:
      (source.employeeCode as string | undefined) ||
      (workerSnapshot.employeeCode as string | undefined) ||
      defaultForm.employeeCode,
    nationalId:
      (source.nationalId as string | undefined) ||
      (workerSnapshot.nationalId as string | undefined) ||
      defaultForm.nationalId,
    firstName:
      (source.firstName as string | undefined) ||
      (workerSnapshot.firstName as string | undefined) ||
      defaultForm.firstName,
    lastName:
      (source.lastName as string | undefined) ||
      (workerSnapshot.lastName as string | undefined) ||
      defaultForm.lastName,
    sex:
      (source.sex as string | undefined) ||
      (workerSnapshot.sex as string | undefined) ||
      defaultForm.sex,
    dateOfBirth:
      (source.dateOfBirth as string | undefined) ||
      (workerSnapshot.dateOfBirth as string | undefined) ||
      defaultForm.dateOfBirth,
    birthPlace:
      (source.birthPlace as string | undefined) ||
      (workerSnapshot.birthPlace as string | undefined) ||
      defaultForm.birthPlace,
    phone:
      (source.phone as string | undefined) ||
      (workerSnapshot.phone as string | undefined) ||
      defaultForm.phone,
    companyName:
      (source.companyName as string | undefined) ||
      (workerSnapshot.companyName as string | undefined) ||
      defaultForm.companyName,
    siteName:
      (source.siteName as string | undefined) ||
      (workerSnapshot.siteName as string | undefined) ||
      defaultForm.siteName,
    position:
      (source.position as string | undefined) ||
      (workerSnapshot.position as string | undefined) ||
      defaultForm.position,
    department:
      (source.department as string | undefined) ||
      (workerSnapshot.department as string | undefined) ||
      defaultForm.department,
    professionalHistory:
      (source.professionalHistory as WorkerMedicalFileForm["professionalHistory"] | undefined) ||
      (workerSnapshot.professionalHistory as WorkerMedicalFileForm["professionalHistory"] | undefined) ||
      defaultForm.professionalHistory,
    vaccinations:
      (source.vaccinations as WorkerMedicalFileForm["vaccinations"] | undefined) ||
      (workerSnapshot.vaccinations as WorkerMedicalFileForm["vaccinations"] | undefined) ||
      defaultForm.vaccinations,
    workAccidents:
      (source.workAccidents as WorkerMedicalFileForm["workAccidents"] | undefined) ||
      (workerSnapshot.workAccidents as WorkerMedicalFileForm["workAccidents"] | undefined) ||
      defaultForm.workAccidents,
    occupationalDiseases:
      (source.occupationalDiseases as WorkerMedicalFileForm["occupationalDiseases"] | undefined) ||
      (workerSnapshot.occupationalDiseases as WorkerMedicalFileForm["occupationalDiseases"] | undefined) ||
      defaultForm.occupationalDiseases,
    spontaneousConsultations:
      (source.spontaneousConsultations as WorkerMedicalFileForm["spontaneousConsultations"] | undefined) ||
      (workerSnapshot.spontaneousConsultations as WorkerMedicalFileForm["spontaneousConsultations"] | undefined) ||
      defaultForm.spontaneousConsultations,
    internalVisitHire:
      (source.internalVisitHire as boolean | undefined) ?? Boolean(internalVisit.hire),
    internalVisitPeriodic:
      (source.internalVisitPeriodic as boolean | undefined) ?? Boolean(internalVisit.periodic),
    internalVisitDate:
      (source.internalVisitDate as string | undefined) ||
      (internalVisit.date as string | undefined) ||
      defaultForm.internalVisitDate,
    internalVisitDoctor:
      (source.internalVisitDoctor as string | undefined) ||
      (internalVisit.doctor as string | undefined) ||
      defaultForm.internalVisitDoctor,
    internalVisitWeightKg:
      (source.internalVisitWeightKg as string | undefined) ||
      (internalVisit.weightKg as string | undefined) ||
      defaultForm.internalVisitWeightKg,
    internalVisitHeightCm:
      (source.internalVisitHeightCm as string | undefined) ||
      (internalVisit.heightCm as string | undefined) ||
      defaultForm.internalVisitHeightCm,
    internalVisitTa:
      (source.internalVisitTa as string | undefined) ||
      (internalVisit.ta as string | undefined) ||
      defaultForm.internalVisitTa,
    internalVisitFc:
      (source.internalVisitFc as string | undefined) ||
      (internalVisit.fc as string | undefined) ||
      defaultForm.internalVisitFc,
    internalVisitDistanceOdSc:
      (source.internalVisitDistanceOdSc as string | undefined) ||
      (internalVisit.distanceOdSc as string | undefined) ||
      defaultForm.internalVisitDistanceOdSc,
    internalVisitDistanceOdAc:
      (source.internalVisitDistanceOdAc as string | undefined) ||
      (internalVisit.distanceOdAc as string | undefined) ||
      defaultForm.internalVisitDistanceOdAc,
    internalVisitDistanceOgSc:
      (source.internalVisitDistanceOgSc as string | undefined) ||
      (internalVisit.distanceOgSc as string | undefined) ||
      defaultForm.internalVisitDistanceOgSc,
    internalVisitDistanceOgAc:
      (source.internalVisitDistanceOgAc as string | undefined) ||
      (internalVisit.distanceOgAc as string | undefined) ||
      defaultForm.internalVisitDistanceOgAc,
    internalVisitDistanceOdg:
      (source.internalVisitDistanceOdg as string | undefined) ||
      (internalVisit.distanceOdg as string | undefined) ||
      defaultForm.internalVisitDistanceOdg,
    clinicalExam:
      (normalizedVisitData.clinicalExam as WorkerMedicalFileForm["clinicalExam"] | undefined) ||
      (source.clinicalExam as WorkerMedicalFileForm["clinicalExam"] | undefined) ||
      defaultForm.clinicalExam,
    complementaryExams:
      (normalizedVisitData.complementaryExams as WorkerMedicalFileForm["complementaryExams"] | undefined) ||
      (source.complementaryExams as WorkerMedicalFileForm["complementaryExams"] | undefined) ||
      defaultForm.complementaryExams,
    profilTaGlycemie:
      (normalizedVisitData.profilTaGlycemie as WorkerMedicalFileForm["profilTaGlycemie"] | undefined) ||
      defaultForm.profilTaGlycemie,
    medicalDecision: {
      ...defaultForm.medicalDecision,
      ...((normalizedVisitData.medicalDecision as WorkerMedicalFileForm["medicalDecision"] | undefined) ||
        (source.medicalDecision as WorkerMedicalFileForm["medicalDecision"] | undefined) ||
        {}),
      validation: {
        ...defaultForm.medicalDecision.validation,
        ...((normalizedVisitData.validation as WorkerMedicalFileForm["medicalDecision"]["validation"] | undefined) ||
          {}),
        ...(((normalizedVisitData.medicalDecision as Record<string, unknown> | undefined)?.validation as
          | WorkerMedicalFileForm["medicalDecision"]["validation"]
          | undefined) || {}),
      },
    },
    auditTrail:
      (normalizedVisitData.auditTrail as WorkerMedicalFileForm["auditTrail"] | undefined) || defaultForm.auditTrail,
    workStoppageCertificate:
      normalizedVisitData.workStoppageCertificate === null
        ? null
        : ((normalizedVisitData.workStoppageCertificate as WorkerMedicalFileForm["workStoppageCertificate"] | undefined) ||
          defaultForm.workStoppageCertificate),
    dynamicMedicalTests:
      (normalizedVisitData.dynamicMedicalTests as Record<string, DynamicMedicalTestValue> | undefined) ||
      (source.dynamicMedicalTests as Record<string, DynamicMedicalTestValue> | undefined) ||
      {},
  });


  return hydratedForm;
};

const hydrateFolderAndVisitForm = (
  baseForm: WorkerMedicalFileForm,
  workerMedicalFileData: unknown,
  visitFormData: unknown,
): WorkerMedicalFileForm => {
  const folderData = mergeMedicalFileForm(baseForm, (workerMedicalFileData as Partial<WorkerMedicalFileForm> | null) ?? null);
  const hydratedForm = hydrateFormFromMedicalVisit(folderData, visitFormData);
  return hydratedForm;
};


{/*const lastWorkerId = await workersApi.getLastId();  await workersApi.getLastId(); */}

          

const createEmptyForm = (
  worker?: Worker | null,
  companyName?: string,
  siteName?: string,
  campaignId?: string,
  doctorName?: string,
  nextWorkerId?: number | null
): WorkerMedicalFileForm => {
  const workerFullName = formatWorkerFullName(worker?.first_name, worker?.last_name);

  return ({
 medicalFileNumber: worker
  ? `MF-${worker.id}`
  : `MF-${nextWorkerId ?? ""}`,
  employeeCode: worker?.employee_code || "",
  nationalId: worker?.national_id || "",
  lastName: worker?.last_name || "",
  firstName: worker?.first_name || "",
  etat_actual: worker?.etat_actual || "present",
  sex: worker?.gender || "",
  dateOfBirth: worker?.birth_date?.slice(0, 10) || "",
  birthPlace: worker?.birth_wilaya || "",
  familySituation: "",
  phone: "",
  originAddress: "",
  professionalAddress: "",
  direction: "",
  position: worker?.position || "",
  department: "",
  service: "",
  workshop: "",
  schoolEducation: "",
  professionalTraining: "",
  professionalQualification: "",
  nationalServiceStatus: "",
  nationalServiceNotes: "",
  chronicDiseaseNotes: "",
  bloodGroup: "",
  congenitalDiseases: "",
  generalDiseases: "",
  surgicalInterventions: "",
  accidents: "",
  intoxications: "",
  tobacco: "",
  chewingTobacco: "",
  alcoholism: "",
  otherIntoxications: "",
  familyHistoryFather: "",
  familyHistoryMother: "",
  familyHistorySisters: "",
  familyHistoryBrothers: "",
  familyHistorySpouse: "",
  familyHistoryChildrenBoys: "",
  familyHistoryChildrenGirls: "",
  professionalDiseaseNotes: "",
  companyName: companyName || "",
  siteName: siteName || "",
  professionalHistory: [createProfessionalHistoryRow()],
  vaccinations: [createVaccinationRow()],
  workAccidents: [createWorkAccidentRow()],
  occupationalDiseases: [createOccupationalDiseaseRow()],
  spontaneousConsultations: [createConsultationRow()],
  internalVisitHire: false,
  internalVisitPeriodic: false,
  internalVisitDate: "",
  internalVisitDoctor: doctorName || "",
  internalVisitWeightKg: "",
  internalVisitHeightCm: "",
  internalVisitTa: "",
  internalVisitFc: "",
  internalVisitDistanceOdSc: "",
  internalVisitDistanceOdAc: "",
  internalVisitDistanceOgSc: "",
  internalVisitDistanceOgAc: "",
  internalVisitDistanceOdg: "",
  clinicalExam: createEmptyClinicalExam(),
  complementaryExams: createEmptyComplementaryExams(),
  profilTaGlycemie: createEmptyProfilTaGlycemie(workerFullName),
  medicalDecision: createEmptyMedicalDecision(doctorName),
  workStoppageCertificate: null,
  confirmationStatus: "draft",
  confirmationDoctor: "",
  confirmationDate: "",
  confirmationSignature: "",
  isLocked: false,
  auditTrail: [],
});
};

const isTruthyText = (value: string) => Boolean(value.trim());

type CampaignMedicalTestDescriptor = {
  key: string;
  label: string;
  sectionId: "internalVisit" | "clinicalExam" | "complementaryExams";
  match: (assignment: CampaignTestAssignment) => boolean;
  isComplete: (form: WorkerMedicalFileForm) => boolean;
};

type CampaignMedicalSectionId = CampaignMedicalTestDescriptor["sectionId"];

type PersistedCampaignTest = {
  campaign_test_id: number;
  test_id: number;
  name: string;
  description: string | null;
  type: string | null;
  required: boolean;
};

type DynamicMedicalTestFieldType =
  | "text"
  | "number"
  | "textarea"
  | "checkbox"
  | "select"
  | "date"
  | "radio";

type DynamicMedicalTestOption = {
  label: string;
  value: string;
};

type DynamicMedicalTestField = {
  type: DynamicMedicalTestFieldType | string;
  name: string;
  label: string;
  placeholder?: string;
  required?: boolean;
  disabled?: boolean;
  rows?: number;
  options?: DynamicMedicalTestOption[];
  colSpan?: number;
  wrapperClassName?: string;
  labelClassName?: string;
  inputClassName?: string;
};

type DynamicMedicalTestLayout = {
  columns?: number;
  gap?: number;
};

type DynamicMedicalTestConfig = {
  layout?: DynamicMedicalTestLayout;
  fields?: DynamicMedicalTestField[];
};

type DynamicMedicalTestValue = {
  testId: number;
  testName: string;
  values: Record<string, unknown>;
};

type DocumentCollectionType = "visite" | "aptitude" | "orientation" | "ordonnance";

interface WorkerDocumentItem {
  id: number;
  date?: string;
  title?: string;
  doctor?: string;
  status?: string;
  pdfAvailable?: boolean;
}

type WorkerMedicalFileDataWithDynamicTests = Partial<WorkerMedicalFileForm> & {
  dynamicMedicalTests?: Record<string, DynamicMedicalTestValue> | null;
};

type WorkerMedicalVisitFormData = Record<string, unknown> & {
  internalVisit: Record<string, unknown>;
  clinicalExam: ClinicalExam;
  complementaryExams: ComplementaryExams;
  medicalDecision: MedicalDecision;
  dynamicMedicalTests: Record<string, DynamicMedicalTestValue>;
  profilTaGlycemie: WorkerMedicalFileForm["profilTaGlycemie"];
  aptitudeCertificate: Record<string, unknown>;
  orientationCertificates: Record<string, unknown>[];
  workStoppageCertificate: WorkerMedicalFileForm["workStoppageCertificate"];
  ordonnances: Record<string, unknown>[];
  validation: WorkerMedicalFileForm["medicalDecision"]["validation"];
  auditTrail: WorkerMedicalFileForm["auditTrail"];
};

const normalizeMedicalTestToken = (value?: string | null) =>
  (value || "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, " ")
    .trim();

const hasAnyValue = (...values: string[]) => values.some((value) => isTruthyText(value));

const matchesCampaignTest = (
  assignment: CampaignTestAssignment,
  nameToken: string,
  sectionTokens: string[] = [],
) => {
  const normalizedName = normalizeMedicalTestToken(assignment.test?.name);
  const normalizedSection = normalizeMedicalTestToken(
    assignment.test?.section || assignment.test?.category,
  );

  if (normalizedName !== nameToken) {
    return false;
  }

  if (!sectionTokens.length) {
    return true;
  }

  return sectionTokens.some((token) => normalizedSection.includes(token));
};

const sanitizeDynamicColumns = (value?: number) => {
  if (!value || !Number.isFinite(value)) return 2;
  return Math.max(1, Math.min(4, Math.trunc(value)));
};

const sanitizeDynamicGap = (value?: number) => {
  if (!value || !Number.isFinite(value)) return 4;
  return Math.max(1, Math.min(8, Math.trunc(value)));
};

const normalizeDynamicMedicalTestConfig = (value: unknown): DynamicMedicalTestConfig | null => {
  if (!value || typeof value !== "object") return null;

  const source = value as Partial<DynamicMedicalTestConfig> & {
    layout?: Partial<DynamicMedicalTestLayout>;
    fields?: unknown[];
  };
  const fields = Array.isArray(source.fields)
    ? source.fields
        .filter((field): field is DynamicMedicalTestField => Boolean(field && typeof field === "object"))
        .map((field) => ({
          ...field,
          name: String(field.name || "").trim(),
          label: String(field.label || "").trim(),
          type: String(field.type || "").trim(),
          rows: typeof field.rows === "number" ? field.rows : undefined,
          colSpan: typeof field.colSpan === "number" ? field.colSpan : undefined,
          options: Array.isArray(field.options)
            ? field.options
                .filter((option): option is DynamicMedicalTestOption => Boolean(option && typeof option === "object"))
                .map((option) => ({
                  label: String(option.label || "").trim(),
                  value: String(option.value || "").trim(),
                }))
            : undefined,
        }))
        .filter((field) => field.name.length > 0 && field.label.length > 0 && field.type.length > 0)
    : [];

  return {
    layout: {
      columns: sanitizeDynamicColumns(source.layout?.columns),
      gap: sanitizeDynamicGap(source.layout?.gap),
    },
    fields,
  };
};

const parseDynamicMedicalTestConfig = (description: unknown): DynamicMedicalTestConfig | null => {
  

  if (typeof description !== "string") {
    return null;
  }

  const trimmed = description.trim();
  if (!trimmed) {
    return null;
  }

  const looksLikeJson = trimmed.startsWith("{") || trimmed.startsWith("[");
  if (!looksLikeJson) {
    return null;
  }

  try {
    const config = normalizeDynamicMedicalTestConfig(JSON.parse(trimmed));
    
    return config;
  } catch {
    return null;
  }
};

const getDynamicMedicalTestSectionId = (assignment: CampaignTestAssignment): CampaignMedicalSectionId => {
  const normalizedSection = normalizeMedicalTestToken(assignment.test?.section || assignment.test?.category);

  if (normalizedSection.includes("fiche interne de visite medicale")) return "internalVisit";
  if (normalizedSection.includes("examen clinique")) return "clinicalExam";
  if (normalizedSection.includes("examens complementaires")) return "complementaryExams";
  return "complementaryExams";
};

const getDynamicMedicalTestName = (assignment: CampaignTestAssignment) =>
  assignment.name?.trim() || assignment.test?.name?.trim() || "Examen médical";

const getDynamicMedicalTestConfigSource = (assignment: CampaignTestAssignment) =>
  assignment.description ?? assignment.test?.description ?? null;

const isLikelyJsonDescription = (description: unknown) =>
  typeof description === "string" && /^[\s]*[{[]/.test(description);

const normalizeDynamicMedicalTestsMap = (
  value: unknown,
): Record<string, DynamicMedicalTestValue> => {
  if (Array.isArray(value)) {
    return value.reduce<Record<string, DynamicMedicalTestValue>>((acc, item) => {
      if (!item || typeof item !== "object") return acc;
      const candidate = item as {
        testId?: unknown;
        testName?: unknown;
        values?: unknown;
      };
      const testId = Number(candidate.testId);
      if (!Number.isFinite(testId)) return acc;
      acc[String(testId)] = {
        testId,
        testName: String(candidate.testName || "").trim(),
        values:
          candidate.values && typeof candidate.values === "object" && !Array.isArray(candidate.values)
            ? (candidate.values as Record<string, unknown>)
            : {},
      };
      return acc;
    }, {});
  }

  if (!value || typeof value !== "object") return {};

  const source = value as Record<string, unknown>;
  return Object.entries(source).reduce<Record<string, DynamicMedicalTestValue>>((acc, [key, item]) => {
    if (!item || typeof item !== "object") return acc;

    const candidate = item as {
      testId?: unknown;
      testName?: unknown;
      values?: unknown;
    };
    const testId = Number(candidate.testId ?? key);
    if (!Number.isFinite(testId)) return acc;

    const values =
      candidate.values && typeof candidate.values === "object" && !Array.isArray(candidate.values)
        ? (candidate.values as Record<string, unknown>)
        : {};

    acc[String(testId)] = {
      testId,
      testName: String(candidate.testName || "").trim(),
      values,
    };
    return acc;
  }, {});
};

const restoreDynamicMedicalTests = (
  source: Record<string, unknown> | undefined | null,
): Record<string, DynamicMedicalTestValue> => {
  const dynamicMedicalTests = source?.dynamicMedicalTests;

  if (dynamicMedicalTests && typeof dynamicMedicalTests === "object") {
    const restored = normalizeDynamicMedicalTestsMap(dynamicMedicalTests);
    
    return restored;
  }

  
  return {};
};

const initializeDynamicMedicalTests = (
  source: unknown,
  campaignTests: CampaignTestAssignment[],
): Record<string, DynamicMedicalTestValue> => {
  const saved = normalizeDynamicMedicalTestsMap(source);
  const next: Record<string, DynamicMedicalTestValue> = {};

  campaignTests
    .filter((assignment) => !campaignMedicalTestDescriptors.some((descriptor) => descriptor.match(assignment)))
    .forEach((assignment) => {
      const testId = assignment.test_id;
      const testKey = String(testId);
      const testName = getDynamicMedicalTestName(assignment);
      const config = parseDynamicMedicalTestConfig(getDynamicMedicalTestConfigSource(assignment));
      const savedEntry = saved[testKey];
      const values: Record<string, unknown> = { ...(savedEntry?.values || {}) };

      config?.fields?.forEach((field) => {
        if (!(field.name in values)) {
          values[field.name] =
            field.type === "checkbox"
              ? false
              : field.type === "radio" || field.type === "select"
                ? field.options?.[0]?.value || ""
                : "";
        }
      });

      next[testKey] = {
        testId,
        testName: savedEntry?.testName || testName,
        values,
      };
    });

  return next;
};

const campaignMedicalTestDescriptors: CampaignMedicalTestDescriptor[] = [
  {
    key: "acuite-visuelle",
    label: "Acuité visuelle",
    sectionId: "internalVisit",
    match: (assignment) => matchesCampaignTest(assignment, "acuite visuelle"),
    isComplete: (form) =>
      hasAnyValue(
        form.internalVisitDistanceOdSc,
        form.internalVisitDistanceOdAc,
        form.internalVisitDistanceOgSc,
        form.internalVisitDistanceOgAc,
      ),
  },
  {
    key: "acuite-visuelle-binoculaire",
    label: "Acuité visuelle Binoculaire",
    sectionId: "internalVisit",
    match: (assignment) => matchesCampaignTest(assignment, "acuite visuelle binoculaire"),
    isComplete: (form) => hasAnyValue(form.internalVisitDistanceOdg),
  },
  {
    key: "ophtalmologie",
    label: "Ophtalmologie",
    sectionId: "clinicalExam",
    match: (assignment) => matchesCampaignTest(assignment, "ophtalmologie"),
    isComplete: (form) =>
      hasAnyValue(form.clinicalExam.ophthalmology?.observations),
  },
  {
    key: "orl",
    label: "ORL",
    sectionId: "clinicalExam",
    match: (assignment) => matchesCampaignTest(assignment, "orl"),
    isComplete: (form) =>
      hasAnyValue(
        form.clinicalExam.ent?.nose,
        form.clinicalExam.ent?.ears,
        form.clinicalExam.ent?.throat,
      ),
  },
  {
    key: "stomatologie",
    label: "Stomatologie",
    sectionId: "clinicalExam",
    match: (assignment) => matchesCampaignTest(assignment, "stomatologie"),
    isComplete: (form) =>
      hasAnyValue(
        form.clinicalExam.stomatology?.teeth,
        form.clinicalExam.stomatology?.others,
      ),
  },
  {
    key: "cardio-vasculaire",
    label: "Cardio Vasculaire",
    sectionId: "clinicalExam",
    match: (assignment) =>
      matchesCampaignTest(assignment, "cardio vasculaire") ||
      matchesCampaignTest(assignment, "cardio-vasculaire"),
    isComplete: (form) =>
      hasAnyValue(
        form.clinicalExam.cardiovascular?.bloodPressure,
        form.clinicalExam.cardiovascular?.dyspnea,
      ),
  },
  {
    key: "digestif",
    label: "Digestif",
    sectionId: "clinicalExam",
    match: (assignment) => matchesCampaignTest(assignment, "digestif"),
    isComplete: (form) =>
      hasAnyValue(
        form.clinicalExam.digestive.ulcer,
        form.clinicalExam.digestive.colopathy,
        form.clinicalExam.digestive.hemorrhoids,
        form.clinicalExam.digestive.others,
      ),
  },
  {
    key: "uro-genital",
    label: "Uro-génital",
    sectionId: "clinicalExam",
    match: (assignment) => matchesCampaignTest(assignment, "uro genital"),
    isComplete: (form) =>
      hasAnyValue(
        form.clinicalExam.urogenital.dysuria,
        form.clinicalExam.urogenital.impotence,
        form.clinicalExam.urogenital.others,
      ),
  },
  {
    key: "endocrinien",
    label: "Endocrinien",
    sectionId: "clinicalExam",
    match: (assignment) => matchesCampaignTest(assignment, "endocrinien"),
    isComplete: (form) =>
      hasAnyValue(
        form.clinicalExam.endocrine.diabetes,
        form.clinicalExam.endocrine.thyroid,
        form.clinicalExam.endocrine.others,
      ),
  },
  {
    key: "hematologie",
    label: "Hematologie",
    sectionId: "clinicalExam",
    match: (assignment) => matchesCampaignTest(assignment, "hematologie"),
    isComplete: (form) =>
      hasAnyValue(
        form.clinicalExam.hematology.hemostasis,
        form.clinicalExam.hematology.adenopathy,
        form.clinicalExam.hematology.others,
      ),
  },
  {
    key: "neuro-psychiatrie",
    label: "Neuro-Psychiatrie",
    sectionId: "clinicalExam",
    match: (assignment) => matchesCampaignTest(assignment, "neuro psychiatrie"),
    isComplete: (form) =>
      hasAnyValue(
        form.clinicalExam.neuroPsychiatric.headachesVertigo,
        form.clinicalExam.neuroPsychiatric.neurologicalSigns,
        form.clinicalExam.neuroPsychiatric.personalityDisorders,
        form.clinicalExam.neuroPsychiatric.others,
      ),
  },
  {
    key: "osteo-articulaire",
    label: "Osteo-Articulaire",
    sectionId: "clinicalExam",
    match: (assignment) => matchesCampaignTest(assignment, "osteo articulaire"),
    isComplete: (form) =>
      hasAnyValue(form.clinicalExam.osteoArticular.polyarthralgia),
  },
  {
    key: "dermatologie",
    label: "Dermatologie",
    sectionId: "clinicalExam",
    match: (assignment) => matchesCampaignTest(assignment, "dermatologie"),
    isComplete: (form) =>
      hasAnyValue(
        form.clinicalExam.dermatology.lesions,
        form.clinicalExam.dermatology.skinAllergies,
        form.clinicalExam.dermatology.urticaria,
      ),
  },
  {
    key: "ecg",
    label: "ECG",
    sectionId: "complementaryExams",
    match: (assignment) => matchesCampaignTest(assignment, "ecg"),
    isComplete: (form) => hasAnyValue(form.complementaryExams.cardiology.ecg),
  },
  {
    key: "audiogramme",
    label: "Audiogramme",
    sectionId: "complementaryExams",
    match: (assignment) => matchesCampaignTest(assignment, "audiogramme"),
    isComplete: (form) => hasAnyValue(form.complementaryExams.audiology.audiogram),
  },
  {
    key: "efr",
    label: "EFR",
    sectionId: "complementaryExams",
    match: (assignment) => matchesCampaignTest(assignment, "efr"),
    isComplete: (form) => hasAnyValue(form.complementaryExams.respiratory.efr),
  },
  {
    key: "biologie",
    label: "Biologie",
    sectionId: "complementaryExams",
    match: (assignment) => matchesCampaignTest(assignment, "biologie"),
    isComplete: (form) =>
      hasAnyValue(
        form.complementaryExams.biology.glycemia,
        form.complementaryExams.biology.hba1c,
        form.complementaryExams.biology.urea,
        form.complementaryExams.biology.creatinine,
        form.complementaryExams.biology.cholesterol,
        form.complementaryExams.biology.triglycerides,
        form.complementaryExams.biology.hdlLdl,
        form.complementaryExams.biology.urineChemistry,
      ),
  },
  {
    key: "nfs-hematologie",
    label: "NFS / Hematologie",
    sectionId: "complementaryExams",
    match: (assignment) =>
      matchesCampaignTest(assignment, "nfs hematologie") ||
      matchesCampaignTest(assignment, "nfs") ||
      matchesCampaignTest(assignment, "hematologie"),
    isComplete: (form) =>
      hasAnyValue(
        form.complementaryExams.hematology.gr,
        form.complementaryExams.hematology.gb,
        form.complementaryExams.hematology.hb,
        form.complementaryExams.hematology.ht,
        form.complementaryExams.hematology.vgm,
        form.complementaryExams.hematology.ccmh,
        form.complementaryExams.hematology.plt,
        form.complementaryExams.hematology.pn,
        form.complementaryExams.hematology.lymphocytes,
        form.complementaryExams.hematology.bem,
        form.complementaryExams.hematology.vs,
      ),
  },
  {
    key: "parasitologie-des-selles",
    label: "Parasitologie des selles",
    sectionId: "complementaryExams",
    match: (assignment) => matchesCampaignTest(assignment, "parasitologie des selles"),
    isComplete: (form) => hasAnyValue(form.complementaryExams.parasitology.stoolExam),
  },
  {
    key: "autres-examens",
    label: "Autres Examens",
    sectionId: "complementaryExams",
    match: (assignment) => matchesCampaignTest(assignment, "autres examens"),
    isComplete: (form) => hasAnyValue(form.complementaryExams.otherExams.freeText),
  },
];

const MedicalSectionCard = ({
  icon: Icon,
  title,
  description,
  children,
}: {
  icon: LucideIcon;
  title: string;
  description: string;
  children: ReactNode;
}) => (
  <Card className="rounded-3xl border-slate-200/90 p-6">
    <div className="mb-6 flex items-start gap-4">
      <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-cyan-50 text-cyan-700">
        <Icon className="h-5 w-5" />
      </div>
      <div>
        <h2 className="text-xl font-black text-slate-950">{title}</h2>
        <p className="mt-1 text-sm text-slate-500">{description}</p>
      </div>
    </div>
    {children}
  </Card>
);

const MedicalSubsection = ({
  title,
  description,
  children,
  isCollapsible = false,
}: {
  title: ReactNode;
  description?: string;
  children: ReactNode;
  isCollapsible?: boolean;
}) => {
  const [isOpen, setIsOpen] = useState(isCollapsible ? false : true);

  return (
    <Card className="rounded-3xl border-slate-200/90 p-5">
      <div
        className="mb-4 cursor-pointer flex items-center justify-between"
        onClick={() => setIsOpen(!isOpen)}
      >
        <div>
          <h3 className="text-base font-black text-slate-950">
            {title}
          </h3>
          {description && (
            <p className="mt-1 text-sm text-slate-500">
              {description}
            </p>
          )}
        </div>

        <span className="text-xl">
          {isOpen ? "−" : "+"}
        </span>
      </div>

      {isOpen && children}
    </Card>
  );
};

export const WorkerMedicalFilePage = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const { campaignId, workerId, visitId } = useParams();
  const { currentCampaign, currentWorkspace } = useCampaignWorkspace();
  const { user, loading: authLoading, isAuthenticated } = useAuth();
  const doctorName = [user?.first_name, user?.last_name].filter(Boolean).join(" ").trim();
  const currentUserSignatureUrl =
    user?.signatureUrl ??
    user?.signature_url ??
    user?.signatureImageUrl ??
    user?.signaturePngUrl ??
    user?.signature_png_url ??
    null;
  const currentUserHasSignature = Boolean(
    currentUserSignatureUrl || user?.hasSignature || user?.signature_png,
  );
  const normalizedRole = user?.role?.toLowerCase();
  const canSignMedicalDocuments =
    normalizedRole === "doctor" ||
    normalizedRole === "admin" ||
    normalizedRole === "super admin" ||
    normalizedRole === "super_admin";
  const canSignPrescription = canSignMedicalDocuments;
  const signatureAuthorizationMessage = "Only authorized validators can sign medical documents.";
  
  
  const isCreateMode = !workerId || workerId === "create";
  const normalizedVisitId = visitId ? Number(visitId) : null;
  const hasSelectedVisit = normalizedVisitId !== null && Number.isFinite(normalizedVisitId);
  const isWorkerCreatePage = isCreateMode;
  const isMedicalVisitPage = hasSelectedVisit;
  const visitWorkflowSectionIds = new Set<TabId>([
    "internalVisit",
    "clinicalExam",
    "complementaryExams",
    "medicalDecision",
    "medicalOrientation",
    "medicalAptitude",
    "pdfViewer",
    "ordonnance",
  ]);
  const [activeTab, setActiveTab] = useState<TabId>("personal");
  const [activeSectionGroup, setActiveSectionGroup] = useState<"medicalFolder" | "visitsMedical">(
    "medicalFolder",
  );
  const [worker, setWorker] = useState<Worker | null>(null);
  const [form, setForm] = useState<WorkerMedicalFileForm>(() =>
    createEmptyForm(
      null,
      currentCampaign?.company_name,
      currentCampaign?.site_name,
      campaignId,
      doctorName,
    ),
  );
  const [loading, setLoading] = useState(true);
  const [notice, setNotice] = useState<{
    type: "success" | "error";
    message: string;
  } | null>(null);
  const profilExcelInputRef = useRef<HTMLInputElement | null>(null);
  const [profilImportPreviewOpen, setProfilImportPreviewOpen] = useState(false);
  const [profilImportRows, setProfilImportRows] = useState<ProfilImportPreviewRow[]>([]);
  const [profilIgnoredRows, setProfilIgnoredRows] = useState<ProfilImportIgnoredRow[]>([]);
  const [profilImportedFileName, setProfilImportedFileName] = useState("");
  const [errors, setErrors] = useState<Partial<Record<keyof WorkerMedicalFileForm, string>>>(
    {},
  );
  const [pdfDownloading, setPdfDownloading] = useState(false);
  const [pdfPreviewUrl, setPdfPreviewUrl] = useState<string | null>(null);
  const [pdfPreviewLoading, setPdfPreviewLoading] = useState(false);
  const [dossierPdfDownloading, setDossierPdfDownloading] = useState(false);
  const [dossierPdfPreviewUrl, setDossierPdfPreviewUrl] = useState<string | null>(null);
  const [dossierPdfPreviewLoading, setDossierPdfPreviewLoading] = useState(false);
  const [prescriptions, setPrescriptions] = useState<Prescription[]>([]);
  const [prescriptionForm, setPrescriptionForm] = useState<PrescriptionFormState>(() =>
    createEmptyPrescriptionForm(null, doctorName),
  );

  const [prescriptionLoading, setPrescriptionLoading] = useState(false);
  const [prescriptionSaving, setPrescriptionSaving] = useState(false);
  const [prescriptionPrinting, setPrescriptionPrinting] = useState(false);
  const [prescriptionDownloading, setPrescriptionDownloading] = useState(false);
  const [prescriptionPreviewUrl, setPrescriptionPreviewUrl] = useState<string | null>(null);
  const [prescriptionPreviewLoading, setPrescriptionPreviewLoading] = useState(false);
  const [manualPrescriptionEntryState, setManualPrescriptionEntryState] = useState<Record<string, boolean>>({});
  
  // State
  const [orientations, setOrientations] = useState<OrientationCertificate[]>([]);
  const [orientationForm, setOrientationForm] = useState<MedicalOrientationFormState>(
    createEmptyMedicalOrientationForm(null , doctorName)
  );
  const [orientationLoading, setOrientationLoading] = useState(false);
  const [orientationSaving, setOrientationSaving] = useState(false);
  const [orientationPdfPreviewLoading, setOrientationPdfPreviewLoading] = useState(false);
  const [orientationPdfPreviewUrl, setOrientationPdfPreviewUrl] = useState<string | null>(null);
  const [orientationPdfDownloading, setOrientationPdfDownloading] = useState(false);
  const [orientationPrinting, setOrientationPrinting] = useState(false);
  const [aptitudePdfPreviewLoading, setAptitudePdfPreviewLoading] = useState(false);
  const [aptitudePdfPreviewUrl, setAptitudePdfPreviewUrl] = useState<string | null>(null);
  const [campaignTests, setCampaignTests] = useState<CampaignTestAssignment[]>([]);
  const [campaignTestsLoading, setCampaignTestsLoading] = useState(false);
  const [campaignTestsError, setCampaignTestsError] = useState<string | null>(null);
  const [dynamicMedicalTestValues, setDynamicMedicalTestValues] = useState<
    Record<string, DynamicMedicalTestValue>
  >({});
  const [, setDynamicMedicalTestErrors] = useState<Record<number, string>>({});
  const [medicalFileDataSource, setMedicalFileDataSource] = useState<unknown>(null);
  const [medicalVisit, setMedicalVisit] = useState<MedicalVisit | null>(null);
  const [workerVisits, setWorkerVisits] = useState<MedicalVisit[]>([]);
  const [aptitudeCertificate, setAptitudeCertificate] = useState<AptitudeCertificate | null>(null);
  const [aptitudeForm, setAptitudeForm] = useState<MedicalAptitudeFormState>(() =>
    createEmptyMedicalAptitudeFormState(null, null, Number(campaignId), normalizedVisitId ?? 0, doctorName),
  );
  const [isEditingAptitudeCertificate, setIsEditingAptitudeCertificate] = useState(false);
  const [aptitudeLoading, setAptitudeLoading] = useState(false);
  const [aptitudeSaving, setAptitudeSaving] = useState(false);
  const [visitCampaignTestsByCampaignId, setVisitCampaignTestsByCampaignId] = useState<
    Record<number, string[]>
  >({});
  const [visitLoading, setVisitLoading] = useState(false);
  const [visitSaving, setVisitSaving] = useState(false);
  const [visitValidating, setVisitValidating] = useState(false);
  const [visitSectionSaving, setVisitSectionSaving] = useState(false);
  const [, setActiveVisitId] = useState<number | null>(normalizedVisitId);
  const [duplicateCheckLoading, setDuplicateCheckLoading] = useState(false);
  const [duplicateWorker, setDuplicateWorker] = useState<Worker | null>(null);
  const [duplicateCheckError, setDuplicateCheckError] = useState<string | null>(null);
  const [duplicateHistory, setDuplicateHistory] = useState<WorkerLookupHistory | null>(null);
  const [duplicateModalOpen, setDuplicateModalOpen] = useState(false);
  const [selectedQuickVisitId, setSelectedQuickVisitId] = useState<number | null>(
    normalizedVisitId,
  );
  const [selectedOrientationCertificateId, setSelectedOrientationCertificateId] = useState<number | null>(null);
  const [selectedPrescriptionId, setSelectedPrescriptionId] = useState<number | null>(null);
  const [isQuickActionsCollapsed, setIsQuickActionsCollapsed] = useState(false);

  const activeAptitudeCertificateId = aptitudeCertificate?.id ?? null;
  const aptitudeCertificates = aptitudeCertificate ? [aptitudeCertificate] : [];
  const selectedAptitudeCertificateId = activeAptitudeCertificateId;
  const selectedWorkerMedicalVisits = useMemo(() => {
    const selectedWorkerId = Number(workerId || worker?.id);
    if (!Number.isFinite(selectedWorkerId)) return [];

    return workerVisits.filter((visit) => {
      const visitWorkerId = Number(
        visit.worker_id ??
          (visit as MedicalVisit & { workerId?: number; worker?: { id?: number } | null }).workerId ??
          (visit as MedicalVisit & { worker?: { id?: number } | null }).worker?.id,
      );

      return visitWorkerId === selectedWorkerId;
    });
  }, [workerVisits, workerId, worker?.id]);

  const resolvedActiveVisitId = useMemo(() => {
    const candidates = [
      normalizedVisitId,
      selectedQuickVisitId,
      medicalVisit?.id ?? null,
      selectedWorkerMedicalVisits[0]?.id ?? null,
    ];
    for (const candidate of candidates) {
      if (!candidate || Number.isNaN(candidate)) {
        continue;
      }
      const matchingVisit = selectedWorkerMedicalVisits.find((visit) => visit.id === candidate);
      if (matchingVisit) {
        return matchingVisit.id;
      }
    }
    return null;
  }, [medicalVisit?.id, normalizedVisitId, selectedQuickVisitId, selectedWorkerMedicalVisits]);

  const activeVisitRecord = useMemo(
    () => selectedWorkerMedicalVisits.find((visit) => visit.id === resolvedActiveVisitId) ?? null,
    [resolvedActiveVisitId, selectedWorkerMedicalVisits],
  );

  const refreshWorkerVisits = async () => {
    if (!workerId || workerId === "create") return;
    const visits = await medicalVisitsApi.listByWorker(workerId);
    setWorkerVisits(Array.isArray(visits) ? visits : []);
    setSelectedQuickVisitId((current) => current ?? visits[0]?.id ?? null);
  };

  const refreshAptitudeCertificate = async (explicitVisitId?: number) => {
    const targetVisitId = explicitVisitId || medicalVisit?.id || normalizedVisitId || 0;
    if (isCreateMode || !workerId || !targetVisitId) {
      setAptitudeCertificate(null);
      setAptitudeForm(createEmptyMedicalAptitudeFormState(null, worker, Number(campaignId), targetVisitId, doctorName));
      return;
    }

    setAptitudeLoading(true);
    try {
      const record = await aptitudeCertificatesApi.getByVisit(targetVisitId);
      if (import.meta.env.DEV) {
        
      }
      const rawValidatorSignatureUrl =
        record.validatorSignatureUrl ||
        record.validator_signature_url ||
        record.validatedDoctorSignatureUrl ||
        record.validated_doctor_signature_url ||
        record.signatureUrl ||
        record.signature_url ||
        record.validator?.signatureUrl ||
        record.validator?.signature_url ||
        record.validator?.signature_path ||
        null;
      let validatorSignatureUrl = rawValidatorSignatureUrl;
      if (record.id && rawValidatorSignatureUrl) {
        try {
          const signatureBlob = await aptitudeCertificatesApi.downloadValidatorSignature(record.id);
          validatorSignatureUrl = window.URL.createObjectURL(signatureBlob);
        } catch {
          validatorSignatureUrl = rawValidatorSignatureUrl;
        }
      }
      const normalizedRecord = { ...record, validatorSignatureUrl };
      const normalizedAptitude = createEmptyMedicalAptitudeFormState(
        normalizedRecord,
        worker,
        Number(campaignId),
        targetVisitId,
        doctorName,
        currentCampaign,
        medicalVisit,
        form,
      );
      if (import.meta.env.DEV) {
        
      }
      setAptitudeCertificate(normalizedRecord);
      setAptitudeForm(normalizedAptitude);
    } catch {
      setAptitudeCertificate(null);
      setAptitudeForm(
        createEmptyMedicalAptitudeFormState(
          null,
          worker,
          Number(campaignId),
          targetVisitId,
          doctorName,
          currentCampaign,
          medicalVisit,
          form,
        ),
      );
    } finally {
      setAptitudeLoading(false);
    }
  };

  const updateAptitudeField = <K extends keyof MedicalAptitudeFormState>(
    key: K,
    value: MedicalAptitudeFormState[K],
  ) => {
    setAptitudeForm((current) => ({ ...current, [key]: value }));
    if (key === "aptitude") {
      updateMedicalDecision("aptitude", value as MedicalDecision["aptitude"]);
    }
  };

  const normalizedAptitudeStatus = String(aptitudeForm.status || "draft")
    .trim()
    .toLowerCase();
  const isAptitudeValidated = ["confirmed", "validated", "valide", "validé"].includes(
    normalizedAptitudeStatus,
  );
  const isAptitudeSaving = aptitudeSaving;
  const normalizedUserRoleForAptitude = (user?.role || "").trim().toLowerCase();
  const canEditConfirmedAptitude =
    isEditingAptitudeCertificate &&
    ["super_admin", "super admin", "admin", "doctor"].includes(normalizedUserRoleForAptitude);
  const isAptitudeReadOnly = isAptitudeValidated && !canEditConfirmedAptitude;
  const canEditAptitude = !isAptitudeReadOnly && aptitudeSaving !== true;
  const canValidateAptitude =
    !isAptitudeValidated &&
    aptitudeSaving !== true &&
    ["super_admin", "super admin", "admin", "doctor"].includes(normalizedUserRoleForAptitude);
  const shouldShowValidatorSignature =
    aptitudeForm.status === "confirmed" &&
    (aptitudeForm.includeValidatorSignature === true ||
      Boolean(aptitudeForm.validatorSignatureUrl && (aptitudeForm.validatedAt || aptitudeForm.validatedByUserId)));
  const validatorSignatureMissing =
    aptitudeForm.status === "confirmed" &&
    (aptitudeForm.includeValidatorSignature === true ||
      Boolean(aptitudeForm.validatedAt || aptitudeForm.validatedByUserId)) &&
    !aptitudeForm.validatorSignatureUrl;

  useEffect(() => {
    if (!import.meta.env.DEV || !activeAptitudeCertificateId) return;
    
    
    if (shouldShowValidatorSignature && !aptitudeForm.validatorSignatureUrl) {
      console.warn(
        "[AptitudeCertificate][Display warning] Signature du médecin validateur indisponible pour ce certificat.",
      );
    }
  }, [
    activeAptitudeCertificateId,
    aptitudeForm.includeValidatorSignature,
    aptitudeForm.status,
    aptitudeForm.validatedAt,
    aptitudeForm.validatedDoctorName,
    aptitudeForm.validatorSignatureUrl,
    shouldShowValidatorSignature,
  ]);

  useEffect(() => {
    
  }, [aptitudeForm.status, canEditAptitude, canValidateAptitude, form.isLocked, isAptitudeSaving, user?.role]);

  useEffect(() => {
    
  }, [
    aptitudeForm.status,
    aptitudeSaving,
    isAptitudeValidated,
    isAptitudeSaving,
    user?.role,
    normalizedUserRoleForAptitude,
    isEditingAptitudeCertificate,
    canEditConfirmedAptitude,
    isAptitudeReadOnly,
    canEditAptitude,
    canValidateAptitude,
  ]);

  const buildCurrentAptitudeValidator = () => ({
    validatedDoctorId: user?.id ?? null,
    validatedDoctorName:
      user?.full_name || `${user?.first_name || ""} ${user?.last_name || ""}`.trim() || null,
    validatedDoctorRole: user?.role ?? null,
    validatedAt: new Date().toISOString(),
    validatorSignatureUrl: currentUserSignatureUrl || null,
  });

  const buildAptitudePayload = (mode: "draft" | "validate" = "draft") => ({
    aptitude: form.medicalDecision.aptitude || aptitudeForm.aptitude || undefined,
    aptitude_interpretation: aptitudeForm.aptitudeInterpretation.trim() || null,
    doctor_recommendations: aptitudeForm.doctorRecommendations.trim() || null,
    visit_date: aptitudeForm.visitDate || null,
    issue_date: aptitudeForm.issueDate || null,
    includeValidatorSignature: mode === "validate" ? true : aptitudeForm.includeValidatorSignature,
    status: mode === "validate" ? ("confirmed" as const) : aptitudeForm.status,
    ...(mode === "validate" ? buildCurrentAptitudeValidator() : {}),
  });

  const [activeQuickActionTab, setActiveQuickActionTab] =
    useState<"dossier" | "visite" | "aptitude" | "orientation" | "ordonnance">(
      "dossier",
    );

  const quickActionTabs = [
    { id: "dossier", label: "Documents médicaux" },
    { id: "visite", label: "Visite médicale" },
    { id: "aptitude", label: "Certificat d'aptitude" },
    { id: "orientation", label: "Orientation médicale" },
    { id: "ordonnance", label: "Ordonnance" },
  ] as const;
  const shouldLoadWorkerVisits =
    activeSectionGroup === "visitsMedical" || activeQuickActionTab === "visite";
  const shouldLoadAptitudeCertificate =
    activeQuickActionTab === "aptitude" || activeTab === "medicalAptitude";
  const shouldLoadOrientations =
    activeQuickActionTab === "orientation" || activeTab === "medicalOrientation";
  const shouldLoadPrescriptions =
    activeQuickActionTab === "ordonnance" || activeTab === "ordonnance";

  useEffect(() => {
    const nextTab = (location.state as { tab?: TabId } | null)?.tab;
    if (nextTab === "internalVisit") {
      setActiveTab("internalVisit");
    }
  }, [location.state]);

  useEffect(() => {
    updateMedicalDecision("recommendations", {
      doctorRecommendations: `La prochaine visite médicale périodique est prévue le : ${form.medicalDecision.nextVisit.nextVisitDate || ""}`,
    });
  }, [form.medicalDecision.nextVisit.nextVisitDate]);



  const storageKey = useMemo(
    () =>
      `medical-folder.worker-medical-file.${campaignId}.${workerId || "create"}.${visitId || "draft"}`,
    [campaignId, workerId, visitId],
  );

  useEffect(() => {
    if (!campaignId) return;
    if (hasSelectedVisit && worker?.id === Number(workerId)) {
      return;
    }
    let cancelled = false;

    const load = async () => {
      setLoading(true);
      try {
        const draft = window.localStorage.getItem(storageKey);
        if (isCreateMode) {
          

          if (cancelled) {
            
            return;
          }

          setWorker(null);
          window.localStorage.removeItem(storageKey);

          

          const nextWorkerId = await workersApi.getLastId();

          
          

          const emptyForm = createEmptyForm(
            null,
            currentCampaign?.company_name,
            currentCampaign?.site_name || currentCampaign?.branch_name,
            campaignId,
            doctorName,
            nextWorkerId
          );

          
        
          setForm({
            ...emptyForm,
            employeeCode: String(nextWorkerId), // or workerId depending on your form field
          });

          return;
        
        } else {
          const workerResponse = await workersApi.get(Number(workerId));

          if (cancelled) return;

          setWorker(workerResponse);
          
          setPrescriptionForm(createEmptyPrescriptionForm(workerResponse, doctorName));

          if (draft) {
            const parsed = JSON.parse(draft) as WorkerMedicalFileForm & { mission?: string };
            const defaultForm = createEmptyForm(
              workerResponse,
              currentCampaign?.company_name,
              currentCampaign?.site_name || currentCampaign?.branch_name,
              campaignId,
              doctorName,
            );
            if (!hasSelectedVisit) {
              const mergedFolderDraft = {
                ...((workerResponse.medical_file_data as Partial<WorkerMedicalFileForm> | null) ?? {}),
                ...parsed,
                companyName: currentCampaign?.company_name || parsed.companyName,
                siteName: currentCampaign?.site_name || parsed.siteName,
              };
              setForm(mergeMedicalFileForm(defaultForm, mergedFolderDraft));
              setMedicalFileDataSource(parsed);
              setDynamicMedicalTestValues(
                restoreDynamicMedicalTests(parsed as unknown as Record<string, unknown>),
              );
            }
          } else {
            const defaultForm = createEmptyForm(
              workerResponse,
              currentCampaign?.company_name,
              currentCampaign?.site_name || currentCampaign?.branch_name,
              campaignId,
              doctorName,
            );
            if (!hasSelectedVisit) {
              setForm(
                mergeMedicalFileForm(
                  defaultForm,
                  (workerResponse.medical_file_data as Partial<WorkerMedicalFileForm> | null) ?? null,
                ),
              );
              setMedicalFileDataSource(workerResponse.medical_file_data);
              setDynamicMedicalTestValues(
                restoreDynamicMedicalTests(
                  (workerResponse.medical_file_data as Record<string, unknown> | null) ?? null,
                ),
              );
            }
          }
        }
      } catch {
        if (cancelled) return;
        setWorker(null);
      } finally {
        if (!cancelled) setLoading(false);
      }
    };

    void load();

    return () => {
      cancelled = true;
    };
  }, [
    campaignId,
    currentCampaign?.branch_name,
    currentCampaign?.company_name,
    currentCampaign?.site_name,
    doctorName,
    hasSelectedVisit,
    isCreateMode,
    storageKey,
    worker?.id,
    workerId,
  ]);

  useEffect(() => {
    setDynamicMedicalTestValues((current) => {
      const initialized = initializeDynamicMedicalTests(medicalFileDataSource, campaignTests);
      const merged = { ...initialized };

      Object.entries(current).forEach(([key, entry]) => {
        merged[key] = {
          testId: entry.testId,
          testName: entry.testName || merged[key]?.testName || "",
          values: {
            ...(merged[key]?.values || {}),
            ...(entry.values || {}),
          },
        };
      });

      
      return merged;
    });
  }, [campaignTests, medicalFileDataSource]);

  useEffect(() => {
    if (!campaignId) {
      setCampaignTests([]);
      setCampaignTestsError(null);
      return;
    }

    let cancelled = false;

    const loadCampaignTests = async () => {
      setCampaignTestsLoading(true);
      setCampaignTestsError(null);
      try {
        const records = await campaignsApi.tests(Number(campaignId));
        if (!cancelled) {
          setCampaignTests(records);
        }
      } catch {
        if (!cancelled) {
          setCampaignTests([]);
          setCampaignTestsError("Impossible de charger les examens medicaux de cette campagne.");
        }
      } finally {
        if (!cancelled) {
          setCampaignTestsLoading(false);
        }
      }
    };

    void loadCampaignTests();

    return () => {
      cancelled = true;
    };
  }, [campaignId]);

  useEffect(() => {
    if (!shouldLoadWorkerVisits || !workerId || workerId === "create") return;
    let cancelled = false;
    const loadVisits = async () => {
      setVisitLoading(true);
      try {
        const visits = await medicalVisitsApi.listByWorker(workerId);
        if (cancelled) return;
        setWorkerVisits(Array.isArray(visits) ? visits : []);
        setSelectedQuickVisitId((current) => current ?? visits[0]?.id ?? null);
      } catch {
        if (!cancelled) setWorkerVisits([]);
      } finally {
        if (!cancelled) setVisitLoading(false);
      }
    };
    void loadVisits();
    return () => {
      cancelled = true;
    };
  }, [shouldLoadWorkerVisits, workerId]);

  useEffect(() => {
    if (resolvedActiveVisitId && selectedQuickVisitId !== resolvedActiveVisitId) {
      setSelectedQuickVisitId(resolvedActiveVisitId);
    }
  }, [resolvedActiveVisitId, selectedQuickVisitId]);

  useEffect(() => {
    if (activeSectionGroup !== "visitsMedical") return;

    const uniqueCampaignIds = Array.from(
      new Set(
        workerVisits
          .map((visit) => (typeof visit.campaign_id === "number" ? visit.campaign_id : null))
          .filter((value): value is number => value !== null),
      ),
    );

    if (uniqueCampaignIds.length === 0) {
      setVisitCampaignTestsByCampaignId({});
      return;
    }

    let cancelled = false;

    const loadVisitCampaignTests = async () => {
      const entries = await Promise.all(
        uniqueCampaignIds.map(async (id) => {
          if (id === Number(campaignId)) {
            return [
              id,
              campaignTests
                .map((item) => item.test?.name?.trim() || "")
                .filter(Boolean),
            ] as const;
          }

          try {
            const tests = await campaignsApi.tests(id);
            return [
              id,
              tests
                .map((item) => item.test?.name?.trim() || "")
                .filter(Boolean),
            ] as const;
          } catch {
            return [id, []] as const;
          }
        }),
      );

      if (!cancelled) {
        setVisitCampaignTestsByCampaignId(Object.fromEntries(entries));
      }
    };

    void loadVisitCampaignTests();

    return () => {
      cancelled = true;
    };
  }, [activeSectionGroup, campaignId, campaignTests, workerVisits]);

  useEffect(() => {
    if (!hasSelectedVisit || !normalizedVisitId) {
      setMedicalVisit(null);
      setDynamicMedicalTestValues({});
      return;
    }

    let cancelled = false;
    const loadVisit = async () => {
      try {
        const visit = await medicalVisitsApi.get(normalizedVisitId);
        if (cancelled) return;
        const parsedFormData = parseMedicalVisitFormData(visit.form_data);
        const visitFormData = (parsedFormData || null) as WorkerMedicalFileDataWithDynamicTests | null;
        
        
        
        setMedicalVisit({
          ...visit,
          form_data: parsedFormData ?? visit.form_data,
        });
        setMedicalFileDataSource(visitFormData);
        setActiveVisitId(visit.id);
        setDynamicMedicalTestValues(
          restoreDynamicMedicalTests(visitFormData as unknown as Record<string, unknown> | null),
        );
      } catch {
        if (!cancelled) {
          setMedicalVisit(null);
          setDynamicMedicalTestValues({});
        }
      }
    };

    void loadVisit();

    return () => {
      cancelled = true;
    };
  }, [
    hasSelectedVisit,
    normalizedVisitId,
  ]);

  useEffect(() => {
    if (!medicalVisit) return;

    const parsedFormData = parseMedicalVisitFormData(medicalVisit.form_data);
    const defaultForm = createEmptyForm(
      worker,
      currentCampaign?.company_name,
      currentCampaign?.site_name || currentCampaign?.branch_name,
      campaignId,
      doctorName,
    );
    const folderSource =
      worker?.medical_file_data && Object.keys(worker.medical_file_data).length > 0
        ? worker.medical_file_data
        : parsedFormData && typeof parsedFormData === "object"
          ? ((parsedFormData as Record<string, unknown>).workerSnapshot as Record<string, unknown> | undefined) ?? {}
          : {};
    
    setForm(hydrateFolderAndVisitForm(defaultForm, folderSource, parsedFormData));
  }, [
    campaignId,
    currentCampaign?.branch_name,
    currentCampaign?.company_name,
    currentCampaign?.site_name,
    doctorName,
    medicalVisit,
    worker,
  ]);

  useEffect(() => {
    if (!medicalVisit?.form_data) return;
    const visitFormData = medicalVisit.form_data as WorkerMedicalFileDataWithDynamicTests;
    
    setDynamicMedicalTestValues(
      restoreDynamicMedicalTests(visitFormData as unknown as Record<string, unknown>),
    );
  }, [medicalVisit?.id]);

  useEffect(() => {
    if (!shouldLoadAptitudeCertificate) return;
    void refreshAptitudeCertificate(normalizedVisitId ?? undefined);
  }, [isCreateMode, normalizedVisitId, shouldLoadAptitudeCertificate, workerId]);

  useEffect(() => {
    if (!shouldLoadPrescriptions || isCreateMode || !workerId || !campaignId) {
      setPrescriptions([]);
      setPrescriptionForm(createEmptyPrescriptionForm(worker, doctorName));
      return;
    }

    let cancelled = false;

    const loadPrescriptions = async () => {
      setPrescriptionLoading(true);
      try {
        const records = await prescriptionsApi.list({
          worker_id: Number(workerId),
          campaign_id: Number(campaignId),
          medical_visit_id: resolvedActiveVisitId ?? undefined,
        });
        if (cancelled) return;
        setPrescriptions(records);
        setSelectedPrescriptionId((current) => current ?? records[0]?.id ?? null);
        setPrescriptionForm(
          records[0]
            ? mapPrescriptionToForm(records[0], worker, doctorName)
            : createEmptyPrescriptionForm(worker, doctorName),
        );
      } catch {
        if (cancelled) return;
        setPrescriptions([]);
        setPrescriptionForm(createEmptyPrescriptionForm(worker, doctorName));
      } finally {
        if (!cancelled) {
          setPrescriptionLoading(false);
        }
      }
    };

    void loadPrescriptions();

    return () => {
      cancelled = true;
    };
  }, [
    campaignId,
    doctorName,
    isCreateMode,
    resolvedActiveVisitId,
    shouldLoadPrescriptions,
    worker,
    workerId,
  ]);

  useEffect(() => {
  if (!shouldLoadOrientations || isCreateMode || !workerId || !campaignId) {
    setOrientations([]);
    setOrientationForm(createEmptyMedicalOrientationForm(worker, doctorName));
    return;
  }

  let cancelled = false;

  const loadOrientations = async () => {
  setOrientationLoading(true);
  try {
    const response = await orientationsApi.list({
      worker_id: Number(workerId),
      campaign_id: Number(campaignId),
      medical_visit_id: resolvedActiveVisitId ?? undefined,
    });
    if (cancelled) return;
    
    // Client-side filter fallback until backend is fixed
    const allRecords = response.items ?? response ?? [];
    const records = allRecords
      .filter(
        (item) =>
          item.worker_id === Number(workerId) &&
          item.campaign_id === Number(campaignId) &&
          (resolvedActiveVisitId == null || item.medical_visit_id === resolvedActiveVisitId),
      )
      .map(normalizeOrientationCertificateForUi);
    
    setOrientations(records);
    setSelectedOrientationCertificateId((current) => current ?? records[0]?.id ?? null);
    setOrientationForm(
      records[0]
        ? mapOrientationToForm(records[0], worker, doctorName)
        : createEmptyMedicalOrientationForm(worker, doctorName),
    );
    } catch {
      if (cancelled) return;
      setOrientations([]);
      setOrientationForm(createEmptyMedicalOrientationForm(worker, doctorName));
    } finally {
      if (!cancelled) {
        setOrientationLoading(false);
      }
    }
  };

  void loadOrientations();

  return () => {
    cancelled = true;
  };
}, [
  campaignId,
  doctorName,
  isCreateMode,
  resolvedActiveVisitId,
  shouldLoadOrientations,
  worker,
  workerId,
]);

  useEffect(() => {
    if (!storageKey) return;
    if (!form.firstName.trim() && !form.lastName.trim() && !form.dateOfBirth.trim()) {
      return;
    }

    window.localStorage.setItem(storageKey, JSON.stringify(form));
  }, [form, storageKey, form.firstName, form.lastName, form.dateOfBirth]);

  useEffect(() => {
    if (!isCreateMode) return;
    if (authLoading || !isAuthenticated || !user) return;

    const firstName = form.firstName.trim();
    const lastName = form.lastName.trim();
    const birthDate = form.dateOfBirth.trim();
    const nationalId = form.nationalId.trim();

    if (!firstName || !lastName || !birthDate || !nationalId) {
      setDuplicateWorker(null);
      setDuplicateHistory(null);
      setDuplicateModalOpen(false);
      setDuplicateCheckLoading(false);
      setDuplicateCheckError(null);
      return;
    }

    let cancelled = false;
    const timer = window.setTimeout(async () => {
      setDuplicateCheckLoading(true);
      setDuplicateCheckError(null);
      try {
        const result = await workersApi.lookupWithHistory({
          first_name: firstName,
          last_name: lastName,
          birth_date: birthDate,
          national_id: nationalId,
        });
        if (cancelled) return;
        setDuplicateWorker(result.worker);
        setWorker(result.worker);
        setNotice({
          type: "success",
          message: "Ce travailleur est déjà inscrit ; son dossier médical a été ouvert.",
        });
        setDuplicateHistory(result.history as WorkerLookupHistory);
        setDuplicateModalOpen(true);
      } catch (error) {
        if (cancelled) return;
        const status = (error as { response?: { status?: number } })?.response?.status;
        if (status === 404) {
          setDuplicateWorker(null);
          setDuplicateCheckError(null);
          return;
        }
        setDuplicateWorker(null);
        setDuplicateCheckError("تعذر التحقق من وجود العامل حاليا.");
      } finally {
        if (!cancelled) {
          setDuplicateCheckLoading(false);
        }
      }
    }, 500);

    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [
    authLoading,
    campaignId,
    form.dateOfBirth,
    form.firstName,
    form.lastName,
    form.nationalId,
    isAuthenticated,
    isCreateMode,
    navigate,
    user,
  ]);

  useEffect(() => {
    const patientName = `${form.firstName} ${form.lastName}`.trim() || worker?.full_name || "";
    const age = calculateAgeFromDate(form.dateOfBirth || worker?.birth_date);
    setPrescriptionForm((current) => ({
      ...current,
      medical_visit_id: current.medical_visit_id ?? resolvedActiveVisitId ?? null,
      patient_name: patientName,
      age,
      doctor_name: current.doctor_name || doctorName,
    }));
  }, [
    doctorName,
    form.dateOfBirth,
    form.firstName,
    form.lastName,
    resolvedActiveVisitId,
    worker?.birth_date,
    worker?.full_name,
  ]);

  useEffect(() => {
    return () => {
      if (pdfPreviewUrl) {
        window.URL.revokeObjectURL(pdfPreviewUrl);
      }
      if (dossierPdfPreviewUrl) {
        window.URL.revokeObjectURL(dossierPdfPreviewUrl);
      }
      if (prescriptionPreviewUrl) {
        window.URL.revokeObjectURL(prescriptionPreviewUrl);
      }
      if (aptitudePdfPreviewUrl) {
        window.URL.revokeObjectURL(aptitudePdfPreviewUrl);
      }
    };
  }, [aptitudePdfPreviewUrl, dossierPdfPreviewUrl, pdfPreviewUrl, prescriptionPreviewUrl]);

  useEffect(() => {
    if (activeTab !== "pdfViewer" || pdfPreviewUrl || pdfPreviewLoading || isCreateMode || !workerId) {
      return;
    }
    handleLoadPdfPreview();
  }, [activeTab, isCreateMode, pdfPreviewLoading, pdfPreviewUrl, workerId]);

  useEffect(() => {
    if (
      activeTab !== "pdfDossier" ||
      dossierPdfPreviewUrl ||
      dossierPdfPreviewLoading ||
      isCreateMode ||
      !workerId
    ) {
      return;
    }
    handleLoadDossierPdfPreview();
  }, [activeTab, dossierPdfPreviewLoading, dossierPdfPreviewUrl, isCreateMode, workerId]);

  const updateField = <K extends keyof WorkerMedicalFileForm>(
    key: K,
    value: WorkerMedicalFileForm[K],
  ) => {
    setForm((current) => ({ ...current, [key]: value }));
    setErrors((current) => ({ ...current, [key]: undefined }));
  };

  const updateClinicalExam = <K extends keyof ClinicalExam>(
    key: K,
    value: ClinicalExam[K],
  ) => {
    setForm((current) => ({ ...current, clinicalExam: { ...current.clinicalExam, [key]: value } }));
  };

  const updateComplementaryExams = <K extends keyof ComplementaryExams>(
    key: K,
    value: ComplementaryExams[K],
  ) => {
    setForm((current) => ({
      ...current,
      complementaryExams: { ...current.complementaryExams, [key]: value },
    }));
  };

  const buildDefaultProfilTaGlycemie = () =>
    createEmptyProfilTaGlycemie(formatWorkerFullName(form.firstName, form.lastName));

  const buildDefaultWorkStoppageCertificate = () =>
    createEmptyWorkStoppageCertificate(
      form.medicalDecision.validation.validatingDoctor || doctorName,
      formatWorkerFullName(form.firstName, form.lastName),
      calculateAgeFromDate(form.dateOfBirth || worker?.birth_date),
      form.position || form.direction,
    );

  const updateProfilTaGlycemie = (
    value: WorkerMedicalFileForm["profilTaGlycemie"],
  ) => {
    setForm((current) => ({
      ...current,
      profilTaGlycemie: value,
    }));
  };

  const updateWorkStoppageCertificate = (
    value: WorkerMedicalFileForm["workStoppageCertificate"],
  ) => {
    setForm((current) => ({
      ...current,
      workStoppageCertificate: value,
    }));
  };

  const addProfilTaGlycemieRow = () => {
    setForm((current) => ({
      ...current,
      profilTaGlycemie: {
        ...(current.profilTaGlycemie.fullName
          ? current.profilTaGlycemie
          : buildDefaultProfilTaGlycemie()),
        rows: [...current.profilTaGlycemie.rows, createProfilTaGlycemieRow()],
      },
    }));
  };

  const removeProfilTaGlycemieRow = (rowId: string) => {
    setForm((current) => {
      const remainingRows = current.profilTaGlycemie.rows.filter((row) => row.id !== rowId);
      return {
        ...current,
        profilTaGlycemie: {
          ...current.profilTaGlycemie,
          rows: remainingRows.length > 0 ? remainingRows : [createProfilTaGlycemieRow()],
        },
      };
    });
  };

  const handleDownloadProfilTemplate = async () => {
    try {
      downloadTemplate(form.profilTaGlycemie.fullName, form.profilTaGlycemie.rows);
    } catch {
      setNotice({
        type: "error",
        message: "Impossible de generer le fichier Excel.",
      });
    }
  };

  const resetProfilImportState = () => {
    setProfilImportPreviewOpen(false);
    setProfilImportRows([]);
    setProfilIgnoredRows([]);
    setProfilImportedFileName("");
    if (profilExcelInputRef.current) {
      profilExcelInputRef.current.value = "";
    }
  };

  const importExcel = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) {
      return;
    }

    const lowerName = file.name.toLowerCase();
    if (!lowerName.endsWith(".xlsx") && !lowerName.endsWith(".xls")) {
      setNotice({
        type: "error",
        message: "Le fichier selectionne ne correspond pas au modele Profil TA et Glycemie.",
      });
      event.target.value = "";
      return;
    }

    try {
      const buffer = await file.arrayBuffer();
      const workbook = XLSX.read(buffer, {
        type: "array",
        cellDates: true,
        raw: true,
      });
      const worksheetName = workbook.SheetNames[0];
      const worksheet = worksheetName ? workbook.Sheets[worksheetName] : null;

      if (!worksheet) {
        throw new Error("INVALID_TEMPLATE");
      }

      const parsed = parseWorksheet(worksheet, form.profilTaGlycemie.rows);

      if (!parsed) {
        throw new Error("INVALID_TEMPLATE");
      }

      if (parsed.previewRows.length === 0) {
        setNotice({
          type: "error",
          message:
            parsed.ignoredRows.length > 0
              ? "Aucune ligne valide n'a ete detectee dans ce fichier."
              : "Le fichier selectionne ne correspond pas au modele Profil TA et Glycemie.",
        });
        event.target.value = "";
        return;
      }

      setProfilImportedFileName(file.name);
      setProfilImportRows(parsed.previewRows);
      setProfilIgnoredRows(parsed.ignoredRows);
      setProfilImportPreviewOpen(true);
    } catch {
      setNotice({
        type: "error",
        message: "Le fichier selectionne ne correspond pas au modele Profil TA et Glycemie.",
      });
      event.target.value = "";
    }
  };

  const handleConfirmProfilImport = () => {
    if (profilImportRows.length === 0) {
      resetProfilImportState();
      return;
    }

    const importedRows = profilImportRows.map((row) => ({
      id:
        typeof globalThis.crypto?.randomUUID === "function"
          ? globalThis.crypto.randomUUID()
          : createId(),
      date: row.date,
      rightArm: row.beforeBreakfast === null ? "" : String(row.beforeBreakfast),
      leftArm: row.beforeLunch === null ? "" : String(row.beforeLunch),
      time: row.beforeDinner === null ? "" : String(row.beforeDinner),
      glycemia: "",
      observation: "",
    }));

    setForm((current) => {
      const [firstRow] = current.profilTaGlycemie.rows;
      const hasOnlyEmptyPlaceholder =
        current.profilTaGlycemie.rows.length === 1 &&
        Boolean(firstRow) &&
        [
          firstRow.date,
          firstRow.rightArm,
          firstRow.leftArm,
          firstRow.time,
        ].every((value) => value.trim() === "");

      return {
        ...current,
        profilTaGlycemie: {
          ...(current.profilTaGlycemie.fullName
            ? current.profilTaGlycemie
            : buildDefaultProfilTaGlycemie()),
          rows: [
            ...(hasOnlyEmptyPlaceholder ? [] : current.profilTaGlycemie.rows),
            ...importedRows,
          ],
        },
      };
    });

    setNotice({
      type: "success",
      message:
        profilIgnoredRows.length > 0
          ? `${profilImportRows.length} ligne(s) importee(s). ${profilIgnoredRows.length} ligne(s) ignoree(s).`
          : `${profilImportRows.length} ligne(s) importee(s) avec succes.`,
    });

    resetProfilImportState();
  };
  
const updateMedicalDecision = <K extends keyof MedicalDecision>(
  key: K,
  value: MedicalDecision[K],
) => {
  setForm((current) => {
    const medicalDecision = {
      ...current.medicalDecision,
      [key]: value,
    };

    if (key === "nextVisit") {
      const nextVisit = value as MedicalDecision["nextVisit"];

      const formattedDate = formatDisplayDate(nextVisit.nextVisitDate);
      

      medicalDecision.recommendations = {
        ...medicalDecision.recommendations,
        doctorRecommendations:
          `La prochaine visite médicale périodique est prévue le : ${formattedDate}`,
      };
    }

    return {
      ...current,
      medicalDecision,
    };
  });
};

  const validateForm = () => {
    const nextErrors: Partial<Record<keyof WorkerMedicalFileForm, string>> = {};
    if (!form.medicalFileNumber.trim()) {
      nextErrors.medicalFileNumber = "Le numero de dossier est obligatoire.";
    }
    if (!/^\d{18}$/.test(form.nationalId.trim())) {
      nextErrors.nationalId = "Le numero d'identite nationale doit contenir exactement 18 chiffres.";
    }
    if (!form.lastName.trim()) nextErrors.lastName = "Le nom est obligatoire.";
    if (!form.firstName.trim()) nextErrors.firstName = "Le prenom est obligatoire.";
    if (!form.sex.trim()) nextErrors.sex = "Le sexe est obligatoire.";
    if (!form.dateOfBirth.trim()) {
      nextErrors.dateOfBirth = "La date de naissance est obligatoire.";
    }
    if (!/^\d{10}$/.test(form.phone.trim())) {
      nextErrors.phone = "Le numero de telephone doit contenir exactement 10 chiffres.";
    }
    if (!form.companyName.trim()) nextErrors.companyName = "L'entreprise est obligatoire.";
    if (!form.siteName.trim()) nextErrors.siteName = "Le site est obligatoire.";
    setErrors(nextErrors);
    return Object.keys(nextErrors).length === 0;
  };

  const validateMedicalFolderFields = () => {
    return validateForm();
  };

  const workerVisitTestHistory = useMemo(() => {
    return selectedWorkerMedicalVisits.map((visit) => {
      const visitData = (visit.form_data as Record<string, unknown> | null) || {};
      const rawTests = Array.isArray(visitData.selectedTests)
        ? visitData.selectedTests
        : Array.isArray(visitData.tests)
          ? visitData.tests
          : [];

      const serializedTests = rawTests
        .map((item) => {
          if (typeof item === "string") return item.trim();
          if (item && typeof item === "object") {
            const candidate = item as { name?: unknown; label?: unknown; test_name?: unknown };
            return String(candidate.name || candidate.label || candidate.test_name || "").trim();
          }
          return "";
        })
        .filter(Boolean);

      const campaignScopedTests =
        typeof visit.campaign_id === "number"
          ? visitCampaignTestsByCampaignId[visit.campaign_id] || []
          : [];

      const tests = serializedTests.length > 0 ? serializedTests : campaignScopedTests;

      const decision = (visitData.medicalDecision as Record<string, unknown> | undefined) || {};
      const validation = (decision.validation as Record<string, unknown> | undefined) || {};

      return {
        visitId: visit.id,
        visitDate: visit.visit_date,
        status: visit.status,
        companyName:
          String(visitData.companyName || visitData.company_name || currentCampaign?.company_name || "").trim() ||
          undefined,
        branchName:
          String(visitData.branchName || visitData.branch_name || currentCampaign?.branch_name || "").trim() ||
          undefined,
        siteName:
          String(visitData.siteName || visitData.site_name || visit.site_name || currentCampaign?.site_name || "").trim() ||
          undefined,
        campaignName:
          String(visitData.campaignName || visitData.campaign_name || currentCampaign?.title || currentCampaign?.company_name || "").trim() ||
          undefined,
        validatedDoctor:
          String(
            validation.validatingDoctor ||
              validation.doctor ||
              visitData.confirmationDoctor ||
              visitData.internalVisitDoctor ||
              visitData.validatedDoctor ||
              visitData.validateDoctor ||
              "",
          ).trim() || undefined,
        aptitude:
          String(
            decision.aptitude ||
              decision.medicalAptitude ||
              visitData.aptitude ||
              "",
          ).trim() || undefined,
        tests,
      };
    });
  }, [
    currentCampaign?.branch_name,
    currentCampaign?.company_name,
    currentCampaign?.site_name,
    currentCampaign?.title,
    selectedWorkerMedicalVisits,
    visitCampaignTestsByCampaignId,
  ]);

  const currentCampaignDescriptors = useMemo(
    () =>
      campaignMedicalTestDescriptors.filter((descriptor) =>
        campaignTests.some((assignment) => descriptor.match(assignment)),
      ),
    [campaignTests],
  );

  const currentCampaignDynamicTests = useMemo(() => {
    return campaignTests
      .filter((assignment) => !campaignMedicalTestDescriptors.some((descriptor) => descriptor.match(assignment)))
      .map((assignment) => {
        const description = getDynamicMedicalTestConfigSource(assignment);
        const config = parseDynamicMedicalTestConfig(description);
        const shouldShowError = isLikelyJsonDescription(description) && !config;
        return {
          assignment,
          testId: assignment.test_id,
          campaignTestId: assignment.campaign_test_id || assignment.id,
          name: getDynamicMedicalTestName(assignment),
          sectionId: getDynamicMedicalTestSectionId(assignment),
          config,
          configError: shouldShowError ? "Configuration invalide" : null,
        };
      });
  }, [campaignTests]);

  useEffect(() => {
    setDynamicMedicalTestErrors((current) => {
      const next = { ...current };
      currentCampaignDynamicTests.forEach((test) => {
        if (test.configError) {
          next[test.testId] = test.configError;
        } else {
          delete next[test.testId];
        }
      });
      return next;
    });

    setDynamicMedicalTestValues((current) => {
      const next = { ...current };
      currentCampaignDynamicTests.forEach((test) => {
        const testKey = String(test.testId);
        if (!next[testKey]) {
          next[testKey] = {
            testId: test.testId,
            testName: test.name,
            values: {},
          };
          test.config?.fields?.forEach((field) => {
            next[testKey].values[field.name] =
              field.type === "checkbox"
                ? false
                : field.type === "radio" || field.type === "select"
                  ? field.options?.[0]?.value || ""
                  : "";
          });
        }
      });
      return next;
    });
  }, [currentCampaignDynamicTests]);

  const currentCampaignTestKeys = useMemo(
    () => new Set(currentCampaignDescriptors.map((descriptor) => descriptor.key)),
    [currentCampaignDescriptors],
  );

  const currentCampaignSectionIds = useMemo(
    () =>
      new Set<CampaignMedicalSectionId>([
        ...currentCampaignDescriptors.map((descriptor) => descriptor.sectionId),
        ...currentCampaignDynamicTests.map((item) => item.sectionId),
      ]),
    [currentCampaignDescriptors, currentCampaignDynamicTests],
  );

  const hasAssignedCampaignTests = campaignTests.length > 0;

  const requiredCampaignTestsMissing = useMemo(() => {
    return currentCampaignDescriptors
      .filter((descriptor) =>
        campaignTests.some((assignment) => assignment.required && descriptor.match(assignment)),
      )
      .filter((descriptor) => !descriptor.isComplete(form))
      .map((descriptor) => descriptor.label);
  }, [campaignTests, currentCampaignDescriptors, form]);

  const buildVisitFormData = (
    sourceForm: WorkerMedicalFileForm,
    options?: { resetValidation?: boolean },
  ): WorkerMedicalVisitFormData => {
    const existingVisitData = normalizeMedicalVisitFormData(medicalVisit?.form_data);
    const dynamicMedicalTests = dynamicMedicalTestValues;
    const workerFullName = formatWorkerFullName(sourceForm.firstName, sourceForm.lastName);
    const defaultProfilTaGlycemie = createEmptyProfilTaGlycemie(workerFullName);
    const shouldResetValidation = options?.resetValidation === true;
    const aptitudeCertificateSnapshot = {
      id: shouldResetValidation ? null : (activeAptitudeCertificateId ?? null),
      certificateNumber: aptitudeForm.certificateNumber || "",
      aptitude: sourceForm.medicalDecision.aptitude || aptitudeForm.aptitude || "",
      aptitudeInterpretation: aptitudeForm.aptitudeInterpretation || "",
      doctorRecommendations: aptitudeForm.doctorRecommendations || "",
      visitDate: aptitudeForm.visitDate || sourceForm.internalVisitDate || "",
      issueDate: aptitudeForm.issueDate || "",
      status: shouldResetValidation ? "draft" : (aptitudeForm.status || "draft"),
      includeValidatorSignature: shouldResetValidation ? false : (aptitudeForm.includeValidatorSignature ?? false),
      validatorSignatureUrl: shouldResetValidation ? null : (aptitudeForm.validatorSignatureUrl ?? null),
      validatedDoctorName: shouldResetValidation ? "" : (aptitudeForm.validatedDoctorName || ""),
      validatedByUserId: shouldResetValidation ? null : (aptitudeForm.validatedByUserId ?? null),
      validatedAt: shouldResetValidation ? null : (aptitudeForm.validatedAt ?? null),
      validatorRole: shouldResetValidation ? null : (aptitudeForm.validatorRole ?? null),
      firstName: aptitudeForm.firstName || sourceForm.firstName || "",
      lastName: aptitudeForm.lastName || sourceForm.lastName || "",
      companyName: aptitudeForm.companyName || sourceForm.companyName || "",
      jobTitle: aptitudeForm.jobTitle || sourceForm.position || "",
      birthDate: aptitudeForm.birthDate || sourceForm.dateOfBirth || "",
      birthPlace: aptitudeForm.birthPlace || sourceForm.birthPlace || "",
      bloodGroup: aptitudeForm.bloodGroup || sourceForm.bloodGroup || "",
    };

    return {
      internalVisit: {
        hire: sourceForm.internalVisitHire,
        periodic: sourceForm.internalVisitPeriodic,
        date: sourceForm.internalVisitDate,
        doctor: sourceForm.internalVisitDoctor,
        weightKg: sourceForm.internalVisitWeightKg,
        heightCm: sourceForm.internalVisitHeightCm,
        ta: sourceForm.internalVisitTa,
        fc: sourceForm.internalVisitFc,
        distanceOdSc: sourceForm.internalVisitDistanceOdSc,
        distanceOdAc: sourceForm.internalVisitDistanceOdAc,
        distanceOgSc: sourceForm.internalVisitDistanceOgSc,
        distanceOgAc: sourceForm.internalVisitDistanceOgAc,
        distanceOdg: sourceForm.internalVisitDistanceOdg,
      },
      clinicalExam: sourceForm.clinicalExam,
      complementaryExams: sourceForm.complementaryExams,
      medicalDecision: sourceForm.medicalDecision,
      dynamicMedicalTests,
      profilTaGlycemie: {
        ...defaultProfilTaGlycemie,
        ...sourceForm.profilTaGlycemie,
        fullName: sourceForm.profilTaGlycemie?.fullName || workerFullName,
        rows:
          sourceForm.profilTaGlycemie?.rows?.length > 0
            ? sourceForm.profilTaGlycemie.rows
            : defaultProfilTaGlycemie.rows,
      },
      aptitudeCertificate: {
        ...((existingVisitData.aptitudeCertificate as Record<string, unknown> | undefined) || {}),
        ...aptitudeCertificateSnapshot,
      },
      orientationCertificates: orientations.map((orientation) => ({
        id: shouldResetValidation ? null : orientation.id,
        orientationNumber: orientation.orientation_number,
        orientationDate: orientation.orientation_date,
        orientationType: orientation.orientation_type,
        orientationTypeOther: orientation.orientation_type_other,
        orientationTypes: getOrientationTypesFromCertificate(orientation),
        orientationDetails: orientation.orientation_details,
        prescribingDoctor: orientation.doctor_name,
        includeValidatorSignature: shouldResetValidation ? false : (orientation.includeValidatorSignature ?? false),
        status: shouldResetValidation ? "draft" : orientation.status,
        validatorId: shouldResetValidation ? null : orientation.validatorId,
        validatorName: shouldResetValidation ? null : orientation.validatorName,
        validatorRole: shouldResetValidation ? null : orientation.validatorRole,
        validatedAt: shouldResetValidation ? null : orientation.validatedAt,
      })),
      workStoppageCertificate: sourceForm.workStoppageCertificate ?? null,
      ordonnances: prescriptions.map((prescription) => ({
        id: shouldResetValidation ? null : prescription.id,
        prescription_number: prescription.prescription_number,
        prescription_date: prescription.prescription_date,
        doctor_name: prescription.doctor_name,
        diagnosis: prescription.diagnosis,
        notes: prescription.notes,
        status: shouldResetValidation ? "draft" : prescription.status,
        includeValidatorSignature: shouldResetValidation ? false : (prescription.includeValidatorSignature ?? false),
        validatedAt: shouldResetValidation ? null : prescription.validatedAt,
        validatorName: shouldResetValidation ? null : prescription.validatorName,
        validatorRole: shouldResetValidation ? null : prescription.validatorRole,
        items: prescription.items,
      })),
      validation: shouldResetValidation
        ? {
            ...sourceForm.medicalDecision.validation,
            validatingDoctor: sourceForm.medicalDecision.validation.validatingDoctor,
            validationDate: sourceForm.medicalDecision.validation.validationDate,
            electronicSignature: "",
            includeValidatorSignature: false,
          }
        : sourceForm.medicalDecision.validation,
      auditTrail: sourceForm.auditTrail,
    };
  };

  const buildMedicalFileData = (sourceForm: WorkerMedicalFileForm) => ({
    medicalFileNumber: sourceForm.medicalFileNumber,
    employeeCode: sourceForm.employeeCode,
    nationalId: sourceForm.nationalId,
    lastName: sourceForm.lastName,
    firstName: sourceForm.firstName,
    etat_actual: sourceForm.etat_actual || "present",
    sex: sourceForm.sex,
    dateOfBirth: sourceForm.dateOfBirth,
    birthPlace: sourceForm.birthPlace,
    familySituation: sourceForm.familySituation,
    phone: sourceForm.phone,
    originAddress: sourceForm.originAddress,
    professionalAddress: sourceForm.professionalAddress,
    direction: sourceForm.direction,
    position: sourceForm.position,
    department: sourceForm.department,
    service: sourceForm.service,
    workshop: sourceForm.workshop,
    schoolEducation: sourceForm.schoolEducation,
    professionalTraining: sourceForm.professionalTraining,
    professionalQualification: sourceForm.professionalQualification,
    nationalServiceStatus: sourceForm.nationalServiceStatus,
    nationalServiceNotes: sourceForm.nationalServiceNotes,
    chronicDiseaseNotes: sourceForm.chronicDiseaseNotes,
    bloodGroup: sourceForm.bloodGroup,
    congenitalDiseases: sourceForm.congenitalDiseases,
    generalDiseases: sourceForm.generalDiseases,
    surgicalInterventions: sourceForm.surgicalInterventions,
    accidents: sourceForm.accidents,
    intoxications: sourceForm.intoxications,
    tobacco: sourceForm.tobacco,
    chewingTobacco: sourceForm.chewingTobacco,
    alcoholism: sourceForm.alcoholism,
    otherIntoxications: sourceForm.otherIntoxications,
    familyHistoryFather: sourceForm.familyHistoryFather,
    familyHistoryMother: sourceForm.familyHistoryMother,
    familyHistorySisters: sourceForm.familyHistorySisters,
    familyHistoryBrothers: sourceForm.familyHistoryBrothers,
    familyHistorySpouse: sourceForm.familyHistorySpouse,
    familyHistoryChildrenBoys: sourceForm.familyHistoryChildrenBoys,
    familyHistoryChildrenGirls: sourceForm.familyHistoryChildrenGirls,
    professionalDiseaseNotes: sourceForm.professionalDiseaseNotes,
    companyName: sourceForm.companyName,
    siteName: sourceForm.siteName,
    professionalHistory: sourceForm.professionalHistory,
    vaccinations: sourceForm.vaccinations,
    workAccidents: sourceForm.workAccidents,
    occupationalDiseases: sourceForm.occupationalDiseases,
    spontaneousConsultations: sourceForm.spontaneousConsultations,
    confirmationStatus: sourceForm.confirmationStatus,
    confirmationDoctor: sourceForm.confirmationDoctor,
    confirmationDate: sourceForm.confirmationDate,
    isLocked: sourceForm.isLocked,
  });

  const validateDynamicMedicalTests = () => {
    for (const test of currentCampaignDynamicTests) {
      if (!test.config?.fields?.length) continue;
      const saved = dynamicMedicalTestValues[String(test.testId)]?.values || {};
      const missingRequired = test.config.fields.some((field) => {
        if (!field.required) return false;
        const value = saved[field.name];
        return value === undefined || value === null || String(value).trim() === "";
      });
      if (missingRequired) {
        setNotice({
          type: "error",
          message: `Les champs obligatoires du test ${test.name} sont manquants.`,
        });
        return false;
      }
    }
    return true;
  };

  const validateMedicalVisitFields = () => {
    const hasWorkStoppageData = Boolean(
      form.workStoppageCertificate &&
        [
          form.workStoppageCertificate.workStopDuration,
          form.workStoppageCertificate.workStopExtensionDuration,
          form.workStoppageCertificate.startDate,
          form.workStoppageCertificate.endDate,
          form.workStoppageCertificate.returnToWork ? "true" : "",
        ].some((value) => String(value || "").trim() !== ""),
    );

    if (
      hasWorkStoppageData &&
      form.workStoppageCertificate &&
      (
        !form.workStoppageCertificate.doctorFullName.trim() ||
        !form.workStoppageCertificate.workerFullName.trim() ||
        !form.workStoppageCertificate.workerAge.trim() ||
        !form.workStoppageCertificate.position.trim() ||
        !form.workStoppageCertificate.startDate.trim() ||
        !form.workStoppageCertificate.endDate.trim() ||
        !form.workStoppageCertificate.issuedAt.trim() ||
        (
          !form.workStoppageCertificate.workStopDuration.trim() &&
          !form.workStoppageCertificate.workStopExtensionDuration.trim() &&
          !form.workStoppageCertificate.returnToWork
        )
      )
    ) {
      setNotice({
        type: "error",
        message: "Veuillez completer le CM d'arret de travail ou le vider avant de valider la visite.",
      });
      return false;
    }

    if (!validateDynamicMedicalTests()) {
      return false;
    }

    if (requiredCampaignTestsMissing.length > 0) {
      setNotice({
        type: "error",
        message: `Les tests obligatoires suivants sont manquants: ${requiredCampaignTestsMissing.join(", ")}.`,
      });
      return false;
    }

    return true;
  };

  const handleSaveDraft = () => {
    window.localStorage.setItem(storageKey, JSON.stringify(buildMedicalFileData(form)));
    setNotice({
      type: "success",
      message: "Le brouillon du dossier a ete enregistre localement.",
    });
  };

  const ensureWorkerAssignedToCampaign = async (workerToAssignId: number) => {
    if (!currentCampaign?.id) return;
    const assignedWorkers = await campaignsApi.workers(currentCampaign.id);
    const alreadyAssigned = assignedWorkers.some((item) => item.id === workerToAssignId);
    if (!alreadyAssigned) {
      await campaignsApi.addWorkers(currentCampaign.id, [workerToAssignId]);
    }
  };

  const persistMedicalWorkflow = async (options?: {
    confirm?: boolean;
    createVisitOnWorkerCreate?: boolean;
    targetVisitId?: number | null;
    suppressSuccessNotice?: boolean;
    validateScope?: "none" | "folder" | "visit";
  }) => {
    const validateScope = options?.validateScope || "folder";

    if (isCreateMode && duplicateWorker) {
      setDuplicateModalOpen(true);
      return null;
    }
    if (duplicateCheckLoading) {
      setNotice({
        type: "error",
        message: "Ø¬Ø§Ø±ÙŠ Ø§Ù„ØªØ­Ù‚Ù‚ Ù…Ù† ÙˆØ¬ÙˆØ¯ Ø§Ù„Ø¹Ø§Ù…Ù„...",
      });
      return null;
    }

    const submissionDoctor =
      form.medicalDecision.validation.validatingDoctor || doctorName || form.internalVisitDoctor;
    const submissionDate = new Date().toISOString();
    const formToSave = options?.confirm
      ? {
          ...form,
          confirmationStatus: "confirmed" as const,
          confirmationDoctor: submissionDoctor,
          confirmationDate: submissionDate,
          confirmationSignature:
            form.medicalDecision.validation.electronicSignature || "Signature en attente",
          isLocked: true,
          auditTrail: [
            ...form.auditTrail,
            {
              id: createId(),
              action: "Confirmation du dossier",
              actor: submissionDoctor || "MÃ©decin",
              at: submissionDate,
            },
          ],
        }
      : {
          ...form,
          confirmationStatus: "draft" as const,
          isLocked: false,
        };

    if (validateScope === "folder" && !validateMedicalFolderFields()) {
      setNotice({
        type: "error",
        message: "Veuillez completer les champs obligatoires avant la validation du dossier.",
      });
      return null;
    }

    if (validateScope === "visit" && !validateMedicalVisitFields()) {
      return null;
    }

    if (!currentCampaign) {
      setNotice({
        type: "error",
        message: "Aucune campagne active n'est disponible pour enregistrer ce dossier.",
      });
      return null;
    }

    const medicalFileData = buildMedicalFileData(formToSave);
    const shouldPersistVisit =
      validateScope !== "folder" &&
      (Boolean(options?.targetVisitId ?? medicalVisit?.id ?? normalizedVisitId) ||
        Boolean(isCreateMode && options?.createVisitOnWorkerCreate));
    const workerPayload = {
      first_name: formToSave.firstName,
      last_name: formToSave.lastName,
      employee_code: formToSave.employeeCode.trim(),
      national_id: formToSave.nationalId.trim(),
      full_name: `${formToSave.firstName} ${formToSave.lastName}`.trim(),
      company_id: currentCampaign.company_id,
      branch_id: currentCampaign.branch_id,
      drilling_site_id: currentCampaign.drilling_site_id || undefined,
      position: formToSave.position || formToSave.direction || "Worker",
      etat_actual: formToSave.etat_actual || "present",
      gender: formToSave.sex,
      birth_date: formToSave.dateOfBirth || null,
      birth_wilaya: formToSave.birthPlace || null,
      marital_status: formToSave.familySituation || null,
      blood_group: formToSave.bloodGroup || null,
      phone: formToSave.phone || null,
      address: formToSave.originAddress || formToSave.professionalAddress || null,
      department: formToSave.department || null,
      medical_status: "in_progress",
      medical_file_status: options?.confirm ? "confirmed" : "draft",
      medical_file_data: medicalFileData,
      status: "active" as const,
    };

    const applyWorkerNationalIdError = (error: unknown) => {
      const response = error as { response?: { status?: number; data?: { message?: string } } };
      if (response?.response?.status === 400 && response.response.data?.message === "National identity number already exists.") {
        setErrors((current) => ({
          ...current,
          nationalId: "National identity number already exists.",
        }));
        return true;
      }
      return false;
    };

    let committedVisitBeforeWorker: MedicalVisit | null = null;
    try {
      const targetVisitId = options?.targetVisitId ?? medicalVisit?.id ?? normalizedVisitId;
      let savedVisit: MedicalVisit | null = null;
      // Check the visit's version before changing the worker's medical snapshot.
      if (shouldPersistVisit && targetVisitId && !isCreateMode) {
        savedVisit = await medicalVisitsApi.update(targetVisitId, {
          version: medicalVisit?.version,
          worker_id: Number(workerId),
          campaign_id: Number(campaignId),
          visit_date: medicalVisit?.visit_date || form.internalVisitDate || new Date().toISOString().slice(0, 10),
          status: medicalVisit?.status || "draft",
          form_data: buildVisitFormData(formToSave),
        });
        committedVisitBeforeWorker = savedVisit;
        setMedicalVisit(savedVisit);
      }
      const savedWorker = isCreateMode
        ? await workersApi.create(workerPayload)
        : await workersApi.update(workerId!, { ...workerPayload, sync_version: worker?.sync_version });

      await ensureWorkerAssignedToCampaign(savedWorker.id);
      setWorker((current) => ({
        ...(current || savedWorker),
        ...savedWorker,
        medical_file_data: savedWorker.medical_file_data,
      }));
      setMedicalFileDataSource(savedWorker.medical_file_data);

      if (shouldPersistVisit && targetVisitId && !savedVisit) {
        const visitFormData = buildVisitFormData(formToSave);
        savedVisit = await medicalVisitsApi.update(targetVisitId, {
          version: medicalVisit?.version,
          worker_id: savedWorker.id,
          campaign_id: Number(campaignId),
          visit_date: medicalVisit?.visit_date || form.internalVisitDate || new Date().toISOString().slice(0, 10),
          status: medicalVisit?.status || "draft",
          form_data: visitFormData,
        });
      } else if (shouldPersistVisit && isCreateMode && options?.createVisitOnWorkerCreate) {
        const visitFormData = buildVisitFormData(formToSave);
        savedVisit = await medicalVisitsApi.create({
          worker_id: savedWorker.id,
          campaign_id: Number(campaignId),
          visit_date: form.internalVisitDate || new Date().toISOString().slice(0, 10),
          status: "draft",
          form_data: visitFormData,
        });
      }

      if (savedVisit) {
        setMedicalVisit(savedVisit);
        setActiveVisitId(savedVisit.id);
        setSelectedQuickVisitId(savedVisit.id);
      }

      window.localStorage.setItem(storageKey, JSON.stringify(formToSave));
      window.localStorage.setItem(
        `${MEDICAL_FILE_STORAGE_PREFIX}${campaignId}.${savedWorker.id}.${savedVisit?.id || "draft"}`,
        JSON.stringify(buildMedicalFileData(formToSave)),
      );

      const nextDefaultForm = createEmptyForm(
        savedWorker,
        currentCampaign?.company_name,
        currentCampaign?.site_name || currentCampaign?.branch_name,
        campaignId,
        doctorName,
      );
      const nextForm = hydrateFolderAndVisitForm(
        nextDefaultForm,
        savedWorker.medical_file_data,
        savedVisit?.form_data ?? medicalVisit?.form_data ?? (shouldPersistVisit ? buildVisitFormData(formToSave) : null),
      );
      setForm(nextForm);

      if (shouldPersistVisit) {
        await refreshWorkerVisits();
        await refreshAptitudeCertificate(savedVisit?.id);
      }

      if (!options?.suppressSuccessNotice) {
        setNotice({
          type: "success",
          message: options?.confirm
            ? "Le dossier medical a ete confirme et verrouille localement pour revue."
            : "Le dossier medical a ete valide. Le travailleur a ete enregistre avec l'entreprise, la branche, le site de forage et la campagne.",
        });
      }

      return { worker: savedWorker, visit: savedVisit };
    } catch (error) {
      const nationalIdError = applyWorkerNationalIdError(error);
      if (committedVisitBeforeWorker) {
        throw new Error("VISIT_SAVED_WORKER_NOT_SAVED");
      }
      if (nationalIdError) return null;
      throw error;
    }
  };

  const legacyHandleSubmit = (options?: { confirm?: boolean }) => {
    const run = async () => {
      if (isCreateMode && duplicateWorker) {
        setDuplicateModalOpen(true);
        return;
      }
      if (duplicateCheckLoading) {
        setNotice({
          type: "error",
          message: "جاري التحقق من وجود العامل...",
        });
        return;
      }
      const submissionDoctor =
        form.medicalDecision.validation.validatingDoctor || doctorName || form.internalVisitDoctor;
      const submissionDate = new Date().toISOString();
      const formToSave = options?.confirm
        ? {
            ...form,
            confirmationStatus: "confirmed" as const,
            confirmationDoctor: submissionDoctor,
            confirmationDate: submissionDate,
            confirmationSignature:
              form.medicalDecision.validation.electronicSignature || "Signature en attente",
            isLocked: true,
            auditTrail: [
              ...form.auditTrail,
              {
                id: createId(),
                action: "Confirmation du dossier",
                actor: submissionDoctor || "Médecin",
                at: submissionDate,
              },
            ],
          }
        : form;
      if (!validateDynamicMedicalTests()) {
        return;
      }
      const visitFormData = buildVisitFormData(formToSave);

      if (!validateForm()) {
        setNotice({
          type: "error",
          message: "Veuillez completer les champs obligatoires avant la validation du dossier.",
        });
        return;
      }

      if (requiredCampaignTestsMissing.length > 0) {
        setNotice({
          type: "error",
          message: `Les tests obligatoires suivants sont manquants: ${requiredCampaignTestsMissing.join(", ")}.`,
        });
        return;
      }

      if (!currentCampaign) {
        setNotice({
          type: "error",
          message: "Aucune campagne active n'est disponible pour enregistrer ce dossier.",
        });
        return;
      }

      const workerPayload = {
        first_name: form.firstName,
        last_name: form.lastName,
        employee_code: form.employeeCode.trim(),
        national_id: form.nationalId.trim(),
        full_name: `${form.firstName} ${form.lastName}`.trim(),
        company_id: currentCampaign.company_id,
        branch_id: currentCampaign.branch_id,
        drilling_site_id: currentCampaign.drilling_site_id || undefined,
        position: form.position || form.direction || "Worker",
        etat_actual: form.etat_actual || "present",
        gender: form.sex,
        birth_date: form.dateOfBirth || null,
        birth_wilaya: form.birthPlace || null,
        marital_status: form.familySituation || null,
        blood_group: form.bloodGroup || null,
        phone: form.phone || null,
        address: form.originAddress || form.professionalAddress || null,
        department: form.department || null,
        medical_status: "in_progress",
        medical_file_data: buildMedicalFileData(formToSave),
        status: "active" as const,
      };

      const applyWorkerNationalIdError = (error: unknown) => {
        const response = error as { response?: { status?: number; data?: { message?: string } } };
        if (response?.response?.status === 400 && response.response.data?.message === "National identity number already exists.") {
          setErrors((current) => ({
            ...current,
            nationalId: "National identity number already exists.",
          }));
          return true;
        }
        return false;
      };

      if (isCreateMode && currentCampaign) {
        try {
          const savedWorker = await workersApi.create(workerPayload);
          await ensureWorkerAssignedToCampaign(savedWorker.id);
          const nextKey = `medical-folder.worker-medical-file.${campaignId}.${savedWorker.id}`;
          window.localStorage.setItem(nextKey, JSON.stringify(buildMedicalFileData(formToSave)));
          if (options?.confirm) setForm(formToSave);
          setNotice({
            type: "success",
            message: "Le travailleur a ete cree, rattache a la campagne et enregistre avec son entreprise, sa branche et son site.",
          });
          navigate(`/app/workspace/${campaignId}/workers/${savedWorker.id}/medical-file`);
          return;
        } catch (error) {
          if (applyWorkerNationalIdError(error)) {
            return;
          }
          setNotice({
            type: "error",
            message: "Impossible de creer le travailleur depuis ce dossier pour le moment.",
          });
          return;
        }
      }

      if (workerId) {
        try {
          const updated = await workersApi.update(workerId, { ...workerPayload, sync_version: worker?.sync_version });
          await ensureWorkerAssignedToCampaign(updated.id);
          setWorker(updated);
          if (medicalVisit?.id) {
            const updatedVisit = await medicalVisitsApi.update(medicalVisit.id, {
              version: medicalVisit.version,
              worker_id: updated.id,
              campaign_id: Number(campaignId),
              visit_date: medicalVisit.visit_date || form.internalVisitDate || new Date().toISOString().slice(0, 10),
              status: medicalVisit.status || "draft",
              form_data: visitFormData,
            });
            setMedicalVisit(updatedVisit);
          }
          await refreshAptitudeCertificate();
        } catch (error) {
          if (applyWorkerNationalIdError(error)) {
            return;
          }
          setNotice({
            type: "error",
            message: "Impossible d'enregistrer les informations du dossier en base pour le moment.",
          });
          return;
        }
      }

      window.localStorage.setItem(storageKey, JSON.stringify(formToSave));
      if (options?.confirm) setForm(formToSave);
      setNotice({
        type: "success",
        message: options?.confirm
          ? "Le dossier medical a ete confirme et verrouille localement pour revue."
          : "Le dossier medical a ete valide. Le travailleur a ete enregistre avec l'entreprise, la branche, le site de forage et la campagne.",
      });
    };

    void run();
  };

  void legacyHandleSubmit;

  const handleSubmit = (options?: { confirm?: boolean }) => {
    const run = async () => {
      try {
        const result = await persistMedicalWorkflow({
          ...options,
          createVisitOnWorkerCreate: isWorkerCreatePage,
          validateScope: "folder",
        });
        if (!result || !isWorkerCreatePage) {
          return;
        }
        if (result.visit?.id) {
          navigate(buildWorkerMedicalVisitRoute(campaignId!, result.worker.id, result.visit.id), {
            state: { tab: "internalVisit" },
          });
          return;
        }
        navigate(buildWorkerMedicalFileRoute(campaignId!, result.worker.id));
      } catch (error) {
        if (error instanceof Error && error.message === "VISIT_SAVED_WORKER_NOT_SAVED") {
          setNotice({ type: "error", message: "La visite a ete enregistree, mais les informations du travailleur ne l'ont pas ete. Votre formulaire reste ouvert." });
          return;
        }
        const response = error as { response?: { status?: number; data?: { message?: string; details?: { attempt_saved?: boolean } } } };
        if (response.response?.status === 409 && response.response.data?.message === "EXPECTED_VERSION_CONFLICT") {
          setNotice({ type: "error", message: response.response.data.details?.attempt_saved
            ? "Une autre modification a ete enregistree. Votre saisie reste dans le formulaire et sa tentative est conservee pour examen."
            : "Une autre modification a ete enregistree. Gardez votre saisie et reessayez apres verification." });
          return;
        }
        setNotice({
          type: "error",
          message:
            response?.response?.data?.message ||
            (isCreateMode
              ? "Impossible de creer le travailleur depuis ce dossier pour le moment."
              : "Impossible d'enregistrer les informations du dossier en base pour le moment."),
        });
      }
    };

    void run();
  };

  const handlePrint = () => {
    window.print();
  };

  const handleCreateNewVisit = async () => {
    if (!worker || !campaignId || visitSaving) return;
    setVisitSaving(true);
    try {
      const createdVisit = await medicalVisitsApi.create({
        worker_id: worker.id,
        campaign_id: Number(campaignId),
        visit_date: new Date().toISOString().slice(0, 10),
        status: "draft",
        form_data: buildVisitFormData(form, { resetValidation: true }),
      });
      setMedicalVisit(createdVisit);
      setActiveVisitId(createdVisit.id);
      await refreshWorkerVisits();
      navigate(buildWorkerMedicalVisitRoute(campaignId, worker.id, createdVisit.id), {
        state: { tab: "internalVisit" },
      });
      setNotice({
        type: "success",
        message: "La nouvelle visite médicale a été créée avec succès.",
      });
    } catch {
      setNotice({
        type: "error",
        message: "Impossible de créer la nouvelle visite médicale pour le moment.",
      });
    } finally {
      setVisitSaving(false);
    }
  };

  const saveCurrentVisitFormData = async () => {
    if (!medicalVisit?.id || !worker || !workerId || !campaignId) {
      return null;
    }
    const result = await persistMedicalWorkflow({
      targetVisitId: medicalVisit.id,
      suppressSuccessNotice: true,
      validateScope: "none",
    });
    return result?.visit ?? null;
  };

  const handleValidateVisit = async () => {
    const targetVisitId = selectedQuickVisitId ?? normalizedVisitId;
    if (!targetVisitId || Number.isNaN(targetVisitId)) {
      setNotice({
        type: "error",
        message: "Selectionnez une visite avant de la valider.",
      });
      return;
    }
    if (!canSignMedicalDocuments) {
      setNotice({
        type: "error",
        message: signatureAuthorizationMessage,
      });
      return;
    }
    if (
      form.medicalDecision.validation.includeValidatorSignature &&
      !(
        currentUserSignatureUrl ||
        user?.signaturePath ||
        user?.signature_path ||
        user?.signature_png
      )
    ) {
      setNotice({
        type: "error",
        message: "Veuillez televerser votre signature PNG dans les parametres avant de valider la visite.",
      });
      return;
    }

    if (import.meta.env.DEV) {
      
    }

    setVisitValidating(true);
    try {
      if (!validateMedicalVisitFields()) {
        return;
      }

      if (medicalVisit?.id === targetVisitId) {
        const savedVisit = await saveCurrentVisitFormData();
        if (!savedVisit) {
          return;
        }
      }

      const validatedVisit = await medicalVisitsApi.validateVisit(targetVisitId, {
        version: medicalVisit?.version,
        doctor_notes: medicalVisit?.doctor_notes ?? undefined,
      });


      setMedicalVisit(validatedVisit);
      setActiveVisitId(validatedVisit.id);
      setSelectedQuickVisitId(validatedVisit.id);
      try {
        await refreshWorkerVisits();
        const refreshedVisit = await medicalVisitsApi.get(targetVisitId);
        setMedicalVisit(refreshedVisit);
      } catch (refreshError) {
        void refreshError;
      }

      setNotice({
        type: "success",
        message: "La visite medicale a ete validee avec succes.",
      });
    } catch (error) {
      const response = error as {
        data?: { message?: string; details?: { attempt_saved?: boolean } };
        response?: { status?: number; data?: { message?: string; details?: { attempt_saved?: boolean } } };
      };
      if (response.response?.status === 409 && response.response.data?.message === "EXPECTED_VERSION_CONFLICT") {
        setNotice({ type: "error", message: response.response.data.details?.attempt_saved
          ? "La tentative de validation a ete conservee pour examen. Votre saisie reste dans le formulaire."
          : "La validation a rencontre une autre modification. Votre saisie reste dans le formulaire." });
        return;
      }
      setNotice({
        type: "error",
        message:
          response?.response?.data?.message ||
          response?.data?.message ||
          "Impossible de valider la visite medicale.",
      });
    } finally {
      setVisitValidating(false);
    }
  };

  const handleSwitchVisitSection = (nextSection: TabId) => {
    if (nextSection === activeTab) return;
    setActiveTab(nextSection);
  };

  const handleOpenVisitFromModal = (nextVisitId: number) => {
    const targetWorker = worker || duplicateWorker;
    if (!targetWorker) return;
    setDuplicateModalOpen(false);
    setActiveVisitId(nextVisitId);
    navigate(buildWorkerMedicalVisitRoute(campaignId!, targetWorker.id, nextVisitId), {
      state: { tab: "internalVisit" },
    });
  };

  const handleDuplicateVisitFromModal = async (sourceVisitId: number) => {
    const targetWorker = worker || duplicateWorker;
    if (!targetWorker || !campaignId || visitSaving) return;
    setVisitSaving(true);
    try {
      const duplicated = await medicalVisitsApi.duplicateVisit(targetWorker.id, sourceVisitId, {
        campaign_id: Number(campaignId),
        company_name: currentCampaign?.company_name,
        branch_name: currentCampaign?.branch_name,
        site_name: currentCampaign?.site_name,
        campaign_name: currentCampaign?.title || currentCampaign?.company_name,
      });
      setDuplicateModalOpen(false);
      setMedicalVisit(duplicated);
      setActiveVisitId(duplicated.id);
      navigate(buildWorkerMedicalVisitRoute(campaignId!, targetWorker.id, duplicated.id), {
        state: { tab: "internalVisit" },
      });
      setNotice({
        type: "success",
        message: "La visite a été dupliquée avec succès.",
      });
    } catch {
      setNotice({
        type: "error",
        message: "Impossible de dupliquer la visite pour le moment.",
      });
    } finally {
      setVisitSaving(false);
    }
  };


  const refreshPrescriptions = async (nextSelectedId?: number) => {
    if (isCreateMode || !workerId || !campaignId) return;
    const records = await prescriptionsApi.list({
      worker_id: Number(workerId),
      campaign_id: Number(campaignId),
      medical_visit_id: resolvedActiveVisitId ?? undefined,
    });
    setPrescriptions(records);
    const selected =
      (typeof nextSelectedId === "number"
        ? records.find((item) => item.id === nextSelectedId)
        : undefined) || records[0];
    setPrescriptionForm(
      selected
        ? mapPrescriptionToForm(selected, worker, doctorName)
        : createEmptyPrescriptionForm(worker, doctorName),
    );
  };

  const updatePrescriptionField = <K extends keyof PrescriptionFormState>(
    key: K,
    value: PrescriptionFormState[K],
  ) => {
    setPrescriptionForm((current) => ({ ...current, [key]: value }));
  };


  const updatePrescriptionItem = (
    itemId: string,
    key: keyof PrescriptionFormItem,
    value: string,
  ) => {
    setPrescriptionForm((current) => ({
      ...current,
      items: current.items.map((item) => {
        if (item.id !== itemId) return item;
        const nextItem = { ...item, [key]: value };
        if (key === "brand_name") {
          nextItem.medication_name = value;
        }
        if (key === "dose_quantity" || key === "dose_unit") {
          nextItem.dosage = buildPrescriptionLegacyDosage(nextItem);
        }
        if (key === "duration_value" || key === "duration_unit") {
          nextItem.duration = buildPrescriptionLegacyDuration(nextItem);
        }
        if (key === "number_of_boxes") {
          nextItem.quantity = value;
        }
        if (key === "frequency_custom" && value) {
          nextItem.frequency = "Autre...";
        }
        return nextItem;
      }),
    }));
  };

  const handlePrescriptionMedicineInputChange = (itemId: string, value: string) => {
    setManualPrescriptionEntryState((current) => ({ ...current, [itemId]: false }));
    setPrescriptionForm((current) => ({
      ...current,
      items: current.items.map((item) =>
        item.id === itemId
          ? {
              ...item,
              medicine_id: null,
              medication_name: value,
              brand_name: value,
              generic_name: "",
              strength: "",
              pharmaceutical_form: "",
              packaging: "",
              laboratory: "",
            }
          : item,
      ),
    }));
  };

  const handleSelectMedicineResult = (itemId: string, medicine: MedicineSearchItem) => {
    setManualPrescriptionEntryState((current) => ({ ...current, [itemId]: false }));
    setPrescriptionForm((current) => ({
      ...current,
      items: current.items.map((item) =>
        item.id === itemId
          ? {
              ...item,
              medicine_id: medicine.id,
              medication_name: medicine.brandName,
              brand_name: medicine.brandName,
              generic_name: medicine.genericName || "",
              strength: medicine.strength || "",
              pharmaceutical_form: medicine.pharmaceuticalForm || "",
              packaging: medicine.packaging || "",
              laboratory: medicine.laboratory || "",
            }
          : item,
      ),
    }));
  };

  const handleClearSelectedMedicine = (itemId: string) => {
    setManualPrescriptionEntryState((current) => ({ ...current, [itemId]: false }));
    setPrescriptionForm((current) => ({
      ...current,
      items: current.items.map((item) =>
        item.id === itemId
          ? {
              ...item,
              medicine_id: null,
              medication_name: "",
              brand_name: "",
              generic_name: "",
              strength: "",
              pharmaceutical_form: "",
              packaging: "",
              laboratory: "",
            }
          : item,
      ),
    }));
  };

  const handleCreatePrescriptionDraft = () => {
    setPrescriptionForm({
      ...createEmptyPrescriptionForm(worker, doctorName),
      medical_visit_id: resolvedActiveVisitId ?? null,
    });
    setManualPrescriptionEntryState({});
  };


  const handleSelectPrescription = (prescription: Prescription) => {
    setPrescriptionForm(mapPrescriptionToForm(prescription, worker, doctorName));
    setManualPrescriptionEntryState({});
  };



  const handleAddMedication = () => {
    setPrescriptionForm((current) => ({
      ...current,
      items: [...current.items, { ...createPrescriptionItemRow(), sort_order: current.items.length }],
    }));
  };

  const handleRemoveMedication = (itemId: string) => {
    setPrescriptionForm((current) => ({
      ...current,
      items: (current.items.length > 1
        ? current.items.filter((item) => item.id !== itemId)
        : [createPrescriptionItemRow()]).map((item, index) => ({ ...item, sort_order: index })),
    }));
    setManualPrescriptionEntryState((current) => {
      const next = { ...current };
      delete next[itemId];
      return next;
    });
  };

  const handleDuplicateMedication = (itemId: string) => {
    setPrescriptionForm((current) => {
      const sourceIndex = current.items.findIndex((item) => item.id === itemId);
      if (sourceIndex === -1) return current;
      const source = current.items[sourceIndex];
      const duplicate = { ...source, id: createId(), sort_order: sourceIndex + 1 };
      const items = [...current.items];
      items.splice(sourceIndex + 1, 0, duplicate);
      return {
        ...current,
        items: items.map((item, index) => ({ ...item, sort_order: index })),
      };
    });
  };

  const handleMoveMedication = (itemId: string, direction: "up" | "down") => {
    setPrescriptionForm((current) => {
      const index = current.items.findIndex((item) => item.id === itemId);
      if (index === -1) return current;
      const targetIndex = direction === "up" ? index - 1 : index + 1;
      if (targetIndex < 0 || targetIndex >= current.items.length) return current;
      const items = [...current.items];
      const [moved] = items.splice(index, 1);
      items.splice(targetIndex, 0, moved);
      return {
        ...current,
        items: items.map((item, itemIndex) => ({ ...item, sort_order: itemIndex })),
      };
    });
  };

  const buildPrescriptionPayload = () => ({
    worker_id: Number(workerId),
    campaign_id: Number(campaignId),
    medical_visit_id: prescriptionForm.medical_visit_id ?? resolvedActiveVisitId ?? null,
    doctor_id: typeof user?.id === "number" ? user.id : null,
    prescription_number: prescriptionForm.prescription_number || undefined,
    prescription_date: prescriptionForm.prescription_date,
    diagnosis: prescriptionForm.diagnosis,
    notes: prescriptionForm.notes,
    includeValidatorSignature: prescriptionForm.includeValidatorSignature,
    status: prescriptionForm.status,
    items: prescriptionForm.items
      .filter((item) => hasStructuredPrescriptionItemContent(item))
      .map((item, index) => ({
        medicine_id: item.medicine_id ?? null,
        medication_name:
          normalizePrescriptionText(item.medication_name) ||
          normalizePrescriptionText(item.brand_name) ||
          normalizePrescriptionText(item.generic_name),
        brand_name: normalizePrescriptionText(item.brand_name) || null,
        generic_name: normalizePrescriptionText(item.generic_name) || null,
        strength: normalizePrescriptionText(item.strength) || null,
        pharmaceutical_form: normalizePrescriptionText(item.pharmaceutical_form) || null,
        dosage: buildPrescriptionLegacyDosage(item) || normalizePrescriptionText(item.dosage) || null,
        dose_quantity: normalizePrescriptionText(item.dose_quantity) || null,
        dose_unit: normalizePrescriptionText(item.dose_unit) || null,
        frequency:
          normalizePrescriptionText(item.frequency) === "Autre..."
            ? "Autre..."
            : normalizePrescriptionText(item.frequency) || null,
        frequency_custom:
          normalizePrescriptionText(item.frequency) === "Autre..."
            ? normalizePrescriptionText(item.frequency_custom) || null
            : normalizePrescriptionText(item.frequency_custom) || null,
        duration: buildPrescriptionLegacyDuration(item) || normalizePrescriptionText(item.duration) || null,
        duration_value: normalizePrescriptionText(item.duration_value) || null,
        duration_unit: normalizePrescriptionText(item.duration_unit) || null,
        quantity: normalizePrescriptionText(item.number_of_boxes) || normalizePrescriptionText(item.quantity) || null,
        number_of_boxes: normalizePrescriptionText(item.number_of_boxes) || null,
        instructions: normalizePrescriptionText(item.instructions) || null,
        sort_order: index,
      })),
  });

  const handleSavePrescriptionDraft = () => {
    const run = async () => {
      if (isCreateMode || !workerId || !campaignId) {
        setNotice({
          type: "error",
          message: "Enregistrez d'abord le dossier du travailleur avant de creer une ordonnance.",
        });
        return;
      }
      if (!(prescriptionForm.medical_visit_id ?? resolvedActiveVisitId)) {
        setNotice({
          type: "error",
          message: "Aucune visite médicale active n'est disponible pour ce travailleur.",
        });
        return;
      }

      setPrescriptionSaving(true);
      try {
        const payload = buildPrescriptionPayload();
        const saved = prescriptionForm.id
          ? await prescriptionsApi.update(prescriptionForm.id, payload)
          : await prescriptionsApi.create(payload);
        await refreshPrescriptions(saved.id);
        setNotice({
          type: "success",
          message: "Le brouillon de l'ordonnance a ete enregistre.",
        });
      } catch {
        setNotice({
          type: "error",
          message: "Impossible d'enregistrer l'ordonnance pour le moment.",
        });
      } finally {
        setPrescriptionSaving(false);
      }
    };

    void run();
  };

  const handleSignPrescription = () => {
    const run = async () => {
      if (!prescriptionForm.id) {
        setNotice({
          type: "error",
          message: "Enregistrez d'abord le brouillon avant de signer l'ordonnance.",
        });
        return;
      }
      if (!canSignPrescription) {
        setNotice({
          type: "error",
          message: "Seuls les profils Doctor, Admin ou Super Admin peuvent signer une ordonnance.",
        });
        return;
      }
      const itemsToValidate = prescriptionForm.items.filter((item) => hasStructuredPrescriptionItemContent(item));
      if (!itemsToValidate.length || itemsToValidate.some((item) => !hasCompletePrescriptionItemForValidation(item))) {
        setNotice({
          type: "error",
          message: "Completez au moins un medicament avec dose, frequence et duree avant de valider l'ordonnance.",
        });
        return;
      }
      setPrescriptionSaving(true);
      try {
        const savedDraft = await prescriptionsApi.update(prescriptionForm.id, buildPrescriptionPayload());
        const signed = await prescriptionsApi.validate(savedDraft.id);
        await refreshPrescriptions(signed.id);
        setNotice({
          type: "success",
          message: "L'ordonnance a ete validee avec succes.",
        });
      } catch {
        setNotice({
          type: "error",
          message: "La validation de l'ordonnance a echoue.",
        });
      } finally {
        setPrescriptionSaving(false);
      }
    };

    void run();
  };

  const handleDownloadPrescriptionPdf = () => {
    const run = async () => {
      if (!prescriptionForm.id) {
        setNotice({
          type: "error",
          message: "Enregistrez d'abord l'ordonnance avant de generer son PDF.",
        });
        return;
      }
      setPrescriptionDownloading(true);
      try {
        const { blob, filename } = await prescriptionsApi.downloadPdf(prescriptionForm.id, {
          includeSignature: canSignMedicalDocuments && prescriptionForm.includeValidatorSignature,
        });
        const blobUrl = window.URL.createObjectURL(blob);
        const link = document.createElement("a");
        link.href = blobUrl;
        link.download = filename;
        document.body.appendChild(link);
        link.click();
        link.remove();
        window.URL.revokeObjectURL(blobUrl);
        setNotice({
          type: "success",
          message: "Le PDF de l'ordonnance a ete genere.",
        });
      } catch {
        setNotice({
          type: "error",
          message: "Impossible de generer le PDF de l'ordonnance pour le moment.",
        });
      } finally {
        setPrescriptionDownloading(false);
      }
    };

    void run();
  };

  const handleLoadPrescriptionPdfPreview = () => {
    const run = async () => {
      if (!prescriptionForm.id) {
        setNotice({
          type: "error",
          message: "Enregistrez d'abord l'ordonnance avant d'afficher son PDF.",
        });
        return;
      }
      setPrescriptionPreviewLoading(true);
      try {
        const blob = await prescriptionsApi.previewPdf(prescriptionForm.id, {
          includeSignature: canSignMedicalDocuments && prescriptionForm.includeValidatorSignature,
        });
        const nextUrl = window.URL.createObjectURL(blob);
        setPrescriptionPreviewUrl((current) => {
          if (current) {
            window.URL.revokeObjectURL(current);
          }
          return nextUrl;
        });
      } catch {
        setNotice({
          type: "error",
          message: "Impossible de charger l'aperçu PDF de l'ordonnance pour le moment.",
        });
      } finally {
        setPrescriptionPreviewLoading(false);
      }
    };

    void run();
  };

  const handleDuplicatePrescription = () => {
    const run = async () => {
      if (!prescriptionForm.id) {
        setNotice({
          type: "error",
          message: "Selectionnez d'abord une ordonnance a dupliquer.",
        });
        return;
      }

      setPrescriptionSaving(true);
      try {
        const duplicated = await prescriptionsApi.duplicate(prescriptionForm.id);
        await refreshPrescriptions(duplicated.id);
        setNotice({
          type: "success",
          message: "Une nouvelle ordonnance brouillon a ete creee a partir de l'originale.",
        });
      } catch {
        setNotice({
          type: "error",
          message: "Impossible de dupliquer l'ordonnance pour le moment.",
        });
      } finally {
        setPrescriptionSaving(false);
      }
    };

    void run();
  };

  const handleCancelPrescription = () => {
    const run = async () => {
      if (!prescriptionForm.id) {
        setNotice({
          type: "error",
          message: "Selectionnez d'abord une ordonnance a annuler.",
        });
        return;
      }

      setPrescriptionSaving(true);
      try {
        await prescriptionsApi.cancel(prescriptionForm.id);
        await refreshPrescriptions(prescriptionForm.id);
        setNotice({
          type: "success",
          message: "L'ordonnance a ete annulee.",
        });
      } catch {
        setNotice({
          type: "error",
          message: "Impossible d'annuler l'ordonnance.",
        });
      } finally {
        setPrescriptionSaving(false);
      }
    };

    void run();
  };

  const handlePrintPrescription = () => {
    const run = async () => {
      if (!prescriptionForm.id) {
        setNotice({
          type: "error",
          message: "Enregistrez d'abord l'ordonnance avant de l'imprimer.",
        });
        return;
      }
      setPrescriptionPrinting(true);
      try {
        await prescriptionsApi.markPrinted(prescriptionForm.id);
        const { blob } = await prescriptionsApi.downloadPdf(prescriptionForm.id, {
          includeSignature: canSignMedicalDocuments && prescriptionForm.includeValidatorSignature,
        });
        const blobUrl = window.URL.createObjectURL(blob);
        const frame = document.createElement("iframe");
        frame.style.position = "fixed";
        frame.style.width = "0";
        frame.style.height = "0";
        frame.style.border = "0";
        frame.src = blobUrl;
        document.body.appendChild(frame);
        frame.onload = () => {
          frame.contentWindow?.focus();
          frame.contentWindow?.print();
          window.setTimeout(() => {
            window.URL.revokeObjectURL(blobUrl);
            frame.remove();
          }, 1500);
        };
        await refreshPrescriptions(prescriptionForm.id);
        setNotice({
          type: "success",
          message: "L'ordonnance a ete preparee pour impression.",
        });
      } catch {
        setNotice({
          type: "error",
          message: "Impossible d'imprimer l'ordonnance pour le moment.",
        });
      } finally {
        setPrescriptionPrinting(false);
      }
    };

    void run();
  };
  

  const handleDeletePrescription = () => {
    const run = async () => {
      if (!prescriptionForm.id) {
        setPrescriptionForm(createEmptyPrescriptionForm(worker, doctorName));
        return;
      }
      setPrescriptionSaving(true);
      try {
        await prescriptionsApi.remove(prescriptionForm.id);
        await refreshPrescriptions();
        setNotice({
          type: "success",
          message: "L'ordonnance a ete supprimee.",
        });
      } catch {
        setNotice({
          type: "error",
          message: "Impossible de supprimer l'ordonnance.",
        });
      } finally {
        setPrescriptionSaving(false);
      }
    };

    void run();
  };

  // ─────────────────────────────────────────────────────────────
  //  ORIENTATION API-STYLE HANDLERS
  //  (mirrors prescriptionsApi pattern exactly)
  // ─────────────────────────────────────────────────────────────
  const fetchNextOrientationNumber = async (): Promise<string> => {
    try {
      const response = await orientationsApi.getLastOrientationCertificateId();
      
      const lastId = response.last_id ?? 0;
      const nextId = lastId + 1;
      return `ORI-${nextId.toString().padStart(4, '0')}`;
    } catch {
      return `ORI-${Date.now().toString().slice(-4)}`;
    }
  };

 const refreshOrientations = async (nextSelectedId?: number) => {
    if (isCreateMode || !workerId || !campaignId) return;

    const response = await orientationsApi.list({
      worker_id: Number(workerId),
      campaign_id: Number(campaignId),
      medical_visit_id: resolvedActiveVisitId ?? undefined,
    });

    // Extract items from paginated response
    const records = (response.items ?? response ?? [])
      .filter((item) => resolvedActiveVisitId == null || item.medical_visit_id === resolvedActiveVisitId)
      .map(normalizeOrientationCertificateForUi);

    setOrientations(records);

    const selected =
      (typeof nextSelectedId === "number"
        ? records.find((item) => item.id === nextSelectedId)
        : undefined) || records[0];

    setOrientationForm(
      selected
        ? mapOrientationToForm(selected, worker, doctorName)
        : createEmptyMedicalOrientationForm(worker, doctorName),
    );
  };

  const updateOrientationField = <K extends keyof MedicalOrientationFormState>(
    key: K,
    value: MedicalOrientationFormState[K],
  ) => {
    setOrientationForm((current) => ({ ...current, [key]: value }));
  };

  

  const handleCreateOrientationDraft = async () => {
    const nextNumber = await fetchNextOrientationNumber();
    setOrientationForm({
      ...createEmptyMedicalOrientationForm(worker, doctorName),
      medical_visit_id: resolvedActiveVisitId ?? null,
      orientation_number: nextNumber,
    });
    setOrientationPdfPreviewUrl(null);
  };

  const handleSelectOrientation = (orientation: OrientationCertificate) => {
    setOrientationForm(mapOrientationToForm(orientation, worker, doctorName));
  };

  const buildOrientationPayload = () => {
    const orientationType = orientationForm.orientationTypes.specialistAdvice
      ? "avis_specialise"
      : orientationForm.orientationTypes.diagnosticCare
        ? "prise_en_charge_diagnostic"
        : orientationForm.orientationTypes.other
          ? "autre"
          : "";
    const payload = {
      worker_id: Number(workerId),
      campaign_id: Number(campaignId),
      medical_visit_id: orientationForm.medical_visit_id ?? resolvedActiveVisitId ?? null,
      doctor_id: typeof user?.id === "number" ? user.id : null,
      orientation_number: orientationForm.orientation_number || undefined,
      orientation_date: orientationForm.orientation_date,
      worker_name: orientationForm.patient_name,
      orientation_type: orientationType,
      orientation_type_other: orientationForm.orientationTypes.other
        ? orientationForm.orientationTypeOther
        : null,
      orientation_types: orientationForm.orientationTypes,
      orientationTypes: orientationForm.orientationTypes,
      orientation_details: orientationForm.orientation_details,
      doctor_name: orientationForm.doctor_name,
      includeValidatorSignature: orientationForm.includeValidatorSignature,
      status: orientationForm.status,
    };
    
    
    return payload;
  };

  const handleSaveOrientationDraft = () => {
    const run = async () => {
      if (isCreateMode || !workerId || !campaignId) {
        setNotice({
          type: "error",
          message: "Enregistrez d'abord le dossier du travailleur avant de creer une orientation.",
        });
        return;
      }
      if (!(orientationForm.medical_visit_id ?? resolvedActiveVisitId)) {
        setNotice({
          type: "error",
          message: "Aucune visite médicale active n'est disponible pour ce travailleur.",
        });
        return;
      }

      setOrientationSaving(true);
      try {
        const payload = buildOrientationPayload();
        const saved = orientationForm.id
          ? await orientationsApi.update(orientationForm.id, payload)
          : await orientationsApi.create(payload);
        
        
        // CRITICAL: Update the form with the saved ID
        setOrientationForm((prev) => ({
          ...prev,
          id: saved.id,
          orientation_number: saved.orientation_number || prev.orientation_number,
          status: saved.status,
        }));
        
        await refreshOrientations(saved.id);
        setNotice({
          type: "success",
          message: "Le brouillon de l'orientation a ete enregistre.",
        });
      } catch {
        setNotice({
          type: "error",
          message: "Impossible d'enregistrer l'orientation pour le moment.",
        });
      } finally {
        setOrientationSaving(false);
      }
    };

    void run();
  };
  const canSignOrientation =
    orientationForm.orientation_number.trim() !== "" &&
    orientationForm.orientation_date !== "" &&
    orientationForm.patient_name.trim() !== "" &&
    orientationForm.doctor_name.trim() !== "" &&
    Object.values(orientationForm.orientationTypes).some(Boolean) &&
    (!orientationForm.orientationTypes.other || orientationForm.orientationTypeOther.trim() !== "") &&
    orientationForm.orientation_details.trim() !== "";

  const handleSignOrientation = () => {
    const run = async () => {
      if (!orientationForm.id) {
        setNotice({
          type: "error",
          message: "Enregistrez d'abord le brouillon avant de signer l'orientation.",
        });
        return;
      }
      if (!canSignOrientation) {
        setNotice({
          type: "error",
          message: "Veuillez remplir tous les champs obligatoires avant de signer.",
        });
        return;
      }
      if (!canSignMedicalDocuments) {
        setNotice({
          type: "error",
          message: signatureAuthorizationMessage,
        });
        return;
      }
      setOrientationSaving(true);
      try {
        const savedDraft = await orientationsApi.update(orientationForm.id, buildOrientationPayload());
        const signed = await orientationsApi.sign(savedDraft.id);
        await refreshOrientations(signed.id);
        setNotice({
          type: "success",
          message: "L'orientation a ete signee.",
        });
      } catch (error) {
        const message = await getApiErrorMessage(
          error,
          "La signature de l'orientation a echoue.",
        );
        if (import.meta.env.DEV) {
          const response = (
            error as {
              response?: {
                status?: number;
                data?: {
                  code?: string;
                  detail?: { code?: string };
                };
              };
            }
          )?.response;
          
        }
        setNotice({
          type: "error",
          message,
        });
      } finally {
        setOrientationSaving(false);
      }
    };

    void run();
  };

  

  
  const handlePrintOrientation = () => {
    const run = async () => {
      if (!orientationForm.id) {
        setNotice({
          type: "error",
          message: "Enregistrez d'abord l'orientation avant de l'imprimer.",
        });
        return;
      }
      setOrientationPrinting(true);
      try {
        await orientationsApi.markPrinted(orientationForm.id);
        const { blob } = await orientationsApi.downloadPdf(
          orientationForm.id,
          canSignMedicalDocuments && orientationForm.includeValidatorSignature,
        );
        const blobUrl = window.URL.createObjectURL(blob);
        const frame = document.createElement("iframe");
        frame.style.position = "fixed";
        frame.style.width = "0";
        frame.style.height = "0";
        frame.style.border = "0";
        frame.src = blobUrl;
        document.body.appendChild(frame);
        frame.onload = () => {
          frame.contentWindow?.focus();
          frame.contentWindow?.print();
          window.setTimeout(() => {
            window.URL.revokeObjectURL(blobUrl);
            frame.remove();
          }, 1500);
        };
        await refreshOrientations(orientationForm.id);
        setNotice({
          type: "success",
          message: "L'orientation a ete preparee pour impression.",
        });
      } catch {
        setNotice({
          type: "error",
          message: "Impossible d'imprimer l'orientation pour le moment.",
        });
      } finally {
        setOrientationPrinting(false);
      }
    };

    void run();
  };

  const handleDeleteOrientation = () => {
    const run = async () => {
      if (!orientationForm.id) {
        setOrientationForm(createEmptyMedicalOrientationForm(worker, doctorName));
        return;
      }
      setOrientationSaving(true);
      try {
        await orientationsApi.remove(orientationForm.id, { password: "" });
        await refreshOrientations();
        setNotice({
          type: "success",
          message: "L'orientation a ete supprimee.",
        });
      } catch {
        setNotice({
          type: "error",
          message: "Impossible de supprimer l'orientation.",
        });
      } finally {
        setOrientationSaving(false);
      }
    };

    void run();
  };

  const handleDownloadAptitudePdf = () => {
    const run = async () => {
      if (!activeAptitudeCertificateId || !aptitudeForm.medicalVisitId) {
        setNotice({
          type: "error",
          message: "Selectionnez un certificat d'aptitude avant de telecharger le PDF.",
        });
        return;
      }

      try {
        if (!isAptitudeValidated) {
          await aptitudeCertificatesApi.updateByVisit(aptitudeForm.medicalVisitId, buildAptitudePayload());
          await refreshAptitudeCertificate(aptitudeForm.medicalVisitId);
        }
        const { blob, filename } = await aptitudeCertificatesApi.downloadPdf(
          activeAptitudeCertificateId,
          { cacheBust: true },
        );
        downloadDocument(blob, filename);
      } catch {
        setNotice({
          type: "error",
          message: "Impossible de telecharger le certificat d'aptitude pour le moment.",
        });
      }
    };

    void run();
  };

  const handleLoadAptitudePdfPreview = () => {
    const run = async () => {
      if (!activeAptitudeCertificateId || !aptitudeForm.medicalVisitId) {
        setNotice({
          type: "error",
          message: "Selectionnez un certificat d'aptitude avant d'afficher son PDF.",
        });
        return;
      }

      setAptitudePdfPreviewLoading(true);
      try {
        if (!isAptitudeValidated) {
          await aptitudeCertificatesApi.updateByVisit(aptitudeForm.medicalVisitId, buildAptitudePayload());
          await refreshAptitudeCertificate(aptitudeForm.medicalVisitId);
        }
        const { blob } = await aptitudeCertificatesApi.downloadPdf(activeAptitudeCertificateId, {
          cacheBust: true,
        });
        const nextUrl = window.URL.createObjectURL(blob);
        setAptitudePdfPreviewUrl((current) => {
          if (current) {
            window.URL.revokeObjectURL(current);
          }
          return nextUrl;
        });
      } catch {
        setNotice({
          type: "error",
          message: "Impossible de charger l'aperçu PDF du certificat d'aptitude pour le moment.",
        });
      } finally {
        setAptitudePdfPreviewLoading(false);
      }
    };

    void run();
  };

  const handlePrintAptitudePdf = () => {
    const run = async () => {
      if (!activeAptitudeCertificateId || !aptitudeForm.medicalVisitId) {
        setNotice({
          type: "error",
          message: "Selectionnez un certificat d'aptitude avant de l'imprimer.",
        });
        return;
      }

      try {
        if (!isAptitudeValidated) {
          await aptitudeCertificatesApi.updateByVisit(aptitudeForm.medicalVisitId, buildAptitudePayload());
        }
        const { blob } = await aptitudeCertificatesApi.downloadPdf(activeAptitudeCertificateId, {
          cacheBust: true,
        });
        printBlob(blob);
      } catch {
        setNotice({
          type: "error",
          message: "Impossible d'imprimer le certificat d'aptitude pour le moment.",
        });
      }
    };

    void run();
  };

  const handleSaveAptitudeDraft = () => {
    const run = async () => {
      if (!aptitudeForm.medicalVisitId) {
        setNotice({
          type: "error",
          message: "Selectionnez une visite medicale avant d'enregistrer le certificat d'aptitude.",
        });
        return;
      }
      setAptitudeSaving(true);
      try {
        const nextStatus: MedicalAptitudeFormState["status"] = isAptitudeValidated
          ? "confirmed"
          : "draft";
        const saved = await aptitudeCertificatesApi.updateByVisit(aptitudeForm.medicalVisitId, {
          ...buildAptitudePayload(),
          includeValidatorSignature: isAptitudeValidated
            ? aptitudeForm.includeValidatorSignature
            : false,
          status: nextStatus,
        });
        setAptitudeCertificate(saved);
        const nextCertificate = {
          ...saved,
          status: nextStatus,
          includeValidatorSignature: isAptitudeValidated
            ? (saved.includeValidatorSignature ?? aptitudeForm.includeValidatorSignature)
            : false,
          validatorSignatureUrl: isAptitudeValidated
            ? (saved.validatorSignatureUrl ??
              saved.validator_signature_url ??
              aptitudeForm.validatorSignatureUrl ??
              null)
            : null,
          validatedDoctorName: isAptitudeValidated
            ? (saved.validatedDoctorName ??
              saved.validated_doctor_name ??
              aptitudeForm.validatedDoctorName)
            : "",
          validatedByUserId: isAptitudeValidated
            ? (saved.validatedByUserId ??
              saved.validated_by_user_id ??
              aptitudeForm.validatedByUserId ??
              null)
            : null,
          validatedAt: isAptitudeValidated
            ? (saved.validatedAt ??
              saved.validated_at ??
              aptitudeForm.validatedAt ??
              null)
            : null,
          validatorRole: isAptitudeValidated
            ? (saved.validatorRole ??
              saved.validator_role ??
              aptitudeForm.validatorRole ??
              null)
            : null,
        };
        setAptitudeForm(
          createEmptyMedicalAptitudeFormState(
            nextCertificate,
            worker,
            Number(campaignId),
            aptitudeForm.medicalVisitId,
            doctorName,
          ),
        );
        setIsEditingAptitudeCertificate(false);
        if (medicalVisit?.id === aptitudeForm.medicalVisitId) {
          setMedicalVisit((current) =>
            current
              ? {
                  ...current,
                  form_data: {
                    ...(parseMedicalVisitFormData(current.form_data) as Record<string, unknown> | null),
                    ...buildVisitFormData(form),
                    aptitudeCertificate: {
                      ...(nextCertificate as unknown as Record<string, unknown>),
                    },
                  },
                }
              : current,
          );
        }
        setNotice({
          type: "success",
          message: "Le brouillon du certificat d'aptitude a ete enregistre.",
        });
      } catch {
        setNotice({
          type: "error",
          message: "Impossible d'enregistrer le brouillon du certificat d'aptitude.",
        });
      } finally {
        setAptitudeSaving(false);
      }
    };

    void run();
  };

  const handleValidateAptitudeCertificate = () => {
    const run = async () => {
      if (!aptitudeForm.medicalVisitId) {
        setNotice({
          type: "error",
          message: "Selectionnez une visite medicale avant de valider le certificat d'aptitude.",
        });
        return;
      }
      if (!canSignMedicalDocuments) {
        setNotice({
          type: "error",
          message: signatureAuthorizationMessage,
        });
        return;
      }
      if (!currentUserSignatureUrl) {
        setNotice({
          type: "error",
          message: "Veuillez ajouter votre signature PNG dans les parametres avant de valider ce certificat.",
        });
        return;
      }
      
      
      setAptitudeSaving(true);
      try {
        const validated = await aptitudeCertificatesApi.validateByVisit(aptitudeForm.medicalVisitId, {
          ...buildAptitudePayload("validate"),
        });
        
        const currentValidator = buildCurrentAptitudeValidator();
        const fallbackValidated = (() => {
          
          const rawValidatedByUserId =
            (validated as unknown as Record<string, unknown>).validatedByUserId ??
            (validated as unknown as Record<string, unknown>).validated_by_user_id ??
            (validated as unknown as Record<string, unknown>).validatorId ??
            null;
          const normalizedValidatedByUserId =
            typeof rawValidatedByUserId === "number"
              ? rawValidatedByUserId
              : typeof rawValidatedByUserId === "string" && rawValidatedByUserId.trim()
                ? Number(rawValidatedByUserId)
                : null;
          const hasValidatorName =
            Boolean(validated.validatedDoctorName) ||
            Boolean((validated as unknown as Record<string, unknown>).validated_doctor_name) ||
            Boolean(validated.validatorName) ||
            Boolean((validated as unknown as Record<string, unknown>).validator_name) ||
            Boolean(validated.doctor_name);
          const hasValidatedAt =
            Boolean(validated.validatedAt) ||
            Boolean((validated as unknown as Record<string, unknown>).validated_at);
          const hasValidatorId = Boolean(normalizedValidatedByUserId);
          const temporaryValidatorName =
            user?.full_name ||
            `${user?.first_name || ""} ${user?.last_name || ""}`.trim() ||
            "";

          return {
            ...validated,
            status: "confirmed" as const,
            includeValidatorSignature: true,
            validatedDoctorName:
              validated.validatedDoctorName ||
              ((validated as unknown as Record<string, unknown>).validated_doctor_name as string | undefined) ||
              currentValidator.validatedDoctorName ||
              (hasValidatorName ? undefined : temporaryValidatorName),
            validatorSignatureUrl:
              validated.validatorSignatureUrl ||
              ((validated as unknown as Record<string, unknown>).validator_signature_url as string | undefined) ||
              currentValidator.validatorSignatureUrl ||
              (hasValidatorName || hasValidatedAt || hasValidatorId ? undefined : currentUserSignatureUrl || null),
            validatedAt:
              validated.validatedAt ||
              ((validated as unknown as Record<string, unknown>).validated_at as string | undefined) ||
              currentValidator.validatedAt ||
              (hasValidatedAt ? undefined : new Date().toISOString()),
            validatedByUserId:
              normalizedValidatedByUserId ??
              currentValidator.validatedDoctorId ??
              (hasValidatorId ? null : user?.id ?? null),
            validatorRole:
              validated.validatorRole ||
              ((validated as unknown as Record<string, unknown>).validator_role as string | undefined) ||
              currentValidator.validatedDoctorRole ||
              (hasValidatorName || hasValidatedAt || hasValidatorId ? undefined : user?.role || null),
          };
        })();
        
        setAptitudeCertificate(fallbackValidated);
        const nextAptitudeForm = createEmptyMedicalAptitudeFormState(
          fallbackValidated,
          worker,
          Number(campaignId),
          aptitudeForm.medicalVisitId,
          doctorName,
        );
        setAptitudeForm({
          ...nextAptitudeForm,
          validatedDoctorName:
            currentValidator.validatedDoctorName || nextAptitudeForm.validatedDoctorName,
        });
        try {
          await refreshAptitudeCertificate(aptitudeForm.medicalVisitId);
        } catch {
          // Keep the optimistic validated state if the follow-up refresh fails.
        }
        setNotice({
          type: "success",
          message: "Le certificat d'aptitude a ete valide.",
        });
      } catch {
        setNotice({
          type: "error",
          message: "La validation du certificat d'aptitude a echoue.",
        });
      } finally {
        setAptitudeSaving(false);
      }
    };

    void run();
  };

  const handleDeleteAptitudeCertificate = () => {
    const run = async () => {
      if (!aptitudeForm.medicalVisitId) {
        setNotice({
          type: "error",
          message: "Selectionnez une visite medicale avant de supprimer le certificat d'aptitude.",
        });
        return;
      }
      if (!canSignMedicalDocuments) {
        setNotice({
          type: "error",
          message: signatureAuthorizationMessage,
        });
        return;
      }
      setAptitudeSaving(true);
      try {
        await aptitudeCertificatesApi.deleteByVisit(aptitudeForm.medicalVisitId);
        await refreshAptitudeCertificate(aptitudeForm.medicalVisitId);
        setNotice({
          type: "success",
          message: "Le certificat d'aptitude a ete supprime.",
        });
      } catch {
        setNotice({
          type: "error",
          message: "Impossible de supprimer le certificat d'aptitude.",
        });
      } finally {
        setAptitudeSaving(false);
      }
    };

    void run();
  };
 
  const handleDownloadMedicalVisitPdf = () => {
    const run = async () => {
      if (isCreateMode || !workerId || !selectedQuickVisitId) {
        setNotice({
          type: "error",
          message: "Selectionnez une visite avant de telecharger son PDF.",
        });
        return;
      }

      setPdfDownloading(true);
      try {
        const { blob, filename } = await workersApi.downloadMedicalVisitPdf(
          workerId,
          workerVisits.find((visit) => visit.id === selectedQuickVisitId)?.campaign_id ||
            currentWorkspace?.campaign_id ||
            campaignId,
          selectedQuickVisitId,
        );
        downloadDocument(blob, filename);
        setNotice({
          type: "success",
          message: "Le PDF Fich intern de visit Medicale a ete genere depuis la base.",
        });
      } catch {
        setNotice({
          type: "error",
          message: "Impossible de generer le PDF. Verifiez le modele PDF et le mapping des coordonnees dans le backend.",
        });
      } finally {
        setPdfDownloading(false);
      }
    };

    void run();
  };

  const handleLoadPdfPreview = () => {
    const run = async () => {
      if (isCreateMode || !workerId || !selectedQuickVisitId) {
        setNotice({
          type: "error",
          message: "Selectionnez une visite avant d'afficher le PDF.",
        });
        return;
      }

      setPdfPreviewLoading(true);
      try {
        const { blob } = await workersApi.downloadMedicalVisitPdf(
          workerId,
          currentWorkspace?.campaign_id || campaignId,
          selectedQuickVisitId,
        );
        const nextUrl = window.URL.createObjectURL(blob);
        setPdfPreviewUrl((current) => {
          if (current) {
            window.URL.revokeObjectURL(current);
          }
          return nextUrl;
        });
      } catch {
        setNotice({
          type: "error",
          message: "Impossible de charger l'aperçu PDF pour le moment.",
        });
      } finally {
        setPdfPreviewLoading(false);
      }
    };

    void run();
  };

  const handleLoadOrientationPdfPreview = () => {
    const run = async () => {
      if (!orientationForm.id) {
        setNotice({
          type: "error",
          message: "Enregistrez d'abord l'orientation avant d'afficher son PDF.",
        });
        return;
      }

      setOrientationPdfPreviewLoading(true);
      try {
        const { blob } = await orientationsApi.downloadPdf(
          orientationForm.id,
          orientationForm.includeValidatorSignature,
        );
        const nextUrl = window.URL.createObjectURL(blob);
        setOrientationPdfPreviewUrl((current) => {
          if (current) {
            window.URL.revokeObjectURL(current);
          }
          return nextUrl;
        });
      } catch {
        setNotice({
          type: "error",
          message: "Impossible de charger l'aperçu PDF de l'orientation pour le moment.",
        });
      } finally {
        setOrientationPdfPreviewLoading(false);
      }
    };

    void run();
  };
  const handleDownloadOrientationPdf = () => {
    const run = async () => {
      if (isCreateMode || !workerId) {
        setNotice({
          type: "error",
          message:
            "Enregistrez d'abord le dossier du travailleur en base avant de télécharger le PDF.",
        });
        return;
      }

      setOrientationPdfDownloading(true);

      try {
        const { blob, filename } = await orientationsApi.downloadPdf(
          orientationForm.id!,
          canSignMedicalDocuments && orientationForm.includeValidatorSignature,
        );

        downloadDocument(blob, filename || `orientation-medicale-${workerId}.pdf`);
      } catch {
        setNotice({
          type: "error",
          message:
            "Impossible de télécharger le PDF d'orientation pour le moment.",
        });
      } finally {
        setOrientationPdfDownloading(false);
      }
    };

    void run();
  };

  const handleDownloadMedicalDossierPdf = () => {
    const run = async () => {
      if (isCreateMode || !workerId) {
        setNotice({
          type: "error",
          message: "Enregistrez d'abord le dossier du travailleur en base avant de telecharger le PDF dossier.",
        });
        return;
      }

      setDossierPdfDownloading(true);
      try {
        const { blob, filename } = await workersApi.downloadMedicalDossierPdf(
          workerId,
          currentWorkspace?.campaign_id || campaignId,
        );
        downloadDocument(blob, filename);
        setNotice({
          type: "success",
          message: "Le PDF Dossier medical a ete genere depuis la base.",
        });
      } catch {
        setNotice({
          type: "error",
          message: "Impossible de generer le PDF Dossier medical pour le moment.",
        });
      } finally {
        setDossierPdfDownloading(false);
      }
    };

    void run();
  };

  const handlePrintMedicalVisitPdf = () => {
    const run = async () => {
      if (isCreateMode || !workerId || !selectedQuickVisitId) {
        setNotice({
          type: "error",
          message: "Selectionnez une visite avant de l'imprimer.",
        });
        return;
      }

      setPdfDownloading(true);
      try {
        const { blob } = await workersApi.downloadMedicalVisitPdf(
          workerId,
          workerVisits.find((visit) => visit.id === selectedQuickVisitId)?.campaign_id ||
            currentWorkspace?.campaign_id ||
            campaignId,
          selectedQuickVisitId,
        );
        openPdfBlob(blob);
      } catch {
        setNotice({
          type: "error",
          message: "Impossible d'imprimer la visite medicale pour le moment.",
        });
      } finally {
        setPdfDownloading(false);
      }
    };

    void run();
  };

  const handlePrintMedicalDossierPdf = () => {
    const run = async () => {
      if (isCreateMode || !workerId) {
        setNotice({
          type: "error",
          message: "Enregistrez d'abord le dossier du travailleur en base avant de l'imprimer.",
        });
        return;
      }

      setDossierPdfDownloading(true);
      try {
        const { blob } = await workersApi.downloadMedicalDossierPdf(
          workerId,
          currentWorkspace?.campaign_id || campaignId,
        );
        openPdfBlob(blob);
      } catch {
        setNotice({
          type: "error",
          message: "Impossible d'imprimer le dossier medical pour le moment.",
        });
      } finally {
        setDossierPdfDownloading(false);
      }
    };

    void run();
  };

  

  const handleLoadDossierPdfPreview = () => {
    const run = async () => {
      if (isCreateMode || !workerId) {
        setNotice({
          type: "error",
          message: "Enregistrez d'abord le dossier du travailleur en base avant d'afficher le PDF dossier.",
        });
        return;
      }

      setDossierPdfPreviewLoading(true);
      try {
        const { blob } = await workersApi.downloadMedicalDossierPdf(
          workerId,
          currentWorkspace?.campaign_id || campaignId,
        );
        const nextUrl = window.URL.createObjectURL(blob);
        setDossierPdfPreviewUrl((current) => {
          if (current) {
            window.URL.revokeObjectURL(current);
          }
          return nextUrl;
        });
      } catch {
        setNotice({
          type: "error",
          message: "Impossible de charger l'aperçu PDF Dossier medical pour le moment.",
        });
      } finally {
        setDossierPdfPreviewLoading(false);
      }
    };

    void run();
  };

  const missingFields = useMemo(() => {
    const candidates = [
      !form.nationalId.trim() ? "Numero d'identite nationale" : null,
      !form.phone.trim() ? "Telephone" : null,
      !form.position.trim() ? "Poste" : null,
      !form.internalVisitDate.trim() ? "Date de visite" : null,
      !form.internalVisitDoctor.trim() ? "Medecin" : null,
      !form.clinicalExam.cardiovascular.bloodPressure.trim() ? "Examen clinique / TA" : null,
      !form.complementaryExams.biology.glycemia.trim() ? "Examens complementaires / Glycemie" : null,
      !form.medicalDecision.aptitude.trim() ? "Decision medicale / Aptitude" : null,
      !form.medicalDecision.validation.validatingDoctor.trim()
        ? "Decision medicale / Medecin validateur"
        : null,
    ];
    return candidates.filter(Boolean) as string[];
  }, [form]);

  const medicalAlerts = useMemo(() => {
    const alerts = [];
    if (form.medicalDecision.aptitude === "temporarily_unfit") {
      alerts.push("Aptitude signalee comme inapte temporaire.");
    }
    if (form.medicalDecision.aptitude === "definitively_unfit") {
      alerts.push("Aptitude signalee comme inapte definitive.");
    }
    if (form.internalVisitTa.trim()) {
      alerts.push(`TA renseignee: ${form.internalVisitTa}.`);
    }
    if (form.clinicalExam.respiratory.asthma.trim()) {
      alerts.push(`Respiratoire / Asthme: ${form.clinicalExam.respiratory.asthma}.`);
    }
    return alerts.slice(0, 4);
  }, [form]);

  const isFilled = (value: unknown) => String(value || "").trim().length > 0;

  const getCompletedCount = (values: unknown[]) => values.filter(isFilled).length;

  const renderCompletionBadge = (filled: number, total: number) => {
    if (filled <= 0) return null;

    return (
      <span className="ml-2 inline-flex items-center gap-1 rounded-full bg-emerald-50 px-2 py-0.5 text-[11px] font-bold text-emerald-700 ring-1 ring-emerald-200">
        <CheckCircle2 className="h-3 w-3" />
        {filled}/{total} Complété
      </span>
    );
  };

  const renderTestTitle = (title: string, values: unknown[], icon: ReactNode) => {
    const filled = getCompletedCount(values);

    return (
      <span className="inline-flex flex-wrap items-center gap-2">
        <span className="flex h-7 w-7 items-center justify-center rounded-lg border border-slate-200 bg-slate-100 text-slate-600">
          {icon}
        </span>
        <span className="font-semibold text-slate-800">{title}</span>
        {renderCompletionBadge(filled, values.length)}
      </span>
    );
  };

  const downloadDocument = (blob: Blob, filename: string) => {
    const blobUrl = window.URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = blobUrl;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.URL.revokeObjectURL(blobUrl);
  };

  const renderDocumentCollection = ({
    title,
    items,
    selectedId,
    onSelect,
    emptyMessage,
    generateAction,
    downloadAction,
    editAction,
    printAction,
    generateLabel,
  }: {
    title: string;
    items: WorkerDocumentItem[];
    selectedId: number | null;
    onSelect: (id: number | null) => void;
    emptyMessage: string;
    generateAction: () => void;
    downloadAction: () => void;
    editAction: () => void;
    printAction: () => void;
    generateLabel: string;
  }) => {
    const hasItems = items.length > 0;
    const selected = items.find((item) => item.id === selectedId) || null;
    const options = [
      { value: "", label: hasItems ? `Sélectionner ${title.toLowerCase()}` : emptyMessage },
      ...items.map((item) => {
        const statusLabel = item.status ? item.status : "";
        const label = [formatDisplayDate(item.date), item.doctor ? `Dr ${item.doctor}` : "", statusLabel]
          .filter(Boolean)
          .join(" - ");
        return { value: String(item.id), label: label || item.title || `#${item.id}` };
      }),
    ];

    return (
      <div className="grid gap-3">
        {hasItems ? (
          <Select
            label={title}
            value={selectedId ?? ""}
            onChange={(event) => onSelect(event.target.value ? Number(event.target.value) : null)}
            options={options}
          />
        ) : (
          <div className="rounded-2xl border border-dashed border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-500">
            {emptyMessage}
          </div>
        )}

        <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
          <Button variant="secondary" size="sm" icon={Plus} onClick={generateAction}>
            {generateLabel}
          </Button>
          <Button variant="secondary" size="sm" icon={FileDown} onClick={downloadAction} disabled={!selected}>
            Télécharger PDF
          </Button>
          <Button variant="secondary" size="sm" icon={Pencil} onClick={editAction} disabled={!selected}>
            Modifier
          </Button>
          <Button variant="secondary" size="sm" icon={Printer} onClick={printAction} disabled={!selected}>
            Imprimer
          </Button>
        </div>
      </div>
    );
  };

  const openPdfBlob = (blob: Blob) => {
    const blobUrl = window.URL.createObjectURL(blob);
    const frame = document.createElement("iframe");
    frame.style.position = "fixed";
    frame.style.width = "0";
    frame.style.height = "0";
    frame.style.border = "0";
    frame.src = blobUrl;
    document.body.appendChild(frame);
    frame.onload = () => {
      frame.contentWindow?.focus();
      frame.contentWindow?.print();
      window.setTimeout(() => {
        window.URL.revokeObjectURL(blobUrl);
        frame.remove();
      }, 1500);
    };
  };
  const printBlob = (blob: Blob) => {
    const blobUrl = window.URL.createObjectURL(blob);
    const printWindow = window.open(blobUrl, "_blank", "noopener,noreferrer");
    if (!printWindow) {
      window.URL.revokeObjectURL(blobUrl);
      return;
    }
    printWindow.onload = () => {
      printWindow.focus();
      printWindow.print();
      window.setTimeout(() => window.URL.revokeObjectURL(blobUrl), 1500);
    };
  };

  const shouldShowCampaignMedicalTest = (key: string) =>
    currentCampaignTestKeys.has(key);

  const getCampaignMedicalTestTitle = (key: string, fallbackTitle: string) => {
    const matchedAssignment = campaignTests.find((assignment) =>
      campaignMedicalTestDescriptors.some(
        (descriptor) => descriptor.key === key && descriptor.match(assignment),
      ),
    );

    return matchedAssignment?.name?.trim() || matchedAssignment?.test?.name?.trim() || fallbackTitle;
  };

  const shouldShowCampaignMedicalSection = (
    sectionId: "internalVisit" | "clinicalExam" | "complementaryExams",
  ) => currentCampaignSectionIds.has(sectionId);

  const updateDynamicMedicalTestValue = (
    testId: number,
    fieldName: string,
    value: string | boolean,
  ) => {
    
    setDynamicMedicalTestValues((current) => ({
      ...current,
      [String(testId)]: {
        testId,
        testName: current[String(testId)]?.testName || "",
        values: {
          ...(current[String(testId)]?.values || {}),
          [fieldName]: value,
        },
      },
    }));
  };

  const renderDynamicMedicalTestField = (
    testId: number,
    field: DynamicMedicalTestField,
    value: string | boolean,
  ) => {
    const labelClassName = cn(
      "text-sm font-semibold text-slate-700",
      field.labelClassName,
    );
    const wrapperClassName = cn("space-y-2", field.wrapperClassName);
    const inputClassName = cn(
      "rounded-xl border border-slate-300 bg-slate-50 focus:border-brand-500",
      field.type === "textarea" &&
        "min-h-32 w-full rounded-xl border border-slate-300 bg-slate-50 px-4 py-3 focus:border-brand-500",
      field.inputClassName,
    );

    if (field.type === "textarea") {
      return (
        <div className={wrapperClassName}>
          <span className={labelClassName}>{field.label}</span>
          <textarea
            rows={field.rows || 4}
            disabled={field.disabled}
            value={String(value ?? "")}
            placeholder={field.placeholder}
            onChange={(event) => updateDynamicMedicalTestValue(testId, field.name, event.target.value)}
            className={inputClassName}
          />
        </div>
      );
    }

    if (field.type === "checkbox") {
      return (
        <label className={wrapperClassName}>
          <span className={labelClassName}>{field.label}</span>
          <div className="flex items-center gap-3 rounded-xl border border-slate-300 bg-slate-50 px-4 py-3">
            <input
              type="checkbox"
              checked={Boolean(value)}
              disabled={field.disabled}
              onChange={(event) =>
                updateDynamicMedicalTestValue(testId, field.name, event.target.checked)
              }
              className="h-4 w-4 rounded border-slate-300 text-brand-600 focus:ring-brand-500"
            />
            <span className="text-sm text-slate-600">{field.placeholder || "Activer"}</span>
          </div>
        </label>
      );
    }

    if (field.type === "select") {
      return (
        <div className={wrapperClassName}>
          <span className={labelClassName}>{field.label}</span>
          <Select
            label=""
            options={(field.options || []).map((option) => ({ label: option.label, value: option.value }))}
            value={String(value ?? "")}
            disabled={field.disabled}
            onChange={(event) => updateDynamicMedicalTestValue(testId, field.name, event.target.value)}
            className={inputClassName}
          />
        </div>
      );
    }

    if (field.type === "radio") {
      return (
        <div className={wrapperClassName}>
          <span className={labelClassName}>{field.label}</span>
          <div className="space-y-2">
            {(field.options || []).map((option) => (
              <label
                key={option.value}
                className="flex items-center gap-3 rounded-xl border border-slate-300 bg-slate-50 px-4 py-3"
              >
                <input
                  type="radio"
                  name={`${testId}-${field.name}`}
                  checked={String(value ?? "") === option.value}
                  disabled={field.disabled}
                  onChange={() => updateDynamicMedicalTestValue(testId, field.name, option.value)}
                  className="h-4 w-4 border-slate-300 text-brand-600 focus:ring-brand-500"
                />
                <span className="text-sm text-slate-600">{option.label}</span>
              </label>
            ))}
          </div>
        </div>
      );
    }

    return (
      <div className={wrapperClassName}>
        <span className={labelClassName}>{field.label}</span>
        <Input
          type={field.type === "number" ? "number" : field.type === "date" ? "date" : "text"}
          disabled={field.disabled}
          value={String(value ?? "")}
          placeholder={field.placeholder}
          onChange={(event) => updateDynamicMedicalTestValue(testId, field.name, event.target.value)}
          className={inputClassName}
        />
      </div>
    );
  };

  const renderDynamicMedicalTestCard = (
    assignment: CampaignTestAssignment,
    sectionId: CampaignMedicalSectionId,
  ) => {
    const config = parseDynamicMedicalTestConfig(
      getDynamicMedicalTestConfigSource(assignment),
    );

    const testId = assignment.test_id;
    const testName = getDynamicMedicalTestName(assignment);
    const values = dynamicMedicalTestValues[String(testId)]?.values || {};

    if (!config) {
      return (
        <MedicalSubsection
          key={`dynamic-invalid-${testId}`}
          title={testName}
          description="Configuration JSON invalide."
          isCollapsible
        >
          <div className="rounded-2xl border border-amber-200 bg-amber-50/80 px-4 py-4 text-sm font-medium text-amber-800">
            Configuration invalide
          </div>
        </MedicalSubsection>
      );
    }

    return (
     
      <MedicalSubsection
        key={`dynamic-${sectionId}-${testId}`}
        title={testName}
        description="Examen médical dynamique"
        isCollapsible
      >
        <div
          className="grid gap-4"
          style={{
            gridTemplateColumns: `repeat(${config.layout?.columns || 2}, minmax(0, 1fr))`,
          }}
        >
          {config.fields?.map((field) => {
            const columns = config.layout?.columns || 2;
            const span = Math.max(1, Math.min(columns, field.colSpan || 1));
            const fieldValue = values[field.name];
            

            return (
              <div
                key={`${testId}-${field.name}`}
                style={{ gridColumn: `span ${span} / span ${span}` }}
              >
                {renderDynamicMedicalTestField(
                  testId,
                  field,
                  typeof fieldValue === "string" || typeof fieldValue === "boolean" ? fieldValue : "",
                )}
              </div>
            );
          })}
        </div>
      </MedicalSubsection>
      
    );
  };

  const lastNameSuggestions = [
    worker?.last_name,
    "Ouahbi",
    "Benali",
    "Bouzid",
    "Belkacem",
    "Saadi",
    "Mekki",
    "Khaldi",
  ].filter(Boolean) as string[];

  const firstNameSuggestions = [
    worker?.first_name,
    "Mohammed",
    "Ahmed",
    "Islam",
    "Yacine",
    "Amine",
    "Nassim",
    "Sofiane",
  ].filter(Boolean) as string[];

  const originAddressSuggestions = [
    "Ouargla, Algeria",
    "Hassi Messaoud, Ouargla",
    "Touggourt, Algeria",
    "Ghardaia, Algeria",
    "Biskra, Algeria",
    "Algiers, Algeria",
  ];

  const professionalAddressSuggestions = [
    currentCampaign?.company_name
      ? `${currentCampaign.company_name} - ${currentCampaign.site_name || currentCampaign.branch_name}`
      : "",
    currentCampaign?.site_name || "",
    currentCampaign?.branch_name || "",
    "Hassi Messaoud Base",
    "In Amenas Site Clinic",
    "Hassi RMel Operations",
  ].filter(Boolean) as string[];

  const positionSuggestions = Array.from(
    new Set([worker?.position, ...JOB_TITLES].filter(Boolean)),
  ) as string[];

  const departmentSuggestions = [
    "Operations",
    "Medical",
    "HSE",
    "Logistics",
    "Maintenance",
    "Administration",
  ];

  const serviceSuggestions = [
    "Occupational Health",
    "Emergency Response",
    "Field Operations",
    "Laboratory",
    "Clinical Screening",
    "Preventive Medicine",
  ];

  const workshopSuggestions = [
    "Rig Floor",
    "Mechanical Workshop",
    "Electrical Workshop",
    "Site Clinic",
    "Mud Logging Unit",
    "Support Base",
  ];

  const medicalAutocompleteSuggestions = useMemo(() => {
    const drafts = getStoredMedicalFileDrafts();
    const forms = [...drafts, form];

    return {
      schoolEducation: collectUniqueSuggestions(forms.map((item) => item.schoolEducation)),
      professionalTraining: collectUniqueSuggestions(forms.map((item) => item.professionalTraining)),
      professionalQualification: collectUniqueSuggestions(
        forms.map((item) => item.professionalQualification),
      ),
      nationalServiceNotes: collectUniqueSuggestions(forms.map((item) => item.nationalServiceNotes)),
      congenitalDiseases: collectUniqueSuggestions(forms.map((item) => item.congenitalDiseases)),
      generalDiseases: collectUniqueSuggestions(forms.map((item) => item.generalDiseases)),
      surgicalInterventions: collectUniqueSuggestions(forms.map((item) => item.surgicalInterventions)),
      accidents: collectUniqueSuggestions(forms.map((item) => item.accidents)),
      intoxications: collectUniqueSuggestions(forms.map((item) => item.intoxications)),
      tobacco: collectUniqueSuggestions(forms.map((item) => item.tobacco)),
      chewingTobacco: collectUniqueSuggestions(forms.map((item) => item.chewingTobacco)),
      alcoholism: collectUniqueSuggestions(forms.map((item) => item.alcoholism)),
      otherIntoxications: collectUniqueSuggestions(forms.map((item) => item.otherIntoxications)),
      professionalDiseaseNotes: collectUniqueSuggestions(
        forms.map((item) => item.professionalDiseaseNotes),
      ),
      occupiedPosition: collectUniqueSuggestions(
        forms.flatMap((item) => item.professionalHistory?.map((row) => row.occupiedPosition) || []),
      ),
      workplaceAndRisks: collectUniqueSuggestions(
        forms.flatMap(
          (item) => item.professionalHistory?.map((row) => row.workplaceAndRisks) || [],
        ),
      ),
      vaccineName: collectUniqueSuggestions(
        forms.flatMap((item) => item.vaccinations?.map((row) => row.vaccineName) || []),
      ),
    };
  }, [form]);

  const renderSectionContent = (sectionId: TabId) => {
    if (visitWorkflowSectionIds.has(sectionId) && !hasSelectedVisit) {
      return (
        <div className="space-y-5">
          <EmptyState
            title="No medical visit selected"
            description="Select an existing medical visit from the history above or create a new visit to begin the examination workflow."
            actionLabel="Create New Visit"
            onAction={() => {
              void handleCreateNewVisit();
            }}
          />
        </div>
      );
    }

    if (sectionId === "personal") {
      return (
        <div className="space-y-5">
          <MedicalSectionCard
            icon={UserRound}
            title="Identite du travailleur"
            description="Renseignez les informations d'etat civil, de contact et d'affectation administrative."
          >
            <div className="grid gap-4 grid-cols-1 md:grid-cols-3">
              <Input
                label="Numero de dossier medical"
                value={form.medicalFileNumber}
                error={errors.medicalFileNumber || null}
                readOnly
                className="cursor-not-allowed bg-slate-100/90 text-slate-500"
              />
              <Input
                label="Matricule"
                value={form.employeeCode}
                onChange={(event) => {
                  const nextCode = event.target.value;

                  setForm((current) => ({
                    ...current,
                    employeeCode: nextCode,
                  }));
                }}
              />
              <Input
                label="Numero d'identite nationale"
                type="text"
                inputMode="numeric"
                pattern="\d{18}"
                maxLength={18}
                value={form.nationalId}
                error={errors.nationalId || null}
                onChange={(event) =>
                  updateField("nationalId", event.target.value.replace(/\D/g, "").slice(0, 18))
                }
              />
              <Input
                label="Nom"
                value={form.lastName.toUpperCase()}
                error={errors.lastName || null}
                list="worker-last-name-suggestions"
                onChange={(event) => updateField("lastName", event.target.value.toUpperCase())}
              />
              <Input
                label="Prenom"
                value={form.firstName.toUpperCase()}
                error={errors.firstName || null}
                list="worker-first-name-suggestions"
                onChange={(event) => updateField("firstName", event.target.value.toUpperCase())}
              />
              <Select
                label="État actuel"
                options={WORKER_ETAT_ACTUAL_OPTIONS}
                value={form.etat_actual}
                onChange={(event) =>
                  updateField("etat_actual", event.target.value as Worker["etat_actual"])
                }
              />
              {isCreateMode ? (
                <div className="col-span-full">
                  {duplicateCheckLoading ? (
                    <p className="text-sm font-semibold text-sky-700">La présence du travailleur est en cours de vérification... </p>
                  ) : duplicateWorker ? (
                    <p className="text-sm font-semibold text-amber-700">
               Ce travailleur est déjà inscrit ; son dossier médical sera ouvert.                    </p>
                  ) : duplicateCheckError ? (
                    <p className="text-sm font-semibold text-amber-700">{duplicateCheckError}</p>
                  ) : form.firstName.trim() && form.lastName.trim() && form.dateOfBirth.trim() && form.nationalId.trim() ? (
                    <p className="text-sm font-semibold text-emerald-700">Ce travailleur est nouveau ; vous pouvez continuer l'enregistrement.</p>
                  ) : null}
                </div>
              ) : null}
              <Select
                label="Sexe"
                options={[
                  { label: "Selectionner", value: "" },
                  { label: "Masculin", value: "Masculin" },
                  { label: "Feminin", value: "Feminin" },
                ]}
                value={form.sex}
                error={errors.sex || null}
                onChange={(event) => updateField("sex", event.target.value)}
              />
              <Input
                label="Date de naissance"
                type="date"
                value={form.dateOfBirth}
                error={errors.dateOfBirth || null}
                onChange={(event) => updateField("dateOfBirth", event.target.value)}
              />
              <Input
                label="Lieu de naissance"
                value={form.birthPlace}
                list="worker-birth-place-suggestions"
                onChange={(event) => updateField("birthPlace", event.target.value)}
              />
              <PhoneInput
                label="Telephone"
                value={form.phone}
                error={errors.phone || null}
                onChange={(value) => updateField("phone", value)}
              />
              <Select
                label="Situation familiale"
                options={[
                  { label: "Selectionner", value: "" },
                  { label: "Celibataire", value: "single" },
                  { label: "Marie(e)", value: "married" },
                  { label: "Divorce(e)", value: "divorced" },
                  { label: "Veuf / Veuve", value: "widowed" },
                ]}
                value={form.familySituation}
                onChange={(event) => updateField("familySituation", event.target.value)}
              />
              <Input
                label="Adresse d'origine"
                value={form.originAddress}
                list="worker-origin-address-suggestions"
                onChange={(event) => updateField("originAddress", event.target.value)}
              />
              <Input
                label="Adresse professionnelle"
                value={form.professionalAddress}
                list="worker-professional-address-suggestions"
                onChange={(event) => updateField("professionalAddress", event.target.value)}
              />
              <Input
                label="Direction"
                value={form.direction}
                onChange={(event) => updateField("direction", event.target.value)}
              />
              <Input
                label="Poste"
                value={form.position}
                list="worker-position-suggestions"
                onChange={(event) => updateField("position", event.target.value)}
              />
              <Input
                label="Departement"
                value={form.department}
                list="worker-department-suggestions"
                onChange={(event) => updateField("department", event.target.value)}
              />
              <Input
                label="Service"
                value={form.service}
                list="worker-service-suggestions"
                onChange={(event) => updateField("service", event.target.value)}
              />
              <Input
                label="Entreprise"
                value={form.companyName}
                error={errors.companyName || null}
                readOnly
                className="cursor-not-allowed bg-slate-100/90 text-slate-500"
              />
              <Input
                label="Site"
                value={form.siteName}
                error={errors.siteName || null}
                readOnly
                className="cursor-not-allowed bg-slate-100/90 text-slate-500"
              />
            </div>
            <datalist id="worker-last-name-suggestions">
              {lastNameSuggestions.map((value) => (
                <option key={value} value={value} />
              ))}
            </datalist>
            <datalist id="worker-first-name-suggestions">
              {firstNameSuggestions.map((value) => (
                <option key={value} value={value} />
              ))}
            </datalist>
            <datalist id="worker-birth-place-suggestions">
              {algeriaWilayas.map((value) => (
                <option key={value} value={value} />
              ))}
            </datalist>
            <datalist id="worker-origin-address-suggestions">
              {originAddressSuggestions.map((value) => (
                <option key={value} value={value} />
              ))}
            </datalist>
            <datalist id="worker-professional-address-suggestions">
              {professionalAddressSuggestions.map((value) => (
                <option key={value} value={value} />
              ))}
            </datalist>
            <datalist id="worker-position-suggestions">
              {positionSuggestions.map((value) => (
                <option key={value} value={value} />
              ))}
            </datalist>
            <datalist id="worker-occupied-position-suggestions">
              {Array.from(
                new Set([...positionSuggestions, ...medicalAutocompleteSuggestions.occupiedPosition]),
              ).map((value) => (
                <option key={value} value={value} />
              ))}
            </datalist>
            <datalist id="worker-school-education-suggestions">
              {medicalAutocompleteSuggestions.schoolEducation.map((value) => (
                <option key={value} value={value} />
              ))}
            </datalist>
            <datalist id="worker-professional-training-suggestions">
              {medicalAutocompleteSuggestions.professionalTraining.map((value) => (
                <option key={value} value={value} />
              ))}
            </datalist>
            <datalist id="worker-professional-qualification-suggestions">
              {medicalAutocompleteSuggestions.professionalQualification.map((value) => (
                <option key={value} value={value} />
              ))}
            </datalist>
            <datalist id="worker-department-suggestions">
              {departmentSuggestions.map((value) => (
                <option key={value} value={value} />
              ))}
            </datalist>
            <datalist id="worker-service-suggestions">
              {serviceSuggestions.map((value) => (
                <option key={value} value={value} />
              ))}
            </datalist>
            <datalist id="worker-national-service-notes-suggestions">
              {medicalAutocompleteSuggestions.nationalServiceNotes.map((value) => (
                <option key={value} value={value} />
              ))}
            </datalist>
            <datalist id="worker-congenitalDiseases-suggestions">
              {medicalAutocompleteSuggestions.congenitalDiseases.map((value) => (
                <option key={value} value={value} />
              ))}
            </datalist>
            <datalist id="worker-generalDiseases-suggestions">
              {medicalAutocompleteSuggestions.generalDiseases.map((value) => (
                <option key={value} value={value} />
              ))}
            </datalist>
            <datalist id="worker-surgicalInterventions-suggestions">
              {medicalAutocompleteSuggestions.surgicalInterventions.map((value) => (
                <option key={value} value={value} />
              ))}
            </datalist>
            <datalist id="worker-accidents-suggestions">
              {medicalAutocompleteSuggestions.accidents.map((value) => (
                <option key={value} value={value} />
              ))}
            </datalist>
            <datalist id="worker-intoxications-suggestions">
              {medicalAutocompleteSuggestions.intoxications.map((value) => (
                <option key={value} value={value} />
              ))}
            </datalist>
            <datalist id="worker-tobacco-suggestions">
              {medicalAutocompleteSuggestions.tobacco.map((value) => (
                <option key={value} value={value} />
              ))}
            </datalist>
            <datalist id="worker-chewingTobacco-suggestions">
              {medicalAutocompleteSuggestions.chewingTobacco.map((value) => (
                <option key={value} value={value} />
              ))}
            </datalist>
            <datalist id="worker-alcoholism-suggestions">
              {medicalAutocompleteSuggestions.alcoholism.map((value) => (
                <option key={value} value={value} />
              ))}
            </datalist>
            <datalist id="worker-otherIntoxications-suggestions">
              {medicalAutocompleteSuggestions.otherIntoxications.map((value) => (
                <option key={value} value={value} />
              ))}
            </datalist>
            <datalist id="worker-workplace-risks-suggestions">
              {medicalAutocompleteSuggestions.workplaceAndRisks.map((value) => (
                <option key={value} value={value} />
              ))}
            </datalist>
            <datalist id="worker-vaccine-name-suggestions">
              {medicalAutocompleteSuggestions.vaccineName.map((value) => (
                <option key={value} value={value} />
              ))}
            </datalist>
            <datalist id="worker-professional-disease-notes-suggestions">
              {medicalAutocompleteSuggestions.professionalDiseaseNotes.map((value) => (
                <option key={value} value={value} />
              ))}
            </datalist>
            <datalist id="worker-workshop-suggestions">
              {workshopSuggestions.map((value) => (
                <option key={value} value={value} />
              ))}
            </datalist>
          </MedicalSectionCard>
        </div>
      );
    }

    if (sectionId === "professional") {
      return (
        <div className="space-y-5">
          <MedicalSectionCard
            icon={BriefcaseMedical}
            title="Informations professionnelles"
            description="Decrivez la formation, les qualifications et l'historique professionnel du travailleur."
          >
            <div className="grid gap-4 grid-cols-1 md:grid-cols-[0.2fr_0.4fr_0.4fr]">
              <Input
                label="Niveau scolaire"
                value={form.schoolEducation}
                list="worker-school-education-suggestions"
                onChange={(event) => updateField("schoolEducation", event.target.value)}
              />
              <Input
                label="Formation professionnelle"
                value={form.professionalTraining}
                list="worker-professional-training-suggestions"
                onChange={(event) => updateField("professionalTraining", event.target.value)}
              />
              <Input
                label="Qualification professionnelle"
                value={form.professionalQualification}
                list="worker-professional-qualification-suggestions"
                onChange={(event) =>
                  updateField("professionalQualification", event.target.value)
                }
              />
            </div>
          </MedicalSectionCard>

          <Card className="max-w-[760px] rounded-3xl border-slate-200/90 p-0">
            <div className="flex flex-col gap-4 border-b border-slate-200 bg-slate-50/60 px-3 py-3 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <h3 className="text-lg font-black text-slate-950">Historique professionnel</h3>
                <p className="mt-1 max-w-2xl text-sm text-slate-500">
                  Suivez les postes occupes, les periodes et les risques d'exposition associes.
                </p>
              </div>

              <Button
                variant="secondary"
                size="sm"
                icon={Plus}
                onClick={() =>
                  updateField("professionalHistory", [
                    ...form.professionalHistory,
                    createProfessionalHistoryRow(),
                  ])
                }
              >
                Ajouter
              </Button>
            </div>

            <div className="space-y-4">
              {form.professionalHistory.map((row) => (
                <div
                  key={row.id}
                  className="border border-slate-200 bg-white p-2 shadow-sm"
                >
                  <div className="mb-4 flex items-center justify-between gap-3">
                    <p className="text-sm font-black text-slate-900">Poste occupe</p>
                    <button
                      type="button"
                      onClick={() =>
                        updateField(
                          "professionalHistory",
                          form.professionalHistory.filter((item) => item.id !== row.id),
                        )
                      }
                      className="inline-flex h-9 w-9 items-center justify-center rounded-xl text-slate-400 transition hover:bg-red-50 hover:text-red-600"
                      aria-label="Supprimer la ligne"
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </div>

                  <div className="grid gap-4 md:grid-cols-2">
                    <Input
                      label="Poste occupe"
                      value={row.occupiedPosition}
                      list="worker-position-suggestions"
                      onChange={(event) =>
                        updateField(
                          "professionalHistory",
                          form.professionalHistory.map((item) =>
                            item.id === row.id
                              ? { ...item, occupiedPosition: event.target.value }
                              : item,
                          ),
                        )
                      }
                    />
                    <div className="grid gap-4 md:grid-cols-2">
                    <Input
                      label="Date de debut"
                      type="date"
                      value={row.fromDate}
                      onChange={(event) =>
                        updateField(
                          "professionalHistory",
                          form.professionalHistory.map((item) =>
                            item.id === row.id ? { ...item, fromDate: event.target.value } : item,
                          ),
                        )
                      }
                    />
                    <Input
                      label="Date de fin"
                      type="date"
                      value={row.toDate}
                      onChange={(event) =>
                        updateField(
                          "professionalHistory",
                          form.professionalHistory.map((item) =>
                            item.id === row.id ? { ...item, toDate: event.target.value } : item,
                          ),
                        )
                      }
                    />
                    </div>
                    <Input
                      label="Lieu de travail et risques professionnels"
                      value={row.workplaceAndRisks}
                      list="worker-workplace-risks-suggestions"
                      onChange={(event) =>
                        updateField(
                          "professionalHistory",
                          form.professionalHistory.map((item) =>
                            item.id === row.id
                              ? { ...item, workplaceAndRisks: event.target.value }
                              : item,
                          ),
                        )
                      }
                    />
                  </div>
                </div>
              ))}
            </div>
          </Card>

          <MedicalSectionCard
            icon={ShieldCheck}
            title="Service national"
            description="Renseignez le statut de service national et les observations associees."
          >
            <div className="grid gap-4 lg:grid-cols-[0.8fr_1.2fr]">
              <Select
                label="Statut du service national"
                options={[
                  { label: "Selectionner", value: "" },
                  { label: "Terminee", value: "completed" },
                  { label: "Dispense", value: "dispensed" },
                  { label: "Inapte", value: "unfit" },
                ]}
                value={form.nationalServiceStatus}
                onChange={(event) => updateField("nationalServiceStatus", event.target.value)}
              />
              <label className="block space-y-2">
                <span className="text-sm font-bold tracking-[0.01em] text-slate-800">
                  Notes
                </span>
                <textarea
                  rows={3}
                  value={form.nationalServiceNotes}
                  onChange={(event) => updateField("nationalServiceNotes", event.target.value)}
                  className={textareaClassName}
                />
              </label>
            </div>
          </MedicalSectionCard>
        </div>
      );
    }

    if (sectionId === "medical") {
      return (
        <div className="space-y-5 w-full">
          <MedicalSectionCard
            icon={HeartPulse}
            title="Antecedents medicaux"
            description="Centralisez les informations medicales chroniques, 
            les antecedents personnels et le statut vaccinal."
          >
            <div className="grid gap-4 md:grid-cols-[5fr_2fr]">
              <label className="block space-y-2">
                <span className="text-sm font-bold tracking-[0.01em] text-slate-800">
                  Notes sur les maladies chroniques
                </span>
                <textarea
                  rows={2}
                  value={form.chronicDiseaseNotes}
                  onChange={(event) => updateField("chronicDiseaseNotes", event.target.value)}
                  className={textareaClassName}
                />
              </label>
                <div className="max-w-[220px]">
                  <Select
                    label="Groupe sanguin / Rhesus"
                    options={[
                      { label: "Selectionner", value: "" },
                      { label: "A+", value: "A+" },
                      { label: "A-", value: "A-" },
                      { label: "B+", value: "B+" },
                      { label: "B-", value: "B-" },
                      { label: "AB+", value: "AB+" },
                      { label: "AB-", value: "AB-" },
                      { label: "O+", value: "O+" },
                      { label: "O-", value: "O-" },
                    ]}
                    value={form.bloodGroup}
                    onChange={(event) => updateField("bloodGroup", event.target.value)}
                    className="bg-white"
                  />
                </div>
            </div>
          </MedicalSectionCard>

          <MedicalSectionCard
            icon={HeartPulse}
            title="Antecedents personnels"
            description="Completez les antecedents medicaux, chirurgicaux et les habitudes toxiques."
          >
            <div className="grid gap-4 md:grid-cols-3">
              {[
                ["congenitalDiseases", "Maladies congenitales"],
                ["generalDiseases", "Maladies generales"],
                ["surgicalInterventions", "Interventions chirurgicales"],
                ["accidents", "Accidents"],
                ["intoxications", "Intoxications"],
                ["tobacco", "Tabac"],
                ["chewingTobacco", "Tabac a chiquer"],
                ["alcoholism", "Alcool"],
                ["otherIntoxications", "Autres intoxications"],
              ].map(([key, label]) => (
                <label key={key} className="block max-w-[320px] space-y-2">
                  <span className="text-sm font-bold tracking-[0.01em] text-slate-800">
                    {label}
                  </span>
                  <textarea
                    rows={3}
                    value={String(form[key as keyof WorkerMedicalFileForm] || "")}
                    onChange={(event) =>
                      updateField(
                        key as keyof WorkerMedicalFileForm,
                        event.target.value as never,
                      )
                    }
                    className={textareaClassName}
                  />
                </label>
              ))}
            </div>
          </MedicalSectionCard>

          <Card className="rounded-3xl border-slate-200/90 p-0">
            <div className="flex flex-col gap-4 border-b border-slate-200 bg-slate-50/60 px-2 py-2 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <h3 className="text-lg font-black text-slate-950">Tableau vaccinal</h3>
                <p className="mt-1 max-w-2xl text-sm text-slate-500">
                  Suivez les doses vaccinales et les rappels reportes dans le dossier papier.
                </p>
              </div>

              <Button
                variant="secondary"
                size="sm"
                icon={Plus}
                onClick={() =>
                  updateField("vaccinations", [...form.vaccinations, createVaccinationRow()])
                }
              >
                Ajouter
              </Button>
            </div>

            <div className="space-y-4">
              {form.vaccinations.map((row) => (
                <div
                  key={row.id}
                  className="rounded-xl border border-slate-200 bg-white p-2 shadow-sm"
                >
                  <div className="mb-4 flex items-center justify-between gap-3">
                    <p className="text-sm font-black text-slate-900">Vaccin</p>
                    <button
                      type="button"
                      onClick={() =>
                        updateField(
                          "vaccinations",
                          form.vaccinations.filter((item) => item.id !== row.id),
                        )
                      }
                      className="inline-flex h-9 w-9 items-center justify-center rounded-xl text-slate-400 transition hover:bg-red-50 hover:text-red-600"
                      aria-label="Supprimer la ligne"
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </div>

                  <div className="grid gap-4 md:grid-cols-3">
                    <Input
                      label="Vaccin"
                      value={row.vaccineName}
                      list="worker-vaccine-name-suggestions"
                      onChange={(event) =>
                        updateField(
                          "vaccinations",
                          form.vaccinations.map((item) =>
                            item.id === row.id
                              ? { ...item, vaccineName: event.target.value }
                              : item,
                          ),
                        )
                      }
                    />
                    <Input
                      label="1re dose"
                      type="date"
                      value={row.firstDose}
                      onChange={(event) =>
                        updateField(
                          "vaccinations",
                          form.vaccinations.map((item) =>
                            item.id === row.id
                              ? { ...item, firstDose: event.target.value }
                              : item,
                          ),
                        )
                      }
                    />
                    <Input
                      label="2e dose"
                      type="date"
                      value={row.secondDose}
                      onChange={(event) =>
                        updateField(
                          "vaccinations",
                          form.vaccinations.map((item) =>
                            item.id === row.id
                              ? { ...item, secondDose: event.target.value }
                              : item,
                          ),
                        )
                      }
                    />
                    <Input
                      label="1er rappel"
                      type="date"
                      value={row.firstBooster}
                      onChange={(event) =>
                        updateField(
                          "vaccinations",
                          form.vaccinations.map((item) =>
                            item.id === row.id
                              ? { ...item, firstBooster: event.target.value }
                              : item,
                          ),
                        )
                      }
                    />
                    <Input
                      label="2e rappel"
                      type="date"
                      value={row.secondBooster}
                      onChange={(event) =>
                        updateField(
                          "vaccinations",
                          form.vaccinations.map((item) =>
                            item.id === row.id
                              ? { ...item, secondBooster: event.target.value }
                              : item,
                          ),
                        )
                      }
                    />
                  </div>
                </div>
              ))}
            </div>
          </Card>
        </div>
      );
    }

    if (sectionId === "family") {
      return (
        <div className="space-y-5">
          <MedicalSectionCard
            icon={Users}
            title="Antecedents familiaux"
            description="Documentez les elements de contexte familial utiles a l'evaluation de sante au travail."
          >
            <div className="grid gap-4 grid-cols-1 md:grid-cols-2 xl:grid-cols-3">
              {[
                ["familyHistoryFather", "Pere"],
                ["familyHistoryMother", "Mere"],
                ["familyHistorySisters", "Soeurs"],
                ["familyHistoryBrothers", "Freres"],
                ["familyHistorySpouse", "Conjoint(e)"],
                ["familyHistoryChildrenBoys", "Enfants garcons"],
                ["familyHistoryChildrenGirls", "Enfants filles"],
              ].map(([key, label]) => (
                <Input
                  key={key}
                  label={label}
                  value={String(form[key as keyof WorkerMedicalFileForm] || "")}
                  onChange={(event) =>
                    updateField(
                      key as keyof WorkerMedicalFileForm,
                      event.target.value as never,
                    )
                  }
                />
              ))}
            </div>
          </MedicalSectionCard>
        </div>
      );
    }

    if (sectionId === "risks") {
      return (
        <div className="space-y-5">
          <div className="max-w-[760px]">
            <EditableMedicalTable
              title="Accidents de travail"
              rows={form.workAccidents}
              createRow={createWorkAccidentRow}
              onChange={(rows) => updateField("workAccidents", rows)}
              columns={[
                { key: "date", title: "Date", type: "date" },
                { key: "place", title: "Lieu", placeholder: "Lieu de travail" },
                { key: "consequences", title: "Consequences", placeholder: "Consequences" },
              ]}
            />
          </div>

          <Card className="max-w-[760px] rounded-3xl border-slate-200/90 p-0">
            <div className="flex flex-col gap-4 border-b border-slate-200 bg-slate-50/60 px-3 py-3 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <h3 className="text-lg font-black text-slate-950">Maladies professionnelles</h3>
                <p className="mt-1 max-w-2xl text-sm text-slate-500">
                  Renseignez les expositions, symptomes et informations administratives associees.
                </p>
              </div>

              <Button
                variant="secondary"
                size="sm"
                icon={Plus}
                onClick={() =>
                  updateField("occupationalDiseases", [
                    ...form.occupationalDiseases,
                    createOccupationalDiseaseRow(),
                  ])
                }
              >
                Ajouter
              </Button>
            </div>

            <div className="space-y-4">
              {form.occupationalDiseases.map((row) => (
                <div
                  key={row.id}
                  className="border border-slate-200 bg-white p-4 shadow-sm"
                >
                  <div className="mb-4 flex items-center justify-between gap-3">
                    <p className="text-sm font-black text-slate-900">Maladie professionnelle</p>
                    <button
                      type="button"
                      onClick={() =>
                        updateField(
                          "occupationalDiseases",
                          form.occupationalDiseases.filter((item) => item.id !== row.id),
                        )
                      }
                      className="inline-flex h-9 w-9 items-center justify-center rounded-xl text-slate-400 transition hover:bg-red-50 hover:text-red-600"
                      aria-label="Supprimer la ligne"
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </div>

                  <div className="grid gap-4 md:grid-cols-3">
                    <Input
                      label="Date"
                      type="date"
                      value={row.date}
                      onChange={(event) =>
                        updateField(
                          "occupationalDiseases",
                          form.occupationalDiseases.map((item) =>
                            item.id === row.id ? { ...item, date: event.target.value } : item,
                          ),
                        )
                      }
                    />
                    <Input
                      label="Lieu"
                      value={row.place}
                      onChange={(event) =>
                        updateField(
                          "occupationalDiseases",
                          form.occupationalDiseases.map((item) =>
                            item.id === row.id ? { ...item, place: event.target.value } : item,
                          ),
                        )
                      }
                    />
                    <Input
                      label="Produits d'exposition"
                      value={row.exposedProducts}
                      onChange={(event) =>
                        updateField(
                          "occupationalDiseases",
                          form.occupationalDiseases.map((item) =>
                            item.id === row.id
                              ? { ...item, exposedProducts: event.target.value }
                              : item,
                          ),
                        )
                      }
                    />
                    </div>
                    <div className="py-2"/>

                    <div className="grid gap-4 md:grid-cols-[0.6fr_0.2fr_0.2fr]">
                     
                    <Input
                      label="Symptomes cliniques et paracliniques"
                      value={row.symptoms}
                      onChange={(event) =>
                        updateField(
                          "occupationalDiseases",
                          form.occupationalDiseases.map((item) =>
                            item.id === row.id ? { ...item, symptoms: event.target.value } : item,
                          ),
                        )
                      }
                    />
                    <Input
                      label="Numero TMP"
                      value={row.tmpNumber}
                      onChange={(event) =>
                        updateField(
                          "occupationalDiseases",
                          form.occupationalDiseases.map((item) =>
                            item.id === row.id ? { ...item, tmpNumber: event.target.value } : item,
                          ),
                        )
                      }
                    />
                    <Input
                      label="IPP"
                      value={row.ipp}
                      onChange={(event) =>
                        updateField(
                          "occupationalDiseases",
                          form.occupationalDiseases.map((item) =>
                            item.id === row.id ? { ...item, ipp: event.target.value } : item,
                          ),
                        )
                      }
                    />
                  </div>
                </div>
              ))}
            </div>
          </Card>

          <MedicalSectionCard
            icon={AlertTriangle}
            title="Risques professionnels"
            description="Ajoutez les maladies a caractere professionnel et les remarques de suivi."
          >
            <Input
              label="Maladies a caractere professionnel"
              value={form.professionalDiseaseNotes}
              list="worker-professional-disease-notes-suggestions"
              onChange={(event) => updateField("professionalDiseaseNotes", event.target.value)}
            />
          </MedicalSectionCard>
        </div>
      );
    }

    if (sectionId === "consultations") {
      return (
        <div className="space-y-5">
          <Card className="max-w-[760px] rounded-3xl border-slate-200/90 p-0">
            <div className="flex flex-col gap-4 border-b border-slate-200 bg-slate-50/60 px-3 py-3 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <h3 className="text-lg font-black text-slate-950">Consultations spontanees</h3>
                <p className="mt-1 max-w-2xl text-sm text-slate-500">
                  Consignez chronologiquement les consultations, constats et observations de suivi.
                </p>
              </div>

              <Button
                variant="secondary"
                size="sm"
                icon={Plus}
                onClick={() =>
                  updateField("spontaneousConsultations", [
                    ...form.spontaneousConsultations,
                    createConsultationRow(),
                  ])
                }
              >
                Ajouter
              </Button>
            </div>

            <div className="space-y-4">
              {form.spontaneousConsultations.map((row) => (
                <div
                  key={row.id}
                  className="border border-slate-200 bg-white p-4 shadow-sm"
                >
                  <div className="mb-4 flex items-center justify-between gap-3">
                    <p className="text-sm font-black text-slate-900">Consultation</p>
                    <button
                      type="button"
                      onClick={() =>
                        updateField(
                          "spontaneousConsultations",
                          form.spontaneousConsultations.filter((item) => item.id !== row.id),
                        )
                      }
                      className="inline-flex h-9 w-9 items-center justify-center rounded-xl text-slate-400 transition hover:bg-red-50 hover:text-red-600"
                      aria-label="Supprimer la ligne"
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </div>

                  <div className="grid gap-4 grid-cols-1 md:grid-cols-[1fr_4fr]">
                    <div className="max-w-[220px]">
                      <Input
                        label="Date"
                        type="date"
                        value={row.date}
                        onChange={(event) =>
                          updateField(
                            "spontaneousConsultations",
                            form.spontaneousConsultations.map((item) =>
                              item.id === row.id ? { ...item, date: event.target.value } : item,
                            ),
                          )
                        }
                      />
                    </div>

                    <label className="block max-w-[520px] space-y-2">
                      <span className="text-sm font-bold tracking-[0.01em] text-slate-800">
                        Observation
                      </span>
                      <textarea
                        rows={4}
                        value={row.observation}
                        onChange={(event) =>
                          updateField(
                            "spontaneousConsultations",
                            form.spontaneousConsultations.map((item) =>
                              item.id === row.id
                                ? { ...item, observation: event.target.value }
                                : item,
                            ),
                          )
                        }
                        className={textareaClassName}
                      />
                    </label>
                  </div>
                </div>
              ))}
            </div>
          </Card>
        </div>
      );
    }

    if (sectionId === "internalVisit") {
      return (
        <div className="space-y-5">
          {campaignTestsLoading ? (
            <Card className="rounded-3xl border-slate-200/90 p-6">
              <div className="flex items-center gap-3 text-sm font-medium text-slate-600">
                <Spinner />
                <span>Chargement des examens medicaux de la campagne...</span>
              </div>
            </Card>
          ) : null}

          {!campaignTestsLoading && campaignTestsError ? (
            <Card className="rounded-3xl border-rose-200 bg-rose-50/70 p-6">
              <div className="flex items-start gap-3 text-sm font-medium text-rose-700">
                <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
                <span>{campaignTestsError}</span>
              </div>
            </Card>
          ) : null}

          {!campaignTestsLoading && !campaignTestsError && !hasAssignedCampaignTests ? (
            <EmptyState
              title="Aucun examen médical affecté à cette campagne."
              description="Ajoutez des examens depuis Tests medicaux dans l'edition de la campagne pour les rendre disponibles ici."
            />
          ) : null}
          
          <MedicalSectionCard
            icon={FileDown}
            title="Fiche interne de visite médicale"
            description="Renseignez la synthese de visite, les constantes cliniques et l'acuite visuelle."
          >
            <div className="grid gap-4 grid-cols-3 md:grid-cols-[0.8fr_0.8fr_1.2fr]">
              <Input
                label="Nom & prenom"
                value={`${form.firstName} ${form.lastName}`.trim()}
                readOnly
                className="cursor-not-allowed bg-slate-100/90 text-slate-500"
              />
              <Input
                label="Ne le"
                value={formatDisplayDate(form.dateOfBirth)}
                readOnly
                className="cursor-not-allowed bg-slate-100/90 text-slate-500"
              />
              <Input
                label="Post de travaill"
                value={form.position}
                readOnly
                className="cursor-not-allowed bg-slate-100/90 text-slate-500"
              />
              <Input
                label="Date"
                type="date"
                value={form.internalVisitDate}
                onChange={(event) => updateField("internalVisitDate", event.target.value)}
              />
              <Input
                label="Medecin"
                value={form.internalVisitDoctor}
                readOnly
                className="cursor-not-allowed bg-slate-100/90 text-slate-500"
              />
              <div className="grid gap-3 sm:grid-cols-2">
                <label className="flex items-center gap-3 rounded-2xl border border-slate-200 bg-slate-50/70 px-4 py-3 text-sm font-medium text-slate-800">
                  <input
                    type="radio"
                    name="internalVisitType"
                    checked={form.internalVisitHire}
                    onChange={() => {
                      updateField("internalVisitHire", true);
                      updateField("internalVisitPeriodic", false);
                    }}
                    className="h-4 w-4 border-slate-300 text-cyan-600 focus:ring-cyan-500"
                  />
                  <span>Visite d'embauche</span>
                </label>
                <label className="flex items-center gap-3 rounded-2xl border border-slate-200 bg-slate-50/70 px-4 py-3 text-sm font-medium text-slate-800">
                  <input
                    type="radio"
                    name="internalVisitType"
                    checked={form.internalVisitPeriodic}
                    onChange={() => {
                      updateField("internalVisitHire", false);
                      updateField("internalVisitPeriodic", true);
                    }}
                    className="h-4 w-4 border-slate-300 text-cyan-600 focus:ring-cyan-500"
                  />
                  <span>Visite périodique</span>
                </label>
              </div>
            </div>
            <div className="mt-5 h-px" />
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
              <Input
                label="Poids (Kg)"
                value={form.internalVisitWeightKg}
                onChange={(event) => updateField("internalVisitWeightKg", event.target.value)}
              />
              <Input
                label="Taille (cm)"
                value={form.internalVisitHeightCm}
                onChange={(event) => updateField("internalVisitHeightCm", event.target.value)}
              />
              <Input
                label="TA"
                value={form.internalVisitTa}
                onChange={(event) =>
                  updateField("internalVisitTa", formatTA(event.target.value))
                }
              />
              <Input
                label="FC"
                value={form.internalVisitFc}
                onChange={(event) => updateField("internalVisitFc", event.target.value)}
              />
            </div>

           
          </MedicalSectionCard>

          {shouldShowCampaignMedicalTest("acuite-visuelle") ? (
            <MedicalSubsection
              title={renderTestTitle(getCampaignMedicalTestTitle("acuite-visuelle", "Acuité visuelle"), [
                form.internalVisitDistanceOdSc,
                form.internalVisitDistanceOdAc,
                form.internalVisitDistanceOgSc,
                form.internalVisitDistanceOgAc,
              ],
              <Eye className="h-4 w-4" />,
            )}
              isCollapsible={true}
            >
              <div className="space-y-1">
                <div className="rounded-[0.25rem] border border-slate-200 bg-slate-50/60 p-2">
                  <div className="grid items-end gap-4 md:grid-cols-[minmax(0,1.2fr)_minmax(0,1fr)_minmax(0,1fr)]">
                    <div>
                      <p className="text-sm font-black uppercase text-cyan-800">OD</p>
                      <p className="mt-1 text-sm text-slate-500">Oeil droit</p>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="shrink-0 text-sm font-bold tracking-[0.01em] text-slate-800">SC</span>
                      <div className="min-w-0 flex-1">
                        <Input
                          type="number"
                          min={1}
                          max={10}
                          step={1}
                          value={form.internalVisitDistanceOdSc}
                          onChange={(event) => {
                            const value = event.target.value;

                            if (value === "") {
                              updateField("internalVisitDistanceOdSc", "");
                              return;
                            }

                            const clamped = Math.min(10, Math.max(1, Number(value)));

                            updateField("internalVisitDistanceOdSc", String(clamped));
                          }}
                        />
                      </div>
                      <span className="shrink-0 text-sm font-semibold text-slate-500">/ 10</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="shrink-0 text-sm font-bold tracking-[0.01em] text-slate-800">AC</span>
                      <div className="min-w-0 flex-1">
                        <Input
                          type="number"
                          min={1}
                          max={10}
                          step={1}
                          value={form.internalVisitDistanceOdAc}
                          onChange={(event) => {
                            const value = event.target.value;

                            if (value === "") {
                              updateField("internalVisitDistanceOdAc", "");
                              return;
                            }

                            const clamped = Math.min(10, Math.max(1, Number(value)));

                            updateField("internalVisitDistanceOdAc", String(clamped));
                          }}
                        />
                      </div>
                      <span className="shrink-0 text-sm font-semibold text-slate-500">/ 10</span>
                    </div>
                  </div>
                </div>

                <div className="rounded-[0.25rem] border border-slate-200 bg-slate-50/60 p-2">
                  <div className="grid items-end gap-4 md:grid-cols-[minmax(0,1.2fr)_minmax(0,1fr)_minmax(0,1fr)]">
                    <div>
                      <p className="text-sm font-black uppercase text-emerald-800">OG</p>
                      <p className="mt-1 text-sm text-slate-500">Oeil gauche</p>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="shrink-0 text-sm font-bold tracking-[0.01em] text-slate-800">SC</span>
                      <div className="min-w-0 flex-1">
                        <Input
                          type="number"
                          min={1}
                          max={10}
                          step={1}
                          value={form.internalVisitDistanceOgSc}
                          onChange={(event) => {
                            const value = event.target.value;

                            if (value === "") {
                              updateField("internalVisitDistanceOgSc", "");
                              return;
                            }

                            const clamped = Math.min(10, Math.max(1, Number(value)));

                            updateField("internalVisitDistanceOgSc", String(clamped));
                          }}
                        />
                      </div>
                      <span className="shrink-0 text-sm font-semibold text-slate-500">/ 10</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="shrink-0 text-sm font-bold tracking-[0.01em] text-slate-800">AC</span>
                      <div className="min-w-0 flex-1">
                        <Input
                          type="number"
                          min={1}
                          max={10}
                          step={1}
                          value={form.internalVisitDistanceOgAc}
                          onChange={(event) => {
                            const value = event.target.value;

                            if (value === "") {
                              updateField("internalVisitDistanceOgAc", "");
                              return;
                            }

                            const clamped = Math.min(10, Math.max(1, Number(value)));

                            updateField("internalVisitDistanceOgAc", String(clamped));
                          }}
                        />
                      </div>
                      <span className="shrink-0 text-sm font-semibold text-slate-500">/ 10</span>
                    </div>
                  </div>
                </div>

              </div>
            </MedicalSubsection>
          ) : null}

          {shouldShowCampaignMedicalTest("acuite-visuelle-binoculaire") ? (
            <MedicalSubsection
              title={renderTestTitle(
                getCampaignMedicalTestTitle(
                  "acuite-visuelle-binoculaire",
                  "Acuité visuelle Binoculaire",
                ),
                [form.internalVisitDistanceOdg],
                <ScanEye className="h-4 w-4" />,
              )}
              isCollapsible={true}>
              <div className="rounded-[0.25rem] border border-slate-200 bg-slate-50/60 p-2">
                <div className="flex flex-wrap items-center gap-1">
                  <span className="text-sm font-black text-slate-900">
                    Acuité visuelle binoculaire
                  </span>
                  <div className="flex-1 w-full" />
                  <span className="shrink-0 text-sm font-bold tracking-[0.01em] text-slate-800">
                    ODG
                  </span>
                  <div className="min-w-[120px] flex-1 max-w-[180px]">
                    <Input
                      type="number"
                      min={1}
                      max={10}
                      step={1}
                      value={form.internalVisitDistanceOdg}
                      onChange={(event) => {
                        const value = event.target.value;

                        if (value === "") {
                          updateField("internalVisitDistanceOdg", "");
                          return;
                        }

                        const clamped = Math.min(10, Math.max(1, Number(value)));

                        updateField("internalVisitDistanceOdg", String(clamped));
                      }}
                    />
                  </div>
                  <span className="shrink-0 text-sm font-semibold text-slate-500">/ 10</span>
                </div>
              </div>
            </MedicalSubsection>
          ) : null}
          <div className="space-y-6">
          {currentCampaignDynamicTests
            .filter((item) => item.sectionId === "internalVisit")
            .map((item) => renderDynamicMedicalTestCard(item.assignment, "internalVisit"))}
        </div>
        </div>
      );
    }

    if (sectionId === "clinicalExam") {
      if (campaignTestsLoading) {
        return (
          <div className="space-y-5">
            <MedicalSectionCard
              icon={Stethoscope}
              title="Examen clinique"
              description="Chargement des examens medicaux affectes a cette campagne."
            >
              <div className="flex items-center gap-3 text-sm font-medium text-slate-600">
                <Spinner />
                <span>Chargement des examens medicaux de la campagne...</span>
              </div>
            </MedicalSectionCard>
          </div>
        );
      }

      if (campaignTestsError) {
        return (
          <div className="space-y-5">
            <MedicalSectionCard
              icon={Stethoscope}
              title="Examen clinique"
              description="Impossible de charger les examens medicaux de cette campagne."
            >
              <div className="rounded-2xl border border-rose-200 bg-rose-50/70 px-4 py-6 text-sm text-rose-700">
                {campaignTestsError}
              </div>
            </MedicalSectionCard>
          </div>
        );
      }

      if (!hasAssignedCampaignTests) {
        return (
          <div className="space-y-5">
            <MedicalSectionCard
              icon={Stethoscope}
              title="Examen clinique"
              description="Aucun examen medical n'est disponible pour cette campagne."
            >
              <EmptyState
                title="Aucun examen médical affecté à cette campagne."
                description="Ajoutez des examens depuis Tests medicaux dans l'edition de la campagne pour les rendre disponibles ici."
              />
            </MedicalSectionCard>
          </div>
        );
      }

      if (!shouldShowCampaignMedicalSection("clinicalExam")) {
        return (
          <div className="space-y-5">
            <MedicalSectionCard
              icon={Stethoscope}
              title="Examen clinique"
              description="Aucun test requis pour cette campagne."
            >
              <div className="rounded-2xl border border-dashed border-slate-200 bg-slate-50/70 px-4 py-6 text-sm text-slate-500">
                Aucun test requis pour cette campagne.
              </div>
            </MedicalSectionCard>
          </div>
        );
      }

      return (
        <div className="space-y-5">
          <MedicalSectionCard
            icon={Stethoscope}
            title="Examen clinique"
            description="Structurez l'examen clinique en sous-specialites pour une lecture medicale rapide."
          >
            <div className="grid gap-5 xl:grid-cols-1">
              {shouldShowCampaignMedicalTest("ophtalmologie") ? (
              <MedicalSubsection
                title={renderTestTitle(getCampaignMedicalTestTitle("ophtalmologie", "Ophtalmologie"), [
                  form.clinicalExam.ophthalmology.observations,
                ],
                <Eye className="h-4 w-4" />,
              )}
                isCollapsible={true}
              >
                <label className="block space-y-2">
                  <span className="text-sm font-bold text-slate-800">Observations</span>
                  <textarea
                    rows={2}
                    value={form.clinicalExam.ophthalmology.observations}
                    onChange={(event) =>
                      updateClinicalExam("ophthalmology", {
                        observations: event.target.value,
                      })
                    }
                    className={textareaClassName}
                  />
                </label>
              </MedicalSubsection>
              ) : null}

              {shouldShowCampaignMedicalTest("orl") ? (
              <MedicalSubsection
                title={renderTestTitle(getCampaignMedicalTestTitle("orl", "ORL"), [
                  form.clinicalExam.ent.nose,
                  form.clinicalExam.ent.ears,
                  form.clinicalExam.ent.throat,
                ],
                <Ear className="h-4 w-4" />,
              )}
                isCollapsible={true}
              >
                <div className="grid gap-4 grid-cols-1 md:grid-cols-3">
                  <Textarea
                    label="Nez"
                    rows={4}
                    value={form.clinicalExam.ent.nose}
                    onChange={(event) =>
                      updateClinicalExam("ent", { ...form.clinicalExam.ent, nose: event.target.value })
                    }
                  />
                  <Textarea
                    label="Oreilles"
                    rows={4}
                    value={form.clinicalExam.ent.ears}
                    onChange={(event) =>
                      updateClinicalExam("ent", { ...form.clinicalExam.ent, ears: event.target.value })
                    }
                  />
                  <Textarea
                    label="Gorge"
                    rows={4}
                    value={form.clinicalExam.ent.throat}
                    onChange={(event) =>
                      updateClinicalExam("ent", { ...form.clinicalExam.ent, throat: event.target.value })
                    }
                  />
                </div>
              </MedicalSubsection>
              ) : null}

              {shouldShowCampaignMedicalTest("stomatologie") ? (
              <MedicalSubsection
                title={renderTestTitle(getCampaignMedicalTestTitle("stomatologie", "Stomatologie"), [
                  form.clinicalExam.stomatology.teeth,
                  form.clinicalExam.stomatology.others,
                ],
                <Smile className="h-4 w-4" />,
              )}
                isCollapsible={true}
              >
                <div className="grid gap-4 grid-cols-1 md:grid-cols-2">
                  <Textarea
                    label="Denture"
                    rows={2}
                    value={form.clinicalExam.stomatology.teeth}
                    onChange={(event) =>
                      updateClinicalExam("stomatology", {
                        ...form.clinicalExam.stomatology,
                        teeth: event.target.value,
                      })
                    }
                  />
                  <Textarea
                    label="Autres"
                    rows={2}
                    value={form.clinicalExam.stomatology.others}
                    onChange={(event) =>
                      updateClinicalExam("stomatology", {
                        ...form.clinicalExam.stomatology,
                        others: event.target.value,
                      })
                    }
                  />
                </div>
              </MedicalSubsection>
              ) : null}

              {shouldShowCampaignMedicalTest("cardio-vasculaire") ? (
              <MedicalSubsection
                title={renderTestTitle(getCampaignMedicalTestTitle("cardio-vasculaire", "Cardio Vasculaire"), [
                  form.internalVisitTa,
                  form.clinicalExam.cardiovascular.dyspnea,
                ],
                <HeartPulse className="h-4 w-4" />,
              )}
                isCollapsible={true}
              >
                <div className="space-y-4">
                <div className="flex grid gap-3 grid-cols-1 md:grid-cols-[1fr_10fr]">
                  <Input
                    label="TA"
                    value={form.internalVisitTa}
                    readOnly
                    onChange={(event) =>
                      updateClinicalExam("cardiovascular", {
                        ...form.clinicalExam.cardiovascular,
                        bloodPressure: event.target.value,
                      })
                    }
                  />
                  <Input
                    label="Dyspnee"
                    value={form.clinicalExam.cardiovascular.dyspnea}
                    onChange={(event) =>
                      updateClinicalExam("cardiovascular", {
                        ...form.clinicalExam.cardiovascular,
                        dyspnea: event.target.value,
                      })
                    }
                  />
                  </div>
                </div>
              </MedicalSubsection>
              ) : null}

              {shouldShowCampaignMedicalTest("respiratoire-clinique") ? (
              <MedicalSubsection
                title={renderTestTitle(getCampaignMedicalTestTitle("respiratoire-clinique", "Respiratoire"), [
                  form.clinicalExam.respiratory.chronicCough,
                  form.clinicalExam.respiratory.asthma,
                ],
                <Wind className="h-4 w-4" />,
              )}
                isCollapsible={true}
              >
                <div className="grid gap-3 grid-cols-1 md:grid-cols-2">
                  <Textarea
                    label="Toux chronique"
                    rows={2}
                    value={form.clinicalExam.respiratory.chronicCough}
                    onChange={(event) =>
                      updateClinicalExam("respiratory", {
                        ...form.clinicalExam.respiratory,
                        chronicCough: event.target.value,
                      })
                    }
                  />
                  <Textarea
                    label="Asthme"
                    rows={2}
                    value={form.clinicalExam.respiratory.asthma}
                    onChange={(event) =>
                      updateClinicalExam("respiratory", {
                        ...form.clinicalExam.respiratory,
                        asthma: event.target.value,
                      })
                    }
                  />
                </div>
              </MedicalSubsection>
              ) : null}

              {shouldShowCampaignMedicalTest("digestif") ? (
              <MedicalSubsection
                title={renderTestTitle(getCampaignMedicalTestTitle("digestif", "Digestif"), [
                  form.clinicalExam.digestive.ulcer,
                  form.clinicalExam.digestive.colopathy,
                  form.clinicalExam.digestive.hemorrhoids,
                  form.clinicalExam.digestive.others,
                ],
                <Pill className="h-4 w-4" />,
              )}
                isCollapsible={true}
              >
                <div className="space-y-4">
                  <div className="grid gap-3 grid-cols-1 md:grid-cols-2">
                  <Textarea
                    label="Ulcere"
                    rows={2}
                    value={form.clinicalExam.digestive.ulcer}
                    onChange={(event) =>
                      updateClinicalExam("digestive", {
                        ...form.clinicalExam.digestive,
                        ulcer: event.target.value,
                      })
                    }
                  />
                  <Textarea
                    label="Colopathie"
                    rows={2}
                    value={form.clinicalExam.digestive.colopathy}
                    onChange={(event) =>
                      updateClinicalExam("digestive", {
                        ...form.clinicalExam.digestive,
                        colopathy: event.target.value,
                      })
                    }
                  />
                  </div>
                  <div className="grid gap-3 grid-cols-1 md:grid-cols-2">
                  <Textarea
                    label="Hemorroides"
                    rows={2}
                    value={form.clinicalExam.digestive.hemorrhoids}
                    onChange={(event) =>
                      updateClinicalExam("digestive", {
                        ...form.clinicalExam.digestive,
                        hemorrhoids: event.target.value,
                      })
                    }
                  />
                  <Textarea
                    label="Autres"
                    rows={2}
                    value={form.clinicalExam.digestive.others}
                    onChange={(event) =>
                      updateClinicalExam("digestive", {
                        ...form.clinicalExam.digestive,
                        others: event.target.value,
                      })
                    }
                  />
                </div>
                </div>
              </MedicalSubsection>
              ) : null}

              {shouldShowCampaignMedicalTest("uro-genital") ? (
              <MedicalSubsection
                title={renderTestTitle(getCampaignMedicalTestTitle("uro-genital", "Uro-genital"), [
                  form.clinicalExam.urogenital.dysuria,
                  form.clinicalExam.urogenital.impotence,
                  form.clinicalExam.urogenital.others,
                ],
                <Droplets className="h-4 w-4" />,
              )}
                isCollapsible={true}
              >
                <div className="grid gap-3 grid-cols-1 md:grid-cols-3">
                  <Textarea
                    label="Dysurie"
                    rows={4}
                    value={form.clinicalExam.urogenital.dysuria}
                    onChange={(event) =>
                      updateClinicalExam("urogenital", {
                        ...form.clinicalExam.urogenital,
                        dysuria: event.target.value,
                      })
                    }
                  />
                  <Textarea
                    label="Impuissance"
                    rows={4}
                    value={form.clinicalExam.urogenital.impotence}
                    onChange={(event) =>
                      updateClinicalExam("urogenital", {
                        ...form.clinicalExam.urogenital,
                        impotence: event.target.value,
                      })
                    }
                  />
                  <Textarea
                    label="Autres"
                    rows={4}
                    value={form.clinicalExam.urogenital.others}
                    onChange={(event) =>
                      updateClinicalExam("urogenital", {
                        ...form.clinicalExam.urogenital,
                        others: event.target.value,
                      })
                    }
                  />
                </div>
              </MedicalSubsection>
              ) : null}

              {shouldShowCampaignMedicalTest("endocrinien") ? (
              <MedicalSubsection
                title={renderTestTitle(getCampaignMedicalTestTitle("endocrinien", "Endocrinien"), [
                  form.clinicalExam.endocrine.diabetes,
                  form.clinicalExam.endocrine.thyroid,
                  form.clinicalExam.endocrine.others,
                ],
                <Activity className="h-4 w-4" />,
              )}
                isCollapsible={true}
              >
                <div className="grid gap-4 grid-cols-1 md:grid-cols-3">
                  <Textarea
                    label="Diabete"
                    rows={4}
                    value={form.clinicalExam.endocrine.diabetes}
                    onChange={(event) =>
                      updateClinicalExam("endocrine", {
                        ...form.clinicalExam.endocrine,
                        diabetes: event.target.value,
                      })
                    }
                  />
                  <Textarea
                    label="Thyroide"
                    rows={4}
                    value={form.clinicalExam.endocrine.thyroid}
                    onChange={(event) =>
                      updateClinicalExam("endocrine", {
                        ...form.clinicalExam.endocrine,
                        thyroid: event.target.value,
                      })
                    }
                  />
                  <Textarea
                    label="Autres"
                    rows={4}
                    value={form.clinicalExam.endocrine.others}
                    onChange={(event) =>
                      updateClinicalExam("endocrine", {
                        ...form.clinicalExam.endocrine,
                        others: event.target.value,
                      })
                    }
                  />
                </div>
              </MedicalSubsection>
              ) : null}

              {shouldShowCampaignMedicalTest("hematologie") ? (
              <MedicalSubsection
                title={renderTestTitle(getCampaignMedicalTestTitle("hematologie", "Hematologie"), [
                  form.clinicalExam.hematology.hemostasis,
                  form.clinicalExam.hematology.adenopathy,
                  form.clinicalExam.hematology.others,
                ],
                <Droplet className="h-4 w-4" />,
              )}
                isCollapsible={true}
              >
                <div className="grid gap-4 grid-cols-1 md:grid-cols-3">
                  <Textarea
                    label="Hemostase"
                    rows={4}
                    value={form.clinicalExam.hematology.hemostasis}
                    onChange={(event) =>
                      updateClinicalExam("hematology", {
                        ...form.clinicalExam.hematology,
                        hemostasis: event.target.value,
                      })
                    }
                  />
                  <Textarea
                    label="Adenopathie"
                    rows={4}
                    value={form.clinicalExam.hematology.adenopathy}
                    onChange={(event) =>
                      updateClinicalExam("hematology", {
                        ...form.clinicalExam.hematology,
                        adenopathy: event.target.value,
                      })
                    }
                  />
                  <Textarea
                    label="Autres"
                    rows={4}
                    value={form.clinicalExam.hematology.others}
                    onChange={(event) =>
                      updateClinicalExam("hematology", {
                        ...form.clinicalExam.hematology,
                        others: event.target.value,
                      })
                    }
                  />
                </div>
              </MedicalSubsection>
              ) : null}

              {shouldShowCampaignMedicalTest("neuro-psychiatrie") ? (
              <MedicalSubsection
                title={renderTestTitle(getCampaignMedicalTestTitle("neuro-psychiatrie", "Neuro-Psychiatrie"), [
                  form.clinicalExam.neuroPsychiatric.headachesVertigo,
                  form.clinicalExam.neuroPsychiatric.neurologicalSigns,
                  form.clinicalExam.neuroPsychiatric.personalityDisorders,
                  form.clinicalExam.neuroPsychiatric.others,
                ],
                <Brain className="h-4 w-4" />,
              )}
                isCollapsible={true}
              >
                <div>
                <div className="grid gap-4 grid-cols-1 md:grid-cols-2">
                  <Textarea
                    label="Cephalees / Vertiges"
                    rows={2}
                    value={form.clinicalExam.neuroPsychiatric.headachesVertigo}
                    onChange={(event) =>
                      updateClinicalExam("neuroPsychiatric", {
                        ...form.clinicalExam.neuroPsychiatric,
                        headachesVertigo: event.target.value,
                      })
                    }
                  />
                  <Textarea
                    label="Signes neurologiques"
                    rows={2}
                    value={form.clinicalExam.neuroPsychiatric.neurologicalSigns}
                    onChange={(event) =>
                      updateClinicalExam("neuroPsychiatric", {
                        ...form.clinicalExam.neuroPsychiatric,
                        neurologicalSigns: event.target.value,
                      })
                    }
                  />
                  </div>
                  <div className="space-y-4"/>
                  <div className="grid gap-4 grid-cols-1 md:grid-cols-2">
                  <Textarea
                    label="Troubles de personnalite"
                    rows={2}
                    value={form.clinicalExam.neuroPsychiatric.personalityDisorders}
                    onChange={(event) =>
                      updateClinicalExam("neuroPsychiatric", {
                        ...form.clinicalExam.neuroPsychiatric,
                        personalityDisorders: event.target.value,
                      })
                    }
                  />
                  <Textarea
                    label="Autres"
                    rows={2}
                    value={form.clinicalExam.neuroPsychiatric.others}
                    onChange={(event) =>
                      updateClinicalExam("neuroPsychiatric", {
                        ...form.clinicalExam.neuroPsychiatric,
                        others: event.target.value,
                      })
                    }
                  />
                </div>
                </div>
              </MedicalSubsection>
              ) : null}

              {shouldShowCampaignMedicalTest("osteo-articulaire") ? (
              <MedicalSubsection
                title={renderTestTitle(getCampaignMedicalTestTitle("osteo-articulaire", "Osteo-Articulaire"), [
                  form.clinicalExam.osteoArticular.polyarthralgia,
                ],
                <Bone className="h-4 w-4" />,
              )}
                isCollapsible={true}
              >
                <div className="space-y-4">
                  <Input
                    label="Polyarthralgies"
                    value={form.clinicalExam.osteoArticular.polyarthralgia}
                    onChange={(event) =>
                      updateClinicalExam("osteoArticular", {
                        ...form.clinicalExam.osteoArticular,
                        polyarthralgia: event.target.value,
                      })
                    }
                  />
                </div>
              </MedicalSubsection>
              ) : null}

              {shouldShowCampaignMedicalTest("dermatologie") ? (
              <MedicalSubsection
                title={renderTestTitle(getCampaignMedicalTestTitle("dermatologie", "Dermatologie"), [
                  form.clinicalExam.dermatology.lesions,
                  form.clinicalExam.dermatology.skinAllergies,
                  form.clinicalExam.dermatology.urticaria,
                ],
                <ShieldPlus className="h-4 w-4" />,
              )}
                isCollapsible={true}
              >
                <div className="grid gap-4 grid-cols-1 md:grid-cols-3">
                  <Textarea
                    label="Lesions"
                    rows={4}
                    value={form.clinicalExam.dermatology.lesions}
                    onChange={(event) =>
                      updateClinicalExam("dermatology", {
                        ...form.clinicalExam.dermatology,
                        lesions: event.target.value,
                      })
                    }
                  />
                  <Textarea
                    label="Allergies cutanees"
                    rows={4}
                    value={form.clinicalExam.dermatology.skinAllergies}
                    onChange={(event) =>
                      updateClinicalExam("dermatology", {
                        ...form.clinicalExam.dermatology,
                        skinAllergies: event.target.value,
                      })
                    }
                  />
                  <Textarea
                    label="Urticaire"
                    rows={4}
                    value={form.clinicalExam.dermatology.urticaria}
                    onChange={(event) =>
                      updateClinicalExam("dermatology", {
                        ...form.clinicalExam.dermatology,
                        urticaria: event.target.value,
                      })
                    }
                  />
                </div>
              </MedicalSubsection>
              ) : null}
            </div>

            <div className="mt-5">
              {shouldShowCampaignMedicalTest("observations-generales") ? (
              <MedicalSubsection
                title={renderTestTitle(
                  getCampaignMedicalTestTitle(
                    "observations-generales",
                    "Observations generales du medecin",
                  ),
                  [
                    form.clinicalExam.doctorGeneralObservations.comments,
                    form.clinicalExam.doctorGeneralObservations.recommendations,
                  ],
                  <ClipboardList className="h-4 w-4" />,
                )}
                isCollapsible={true}
              >
                <div className="grid gap-4 md:grid-cols-2">
                  <label className="block space-y-2">
                    <span className="text-sm font-bold text-slate-800">Commentaires</span>
                    <textarea
                      rows={4}
                      value={form.clinicalExam.doctorGeneralObservations.comments}
                      onChange={(event) =>
                        updateClinicalExam("doctorGeneralObservations", {
                          ...form.clinicalExam.doctorGeneralObservations,
                          comments: event.target.value,
                        })
                      }
                      className={textareaClassName}
                    />
                  </label>
                  <label className="block space-y-2">
                    <span className="text-sm font-bold text-slate-800">Recommandations</span>
                    <textarea
                      rows={4}
                      value={form.clinicalExam.doctorGeneralObservations.recommendations}
                      onChange={(event) =>
                        updateClinicalExam("doctorGeneralObservations", {
                          ...form.clinicalExam.doctorGeneralObservations,
                          recommendations: event.target.value,
                        })
                      }
                      className={textareaClassName}
                    />
                  </label>
                </div>
              </MedicalSubsection>
              ) : null}
              <div className="space-y-6">

              {currentCampaignDynamicTests
                .filter((item) => item.sectionId === "clinicalExam")
                .map((item) => renderDynamicMedicalTestCard(item.assignment, "clinicalExam"))}
            </div>
            </div>
          </MedicalSectionCard>
        </div>
      );
    }

    if (sectionId === "complementaryExams") {
      if (campaignTestsLoading) {
        return (
          <div className="space-y-5">
            <MedicalSectionCard
              icon={FlaskConical}
              title="Examens complementaires"
              description="Chargement des examens medicaux affectes a cette campagne."
            >
              <div className="flex items-center gap-3 text-sm font-medium text-slate-600">
                <Spinner />
                <span>Chargement des examens medicaux de la campagne...</span>
              </div>
            </MedicalSectionCard>
          </div>
        );
      }

      if (campaignTestsError) {
        return (
          <div className="space-y-5">
            <MedicalSectionCard
              icon={FlaskConical}
              title="Examens complementaires"
              description="Impossible de charger les examens medicaux de cette campagne."
            >
              <div className="rounded-2xl border border-rose-200 bg-rose-50/70 px-4 py-6 text-sm text-rose-700">
                {campaignTestsError}
              </div>
            </MedicalSectionCard>
          </div>
        );
      }

      if (!hasAssignedCampaignTests) {
        return (
          <div className="space-y-5">
            <MedicalSectionCard
              icon={FlaskConical}
              title="Examens complementaires"
              description="Aucun examen medical n'est disponible pour cette campagne."
            >
              <EmptyState
                title="Aucun examen médical affecté à cette campagne."
                description="Ajoutez des examens depuis Tests medicaux dans l'edition de la campagne pour les rendre disponibles ici."
              />
            </MedicalSectionCard>
          </div>
        );
      }

      if (!shouldShowCampaignMedicalSection("complementaryExams")) {
        return (
          <div className="space-y-5">
            <MedicalSectionCard
              icon={FlaskConical}
              title="Examens complementaires"
              description="Aucun test complementaire n'est requis pour cette campagne."
            >
              <EmptyState
                title="Aucun test requis pour cette campagne"
                description="Les examens complementaires n'ont pas ete affectes a cette campagne."
              />
            </MedicalSectionCard>
          </div>
        );
      }

      return (
        <div className="space-y-5">
          <MedicalSectionCard
            icon={FlaskConical}
            title="Examens complementaires"
            description="Consolidez les examens fonctionnels, biologiques et radiologiques dans un format medical compact."
          >
            <div className="grid gap-5 xl:grid-cols-1">
              {shouldShowCampaignMedicalTest("ecg") ? (
                <MedicalSubsection
                  title={renderTestTitle(getCampaignMedicalTestTitle("ecg", "ECG"), [
                    form.complementaryExams.cardiology.ecg,
                  ],
                  <HeartPulse className="h-4 w-4" />,
                )}
                  isCollapsible={true}
                >
                  <Input
                    label="ECG"
                    value={form.complementaryExams.cardiology.ecg}
                    onChange={(event) =>
                      updateComplementaryExams("cardiology", { ecg: event.target.value })
                    }
                  />
                </MedicalSubsection>
              ) : null}
              {shouldShowCampaignMedicalTest("audiogramme") ? (
                <MedicalSubsection
                  title={renderTestTitle(getCampaignMedicalTestTitle("audiogramme", "Audiogramme"), [
                    form.complementaryExams.audiology.audiogram,
                  ],
                  <Volume2 className="h-4 w-4" />,
                )}
                  isCollapsible={true}
                >
                  <Input
                    label="Audiogramme"
                    value={form.complementaryExams.audiology.audiogram}
                    onChange={(event) =>
                      updateComplementaryExams("audiology", { audiogram: event.target.value })
                    }
                  />
                </MedicalSubsection>
              ) : null}
              {shouldShowCampaignMedicalTest("efr") ? (
                <MedicalSubsection
                  title={renderTestTitle(getCampaignMedicalTestTitle("efr", "EFR"), [
                    form.complementaryExams.respiratory.efr,
                  ],
                  <Wind className="h-4 w-4" />,
                )}
                  isCollapsible={true}
                >
                  <Input
                    label="EFR"
                    value={form.complementaryExams.respiratory.efr}
                    onChange={(event) =>
                      updateComplementaryExams("respiratory", { efr: event.target.value })
                    }
                  />
                </MedicalSubsection>
              ) : null}
              {shouldShowCampaignMedicalTest("parasitologie-des-selles") ? (
                <MedicalSubsection
                  title={renderTestTitle(
                    getCampaignMedicalTestTitle(
                      "parasitologie-des-selles",
                      "Parasitologie des selles",
                    ),
                    [form.complementaryExams.parasitology.stoolExam],
                    <Bug className="h-4 w-4" />,
                  )}
                  isCollapsible={true}
                >
                  <Input
                    label="Examen des selles"
                    value={form.complementaryExams.parasitology.stoolExam}
                    onChange={(event) =>
                      updateComplementaryExams("parasitology", { stoolExam: event.target.value })
                    }
                  />
                </MedicalSubsection>
              ) : null}
            </div>

            <div className="mt-5 grid gap-5">
              {shouldShowCampaignMedicalTest("biologie") ? (
                <MedicalSubsection
                  title={renderTestTitle(getCampaignMedicalTestTitle("biologie", "Biologie"), [
                    form.bloodGroup,
                    form.complementaryExams.biology.urineChemistry,
                    form.complementaryExams.biology.cholesterol,
                    form.complementaryExams.biology.glycemia,
                    form.complementaryExams.biology.urea,
                    form.complementaryExams.biology.triglycerides,
                    form.complementaryExams.biology.hba1c,
                    form.complementaryExams.biology.creatinine,
                    form.complementaryExams.biology.hdlLdl,
                  ],
                  <FlaskConical className="h-4 w-4" />,
                )}
                  isCollapsible={true}
                >
                <div className="space-y-4">
                  <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
                    <Input
                      label="Groupe sanguin / Rhesus"
                      value={form.bloodGroup}
                      readOnly
                      className="cursor-not-allowed bg-slate-100/90 text-slate-500"
                    />
                    {[
                      ["urineChemistry", "Chimie des urines"],
                      ["cholesterol", "Cholesterol"],
                    ].map(([key, label]) => (
                      <Input
                        key={key}
                        label={label}
                        value={form.complementaryExams.biology[key as keyof ComplementaryExams["biology"]]}
                        onChange={(event) =>
                          updateComplementaryExams("biology", {
                            ...form.complementaryExams.biology,
                            [key]: event.target.value,
                          })
                        }
                      />
                    ))}
                  </div>
                  <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
                    {[
                      ["glycemia", "Glycémie"],
                      ["urea", "Urée Sanguine"],
                      ["triglycerides", "Triglycerides"],
                    ].map(([key, label]) => (
                      <Input
                        key={key}
                        label={label}
                        value={form.complementaryExams.biology[key as keyof ComplementaryExams["biology"]]}
                        onChange={(event) =>
                          updateComplementaryExams("biology", {
                            ...form.complementaryExams.biology,
                            [key]: event.target.value,
                          })
                        }
                      />
                    ))}
                  </div>
                  <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
                    {[
                      ["hba1c", "Hb A1 c"],
                      ["creatinine", "Créatinine Sanguine"],
                      ["hdlLdl", "HDL / LDL"],
                    ].map(([key, label]) => (
                      <Input
                        key={key}
                        label={label}
                        value={form.complementaryExams.biology[key as keyof ComplementaryExams["biology"]]}
                        onChange={(event) =>
                          updateComplementaryExams("biology", {
                            ...form.complementaryExams.biology,
                            [key]: event.target.value,
                          })
                        }
                      />
                    ))}
                  </div>
                </div>
                </MedicalSubsection>
              ) : null}

              {shouldShowCampaignMedicalTest("nfs-hematologie") ? (
                <MedicalSubsection
                  title={renderTestTitle(
                    getCampaignMedicalTestTitle(
                      "nfs-hematologie",
                      "NFS / Hematologie",
                    ),
                    [
                      form.complementaryExams.hematology.gr,
                      form.complementaryExams.hematology.vgm,
                      form.complementaryExams.hematology.gb,
                      form.complementaryExams.hematology.pn,
                      form.complementaryExams.hematology.hb,
                      form.complementaryExams.hematology.ccmh,
                      form.complementaryExams.hematology.lymphocytes,
                      form.complementaryExams.hematology.bem,
                      form.complementaryExams.hematology.ht,
                      form.complementaryExams.hematology.plt,
                    form.complementaryExams.hematology.vs,
                  ],
                  <TestTube className="h-4 w-4" />,
                )}
                  isCollapsible={true}
                >
                <div className="space-y-4">
                  <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
                    {[
                      ["gr", "GR"],
                      ["vgm", "VGM"],
                      ["gb", "GB"],
                      ["pn", "PN"],
                    ].map(([key, label]) => (
                      <Input
                        key={key}
                        label={label}
                        value={
                          form.complementaryExams.hematology[
                            key as keyof ComplementaryExams["hematology"]
                          ]
                        }
                        onChange={(event) =>
                          updateComplementaryExams("hematology", {
                            ...form.complementaryExams.hematology,
                            [key]: event.target.value,
                          })
                        }
                      />
                    ))}
                  </div>
                  <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
                    {[
                      ["hb", "Hb"],
                      ["ccmh", "CCMH"],
                      ["lymphocytes", "Lymphocytes"],
                      ["bem", "B.E.M"],
                    ].map(([key, label]) => (
                      <Input
                        key={key}
                        label={label}
                        value={
                          form.complementaryExams.hematology[
                            key as keyof ComplementaryExams["hematology"]
                          ]
                        }
                        onChange={(event) =>
                          updateComplementaryExams("hematology", {
                            ...form.complementaryExams.hematology,
                            [key]: event.target.value,
                          })
                        }
                      />
                    ))}
                  </div>
                  <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
                    {[
                      ["ht", "Ht"],
                      ["plt", "PLT"],
                      ["vs", "VS"],
                    ].map(([key, label]) => (
                      <Input
                        key={key}
                        label={label}
                        value={
                          form.complementaryExams.hematology[
                            key as keyof ComplementaryExams["hematology"]
                          ]
                        }
                        onChange={(event) =>
                          updateComplementaryExams("hematology", {
                            ...form.complementaryExams.hematology,
                            [key]: event.target.value,
                          })
                        }
                      />
                    ))}
                  </div>
                </div>
                </MedicalSubsection>
              ) : null}

              {shouldShowCampaignMedicalTest("radiologie") ? (
                <MedicalSubsection
                  title={renderTestTitle(getCampaignMedicalTestTitle("radiologie", "Radiologie"), [
                    form.complementaryExams.radiology.chestXray,
                    form.complementaryExams.radiology.others,
                  ],
                  <Scan className="h-4 w-4" />,
                )}
                  isCollapsible={true}
                >
                <div className="grid gap-4 md:grid-cols-2">
                  <Input
                    label="Radio pulmonaire"
                    value={form.complementaryExams.radiology.chestXray}
                    onChange={(event) =>
                      updateComplementaryExams("radiology", {
                        ...form.complementaryExams.radiology,
                        chestXray: event.target.value,
                      })
                    }
                  />
                  <Input
                    label="Autres"
                    value={form.complementaryExams.radiology.others}
                    onChange={(event) =>
                      updateComplementaryExams("radiology", {
                        ...form.complementaryExams.radiology,
                        others: event.target.value,
                      })
                    }
                  />
                </div>
                </MedicalSubsection>
              ) : null}

              {shouldShowCampaignMedicalTest("autres-examens") ? (
                <MedicalSubsection
                  title={renderTestTitle(getCampaignMedicalTestTitle("autres-examens", "Autres examens"), [
                    form.complementaryExams.otherExams.freeText,
                  ],
                  <Microscope className="h-4 w-4" />,
                )}
                  isCollapsible={true}
                >
                <label className="block space-y-2">
                  <span className="text-sm font-bold text-slate-800">Zone libre</span>
                  <textarea
                    rows={3}
                    value={form.complementaryExams.otherExams.freeText}
                    onChange={(event) =>
                      updateComplementaryExams("otherExams", {
                        freeText: event.target.value,
                      })
                    }
                    className={textareaClassName}
                  />
                </label>
                </MedicalSubsection>
              ) : null}
              <div className="space-y-6">
              {currentCampaignDynamicTests
                .filter((item) => item.sectionId === "complementaryExams")
                .map((item) => renderDynamicMedicalTestCard(item.assignment, "complementaryExams"))}
              </div>
              <MedicalSubsection
                title={renderTestTitle("Orientation", [
                  form.medicalDecision.orientation.specialty,
                  form.medicalDecision.orientation.specialistAdvice,
                  form.medicalDecision.orientation.specialistAdviceDetails,
                  form.medicalDecision.orientation.treatment,
                  form.medicalDecision.orientation.treatmentDetails,
                  form.medicalDecision.orientation.hospitalization,
                  form.medicalDecision.orientation.hospitalizationDetails,
                ],
                <Scan className="h-4 w-4" />,
              )}
                isCollapsible={true}
              >
                <div className="grid grid-cols-1 md:grid-cols-[1fr_2fr] gap-4">
                  <Textarea
                    label="Specialite"
                    rows={2}
                    value={form.medicalDecision.orientation.specialty}
                    onChange={(event) =>
                      updateMedicalDecision("orientation", {
                        ...form.medicalDecision.orientation,
                        specialty: event.target.value,
                      })
                    }
                  />
              
                {hasSpecialtyInput(form.medicalDecision.orientation.specialty) && (
                 <div className="grid grid-cols-1 gap-4">
                  <div className="grid grid-cols-1 gap-4">
                    {[
                      [
                        "specialistAdvice",
                        "Pour avis spécialisé",
                        "specialistAdviceDetails",
                      ],
                      [
                        "treatment",
                        "Pour traitement",
                        "treatmentDetails",
                      ],
                      [
                        "hospitalization",
                        "Pour hospitalisation",
                        "hospitalizationDetails",
                      ],
                    ].map(([key, label, detailKey]) => {
                      const selected =
                        form.medicalDecision.orientation[
                          key as keyof MedicalDecision["orientation"]
                        ] as boolean;

                      return (
                        <div
                          key={key}
                          onClick={() =>
                            updateMedicalDecision("orientation", {
                              ...form.medicalDecision.orientation,

                              specialistAdvice: key === "specialistAdvice",
                              treatment: key === "treatment",
                              hospitalization: key === "hospitalization",

                              specialistAdviceDetails:
                                key === "specialistAdvice"
                                  ? form.medicalDecision.orientation.specialistAdviceDetails
                                  : "",

                              treatmentDetails:
                                key === "treatment"
                                  ? form.medicalDecision.orientation.treatmentDetails
                                  : "",

                              hospitalizationDetails:
                                key === "hospitalization"
                                  ? form.medicalDecision.orientation.hospitalizationDetails
                                  : "",
                            })
                          }
                          className={`cursor-pointer rounded-2xl border p-4 transition-all duration-200 ${
                            selected
                              ? "border-cyan-500 bg-cyan-50 shadow-md"
                              : "border-slate-200 bg-white hover:border-cyan-300 hover:shadow-sm"
                          }`}
                        >
                          <div className="flex items-center gap-3">
                            <div
                              className={`flex h-5 w-5 items-center justify-center rounded-full border-2 ${
                                selected
                                  ? "border-cyan-600"
                                  : "border-slate-300"
                              }`}
                            >
                              {selected && (
                                <div className="h-2.5 w-2.5 rounded-full bg-cyan-600" />
                              )}
                            </div>

                            <span className="font-medium text-slate-900">
                              {label}
                            </span>
                          </div>

                          {selected && (
                            <div className="mt-4 border-t border-slate-200 pt-4">
                              <Input
                                label={""}
                                value={
                                  form.medicalDecision.orientation[
                                    detailKey as keyof MedicalDecision["orientation"]
                                  ] as string
                                }
                                onChange={(event) =>
                                  updateMedicalDecision("orientation", {
                                    ...form.medicalDecision.orientation,
                                    [detailKey]: event.target.value,
                                  })
                                }
                              />
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                  </div>
                )} 
                </div>
                
              </MedicalSubsection>

              <MedicalSubsection
                title={renderTestTitle("Reponse specialiste", [
                  form.medicalDecision.specialistResponse.response,
                  form.medicalDecision.specialistResponse.socialService,
                  form.medicalDecision.specialistResponse.employmentService,
                ],
                <Stethoscope className="h-4 w-4" />,
              )}
                isCollapsible={true}
              >
                <div className="grid gap-4 md:grid-cols-3">
                  <Textarea
                    label="Reponse"
                    rows={2}
                    value={form.medicalDecision.specialistResponse.response}
                    onChange={(event) =>
                      updateMedicalDecision("specialistResponse", {
                        ...form.medicalDecision.specialistResponse,
                        response: event.target.value,
                      })
                    }
                  />
                  <Textarea
                    label="Service social"
                    rows={2}
                    value={form.medicalDecision.specialistResponse.socialService}
                    onChange={(event) =>
                      updateMedicalDecision("specialistResponse", {
                        ...form.medicalDecision.specialistResponse,
                        socialService: event.target.value,
                      })
                    }
                  />
                  <Textarea
                    label="Service emploi"
                    rows={2}
                    value={form.medicalDecision.specialistResponse.employmentService}
                    onChange={(event) =>
                      updateMedicalDecision("specialistResponse", {
                        ...form.medicalDecision.specialistResponse,
                        employmentService: event.target.value,
                      })
                    }
                  />
                </div>
              </MedicalSubsection>
            </div>
          </MedicalSectionCard>
        </div>
      );
    }

    if (sectionId === "medicalDecision") {
      const aptitudeCards: Array<{
        value: MedicalDecision["aptitude"];
        label: string;
        tone: string;
      }> = [
        { value: "apte", label: "Apte", tone: "border-emerald-200 bg-emerald-50 text-emerald-700" },
        {
          value: "apte_with_restrictions",
          label: "Apte avec reserves",
          tone: "border-amber-200 bg-amber-50 text-amber-700",
        },
        {
          value: "temporarily_unfit",
          label: "Inapte temporaire",
          tone: "border-orange-200 bg-orange-50 text-orange-700",
        },
        {
          value: "definitively_unfit",
          label: "Inapte definitive",
          tone: "border-rose-200 bg-rose-50 text-rose-700",
        },
      ];

      return (
        <div className="space-y-5">
          <MedicalSectionCard
            icon={BadgeCheck}
            title="Decision medicale"
            description="Formalisez l'orientation, l'aptitude, la validation et les recommandations finales."
          >

            <div className="grid gap-5 md:grid-cols-1">
              <MedicalSubsection
                title={renderTestTitle("Résumé global des examens", [
                  form.clinicalExam.ophthalmology.observations,
                  form.clinicalExam.ent.nose,
                  form.clinicalExam.ent.ears,
                  form.clinicalExam.ent.throat,
                  form.clinicalExam.stomatology.teeth,
                  form.clinicalExam.stomatology.others,
                  form.clinicalExam.cardiovascular.dyspnea,
                  form.clinicalExam.respiratory.chronicCough,
                  form.clinicalExam.respiratory.asthma,
                  form.clinicalExam.digestive.ulcer,
                  form.clinicalExam.digestive.colopathy,
                  form.clinicalExam.digestive.hemorrhoids,
                  form.clinicalExam.digestive.others,
                  form.clinicalExam.urogenital.dysuria,
                  form.clinicalExam.urogenital.impotence,
                  form.clinicalExam.urogenital.others,
                  form.clinicalExam.endocrine.diabetes,
                  form.clinicalExam.endocrine.thyroid,
                  form.clinicalExam.endocrine.others,
                  form.clinicalExam.hematology.hemostasis,
                  form.clinicalExam.hematology.adenopathy,
                  form.clinicalExam.hematology.others,
                  form.clinicalExam.neuroPsychiatric.headachesVertigo,
                  form.clinicalExam.neuroPsychiatric.neurologicalSigns,
                  form.clinicalExam.neuroPsychiatric.personalityDisorders,
                  form.clinicalExam.neuroPsychiatric.others,
                  form.clinicalExam.osteoArticular.polyarthralgia,
                  form.clinicalExam.dermatology.lesions,
                  form.clinicalExam.dermatology.skinAllergies,
                  form.clinicalExam.dermatology.urticaria,
                  form.complementaryExams.cardiology.ecg,
                  form.complementaryExams.audiology.audiogram,
                  form.complementaryExams.respiratory.efr,
                  form.complementaryExams.parasitology.stoolExam,
                  form.complementaryExams.radiology.chestXray,
                  form.complementaryExams.radiology.others,
                  form.complementaryExams.otherExams.freeText,
                ],
                <FileText className="h-4 w-4" />,
              )}
              >
                <div className="space-y-1 text-sm">

                  {/* CLINICAL SUMMARY */}
                  <div className="border border-slate-200 bg-white shadow-sm">
                    <h3 className="mb-4 text-base font-semibold text-slate-900">
                      Examens cliniques
                    </h3>

                    <div className="grid grid-cols-1 md:grid-cols-1 gap-3">
                      {shouldShowCampaignMedicalTest("ophtalmologie") ? (
                        <SummaryCard
                          title="Ophtalmologie"
                          items={[
                            ["Observation", form.clinicalExam.ophthalmology.observations],
                          ]}
                          
                        />
                      ) : null}

                      {shouldShowCampaignMedicalTest("orl") ? (
                        <SummaryCard
                          title="ORL"
                          items={[
                            ["Nez", form.clinicalExam.ent.nose],
                            ["Oreilles", form.clinicalExam.ent.ears],
                            ["Gorge", form.clinicalExam.ent.throat],
                          ]}
                        />
                      ) : null}

                      {shouldShowCampaignMedicalTest("cardio-vasculaire") ? (
                        <SummaryCard
                          title="Cardio Vasculaire"
                          items={[
                            ["TA", form.internalVisitTa],
                            ["Dyspnée", form.clinicalExam.cardiovascular.dyspnea],
                          ]}
                        />
                      ) : null}

                      {shouldShowCampaignMedicalTest("respiratoire-clinique") ? (
                        <SummaryCard
                          title="Respiratoire"
                          items={[
                            ["Toux chronique", form.clinicalExam.respiratory.chronicCough],
                            ["Asthme", form.clinicalExam.respiratory.asthma],
                          ]}
                        />
                      ) : null}

                      {shouldShowCampaignMedicalTest("digestif") ? (
                        <SummaryCard
                          title="Digestif"
                          items={[
                            ["Ulcère", form.clinicalExam.digestive.ulcer],
                            ["Colopathie", form.clinicalExam.digestive.colopathy],
                            ["Hémorroïdes", form.clinicalExam.digestive.hemorrhoids],
                            ["Autres", form.clinicalExam.digestive.others],
                          ]}
                        />
                      ) : null}

                      {shouldShowCampaignMedicalTest("uro-genital") ? (
                        <SummaryCard
                          title="Uro-génital"
                          items={[
                            ["Dysurie", form.clinicalExam.urogenital.dysuria],
                            ["Impuissance", form.clinicalExam.urogenital.impotence],
                            ["Autres", form.clinicalExam.urogenital.others],
                          ]}
                        />
                      ) : null}

                      {shouldShowCampaignMedicalTest("endocrinien") ? (
                        <SummaryCard
                          title="Endocrinien"
                          items={[
                            ["Diabète", form.clinicalExam.endocrine.diabetes],
                            ["Thyroïde", form.clinicalExam.endocrine.thyroid],
                            ["Autres", form.clinicalExam.endocrine.others],
                          ]}
                        />
                      ) : null}
                      {shouldShowCampaignMedicalTest("acuite-visuelle-binoculaire") ? (
                        <SummaryCard
                          title="Acuité visuelle binoculaire"
                          items={[["binoculaire ODG", form.internalVisitDistanceOdg]]}
                        />
                      ) : null}
                    </div>
                  </div>

                  {/* COMPLEMENTARY EXAMS */}
                  <div className="grid grid-cols-[220px_1fr] gap-1">

                  {/* Title */}
                  <div className="border border-slate-200 bg-white p-4 shadow-sm flex items-center">
                    <h3 className="font-semibold text-slate-900">
                      Examens complémentaires
                    </h3>
                  </div>

                  {/* Results */}
                  <div className="border border-slate-200 bg-white p-4 shadow-sm">
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-y-2 gap-x-8">
                      {shouldShowCampaignMedicalTest("ecg") ? (
                        <div>
                          <span className="font-medium text-slate-600">ECG :</span>
                          <span className="text-slate-900"> {form.complementaryExams.cardiology.ecg || "-"}</span>
                        </div>
                      ) : null}
                      {shouldShowCampaignMedicalTest("biologie") ? (
                        <>
                          <div>
                            <span className="font-medium text-slate-600">Glycémie :</span>
                            <span className="text-slate-900"> {form.complementaryExams.biology.glycemia || "-"}</span>
                          </div>
                          <div>
                            <span className="font-medium text-slate-600">HbA1c :</span>
                            <span className="text-slate-900"> {form.complementaryExams.biology.hba1c || "-"}</span>
                          </div>
                          <div>
                            <span className="font-medium text-slate-600">Créatinine :</span>
                            <span className="text-slate-900"> {form.complementaryExams.biology.creatinine || "-"}</span>
                          </div>
                          <div>
                            <span className="font-medium text-slate-600">Cholestérol :</span>
                            <span className="text-slate-900"> {form.complementaryExams.biology.cholesterol || "-"}</span>
                          </div>
                          <div>
                            <span className="font-medium text-slate-600">Triglycérides :</span>
                            <span className="text-slate-900"> {form.complementaryExams.biology.triglycerides || "-"}</span>
                          </div>
                        </>
                      ) : null}
                      {shouldShowCampaignMedicalTest("efr") ? (
                        <div>
                          <span className="font-medium text-slate-600">EFR :</span>
                          <span className="text-slate-900"> {form.complementaryExams.respiratory.efr || "-"}</span>
                        </div>
                      ) : null}
                      {shouldShowCampaignMedicalTest("audiogramme") ? (
                        <div>
                          <span className="font-medium text-slate-600">Audiogramme :</span>
                          <span className="text-slate-900"> {form.complementaryExams.audiology.audiogram || "-"}</span>
                        </div>
                      ) : null}
                      {shouldShowCampaignMedicalTest("parasitologie-des-selles") ? (
                        <div>
                          <span className="font-medium text-slate-600">Parasitologie des selles :</span>
                          <span className="text-slate-900"> {form.complementaryExams.parasitology.stoolExam || "-"}</span>
                        </div>
                      ) : null}
                    </div>
                  </div>

                </div>

                  
                 

                 
                 
                </div>
              </MedicalSubsection>
              
            
            </div>
            <div className="mt-5"/>
            <div className="grid gap-5 xl:grid-cols-1">
              

              <MedicalSubsection
                title={renderTestTitle("CAT", [form.medicalDecision.cat.conduct], <ClipboardCheck className="h-4 w-4" />)}
              >
                <label className="block space-y-2">
                  <span className="text-sm font-bold text-slate-800">Conduite a tenir</span>
                  <textarea
                    rows={4}
                    value={form.medicalDecision.cat.conduct}
                    onChange={(event) =>
                      updateMedicalDecision("cat", { conduct: event.target.value })
                    }
                    className={textareaClassName}
                  />
                </label>
              </MedicalSubsection>
            </div>

            <div className="mt-5">
              <MedicalSubsection
                title={renderTestTitle("Aptitude", [form.medicalDecision.aptitude], <BadgeCheck className="h-4 w-4" />)}
                description="Selectionnez la decision finale la plus appropriee."
              >
                <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
                  {aptitudeCards.map((card) => {
                    const active = form.medicalDecision.aptitude === card.value;
                    return (
                      <button
                        key={card.value}
                        type="button"
                        onClick={() => updateMedicalDecision("aptitude", card.value)}
                        className={cn(
                          "rounded-3xl border p-4 text-left transition-all",
                          active ? card.tone : "border-slate-200 bg-white text-slate-700 hover:border-cyan-200 hover:bg-cyan-50/50",
                        )}
                      >
                        <p className="text-sm font-black">{card.label}</p>
                        <p className="mt-1 text-xs opacity-80">
                          {active ? "Decision selectionnee" : "Cliquer pour selectionner"}
                        </p>
                      </button>
                    );
                  })}
                </div>
                <label className="mt-4 block space-y-2">
                  <span className="text-sm font-bold text-slate-800">
                    Interpretation de la decision
                  </span>
                  <textarea
                    rows={1}
                    value={form.medicalDecision.interpretation.decisionInterpretation}
                    onChange={(event) =>
                      updateMedicalDecision("interpretation", {
                        decisionInterpretation: event.target.value,
                      })
                    }
                    className={textareaClassName}
                  />
                </label>
              </MedicalSubsection>
            </div>

            <div className="mt-5 grid gap-5 xl:grid-cols-1">
              <MedicalSubsection
                title={renderTestTitle("Prochaine visite", [
                  form.medicalDecision.nextVisit.nextVisitSchedule,
                  form.medicalDecision.nextVisit.nextVisitCustomMonths,
                  form.medicalDecision.nextVisit.nextVisitDate,
                ], <CalendarDays className="h-4 w-4" />)}
              >
                <div className="grid gap-4 md:grid-cols-2">
                  <Select
                    label="Echeance"
                    options={[
                      { label: "Selectionner", value: "" },
                      { label: "6 mois", value: "6_mois" },
                      { label: "12 mois", value: "12_mois" },
                      { label: "Specifique", value: "specific" },
                      { label: "A convoquer", value: "a_convoquer" },
                    ]}
                    value={form.medicalDecision.nextVisit.nextVisitSchedule}
                    onChange={(event) => {
                      const nextVisitSchedule = event.target.value;
                      const baseDate =
                        form.medicalDecision.validation.validationDate || form.internalVisitDate;
                      updateMedicalDecision("nextVisit", {
                        nextVisitSchedule,
                        nextVisitCustomMonths:
                          nextVisitSchedule === "specific"
                            ? form.medicalDecision.nextVisit.nextVisitCustomMonths
                            : "",
                        nextVisitDate: calculateNextVisitDate(
                          baseDate,
                          nextVisitSchedule,
                          form.medicalDecision.nextVisit.nextVisitCustomMonths,
                        ),
                      });
                    }}
                  />
                  <Input
                    label="Valeur specifique (mois)"
                    type="text"
                    inputMode="numeric"
                    maxLength={2}
                    value={form.medicalDecision.nextVisit.nextVisitCustomMonths}
                    readOnly={form.medicalDecision.nextVisit.nextVisitSchedule !== "specific"}
                    className={
                      form.medicalDecision.nextVisit.nextVisitSchedule !== "specific"
                        ? "cursor-not-allowed bg-slate-100/90 text-slate-500"
                        : undefined
                    }
                    onChange={(event) => {
                      const nextVisitCustomMonths = event.target.value.replace(/\D/g, "").slice(0, 2);
                      const baseDate =
                        form.medicalDecision.validation.validationDate || form.internalVisitDate;
                      updateMedicalDecision("nextVisit", {
                        ...form.medicalDecision.nextVisit,
                        nextVisitCustomMonths,
                        nextVisitDate: calculateNextVisitDate(
                          baseDate,
                          form.medicalDecision.nextVisit.nextVisitSchedule,
                          nextVisitCustomMonths,
                        ),
                      });
                    }}
                  />
                  <Input
                    label="Date prochaine visite"
                    value={formatDisplayDate(form.medicalDecision.nextVisit.nextVisitDate)}
                    readOnly
                    className="cursor-not-allowed bg-slate-100/90 text-slate-500"
                  />
                </div>
              </MedicalSubsection>

              <MedicalSubsection
                title={renderTestTitle("Validation", [
                  form.medicalDecision.validation.validatingDoctor,
                  form.medicalDecision.validation.validationDate,
                  form.medicalDecision.validation.includeValidatorSignature,
                ], <ShieldCheck className="h-4 w-4" />)}
              >
                <div className="grid gap-4 md:grid-cols-2">
                  <Input
                    label="Medecin validateur"
                    value={"Dr. " +form.medicalDecision.validation.validatingDoctor}
                    readOnly
                    className="cursor-not-allowed bg-slate-100/90 text-slate-500"
                  />
                  <Input
                    label="Date validation"
                    value={formatDisplayDate(form.medicalDecision.validation.validationDate)}
                    readOnly
                    className="cursor-not-allowed bg-slate-100/90 text-slate-500"
                  />
                  
                  <label className="flex items-center gap-3 rounded-2xl border border-slate-200 bg-slate-50/70 px-4 py-4 text-sm font-semibold text-slate-800">
                    <input
                      type="checkbox"
                      checked={form.medicalDecision.validation.includeValidatorSignature}
                      disabled={!canSignMedicalDocuments}
                      title={!canSignMedicalDocuments ? signatureAuthorizationMessage : undefined}
                      onChange={(event) =>
                        updateMedicalDecision("validation", {
                          ...form.medicalDecision.validation,
                          includeValidatorSignature: event.target.checked,
                        })
                      }
                      className="h-4 w-4 rounded border-slate-300 text-[#0085A3] focus:ring-[#0085A3]/20"
                    />
                    <span>Ajouter la signature du validateur dans le PDF</span>
                  </label>
                  <div className="rounded-2xl border border-slate-200 bg-slate-50/70 px-4 py-4 text-sm text-slate-600">
                    {!canSignMedicalDocuments
                      ? signatureAuthorizationMessage
                      : currentUserHasSignature
                      ? "Une signature PNG est configuree dans votre profil."
                      : "Veuillez televerser votre signature PNG dans les parametres avant de signer."}
                  </div>
                </div>
              </MedicalSubsection>
            </div>
          </MedicalSectionCard>
        </div>
      );
    }

if (sectionId === "medicalOrientation") {
  return (
    <div className="space-y-5">
      <MedicalSectionCard
        icon={Stethoscope}
        title="Orientations Médicales (Demande d'Avis Spécialiste)"
        description="Gérez une ou plusieurs orientations médicales par travailleur."
      >
        <div className="grid gap-5 xl:grid-cols-1">
          {/* ─── Liste des orientations existantes ─── */}
          <Card className="rounded-3xl border-slate-200/90 p-5">
            <div className="flex items-center justify-between gap-3">
              <div>
                <h3 className="text-base font-black text-slate-950">Orientations enregistrées</h3>
                <p className="mt-1 text-sm text-slate-500">
                  Plusieurs orientations peuvent être rattachées au même travailleur.
                </p>
              </div>
              <Button
                variant="secondary"
                size="sm"
                icon={Plus}
                onClick={() => {
                  handleCreateOrientationDraft();
                }}
              >
                Nouvelle
              </Button>
            </div>

            <div className="mt-4 space-y-3">
              {orientationLoading ? (
                <div className="flex min-h-[160px] items-center justify-center rounded-3xl border border-slate-200 bg-slate-50/70">
                  <Spinner />
                </div>
              ) : orientations.length > 0 ? (
                orientations.map((item) => {
                  const active = item.id === orientationForm.id;
                  
                  return (
                    <button
                      key={item.id}
                      type="button"
                      onClick={() => handleSelectOrientation(item)}
                      className={cn(
                        "w-full rounded-3xl border p-4 text-left transition-all",
                        active
                          ? "border-cyan-200 bg-cyan-50/80 shadow-sm"
                          : "border-slate-200 bg-white hover:border-slate-300 hover:bg-slate-50",
                      )}
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <p className="text-sm font-black text-slate-950">
                            {item.orientation_number || `Orientation #${item.id}`}
                          </p>
                          <p className="mt-1 text-xs text-slate-500">{formatDisplayDate(item.orientation_date)}</p>
                        </div>
                        <span
                          className={cn(
                            "rounded-full px-2.5 py-1 text-[11px] font-black uppercase tracking-[0.08em]",
                            item.status === "signed"
                              ? "bg-emerald-100 text-emerald-700"
                              : "bg-amber-100 text-amber-700",
                          )}
                        >
                          {item.status}
                        </span>
                      </div>
                      <p className="mt-3 line-clamp-2 text-sm text-slate-600">
                        {item.orientation_type || "Aucun type renseigné"}
                        {item.orientation_type_other ? ` — ${item.orientation_type_other}` : ""}
                      </p>
                    </button>
                  );
                })
              ) : (
                <div className="rounded-3xl border border-dashed border-slate-300 bg-slate-50/70 p-5 text-sm text-slate-500">
                  Aucune orientation enregistrée pour ce travailleur dans cette campagne.
                </div>
              )}
            </div>
          </Card>

          {/* ─── Formulaire d'orientation active ─── */}
          <div className="space-y-5">
            {isCreateMode ? (
              <div className="rounded-3xl border border-amber-200 bg-amber-50/80 p-5 text-sm font-semibold text-amber-800">
                Enregistrez d'abord le travailleur pour activer les orientations en base.
              </div>
            ) : null}

            <div className="rounded-[30px] border border-slate-200 bg-white shadow-sm">
              <div className="rounded-[0.3rem] border border-cyan-100 bg-gradient-to-br from-cyan-50 via-white to-emerald-50 p-6">
                {/* Header */}
                <div className="flex flex-wrap items-start justify-between border-b border-slate-200">
                  <div>
                    <p className="text-xs font-black uppercase tracking-[0.16em] text-cyan-700">
                      Service de médecine du travail
                    </p>
                    <h3 className="mt-2 text-xl font-black text-slate-950">
                      {currentCampaign?.company_name || "Clinique"}
                    </h3>
                    <p className="mt-1 text-sm text-slate-500">
                      {currentCampaign?.site_name || currentCampaign?.branch_name || "Ouargla"}
                    </p>
                  </div>
                  <div className="min-w-[200px] text-right">
                    <p className="text-xs font-bold uppercase tracking-[0.14em] text-slate-400">
                      Statut
                    </p>
                    <p className="mt-2 text-lg font-black text-slate-950">{orientationForm.status}</p>
                  </div>
                </div>

                {/* Titre */}
                <div className="py-5 text-center">
                  <p className="text-3xl font-black tracking-[0.26em] text-slate-950">
                    ORIENTATION MÉDICALE
                  </p>
                </div>

                {/* Champs principaux */}
                <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-[2fr_0.5fr_2fr_2fr]">
                  {orientationForm.orientation_number && (
                    <Input
                      label="ID Orientation"
                      value={orientationForm.id ? `#${orientationForm.id}` : "Nouveau"}
                      readOnly
                      className="cursor-not-allowed bg-slate-100/90 text-slate-500"
                    />
                  )}
                  {/* Orientation number and date 
                  <Input
                    label="Numéro orientation"
                    value={orientationForm.orientation_number}
                    onChange={(e) =>
                      updateOrientationField("orientation_number", e.target.value)
                    }
                  />
                  */}
  
                  <Input
                    label="Date orientation"
                    type="date"
                    value={orientationForm.orientation_date}
                    onChange={(e) =>
                      updateOrientationField("orientation_date", e.target.value)
                    }
                  />
                  <Input
                    label="Âge"
                    value={calculateAgeFromDate(worker?.birth_date) || ""}
                    readOnly
                    className="cursor-not-allowed bg-slate-100/90 text-slate-500"
                  />
                  <Input
                    label="Nom et Prénom patient"
                    value={worker?.full_name || ""}
                    readOnly
                    className="cursor-not-allowed bg-slate-100/90 text-slate-500 md:col-span-2"
                  />
                  <Input
                    label="Médecin prescripteur"
                    value={form.medicalDecision.validation.validatingDoctor}
                    onChange={(e) =>
                      updateOrientationField("doctor_name", e.target.value)
                    }
                  />
                </div>

                {/* Type d'orientation */}
                <div className="mt-5 space-y-4">
                  <span className="text-sm font-bold tracking-[0.01em] text-slate-800">
                    Type d'orientation
                  </span>

                  <div className="grid gap-3 md:grid-cols-[0.8fr_2fr_0.5fr]">
                    <label className="flex items-center gap-3 rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm font-semibold text-slate-800">
                      <input
                        type="checkbox"
                        checked={orientationForm.orientationTypes?.specialistAdvice ?? false}
                        onChange={(e) =>
                          updateOrientationField("orientationTypes", {
                            ...orientationForm.orientationTypes,
                            specialistAdvice: e.target.checked,
                          })
                        }
                      />
                      Avis Spécialisé
                    </label>

                    <label className="flex items-center gap-3 rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm font-semibold text-slate-800">
                      <input
                        type="checkbox"
                        checked={orientationForm.orientationTypes?.diagnosticCare ?? false}
                        onChange={(e) =>
                          updateOrientationField("orientationTypes", {
                            ...orientationForm.orientationTypes,
                            diagnosticCare: e.target.checked,
                          })
                        }
                      />
                      Pris en charge diagnostic , traitement et Suivi
                    </label>

                    <label className="flex items-center gap-3 rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm font-semibold text-slate-800">
                      <input
                        type="checkbox"
                        checked={orientationForm.orientationTypes?.other ?? false}
                        onChange={(e) =>
                          updateOrientationField("orientationTypes", {
                            ...orientationForm.orientationTypes,
                            other: e.target.checked,
                          })
                        }
                      />
                      Autres
                    </label>
                  </div>

                  {orientationForm.orientationTypes?.other && (
                    <Textarea
                      label="Précisez"
                      rows={3}
                      value={orientationForm.orientationTypeOther}
                      onChange={(e) =>
                        updateOrientationField("orientationTypeOther", e.target.value)
                      }
                    />
                  )}
                </div>

                {/* Détails / Conduct */}
                <div className="mt-5 grid gap-4">
                  <Textarea
                    label="Détails de l'orientation"
                    rows={4}
                    value={orientationForm.orientation_details}
                    onChange={(e) =>
                      updateOrientationField("orientation_details", e.target.value)
                    }
                    placeholder="Motif, observations cliniques, recommandations pour le spécialiste..."
                  />
                </div>

                {/* Observations cliniques rapides */}
                <div className="mt-6 rounded-[26px] border border-slate-200 bg-white p-5">
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <div>
                      <p className="text-base font-black text-slate-950">
                        Observations cliniques disponibles
                      </p>
                      <p className="mt-1 text-sm text-slate-500">
                        Cliquez sur un élément pour l'ajouter automatiquement aux détails.
                      </p>
                    </div>
                  </div>

                  {(() => {
                    const clinicalFields: Array<{ label: string; value: string }> = [
                      { label: "Ophtalmologie", value: form.clinicalExam.ophthalmology.observations },
                      { label: "Nez", value: form.clinicalExam.ent.nose },
                      { label: "Oreilles", value: form.clinicalExam.ent.ears },
                      { label: "Gorge", value: form.clinicalExam.ent.throat },
                      { label: "Denture", value: form.clinicalExam.stomatology.teeth },
                      { label: "Autres Stomatologie", value: form.clinicalExam.stomatology.others },
                      { label: "TA", value: form.clinicalExam.cardiovascular.bloodPressure },
                      { label: "Dyspnée", value: form.clinicalExam.cardiovascular.dyspnea },
                      { label: "Toux chronique", value: form.clinicalExam.respiratory.chronicCough },
                      { label: "Asthme", value: form.clinicalExam.respiratory.asthma },
                      { label: "Ulcère", value: form.clinicalExam.digestive.ulcer },
                      { label: "Colopathie", value: form.clinicalExam.digestive.colopathy },
                      { label: "Hémorroïdes", value: form.clinicalExam.digestive.hemorrhoids },
                      { label: "Autres Digestif", value: form.clinicalExam.digestive.others },
                      { label: "Dysurie", value: form.clinicalExam.urogenital.dysuria },
                      { label: "Impuissance", value: form.clinicalExam.urogenital.impotence },
                      { label: "Autres Uro-génital", value: form.clinicalExam.urogenital.others },
                      { label: "Diabète", value: form.clinicalExam.endocrine.diabetes },
                      { label: "Thyroïde", value: form.clinicalExam.endocrine.thyroid },
                      { label: "Autres Endocrinologie", value: form.clinicalExam.endocrine.others },
                      { label: "Hemostase", value: form.clinicalExam.hematology.hemostasis },
                      { label: "Adénopathie", value: form.clinicalExam.hematology.adenopathy },
                      { label: "Autres Hématologie", value: form.clinicalExam.hematology.others },
                      { label: "Céphalées / Vertiges", value: form.clinicalExam.neuroPsychiatric.headachesVertigo },
                      { label: "Signes neurologiques", value: form.clinicalExam.neuroPsychiatric.neurologicalSigns },
                      { label: "Troubles personnalité", value: form.clinicalExam.neuroPsychiatric.personalityDisorders },
                      { label: "Polyarthralgies", value: form.clinicalExam.osteoArticular.polyarthralgia },
                      { label: "Lésions", value: form.clinicalExam.dermatology.lesions },
                      { label: "Allergies cutanées", value: form.clinicalExam.dermatology.skinAllergies },
                      { label: "Urticaire", value: form.clinicalExam.dermatology.urticaria },
                      { label: "ECG", value: form.complementaryExams.cardiology.ecg },
                      { label: "Audiogramme", value: form.complementaryExams.audiology.audiogram },
                      { label: "EFR", value: form.complementaryExams.respiratory.efr },
                      { label: "Glycémie", value: form.complementaryExams.biology.glycemia },
                      { label: "HbA1c", value: form.complementaryExams.biology.hba1c },
                      { label: "Créatinine", value: form.complementaryExams.biology.creatinine },
                      { label: "Cholestérol", value: form.complementaryExams.biology.cholesterol },
                      { label: "Triglycérides", value: form.complementaryExams.biology.triglycerides },
                      { label: "Radio thorax", value: form.complementaryExams.radiology.chestXray },
                    ].filter((f) => Boolean(f.value.trim()));

                    const appendToDetails = (label: string, value: string) => {
                      const line = `${label}: ${value}`;
                      const current = orientationForm.orientation_details;
                      const already = current.includes(line);
                      updateOrientationField(
                        "orientation_details",
                        already
                          ? current.replace(`\n${line}`, "").replace(line, "").trim()
                          : current
                          ? `${current}\n${line}`
                          : line,
                      );
                    };

                    return (
                      <div className="mt-4 space-y-4">
                        {clinicalFields.length > 0 && (
                          <div className="flex flex-wrap gap-2">
                            {clinicalFields.map((f) => {
                              const line = `${f.label}: ${f.value}`;
                              const active = orientationForm.orientation_details.includes(line);
                              return (
                                <button
                                  key={f.label}
                                  type="button"
                                  onClick={() => appendToDetails(f.label, f.value)}
                                  className={cn(
                                    "rounded-full border px-3 py-1 text-xs font-semibold transition-all",
                                    active
                                      ? "border-cyan-400 bg-cyan-50 text-cyan-700"
                                      : "border-slate-200 bg-white text-slate-600 hover:border-cyan-200 hover:bg-cyan-50/50",
                                  )}
                                >
                                  {active ? "✓ " : ""}{f.label}
                                </button>
                              );
                            })}
                          </div>
                        )}
                      </div>
                    );
                  })()}
                </div>

                <div className="mt-6 grid gap-5 xl:grid-cols-[1fr,0.3fr]">
                  <div className="rounded-3xl border border-slate-200 bg-white/80 p-5">
                    <p className="text-sm font-black text-slate-950">Médecin validateur</p>

                    <div className="mt-3 grid gap-4 md:grid-cols-2">
                      <Input
                        label="Médecin validateur"
                        value={orientationForm.validatorName || ""}
                        readOnly
                        className="cursor-not-allowed bg-slate-100/90 text-slate-500"
                      />

                      <Input
                        label="Date validation"
                        value={formatDisplayDate(orientationForm.validatedAt)}
                        readOnly
                        className="cursor-not-allowed bg-slate-100/90 text-slate-500"
                      />
                    </div>
                  </div>

                  <div className="rounded-3xl border border-dashed border-slate-300 bg-white/80 p-5 text-right">
                    <p className="text-xs font-black uppercase tracking-[0.14em] text-slate-400">
                      Signature
                    </p>
                    {(orientationForm.status === "confirmed" || orientationForm.status === "validated") &&
                    orientationForm.includeValidatorSignature === true &&
                    orientationForm.validatorSignatureUrl ? (
                      <img
                        src={orientationForm.validatorSignatureUrl}
                        alt="Signature du validateur"
                        className="ml-auto mt-4 max-h-24 max-w-full object-contain"
                      />
                    ) : orientationForm.status === "confirmed" || orientationForm.status === "validated" ? (
                      orientationForm.includeValidatorSignature === true && !orientationForm.validatorSignatureUrl ? (
                        <p className="mt-6 text-sm text-amber-700">
                          Signature du médecin validateur indisponible pour ce certificat.
                        </p>
                      ) : (
                        <p className="mt-6 text-sm text-slate-600">
                          La signature du validateur n&apos;est pas incluse pour ce certificat.
                        </p>
                      )
                    ) : (
                      <p className="mt-8 text-sm font-bold text-slate-900">
                        {orientationForm.validatorName || "Médecin validateur"}
                      </p>
                    )}
                  </div>
                </div>

                <div className="mt-6 border-t border-slate-200 pt-4 text-center text-xs font-semibold tracking-[0.08em] text-slate-500">
                  {currentCampaign?.company_name || "Clinique"} |{" "}
                  {currentCampaign?.site_name || currentCampaign?.branch_name || form.siteName || "Ouargla"} |{" "}
                  Certificat prêt pour impression
                </div>
              </div>
            </div>

            {/* ─── PDF Orientation ─── */}
            <MedicalSubsection title={renderTestTitle("PDF Orientation Médicale", [orientationForm.orientation_number, orientationForm.orientation_date, Object.values(orientationForm.orientationTypes).some(Boolean) ? "type" : "", orientationForm.orientation_details], <FileText className="h-4 w-4" />)}>
              <div className="rounded-sm border border-slate-200 bg-slate-50/70 p-5">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <p className="text-sm font-black text-slate-900">Orientation générée</p>
                    <p className="mt-1 text-sm text-slate-500">
                      Affichez le rendu PDF final avant impression ou téléchargement.
                    </p>
                  </div>
                  <div className="flex flex-wrap items-center gap-3">
                    <Button
                      variant="secondary"
                      icon={FileDown}
                      onClick={handleLoadOrientationPdfPreview}
                      loading={orientationPdfPreviewLoading}
                      disabled={isCreateMode}
                    >
                      Afficher le PDF
                    </Button>
                  </div>
                </div>
                <div className="mt-3 rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-600">
                  {!canSignMedicalDocuments
                    ? signatureAuthorizationMessage
                    : currentUserHasSignature
                    ? ""
                    : "Aucune signature PNG n'est configurée dans votre profil signataire."}
                </div>
              </div>

              {isCreateMode ? (
                <div className="rounded-sm border border-amber-200 bg-amber-50/70 p-8 text-center">
                  <p className="text-base font-black text-amber-800">Aperçu PDF indisponible</p>
                  <p className="mt-2 text-sm text-amber-700">
                    Enregistrez d'abord le travailleur et l'orientation pour afficher le PDF.
                  </p>
                </div>
              ) : orientationPdfPreviewLoading ? (
                <div className="flex min-h-[50vh] items-center justify-center rounded-sm border border-slate-200 bg-white">
                  <Spinner />
                </div>
              ) : orientationPdfPreviewUrl ? (
                <div className="overflow-hidden rounded-sm border border-slate-200 bg-white shadow-sm">
                  <iframe
                    title="Orientation Médicale PDF"
                    src={orientationPdfPreviewUrl}
                    className="h-[170vh] w-full"
                  />
                </div>
              ) : (
                <div className="rounded-sm border border-dashed border-slate-300 bg-white p-10 text-center">
                  <p className="text-base font-black text-slate-900">Aucun PDF affiché</p>
                  <p className="mt-2 text-sm text-slate-500">
                    Cliquez sur <span className="font-semibold text-slate-700">Afficher le PDF</span> pour charger l'orientation générée.
                  </p>
                </div>
              )}
            </MedicalSubsection>

            {/* ─── Actions ─── */}
            <MedicalSubsection title={renderTestTitle("Actions orientation", [orientationForm.id, orientationForm.status], <BadgeCheck className="h-4 w-4" />)}>
              <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
                <Button
                  variant="secondary"
                  icon={Save}
                  onClick={handleSaveOrientationDraft}
                  loading={orientationSaving}
                >
                  Enregistrer brouillon
                </Button>
                <Button
                  variant="secondary"
                  icon={FileText}
                  onClick={handleSignOrientation}
                  loading={orientationSaving && canSignOrientation}
                  disabled={!canSignOrientation || !canSignMedicalDocuments || isCreateMode}
                  title={!canSignMedicalDocuments ? signatureAuthorizationMessage : undefined}
                >
                  Signer orientation
                </Button>
                <Button
                  variant="secondary"
                  icon={FileDown}
                  onClick={handleDownloadOrientationPdf}
                  loading={orientationPdfDownloading}
                  disabled={isCreateMode}
                >
                  Télécharger PDF
                </Button>
                <Button
                  variant="secondary"
                  icon={Printer}
                  onClick={handlePrintOrientation}
                  loading={orientationPrinting}
                  disabled={isCreateMode}
                >
                  Imprimer
                </Button>
                <Button
                  variant="ghost"
                  icon={Trash2}
                  onClick={handleDeleteOrientation}
                  disabled={isCreateMode || !orientationForm.id}
                >
                  Supprimer orientation
                </Button>
                <Button
                variant="secondary"
                size="sm"
                icon={Plus}
                onClick={() => {
                  handleCreateOrientationDraft();
                }}
              >
                Ajouter
              </Button>
              </div>
            </MedicalSubsection>
          </div>
        </div>
      </MedicalSectionCard>
    </div>
  );
}

if (sectionId === "medicalAptitude") {
  const aptitudeCards: Array<{
    value: MedicalDecision["aptitude"];
    label: string;
    tone: string;
  }> = [
    { value: "apte", label: "Apte", tone: "border-emerald-200 bg-emerald-50 text-emerald-700" },
    { value: "apte_with_restrictions", label: "Apte avec réserves", tone: "border-amber-200 bg-amber-50 text-amber-700" },
    { value: "temporarily_unfit", label: "Inapte temporaire", tone: "border-orange-200 bg-orange-50 text-orange-700" },
    { value: "definitively_unfit", label: "Inapte définitive", tone: "border-rose-200 bg-rose-50 text-rose-700" },
  ];

  // dossier number formatted as 00001, 00002...
  const dossierNumber = form.medicalFileNumber
    ? String(form.medicalFileNumber).replace(/\D/g, "").padStart(5, "0")
    : "00001";

  const fullName = worker?.full_name || `${form.firstName} ${form.lastName}`.trim() || "";
  const [lastName, ...firstParts] = fullName.split(" ");
  const firstName = firstParts.join(" ");
  const handleSelectAptitudeCertificate = (certificate: AptitudeCertificate) => {
    setAptitudeCertificate(certificate);
    setIsEditingAptitudeCertificate(false);
    setAptitudeForm(
      createEmptyMedicalAptitudeFormState(
        certificate,
        worker,
        Number(campaignId),
        medicalVisit?.id || aptitudeForm.medicalVisitId,
        doctorName,
      ),
    );
    setAptitudePdfPreviewUrl(null);
  };

  return (
    <div className="space-y-5">
      <MedicalSectionCard
        icon={CheckCircle2}
        title="Certificat d'aptitude"
        description="Verifiez les informations du travailleur et completez les informations du certificat avant validation."
      >
        <div className="grid gap-5">
          <Card className="rounded-3xl border-slate-200/90 p-5">
            <div className="flex items-center justify-between gap-3">
              <div>
                <h3 className="text-base font-black text-slate-950">Certificat d'aptitude</h3>
                <p className="mt-1 text-sm text-slate-500">
                  Chaque visite medicale conserve un seul certificat d&apos;aptitude.
                </p>
              </div>
              <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-black uppercase tracking-[0.08em] text-slate-600">
                {isAptitudeValidated ? "Validé" : "Brouillon"}
              </span>
            </div>

            <div className="mt-4 space-y-3">
              {isCreateMode ? (
                <div className="rounded-3xl border border-dashed border-slate-300 bg-slate-50/70 p-5 text-sm text-slate-500">
                  Enregistrez d&apos;abord le travailleur pour afficher les certificats d&apos;aptitude.
                </div>
              ) : aptitudeCertificates.length > 0 ? (
                aptitudeCertificates.map((item) => {
                  const active = item.id === activeAptitudeCertificateId;
                  return (
                    <button
                      key={item.id}
                      type="button"
                      onClick={() => handleSelectAptitudeCertificate(item)}
                      disabled={isAptitudeValidated && item.id !== activeAptitudeCertificateId}
                      className={cn(
                        "w-full rounded-3xl border p-4 text-left transition-all",
                        active
                          ? "border-cyan-200 bg-cyan-50/80 shadow-sm"
                          : "border-slate-200 bg-white hover:border-slate-300 hover:bg-slate-50",
                      )}
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <p className="text-sm font-black text-slate-950">
                            {item.certificate_number || `Certificat #${item.id}`}
                          </p>
                          <p className="mt-1 text-xs text-slate-500">
                            {formatDisplayDate(item.issue_date) || "Date inconnue"}
                          </p>
                        </div>
                        <span
                          className={cn(
                            "rounded-full px-2.5 py-1 text-[11px] font-black uppercase tracking-[0.08em]",
                            aptitudeForm.status === "confirmed"
                              ? "bg-emerald-100 text-emerald-700"
                              : "bg-amber-100 text-amber-700",
                          )}
                        >
                          {aptitudeForm.status}
                        </span>
                      </div>
                      <p className="mt-3 line-clamp-2 text-sm text-slate-600">
                        {item.aptitude || "Aucune aptitude renseignée"}
                        {item.doctor_name ? ` — Dr. ${item.doctor_name}` : ""}
                      </p>
                    </button>
                  );
                })
              ) : (
                <div className="rounded-3xl border border-dashed border-slate-300 bg-slate-50/70 p-5 text-sm text-slate-500">
                  Aucune aptitude enregistrée pour ce travailleur dans cette campagne.
                </div>
              )}
            </div>
          </Card>

          <div className="rounded-[30px] border border-slate-200 bg-white shadow-sm">
            <div className="rounded-[0.3rem] border border-cyan-100 bg-gradient-to-br from-cyan-50 via-white to-emerald-50 p-6">
              <div className="flex flex-wrap items-start justify-between border-b border-slate-200 pb-5">
                <div>
                  <p className="text-xs font-black uppercase tracking-[0.16em] text-cyan-700">
                    Service de médecine du travail
                  </p>
                  <h3 className="mt-2 text-xl font-black text-slate-950">
                    {currentCampaign?.company_name || aptitudeForm.companyName || "Clinique"}
                  </h3>
                  <p className="mt-1 text-sm text-slate-500">
                    {currentCampaign?.site_name || currentCampaign?.branch_name || form.siteName || "Ouargla"}
                  </p>
                </div>
                <div className="min-w-[200px] text-right">
                  <p className="text-xs font-bold uppercase tracking-[0.14em] text-slate-400">
                    Statut certificat
                  </p>
                  <p className="mt-2 text-lg font-black text-slate-950">
                    {isAptitudeValidated ? "Confirmé" : "Brouillon"}
                  </p>
                </div>
              </div>

              <div className="py-5 text-center">
                <p className="text-2xl font-black tracking-[0.18em] text-slate-950 md:text-3xl">
                  CERTIFICAT MÉDICAL D&apos;APTITUDE
                </p>
              </div>

              <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-[2fr_1fr_2fr]">
                <Input
                  label="Numéro certificat"
                  value={aptitudeForm.certificateNumber}
                  readOnly
                  className="cursor-not-allowed bg-slate-100/90 text-slate-500"
                />
                <Input
                  label="Date certificat"
                  type="date"
                  value={aptitudeForm.issueDate}
                  readOnly={isAptitudeReadOnly}
                  disabled={isAptitudeReadOnly}
                  className={cn(isAptitudeReadOnly ? "cursor-not-allowed bg-slate-100/90 text-slate-500" : "")}
                  onChange={(e) => updateAptitudeField("issueDate", e.target.value)}
                />
                <Input
                  label="Nom"
                  value={aptitudeForm.lastName || lastName}
                  readOnly
                  className="cursor-not-allowed bg-slate-100/90 text-slate-500"
                />
                <Input
                  label="Prénom"
                  value={aptitudeForm.firstName || firstName}
                  readOnly
                  className="cursor-not-allowed bg-slate-100/90 text-slate-500"
                />
                <Input
                  label="Date de naissance"
                  value={formatDisplayDate(aptitudeForm.birthDate || form.dateOfBirth)}
                  readOnly
                  className="cursor-not-allowed bg-slate-100/90 text-slate-500"
                />
                <Input
                  label="Lieu de naissance"
                  value={aptitudeForm.birthPlace || form.birthPlace}
                  readOnly
                  className="cursor-not-allowed bg-slate-100/90 text-slate-500"
                />
                <Input
                  label="Groupe sanguin"
                  value={aptitudeForm.bloodGroup || form.bloodGroup}
                  readOnly
                  className="cursor-not-allowed bg-slate-100/90 text-slate-500"
                />
                <Input
                  label="Rhésus"
                  value={
                    form.bloodGroup
                      ? form.bloodGroup.includes("+")
                        ? "Positif (+)"
                        : "Négatif (-)"
                      : ""
                  }
                  readOnly
                  className="cursor-not-allowed bg-slate-100/90 text-slate-500"
                />
                <Input
                  label="Poste de travail"
                  value={form.position || aptitudeForm.jobTitle}
                  readOnly
                  className="cursor-not-allowed bg-slate-100/90 text-slate-500"
                />
                <Input
                  label="Entreprise"
                  value={aptitudeForm.companyName || form.companyName}
                  readOnly
                  className="cursor-not-allowed bg-slate-100/90 text-slate-500"
                />
                <Input
                  label="Date de visite"
                  type="date"
                  value={aptitudeForm.visitDate || new Date().toISOString().slice(0, 10)}
                  readOnly={isAptitudeReadOnly}
                  disabled={isAptitudeReadOnly}
                  className={cn(isAptitudeReadOnly ? "cursor-not-allowed bg-slate-100/90 text-slate-500" : "")}
                  onChange={(e) => updateAptitudeField("visitDate", e.target.value)}
                />
                <Input
                  label="Prochaine visite"
                  value={formatDisplayDate(form.medicalDecision.nextVisit.nextVisitDate)}
                  readOnly
                  className="cursor-not-allowed bg-slate-100/90 text-slate-500"
                />
              </div>

              <div className="mt-4 rounded-[0.3rem] border border-slate-200 bg-white p-2">
                <div className="mb-4">
                  <p className="text-base font-black text-slate-950">Décision médicale</p>
                  <p className="mt-1 text-sm text-slate-500">
                    Qualification de l&apos;aptitude, interprétation et recommandations du médecin du travail.
                  </p>
                </div>

                <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
                  {aptitudeCards.map((card) => {
                    const active = form.medicalDecision.aptitude === card.value;
                    return (
                      <button
                        key={card.value}
                        type="button"
                        onClick={() => updateAptitudeField("aptitude", card.value)}
                        disabled={isAptitudeReadOnly}
                        className={cn(
                          "rounded-3xl border p-4 text-left transition-all",
                          active
                            ? card.tone
                            : "border-slate-200 bg-white text-slate-700 hover:border-cyan-200 hover:bg-cyan-50/50",
                        )}
                      >
                        <p className="text-sm font-black">{card.label}</p>
                        <p className="mt-1 text-xs opacity-80">
                          {active ? "Sélectionnée" : "Cliquer pour sélectionner"}
                        </p>
                      </button>
                    );
                  })}
                </div>

                <div className="mt-5 grid gap-4 md:grid-cols-2">
                  <Input
                    label="Aptitude"
                    value={form.medicalDecision.aptitude}
                    readOnly
                    className="cursor-not-allowed bg-slate-100/90 text-slate-500"
                  />
                  <Input
                    label="Interprétation du médecin"
                    value={form.medicalDecision.interpretation.decisionInterpretation}
                    readOnly
                    className="cursor-not-allowed bg-slate-100/90 text-slate-500"
                  />
                </div>

                <label className="mt-5 block space-y-2">
                  <span className="text-sm font-bold tracking-[0.01em] text-slate-800">
                    Recommandations du médecin
                  </span>
                  <textarea
                    rows={3}
                    value={aptitudeForm.doctorRecommendations}
                    readOnly={isAptitudeReadOnly}
                    disabled={isAptitudeReadOnly}
                    onChange={(e) => updateAptitudeField("doctorRecommendations", e.target.value)}
                    className={cn(textareaClassName, isAptitudeReadOnly ? "cursor-not-allowed bg-slate-100/90 text-slate-500" : "")}
                  />
                </label>
              </div>

              <div className="mt-6 grid gap-5 xl:grid-cols-[1fr,0.3fr]">
                <div className="rounded-[0.3rem] border border-slate-200 bg-white/80 p-5">
                  
                  <div className="grid gap-4 md:grid-cols-2">
                    <Input
                      label="Médecin validateur"
                      value={aptitudeForm.validatedDoctorName || ""}
                      readOnly
                      className="cursor-not-allowed bg-slate-100/90 text-slate-500"
                    />
                    <Input
                      label="Date validation"
                      value={formatDisplayDate(aptitudeForm.validatedAt)}
                      readOnly
                      className="cursor-not-allowed bg-slate-100/90 text-slate-500"
                    />
                  </div>
                </div>
                <div className="rounded-3xl border border-dashed border-slate-300 bg-white/80 p-5 text-right">
                  <p className="text-xs font-black uppercase tracking-[0.14em] text-slate-400">
                    Signature
                  </p>
                  {shouldShowValidatorSignature && aptitudeForm.validatorSignatureUrl ? (
                    <img
                      src={aptitudeForm.validatorSignatureUrl}
                      alt="Signature du validateur"
                      className="ml-auto mt-4 max-h-24 max-w-full object-contain"
                    />
                  ) : validatorSignatureMissing ? (
                    <p className="mt-6 text-sm text-amber-700">Signature du médecin validateur indisponible pour ce certificat.</p>
                  ) : isAptitudeValidated && !aptitudeForm.includeValidatorSignature && !aptitudeForm.validatorSignatureUrl ? (
                    <p className="mt-6 text-sm text-slate-600">La signature du validateur n&apos;est pas incluse pour ce certificat.</p>
                  ) : (
                    <p className="mt-8 text-sm font-bold text-slate-900">
                      {aptitudeForm.validatedDoctorName || "Médecin validateur"}
                    </p>
                  )}
                </div>
              </div>

              <div className="mt-6 border-t border-slate-200 pt-4 text-center text-xs font-semibold tracking-[0.08em] text-slate-500">
                {currentCampaign?.company_name || aptitudeForm.companyName || "Clinique"} | {currentCampaign?.site_name || currentCampaign?.branch_name || form.siteName || "Ouargla"} | Certificat prêt pour impression
              </div>
            </div>
          </div>

          <MedicalSubsection title={renderTestTitle("PDF certificat d'aptitude", [
            aptitudeForm.aptitude,
            aptitudeForm.doctorRecommendations,
            aptitudeForm.issueDate,
          ], <FileText className="h-4 w-4" />)}>
            <div className="rounded-sm border border-slate-200 bg-slate-50/70 p-5">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <p className="text-sm font-black text-slate-900">Certificat généré</p>
                  <p className="mt-1 text-sm text-slate-500">
                    Affichez le rendu PDF final avant impression ou téléchargement.
                  </p>
                </div>
                <div className="flex flex-wrap items-center gap-3">
                  <Button
                    variant="secondary"
                    icon={FileDown}
                    onClick={handleLoadAptitudePdfPreview}
                    loading={aptitudePdfPreviewLoading}
                    disabled={!activeAptitudeCertificateId}
                  >
                    Afficher le PDF
                  </Button>
                </div>
              </div>
              <div className="mt-3 rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-600">
                {!canSignMedicalDocuments
                  ? signatureAuthorizationMessage
                  : currentUserHasSignature
                  ? ""
                  : "Veuillez ajouter votre signature PNG dans les paramètres avant de valider ce certificat."}
              </div>
            </div>

            {!activeAptitudeCertificateId ? (
              <div className="rounded-sm border border-amber-200 bg-amber-50/70 p-8 text-center">
                <p className="text-base font-black text-amber-800">Aperçu PDF indisponible</p>
                <p className="mt-2 text-sm text-amber-700">
                  Enregistrez d'abord le travailleur et le certificat pour afficher le PDF.
                </p>
              </div>
            ) : aptitudePdfPreviewLoading ? (
              <div className="flex min-h-[50vh] items-center justify-center rounded-sm border border-slate-200 bg-white">
                <Spinner />
              </div>
            ) : aptitudePdfPreviewUrl ? (
              <div className="overflow-hidden rounded-sm border border-slate-200 bg-white shadow-sm">
                <iframe
                  title="Certificat m�dical d'aptitude PDF"
                  src={aptitudePdfPreviewUrl}
                  className="h-[170vh] w-full"
                />
              </div>
            ) : (
              <div className="rounded-sm border border-dashed border-slate-300 bg-white p-10 text-center">
                <p className="text-base font-black text-slate-900">Aucun PDF affiché</p>
                <p className="mt-2 text-sm text-slate-500">
                  Cliquez sur <span className="font-semibold text-slate-700">Afficher le PDF</span> pour charger le certificat généré.
                </p>
              </div>
            )}
          </MedicalSubsection>

          <MedicalSubsection title={renderTestTitle("Actions aptitude", [activeAptitudeCertificateId, aptitudeForm.aptitude], <BadgeCheck className="h-4 w-4" />)}>
            <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-2">
              <Button
                variant="secondary"
                icon={Save}
                onClick={() => {
                  handleValidateVisit();
                  handleSaveAptitudeDraft();
                }}
                loading={aptitudeSaving}
                disabled={!canEditAptitude}
              >
                {isAptitudeValidated ? "Enregistrer les modifications" : "Enregistrer le brouillon"}
              </Button>
              <Button
                variant="secondary"
                icon={BadgeCheck}
                onClick={handleValidateAptitudeCertificate}
                loading={aptitudeSaving}
                disabled={!canValidateAptitude}
              >
                Valider le certificat
              </Button>
              {canSignMedicalDocuments ? (
                <Button
                  variant="secondary"
                  icon={Pencil}
                  onClick={() => setIsEditingAptitudeCertificate(true)}
                  disabled={aptitudeSaving || !isAptitudeValidated || isEditingAptitudeCertificate}
                >
                  Modifier
                </Button>
              ) : null}
              <Button
                variant="secondary"
                icon={FileDown}
                onClick={handleDownloadAptitudePdf}
                disabled={!activeAptitudeCertificateId}
              >
                Générer / Imprimer PDF
              </Button>
            </div>
          </MedicalSubsection>

        </div>
      </MedicalSectionCard>
    </div>
  );
}
    if (sectionId === "profilTaGlycemie") {
      return (
        <div className="space-y-5">
          <MedicalSectionCard
            icon={Activity}
            title="Profil TA et Glycemie"
            description="Document de suivi des constantes TA et Glycemie pour la visite medicale en cours."
          >
            <MedicalSubsection
              title={renderTestTitle(
                "Profil TA et Glycemie",
                [
                  form.profilTaGlycemie.fullName,
                  ...form.profilTaGlycemie.rows.flatMap((row) => [
                    row.date,
                    row.rightArm,
                    row.leftArm,
                    row.time,
                  ]),
                ],
                <Activity className="h-4 w-4" />,
              )}
            >
              <div className="space-y-4">
                <Input
                  label="Nom & Prenom"
                  value={form.profilTaGlycemie.fullName}
                  onChange={(event) =>
                    updateProfilTaGlycemie({
                      ...form.profilTaGlycemie,
                      fullName: event.target.value,
                    })
                  }
                />

                <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white">
                  <div className="overflow-x-auto">
                    <table className="min-w-full divide-y divide-slate-200 text-sm">
                      <thead className="bg-slate-50">
                        <tr className="text-left text-slate-600">
                          <th className="px-4 py-3 font-bold">Date</th>
                          <th className="px-4 py-3 font-bold">Avant le petit-déjeuner</th>
                          <th className="px-4 py-3 font-bold">Avant le déjeuner</th>
                          <th className="px-4 py-3 font-bold">Avant le dîner</th>
                          <th className="px-4 py-3 font-bold">Actions</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-100">
                        {form.profilTaGlycemie.rows.map((row) => (
                          <tr key={row.id}>
                            <td className="px-4 py-3">
                              <Input
                                label=""
                                type="date"
                                value={row.date}
                                onChange={(event) =>
                                  updateProfilTaGlycemie({
                                    ...form.profilTaGlycemie,
                                    rows: form.profilTaGlycemie.rows.map((currentRow) =>
                                      currentRow.id === row.id
                                        ? { ...currentRow, date: event.target.value }
                                        : currentRow,
                                    ),
                                  })
                                }
                              />
                            </td>
                            <td className="px-4 py-3">
                              <Input
                                label=""
                                value={row.rightArm}
                                onChange={(event) =>
                                  updateProfilTaGlycemie({
                                    ...form.profilTaGlycemie,
                                    rows: form.profilTaGlycemie.rows.map((currentRow) =>
                                      currentRow.id === row.id
                                        ? { ...currentRow, rightArm: event.target.value }
                                        : currentRow,
                                    ),
                                  })
                                }
                              />
                            </td>
                            <td className="px-4 py-3">
                              <Input
                                label=""
                                value={row.leftArm}
                                onChange={(event) =>
                                  updateProfilTaGlycemie({
                                    ...form.profilTaGlycemie,
                                    rows: form.profilTaGlycemie.rows.map((currentRow) =>
                                      currentRow.id === row.id
                                        ? { ...currentRow, leftArm: event.target.value }
                                        : currentRow,
                                    ),
                                  })
                                }
                              />
                            </td>
                            <td className="px-4 py-3">
                              <Input
                                label=""
                                value={row.time}
                                onChange={(event) =>
                                  updateProfilTaGlycemie({
                                    ...form.profilTaGlycemie,
                                    rows: form.profilTaGlycemie.rows.map((currentRow) =>
                                      currentRow.id === row.id
                                        ? { ...currentRow, time: event.target.value }
                                        : currentRow,
                                    ),
                                  })
                                }
                              />
                            </td>
                            <td className="px-4 py-3">
                              <Button
                                type="button"
                                variant="ghost"
                                size="sm"
                                icon={Trash2}
                                onClick={() => removeProfilTaGlycemieRow(row.id)}
                              />
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>

                <input
                  ref={profilExcelInputRef}
                  type="file"
                  accept=".xlsx,.xls"
                  className="hidden"
                  onChange={importExcel}
                />

                <div className="flex flex-wrap items-center gap-3">
                  <Button
                    type="button"
                    variant="secondary"
                    size="sm"
                    icon={Plus}
                    onClick={addProfilTaGlycemieRow}
                  >
                    Ajouter une ligne
                  </Button>
                  <Button
                    type="button"
                    variant="secondary"
                    size="sm"
                    icon={FileSpreadsheet}
                    onClick={() => profilExcelInputRef.current?.click()}
                  >
                    Importer Excel
                  </Button>
                  <Button
                    type="button"
                    variant="secondary"
                    size="sm"
                    icon={Download}
                    onClick={handleDownloadProfilTemplate}
                  >
                    Telecharger Excel
                  </Button>
                </div>
              </div>
            </MedicalSubsection>
          </MedicalSectionCard>
        </div>
      );
    }
    if (sectionId === "medicalArretTravail") {
      return (
        <div className="space-y-5">
          <MedicalSectionCard
            icon={FileDown}
            title="CM d'arret de travail"
            description="Document de synthese pour arret de travail, conserve uniquement dans la visite medicale."
          >
            <MedicalSubsection
              title={renderTestTitle(
                "CM d'arret de travail",
                [
                  form.workStoppageCertificate?.doctorFullName || "",
                  form.workStoppageCertificate?.workerFullName || "",
                  form.workStoppageCertificate?.startDate || "",
                  form.workStoppageCertificate?.endDate || "",
                ],
                <FileText className="h-4 w-4" />,
              )}
            >
              <div className="flex flex-wrap items-center gap-3">
                {form.workStoppageCertificate ? (
                  <Button
                    type="button"
                    variant="secondary"
                    size="sm"
                    onClick={() => updateWorkStoppageCertificate(null)}
                  >
                    Supprimer le certificat
                  </Button>
                ) : (
                  <Button
                    type="button"
                    variant="secondary"
                    size="sm"
                    onClick={() => updateWorkStoppageCertificate(buildDefaultWorkStoppageCertificate())}
                  >
                    Ajouter un CM d'arret de travail
                  </Button>
                )}
              </div>

              {form.workStoppageCertificate ? (
                <div className="mt-4 space-y-5">
                  <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
                    <Input
                      label="Docteur validateur full name"
                      value={form.workStoppageCertificate.doctorFullName}
                      onChange={(event) =>
                        updateWorkStoppageCertificate({
                          ...form.workStoppageCertificate!,
                          doctorFullName: event.target.value,
                        })
                      }
                    />
                    <Input
                      label="Worker full name"
                      value={form.workStoppageCertificate.workerFullName}
                      onChange={(event) =>
                        updateWorkStoppageCertificate({
                          ...form.workStoppageCertificate!,
                          workerFullName: event.target.value,
                        })
                      }
                    />
                    <Input
                      label="Worker Age"
                      value={form.workStoppageCertificate.workerAge}
                      onChange={(event) =>
                        updateWorkStoppageCertificate({
                          ...form.workStoppageCertificate!,
                          workerAge: event.target.value,
                        })
                      }
                    />
                    <Input
                      label="Poste de travail"
                      value={form.workStoppageCertificate.position}
                      onChange={(event) =>
                        updateWorkStoppageCertificate({
                          ...form.workStoppageCertificate!,
                          position: event.target.value,
                        })
                      }
                    />
                  </div>

                  <div className="rounded-2xl border border-slate-200 bg-slate-50/70 p-4">
                    <p className="text-sm font-bold text-slate-800">
                      Presente un etat de sante necessitant:
                    </p>
                    <div className="mt-4 grid gap-4 md:grid-cols-2">
                      <Input
                        label="Un arret de travail de"
                        value={form.workStoppageCertificate.workStopDuration}
                        onChange={(event) =>
                          updateWorkStoppageCertificate({
                            ...form.workStoppageCertificate!,
                            workStopDuration: event.target.value,
                          })
                        }
                      />
                      <Input
                        label="Une prolongation d'arret de travail de"
                        value={form.workStoppageCertificate.workStopExtensionDuration}
                        onChange={(event) =>
                          updateWorkStoppageCertificate({
                            ...form.workStoppageCertificate!,
                            workStopExtensionDuration: event.target.value,
                          })
                        }
                      />
                    </div>
                    <label className="mt-4 flex items-center gap-3 text-sm font-medium text-slate-700">
                      <input
                        type="checkbox"
                        checked={form.workStoppageCertificate.returnToWork}
                        onChange={(event) =>
                          updateWorkStoppageCertificate({
                            ...form.workStoppageCertificate!,
                            returnToWork: event.target.checked,
                          })
                        }
                        className="h-4 w-4 rounded border-slate-300 text-cyan-600 focus:ring-cyan-500"
                      />
                      <span>La reprise de travail</span>
                    </label>
                  </div>

                  <div className="grid gap-4 md:grid-cols-3">
                    <Input
                      label="A compter du"
                      type="date"
                      value={form.workStoppageCertificate.startDate}
                      onChange={(event) =>
                        updateWorkStoppageCertificate({
                          ...form.workStoppageCertificate!,
                          startDate: event.target.value,
                        })
                      }
                    />
                    <Input
                      label="Au"
                      type="date"
                      value={form.workStoppageCertificate.endDate}
                      onChange={(event) =>
                        updateWorkStoppageCertificate({
                          ...form.workStoppageCertificate!,
                          endDate: event.target.value,
                        })
                      }
                    />
                    <Input
                      label="Fait le"
                      type="date"
                      value={form.workStoppageCertificate.issuedAt}
                      onChange={(event) =>
                        updateWorkStoppageCertificate({
                          ...form.workStoppageCertificate!,
                          issuedAt: event.target.value,
                        })
                      }
                    />
                  </div>
                </div>
              ) : (
                <p className="mt-4 text-sm text-slate-500">
                  Aucun certificat d'arret de travail rattache a cette visite.
                </p>
              )}
            </MedicalSubsection>
          </MedicalSectionCard>
        </div>
      );
    }
    if (sectionId === "pdfViewer") {
      return (
        
        <div className="space-y-5">
        
          <MedicalSectionCard
            icon={FileDown}
            title="PDF Ficher"
            description=""
          >
            <div className="rounded-sm border border-slate-200 bg-slate-50/70 p-5">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <p className="text-sm font-black text-slate-900">Fich intern de visit Medicale</p>
                 
                </div>
                <div className="flex flex-wrap gap-3">
                  <Button
                    variant="secondary"
                    icon={FileDown}
                    onClick={handleLoadPdfPreview}
                    loading={pdfPreviewLoading}
                  >
                    Afficher le PDF
                  </Button>
                  <Button
                    variant="secondary"
                    icon={FileDown}
                    onClick={handleDownloadMedicalVisitPdf}
                    loading={pdfDownloading}
                  >
                    Telecharger PDF
                  </Button>
                </div>
              </div>
            </div>

            {isCreateMode ? (
              <div className="rounded-sm border border-amber-200 bg-amber-50/70 p-8 text-center">
                <p className="text-base font-black text-amber-800">Apercu PDF indisponible</p>
                <p className="mt-2 text-sm text-amber-700">
                  Enregistrez d'abord le travailleur en base pour generer et afficher le PDF.
                </p>
              </div>
            ) : pdfPreviewLoading ? (
              <div className="flex min-h-[50vh] items-center justify-center rounded-sm border border-slate-200 bg-white">
                <Spinner />
              </div>
            ) : pdfPreviewUrl ? (
              <div className="overflow-hidden rounded-sm border border-slate-200 bg-white shadow-sm">
                <iframe
                  title="Fich intern de visit Medicale PDF"
                  src={pdfPreviewUrl}
                  className="h-[170vh] w-full"
                />
              </div>
            ) : (
              <div className="rounded-sm border border-dashed border-slate-300 bg-white p-10 text-center">
                <p className="text-base font-black text-slate-900">Aucun PDF affiche</p>
                <p className="mt-2 text-sm text-slate-500">
                  Cliquez sur <span className="font-semibold text-slate-700">Afficher le PDF</span> pour charger le document genere.
                </p>
              </div>
            )}
          </MedicalSectionCard>
        </div>
      );
    }

    if (sectionId === "ordonnance") {
      return (
        <div className="space-y-5">
          <MedicalSectionCard
            icon={Pill}
            title="Ordonnance"
            description="Creez, signez et imprimez des prescriptions professionnelles sans bloquer le flux de validation du dossier medical."
          >
            <div className="grid gap-5 xl:grid-cols-1">
              <Card className="rounded-3xl border-slate-200/90 p-5">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <h3 className="text-base font-black text-slate-950">Ordonnances</h3>
                    <p className="mt-1 text-sm text-slate-500">
                      Plusieurs ordonnances peuvent etre rattachees a la meme campagne.
                    </p>
                  </div>
                  <Button variant="secondary" size="sm" icon={Plus} onClick={handleCreatePrescriptionDraft}>
                    Nouvelle
                  </Button>
                </div>

                <div className="mt-4 space-y-3">
                  {prescriptionLoading ? (
                    <div className="flex min-h-[160px] items-center justify-center rounded-3xl border border-slate-200 bg-slate-50/70">
                      <Spinner />
                    </div>
                  ) : prescriptions.length > 0 ? (
                    prescriptions.map((item) => {
                      const active = item.id === prescriptionForm.id;
                      return (
                        <button
                          key={item.id}
                          type="button"
                          onClick={() => handleSelectPrescription(item)}
                          className={cn(
                            "w-full rounded-3xl border p-4 text-left transition-all",
                            active
                              ? "border-cyan-200 bg-cyan-50/80 shadow-sm"
                              : "border-slate-200 bg-white hover:border-slate-300 hover:bg-slate-50",
                          )}
                        >
                          <div className="flex items-start justify-between gap-3">
                            <div>
                              <p className="text-sm font-black text-slate-950">
                                {item.prescription_number || `Ordonnance #${item.id}`}
                              </p>
                              <p className="mt-1 text-xs text-slate-500">
                                {formatDisplayDate(item.prescription_date)}
                              </p>
                            </div>
                            <span
                              className={cn(
                                "rounded-full px-2.5 py-1 text-[11px] font-black uppercase tracking-[0.08em]",
                                item.status === "signed"
                                  ? "bg-emerald-100 text-emerald-700"
                                  : item.status === "printed"
                                    ? "bg-slate-200 text-slate-700"
                                    : "bg-amber-100 text-amber-700",
                              )}
                            >
                              {item.status}
                            </span>
                          </div>
                          <p className="mt-3 line-clamp-2 text-sm text-slate-600">
                            {item.diagnosis || "Aucun motif renseigne"}
                          </p>
                        </button>
                      );
                    })
                  ) : (
                    <div className="rounded-3xl border border-dashed border-slate-300 bg-slate-50/70 p-5 text-sm text-slate-500">
                      Aucune ordonnance enregistree pour ce travailleur dans cette campagne.
                    </div>
                  )}
                </div>
              </Card>

              <div className="space-y-5">
                {isCreateMode ? (
                  <div className="rounded-3xl border border-amber-200 bg-amber-50/80 p-5 text-sm font-semibold text-amber-800">
                    Enregistrez d'abord le travailleur pour activer les ordonnances en base.
                  </div>
                ) : null}

                <div className="rounded-[30px] border border-slate-200 bg-white p-6 shadow-sm">
                  <div className="rounded-[26px] border border-cyan-100 bg-gradient-to-br from-cyan-50 via-white to-emerald-50 p-6">
                    <div className="flex flex-wrap items-start justify-between gap-4 border-b border-slate-200 pb-5">
                      <div>
                        <p className="text-xs font-black uppercase tracking-[0.16em] text-cyan-700">
                          Service de medecine du travail
                        </p>
                        <h3 className="mt-2 text-xl font-black text-slate-950">
                          {currentCampaign?.company_name || "Clinique"}
                        </h3>
                        <p className="mt-1 text-sm text-slate-500">
                          {currentCampaign?.site_name || currentCampaign?.branch_name || "Ouargla"}
                        </p>
                      </div>
                      <div className="min-w-[200px] text-right">
                        <p className="text-xs font-bold uppercase tracking-[0.14em] text-slate-400">
                          Statut
                        </p>
                        <p className="mt-2 text-lg font-black text-slate-950">{prescriptionForm.status}</p>
                      </div>
                    </div>

                    <div className="py-5 text-center">
                      <p className="text-3xl font-black tracking-[0.26em] text-slate-950">ORDONNANCE</p>
                    </div>

                    <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
                      <Input
                        label="Numero ordonnance"
                        value={prescriptionForm.prescription_number}
                        onChange={(event) =>
                          updatePrescriptionField("prescription_number", event.target.value)
                        }
                      />
                      <Input
                        label="Date ordonnance"
                        type="date"
                        value={prescriptionForm.prescription_date}
                        onChange={(event) =>
                          updatePrescriptionField("prescription_date", event.target.value)
                        }
                      />
                      <Input
                        label="Age"
                        value={prescriptionForm.age}
                        readOnly
                        className="cursor-not-allowed bg-slate-100/90 text-slate-500"
                      />
                      <Input
                        label="Nom et Prenom patient"
                        value={prescriptionForm.patient_name}
                        readOnly
                        className="cursor-not-allowed bg-slate-100/90 text-slate-500 md:col-span-2"
                      />
                      <Input
                        label="Medecin prescripteur"
                        value={"Dr. " +form.medicalDecision.validation.validatingDoctor}
                        readOnly
                        className="cursor-not-allowed bg-slate-100/90 text-slate-500"
                      />
                    </div>

                    <div className="mt-5 grid gap-4">
                      <Textarea
                        label="Diagnostic / Motif"
                        rows={2}
                        value={prescriptionForm.diagnosis}
                        onChange={(event) => updatePrescriptionField("diagnosis", event.target.value)}
                      />
                      <Textarea
                        label="Notes"
                        rows={3}
                        value={prescriptionForm.notes}
                        onChange={(event) => updatePrescriptionField("notes", event.target.value)}
                      />
                    </div>

                    <div className="mt-6 rounded-[26px] border border-slate-200 bg-white p-5">
                      <div className="flex flex-wrap items-center justify-between gap-3">
                        <div>
                          <p className="text-base font-black text-slate-950">Prescription</p>
                          <p className="mt-1 text-sm text-slate-500">
                            Renseignez chaque ligne avec un medicament, une dose, une frequence et une duree.
                          </p>
                        </div>
                        <Button variant="secondary" icon={Plus} onClick={handleAddMedication}>
                          Ajouter medicament
                        </Button>
                      </div>

                      <div className="mt-4 space-y-4">
                        {prescriptionForm.items.map((item, index) => (
                          <div
                            key={item.id}
                            className="rounded-3xl border border-slate-200 bg-slate-50/70 p-4"
                          >
                            <div className="mb-4 flex items-center justify-between gap-3">
                              <p className="text-sm font-black text-slate-950">
                                Medicament {index + 1}
                              </p>
                              <div className="flex flex-wrap items-center gap-2">
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  icon={ChevronUp}
                                  onClick={() => handleMoveMedication(item.id, "up")}
                                  disabled={index === 0}
                                >
                                  Monter
                                </Button>
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  icon={ChevronDown}
                                  onClick={() => handleMoveMedication(item.id, "down")}
                                  disabled={index === prescriptionForm.items.length - 1}
                                >
                                  Descendre
                                </Button>
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  icon={Plus}
                                  onClick={() => handleDuplicateMedication(item.id)}
                                >
                                  Dupliquer
                                </Button>
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  icon={Trash2}
                                  onClick={() => handleRemoveMedication(item.id)}
                                >
                                  Supprimer
                                </Button>
                              </div>
                            </div>
                            <div className="grid gap-4 xl:grid-cols-3">
                              <div className="xl:col-span-4">
                                <MedicineAutocomplete
                                  value={item.brand_name}
                                  selectedMedicineId={item.medicine_id ?? null}
                                  onChange={(value) => handlePrescriptionMedicineInputChange(item.id, value)}
                                  onSelect={(medicine) => handleSelectMedicineResult(item.id, medicine)}
                                  onClear={() => handleClearSelectedMedicine(item.id)}
                                  onManualEntryStateChange={(isManualEntry) =>
                                    setManualPrescriptionEntryState((current) => ({
                                      ...current,
                                      [item.id]: isManualEntry,
                                    }))
                                  }
                                  placeholder="Rechercher un medicament..."
                                />
                                {manualPrescriptionEntryState[item.id] ? (
                                  <p className="mt-2 text-xs font-medium text-amber-700">
                                    Medicament saisi manuellement
                                  </p>
                                ) : null}
                              </div>
                              <Input
                                label="DCI"
                                value={item.generic_name}
                                onChange={(event) =>
                                  updatePrescriptionItem(item.id, "generic_name", event.target.value)
                                }
                              />
                              <Input
                                label="Dosage"
                                value={item.strength}
                                onChange={(event) =>
                                  updatePrescriptionItem(item.id, "strength", event.target.value)
                                }
                              />
                              <Input
                                label="Forme"
                                value={item.pharmaceutical_form}
                                onChange={(event) =>
                                  updatePrescriptionItem(item.id, "pharmaceutical_form", event.target.value)
                                }
                              />
                              <Input
                                label="Conditionnement"
                                value={item.packaging}
                                onChange={(event) =>
                                  updatePrescriptionItem(item.id, "packaging", event.target.value)
                                }
                              />
                              <Input
                                label="Laboratoire"
                                value={item.laboratory}
                                onChange={(event) =>
                                  updatePrescriptionItem(item.id, "laboratory", event.target.value)
                                }
                              />
                              <Input
                                label="Dose"
                                type="number"
                                min="0"
                                step="0.5"
                                value={item.dose_quantity}
                                onChange={(event) =>
                                  updatePrescriptionItem(item.id, "dose_quantity", event.target.value)
                                }
                              />
                              <Select
                                label="Unite"
                                value={item.dose_unit}
                                onChange={(event) =>
                                  updatePrescriptionItem(item.id, "dose_unit", event.target.value)
                                }
                                options={PRESCRIPTION_DOSE_UNIT_OPTIONS.map((option) => ({
                                  value: option,
                                  label: option,
                                }))}
                              />
                              <Select
                                label="Frequence"
                                value={item.frequency || ""}
                                onChange={(event) =>
                                  updatePrescriptionItem(item.id, "frequency", event.target.value)
                                }
                                options={[
                                  { value: "", label: "Selectionner" },
                                  ...PRESCRIPTION_FREQUENCY_OPTIONS.map((option) => ({
                                    value: option,
                                    label: option,
                                  })),
                                ]}
                              />
                              <Input
                                label="Duree"
                                type="number"
                                min="0"
                                step="1"
                                value={item.duration_value}
                                onChange={(event) =>
                                  updatePrescriptionItem(item.id, "duration_value", event.target.value)
                                }
                              />
                              <Select
                                label="Unite duree"
                                value={item.duration_unit}
                                onChange={(event) =>
                                  updatePrescriptionItem(item.id, "duration_unit", event.target.value)
                                }
                                options={PRESCRIPTION_DURATION_UNIT_OPTIONS.map((option) => ({
                                  value: option,
                                  label: option,
                                }))}
                              />
                              <Input
                                label="Nombre de boites"
                                type="number"
                                min="0"
                                step="1"
                                value={item.number_of_boxes}
                                onChange={(event) =>
                                  updatePrescriptionItem(item.id, "number_of_boxes", event.target.value)
                                }
                              />
                              {item.frequency === "Autre..." ? (
                                <Input
                                  label="Frequence personnalisee"
                                  value={item.frequency_custom}
                                  onChange={(event) =>
                                    updatePrescriptionItem(item.id, "frequency_custom", event.target.value)
                                  }
                                  className="xl:col-span-3"
                                />
                              ) : null}
                              <div className="xl:col-span-3">
                                <Textarea
                                  label="Instructions"
                                  rows={2}
                                  value={item.instructions}
                                  onChange={(event) =>
                                    updatePrescriptionItem(item.id, "instructions", event.target.value)
                                  }
                                />
                              </div>
                              <div className="xl:col-span-3 rounded-2xl border border-dashed border-slate-200 bg-white/80 px-4 py-3">
                                <p className="text-xs font-black uppercase tracking-[0.14em] text-slate-400">
                                  Phrase generee
                                </p>
                                <p className="mt-2 text-sm text-slate-700">
                                  {buildPrescriptionPreviewText([item]).replace(/^R\/\s*/u, "") || "Aucune phrase generee."}
                                </p>
                              </div>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>

                    <div className="mt-6 rounded-[26px] border border-slate-200 bg-white p-5">
                      <p className="text-sm font-black text-slate-950">Apercu de l'ordonnance</p>
                      <p className="mt-1 text-sm text-slate-500">
                        Cette zone est generee automatiquement a partir des lignes structurees.
                      </p>
                      <pre className="mt-4 whitespace-pre-wrap rounded-2xl border border-slate-200 bg-slate-50/70 px-4 py-4 text-sm text-slate-700">
                        {buildPrescriptionPreviewText(
                          prescriptionForm.items.filter((entry) => hasStructuredPrescriptionItemContent(entry)),
                        )}
                      </pre>
                    </div>

                    <div className="mt-6 grid gap-5 xl:grid-cols-[1fr,240px]">
                      <div className="rounded-3xl border border-slate-200 bg-white/80 p-5">
                        <p className="text-sm font-black text-slate-950">Patient</p>
                        <p className="mt-2 text-sm text-slate-700">
                          {prescriptionForm.patient_name || "Nom et Prenom non disponible"} - Age {prescriptionForm.age || "-"}
                        </p>
                        <p className="mt-3 text-sm text-slate-500">
                          Corps de prescription large, pret pour l'export PDF et l'impression.
                        </p>
                      </div>
                      <div className="rounded-3xl border border-dashed border-slate-300 bg-white/80 p-5 text-right">
                        <p className="text-xs font-black uppercase tracking-[0.14em] text-slate-400">
                          Signature
                        </p>
                        <p className="mt-8 text-sm font-bold text-slate-900">
                          {prescriptionForm.doctor_name ? `Dr. ${prescriptionForm.doctor_name}` : doctorName ? `Dr. ${doctorName}` : "Medecin prescripteur"}
                        </p>
                      </div>
                    </div>

                    <div className="mt-6 border-t border-slate-200 pt-4 text-center text-xs font-semibold tracking-[0.08em] text-slate-500">
                      {currentCampaign?.company_name || "Clinique"} | {currentCampaign?.site_name || currentCampaign?.branch_name || "Ouargla"} | Contact administratif
                    </div>
                  </div>
                </div>

                <MedicalSubsection title={renderTestTitle("PDF ordonnance", [prescriptionForm.prescription_number, prescriptionForm.prescription_date, prescriptionForm.diagnosis], <FileText className="h-4 w-4" />)}>
                  <div className="rounded-sm border border-slate-200 bg-slate-50/70 p-5">
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <div>
                        <p className="text-sm font-black text-slate-900">Ordonnance generee</p>
                        <p className="mt-1 text-sm text-slate-500">
                          Affichez le rendu PDF final avant impression ou telechargement.
                        </p>
                      </div>
                      <div className="flex flex-wrap items-center gap-3">
                        <Button
                          variant="secondary"
                          icon={FileDown}
                          onClick={handleLoadPrescriptionPdfPreview}
                          loading={prescriptionPreviewLoading}
                          disabled={isCreateMode || !prescriptionForm.id}
                        >
                          Afficher le PDF
                        </Button>
                      </div>
                    </div>
                    <div className="mt-3 rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-600">
                      {!canSignMedicalDocuments
                        ? signatureAuthorizationMessage
                        : currentUserHasSignature
                        ? "Une signature PNG est configuree dans votre profil signataire. Cochez la case pour l'ajouter a l'ordonnance."
                        : "Aucune signature PNG n'est configuree dans votre profil signataire."}
                    </div>
                  </div>

                  {isCreateMode ? (
                    <div className="rounded-sm border border-amber-200 bg-amber-50/70 p-8 text-center">
                      <p className="text-base font-black text-amber-800">Apercu PDF indisponible</p>
                      <p className="mt-2 text-sm text-amber-700">
                        Enregistrez d'abord le travailleur et l'ordonnance pour afficher le PDF.
                      </p>
                    </div>
                  ) : prescriptionPreviewLoading ? (
                    <div className="flex min-h-[50vh] items-center justify-center rounded-sm border border-slate-200 bg-white">
                      <Spinner />
                    </div>
                  ) : prescriptionPreviewUrl ? (
                    <div className="overflow-hidden rounded-sm border border-slate-200 bg-white shadow-sm">
                      <iframe
                        title="Ordonnance PDF"
                        src={prescriptionPreviewUrl}
                        className="h-[170vh] w-full"
                      />
                    </div>
                  ) : (
                    <div className="rounded-sm border border-dashed border-slate-300 bg-white p-10 text-center">
                      <p className="text-base font-black text-slate-900">Aucun PDF affiche</p>
                      <p className="mt-2 text-sm text-slate-500">
                        Cliquez sur <span className="font-semibold text-slate-700">Afficher le PDF</span> pour charger l'ordonnance generee.
                      </p>
                    </div>
                  )}
                </MedicalSubsection>

                <MedicalSubsection title={renderTestTitle("Actions ordonnance", [prescriptionForm.id, prescriptionForm.status, prescriptionForm.items.length], <ClipboardCheck className="h-4 w-4" />)}>
                  <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
                    <Button
                      variant="secondary"
                      icon={Save}
                      onClick={handleSavePrescriptionDraft}
                      loading={prescriptionSaving}
                    >
                      Enregistrer brouillon
                    </Button>
                    <Button
                      variant="secondary"
                      icon={FileText}
                      onClick={handleSignPrescription}
                      loading={prescriptionSaving && canSignPrescription}
                      disabled={!canSignPrescription || isCreateMode}
                    >
                      Valider l'ordonnance
                    </Button>
                    <Button
                      variant="secondary"
                      icon={ClipboardList}
                      onClick={handleDuplicatePrescription}
                      loading={prescriptionSaving}
                      disabled={isCreateMode || !prescriptionForm.id}
                    >
                      Dupliquer
                    </Button>
                    <Button
                      variant="secondary"
                      icon={FileDown}
                      onClick={handleDownloadPrescriptionPdf}
                      loading={prescriptionDownloading}
                      disabled={isCreateMode || !prescriptionForm.id}
                    >
                      Generer PDF ordonnance
                    </Button>
                    <Button
                      variant="secondary"
                      icon={Printer}
                      onClick={handlePrintPrescription}
                      loading={prescriptionPrinting}
                      disabled={isCreateMode || !prescriptionForm.id}
                    >
                      Imprimer
                    </Button>
                    <Button
                      variant="secondary"
                      icon={AlertCircle}
                      onClick={handleCancelPrescription}
                      loading={prescriptionSaving}
                      disabled={isCreateMode || !prescriptionForm.id}
                    >
                      Annuler l'ordonnance
                    </Button>
                    <Button
                      variant="ghost"
                      icon={Trash2}
                      onClick={handleDeletePrescription}
                      disabled={isCreateMode || !prescriptionForm.id}
                    >
                      Supprimer ordonnance
                    </Button>
                  </div>
                </MedicalSubsection>
              </div>
            </div>
          </MedicalSectionCard>
        </div>
      );
    }

    if (sectionId === "pdfDossier") {
      return (
        <div className="space-y-5">
          <MedicalSectionCard
            icon={FileDown}
            title="PDF Dossier"
            description="Visualisez le PDF genere du Dossier medical directement depuis le dossier du travailleur."
          >
            <div className="rounded-sm border border-slate-200 bg-slate-50/70 p-5">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <p className="text-sm font-black text-slate-900">Dossier medical</p>
                </div>
                <div className="flex flex-wrap gap-3">
                  <Button
                    variant="secondary"
                    icon={FileDown}
                    onClick={handleLoadDossierPdfPreview}
                    loading={dossierPdfPreviewLoading}
                  >
                    Afficher le PDF
                  </Button>
                  <Button
                    variant="secondary"
                    icon={FileDown}
                    onClick={handleDownloadMedicalDossierPdf}
                    loading={dossierPdfDownloading}
                  >
                    Telecharger PDF
                  </Button>
                </div>
              </div>
            </div>

            {isCreateMode ? (
              <div className="rounded-sm border border-amber-200 bg-amber-50/70 p-8 text-center">
                <p className="text-base font-black text-amber-800">Apercu PDF indisponible</p>
                <p className="mt-2 text-sm text-amber-700">
                  Enregistrez d'abord le travailleur en base pour generer et afficher le PDF.
                </p>
              </div>
            ) : dossierPdfPreviewLoading ? (
              <div className="flex min-h-[50vh] items-center justify-center rounded-sm border border-slate-200 bg-white">
                <Spinner />
              </div>
            ) : dossierPdfPreviewUrl ? (
              <div className="overflow-hidden rounded-sm border border-slate-200 bg-white shadow-sm">
                <iframe
                  title="Dossier medical PDF"
                  src={dossierPdfPreviewUrl}
                  className="h-[170vh] w-full"
                />
              </div>
            ) : (
              <div className="rounded-sm border border-dashed border-slate-300 bg-white p-10 text-center">
                <p className="text-base font-black text-slate-900">Aucun PDF affiche</p>
                <p className="mt-2 text-sm text-slate-500">
                  Cliquez sur <span className="font-semibold text-slate-700">Afficher le PDF</span> pour charger le document genere.
                </p>
              </div>
            )}
          </MedicalSectionCard>
        </div>
      );
    }

    return (
      <div className="space-y-2">
        <MedicalSectionCard
          icon={ShieldCheck}
          title="Apercu et validation"
          description="Revoyez le dossier, identifiez les manques et lancez les actions finales en toute confiance."
        >
          <div className="mt-6 grid gap-5 xl:grid-cols-2">
            <MedicalSubsection title={renderTestTitle("Resume informations personnelles", [form.firstName, form.lastName, form.nationalId, form.phone, form.dateOfBirth, form.birthPlace], <UserRound className="h-4 w-4" />)}>
              <div className="space-y-2 text-sm text-slate-700">
                <p><span className="font-bold text-slate-900">Travailleur:</span> {`${form.firstName} ${form.lastName}`.trim() || "Non renseigne"}</p>
                <p><span className="font-bold text-slate-900">Identite:</span> {form.nationalId || "Non renseignee"}</p>
                <p><span className="font-bold text-slate-900">Contact:</span> {form.phone || "Non renseigne"}</p>
                <p><span className="font-bold text-slate-900">Naissance:</span> {form.dateOfBirth || "Non renseignee"} - {form.birthPlace || "Wilaya non renseignee"}</p>
              </div>
            </MedicalSubsection>
            <MedicalSubsection title={renderTestTitle("Resume professionnel", [form.position, form.direction, form.service, form.companyName, form.siteName], <BriefcaseMedical className="h-4 w-4" />)}>
              <div className="space-y-2 text-sm text-slate-700">
                <p><span className="font-bold text-slate-900">Poste:</span> {form.position || "Non renseigne"}</p>
                <p><span className="font-bold text-slate-900">Direction:</span> {form.direction || "Non renseignee"}</p>
                <p><span className="font-bold text-slate-900">Service:</span> {form.service || "Non renseigne"}</p>
                <p><span className="font-bold text-slate-900">Entreprise / Site:</span> {form.companyName || "-"} / {form.siteName || "-"}</p>
              </div>
            </MedicalSubsection>
            <MedicalSubsection title={renderTestTitle("Resume medical", [form.medicalDecision.aptitude, form.internalVisitTa, form.internalVisitFc, form.clinicalExam.doctorGeneralObservations.comments], <HeartPulse className="h-4 w-4" />)}>
              <div className="space-y-2 text-sm text-slate-700">
                <p><span className="font-bold text-slate-900">Aptitude:</span> {form.medicalDecision.aptitude || "Non definie"}</p>
                <p><span className="font-bold text-slate-900">TA / FC:</span> {form.internalVisitTa || "-"} / {form.internalVisitFc || "-"}</p>
                <p><span className="font-bold text-slate-900">Commentaires medicaux:</span> {form.clinicalExam.doctorGeneralObservations.comments || "Aucun commentaire"}</p>
              </div>
            </MedicalSubsection>
            <MedicalSubsection title={renderTestTitle("Resume examens", [form.complementaryExams.cardiology.ecg, form.complementaryExams.audiology.audiogram, form.complementaryExams.biology.glycemia], <FileText className="h-4 w-4" />)}>
              <div className="space-y-2 text-sm text-slate-700">
                <p><span className="font-bold text-slate-900">ECG:</span> {form.complementaryExams.cardiology.ecg || "Non renseigne"}</p>
                <p><span className="font-bold text-slate-900">Audiogramme:</span> {form.complementaryExams.audiology.audiogram || "Non renseigne"}</p>
                <p><span className="font-bold text-slate-900">Glycémie:</span> {form.complementaryExams.biology.glycemia || "Non renseignee"}</p>
              </div>
            </MedicalSubsection>
          </div>

          <div className="mt-6 grid gap-5 xl:grid-cols-1">
            <MedicalSubsection title={renderTestTitle("Controle qualite", [form.nationalId, form.phone, form.position, form.internalVisitDate, form.internalVisitDoctor, form.clinicalExam.cardiovascular.bloodPressure, form.complementaryExams.biology.glycemia, form.medicalDecision.aptitude, form.medicalDecision.validation.validatingDoctor], <ShieldCheck className="h-4 w-4" />)}>
              <div className="grid gap-4 md:grid-cols-2">
                <div className="rounded-2xl border border-amber-100 bg-amber-50/70 p-4 md:col-span-2">
                  <p className="text-xs font-bold uppercase tracking-[0.12em] text-amber-700">Champs manquants</p>
                  <div className="mt-2 flex flex-wrap gap-2">
                    {missingFields.length > 0 ? missingFields.map((field) => (
                      <span key={field} className="rounded-full bg-white px-3 py-1 text-xs font-semibold text-slate-700 ring-1 ring-amber-100">
                        {field}
                      </span>
                    )) : <span className="text-sm font-semibold text-emerald-700">Aucun champ critique manquant.</span>}
                  </div>
                </div>
                <div className="rounded-2xl border border-rose-100 bg-rose-50/70 p-4 md:col-span-3">
                  <p className="text-xs font-bold uppercase tracking-[0.12em] text-rose-700">Alertes medicales</p>
                  <div className="mt-2 flex flex-wrap gap-2">
                    {medicalAlerts.length > 0 ? medicalAlerts.map((alert) => (
                      <span key={alert} className="rounded-full bg-white px-3 py-1 text-xs font-semibold text-slate-700 ring-1 ring-rose-100">
                        {alert}
                      </span>
                    )) : <span className="text-sm font-semibold text-slate-600">Aucune alerte medicale detectee.</span>}
                  </div>
                </div>
              </div>
            </MedicalSubsection>

            <MedicalSubsection title={renderTestTitle("Actions", [handleSaveDraft, handlePrint, handleDownloadMedicalVisitPdf], <ClipboardList className="h-4 w-4" />)}>
              <div className="grid gap-3 sm:grid-cols-3">
                <Button variant="secondary" icon={Save} onClick={handleSaveDraft}>
                  Enregistrer brouillon
                </Button>
                <Button variant="secondary" icon={FileDown} onClick={handlePrint}>
                  Apercu Dossier Medical
                </Button>
                <Button variant="secondary" icon={FileDown} onClick={() => setActiveTab("internalVisit")}>
                  Apercu Fiche de Visite Medicale
                </Button>
                <Button
                  variant="secondary"
                  icon={FileDown}
                  onClick={handleDownloadMedicalVisitPdf}
                  loading={pdfDownloading}
                >
                  Telecharger PDF
                </Button>
                <Button variant="secondary" icon={FileDown} onClick={handlePrint}>
                  Imprimer
                </Button>
                <Button
                  icon={ShieldCheck}
                  onClick={() => handleSubmit({ confirm: true })}
                  className="bg-gradient-to-r from-cyan-600 to-teal-600 shadow-lg shadow-cyan-600/20 hover:bg-gradient-to-r hover:from-cyan-700 hover:to-teal-700"
                >
                  Confirmer le dossier
                </Button>
              </div>
            </MedicalSubsection>
          </div>

          {form.confirmationStatus === "confirmed" ? (
            <div className="mt-6">
              <MedicalSubsection title={renderTestTitle("Apres confirmation", [form.confirmationStatus, form.confirmationDoctor, form.confirmationDate], <ShieldCheck className="h-4 w-4" />)}>
                <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
                  <div className="rounded-2xl border border-emerald-200 bg-emerald-50/70 p-4">
                    <p className="text-xs font-bold uppercase tracking-[0.12em] text-emerald-700">Statut</p>
                    <p className="mt-2 text-lg font-black text-emerald-800">Confirme</p>
                  </div>
                  <div className="rounded-2xl border border-slate-200 bg-slate-50/70 p-4">
                    <p className="text-xs font-bold uppercase tracking-[0.12em] text-slate-500">Medecin</p>
                    <p className="mt-2 text-sm font-bold text-slate-900">{"Dr. " + form.confirmationDoctor || "Non renseigne"}</p>
                  </div>
                  <div className="rounded-2xl border border-slate-200 bg-slate-50/70 p-4">
                    <p className="text-xs font-bold uppercase tracking-[0.12em] text-slate-500">Date</p>
                    <p className="mt-2 text-sm font-bold text-slate-900">
                      {formatDisplayDate(form.confirmationDate) || "Non renseignee"}
                    </p>
                  </div>
                  <div className="rounded-2xl border border-slate-200 bg-slate-50/70 p-4">
                    <p className="text-xs font-bold uppercase tracking-[0.12em] text-slate-500">Signature</p>
                    <p className="mt-2 text-sm font-bold text-slate-900">{form.confirmationSignature || "Signature en attente"}</p>
                  </div>
                  <div className="rounded-2xl border border-slate-200 bg-slate-50/70 p-4">
                    <p className="text-xs font-bold uppercase tracking-[0.12em] text-slate-500">Verrouillage du dossier</p>
                    <p className="mt-2 text-sm font-bold text-slate-900">{form.isLocked ? "Dossier verrouille" : "Non verrouille"}</p>
                  </div>
                  <div className="rounded-2xl border border-slate-200 bg-slate-50/70 p-4 xl:col-span-3">
                    <p className="text-xs font-bold uppercase tracking-[0.12em] text-slate-500">Historique d'audit</p>
                    <div className="mt-3 space-y-2">
                      {form.auditTrail.length > 0 ? form.auditTrail.map((entry) => (
                        <div key={entry.id} className="flex flex-wrap items-center justify-between gap-2 rounded-2xl bg-white px-3 py-2 ring-1 ring-slate-100">
                          <span className="text-sm font-semibold text-slate-900">{entry.action}</span>
                          <span className="text-xs text-slate-500">{entry.actor} - {entry.at}</span>
                        </div>
                      )) : <p className="text-sm text-slate-500">Aucun historique disponible.</p>}
                    </div>
                  </div>
                </div>
              </MedicalSubsection>
            </div>
          ) : null}
        </MedicalSectionCard>
      </div>
    );
  };

  if (!currentCampaign || !campaignId) {
    return null;
  }

  if (loading) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center">
        <Spinner />
      </div>
    );
  }

  if (!worker && !isCreateMode) {
    return (
      <EmptyState
        title="Travailleur indisponible"
        description="Nous n'avons pas pu charger ce dossier. Revenez a la liste des travailleurs puis reessayez."
        actionLabel="Retour aux travailleurs"
        onAction={() => navigate(`/app/workspace/${campaignId}/workers`)}
      />
    );
  }

  return (
    <div className="space-y-4 pb-8">
       
      <WorkerAlreadyExistsModal
        open={duplicateModalOpen}
        worker={duplicateWorker}
        history={duplicateHistory}
        currentCampaign={currentCampaign}
        onClose={() => setDuplicateModalOpen(false)}
        onOpenVisit={handleOpenVisitFromModal}
        onDuplicateVisit={handleDuplicateVisitFromModal}
        onCreateNewVisit={handleCreateNewVisit}
      />

      <Modal
        open={profilImportPreviewOpen}
        title="Import Profil TA et Glycemie"
        onClose={resetProfilImportState}
      >
        <div className="space-y-6">
          <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3">
            <p className="text-xs font-bold uppercase tracking-[0.18em] text-cyan-700">
              Fichier selectionne
            </p>
            <p className="mt-1 text-sm font-semibold text-slate-900">{profilImportedFileName}</p>
            <p className="mt-1 text-sm text-slate-600">
              {profilImportRows.length} ligne(s) prete(s) a etre importee(s)
            </p>
          </div>

          <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white">
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-slate-200 text-sm">
                <thead className="bg-slate-50">
                  <tr className="text-left text-slate-600">
                    <th className="px-4 py-3 font-bold">Date</th>
                    <th className="px-4 py-3 font-bold">Avant le petit-déjeuner</th>
                    <th className="px-4 py-3 font-bold">Avant le déjeuner</th>
                    <th className="px-4 py-3 font-bold">Avant le dîner</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {profilImportRows.map((row, index) => (
                    <tr key={`${row.date}-${index}`}>
                      <td className="px-4 py-3 text-slate-700">{formatDisplayDate(row.date)}</td>
                      <td className="px-4 py-3 text-slate-700">
                        {row.beforeBreakfast === null ? "-" : row.beforeBreakfast}
                      </td>
                      <td className="px-4 py-3 text-slate-700">
                        {row.beforeLunch === null ? "-" : row.beforeLunch}
                      </td>
                      <td className="px-4 py-3 text-slate-700">
                        {row.beforeDinner === null ? "-" : row.beforeDinner}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {profilIgnoredRows.length > 0 ? (
            <div className="space-y-3 rounded-2xl border border-amber-200 bg-amber-50/80 p-4">
              <div>
                <p className="text-xs font-bold uppercase tracking-[0.18em] text-amber-700">
                  Lignes ignorees
                </p>
                <p className="mt-1 text-sm text-amber-900">
                  {profilIgnoredRows.length} ligne(s) ont ete ignoree(s) pendant l'analyse.
                </p>
              </div>
              <div className="space-y-2">
                {profilIgnoredRows.map((row) => (
                  <div
                    key={`${row.rowNumber}-${row.reason}`}
                    className="rounded-xl border border-amber-200 bg-white/80 px-3 py-2 text-sm text-slate-700"
                  >
                    Ligne {row.rowNumber}: {row.reason}
                  </div>
                ))}
              </div>
            </div>
          ) : null}

          <div className="flex justify-end gap-3">
            <Button type="button" variant="secondary" onClick={resetProfilImportState}>
              Annuler
            </Button>
            <Button type="button" icon={FileSpreadsheet} onClick={handleConfirmProfilImport}>
              Importer
            </Button>
          </div>
        </div>
      </Modal>



      <Card className="rounded-3xl border-slate-200/90 bg-white p-5 shadow-sm">
        <div className="space-y-4">
          <div className="flex items-start justify-between gap-4">
            <div>
              <p className="text-xs font-bold uppercase tracking-[0.18em] text-cyan-600">
                Actions rapides
              </p>
              <h3 className="mt-1 text-sm font-black text-slate-950">
                Gestion des documents
              </h3>
            </div>
                      

            <Button
              variant="secondary"
              size="sm"
              onClick={() => setIsQuickActionsCollapsed((value) => !value)}
              className="shrink-0"
            >
              <span className="inline-flex items-center gap-2">
                {isQuickActionsCollapsed ? (
                  <ChevronDown className="h-4 w-4 transition-transform duration-300" />
                ) : (
                  <ChevronUp className="h-4 w-4 transition-transform duration-300" />
                )}
                {isQuickActionsCollapsed ? "Afficher" : "Masquer"}
              </span>
            </Button>
          </div>

          <div
            className={cn(
              "overflow-hidden transition-all duration-300 ease-in-out",
              isQuickActionsCollapsed
                ? "max-h-0 -translate-y-2 opacity-0"
                : "max-h-[2000px] translate-y-0 opacity-100",
            )}
          >
            <div className="space-y-4 pt-1">
              <div className="flex gap-2 overflow-x-auto rounded-2xl bg-slate-100 p-1">
                {quickActionTabs.map((tab) => {
                  const isActive = activeQuickActionTab === tab.id;

                  return (
                    <button
                      key={tab.id}
                      type="button"
                      onClick={() => setActiveQuickActionTab(tab.id)}
                      className={cn(
                        "shrink-0 rounded-xl px-3 py-2 text-xs font-bold transition-all",
                        isActive
                          ? "bg-white text-cyan-700 shadow-sm ring-1 ring-slate-200"
                          : "text-slate-500 hover:bg-white/70 hover:text-slate-900",
                      )}
                    >
                      {tab.label}
                    </button>
                  );
                })}
              </div>

              {activeQuickActionTab === "dossier" && (
                <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
                  <Button variant="secondary" size="sm" icon={Save} onClick={handleSaveDraft}>
                    Brouillon
                  </Button>

                  <Button
                    variant="secondary"
                    size="sm"
                    icon={FileDown}
                    onClick={handleDownloadMedicalDossierPdf}
                    loading={pdfDownloading}
                  >
                    PDF
                  </Button>

                  <Button
                    size="sm"
                    icon={ShieldCheck}
                    onClick={() => handleSubmit({ confirm: true })}
                    disabled={duplicateCheckLoading}
                    className="bg-gradient-to-r from-cyan-600 to-teal-600 shadow-lg shadow-cyan-600/20 hover:from-cyan-700 hover:to-teal-700"
                  >
                    Valider
                  </Button>

                  <Button variant="secondary" size="sm" icon={Printer} onClick={handlePrintMedicalDossierPdf}>
                    Imprimer
                  </Button>
                </div>
              )}

              {activeQuickActionTab === "visite" && (
                <div className="grid gap-3">
                  <Select
                    label="Visite"
                    value={selectedQuickVisitId ?? ""}
                    onChange={(event) =>
                      setSelectedQuickVisitId(event.target.value ? Number(event.target.value) : null)
                    }
                    options={[
                      { value: "", label: workerVisits.length ? "Sélectionner une visite" : "Aucune visite" },
                      ...workerVisits.map((visit) => ({
                        value: String(visit.id),
                        label: `${visit.visit_date || "Date inconnue"}${visit.status ? ` - ${visit.status}` : ""}`,
                      })),
                    ]}
                  />

                  <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
                    <Button variant="secondary" size="sm" icon={Save} onClick={handleSaveDraft}>
                      Brouillon
                    </Button>

                    <Button
                      variant="secondary"
                      size="sm"
                      icon={FileDown}
                      onClick={handleDownloadMedicalVisitPdf}
                      loading={pdfDownloading}
                      disabled={!selectedQuickVisitId}
                    >
                      PDF
                    </Button>

                    <Button
                      size="sm"
                      icon={ShieldCheck}
                      onClick={handleValidateVisit}
                      loading={visitValidating}
                      disabled={!selectedQuickVisitId || visitValidating || !canSignMedicalDocuments}
                      title={!canSignMedicalDocuments ? signatureAuthorizationMessage : undefined}
                    >
                      Valider visite
                    </Button>

                    <Button
                      variant="secondary"
                      size="sm"
                      icon={Printer}
                      onClick={handlePrintMedicalVisitPdf}
                      disabled={!selectedQuickVisitId}
                    >
                      Imprimer
                    </Button>
                  </div>
                </div>
              )}

              {activeQuickActionTab === "aptitude" &&
                renderDocumentCollection({
                  title: "Certificat d'aptitude",
                  items: aptitudeCertificates.map((item) => ({
                    id: item.id,
                    date: item.issue_date,
                    doctor: item.doctor_name || undefined,
                    status: item.status,
                    pdfAvailable: true,
                  })),
                  selectedId: selectedAptitudeCertificateId,
                  onSelect: (id) => {
                    const selected = aptitudeCertificates.find((item) => item.id === id);
                    if (!selected) return;
                    setAptitudeCertificate(selected);
                    setAptitudeForm(
                      createEmptyMedicalAptitudeFormState(
                        selected,
                        worker,
                        Number(campaignId),
                        medicalVisit?.id || aptitudeForm.medicalVisitId,
                        doctorName,
                      ),
                    );
                    setAptitudePdfPreviewUrl(null);
                  },
                  emptyMessage: "Aucun document disponible.",
                  generateAction: () => setActiveTab("medicalAptitude"),
                  downloadAction: handleDownloadAptitudePdf,
                  editAction: () => setActiveTab("medicalAptitude"),
                  printAction: handlePrintAptitudePdf,
                  generateLabel: "Generer",
                })}

              {activeQuickActionTab === "orientation" &&
                renderDocumentCollection({
                  title: "Orientation medicale",
                  items: orientations.map((item) => ({
                    id: item.id,
                    date: item.orientation_date,
                    doctor: item.doctor_name || undefined,
                    status: item.status,
                    pdfAvailable: true,
                  })),
                  selectedId: selectedOrientationCertificateId,
                  onSelect: setSelectedOrientationCertificateId,
                  emptyMessage: "Aucun document disponible.",
                  generateAction: () => setActiveTab("medicalOrientation"),
                  downloadAction: () => {
                    if (!selectedOrientationCertificateId) {
                      setNotice({ type: "error", message: "Selectionnez une orientation medicale." });
                      return;
                    }
                    const selected = orientations.find((item) => item.id === selectedOrientationCertificateId);
                    if (selected) {
                      handleSelectOrientation(selected);
                    }
                    handleDownloadOrientationPdf();
                  },
                  editAction: () => {
                    if (!selectedOrientationCertificateId) {
                      setNotice({ type: "error", message: "Selectionnez une orientation medicale." });
                      return;
                    }
                    const selected = orientations.find((item) => item.id === selectedOrientationCertificateId);
                    if (selected) {
                      handleSelectOrientation(selected);
                    }
                    setActiveTab("medicalOrientation");
                  },
                  printAction: () => {
                    if (!selectedOrientationCertificateId) {
                      setNotice({ type: "error", message: "Selectionnez une orientation medicale." });
                      return;
                    }
                    const selected = orientations.find((item) => item.id === selectedOrientationCertificateId);
                    if (selected) {
                      handleSelectOrientation(selected);
                    }
                    handlePrintOrientation();
                  },
                  generateLabel: "Generer",
                })}

              {activeQuickActionTab === "ordonnance" &&
                renderDocumentCollection({
                  title: "Ordonnance",
                  items: prescriptions.map((item) => ({
                    id: item.id,
                    date: item.prescription_date,
                    doctor: item.doctor_name || undefined,
                    status: item.status,
                    pdfAvailable: true,
                  })),
                  selectedId: selectedPrescriptionId,
                  onSelect: setSelectedPrescriptionId,
                  emptyMessage: "Aucun document disponible.",
                  generateAction: () => setActiveTab("ordonnance"),
                  downloadAction: () => {
                    if (!selectedPrescriptionId) {
                      setNotice({ type: "error", message: "Selectionnez une ordonnance." });
                      return;
                    }
                    const selected = prescriptions.find((item) => item.id === selectedPrescriptionId);
                    if (selected) {
                      handleSelectPrescription(selected);
                    }
                    handleDownloadPrescriptionPdf();
                  },
                  editAction: () => {
                    if (!selectedPrescriptionId) {
                      setNotice({ type: "error", message: "Selectionnez une ordonnance." });
                      return;
                    }
                    const selected = prescriptions.find((item) => item.id === selectedPrescriptionId);
                    if (selected) {
                      handleSelectPrescription(selected);
                    }
                    setActiveTab("ordonnance");
                  },
                  printAction: () => {
                    if (!selectedPrescriptionId) {
                      setNotice({ type: "error", message: "Selectionnez une ordonnance." });
                      return;
                    }
                    const selected = prescriptions.find((item) => item.id === selectedPrescriptionId);
                    if (selected) {
                      handleSelectPrescription(selected);
                    }
                    handlePrintPrescription();
                  },
                  generateLabel: "Creer",
                })}
              

              {notice ? (
                <div
                  className={cn(
                    "flex items-start gap-3 rounded-2xl border px-4 py-3 text-sm font-medium",
                    notice.type === "error"
                      ? "border-rose-200 bg-rose-50 text-rose-700"
                      : "border-emerald-200 bg-emerald-50 text-emerald-700",
                  )}
                >
                  <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
                  <span>{notice.message}</span>
                </div>
              ) : null}
            </div>
          </div>
        </div>
      </Card>
      <div className="grid grid-cols-1 lg:grid-cols-[1fr_4fr] gap-4">
        <div className="space-y-3">
          <Card className="h-fit w-[276px] p-2 lg:sticky lg:top-6">
           <div className="mb-4 rounded-xl border border-slate-200 bg-white px-4 py-3 shadow-sm">
              <div className="flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-cyan-50 text-sm font-bold text-cyan-700">
                  {(form.firstName?.[0] || "").toUpperCase()}
                  {(form.lastName?.[0] || "").toUpperCase()}
                </div>

                <div className="min-w-0 flex-1">
                  <h3 className="truncate text-base font-bold text-slate-900">
                    {form.firstName} {form.lastName}
                  </h3>

                  <div className="mt-0.5 flex items-center gap-2 text-xs text-slate-500">
                    <span>Dossier médical</span>
                    <span> 
                       <div className="flex items-center gap-1.5">
                        <BadgeCheck className="w-3.5 h-3.5 text-slate-400" /> {form.employeeCode || "Sans matricule"}
                        </div>
                    </span>
                        
                  </div>
                </div>
              </div>
            </div>

            <nav className="space-y-4">
              <div className="grid grid-cols-2 gap-2">
                <button
                  type="button"
                  onClick={() => {
                    setActiveSectionGroup("medicalFolder");
                    setActiveTab("personal");
                  }}
                  className={cn(
                    "rounded-[0.3rem] px-1 py-1 text-center text-sm font-black transition",
                    activeSectionGroup === "medicalFolder"
                      ? "bg-cyan-600 text-white"
                      : "border border-slate-200 bg-white text-slate-700 hover:bg-slate-100",
                  )}
                >
                  Medical Folder
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setActiveSectionGroup("visitsMedical");
                    setActiveTab("internalVisit");
                  }}
                  className={cn(
                    "rounded-[0.3rem] px-3 py-1 text-center text-sm font-black transition",
                    activeSectionGroup === "visitsMedical"
                      ? "bg-cyan-600 text-white"
                      : "border border-slate-200 bg-white text-slate-700 hover:bg-slate-100",
                  )}
                >
                  Visits Medical
                </button>
              </div>

              {activeSectionGroup === "medicalFolder" ? (
                <div className="space-y-1">
                  {medicalFolderSectionDefinitions.map((section) => {
                    const Icon = section.icon;
                    const isActive = activeTab === section.id;

                    return (
                      <button
                        key={section.id}
                        onClick={() => setActiveTab(section.id)}
                        className={cn(
                          "flex w-full items-center gap-2 rounded-2xl px-3 py-3 text-left transition",
                          isActive
                            ? "bg-cyan-600 text-white"
                            : "text-slate-700 hover:bg-slate-100",
                        )}
                      >
                        <Icon className="h-5 w-5 shrink-0" />
                        <span className="flex-1 text-sm font-semibold">{section.label}</span>
                      </button>
                    );
                  })}
                </div>
              ) : (
                <div className="space-y-1">
                  {medicalVisitSectionDefinitions.map((section) => {
                    const Icon = section.icon;
                    const isActive = activeTab === section.id;
                    const isDisabled = visitSectionSaving;

                    return (
                      <button
                        key={section.id}
                        onClick={() => {
                          void handleSwitchVisitSection(section.id);
                        }}
                        disabled={isDisabled}
                        className={cn(
                          "flex w-full items-center gap-2 rounded-2xl px-3 py-3 text-left transition",
                          isActive
                            ? "bg-cyan-600 text-white"
                            : "text-slate-700 hover:bg-slate-100",
                          isDisabled ? "cursor-not-allowed opacity-70" : "",
                        )}
                      >
                        <Icon className="h-5 w-5 shrink-0" />
                        <span className="flex-1 text-sm font-semibold">{section.label}</span>
                      </button>
                    );
                  })}
                </div>
              )}
            </nav>
          </Card>
        </div>

        <div className="space-y-4">
          {activeSectionGroup === "visitsMedical" && worker && !visitLoading ? (
            <MedicalVisitsPanel
              visits={selectedWorkerMedicalVisits}
              selectedVisitId={normalizedVisitId}
              companyName={currentCampaign?.company_name}
              branchName={currentCampaign?.branch_name}
              siteName={currentCampaign?.site_name}
              campaignName={currentCampaign?.title || currentCampaign?.company_name}
              visitHistory={workerVisitTestHistory}
              isCollapsible={true}
              onOpen={(nextVisitId) =>
                navigate(buildWorkerMedicalVisitRoute(campaignId!, worker.id, nextVisitId), {
                  state: { tab: "internalVisit" },
                })
              }
              onCreateNew={() => {
                void handleCreateNewVisit();
              }}
            />
          ) : null}
          {renderSectionContent(activeTab)}
        </div>
      </div>

      <div className="bottom-4 z-20">
        <Card className="border-slate-200/90 bg-white/95 p-4 shadow-2xl shadow-slate-200/60 backdrop-blur">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div>
              <p className="text-sm font-black text-slate-950">Barre d'actions medicales</p>
              <p className="mt-1 text-sm text-slate-500">
                Brouillon, apercu, impression et confirmation finale du dossier.
              </p>
            </div>
            <div className="flex flex-wrap gap-3">
              <Button variant="secondary" size="sm" icon={Save} onClick={handleSaveDraft}>
                Enregistrer brouillon
              </Button>
              <Button variant="secondary" size="sm" icon={FileDown} onClick={handlePrint}>
                Apercu dossier
              </Button>
              <Button variant="secondary" size="sm" icon={FileDown} onClick={() => setActiveTab("internalVisit")}>
                Apercu fiche visite
              </Button>
              <Button variant="secondary" size="sm" icon={FileDown} onClick={handlePrint}>
                Imprimer
              </Button>
                <Button
                  size="sm"
                  icon={ShieldCheck}
                  onClick={() => handleSubmit({ confirm: true })}
                  disabled={duplicateCheckLoading}
                  className="bg-gradient-to-r from-cyan-600 to-teal-600 shadow-lg shadow-cyan-600/20 hover:bg-gradient-to-r hover:from-cyan-700 hover:to-teal-700"
                >
                  Confirmer le dossier
                </Button>
                <Button
                  type="button"
                  size="sm"
                  icon={UserPlus}
                  aria-label="Ajouter un travailleur"
                  title="Ajouter un nouveau travailleur"
                  onClick={() => navigate(`/app/workspace/${campaignId}/workers/create`)}
                  className="bg-gradient-to-r from-cyan-600 to-teal-600 shadow-lg shadow-cyan-600/20 hover:bg-gradient-to-r hover:from-cyan-700 hover:to-teal-700"
                >
                  Ajouter un travailleur
                </Button>
            </div>
          </div>
        </Card>
      </div>
    </div>
  );
};








