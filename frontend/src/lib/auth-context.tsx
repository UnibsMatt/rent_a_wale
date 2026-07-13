import {
  createContext,
  useContext,
  useEffect,
  useState,
  useSyncExternalStore,
  type ReactNode,
} from "react";
import { authStore, decodeJwt, type Role } from "@/lib/auth-store";
import { refreshAccessToken } from "@/api/client";

const AuthReadyContext = createContext<boolean>(false);

/**
 * Bootstraps the session: the access token lives in memory only, so on a hard
 * reload we exchange the persisted refresh token for a fresh pair before
 * rendering protected routes.
 */
export function AuthProvider({ children }: { children: ReactNode }) {
  const [ready, setReady] = useState(false);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      if (!authStore.getAccessToken() && authStore.getRefreshToken()) {
        try {
          await refreshAccessToken();
        } catch {
          authStore.clearTokens();
        }
      }
      if (!cancelled) setReady(true);
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  return <AuthReadyContext.Provider value={ready}>{children}</AuthReadyContext.Provider>;
}

export interface AuthState {
  ready: boolean;
  isAuthenticated: boolean;
  role: Role | null;
}

export function useAuth(): AuthState {
  const ready = useContext(AuthReadyContext);
  const accessToken = useSyncExternalStore(authStore.subscribe, authStore.getAccessToken);
  const role: Role | null = accessToken ? (decodeJwt(accessToken)?.role ?? "user") : null;
  return { ready, isAuthenticated: accessToken !== null, role };
}
