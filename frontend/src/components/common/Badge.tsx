import type { ReactNode } from "react";
import { cn } from "@/utils/cn";
import { translateUiText } from "@/utils/uiText";

const colorMap: Record<string, string> = {
  active: "border-emerald-200 bg-emerald-50 text-emerald-700",
  completed: "border-sky-200 bg-sky-50 text-sky-700",
  pending: "border-amber-200 bg-amber-50 text-amber-700",
  failed: "border-rose-200 bg-rose-50 text-rose-700",
  inactive: "border-slate-200 bg-slate-100 text-slate-600",

  reviewed: "border-blue-200 bg-blue-50 text-blue-800",
  abnormal: "border-rose-200 bg-rose-50 text-rose-700",
  normal: "border-emerald-200 bg-emerald-50 text-emerald-700",
  fit: "border-emerald-200 bg-emerald-50 text-emerald-700",
  unfit: "border-rose-200 bg-rose-50 text-rose-700",

  draft: "border-slate-200 bg-slate-100 text-slate-600",
  synced: "border-emerald-200 bg-emerald-50 text-emerald-700",
  offline: "border-orange-200 bg-orange-50 text-orange-700",

  super_admin: "border-emerald-200 bg-emerald-50 text-emerald-700",
  admin: "border-purple-200 bg-purple-50 text-purple-700",
  doctor: "border-violet-200 bg-violet-50 text-violet-700",
  assistant: "border-amber-200 bg-amber-50 text-amber-700",
};

export const Badge = ({
  children,
  tone,
  className,
}: {
  children: ReactNode;
  tone?: string;
  className?: string;
}) => (
  <span
    className={cn(
      "inline-flex items-center rounded-md border px-2 py-1 text-[10px] font-extrabold uppercase tracking-[0.1em] shadow-sm",
      colorMap[tone || "inactive"] ||
        "border-slate-200 bg-slate-100 text-slate-600",
      className,
    )}
  >
    {typeof children === "string" ? translateUiText(children) : children}
  </span>
);
