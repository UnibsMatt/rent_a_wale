import { beforeEach, describe, expect, it } from "vitest";
import { authStore, decodeJwt } from "@/lib/auth-store";

function makeJwt(payload: Record<string, unknown>): string {
  const b64 = (obj: Record<string, unknown>) =>
    btoa(JSON.stringify(obj)).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
  return `${b64({ alg: "HS256", typ: "JWT" })}.${b64(payload)}.signature`;
}

describe("authStore", () => {
  beforeEach(() => {
    authStore.clearTokens();
    localStorage.clear();
  });

  it("stores the access token in memory and the refresh token in localStorage", () => {
    authStore.setTokens("access-1", "refresh-1");
    expect(authStore.getAccessToken()).toBe("access-1");
    expect(localStorage.getItem("raw.refresh_token")).toBe("refresh-1");
  });

  it("rotation: a refresh always replaces BOTH tokens", () => {
    authStore.setTokens("access-1", "refresh-1");
    // simulate /auth/refresh response with a rotated pair
    authStore.setTokens("access-2", "refresh-2");
    expect(authStore.getAccessToken()).toBe("access-2");
    expect(authStore.getRefreshToken()).toBe("refresh-2");
    // the old refresh token must be gone — replaying it server-side revokes the session
    expect(localStorage.getItem("raw.refresh_token")).not.toBe("refresh-1");
  });

  it("clearTokens wipes both locations", () => {
    authStore.setTokens("access-1", "refresh-1");
    authStore.clearTokens();
    expect(authStore.getAccessToken()).toBeNull();
    expect(authStore.getRefreshToken()).toBeNull();
  });

  it("decodes the role from the JWT payload", () => {
    authStore.setTokens(makeJwt({ sub: "u1", role: "admin" }), "refresh");
    expect(authStore.getRole()).toBe("admin");
  });

  it("decodeJwt returns null for malformed tokens", () => {
    expect(decodeJwt("not-a-jwt")).toBeNull();
    expect(decodeJwt("")).toBeNull();
  });

  it("notifies subscribers on token changes", () => {
    let calls = 0;
    const unsubscribe = authStore.subscribe(() => {
      calls += 1;
    });
    authStore.setTokens("a", "r");
    authStore.clearTokens();
    unsubscribe();
    authStore.setTokens("b", "r2");
    expect(calls).toBe(2);
  });
});
