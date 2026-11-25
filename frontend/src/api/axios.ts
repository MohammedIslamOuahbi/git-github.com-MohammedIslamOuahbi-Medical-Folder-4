import { isSafetySuspension } from "../services/syncSafety";
import axios from "axios";
import { env } from "@/config/env";
import {
  API_BASE_URL_KEY,
  isUnconfiguredClientApiBaseUrl,
  normalizeApiBaseUrl,
  resolveRuntimeApiBaseUrl,
} from "@/config/runtime";
import type { DeviceIdentity } from "@/types/mission";
import { missionStorage, tokenStorage } from "@/utils/storage";

type ApiEnvelope<T> = {
  success: boolean;
  message: string;
  data: T;
};

const readApiBaseUrl = () => {
  if (typeof window === "undefined") {
    return env.apiBaseUrl;
  }

  const storedValue = window.localStorage.getItem(API_BASE_URL_KEY);
  if (!storedValue || isUnconfiguredClientApiBaseUrl(storedValue)) {
    if (storedValue && isUnconfiguredClientApiBaseUrl(storedValue)) {
      window.localStorage.removeItem(API_BASE_URL_KEY);
    }
    return resolveRuntimeApiBaseUrl();
  }

  try {
    return normalizeApiBaseUrl(storedValue);
  } catch {
    window.localStorage.removeItem(API_BASE_URL_KEY);
    return resolveRuntimeApiBaseUrl();
  }
};

const apiClient = axios.create({
  baseURL: readApiBaseUrl(),
  headers: {
    "Content-Type": "application/json",
  },
});

export const getApiBaseUrl = () => apiClient.defaults.baseURL || readApiBaseUrl();

export const setApiBaseUrl = (baseUrl: string) => {
  const normalized = normalizeApiBaseUrl(baseUrl);
  apiClient.defaults.baseURL = normalized;
  if (typeof window !== "undefined") {
    window.localStorage.setItem(API_BASE_URL_KEY, normalized);
  }
};

let isRefreshing = false;
let failedQueue: Array<{
  resolve: (token: string) => void;
  reject: (error: unknown) => void;
}> = [];

const isAuthEndpoint = (url?: string) => {
  if (!url) {
    return false;
  }

  return ["/auth/login", "/auth/logout", "/auth/refresh"].some((path) => url.includes(path));
};

const processQueue = (error: unknown, token?: string) => {
  failedQueue.forEach((promise) => {
    if (error) {
      promise.reject(error);
      return;
    }
    promise.resolve(token || "");
  });
  failedQueue = [];
};

apiClient.interceptors.request.use((config) => {
  const token = tokenStorage.getAccessToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  const missionCredential = missionStorage.getCredential();
  if (missionCredential) {
    config.headers["X-Mission-Device-Credential"] = missionCredential;
  }
  const cachedDevice = missionStorage.getCachedDevice<DeviceIdentity>();
  if (cachedDevice?.device_uuid) {
    config.headers["X-Device-UUID"] = cachedDevice.device_uuid;
  }
  if (typeof FormData !== "undefined" && config.data instanceof FormData) {
    delete config.headers["Content-Type"];
  }
  return config;
});

apiClient.interceptors.response.use(
  (response) => {
    const payload = response.data as ApiEnvelope<unknown> | unknown;
    if (
      payload &&
      typeof payload === "object" &&
      "success" in payload &&
      "data" in payload
    ) {
      response.data = (payload as ApiEnvelope<unknown>).data;
    }
    return response;
  },
  async (error) => {
    // Keep the HTTP status and structured response available to callers.
    if (isSafetySuspension(error)) return Promise.reject(error);
    const originalRequest = error.config;

    if (
      error.response?.status === 401 &&
      !originalRequest?._retry &&
      !isAuthEndpoint(originalRequest?.url)
    ) {
      if (isRefreshing) {
        return new Promise((resolve, reject) => {
          failedQueue.push({
            resolve: (token) => {
              originalRequest.headers = originalRequest.headers || {};
              originalRequest.headers.Authorization = `Bearer ${token}`;
              resolve(apiClient(originalRequest));
            },
            reject,
          });
        });
      }

      originalRequest._retry = true;
      isRefreshing = true;

      try {
        const refreshToken = tokenStorage.getRefreshToken();
        if (!refreshToken) throw error;

        const response = await axios.post(`${getApiBaseUrl()}/auth/refresh`, {
          refresh_token: refreshToken,
        });
        const { access_token, refresh_token } = response.data.data;
        tokenStorage.setTokens(access_token, refresh_token);
        apiClient.defaults.headers.common.Authorization = `Bearer ${access_token}`;
        processQueue(null, access_token);
        originalRequest.headers = originalRequest.headers || {};
        originalRequest.headers.Authorization = `Bearer ${access_token}`;
        return apiClient(originalRequest);
      } catch (refreshError) {
        tokenStorage.clear();
        processQueue(refreshError);
        return Promise.reject(refreshError);
      } finally {
        isRefreshing = false;
      }
    }

    return Promise.reject(error);
  },
);

export default apiClient;
