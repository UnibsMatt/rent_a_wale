import type { DeploymentStatus } from "@/api/types";

/** API sends decimals as strings; format for display with 2 decimals. */
export function formatCredits(value: string | number | null | undefined): string {
  if (value === null || value === undefined || value === "") return "—";
  const n = typeof value === "string" ? Number(value) : value;
  if (Number.isNaN(n)) return "—";
  return n.toLocaleString(undefined, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

/** Format a small decimal-string cost (e.g. hourly rates) with up to 4 decimals. */
export function formatRate(value: string | number | null | undefined): string {
  if (value === null || value === undefined || value === "") return "—";
  const n = typeof value === "string" ? Number(value) : value;
  if (Number.isNaN(n)) return "—";
  return n.toLocaleString(undefined, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 4,
  });
}

export function formatMB(mb: number | null | undefined): string {
  if (mb === null || mb === undefined || Number.isNaN(mb)) return "—";
  if (mb >= 1024) {
    const gb = mb / 1024;
    return `${gb.toLocaleString(undefined, { maximumFractionDigits: 1 })} GB`;
  }
  return `${Math.round(mb)} MB`;
}

export function formatGB(gb: number | null | undefined): string {
  if (gb === null || gb === undefined || Number.isNaN(gb)) return "—";
  return `${gb.toLocaleString(undefined, { maximumFractionDigits: 1 })} GB`;
}

export function formatDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
}

export function formatRunway(hours: string | number | null | undefined): string {
  if (hours === null || hours === undefined || hours === "") return "∞";
  const n = typeof hours === "string" ? Number(hours) : hours;
  if (Number.isNaN(n)) return "—";
  if (n >= 48) return `${Math.floor(n / 24)} days`;
  return `${n.toLocaleString(undefined, { maximumFractionDigits: 1 })} h`;
}

export function formatCpu(cores: number | null | undefined): string {
  if (cores === null || cores === undefined || Number.isNaN(cores)) return "—";
  return `${cores} ${cores === 1 ? "core" : "cores"}`;
}

export function humanizeStatus(status: string): string {
  return status.replace(/_/g, " ");
}

/** Badge classes per deployment status (dark-first palette). */
export const statusColor: Record<DeploymentStatus, string> = {
  pending: "border-amber-500/40 bg-amber-500/15 text-amber-600 dark:text-amber-400",
  provisioning: "border-blue-500/40 bg-blue-500/15 text-blue-600 dark:text-blue-400",
  running: "border-emerald-500/40 bg-emerald-500/15 text-emerald-600 dark:text-emerald-400",
  stopping: "border-amber-500/40 bg-amber-500/15 text-amber-600 dark:text-amber-400",
  stopped: "border-zinc-500/40 bg-zinc-500/15 text-zinc-600 dark:text-zinc-400",
  failed: "border-red-500/40 bg-red-500/15 text-red-600 dark:text-red-400",
  deleting: "border-red-500/40 bg-red-500/15 text-red-600 dark:text-red-400",
  deleted: "border-zinc-500/40 bg-zinc-500/15 text-zinc-600 dark:text-zinc-500",
  credit_exhausted: "border-orange-500/40 bg-orange-500/15 text-orange-600 dark:text-orange-400",
};

export function statusBadgeClass(status: string): string {
  return (
    statusColor[status as DeploymentStatus] ??
    "border-zinc-500/40 bg-zinc-500/15 text-zinc-600 dark:text-zinc-400"
  );
}
