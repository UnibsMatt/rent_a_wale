import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import {
  ArrowRight,
  Check,
  CircleDashed,
  ExternalLink,
  Loader2,
  XCircle,
} from "lucide-react";
import type { CreateDeploymentRequest, DeploymentStatus } from "@/api/types";
import { useCreateDeployment, useDeployment, usePlatformLogs } from "@/hooks/use-deployments";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { StatusBadge } from "@/components/status-badge";
import { ErrorState } from "@/components/states";
import { formatDate } from "@/lib/format";
import { cn } from "@/lib/utils";

const TIMELINE: { status: DeploymentStatus; label: string; description: string }[] = [
  { status: "pending", label: "Queued", description: "Deployment accepted and waiting for a worker" },
  { status: "provisioning", label: "Provisioning", description: "Pulling images, creating network, volumes and containers" },
  { status: "running", label: "Running", description: "All services are up" },
];

const ORDER: Record<string, number> = { pending: 0, provisioning: 1, running: 2 };

function TimelineRow({
  label,
  description,
  state,
}: {
  label: string;
  description: string;
  state: "done" | "active" | "todo" | "failed";
}) {
  return (
    <li className="flex gap-3">
      <span
        className={cn(
          "mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full border",
          state === "done" && "border-emerald-500 bg-emerald-500/15 text-emerald-500",
          state === "active" && "border-primary text-primary",
          state === "todo" && "border-border text-muted-foreground",
          state === "failed" && "border-red-500 bg-red-500/15 text-red-500",
        )}
      >
        {state === "done" ? (
          <Check className="h-3.5 w-3.5" aria-hidden />
        ) : state === "active" ? (
          <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden />
        ) : state === "failed" ? (
          <XCircle className="h-3.5 w-3.5" aria-hidden />
        ) : (
          <CircleDashed className="h-3.5 w-3.5" aria-hidden />
        )}
      </span>
      <div>
        <p className={cn("text-sm font-medium", state === "todo" && "text-muted-foreground")}>
          {label}
        </p>
        <p className="text-xs text-muted-foreground">{description}</p>
      </div>
    </li>
  );
}

export function LaunchStep({ request }: { request: CreateDeploymentRequest }) {
  const createMutation = useCreateDeployment();
  const [deploymentId, setDeploymentId] = useState<string | null>(null);
  const submitted = useRef(false);

  useEffect(() => {
    if (submitted.current) return;
    submitted.current = true;
    createMutation.mutate(request, {
      onSuccess: (deployment) => setDeploymentId(deployment.id),
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const deploymentQuery = useDeployment(deploymentId ?? undefined, { poll: true });
  const deployment = deploymentQuery.data;
  const status = deployment?.status;
  const failed = status === "failed";
  const running = status === "running";
  const settled = failed || running;
  const logsQuery = usePlatformLogs(deploymentId ?? undefined, { poll: !settled });

  if (createMutation.isError) {
    return (
      <ErrorState
        error={createMutation.error}
        onRetry={() => {
          submitted.current = false;
          createMutation.reset();
          createMutation.mutate(request, {
            onSuccess: (deployment) => setDeploymentId(deployment.id),
          });
          submitted.current = true;
        }}
      />
    );
  }

  const position = status !== undefined ? (ORDER[status] ?? 1) : 0;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <h2 className="text-lg font-semibold">{request.name}</h2>
          {status && <StatusBadge status={status} />}
        </div>
        {running && deployment?.public_url && (
          <a
            href={deployment.public_url}
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-1 text-sm text-primary hover:underline"
          >
            {deployment.public_url.replace(/^https?:\/\//, "")}
            <ExternalLink className="h-3.5 w-3.5" aria-hidden />
          </a>
        )}
      </div>

      <div className="grid gap-4 lg:grid-cols-[280px_1fr]">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Progress</CardTitle>
          </CardHeader>
          <CardContent>
            <ol className="space-y-4">
              {TIMELINE.map((step, i) => {
                let state: "done" | "active" | "todo" | "failed" = "todo";
                if (failed) {
                  state = i < position ? "done" : i === position ? "failed" : "todo";
                } else if (i < position || (running && i === position)) {
                  state = "done";
                } else if (i === position) {
                  state = "active";
                }
                return (
                  <TimelineRow
                    key={step.status}
                    label={step.label}
                    description={step.description}
                    state={state}
                  />
                );
              })}
            </ol>
            {failed && deployment?.failure_reason && (
              <div className="mt-4 rounded-lg border border-red-500/30 bg-red-500/5 p-3 text-xs">
                {deployment.failure_reason}
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Live activity</CardTitle>
          </CardHeader>
          <CardContent>
            <div
              className="max-h-72 space-y-1.5 overflow-y-auto rounded-lg bg-black/40 p-3 font-mono text-xs"
              aria-live="polite"
            >
              {(logsQuery.data ?? []).length === 0 ? (
                <p className="text-muted-foreground">Waiting for events…</p>
              ) : (
                [...(logsQuery.data ?? [])].reverse().map((line, i) => (
                  <p key={i} className="leading-relaxed">
                    <span className="text-muted-foreground">
                      {formatDate(line.created_at)}
                    </span>{" "}
                    <span
                      className={cn(
                        line.level === "error" && "text-red-400",
                        line.level === "warning" && "text-amber-400",
                      )}
                    >
                      {line.message}
                    </span>
                  </p>
                ))
              )}
            </div>
          </CardContent>
        </Card>
      </div>

      {settled && deploymentId && (
        <div className="flex justify-end gap-2">
          <Link to="/dashboard">
            <Button variant="outline">Go to dashboard</Button>
          </Link>
          <Link to={`/deployments/${deploymentId}`}>
            <Button>
              Deployment details <ArrowRight aria-hidden />
            </Button>
          </Link>
        </div>
      )}
    </div>
  );
}
