import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { deploymentsApi, type LifecycleAction } from "@/api/deployments";
import type { CreateDeploymentRequest, DeploymentStatus, EstimateRequest } from "@/api/types";
import { getErrorMessage } from "@/lib/errors";
import { toast } from "@/components/ui/toast";

const TERMINAL_STATUSES: DeploymentStatus[] = [
  "running",
  "stopped",
  "failed",
  "deleted",
  "credit_exhausted",
];

export function isTerminalStatus(status: DeploymentStatus | undefined): boolean {
  return status !== undefined && TERMINAL_STATUSES.includes(status);
}

export function useDeployments(options?: { refetchInterval?: number }) {
  return useQuery({
    queryKey: ["deployments"],
    queryFn: deploymentsApi.list,
    refetchInterval: options?.refetchInterval ?? 15_000,
  });
}

export function useDeployment(id: string | undefined, options?: { poll?: boolean }) {
  return useQuery({
    queryKey: ["deployments", id],
    queryFn: () => deploymentsApi.get(id as string),
    enabled: !!id,
    refetchInterval: options?.poll
      ? (query) => (isTerminalStatus(query.state.data?.status) ? false : 2000)
      : 10_000,
  });
}

export function useDeploymentStats(id: string, enabled = true) {
  return useQuery({
    queryKey: ["deployment-stats", id],
    queryFn: () => deploymentsApi.stats(id),
    enabled,
    refetchInterval: 5000,
  });
}

export function useDeploymentLogs(
  id: string,
  service: string | undefined,
  tail: number,
  autoRefresh: boolean,
) {
  return useQuery({
    queryKey: ["deployment-logs", id, service ?? "", tail],
    queryFn: () => deploymentsApi.logs(id, service, tail),
    refetchInterval: autoRefresh ? 3000 : false,
    placeholderData: (prev) => prev,
  });
}

export function usePlatformLogs(id: string | undefined, options?: { poll?: boolean }) {
  return useQuery({
    queryKey: ["platform-logs", id],
    queryFn: () => deploymentsApi.platformLogs(id as string),
    enabled: !!id,
    refetchInterval: options?.poll ? 2000 : false,
  });
}

export function useDeploymentEvents(id: string) {
  return useQuery({
    queryKey: ["deployment-events", id],
    queryFn: () => deploymentsApi.events(id),
  });
}

export function useEstimate(request: EstimateRequest | null) {
  return useQuery({
    queryKey: ["estimate", request],
    queryFn: () => deploymentsApi.estimate(request as EstimateRequest),
    enabled: request !== null,
    staleTime: 30_000,
  });
}

export function useCreateDeployment() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: CreateDeploymentRequest) => deploymentsApi.create(body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["deployments"] });
      queryClient.invalidateQueries({ queryKey: ["balance"] });
    },
    onError: (err) => toast.error("Deployment failed to submit", getErrorMessage(err)),
  });
}

const ACTION_LABEL: Record<LifecycleAction, string> = {
  stop: "Stop",
  start: "Start",
  restart: "Restart",
  pause: "Pause",
  resume: "Resume",
};

export function useDeploymentAction() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, action }: { id: string; action: LifecycleAction }) =>
      deploymentsApi.action(id, action),
    onSuccess: (_data, { action }) => {
      toast.success(`${ACTION_LABEL[action]} requested`);
      queryClient.invalidateQueries({ queryKey: ["deployments"] });
    },
    onError: (err) => toast.error("Action failed", getErrorMessage(err)),
  });
}

export function useDeleteDeployment() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => deploymentsApi.remove(id),
    onSuccess: () => {
      toast.success("Deletion requested");
      queryClient.invalidateQueries({ queryKey: ["deployments"] });
    },
    onError: (err) => toast.error("Delete failed", getErrorMessage(err)),
  });
}
