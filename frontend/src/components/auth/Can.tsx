import type { ReactNode } from "react";

import { useCan } from "@/hooks/usePermissions";

export const Can = ({
  permission,
  fallback = null,
  children,
}: {
  permission: string;
  fallback?: ReactNode;
  children: ReactNode;
}) => {
  const can = useCan(permission);
  return can ? <>{children}</> : <>{fallback}</>;
};
