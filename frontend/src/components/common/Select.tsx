import type { SelectHTMLAttributes } from "react";
import type { Option } from "@/types/common";
import { cn } from "@/utils/cn";
import { translateUiText } from "@/utils/uiText";

interface SelectProps extends SelectHTMLAttributes<HTMLSelectElement> {
  label?: string;
  options: Option[];
  error?: string | null;
}

export const Select = ({ label, options, error, className, ...props }: SelectProps) => (
  <label className="block space-y-2">
    {label && <span className="text-xs font-bold tracking-[0.02em] text-slate-700">{translateUiText(label)}</span>}
    <select
      className={cn(
        "w-full rounded-md border border-slate-200 bg-white px-3 py-2.5 text-sm font-medium text-ink-800 outline-none transition-all duration-150 focus:border-blue-600 focus:ring-4 focus:ring-blue-600/10",
        error && "border-rose-300",
        className,
      )}
      {...props}
    >
      {options.map((option) => (
        <option key={option.value} value={option.value}>
          {translateUiText(option.label)}
        </option>
      ))}
    </select>
    {error && <span className="text-[11px] font-medium text-rose-600">{translateUiText(error)}</span>}
  </label>
);
