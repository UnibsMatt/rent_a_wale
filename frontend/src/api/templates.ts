import { api } from "@/api/client";
import type { Template } from "@/api/types";

export const templatesApi = {
  async list(): Promise<Template[]> {
    const res = await api.get<Template[]>("/templates");
    return res.data;
  },

  async submit(body: { name: string; description: string; compose_yaml: string }): Promise<Template> {
    const res = await api.post<Template>("/templates", body);
    return res.data;
  },
};
