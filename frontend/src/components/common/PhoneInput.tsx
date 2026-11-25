import React from "react";
import { cn } from "@/utils/cn";

import mobilisLogo from "/mobilis.png";
import ooredooLogo from "/ooredoo.png";
import djezzyLogo from "/djezzy.png";

interface PhoneInputProps
  extends Omit<React.InputHTMLAttributes<HTMLInputElement>, "onChange"> {
  label?: string;
  error?: string | null;
  value: string;
  onChange: (value: string) => void;
}

export const PhoneInput = ({
  label = "Telephone",
  error,
  value,
  onChange,
  className,
  ...props
}: PhoneInputProps) => {
  const operator = value.startsWith("05")
    ? { name: "Ooredoo", logo: ooredooLogo }
    : value.startsWith("06")
      ? { name: "Mobilis", logo: mobilisLogo }
      : value.startsWith("07")
        ? { name: "Djezzy", logo: djezzyLogo }
        : null;

  return (
    <div className="space-y-1">
      {label && (
        <label className="text-xs font-bold tracking-[0.02em] text-slate-700">
          {label}
        </label>
      )}

      <div className="flex items-center gap-2">
        <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-lg border border-slate-200 bg-white shadow-sm">
          {operator ? (
            <img
              src={operator.logo}
              alt={operator.name}
              className="h-8 w-8 object-contain"
            />
          ) : (
            <span className="text-base text-slate-400">☎</span>
          )}
        </div>

        <input
          type="text"
          inputMode="numeric"
          pattern="\d{10}"
          maxLength={10}
          value={value}
          className={cn(
            "w-full rounded-lg border border-slate-200 bg-white px-3 py-2.5 text-sm font-medium text-slate-800 outline-none transition-all duration-200 placeholder:text-slate-400",
            "focus:border-blue-600 focus:ring-4 focus:ring-blue-600/10",
            error &&
              "border-rose-300 bg-rose-50/60 focus:border-rose-400 focus:ring-rose-100",
            className,
          )}
          onChange={(event) =>
            onChange(event.target.value.replace(/\D/g, "").slice(0, 10))
          }
          {...props}
        />
      </div>

      {error && <p className="text-xs font-medium text-rose-500">{error}</p>}
    </div>
  );
};
