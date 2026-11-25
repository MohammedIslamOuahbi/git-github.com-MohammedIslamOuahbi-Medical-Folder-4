import type { Company } from "@/types/entities";

const isYmd = (value?: string | null) => Boolean(value && /^\d{4}-\d{2}-\d{2}$/.test(value));

export const getTodayYmd = () => new Date().toISOString().slice(0, 10);

export const hasValidContractDateRange = (
  contractStartDate?: string | null,
  contractEndDate?: string | null,
) => {
  if (!isYmd(contractStartDate) || !isYmd(contractEndDate)) {
    return false;
  }

  const startDate = contractStartDate as string;
  const endDate = contractEndDate as string;
  return startDate <= endDate;
};

export const isCompanyContractValidOnDate = (
  company: Pick<Company, "contract_start_date" | "contract_end_date"> | null | undefined,
  dateYmd: string,
) => {
  if (!company || !isYmd(dateYmd)) {
    return false;
  }

  if (!hasValidContractDateRange(company.contract_start_date, company.contract_end_date)) {
    return false;
  }

  return company.contract_start_date! <= dateYmd && dateYmd <= company.contract_end_date!;
};
