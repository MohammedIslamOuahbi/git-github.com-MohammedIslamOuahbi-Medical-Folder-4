import type { Worker } from "@/types/entities";

export const WORKER_ETAT_ACTUAL_OPTIONS: Array<{
  value: Worker["etat_actual"];
  label: string;
}> = [
  { value: "present", label: "Présent" },
  { value: "absence", label: "Absence" },
  { value: "sick_leave", label: "Congé maladie" },
  { value: "recovery", label: "Récupération" },
  { value: "mission", label: "Mission" },
  { value: "work_accident", label: "Accident de travail" },
  { value: "annual_leave", label: "Congé annuel" },
  { value: "unpaid_leave", label: "Congé sans solde" },
  { value: "maternity_leave", label: "Congé maternité" },
  { value: "paternity_leave", label: "Congé paternité" },
  { value: "retired", label: "Retraité" },
  { value: "suspended", label: "Suspendu" },
  { value: "terminated", label: "Fin de contrat" },
];
