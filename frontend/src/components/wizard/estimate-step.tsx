import { useState } from "react";
import { ArrowLeft, Coins, Rocket, TriangleAlert } from "lucide-react";
import type { DeploymentKind } from "@/api/types";
import { useEstimate } from "@/hooks/use-deployments";
import { useBalance } from "@/hooks/use-credits";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { CardSkeleton, ErrorState } from "@/components/states";
import { formatCredits, formatCpu, formatMB, formatRate } from "@/lib/format";
import type { WizardConfig } from "@/components/wizard/types";

const BREAKDOWN_LABELS: Record<string, string> = {
  base: "Base fee",
  cpu: "CPU",
  memory: "Memory",
  storage: "Storage",
  extra_services: "Extra services",
};

export function EstimateStep({
  kind,
  config,
  onBack,
  onDeploy,
}: {
  kind: DeploymentKind;
  config: WizardConfig;
  onBack: () => void;
  onDeploy: () => void;
}) {
  const [confirmed, setConfirmed] = useState(false);
  const estimateQuery = useEstimate({
    resources: config.resources,
    service_count: config.serviceCount,
  });
  const balanceQuery = useBalance();

  const estimate = estimateQuery.data;
  const balance = Number(balanceQuery.data?.balance ?? "0");
  const hourly = Number(estimate?.hourly ?? "0");
  const insufficient = estimate !== undefined && balance < hourly;

  return (
    <div className="space-y-6">
      <div className="grid gap-4 lg:grid-cols-2">
        {/* What will be deployed */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Summary</CardTitle>
          </CardHeader>
          <CardContent>
            <dl className="space-y-2 text-sm">
              <div className="flex justify-between">
                <dt className="text-muted-foreground">Name</dt>
                <dd className="font-medium">{config.name}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-muted-foreground">Type</dt>
                <dd className="font-medium capitalize">{kind}</dd>
              </div>
              {config.hostname && (
                <div className="flex justify-between">
                  <dt className="text-muted-foreground">Hostname</dt>
                  <dd className="font-mono text-xs">{config.hostname}</dd>
                </div>
              )}
              <div className="flex justify-between">
                <dt className="text-muted-foreground">CPU</dt>
                <dd>{formatCpu(config.resources.cpu_cores)}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-muted-foreground">Memory</dt>
                <dd>{formatMB(config.resources.memory_mb)}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-muted-foreground">Storage</dt>
                <dd>{config.resources.storage_gb} GB</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-muted-foreground">Services</dt>
                <dd>{config.serviceCount}</dd>
              </div>
            </dl>
          </CardContent>
        </Card>

        {/* Cost */}
        {estimateQuery.isLoading ? (
          <CardSkeleton />
        ) : estimateQuery.isError ? (
          <ErrorState error={estimateQuery.error} onRetry={() => estimateQuery.refetch()} />
        ) : estimate ? (
          <Card>
            <CardHeader className="flex-row items-center justify-between space-y-0">
              <CardTitle className="text-base">Estimated cost</CardTitle>
              <span className="text-xs text-muted-foreground">plan: {estimate.plan_name}</span>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-3 gap-3 text-center">
                {(
                  [
                    ["Hourly", estimate.hourly],
                    ["Daily", estimate.daily],
                    ["Monthly", estimate.monthly],
                  ] as const
                ).map(([label, value]) => (
                  <div key={label} className="rounded-lg border bg-secondary/40 p-3">
                    <p className="text-xs text-muted-foreground">{label}</p>
                    <p className="mt-1 text-lg font-semibold tabular-nums">
                      {formatRate(value)}
                    </p>
                    <p className="text-[10px] text-muted-foreground">credits</p>
                  </div>
                ))}
              </div>
              <div>
                <p className="mb-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
                  Hourly breakdown
                </p>
                <dl className="space-y-1 text-sm">
                  {Object.entries(estimate.breakdown).map(([key, value]) => (
                    <div key={key} className="flex justify-between">
                      <dt className="text-muted-foreground">{BREAKDOWN_LABELS[key] ?? key}</dt>
                      <dd className="tabular-nums">{formatRate(value)}</dd>
                    </div>
                  ))}
                </dl>
              </div>
              <div className="flex items-center justify-between rounded-lg border p-3 text-sm">
                <span className="flex items-center gap-2 text-muted-foreground">
                  <Coins className="h-4 w-4" aria-hidden /> Your balance
                </span>
                <span className="font-semibold tabular-nums">{formatCredits(balance)}</span>
              </div>
            </CardContent>
          </Card>
        ) : null}
      </div>

      {insufficient && (
        <div className="flex items-start gap-3 rounded-lg border border-orange-500/40 bg-orange-500/10 p-4 text-sm">
          <TriangleAlert className="mt-0.5 h-4 w-4 shrink-0 text-orange-500" aria-hidden />
          <p>
            Your balance ({formatCredits(balance)}) is below one hour of runtime (
            {formatRate(estimate?.hourly)} credits). The deployment will be rejected — top up
            on the Credits page first.
          </p>
        </div>
      )}

      <div className="flex items-center gap-2">
        <Checkbox
          id="confirm-cost"
          checked={confirmed}
          onChange={(e) => setConfirmed(e.target.checked)}
        />
        <Label htmlFor="confirm-cost" className="cursor-pointer text-sm font-normal">
          I understand credits are deducted every minute while this deployment is running and
          it will be stopped automatically when my balance reaches zero.
        </Label>
      </div>

      <div className="flex justify-between">
        <Button type="button" variant="outline" onClick={onBack}>
          <ArrowLeft aria-hidden /> Back
        </Button>
        <Button type="button" onClick={onDeploy} disabled={!confirmed || !estimate}>
          <Rocket aria-hidden /> Deploy
        </Button>
      </div>
    </div>
  );
}
