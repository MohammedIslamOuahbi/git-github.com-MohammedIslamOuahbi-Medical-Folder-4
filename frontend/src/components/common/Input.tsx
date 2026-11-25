import type { InputHTMLAttributes } from "react";

import { cn } from "@/utils/cn";
import { translateUiText } from "@/utils/uiText";

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string | null;
}

export const Input = ({
  label,
  error,
  className,
  ...props
}: InputProps) => (
  <label className="block space-y-2">
    {label && (
      <span className="text-xs font-bold tracking-[0.02em] text-slate-700">
        {label}
      </span>
    )}

    <div className="relative">
      <input
        className={cn(
          "w-full rounded-lg border border-slate-200 bg-white px-3 py-2.5 text-sm font-medium text-slate-800 outline-none transition-all duration-200 placeholder:text-slate-400",
          "focus:border-blue-600 focus:ring-4 focus:ring-blue-600/10",
          error &&
            "border-rose-300 bg-rose-50/60 focus:border-rose-400 focus:ring-rose-100",
          className,
        )}
        {...props}
        placeholder={translateUiText(props.placeholder)}
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
