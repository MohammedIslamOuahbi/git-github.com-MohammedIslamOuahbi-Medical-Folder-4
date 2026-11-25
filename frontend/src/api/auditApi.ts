import { createEntityApi } from "./entityFactory";
import type { AuditLog } from "@/types/entities";

export const auditApi = createEntityApi<AuditLog>("/audit-logs");
