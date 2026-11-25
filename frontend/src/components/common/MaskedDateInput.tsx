import { useEffect, useState } from "react";
import type { ChangeEvent, FocusEvent, InputHTMLAttributes } from "react";

import { cn } from "@/utils/cn";
import { translateUiText } from "@/utils/uiText";

type MaskedDateInputProps = Omit<
  InputHTMLAttributes<HTMLInputElement>,
  "type" | "value" | "onChange"
> & {
  label?: string;
  value?: string | null;
  error?: string | null;
  onChange?: (isoDate: string) => void;
};

const formatDigitsToDisplayDate = (value: string) => {
  const digits = value.replace(/\D/g, "").slice(0, 8);

  if (digits.length <= 2) return digits;
  if (digits.length <= 4) return `${digits.slice(0, 2)}/${digits.slice(2)}`;
  return `${digits.slice(0, 2)}/${digits.slice(2, 4)}/${digits.slice(4)}`;
};

const displayDateToIso = (display: string) => {
  const digits = display.replace(/\D/g, "");
  if (digits.length !== 8) return "";

  const dd = digits.slice(0, 2);
  const mm = digits.slice(2, 4);
  const yyyy = digits.slice(4, 8);

  const date = new Date(`${yyyy}-${mm}-${dd}T00:00:00`);
  if (
    Number.isNaN(date.getTime()) ||
    String(date.getDate()).padStart(2, "0") !== dd ||
    String(date.getMonth() + 1).padStart(2, "0") !== mm ||
    String(date.getFullYear()) !== yyyy
  ) {
    return "";
  }

  return `${yyyy}-${mm}-${dd}`;
};

const isoToDisplayDate = (iso?: string | null) => {
  if (!iso) return "";
  const match = String(iso).match(/^(\d{4})-(\d{2})-(\d{2})/);
  if (!match) return "";
  const [, yyyy, mm, dd] = match;
  return `${dd}/${mm}/${yyyy}`;
};

export const MaskedDateInput = ({
  label,
  value,
  error,
  className,
  onChange,
  onBlur,
  disabled,
  readOnly,
  placeholder,
  maxLength,
  ...props
}: MaskedDateInputProps) => {
  const [displayValue, setDisplayValue] = useState(isoToDisplayDate(value));

  useEffect(() => {
    setDisplayValue(isoToDisplayDate(value));
  }, [value]);

  const handleChange = (event: ChangeEvent<HTMLInputElement>) => {
    const formattedValue = formatDigitsToDisplayDate(event.target.value);
    setDisplayValue(formattedValue);

    const isoDate = displayDateToIso(formattedValue);
    onChange?.(isoDate);
  };

  const handleBlur = (event: FocusEvent<HTMLInputElement>) => {
    const isoDate = displayDateToIso(displayValue);
    if (!displayValue.replace(/\D/g, "")) {
      setDisplayValue("");
      onChange?.("");
    } else if (isoDate) {
      setDisplayValue(isoToDisplayDate(isoDate));
      onChange?.(isoDate);
    }

    onBlur?.(event);
  };

  return (
    <label className="block space-y-2">
      {label && (
        <span className="text-xs font-bold tracking-[0.02em] text-slate-700">
          {label}
        </span>
      )}

      <div className="relative">
        <input
          {...props}
          type="text"
          inputMode="numeric"
          placeholder={translateUiText(placeholder || "jj/mm/aaaa")}
          maxLength={maxLength ?? 10}
          disabled={disabled}
          readOnly={readOnly}
          value={displayValue}
          onChange={handleChange}
          onBlur={handleBlur}
          className={cn(
            "w-full rounded-lg border border-slate-200 bg-white px-3 py-2.5 text-sm font-medium text-slate-800 outline-none transition-all duration-200 placeholder:text-slate-400",
            "focus:border-blue-600 focus:ring-4 focus:ring-blue-600/10",
            error &&
              "border-rose-300 bg-rose-50/60 focus:border-rose-400 focus:ring-rose-100",
            className,
          )}
        />

      </div>

      {error && (
        <span className="inline-flex items-center gap-1 text-xs font-semibold text-rose-600">
          <span className="h-1.5 w-1.5 rounded-full bg-rose-500" />
          {translateUiText(error)}
        </span>
      )}
    </label>
  );
};
