import { formatDisplayDate, formatDisplayDateTime } from "@/utils/date";

export const formatDate = (value?: string | null) => {
  return formatDisplayDate(value) || "N/A";
};

export const formatDateTime = (value?: string | null) => {
  return formatDisplayDateTime(value) || "N/A";
};

export const formatNumber = (value?: number | null) =>
  new Intl.NumberFormat().format(value ?? 0);
