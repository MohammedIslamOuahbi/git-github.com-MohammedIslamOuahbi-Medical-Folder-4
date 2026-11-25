import type { OperationMode } from "@/config/runtime";

export const shouldRequireDatabaseHealth = (mode: OperationMode) => mode === "server";
