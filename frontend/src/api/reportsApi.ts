import apiClient from "./axios";
import type { ReportFilter } from "@/types/entities";

export const reportsApi = {
  campaignSummary: async (params?: ReportFilter) => {
    const { data } = await apiClient.get("/reports/campaign-summary", { params });
    return data;
  },
  companyWorkers: async (params?: ReportFilter) => {
    const { data } = await apiClient.get("/reports/company-workers", { params });
    return data;
  },
  abnormalResults: async (params?: ReportFilter) => {
    const { data } = await apiClient.get("/reports/abnormal-results", { params });
    return data;
  },
  workerMedicalHistory: async (params?: ReportFilter) => {
    const { data } = await apiClient.get("/reports/worker-medical-history", { params });
    return data;
  },
};
