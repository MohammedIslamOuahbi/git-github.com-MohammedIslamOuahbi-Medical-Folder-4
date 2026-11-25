import type { TextareaHTMLAttributes } from "react";

import { cn } from "@/utils/cn";
import { translateUiText } from "@/utils/uiText";

interface TextareaProps extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  label?: string;
  error?: string | null;
}

export const Textarea = ({ label, error, className, ...props }: TextareaProps) => (
  <label className="block space-y-2">
    {label ? (
      <span className="text-xs font-bold tracking-[0.02em] text-slate-700">
        {translateUiText(label)}
      </span>
    ) : null}
    <textarea
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
    {error ? (
      <span className="inline-flex items-center gap-1 text-xs font-semibold text-rose-600">
        <span className="h-1.5 w-1.5 rounded-full bg-rose-500" />
        {translateUiText(error)}
      </span>
    ) : null}
  </label>
);
