const pad = (value: number) => String(value).padStart(2, "0");

/**
 * Parse:
 * - yyyy-MM-dd
 * - yyyy-MM-ddTHH:mm:ss
 * - yyyy-MM-dd HH:mm:ss
 */
const parseIsoParts = (value: string) => {
  const match = value
    .trim()
    .match(/^(\d{4})-(\d{2})-(\d{2})(?:[T ](\d{2}):(\d{2})(?::(\d{2}))?)?/);

  if (!match) return null;

  const [, yyyy, mm, dd, hh = "00", min = "00", ss = "00"] = match;

  return {
    yyyy,
    mm,
    dd,
    hh,
    min,
    ss,
  };
};

const asDate = (
  value: string | Date | null | undefined,
): Date | null => {
  if (!value) return null;

  if (value instanceof Date) {
    return Number.isNaN(value.getTime()) ? null : value;
  }

  const raw = value.trim();

  if (!raw) return null;

  const iso = parseIsoParts(raw);

  if (iso) {
    const date = new Date(
      Number(iso.yyyy),
      Number(iso.mm) - 1,
      Number(iso.dd),
      Number(iso.hh),
      Number(iso.min),
      Number(iso.ss),
    );

    return Number.isNaN(date.getTime()) ? null : date;
  }

  const display = raw.match(/^(\d{2})\/(\d{2})\/(\d{4})$/);

  if (display) {
    const [, dd, mm, yyyy] = display;

    const date = new Date(
      Number(yyyy),
      Number(mm) - 1,
      Number(dd),
    );

    return Number.isNaN(date.getTime()) ? null : date;
  }

  const parsed = new Date(raw);

  return Number.isNaN(parsed.getTime()) ? null : parsed;
};

/**
 * Display:
 * yyyy-MM-dd
 * yyyy-MM-ddTHH:mm:ss
 * yyyy-MM-dd HH:mm:ss
 *
 * =>
 *
 * dd/MM/yyyy
 */
export const formatDisplayDate = (
  value: string | Date | null | undefined,
): string => {
  if (!value) return "";

  if (typeof value === "string") {
    const iso = parseIsoParts(value);

    if (iso) {
      return `${iso.dd}/${iso.mm}/${iso.yyyy}`;
    }

    const display = value.trim().match(/^(\d{2})\/(\d{2})\/(\d{4})$/);

    if (display) {
      return value.trim();
    }
  }

  const date = asDate(value);

  if (!date) return "";

  return `${pad(date.getDate())}/${pad(date.getMonth() + 1)}/${date.getFullYear()}`;
};

/**
 * Display:
 * yyyy-MM-ddTHH:mm:ss
 *
 * =>
 *
 * dd/MM/yyyy HH:mm
 */
export const formatDisplayDateTime = (
  value: string | Date | null | undefined,
): string => {
  if (!value) return "";

  if (typeof value === "string") {
    const iso = parseIsoParts(value);

    if (iso) {
      return `${iso.dd}/${iso.mm}/${iso.yyyy} ${iso.hh}:${iso.min}`;
    }
  }

  const date = asDate(value);

  if (!date) return "";

  return `${pad(date.getDate())}/${pad(
    date.getMonth() + 1,
  )}/${date.getFullYear()} ${pad(date.getHours())}:${pad(
    date.getMinutes(),
  )}`;
};

/**
 * Accepts:
 *
 * dd/MM/yyyy
 * yyyy-MM-dd
 * Date
 *
 * Returns:
 *
 * yyyy-MM-dd
 */
export const toIsoDate = (
  value: string | Date | null | undefined,
): string => {
  if (!value) return "";

  if (value instanceof Date) {
    if (Number.isNaN(value.getTime())) return "";

    return `${value.getFullYear()}-${pad(
      value.getMonth() + 1,
    )}-${pad(value.getDate())}`;
  }

  const raw = value.trim();

  if (!raw) return "";

  const iso = parseIsoParts(raw);

  if (iso) {
    return `${iso.yyyy}-${iso.mm}-${iso.dd}`;
  }

  const display = raw.match(/^(\d{2})\/(\d{2})\/(\d{4})$/);

  if (display) {
    const [, dd, mm, yyyy] = display;

    return `${yyyy}-${mm}-${dd}`;
  }

  return "";
};