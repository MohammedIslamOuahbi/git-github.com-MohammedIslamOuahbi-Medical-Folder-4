import axios from "axios";
import apiClient from "./axios";
import type { AuthUser, LoginPayload, TokenPair } from "@/types/auth";
import type { Role } from "@/types/common";
import { detectTauriRuntime, isUnconfiguredClientApiBaseUrl, normalizeApiBaseUrl, readStoredOperationMode } from "@/config/runtime";

const normalizeRole = (role: string): Role => {
  const normalized = role.trim().toLowerCase();
  if (normalized === "super_admin" || normalized === "super admin") return "Super Admin";
  if (normalized === "admin") return "Admin";
  if (normalized === "doctor") return "Doctor";
  return "Assistant";
};

const normalizeAuthUser = (user: AuthUser): AuthUser => {
  const signatureUrl =
    user.signatureUrl ??
    user.signature_url ??
    user.signatureImageUrl ??
    user.signaturePngUrl ??
    user.signature_png_url ??
    user.signaturePath ??
    user.signature_path ??
    null;
  const fullName =
    user.full_name ??
    `${user.first_name || ""} ${user.last_name || ""}`.trim();
  const hasSignature =
    typeof user.hasSignature === "boolean"
      ? user.hasSignature || Boolean(signatureUrl)
      : Boolean(signatureUrl || user.signature_png);

  return {
    ...user,
    full_name: fullName,
    role: normalizeRole(user.role),
    permissions: Array.from(new Set(user.permissions || [])).sort(),
    signatureUrl,
    signature_url: user.signature_url ?? signatureUrl,
    signatureImageUrl: signatureUrl,
    hasSignature,
  };
};

const isWebRuntime = () => !detectTauriRuntime();

const isMalformedApiBaseUrl = (value: string | null | undefined) => {
  if (!value?.trim()) {
    return true;
  }

  if (isUnconfiguredClientApiBaseUrl(value)) {
    return true;
  }

  try {
    normalizeApiBaseUrl(value);
    return false;
  } catch {
    return true;
  }
};

export const authApi = {
  login: async (payload: LoginPayload) => {
    const normalizedPayload = {
      email: payload.email.trim().toLowerCase(),
      password: payload.password,
    };
    const isTauriClientMode = detectTauriRuntime() && (readStoredOperationMode() || "client") === "client";
    const currentBaseUrl = apiClient.defaults.baseURL;

    if (isWebRuntime() && isMalformedApiBaseUrl(currentBaseUrl)) {
      const malformedBaseError = new axios.AxiosError(
        "API base URL is not configured",
        "ERR_BAD_REQUEST",
      );
      throw malformedBaseError;
    }

    if (!isTauriClientMode && isWebRuntime() && isUnconfiguredClientApiBaseUrl(currentBaseUrl)) {
      const unconfiguredBaseError = new axios.AxiosError(
        "API base URL is not configured",
        "ERR_BAD_REQUEST",
      );
      throw unconfiguredBaseError;
    }

    const { data } = await apiClient.post<TokenPair>("/auth/login", normalizedPayload);
    return data;
  },
  me: async () => {
    const { data } = await apiClient.get<AuthUser>("/auth/me");
    return normalizeAuthUser(data);
  },
  updateMe: async (payload: Partial<AuthUser> & { password?: string | null }) => {
    const { data } = await apiClient.put<AuthUser>("/auth/me", payload);
    return normalizeAuthUser(data);
  },
  getMySignature: async () => {
    const { data } = await apiClient.get<{
      hasSignature: boolean;
      signatureImageUrl: string | null;
      signatureUploadedAt: string | null;
    }>("/users/me/signature");
    return data;
  },
  getMySignatureBlob: async () => {
    const { data } = await apiClient.get<Blob>("/users/me/signature/file", {
      responseType: "blob",
    });
    return data;
  },
  uploadMySignature: async (file: File) => {
    const formData = new FormData();
    formData.append("file", file);
    const { data } = await apiClient.post<{
      hasSignature: boolean;
      signatureImageUrl: string | null;
      signatureUploadedAt: string | null;
    }>("/users/me/signature", formData);
    return data;
  },
  deleteMySignature: async () => {
    const { data } = await apiClient.delete<{
      hasSignature: boolean;
      signatureImageUrl: string | null;
      signatureUploadedAt: string | null;
    }>("/users/me/signature");
    return data;
  },
  logout: async () => {
    const { data } = await apiClient.post("/auth/logout");
    return data;
  },
  refresh: async (refresh_token: string) => {
    const { data } = await apiClient.post<TokenPair>("/auth/refresh", {
      refresh_token,
    });
    return data;
  },
};
