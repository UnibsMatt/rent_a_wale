import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import {
  Activity,
  Boxes,
  Coins,
  ExternalLink,
  Hourglass,
  MoreVertical,
  Play,
  Plus,
  RotateCw,
  Square,
  Trash2,
} from "lucide-react";
import type { Deployment } from "@/api/types";
import { useDeployments, useDeploymentAction, useDeleteDeployment } from "@/hooks/use-deployments";
import { useBalance } from "@/hooks/use-credits";
import { formatCredits, formatDate, formatRunway } from "@/lib/format";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { StatusBadge } from "@/components/status-badge";
import { ConfirmDialog } from "@/components/confirm-dialog";
import { CardSkeleton, EmptyState, ErrorState, TableSkeleton } from "@/components/states";

function StatCard({
  title,
  value,
  hint,
  icon: Icon,
}: {
  title: string;
  value: string;
  hint?: string;
  icon: typeof Coins;
}) {
  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between space-y-0 pb-2">
        <CardTitle className="text-sm font-medium text-muted-foreground">{title}</CardTitle>
        <Icon className="h-4 w-4 text-primary" aria-hidden />
      </CardHeader>
      <CardContent>
        <p className="text-2xl font-semibold tabular-nums">{value}</p>
        {hint && <p className="mt-1 text-xs text-muted-foreground">{hint}</p>}
      </CardContent>
    </Card>
  );
}

type PendingConfirm =
  | { type: "stop" | "restart" | "delete"; deployment: Deployment }
  | null;

