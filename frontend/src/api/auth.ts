import { api } from "@/api/client";
import type { LoginRequest, RegisterRequest, TokenPair, User } from "@/api/types";

export const authApi = {
  async login(body: LoginRequest): Promise<TokenPair> {
    const res = await api.post<TokenPair>("/auth/login", body);
    return res.data;
  },

  async register(body: RegisterRequest): Promise<User> {
    const res = await api.post<User>("/auth/register", body);
    return res.data;
  },

  async refresh(refreshToken: string): Promise<TokenPair> {
    const res = await api.post<TokenPair>("/auth/refresh", { refresh_token: refreshToken });
    return res.data;
  },

  async logout(refreshToken: string): Promise<void> {
    await api.post("/auth/logout", { refresh_token: refreshToken });
  },

  async verifyEmail(token: string): Promise<void> {
    await api.post("/auth/verify-email", { token });
  },

  async forgotPassword(email: string): Promise<void> {
    await api.post("/auth/forgot-password", { email });
  },

  async resetPassword(token: string, newPassword: string): Promise<void> {
    await api.post("/auth/reset-password", { token, new_password: newPassword });
  },
};
