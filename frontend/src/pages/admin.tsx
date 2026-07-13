import { useState } from "react";
import { Cpu, HardDrive, MemoryStick, Plus, ShieldBan, ShieldCheck, Trash2 } from "lucide-react";
import type { AdminUser, Deployment, QuotaPatch, Template } from "@/api/types";
import {
  useActivatePricing,
  useAdjustCredits,
  useAdminDeleteDeployment,
  useAdminDeployments,
  useAdminHost,
  useAdminImages,
  useAdminPricing,
  useAdminStopDeployment,
  useAdminTemplates,
  useAdminUsers,
  useAuditLogs,
  useCreateImageRule,
  useCreatePricing,
  useDeactivateUser,
  useDeleteImageRule,
  usePatchQuotas,
  useReviewTemplate,
} from "@/hooks/use-admin";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Progress } from "@/components/ui/progress";
import { Select } from "@/components/ui/select";
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
import { Pagination } from "@/components/pagination";
import { CardSkeleton, EmptyState, ErrorState, TableSkeleton } from "@/components/states";
import { formatCredits, formatDate, formatGB, formatMB, formatRate } from "@/lib/format";

// ---------- Users tab ----------

function AdjustCreditsDialog({
  user,
  onClose,
}: {
  user: AdminUser | null;
  onClose: () => void;
}) {
  const adjust = useAdjustCredits();
  const [amount, setAmount] = useState("");
  const [reason, setReason] = useState("");
  const valid = amount !== "" && !Number.isNaN(Number(amount)) && reason.trim().length >= 3;

  return (
    <Dialog open={user !== null} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>Adjust credits</DialogTitle>
          <DialogDescription>
            {user?.email} — current balance {formatCredits(user?.balance)}. Use a negative
            amount to remove credits.
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-3">
          <div className="space-y-1.5">
            <Label htmlFor="adj-amount">Amount (±)</Label>
            <Input
              id="adj-amount"
              inputMode="decimal"
              placeholder="e.g. 500 or -100"
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="adj-reason">Reason (audited)</Label>
            <Input
              id="adj-reason"
              placeholder="Why is this adjustment made?"
              value={reason}
              onChange={(e) => setReason(e.target.value)}
            />
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button
            disabled={!valid}
            loading={adjust.isPending}
            onClick={() =>
              user &&
              adjust.mutate(
                { userId: user.id, amount: Number(amount), reason },
                { onSuccess: onClose },
              )
            }
          >
            Apply
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function QuotasDialog({ user, onClose }: { user: AdminUser | null; onClose: () => void }) {
  const patchQuotas = usePatchQuotas();
  const [cpu, setCpu] = useState("");
  const [memory, setMemory] = useState("");
  const [storage, setStorage] = useState("");
  const [deployments, setDeployments] = useState("");

  function submit() {
    if (!user) return;
    const patch: QuotaPatch = {};
    if (cpu !== "") patch.max_cpu_quota = Number(cpu);
    if (memory !== "") patch.max_memory_mb_quota = Number(memory);
    if (storage !== "") patch.max_storage_gb_quota = Number(storage);
    if (deployments !== "") patch.max_deployments_quota = Number(deployments);
    patchQuotas.mutate({ userId: user.id, patch }, { onSuccess: onClose });
  }

  return (
    <Dialog open={user !== null} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>Resource quotas</DialogTitle>
          <DialogDescription>
            {user?.email} — leave a field empty to keep the current value.
          </DialogDescription>
        </DialogHeader>
        <div className="grid grid-cols-2 gap-3">
          <div className="space-y-1.5">
            <Label htmlFor="q-cpu">Max CPU cores</Label>
            <Input id="q-cpu" inputMode="decimal" value={cpu} onChange={(e) => setCpu(e.target.value)} />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="q-mem">Max memory (MB)</Label>
            <Input id="q-mem" inputMode="numeric" value={memory} onChange={(e) => setMemory(e.target.value)} />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="q-storage">Max storage (GB)</Label>
            <Input id="q-storage" inputMode="numeric" value={storage} onChange={(e) => setStorage(e.target.value)} />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="q-deps">Max deployments</Label>
            <Input id="q-deps" inputMode="numeric" value={deployments} onChange={(e) => setDeployments(e.target.value)} />
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button loading={patchQuotas.isPending} onClick={submit}>
            Save
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function UsersTab() {
  const [page, setPage] = useState(1);
  const usersQuery = useAdminUsers(page);
  const deactivate = useDeactivateUser();
  const [creditsTarget, setCreditsTarget] = useState<AdminUser | null>(null);
  const [quotasTarget, setQuotasTarget] = useState<AdminUser | null>(null);
  const [deactivateTarget, setDeactivateTarget] = useState<AdminUser | null>(null);

  if (usersQuery.isLoading) return <TableSkeleton rows={6} cols={6} />;
  if (usersQuery.isError)
    return <ErrorState error={usersQuery.error} onRetry={() => usersQuery.refetch()} />;

  return (
    <Card>
      <CardContent className="p-0">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Email</TableHead>
              <TableHead>Role</TableHead>
              <TableHead>Balance</TableHead>
              <TableHead>Active</TableHead>
              <TableHead>Joined</TableHead>
              <TableHead className="text-right">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {usersQuery.data?.items.map((user) => (
              <TableRow key={user.id}>
                <TableCell className="font-medium">{user.email}</TableCell>
                <TableCell>
                  <Badge className="capitalize">{user.role}</Badge>
                </TableCell>
                <TableCell className="tabular-nums">{formatCredits(user.balance)}</TableCell>
                <TableCell>{user.is_active ? "Yes" : "No"}</TableCell>
                <TableCell className="text-muted-foreground">
                  {formatDate(user.created_at)}
                </TableCell>
                <TableCell className="space-x-2 text-right">
                  <Button variant="outline" size="sm" onClick={() => setCreditsTarget(user)}>
                    Credits
                  </Button>
                  <Button variant="outline" size="sm" onClick={() => setQuotasTarget(user)}>
                    Quotas
                  </Button>
                  <Button
                    variant="destructive"
                    size="sm"
                    disabled={!user.is_active}
                    onClick={() => setDeactivateTarget(user)}
                  >
                    Deactivate
                  </Button>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
        <Pagination
          page={page}
          pageSize={usersQuery.data?.page_size ?? 20}
          total={usersQuery.data?.total ?? 0}
          onPageChange={setPage}
        />
      </CardContent>

      <AdjustCreditsDialog user={creditsTarget} onClose={() => setCreditsTarget(null)} />
      <QuotasDialog user={quotasTarget} onClose={() => setQuotasTarget(null)} />
      <ConfirmDialog
        open={deactivateTarget !== null}
        onOpenChange={(open) => !open && setDeactivateTarget(null)}
        title={`Deactivate ${deactivateTarget?.email}?`}
        description="The user will no longer be able to log in. Their deployments keep running until stopped."
        confirmLabel="Deactivate"
        destructive
        loading={deactivate.isPending}
        onConfirm={() =>
          deactivateTarget &&
          deactivate.mutate(deactivateTarget.id, {
            onSettled: () => setDeactivateTarget(null),
          })
        }
      />
    </Card>
  );
}

// ---------- Deployments tab ----------

function DeploymentsTab() {
  const [page, setPage] = useState(1);
  const deploymentsQuery = useAdminDeployments(page);
  const stopMutation = useAdminStopDeployment();
  const deleteMutation = useAdminDeleteDeployment();
  const [confirm, setConfirm] = useState<{ type: "stop" | "delete"; d: Deployment } | null>(null);

  if (deploymentsQuery.isLoading) return <TableSkeleton rows={6} cols={6} />;
  if (deploymentsQuery.isError)
    return (
      <ErrorState error={deploymentsQuery.error} onRetry={() => deploymentsQuery.refetch()} />
    );

  return (
    <Card>
      <CardContent className="p-0">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Name</TableHead>
              <TableHead>Slug</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Cost/h</TableHead>
              <TableHead>Created</TableHead>
              <TableHead className="text-right">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {deploymentsQuery.data?.items.map((d) => (
              <TableRow key={d.id}>
                <TableCell className="font-medium">{d.name}</TableCell>
                <TableCell className="font-mono text-xs">{d.slug}</TableCell>
                <TableCell>
                  <StatusBadge status={d.status} />
                </TableCell>
                <TableCell className="tabular-nums">
                  {formatRate(d.estimated_hourly_cost)}
                </TableCell>
                <TableCell className="text-muted-foreground">{formatDate(d.created_at)}</TableCell>
                <TableCell className="space-x-2 text-right">
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={!["running", "provisioning"].includes(d.status)}
                    onClick={() => setConfirm({ type: "stop", d })}
                  >
                    Stop
                  </Button>
                  <Button
                    variant="destructive"
                    size="sm"
                    disabled={["deleting", "deleted"].includes(d.status)}
                    onClick={() => setConfirm({ type: "delete", d })}
                  >
                    Delete
                  </Button>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
        <Pagination
          page={page}
          pageSize={deploymentsQuery.data?.page_size ?? 20}
          total={deploymentsQuery.data?.total ?? 0}
          onPageChange={setPage}
        />
      </CardContent>

      <ConfirmDialog
        open={confirm !== null}
        onOpenChange={(open) => !open && setConfirm(null)}
        title={
          confirm?.type === "stop"
            ? `Stop "${confirm.d.name}"?`
            : `Delete "${confirm?.d.name}"?`
        }
        description={
          confirm?.type === "stop"
            ? "The user's containers will be stopped."
            : "The deployment and its volumes will be removed permanently."
        }
        confirmLabel={confirm?.type === "stop" ? "Stop" : "Delete"}
        destructive={confirm?.type === "delete"}
        loading={stopMutation.isPending || deleteMutation.isPending}
        onConfirm={() => {
          if (!confirm) return;
          const settle = { onSettled: () => setConfirm(null) };
          if (confirm.type === "stop") stopMutation.mutate(confirm.d.id, settle);
          else deleteMutation.mutate(confirm.d.id, settle);
        }}
      />
    </Card>
  );
}

// ---------- Pricing tab ----------

const PRICE_FIELDS = [
  ["base_cost_per_hour", "Base / hour"],
  ["cpu_cost_per_core_hour", "CPU core / hour"],
  ["memory_cost_per_gb_hour", "GB RAM / hour"],
  ["storage_cost_per_gb_hour", "GB storage / hour"],
  ["service_cost_per_hour", "Extra service / hour"],
] as const;

function PricingTab() {
  const pricingQuery = useAdminPricing();
  const createMutation = useCreatePricing();
  const activateMutation = useActivatePricing();
  const [name, setName] = useState("");
  const [values, setValues] = useState<Record<string, string>>({
    base_cost_per_hour: "0",
    cpu_cost_per_core_hour: "1",
    memory_cost_per_gb_hour: "1",
    storage_cost_per_gb_hour: "0.05",
    service_cost_per_hour: "0.25",
  });

  const valid =
    name.trim().length > 0 &&
    PRICE_FIELDS.every(([key]) => values[key] !== "" && !Number.isNaN(Number(values[key])));

  return (
    <div className="grid gap-4 lg:grid-cols-[1fr_360px]">
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Plans</CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          {pricingQuery.isLoading ? (
            <TableSkeleton rows={3} cols={5} />
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>CPU</TableHead>
                  <TableHead>RAM</TableHead>
                  <TableHead>Storage</TableHead>
                  <TableHead>Service</TableHead>
                  <TableHead className="text-right">Status</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {pricingQuery.data?.map((plan) => (
                  <TableRow key={plan.id}>
                    <TableCell className="font-medium">{plan.name}</TableCell>
                    <TableCell className="tabular-nums">{formatRate(plan.cpu_cost_per_core_hour)}</TableCell>
                    <TableCell className="tabular-nums">{formatRate(plan.memory_cost_per_gb_hour)}</TableCell>
                    <TableCell className="tabular-nums">{formatRate(plan.storage_cost_per_gb_hour)}</TableCell>
                    <TableCell className="tabular-nums">{formatRate(plan.service_cost_per_hour)}</TableCell>
                    <TableCell className="text-right">
                      {plan.is_active ? (
                        <Badge className="border-emerald-500/40 bg-emerald-500/15 text-emerald-500">
                          active
                        </Badge>
                      ) : (
                        <Button
                          variant="outline"
                          size="sm"
                          loading={activateMutation.isPending}
                          onClick={() => activateMutation.mutate(plan.id)}
                        >
                          Activate
                        </Button>
                      )}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">New plan</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="space-y-1.5">
            <Label htmlFor="plan-name">Name</Label>
            <Input id="plan-name" value={name} onChange={(e) => setName(e.target.value)} />
          </div>
          {PRICE_FIELDS.map(([key, label]) => (
            <div key={key} className="space-y-1.5">
              <Label htmlFor={`plan-${key}`}>{label}</Label>
              <Input
                id={`plan-${key}`}
                inputMode="decimal"
                value={values[key]}
                onChange={(e) => setValues((v) => ({ ...v, [key]: e.target.value }))}
              />
            </div>
          ))}
          <p className="text-xs text-muted-foreground">
            Activating applies to new deployments only — running workloads keep their frozen
            prices.
          </p>
          <Button
            className="w-full"
            disabled={!valid}
            loading={createMutation.isPending}
            onClick={() =>
              createMutation.mutate(
                {
                  name: name.trim(),
                  base_cost_per_hour: values.base_cost_per_hour,
                  cpu_cost_per_core_hour: values.cpu_cost_per_core_hour,
                  memory_cost_per_gb_hour: values.memory_cost_per_gb_hour,
                  storage_cost_per_gb_hour: values.storage_cost_per_gb_hour,
                  service_cost_per_hour: values.service_cost_per_hour,
                  activate: true,
                },
                { onSuccess: () => setName("") },
              )
            }
          >
            <Plus aria-hidden /> Create & activate
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}

// ---------- Image rules tab ----------

function ImagesTab() {
  const imagesQuery = useAdminImages();
  const createMutation = useCreateImageRule();
  const deleteMutation = useDeleteImageRule();
  const [pattern, setPattern] = useState("");
  const [mode, setMode] = useState<"allow" | "block">("allow");
  const [reason, setReason] = useState("");

  return (
    <div className="grid gap-4 lg:grid-cols-[1fr_360px]">
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Rules</CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          {imagesQuery.isLoading ? (
            <TableSkeleton rows={4} cols={4} />
          ) : (imagesQuery.data ?? []).length === 0 ? (
            <EmptyState
              className="m-4"
              title="No rules"
              description="With no allow rules, every image except blocked ones is permitted."
            />
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Pattern</TableHead>
                  <TableHead>Mode</TableHead>
                  <TableHead>Reason</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {imagesQuery.data?.map((rule) => (
                  <TableRow key={rule.id}>
                    <TableCell className="font-mono text-xs">{rule.pattern}</TableCell>
                    <TableCell>
                      {rule.mode === "allow" ? (
                        <Badge className="border-emerald-500/40 bg-emerald-500/15 text-emerald-500">
                          <ShieldCheck className="mr-1 h-3 w-3" aria-hidden /> allow
                        </Badge>
                      ) : (
                        <Badge className="border-red-500/40 bg-red-500/15 text-red-500">
                          <ShieldBan className="mr-1 h-3 w-3" aria-hidden /> block
                        </Badge>
                      )}
                    </TableCell>
                    <TableCell className="text-muted-foreground">{rule.reason || "—"}</TableCell>
                    <TableCell className="text-right">
                      <Button
                        variant="ghost"
                        size="icon"
                        aria-label={`Delete rule ${rule.pattern}`}
                        onClick={() => deleteMutation.mutate(rule.id)}
                      >
                        <Trash2 aria-hidden />
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Add rule</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="space-y-1.5">
            <Label htmlFor="rule-pattern">Pattern</Label>
            <Input
              id="rule-pattern"
              className="font-mono"
              placeholder="nginx, nginx:1.27 or bitnami/*"
              value={pattern}
              onChange={(e) => setPattern(e.target.value)}
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="rule-mode">Mode</Label>
            <Select
              id="rule-mode"
              value={mode}
              onChange={(e) => setMode(e.target.value as "allow" | "block")}
            >
              <option value="allow">allow</option>
              <option value="block">block</option>
            </Select>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="rule-reason">Reason</Label>
            <Input
              id="rule-reason"
              value={reason}
              onChange={(e) => setReason(e.target.value)}
            />
          </div>
          <Button
            className="w-full"
            disabled={pattern.trim() === ""}
            loading={createMutation.isPending}
            onClick={() =>
              createMutation.mutate(
                { pattern: pattern.trim(), mode, reason },
                { onSuccess: () => setPattern("") },
              )
            }
          >
            <Plus aria-hidden /> Add rule
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}

// ---------- Templates tab ----------

function TemplatesTab() {
  const templatesQuery = useAdminTemplates();
  const reviewMutation = useReviewTemplate();
  const [preview, setPreview] = useState<Template | null>(null);

  if (templatesQuery.isLoading) return <TableSkeleton rows={4} cols={4} />;
  if (templatesQuery.isError)
    return <ErrorState error={templatesQuery.error} onRetry={() => templatesQuery.refetch()} />;

  return (
    <Card>
      <CardContent className="p-0">
        {(templatesQuery.data ?? []).length === 0 ? (
          <EmptyState className="m-4" title="No templates submitted yet" />
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Name</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Submitted</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {templatesQuery.data?.map((template) => (
                <TableRow key={template.id}>
                  <TableCell className="font-medium">{template.name}</TableCell>
                  <TableCell>
                    <Badge className="capitalize">{template.status}</Badge>
                  </TableCell>
                  <TableCell className="text-muted-foreground">
                    {formatDate(template.created_at)}
                  </TableCell>
                  <TableCell className="space-x-2 text-right">
                    <Button variant="outline" size="sm" onClick={() => setPreview(template)}>
                      View
                    </Button>
                    {template.status === "pending" && (
                      <>
                        <Button
                          size="sm"
                          loading={reviewMutation.isPending}
                          onClick={() =>
                            reviewMutation.mutate({ id: template.id, approve: true })
                          }
                        >
                          Approve
                        </Button>
                        <Button
                          variant="destructive"
                          size="sm"
                          loading={reviewMutation.isPending}
                          onClick={() =>
                            reviewMutation.mutate({ id: template.id, approve: false })
                          }
                        >
                          Reject
                        </Button>
                      </>
                    )}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </CardContent>

      <Dialog open={preview !== null} onOpenChange={(open) => !open && setPreview(null)}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>{preview?.name}</DialogTitle>
            <DialogDescription>{preview?.description}</DialogDescription>
          </DialogHeader>
          <pre className="max-h-96 overflow-auto rounded-lg bg-black/40 p-4 font-mono text-xs">
            {preview?.compose_yaml}
          </pre>
        </DialogContent>
      </Dialog>
    </Card>
  );
}

// ---------- Audit tab ----------

function AuditTab() {
  const [page, setPage] = useState(1);
  const auditQuery = useAuditLogs(page, 50);

  if (auditQuery.isLoading) return <TableSkeleton rows={8} cols={5} />;
  if (auditQuery.isError)
    return <ErrorState error={auditQuery.error} onRetry={() => auditQuery.refetch()} />;

  return (
    <Card>
      <CardContent className="p-0">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Action</TableHead>
              <TableHead>Resource</TableHead>
              <TableHead>Actor</TableHead>
              <TableHead>IP</TableHead>
              <TableHead>When</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {auditQuery.data?.items.map((entry) => (
              <TableRow key={entry.id}>
                <TableCell className="font-mono text-xs">{entry.action}</TableCell>
                <TableCell className="font-mono text-xs text-muted-foreground">
                  {entry.resource_type}
                  {entry.resource_id ? `:${entry.resource_id.slice(0, 8)}` : ""}
                </TableCell>
                <TableCell className="font-mono text-xs">
                  {entry.actor_id ? entry.actor_id.slice(0, 8) : "system"}
                </TableCell>
                <TableCell className="text-muted-foreground">{entry.ip_address || "—"}</TableCell>
                <TableCell className="text-muted-foreground">
                  {formatDate(entry.created_at)}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
        <Pagination
          page={page}
          pageSize={auditQuery.data?.page_size ?? 50}
          total={auditQuery.data?.total ?? 0}
          onPageChange={setPage}
        />
      </CardContent>
    </Card>
  );
}

// ---------- Host tab ----------

function HostGauge({
  icon: Icon,
  label,
  used,
  total,
  format,
}: {
  icon: typeof Cpu;
  label: string;
  used: number;
  total: number;
  format: (n: number) => string;
}) {
  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between space-y-0 pb-2">
        <CardTitle className="text-sm font-medium text-muted-foreground">{label}</CardTitle>
        <Icon className="h-4 w-4 text-primary" aria-hidden />
      </CardHeader>
      <CardContent className="space-y-2">
        <p className="text-xl font-semibold tabular-nums">
          {format(used)} <span className="text-sm text-muted-foreground">/ {format(total)}</span>
        </p>
        <Progress value={used} max={Math.max(1, total)} />
      </CardContent>
    </Card>
  );
}

function HostTab() {
  const hostQuery = useAdminHost();
  if (hostQuery.isLoading)
    return (
      <div className="grid gap-4 sm:grid-cols-3">
        <CardSkeleton />
        <CardSkeleton />
        <CardSkeleton />
      </div>
    );
  if (hostQuery.isError || !hostQuery.data)
    return <ErrorState error={hostQuery.error} onRetry={() => hostQuery.refetch()} />;

  const host = hostQuery.data;
  return (
    <div className="space-y-4">
      <div className="grid gap-4 sm:grid-cols-3">
        <Card>
          <CardHeader className="flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">CPU load</CardTitle>
            <Cpu className="h-4 w-4 text-primary" aria-hidden />
          </CardHeader>
          <CardContent className="space-y-2">
            <p className="text-xl font-semibold tabular-nums">{host.cpu_percent.toFixed(1)}%</p>
            <Progress value={host.cpu_percent} />
          </CardContent>
        </Card>
        <HostGauge
          icon={MemoryStick}
          label="Memory"
          used={host.memory_used_mb}
          total={host.memory_total_mb}
          format={(n) => formatMB(n)}
        />
        <HostGauge
          icon={HardDrive}
          label="Disk"
          used={host.disk_used_gb}
          total={host.disk_total_gb}
          format={(n) => formatGB(n)}
        />
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Allocation</CardTitle>
        </CardHeader>
        <CardContent>
          <dl className="grid gap-4 text-sm sm:grid-cols-2 lg:grid-cols-4">
            <div>
              <dt className="text-muted-foreground">Running tenant containers</dt>
              <dd className="text-lg font-semibold tabular-nums">{host.running_containers}</dd>
            </div>
            <div>
              <dt className="text-muted-foreground">Allocated CPU</dt>
              <dd className="text-lg font-semibold tabular-nums">
                {host.allocated_cpu} <span className="text-xs">({host.allocatable_cpu} free)</span>
              </dd>
            </div>
            <div>
              <dt className="text-muted-foreground">Allocated memory</dt>
              <dd className="text-lg font-semibold tabular-nums">
                {formatMB(host.allocated_memory_mb)}{" "}
                <span className="text-xs">({formatMB(host.allocatable_memory_mb)} free)</span>
              </dd>
            </div>
            <div>
              <dt className="text-muted-foreground">Allocated storage</dt>
              <dd className="text-lg font-semibold tabular-nums">
                {host.allocated_storage_gb} GB{" "}
                <span className="text-xs">({host.allocatable_storage_gb} GB free)</span>
              </dd>
            </div>
          </dl>
          <p className="mt-4 text-xs text-muted-foreground">
            Sampled {formatDate(host.sampled_at)}
          </p>
        </CardContent>
      </Card>
    </div>
  );
}

// ---------- Page ----------

export function AdminPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Administration</h1>
        <p className="text-sm text-muted-foreground">
          Platform operations: users, workloads, pricing and governance.
        </p>
      </div>

      <Tabs defaultValue="users">
        <TabsList className="flex-wrap">
          <TabsTrigger value="users">Users</TabsTrigger>
          <TabsTrigger value="deployments">Deployments</TabsTrigger>
          <TabsTrigger value="pricing">Pricing</TabsTrigger>
          <TabsTrigger value="images">Images</TabsTrigger>
          <TabsTrigger value="templates">Templates</TabsTrigger>
          <TabsTrigger value="audit">Audit log</TabsTrigger>
          <TabsTrigger value="host">Host</TabsTrigger>
        </TabsList>
        <TabsContent value="users">
          <UsersTab />
        </TabsContent>
        <TabsContent value="deployments">
          <DeploymentsTab />
        </TabsContent>
        <TabsContent value="pricing">
          <PricingTab />
        </TabsContent>
        <TabsContent value="images">
          <ImagesTab />
        </TabsContent>
        <TabsContent value="templates">
          <TemplatesTab />
        </TabsContent>
        <TabsContent value="audit">
          <AuditTab />
        </TabsContent>
        <TabsContent value="host">
          <HostTab />
        </TabsContent>
      </Tabs>
    </div>
  );
}
