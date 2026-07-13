import { ArrowRight, Container, FileCode2 } from "lucide-react";
import type { DeploymentKind } from "@/api/types";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

const OPTIONS: {
  kind: DeploymentKind;
  title: string;
  description: string;
  icon: typeof Container;
}[] = [
  {
    kind: "image",
    title: "Docker Image",
    description:
      "Run a single container from any public image. Configure ports, env vars, volumes and resources.",
    icon: Container,
  },
  {
    kind: "compose",
    title: "Docker Compose",
    description:
      "Deploy a multi-service stack from a compose file. We validate it and size resources automatically.",
    icon: FileCode2,
  },
];

export function TypeStep({
  value,
  onChange,
  onNext,
}: {
  value: DeploymentKind | null;
  onChange: (kind: DeploymentKind) => void;
  onNext: () => void;
}) {
  return (
    <div className="space-y-6">
      <div className="grid gap-4 sm:grid-cols-2">
        {OPTIONS.map(({ kind, title, description, icon: Icon }) => {
          const selected = value === kind;
          return (
            <button
              key={kind}
              type="button"
              onClick={() => onChange(kind)}
              aria-pressed={selected}
              className={cn(
                "flex flex-col items-start gap-3 rounded-lg border bg-card p-6 text-left transition-all hover:border-primary/60",
                selected
                  ? "border-primary ring-1 ring-primary shadow-[0_0_24px_-8px_hsl(var(--primary))]"
                  : "border-border",
              )}
            >
              <span
                className={cn(
                  "rounded-md p-2",
                  selected ? "bg-primary/15 text-primary" : "bg-secondary text-muted-foreground",
                )}
              >
                <Icon className="h-6 w-6" aria-hidden />
              </span>
              <span className="text-lg font-semibold">{title}</span>
              <span className="text-sm text-muted-foreground">{description}</span>
            </button>
          );
        })}
      </div>

      <div className="flex justify-end">
        <Button onClick={onNext} disabled={value === null}>
          Continue <ArrowRight aria-hidden />
        </Button>
      </div>
    </div>
  );
}
