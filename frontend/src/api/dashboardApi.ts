import apiClient from "./axios";
import type {
  AdminDashboardData,
  AssistantDashboardData,
  DashboardMeData,
  DoctorDashboardData,
} from "@/types/dashboard";

export const dashboardApi = {
  getAdmin: async () => {
    const { data } = await apiClient.get<AdminDashboardData>("/dashboard/admin");
    return data;
  },
  getDoctor: async () => {
    const { data } = await apiClient.get<DoctorDashboardData>("/dashboard/doctor");
    return data;
  },
  getAssistant: async () => {
    const { data } = await apiClient.get<AssistantDashboardData>("/dashboard/assistant");
    return data;
  },
  getMe: async () => {
    const { data } = await apiClient.get<DashboardMeData>("/dashboard/me");
    return data;
  },
};
