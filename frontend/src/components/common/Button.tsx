import type { ButtonHTMLAttributes } from "react";
import type { LucideIcon } from "lucide-react";
import { LoaderCircle } from "lucide-react";

import { cn } from "@/utils/cn";
import { translateUiText } from "@/utils/uiText";

type Variant = "primary" | "secondary" | "ghost" | "danger";
type Size = "sm" | "md" | "lg";

const variantStyles: Record<Variant, string> = {
  primary:
    "bg-blue-700 text-white shadow-sm hover:bg-blue-800",

  secondary:
    "border border-slate-200 bg-white text-slate-700 shadow-sm hover:border-slate-300 hover:bg-slate-50 hover:text-slate-950",

  ghost:
    "bg-transparent text-slate-600 hover:bg-slate-100 hover:text-slate-950",

  danger:
    "bg-rose-600 text-white shadow-lg shadow-rose-600/20 hover:-translate-y-0.5 hover:bg-rose-700 hover:shadow-xl hover:shadow-rose-600/25",
};

const sizeStyles: Record<Size, string> = {
  sm: "h-8 px-3 text-xs",
  md: "h-9 px-3.5 text-sm",
  lg: "h-10 px-4 text-sm",
};

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
  loading?: boolean;
  icon?: LucideIcon;
}

export const Button = ({
  children,
  variant = "primary",
  size = "md",
  loading,
  icon: Icon,
  className,
  ...props
}: ButtonProps) => (
  <button
    className={cn(
      "inline-flex items-center justify-center gap-2 rounded-md font-bold tracking-[0.01em] transition-colors duration-150 disabled:cursor-not-allowed disabled:opacity-60",
      variantStyles[variant],
      sizeStyles[size],
      className,
    )}
    disabled={loading || props.disabled}
    {...props}
  >
    {loading ? (
      <LoaderCircle className="h-4 w-4 animate-spin" />
    ) : Icon ? (
      <Icon className="h-4 w-4 shrink-0" />
    ) : null}

    {typeof children === "string" ? translateUiText(children) : children}
  </button>
);
