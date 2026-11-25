import { createEntityApi } from "./entityFactory";
import type { DrillingSite } from "@/types/entities";

export const drillingSitesApi = createEntityApi<DrillingSite>("/drilling-sites");
