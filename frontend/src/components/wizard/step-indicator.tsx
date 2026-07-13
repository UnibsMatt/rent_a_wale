import { Check } from "lucide-react";
import { cn } from "@/lib/utils";

const STEPS = ["Type", "Configure", "Estimate", "Launch"];

export function StepIndicator({ current }: { current: number }) {
  return (
    <ol className="flex items-center gap-2 sm:gap-4" aria-label="Wizard progress">
      {STEPS.map((label, i) => {
        const stepNumber = i + 1;
        const done = stepNumber < current;
        const active = stepNumber === current;
        return (
          <li key={label} className="flex flex-1 items-center gap-2 sm:gap-3">
            <span
              aria-current={active ? "step" : undefined}
              className={cn(
                "flex h-8 w-8 shrink-0 items-center justify-center rounded-full border text-sm font-medium transition-colors",
                done && "border-primary bg-primary text-primary-foreground",
                active && "border-primary text-primary",
                !done && !active && "border-border text-muted-foreground",
              )}
            >
              {done ? <Check className="h-4 w-4" aria-hidden /> : stepNumber}
            </span>
            <span
              className={cn(
                "hidden text-sm sm:inline",
                active ? "font-medium text-foreground" : "text-muted-foreground",
              )}
            >
              {label}
            </span>
            {stepNumber < STEPS.length && (
              <span
                className={cn("h-px flex-1", done ? "bg-primary" : "bg-border")}
                aria-hidden
              />
            )}
          </li>
        );
      })}
    </ol>
  );
}