function DeploymentRow({
  deployment,
  onConfirm,
}: {
  deployment: Deployment;
  onConfirm: (c: NonNullable<PendingConfirm>) => void;
}) {
  const navigate = useNavigate();
  const actionMutation = useDeploymentAction();
  const canStop = deployment.status === "running" || deployment.status === "provisioning";
  const canStart = ["stopped", "failed", "credit_exhausted"].includes(deployment.status);

  return (
    <TableRow
      className="cursor-pointer"
      onClick={() => navigate(`/deployments/${deployment.id}`)}
    >
      <TableCell className="font-medium">{deployment.name}</TableCell>
      <TableCell>
        <StatusBadge status={deployment.status} />
      </TableCell>
      <TableCell>
        {deployment.public_url ? (
          <a
            href={deployment.public_url}
            target="_blank"
            rel="noreferrer"
            onClick={(e) => e.stopPropagation()}
            className="inline-flex items-center gap-1 text-primary hover:underline"
          >
            {deployment.public_url.replace(/^https?:\/\//, "")}
            <ExternalLink className="h-3 w-3" aria-hidden />
          </a>
        ) : (
          <span className="text-muted-foreground">—</span>
        )}
      </TableCell>
      <TableCell className="tabular-nums">
        {formatCredits(deployment.estimated_hourly_cost)}/h
      </TableCell>
      <TableCell className="text-muted-foreground">{formatDate(deployment.created_at)}</TableCell>
      <TableCell onClick={(e) => e.stopPropagation()} className="text-right">
        <DropdownMenu>
          <DropdownMenuTrigger
            aria-label={`Actions for ${deployment.name}`}
            className="inline-flex h-8 w-8 items-center justify-center rounded-md hover:bg-accent"
          >
            <MoreVertical className="h-4 w-4" aria-hidden />
          </DropdownMenuTrigger>
          <DropdownMenuContent>
            <DropdownMenuItem
              disabled={!canStop}
              onClick={() => onConfirm({ type: "stop", deployment })}
            >
              <Square aria-hidden /> Stop
            </DropdownMenuItem>
            <DropdownMenuItem
              disabled={!canStart}
              onClick={() => actionMutation.mutate({ id: deployment.id, action: "start" })}
            >
              <Play aria-hidden /> Start
            </DropdownMenuItem>
            <DropdownMenuItem
              disabled={!canStop}
              onClick={() => onConfirm({ type: "restart", deployment })}
            >
              <RotateCw aria-hidden /> Restart
            </DropdownMenuItem>
            <DropdownMenuItem
              destructive
              disabled={deployment.status === "deleting" || deployment.status === "deleted"}
              onClick={() => onConfirm({ type: "delete", deployment })}
            >
              <Trash2 aria-hidden /> Delete
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </TableCell>
    </TableRow>
  );
}

export function DashboardPage() {
  const deploymentsQuery = useDeployments();
  const balanceQuery = useBalance();
  const actionMutation = useDeploymentAction();
  const deleteMutation = useDeleteDeployment();
  const [confirm, setConfirm] = useState<PendingConfirm>(null);

  const deployments = deploymentsQuery.data ?? [];
  const running = deployments.filter((d) => d.status === "running").length;

  function handleConfirm() {
    if (!confirm) return;
    const { type, deployment } = confirm;
    if (type === "delete") {
      deleteMutation.mutate(deployment.id, { onSettled: () => setConfirm(null) });
    } else {
      actionMutation.mutate(
        { id: deployment.id, action: type },
        { onSettled: () => setConfirm(null) },
      );
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Dashboard</h1>
          <p className="text-sm text-muted-foreground">Your containers at a glance</p>
        </div>
        <Link to="/deployments/new">
          <Button>
            <Plus aria-hidden /> New deployment
          </Button>
        </Link>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {balanceQuery.isLoading ? (
          <>
            <CardSkeleton />
            <CardSkeleton />
            <CardSkeleton />
            <CardSkeleton />
          </>
        ) : (
          <>
            <StatCard
              title="Credits remaining"
              value={formatCredits(balanceQuery.data?.balance)}
              icon={Coins}
            />
            <StatCard
              title="Est. hourly spend"
              value={`${formatCredits(balanceQuery.data?.estimated_hourly_spend)}/h`}
              icon={Activity}
            />
            <StatCard
              title="Runway"
              value={formatRunway(balanceQuery.data?.runway_hours ?? null)}
              hint="At current spend rate"
              icon={Hourglass}
            />
            <StatCard
              title="Deployments"
              value={`${running} / ${deployments.length}`}
              hint="Running / total"
              icon={Boxes}
            />
          </>
        )}
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Deployments</CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          {deploymentsQuery.isLoading ? (
            <TableSkeleton rows={4} cols={6} />
          ) : deploymentsQuery.isError ? (
            <ErrorState
              error={deploymentsQuery.error}
              onRetry={() => deploymentsQuery.refetch()}
              className="m-4"
            />
          ) : deployments.length === 0 ? (
            <EmptyState
              className="m-4"
              icon={<Boxes className="h-8 w-8" />}
              title="No deployments yet"
              description="Launch your first container to get started."
              action={
                <Link to="/deployments/new">
                  <Button size="sm">
                    <Plus aria-hidden /> New deployment
                  </Button>
                </Link>
              }
            />
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Public URL</TableHead>
                  <TableHead>Cost</TableHead>
                  <TableHead>Created</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {deployments.map((d) => (
                  <DeploymentRow key={d.id} deployment={d} onConfirm={setConfirm} />
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      <ConfirmDialog
        open={confirm !== null}
        onOpenChange={(open) => !open && setConfirm(null)}
        title={
          confirm?.type === "delete"
            ? `Delete "${confirm.deployment.name}"?`
            : confirm?.type === "stop"
              ? `Stop "${confirm?.deployment.name}"?`
              : `Restart "${confirm?.deployment.name}"?`
        }
        description={
          confirm?.type === "delete"
            ? "This permanently removes the deployment and its volumes. This cannot be undone."
            : confirm?.type === "stop"
              ? "The containers will be stopped. You can start them again later."
              : "All services will be restarted. Brief downtime is expected."
        }
        confirmLabel={
          confirm?.type === "delete" ? "Delete" : confirm?.type === "stop" ? "Stop" : "Restart"
        }
        destructive={confirm?.type === "delete"}
        loading={actionMutation.isPending || deleteMutation.isPending}
        onConfirm={handleConfirm}
      />
    </div>
  );
}
