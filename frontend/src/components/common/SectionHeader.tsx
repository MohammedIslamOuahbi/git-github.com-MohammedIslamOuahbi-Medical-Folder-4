import type { LucideIcon } from "lucide-react";

import { Button } from "./Button";
import { translateUiText } from "@/utils/uiText";

export const SectionHeader = ({
  eyebrow,
  title,
  description,
  actionLabel,
  actionIcon,
  onAction,
}: {
  eyebrow?: string;
  title: string;
  description?: string;
  actionLabel?: string;
  actionIcon?: LucideIcon;
  onAction?: () => void;
}) => (
  <div className="mb-3 flex items-end justify-between gap-2">
    <div className="max-w-4xl">
      {eyebrow && (
        <div className="inline-flex items-center rounded-md border border-blue-200 bg-blue-50 px-2.5 py-1">
          <p className="text-[10px] font-extrabold uppercase tracking-[0.14em] text-blue-800">
            {translateUiText(eyebrow)}
          </p>
        </div>
      )}

      <h1 className="mt-3 text-2xl font-extrabold tracking-tight text-slate-950">
        {translateUiText(title)}
      </h1>

      {description && (
        <p className="mt-2 max-w-3xl text-sm leading-7 text-slate-500">
          {translateUiText(description)}
        </p>
      )}
    </div>

    {actionLabel && onAction && (
      <Button
        onClick={onAction}
        icon={actionIcon}
        className="rounded-lg px-5"
      >
        {translateUiText(actionLabel)}
      </Button>
    )}
  </div>
);
