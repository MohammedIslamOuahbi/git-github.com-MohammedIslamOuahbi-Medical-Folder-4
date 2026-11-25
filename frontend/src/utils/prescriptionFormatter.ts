export type StructuredPrescriptionItem = {
  brand_name?: string | null;
  medication_name?: string | null;
  generic_name?: string | null;
  strength?: string | null;
  dose_quantity?: string | null;
  dose_unit?: string | null;
  frequency?: string | null;
  frequency_custom?: string | null;
  duration_value?: string | null;
  duration_unit?: string | null;
  instructions?: string | null;
  dosage?: string | null;
  duration?: string | null;
};

const clean = (value?: string | null) => (value || "").trim().replace(/[,.;\s]+$/g, "");

export const formatPrescriptionItemSentence = (item: StructuredPrescriptionItem) => {
  const title = [clean(item.brand_name || item.medication_name || item.generic_name), clean(item.strength)]
    .filter(Boolean)
    .join(" ");
  const legacyDose = clean(item.dosage);
  const dose = [clean(item.dose_quantity), clean(item.dose_unit)].filter(Boolean).join(" ") || legacyDose;
  const frequency = clean(item.frequency_custom || item.frequency);
  const legacyDuration = clean(item.duration);
  const durationBase = [clean(item.duration_value), clean(item.duration_unit)].filter(Boolean).join(" ");
  const duration = durationBase ? `pendant ${durationBase}` : legacyDuration ? `pendant ${legacyDuration}` : "";
  const instructions = clean(item.instructions);
  const details = [dose, frequency, duration, instructions ? instructions.toLowerCase() : ""]
    .filter(Boolean)
    .join(", ");

  if (!title && !details) return "";
  if (!title) return `${details}.`;
  if (!details) return `${title}.`;
  return `${title} - ${details}.`;
};

export const buildPrescriptionPreviewText = (items: StructuredPrescriptionItem[]) => {
  const sentences = items.map(formatPrescriptionItemSentence).filter(Boolean);
  if (!sentences.length) {
    return "R/";
  }
  return `R/\n\n${sentences.map((sentence, index) => `${index + 1}. ${sentence}`).join("\n\n")}`;
};
