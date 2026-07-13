import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { KeyRound, MonitorSmartphone, UserRound } from "lucide-react";
import { z } from "zod";
import { useChangePassword, useMe, useQuota, useSessions } from "@/hooks/use-users";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Progress } from "@/components/ui/progress";
import { CardSkeleton } from "@/components/states";
import { formatCpu, formatDate, formatMB } from "@/lib/format";

const passwordSchema = z
  .object({
    current: z.string().min(1, "Required"),
    next: z.string().min(10, "At least 10 characters").max(128),
    confirm: z.string(),
  })
  .refine((v) => v.next === v.confirm, {
    path: ["confirm"],
    message: "Passwords do not match",
  });

type PasswordValues = z.infer<typeof passwordSchema>;

function QuotaBar({ label, used, max }: { label: string; used: string; max: string; }) {
  return (
    <div>
      <div className="mb-1 flex justify-between text-sm">
        <span className="text-muted-foreground">{label}</span>
        <span className="tabular-nums">
          {used} / {max}
        </span>
      </div>
    </div>
  );
}

export function SettingsPage() {
  const meQuery = useMe();
  const quotaQuery = useQuota();
  const sessionsQuery = useSessions();
  const changePassword = useChangePassword();

  const form = useForm<PasswordValues>({
    resolver: zodResolver(passwordSchema),
    defaultValues: { current: "", next: "", confirm: "" },
  });
  const err = form.formState.errors;

  const quota = quotaQuery.data;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Account settings</h1>
        <p className="text-sm text-muted-foreground">Profile, security and usage limits.</p>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        {/* Profile */}
        {meQuery.isLoading ? (
          <CardSkeleton />
        ) : (
          <Card>
            <CardHeader className="flex-row items-center gap-2 space-y-0">
              <UserRound className="h-4 w-4 text-primary" aria-hidden />
              <CardTitle className="text-base">Profile</CardTitle>
            </CardHeader>
            <CardContent>
              <dl className="space-y-2 text-sm">
                <div className="flex justify-between">
                  <dt className="text-muted-foreground">Email</dt>
                  <dd className="font-medium">{meQuery.data?.email}</dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-muted-foreground">Role</dt>
                  <dd>
                    <Badge className="capitalize">{meQuery.data?.role}</Badge>
                  </dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-muted-foreground">Email verified</dt>
                  <dd>{meQuery.data?.is_email_verified ? "Yes" : "No"}</dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-muted-foreground">Container namespace</dt>
                  <dd className="font-mono text-xs">user{meQuery.data?.user_number}</dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-muted-foreground">Member since</dt>
                  <dd>{formatDate(meQuery.data?.created_at)}</dd>
                </div>
              </dl>
            </CardContent>
          </Card>
        )}

        {/* Change password */}
        <Card>
          <CardHeader className="flex-row items-center gap-2 space-y-0">
            <KeyRound className="h-4 w-4 text-primary" aria-hidden />
            <CardTitle className="text-base">Change password</CardTitle>
          </CardHeader>
          <CardContent>
            <form
              className="space-y-3"
              onSubmit={form.handleSubmit((values) =>
                changePassword.mutate(
                  { current: values.current, next: values.next },
                  { onSuccess: () => form.reset() },
                ),
              )}
            >
              <div className="space-y-1.5">
                <Label htmlFor="pw-current">Current password</Label>
                <Input id="pw-current" type="password" {...form.register("current")} />
                {err.current && <p className="text-xs text-red-500">{err.current.message}</p>}
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="pw-next">New password</Label>
                <Input id="pw-next" type="password" {...form.register("next")} />
                {err.next && <p className="text-xs text-red-500">{err.next.message}</p>}
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="pw-confirm">Confirm new password</Label>
                <Input id="pw-confirm" type="password" {...form.register("confirm")} />
                {err.confirm && <p className="text-xs text-red-500">{err.confirm.message}</p>}
              </div>
              <p className="text-xs text-muted-foreground">
                Changing your password signs you out of every device.
              </p>
              <Button type="submit" loading={changePassword.isPending}>
                Update password
              </Button>
            </form>
          </CardContent>
        </Card>
      </div>

      {/* Quotas */}
      {quota && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Resource quotas</CardTitle>
          </CardHeader>
          <CardContent className="grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
            <div>
              <QuotaBar
                label="CPU"
                used={formatCpu(Number(quota.used_cpu))}
                max={formatCpu(Number(quota.max_cpu_quota))}
              />
              <Progress value={Number(quota.used_cpu)} max={Number(quota.max_cpu_quota)} />
            </div>
            <div>
              <QuotaBar
                label="Memory"
                used={formatMB(quota.used_memory_mb)}
                max={formatMB(quota.max_memory_mb_quota)}
              />
              <Progress value={quota.used_memory_mb} max={quota.max_memory_mb_quota} />
            </div>
            <div>
              <QuotaBar
                label="Storage"
                used={`${quota.used_storage_gb} GB`}
                max={`${quota.max_storage_gb_quota} GB`}
              />
              <Progress value={quota.used_storage_gb} max={quota.max_storage_gb_quota} />
            </div>
            <div>
              <QuotaBar
                label="Deployments"
                used={String(quota.used_deployments)}
                max={String(quota.max_deployments_quota)}
              />
              <Progress value={quota.used_deployments} max={quota.max_deployments_quota} />
            </div>
          </CardContent>
        </Card>
      )}

      {/* Sessions */}
      <Card>
        <CardHeader className="flex-row items-center gap-2 space-y-0">
          <MonitorSmartphone className="h-4 w-4 text-primary" aria-hidden />
          <CardTitle className="text-base">Active sessions</CardTitle>
        </CardHeader>
        <CardContent>
          {(sessionsQuery.data ?? []).length === 0 ? (
            <p className="text-sm text-muted-foreground">No active sessions.</p>
          ) : (
            <ul className="space-y-3">
              {sessionsQuery.data?.map((session) => (
                <li
                  key={session.id}
                  className="flex flex-wrap items-center justify-between gap-2 rounded-lg border p-3 text-sm"
                >
                  <div>
                    <p className="font-medium">{session.ip_address || "unknown IP"}</p>
                    <p className="max-w-xl truncate text-xs text-muted-foreground">
                      {session.user_agent || "unknown client"}
                    </p>
                  </div>
                  <div className="text-right text-xs text-muted-foreground">
                    <p>Signed in {formatDate(session.created_at)}</p>
                    <p>Last used {formatDate(session.last_used_at)}</p>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
