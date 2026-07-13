import { cn } from "@/lib/utils";
import { humanizeStatus, statusBadgeClass } from "@/lib/format";

export function StatusBadge({ status, className }: { status: string; className?: string }) {
  const animated = status === "provisioning" || status === "pending" || status === "deleting";
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-medium capitalize",
        statusBadgeClass(status),
        className,
      )}
    >
      <span
        className={cn(
          "h-1.5 w-1.5 rounded-full bg-current",
          (status === "running" || animated) && "animate-pulse",
        )}
        aria-hidden
      />
      {humanizeStatus(status)}
    </span>
  );
}
