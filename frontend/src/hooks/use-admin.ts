import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { adminApi, type CreatePricingRequest } from "@/api/admin";
import type { QuotaPatch } from "@/api/types";
import { getErrorMessage } from "@/lib/errors";
import { toast } from "@/components/ui/toast";

// ---- Users ----

export function useAdminUsers(page: number, pageSize = 20) {
  return useQuery({
    queryKey: ["admin", "users", page, pageSize],
    queryFn: () => adminApi.users(page, pageSize),
    placeholderData: (prev) => prev,
  });
}

export function useAdjustCredits() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ userId, amount, reason }: { userId: string; amount: number; reason: string }) =>
      adminApi.adjustCredits(userId, amount, reason),
    onSuccess: () => {
      toast.success("Credits adjusted");
      queryClient.invalidateQueries({ queryKey: ["admin", "users"] });
    },
    onError: (err) => toast.error("Adjustment failed", getErrorMessage(err)),
  });
}

export function usePatchQuotas() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ userId, patch }: { userId: string; patch: QuotaPatch }) =>
      adminApi.patchQuotas(userId, patch),
    onSuccess: () => {
      toast.success("Quotas updated");
      queryClient.invalidateQueries({ queryKey: ["admin", "users"] });
    },
    onError: (err) => toast.error("Quota update failed", getErrorMessage(err)),
  });
}

export function useDeactivateUser() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (userId: string) => adminApi.deactivateUser(userId),
    onSuccess: () => {
      toast.success("User deactivated");
      queryClient.invalidateQueries({ queryKey: ["admin", "users"] });
    },
    onError: (err) => toast.error("Deactivation failed", getErrorMessage(err)),
  });
}

// ---- Deployments ----

export function useAdminDeployments(page: number, pageSize = 20) {
  return useQuery({
    queryKey: ["admin", "deployments", page, pageSize],
    queryFn: () => adminApi.deployments(page, pageSize),
    placeholderData: (prev) => prev,
  });
}

export function useAdminStopDeployment() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => adminApi.stopDeployment(id),
    onSuccess: () => {
      toast.success("Stop requested");
      queryClient.invalidateQueries({ queryKey: ["admin", "deployments"] });
    },
    onError: (err) => toast.error("Stop failed", getErrorMessage(err)),
  });
}

export function useAdminDeleteDeployment() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => adminApi.deleteDeployment(id),
    onSuccess: () => {
      toast.success("Deletion requested");
      queryClient.invalidateQueries({ queryKey: ["admin", "deployments"] });
    },
    onError: (err) => toast.error("Delete failed", getErrorMessage(err)),
  });
}

// ---- Pricing ----

export function useAdminPricing() {
  return useQuery({ queryKey: ["admin", "pricing"], queryFn: adminApi.pricing });
}

export function useCreatePricing() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: CreatePricingRequest) => adminApi.createPricing(body),
    onSuccess: () => {
      toast.success("Pricing plan created");
      queryClient.invalidateQueries({ queryKey: ["admin", "pricing"] });
      queryClient.invalidateQueries({ queryKey: ["pricing"] });
    },
    onError: (err) => toast.error("Creation failed", getErrorMessage(err)),
  });
}

export function useActivatePricing() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => adminApi.activatePricing(id),
    onSuccess: () => {
      toast.success("Pricing plan activated");
      queryClient.invalidateQueries({ queryKey: ["admin", "pricing"] });
      queryClient.invalidateQueries({ queryKey: ["pricing"] });
    },
    onError: (err) => toast.error("Activation failed", getErrorMessage(err)),
  });
}

// ---- Image rules ----

export function useAdminImages() {
  return useQuery({ queryKey: ["admin", "images"], queryFn: adminApi.images });
}

export function useCreateImageRule() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: adminApi.createImageRule,
    onSuccess: () => {
      toast.success("Image rule added");
      queryClient.invalidateQueries({ queryKey: ["admin", "images"] });
    },
    onError: (err) => toast.error("Rule creation failed", getErrorMessage(err)),
  });
}

export function useDeleteImageRule() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => adminApi.deleteImageRule(id),
    onSuccess: () => {
      toast.success("Image rule removed");
      queryClient.invalidateQueries({ queryKey: ["admin", "images"] });
    },
    onError: (err) => toast.error("Rule deletion failed", getErrorMessage(err)),
  });
}

// ---- Templates ----

export function useAdminTemplates() {
  return useQuery({ queryKey: ["admin", "templates"], queryFn: adminApi.templates });
}

export function useReviewTemplate() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, approve }: { id: string; approve: boolean }) =>
      adminApi.reviewTemplate(id, approve),
    onSuccess: (_data, { approve }) => {
      toast.success(approve ? "Template approved" : "Template rejected");
      queryClient.invalidateQueries({ queryKey: ["admin", "templates"] });
      queryClient.invalidateQueries({ queryKey: ["templates"] });
    },
    onError: (err) => toast.error("Review failed", getErrorMessage(err)),
  });
}

// ---- Host & audit ----

export function useAdminHost() {
  return useQuery({
    queryKey: ["admin", "host"],
    queryFn: adminApi.host,
    refetchInterval: 10_000,
  });
}

export function useAuditLogs(page: number, pageSize = 20) {
  return useQuery({
    queryKey: ["admin", "audit", page, pageSize],
    queryFn: () => adminApi.auditLogs(page, pageSize),
    placeholderData: (prev) => prev,
  });
}
