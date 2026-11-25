import type { ReactNode } from "react";

import { cn } from "@/utils/cn";

export const Card = ({
  className,
  children,
}: {
  className?: string;
  children: ReactNode;
}) => (
  <div
    className={cn(
      "rounded-lg border border-slate-200 bg-white px-5 py-4 shadow-sm transition-colors duration-150 hover:border-slate-300",
      className,
    )}
  >
    {children}
  </div>
);
