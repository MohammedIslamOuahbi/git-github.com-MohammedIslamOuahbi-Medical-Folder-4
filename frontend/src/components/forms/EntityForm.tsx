import type { FormEvent, ReactNode } from "react";
import { Button } from "@/components/common/Button";

export const EntityForm = ({
  children,
  onSubmit,
  submitLabel = "Enregistrer",
}: {
  children: ReactNode;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  submitLabel?: string;
}) => (
  <form className="space-y-4" onSubmit={onSubmit}>
    {children}
    <div className="flex justify-end">
      <Button type="submit">{submitLabel}</Button>
    </div>
  </form>
);
