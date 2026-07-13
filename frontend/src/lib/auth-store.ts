/**
 * Minimal auth token store.
 * - Access token lives in memory only (module variable).
 * - Refresh token is persisted in localStorage.
 * Refresh tokens ROTATE: every successful refresh must store the new pair.
 */

const REFRESH_TOKEN_KEY = "raw.refresh_token";

export type Role = "user" | "admin";

export interface JwtPayload {
  sub?: string;
  role?: Role;
  exp?: number;
  [key: string]: unknown;
}

let accessToken: string | null = null;
const listeners = new Set<() => void>();

function emit(): void {
  for (const listener of listeners) listener();
}

/** Decode a JWT payload without any library (base64url decode of segment 1). */
export function decodeJwt(token: string): JwtPayload | null {
  try {
    const segment = token.split(".")[1];
    if (!segment) return null;
    const base64 = segment.replace(/-/g, "+").replace(/_/g, "/");
    const padded = base64 + "=".repeat((4 - (base64.length % 4)) % 4);
    return JSON.parse(atob(padded)) as JwtPayload;
  } catch {
    return null;
  }
}

export const authStore = {
  getAccessToken(): string | null {
    return accessToken;
  },

  getRefreshToken(): string | null {
    try {
      return localStorage.getItem(REFRESH_TOKEN_KEY);
    } catch {
      return null;
    }
  },

  /** Store a new token pair. Always called with the freshest refresh token (rotation). */
  setTokens(access: string, refresh: string): void {
    accessToken = access;
    try {
      localStorage.setItem(REFRESH_TOKEN_KEY, refresh);
    } catch {
      // storage unavailable — access token still works for this session
    }
    emit();
  },

  clearTokens(): void {
    accessToken = null;
    try {
      localStorage.removeItem(REFRESH_TOKEN_KEY);
    } catch {
      // ignore
    }
    emit();
  },

  /** Role decoded from the in-memory access token; null when logged out. */
  getRole(): Role | null {
    if (!accessToken) return null;
    return decodeJwt(accessToken)?.role ?? "user";
  },

  subscribe(listener: () => void): () => void {
    listeners.add(listener);
    return () => {
      listeners.delete(listener);
    };
  },
};
