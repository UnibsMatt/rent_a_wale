import { api } from "@/api/client";
import type { Balance, CreditTransaction, Page, PricingPlan } from "@/api/types";
import { randomUUID } from "@/lib/utils";

export const creditsApi = {
  async balance(): Promise<Balance> {
    const res = await api.get<Balance>("/credits/balance");
    return res.data;
  },

  async purchase(amount: number): Promise<CreditTransaction> {
    const res = await api.post<CreditTransaction>("/credits/purchase", {
      amount,
      idempotency_key: randomUUID(),
    });
    return res.data;
  },

  async transactions(page = 1, pageSize = 20): Promise<Page<CreditTransaction>> {
    const res = await api.get<Page<CreditTransaction>>("/credits/transactions", {
      params: { page, page_size: pageSize },
    });
    return res.data;
  },

  async pricing(): Promise<PricingPlan> {
    const res = await api.get<PricingPlan>("/credits/pricing");
    return res.data;
  },
};
