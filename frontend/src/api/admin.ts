import { api } from "@/api/client";
import type {
  AdminUser,
  AuditLog,
  Deployment,
  HostStats,
  ImageRule,
  Page,
  PricingPlan,
  QuotaPatch,
  Template,
} from "@/api/types";

export interface CreatePricingRequest {
  name: string;
  base_cost_per_hour: string;
  cpu_cost_per_core_hour: string;
  memory_cost_per_gb_hour: string;
  storage_cost_per_gb_hour: string;
  service_cost_per_hour: string;
  activate: boolean;
}

export const adminApi = {
  // Users
  async users(page = 1, pageSize = 20): Promise<Page<AdminUser>> {
    const res = await api.get<Page<AdminUser>>("/admin/users", {
      params: { page, page_size: pageSize },
    });
    return res.data;
  },
  async adjustCredits(userId: string, amount: number, reason: string): Promise<void> {
    await api.post(`/admin/users/${userId}/credits`, { amount, reason });
  },
  async patchQuotas(userId: string, patch: QuotaPatch): Promise<void> {
    await api.patch(`/admin/users/${userId}/quotas`, patch);
  },
  async deactivateUser(userId: string): Promise<void> {
    await api.post(`/admin/users/${userId}/deactivate`);
  },

  // Deployments
  async deployments(page = 1, pageSize = 20): Promise<Page<Deployment>> {
    const res = await api.get<Page<Deployment>>("/admin/deployments", {
      params: { page, page_size: pageSize },
    });
    return res.data;
  },
  async stopDeployment(id: string): Promise<void> {
    await api.post(`/admin/deployments/${id}/stop`);
  },
  async deleteDeployment(id: string): Promise<void> {
    await api.delete(`/admin/deployments/${id}`);
  },

  // Pricing
  async pricing(): Promise<PricingPlan[]> {
    const res = await api.get<PricingPlan[]>("/admin/pricing");
    return res.data;
  },
  async createPricing(body: CreatePricingRequest): Promise<PricingPlan> {
    const res = await api.post<PricingPlan>("/admin/pricing", body);
    return res.data;
  },
  async activatePricing(id: string): Promise<void> {
    await api.post(`/admin/pricing/${id}/activate`);
  },

  // Image rules
  async images(): Promise<ImageRule[]> {
    const res = await api.get<ImageRule[]>("/admin/images");
    return res.data;
  },
  async createImageRule(body: {
    pattern: string;
    mode: "allow" | "block";
    reason: string;
  }): Promise<ImageRule> {
    const res = await api.post<ImageRule>("/admin/images", body);
    return res.data;
  },
  async deleteImageRule(id: string): Promise<void> {
    await api.delete(`/admin/images/${id}`);
  },

  // Templates
  async templates(): Promise<Template[]> {
    const res = await api.get<Template[]>("/admin/templates");
    return res.data;
  },
  async reviewTemplate(id: string, approve: boolean): Promise<void> {
    await api.post(`/admin/templates/${id}/review`, { approve });
  },

  // Host
  async host(): Promise<HostStats> {
    const res = await api.get<HostStats>("/admin/host");
    return res.data;
  },

  // Audit
  async auditLogs(page = 1, pageSize = 20): Promise<Page<AuditLog>> {
    const res = await api.get<Page<AuditLog>>("/admin/audit-logs", {
      params: { page, page_size: pageSize },
    });
    return res.data;
  },
};
