import { createEntityApi } from "./entityFactory";
import { mutationHeaders } from "./localMutation";
import type { Company } from "@/types/entities";

type CompanyPayload = Omit<Partial<Company>, "email"> & { email?: string | null };

const companyResource = createEntityApi<Company, CompanyPayload>("/companies");

// EmailStr accepts null for an absent optional email, but rejects an empty string.
// Keep undefined omitted for partial updates and null explicit when clearing it.
const prepareCompanyPayload = (payload: CompanyPayload): CompanyPayload => ({
  ...payload,
  ...(payload.email === undefined ? {} : { email: payload.email?.trim() || null }),
});

export const companiesApi = {
  ...companyResource,
  create: async (payload: CompanyPayload) => {
    const prepared = prepareCompanyPayload(payload);
    const operation = await mutationHeaders("new-company", "create", 0, prepared);
    return companyResource.create(prepared, operation.headers as never);
  },
  update: (id: number | string, payload: CompanyPayload) =>
    (async () => {
      const prepared = prepareCompanyPayload(payload);
      const operation = await mutationHeaders(id, "company:update", 1, prepared);
      return companyResource.update(id, prepared, operation.headers as never);
    })(),
};
