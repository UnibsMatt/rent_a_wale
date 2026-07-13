/**
 * TypeScript shapes for the Rent-a-Whale API (all under /api/v1).
 * NOTE: monetary / decimal values arrive as STRINGS — format with lib/format helpers.
 */

export type Role = "user" | "admin";

// ---------- Generic ----------

export interface Page<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

export interface ApiErrorEnvelope {
  error: {
    code: string;
    message: string;
    detail?: Record<string, unknown>;
  };
}

// ---------- Auth ----------

export interface TokenPair {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface RegisterRequest {
  email: string;
  password: string;
}

// ---------- Users ----------

export interface User {
  id: string;
  user_number: number;
  email: string;
  role: Role;
  is_active: boolean;
  is_email_verified: boolean;
  created_at: string;
}

export interface Quota {
  max_cpu_quota: number;
  max_memory_mb_quota: number;
  max_storage_gb_quota: number;
  max_deployments_quota: number;
  used_cpu: number;
  used_memory_mb: number;
  used_storage_gb: number;
  used_deployments: number;
}

export interface UserSession {
  id: string;
  user_agent: string | null;
  ip_address: string | null;
  revoked: boolean;
  created_at: string;
  last_used_at: string | null;
}

// ---------- Credits ----------

export interface Balance {
  balance: string;
  estimated_hourly_spend: string;
  runway_hours: string | null;
}

export interface CreditTransaction {
  id: string;
  kind: string;
  amount: string;
  balance_after: string;
  deployment_id: string | null;
  created_at: string;
}

export interface PricingPlan {
  id: string;
  name: string;
  is_active: boolean;
  base_cost_per_hour: string;
  cpu_cost_per_core_hour: string;
  memory_cost_per_gb_hour: string;
  storage_cost_per_gb_hour: string;
  service_cost_per_hour: string;
  created_at: string;
}

// ---------- Deployments ----------

export type DeploymentKind = "image" | "compose";

export type DeploymentStatus =
  | "pending"
  | "provisioning"
  | "running"
  | "stopping"
  | "stopped"
  | "failed"
  | "deleting"
  | "deleted"
  | "credit_exhausted";

export type RestartPolicy = "no" | "always" | "on-failure" | "unless-stopped";

export interface ResourceSpec {
  cpu_cores: number;
  memory_mb: number;
  storage_gb: number;
}

export interface EstimateRequest {
  resources: ResourceSpec;
  service_count: number;
}

export interface CostEstimate {
  hourly: string;
  daily: string;
  monthly: string;
  plan_name: string;
  breakdown: {
    base: string;
    cpu: string;
    memory: string;
    storage: string;
    extra_services: string;
  };
}

export interface ComposeService {
  name: string;
  image: string;
  web_port: number | null;
  cpu_cores: number;
  memory_mb: number;
  env_keys: string[];
  volumes: string[];
  depends_on: string[];
}

export interface ComposeValidation {
  valid: boolean;
  errors: string[];
  services: ComposeService[];
  aggregate: ResourceSpec | null;
}

export interface VolumeMount {
  name: string;
  container_path: string;
}

export interface ImageSpec {
  image: string;
  command?: string;
  env: Record<string, string>;
  web_port?: number;
  volumes: VolumeMount[];
  restart_policy: RestartPolicy;
}

export interface CreateDeploymentRequest {
  name: string;
  kind: DeploymentKind;
  resources: ResourceSpec;
  hostname?: string;
  image_spec?: ImageSpec;
  compose_yaml?: string;
  template_id?: string;
}

export interface DeploymentService {
  id: string;
  service_name: string;
  image: string;
  container_name: string | null;
  status: string;
  restart_count: number;
  is_web: boolean;
  internal_port: number | null;
}

export interface Deployment {
  id: string;
  name: string;
  slug: string;
  kind: DeploymentKind;
  status: DeploymentStatus;
  cpu_cores: number;
  memory_mb: number;
  storage_gb: number;
  estimated_hourly_cost: string;
  public_url: string | null;
  failure_reason: string | null;
  started_at: string | null;
  stopped_at: string | null;
  created_at: string;
  services: DeploymentService[];
}

export interface DeploymentDetail extends Deployment {
  spec: Record<string, unknown>;
  total_credits_spent: string;
}

export interface ServiceStats {
  service_name: string;
  cpu_percent: number;
  memory_used_mb: number;
  memory_limit_mb: number;
  network_rx_mb: number;
  network_tx_mb: number;
  status: string;
  restart_count: number;
  healthy: boolean;
}

export interface PlatformLog {
  source: string;
  level: string;
  message: string;
  created_at: string;
}

export interface DeploymentEvent {
  event_type: string;
  payload: Record<string, unknown> | null;
  created_at: string;
}

// ---------- Templates ----------

export interface Template {
  id: string;
  name: string;
  description: string;
  compose_yaml: string;
  status: string;
  submitted_by: string | null;
  created_at: string;
}

// ---------- Admin ----------

export interface AdminUser extends User {
  balance: string;
}

export interface ImageRule {
  id: string;
  pattern: string;
  mode: "allow" | "block";
  reason: string | null;
  created_at: string;
}

export interface AuditLog {
  id: string;
  actor_id: string | null;
  action: string;
  resource_type: string;
  resource_id: string | null;
  ip_address: string | null;
  detail: Record<string, unknown> | null;
  created_at: string;
}

export interface HostStats {
  cpu_percent: number;
  memory_used_mb: number;
  memory_total_mb: number;
  disk_used_gb: number;
  disk_total_gb: number;
  running_containers: number;
  allocated_cpu: number;
  allocated_memory_mb: number;
  allocated_storage_gb: number;
  allocatable_cpu: number;
  allocatable_memory_mb: number;
  allocatable_storage_gb: number;
  sampled_at: string;
}

export interface QuotaPatch {
  max_cpu_quota?: number;
  max_memory_mb_quota?: number;
  max_storage_gb_quota?: number;
  max_deployments_quota?: number;
}
