import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import {
  ArrowLeft,
  ExternalLink,
  Pause,
  Play,
  RotateCw,
  Square,
  Trash2,
} from "lucide-react";
import type { DeploymentDetail } from "@/api/types";
import {
  useDeployment,
  useDeploymentAction,
  useDeploymentEvents,
  useDeploymentLogs,
  useDeploymentStats,
  useDeleteDeployment,
  usePlatformLogs,
} from "@/hooks/use-deployments";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { Progress } from "@/components/ui/progress";
import { Select } from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { StatusBadge } from "@/components/status-badge";
import { ConfirmDialog } from "@/components/confirm-dialog";
import { CardSkeleton, EmptyState, ErrorState } from "@/components/states";
import {
  formatCpu,
  formatCredits,
  formatDate,
  formatMB,
  formatRate,
  humanizeStatus,
  statusBadgeClass,
} from "@/lib/format";
import { cn } from "@/lib/utils";

// ---------- Overview tab ----------

function OverviewTab({ deployment }: { deployment: DeploymentDetail }) {
  const eventsQuery = useDeploymentEvents(deployment.id);
  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Services</CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Service</TableHead>
                <TableHead>Image</TableHead>
                <TableHead>Container</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Restarts</TableHead>
                <TableHead>Web</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {deployment.services.map((s) => (
                <TableRow key={s.id}>
                  <TableCell className="font-medium">{s.service_name}</TableCell>
                  <TableCell className="font-mono text-xs">{s.image}</TableCell>
                  <TableCell className="font-mono text-xs">
                    {s.container_name ?? "—"}
                  </TableCell>
                  <TableCell>
                    <Badge className={statusBadgeClass(s.status)}>{s.status}</Badge>
                  </TableCell>
                  <TableCell className="tabular-nums">{s.restart_count}</TableCell>
                  <TableCell>
                    {s.is_web ? `port ${s.internal_port ?? "?"}` : "—"}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Configuration</CardTitle>
          </CardHeader>
          <CardContent>
            <dl className="space-y-2 text-sm">
              <div className="flex justify-between">
                <dt className="text-muted-foreground">Kind</dt>
                <dd className="capitalize">{deployment.kind}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-muted-foreground">CPU</dt>
                <dd>{formatCpu(Number(deployment.cpu_cores))}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-muted-foreground">Memory</dt>
                <dd>{formatMB(deployment.memory_mb)}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-muted-foreground">Storage</dt>
                <dd>{deployment.storage_gb} GB</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-muted-foreground">Created</dt>
                <dd>{formatDate(deployment.created_at)}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-muted-foreground">Started</dt>
                <dd>{formatDate(deployment.started_at)}</dd>
              </div>
            </dl>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Events</CardTitle>
          </CardHeader>
          <CardContent>
            {eventsQuery.isLoading ? (
              <p className="text-sm text-muted-foreground">Loading…</p>
            ) : (eventsQuery.data ?? []).length === 0 ? (
              <p className="text-sm text-muted-foreground">No events yet.</p>
            ) : (
              <ol className="space-y-3">
                {(eventsQuery.data ?? []).map((event, i) => (
                  <li key={i} className="flex items-start gap-3 text-sm">
                    <span className="mt-1.5 h-2 w-2 shrink-0 rounded-full bg-primary" aria-hidden />
                    <div>
                      <p className="font-medium capitalize">
                        {humanizeStatus(event.event_type)}
                      </p>
                      <p className="text-xs text-muted-foreground">
                        {formatDate(event.created_at)}
                      </p>
                    </div>
                  </li>
                ))}
              </ol>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

// ---------- Logs tab ----------

function LogsTab({ deployment }: { deployment: DeploymentDetail }) {
  const [service, setService] = useState<string>("");
  const [tail, setTail] = useState(200);
  const [autoRefresh, setAutoRefresh] = useState(true);
  const logsQuery = useDeploymentLogs(
    deployment.id,
    service || undefined,
    tail,
    autoRefresh,
  );

  return (
    <Card>
      <CardHeader className="flex-row flex-wrap items-center justify-between gap-3 space-y-0">
        <CardTitle className="text-base">Container logs</CardTitle>
        <div className="flex flex-wrap items-center gap-3">
          {deployment.services.length > 1 && (
            <Select
              aria-label="Service"
              className="w-40"
              value={service}
              onChange={(e) => setService(e.target.value)}
            >
              <option value="">All services</option>
              {deployment.services.map((s) => (
                <option key={s.id} value={s.service_name}>
                  {s.service_name}
                </option>
              ))}
            </Select>
          )}
          <Select
            aria-label="Tail lines"
            className="w-32"
            value={String(tail)}
            onChange={(e) => setTail(Number(e.target.value))}
          >
            {[100, 200, 500, 1000].map((n) => (
              <option key={n} value={n}>
                Last {n}
              </option>
            ))}
          </Select>
          <div className="flex items-center gap-2">
            <Checkbox
              id="logs-auto"
              checked={autoRefresh}
              onChange={(e) => setAutoRefresh(e.target.checked)}
            />
            <Label htmlFor="logs-auto" className="cursor-pointer text-sm font-normal">
              Auto-refresh
            </Label>
          </div>
        </div>
      </CardHeader>
      <CardContent>
        {logsQuery.isError ? (
          <ErrorState error={logsQuery.error} onRetry={() => logsQuery.refetch()} />
        ) : (
          <pre
            className="max-h-[520px] overflow-auto whitespace-pre-wrap rounded-lg bg-black/40 p-4 font-mono text-xs leading-relaxed"
            aria-live="polite"
          >
            {logsQuery.data?.trim() || "No log output yet."}
          </pre>
        )}
      </CardContent>
    </Card>
  );
}

// ---------- Stats tab ----------

function StatsTab({ deployment }: { deployment: DeploymentDetail }) {
  const running = deployment.status === "running";
  const statsQuery = useDeploymentStats(deployment.id, running);

  if (!running) {
    return (
      <EmptyState
        title="Deployment is not running"
        description="Live metrics are only available while containers are running."
      />
    );
  }
  if (statsQuery.isLoading) {
    return (
      <div className="grid gap-4 sm:grid-cols-2">
        <CardSkeleton />
        <CardSkeleton />
      </div>
    );
  }
  if (statsQuery.isError) {
    return <ErrorState error={statsQuery.error} onRetry={() => statsQuery.refetch()} />;
  }

  return (
    <div className="grid gap-4 sm:grid-cols-2">
      {(statsQuery.data ?? []).map((s) => (
        <Card key={s.service_name}>
          <CardHeader className="flex-row items-center justify-between space-y-0">
            <CardTitle className="text-base">{s.service_name}</CardTitle>
            <div className="flex items-center gap-2">
              {s.healthy !== null && (
                <Badge
                  className={cn(
                    s.healthy
                      ? "border-emerald-500/40 bg-emerald-500/15 text-emerald-500"
                      : "border-red-500/40 bg-red-500/15 text-red-500",
                  )}
                >
                  {s.healthy ? "healthy" : "unhealthy"}
                </Badge>
              )}
              <Badge className={statusBadgeClass(s.status)}>{s.status}</Badge>
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <div className="mb-1 flex justify-between text-sm">
                <span className="text-muted-foreground">CPU</span>
                <span className="tabular-nums">{s.cpu_percent.toFixed(1)}%</span>
              </div>
              <Progress value={s.cpu_percent} />
            </div>
            <div>
              <div className="mb-1 flex justify-between text-sm">
                <span className="text-muted-foreground">Memory</span>
                <span className="tabular-nums">
                  {formatMB(s.memory_used_mb)} / {formatMB(s.memory_limit_mb)}
                </span>
              </div>
              <Progress value={s.memory_used_mb} max={Math.max(1, s.memory_limit_mb)} />
            </div>
            <dl className="grid grid-cols-3 gap-2 text-sm">
              <div>
                <dt className="text-xs text-muted-foreground">Net RX</dt>
                <dd className="tabular-nums">{s.network_rx_mb.toFixed(1)} MB</dd>
              </div>
              <div>
                <dt className="text-xs text-muted-foreground">Net TX</dt>
                <dd className="tabular-nums">{s.network_tx_mb.toFixed(1)} MB</dd>
              </div>
              <div>
                <dt className="text-xs text-muted-foreground">Restarts</dt>
                <dd className="tabular-nums">{s.restart_count}</dd>
              </div>
            </dl>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

// ---------- History tab ----------

function HistoryTab({ deployment }: { deployment: DeploymentDetail }) {
  const logsQuery = usePlatformLogs(deployment.id);
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Platform history</CardTitle>
      </CardHeader>
      <CardContent>
        {(logsQuery.data ?? []).length === 0 ? (
          <p className="text-sm text-muted-foreground">Nothing recorded yet.</p>
        ) : (
          <ol className="space-y-2">
            {(logsQuery.data ?? []).map((line, i) => (
              <li key={i} className="flex flex-wrap items-baseline gap-x-3 text-sm">
                <span className="w-40 shrink-0 text-xs tabular-nums text-muted-foreground">
                  {formatDate(line.created_at)}
                </span>
                <Badge className="uppercase">{line.source}</Badge>
                <span
                  className={cn(
                    line.level === "error" && "text-red-400",
                    line.level === "warning" && "text-amber-400",
                  )}
                >
                  {line.message}
                </span>
              </li>
            ))}
          </ol>
        )}
      </CardContent>
    </Card>
  );
}

// ---------- Page ----------

export function DeploymentDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const deploymentQuery = useDeployment(id);
  const actionMutation = useDeploymentAction();
  const deleteMutation = useDeleteDeployment();
  const [confirmDelete, setConfirmDelete] = useState(false);

  if (deploymentQuery.isLoading) {
    return (
      <div className="space-y-4">
        <CardSkeleton />
        <CardSkeleton />
      </div>
    );
  }
  if (deploymentQuery.isError || !deploymentQuery.data) {
    return (
      <ErrorState error={deploymentQuery.error} onRetry={() => deploymentQuery.refetch()} />
    );
  }

  const deployment = deploymentQuery.data;
  const canStop = ["running", "provisioning"].includes(deployment.status);
  const canStart = ["stopped", "credit_exhausted"].includes(deployment.status);
  const isRunning = deployment.status === "running";

  return (
    <div className="space-y-6">
      <Link
        to="/dashboard"
        className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="h-4 w-4" aria-hidden /> Back to dashboard
      </Link>

      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="space-y-1">
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-semibold tracking-tight">{deployment.name}</h1>
            <StatusBadge status={deployment.status} />
          </div>
          <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-muted-foreground">
            {deployment.public_url && (
              <a
                href={deployment.public_url}
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-1 text-primary hover:underline"
              >
                {deployment.public_url.replace(/^https?:\/\//, "")}
                <ExternalLink className="h-3.5 w-3.5" aria-hidden />
              </a>
            )}
            <span className="tabular-nums">
              {formatRate(deployment.estimated_hourly_cost)} credits/h
            </span>
            <span className="tabular-nums">
              total spent: {formatCredits(deployment.total_credits_spent)}
            </span>
          </div>
          {deployment.failure_reason && (
            <p className="text-sm text-red-400">{deployment.failure_reason}</p>
          )}
        </div>

        <div className="flex flex-wrap gap-2">
          <Button
            variant="outline"
            size="sm"
            disabled={!canStop || actionMutation.isPending}
            onClick={() => actionMutation.mutate({ id: deployment.id, action: "stop" })}
          >
            <Square aria-hidden /> Stop
          </Button>
          <Button
            variant="outline"
            size="sm"
            disabled={!canStart || actionMutation.isPending}
            onClick={() => actionMutation.mutate({ id: deployment.id, action: "start" })}
          >
            <Play aria-hidden /> Start
          </Button>
          <Button
            variant="outline"
            size="sm"
            disabled={!isRunning || actionMutation.isPending}
            onClick={() => actionMutation.mutate({ id: deployment.id, action: "restart" })}
          >
            <RotateCw aria-hidden /> Restart
          </Button>
          <Button
            variant="outline"
            size="sm"
            disabled={!isRunning || actionMutation.isPending}
            onClick={() => actionMutation.mutate({ id: deployment.id, action: "pause" })}
          >
            <Pause aria-hidden /> Pause
          </Button>
          <Button
            variant="outline"
            size="sm"
            disabled={actionMutation.isPending}
            onClick={() => actionMutation.mutate({ id: deployment.id, action: "resume" })}
          >
            <Play aria-hidden /> Resume
          </Button>
          <Button
            variant="destructive"
            size="sm"
            disabled={["deleting", "deleted"].includes(deployment.status)}
            onClick={() => setConfirmDelete(true)}
          >
            <Trash2 aria-hidden /> Delete
          </Button>
        </div>
      </div>

      <Tabs defaultValue="overview">
        <TabsList>
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="logs">Logs</TabsTrigger>
          <TabsTrigger value="stats">Stats</TabsTrigger>
          <TabsTrigger value="history">History</TabsTrigger>
        </TabsList>
        <TabsContent value="overview">
          <OverviewTab deployment={deployment} />
        </TabsContent>
        <TabsContent value="logs">
          <LogsTab deployment={deployment} />
        </TabsContent>
        <TabsContent value="stats">
          <StatsTab deployment={deployment} />
        </TabsContent>
        <TabsContent value="history">
          <HistoryTab deployment={deployment} />
        </TabsContent>
      </Tabs>

      <ConfirmDialog
        open={confirmDelete}
        onOpenChange={setConfirmDelete}
        title={`Delete "${deployment.name}"?`}
        description="Containers, the network and all volumes will be removed permanently. This cannot be undone."
        confirmLabel="Delete"
        destructive
        loading={deleteMutation.isPending}
        onConfirm={() =>
          deleteMutation.mutate(deployment.id, {
            onSuccess: () => navigate("/dashboard"),
          })
        }
      />
    </div>
  );
}
