import { api } from "@/api/client";
import type {
  ComposeValidation,
  CostEstimate,
  CreateDeploymentRequest,
  Deployment,
  DeploymentDetail,
  DeploymentEvent,
  EstimateRequest,
  PlatformLog,
  ServiceStats,
} from "@/api/types";

export type LifecycleAction = "stop" | "start" | "restart" | "pause" | "resume";

export const deploymentsApi = {
  async list(): Promise<Deployment[]> {
    const res = await api.get<Deployment[]>("/deployments");
    return res.data;
  },

  async get(id: string): Promise<DeploymentDetail> {
    const res = await api.get<DeploymentDetail>(`/deployments/${id}`);
    return res.data;
  },

  async create(body: CreateDeploymentRequest): Promise<DeploymentDetail> {
    const res = await api.post<DeploymentDetail>("/deployments", body);
    return res.data;
  },

  async estimate(body: EstimateRequest): Promise<CostEstimate> {
    const res = await api.post<CostEstimate>("/deployments/estimate", body);
    return res.data;
  },

  async validateCompose(composeYaml: string): Promise<ComposeValidation> {
    const res = await api.post<ComposeValidation>("/deployments/compose/validate", {
      compose_yaml: composeYaml,
    });
    return res.data;
  },

  async stats(id: string): Promise<ServiceStats[]> {
    const res = await api.get<ServiceStats[]>(`/deployments/${id}/stats`);
    return res.data;
  },

  async logs(id: string, service?: string, tail = 200): Promise<string> {
    const res = await api.get<string>(`/deployments/${id}/logs`, {
      params: { service: service || undefined, tail },
      responseType: "text",
      transformResponse: [(data) => data],
    });
    return typeof res.data === "string" ? res.data : String(res.data ?? "");
  },

  async platformLogs(id: string): Promise<PlatformLog[]> {
    const res = await api.get<PlatformLog[]>(`/deployments/${id}/platform-logs`);
    return res.data;
  },

  async events(id: string): Promise<DeploymentEvent[]> {
    const res = await api.get<DeploymentEvent[]>(`/deployments/${id}/events`);
    return res.data;
  },

  /** stop | start | restart return the deployment; pause | resume return {message}. */
  async action(id: string, action: LifecycleAction): Promise<void> {
    await api.post(`/deployments/${id}/${action}`);
  },

  async remove(id: string): Promise<void> {
    await api.delete(`/deployments/${id}`);
  },
};
