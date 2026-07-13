import axios, { AxiosError, type InternalAxiosRequestConfig } from "axios";
import { authStore } from "@/lib/auth-store";
import type { TokenPair } from "@/api/types";

export const API_BASE = `${import.meta.env.VITE_API_URL ?? ""}/api/v1`;

export const api = axios.create({
  baseURL: API_BASE,
  headers: { "Content-Type": "application/json" },
});

// ---- Request interceptor: attach the in-memory access token ----
api.interceptors.request.use((config) => {
  const token = authStore.getAccessToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// ---- Single-flight refresh ----
// Concurrent 401s share ONE refresh call; the rotated pair is stored atomically.
let refreshPromise: Promise<string> | null = null;

async function doRefresh(): Promise<string> {
  const refreshToken = authStore.getRefreshToken();
  if (!refreshToken) {
    throw new Error("No refresh token available");
  }
  // Plain axios (not `api`) so this request never enters the 401-retry loop.
  const res = await axios.post<TokenPair>(`${API_BASE}/auth/refresh`, {
    refresh_token: refreshToken,
  });
  // ROTATION: always persist the NEW refresh token.
  authStore.setTokens(res.data.access_token, res.data.refresh_token);
  return res.data.access_token;
}

export function refreshAccessToken(): Promise<string> {
  if (!refreshPromise) {
    refreshPromise = doRefresh().finally(() => {
      refreshPromise = null;
    });
  }
  return refreshPromise;
}

function redirectToLogin(): void {
  if (window.location.pathname !== "/login") {
    window.location.href = "/login";
  }
}

type RetriableConfig = InternalAxiosRequestConfig & { _retry?: boolean };

// ---- Response interceptor: 401 → refresh once → retry original request ----
api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const config = error.config as RetriableConfig | undefined;
    const status = error.response?.status;
    const isAuthEndpoint = config?.url?.includes("/auth/") ?? false;

    if (status === 401 && config && !config._retry && !isAuthEndpoint) {
      config._retry = true;
      try {
        const token = await refreshAccessToken();
        config.headers.Authorization = `Bearer ${token}`;
        return api(config);
      } catch {
        authStore.clearTokens();
        redirectToLogin();
        return Promise.reject(error);
      }
    }
    return Promise.reject(error);
  },
);
