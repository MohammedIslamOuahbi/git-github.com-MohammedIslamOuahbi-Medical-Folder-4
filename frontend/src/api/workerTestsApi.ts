import { createEntityApi } from "./entityFactory";
import type { WorkerTest } from "@/types/entities";

export const workerTestsApi = createEntityApi<WorkerTest>("/worker-tests");
