import { createEntityApi } from "./entityFactory";
import type { Branch } from "@/types/entities";

export const branchesApi = createEntityApi<Branch>("/branches");
