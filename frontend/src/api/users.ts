import { api } from "@/api/client";
import type { Quota, User, UserSession } from "@/api/types";

export const usersApi = {
  async me(): Promise<User> {
    const res = await api.get<User>("/users/me");
    return res.data;
  },

  async changePassword(currentPassword: string, newPassword: string): Promise<void> {
    await api.post("/users/me/change-password", {
      current_password: currentPassword,
      new_password: newPassword,
    });
  },

  async quota(): Promise<Quota> {
    const res = await api.get<Quota>("/users/me/quota");
    return res.data;
  },

  async sessions(): Promise<UserSession[]> {
    const res = await api.get<UserSession[]>("/users/me/sessions");
    return res.data;
  },
};
