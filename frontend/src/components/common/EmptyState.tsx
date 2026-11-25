import { Inbox } from "lucide-react";

import { Button } from "./Button";
import { translateUiText } from "@/utils/uiText";

export const EmptyState = ({
  title,
  description,
  actionLabel,
  onAction,
}: {
  title: string;
  description: string;
  actionLabel?: string;
  onAction?: () => void;
}) => (
  <div className="rounded-lg border border-slate-200 bg-white px-6 py-12 text-center shadow-sm">
    <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-lg border border-blue-200 bg-blue-50 text-blue-700">
      <Inbox className="h-7 w-7" />
    </div>

    <h3 className="mt-6 text-2xl font-black tracking-tight text-slate-950">
      {translateUiText(title)}
    </h3>

    <p className="mx-auto mt-3 max-w-md text-sm leading-7 text-slate-500">
      {translateUiText(description)}
    </p>

    {actionLabel && onAction && (
      <div className="mt-7">
        <Button
          onClick={onAction}
          className="rounded-lg px-5"
        >
          {translateUiText(actionLabel)}
        </Button>
      </div>
    )}
  </div>
);
