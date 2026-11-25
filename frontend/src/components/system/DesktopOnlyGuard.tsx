import type { ReactNode } from "react";

export const DesktopOnlyGuard = ({ children }: { children: ReactNode }) => {
  return <>{children}</>;
};

