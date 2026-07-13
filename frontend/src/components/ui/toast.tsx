import { useEffect, useState } from "react";
import { CheckCircle2, Info, X, XCircle } from "lucide-react";
import { cn } from "@/lib/utils";

export type ToastVariant = "default" | "success" | "error";

export interface ToastItem {
  id: number;
  title: string;
  description?: string;
  variant: ToastVariant;
}

type Listener = (toasts: ToastItem[]) => void;

let toasts: ToastItem[] = [];
let nextId = 0;
const listeners = new Set<Listener>();
const TOAST_TTL_MS = 5000;

function emit(): void {
  for (const listener of listeners) listener(toasts);
}

export function dismissToast(id: number): void {
  toasts = toasts.filter((t) => t.id !== id);
  emit();
}

function push(item: Omit<ToastItem, "id">): number {
  const id = ++nextId;
  toasts = [...toasts.slice(-4), { ...item, id }];
  emit();
  setTimeout(() => dismissToast(id), TOAST_TTL_MS);
  return id;
}

/** sonner-like imperative toast API. */
export const toast = Object.assign(
  (title: string, description?: string) => push({ title, description, variant: "default" }),
  {
    success: (title: string, description?: string) =>
      push({ title, description, variant: "success" }),
    error: (title: string, description?: string) =>
      push({ title, description, variant: "error" }),
  },
);

const icons: Record<ToastVariant, React.ReactNode> = {
  default: <Info className="h-4 w-4 text-primary" aria-hidden />,
  success: <CheckCircle2 className="h-4 w-4 text-emerald-500" aria-hidden />,
  error: <XCircle className="h-4 w-4 text-red-500" aria-hidden />,
};

export function Toaster() {
  const [items, setItems] = useState<ToastItem[]>(toasts);

  useEffect(() => {
    listeners.add(setItems);
    return () => {
      listeners.delete(setItems);
    };
  }, []);

  if (items.length === 0) return null;

  return (
    <div
      aria-live="polite"
      className="fixed bottom-4 right-4 z-[100] flex w-full max-w-sm flex-col gap-2"
    >
      {items.map((item) => (
        <div
          key={item.id}
          role="status"
          className={cn(
            "pointer-events-auto flex items-start gap-3 rounded-lg border bg-popover p-4 shadow-lg animate-slide-in-right",
            item.variant === "error" && "border-red-500/40",
            item.variant === "success" && "border-emerald-500/40",
          )}
        >
          <span className="mt-0.5">{icons[item.variant]}</span>
          <div className="flex-1 space-y-0.5">
            <p className="text-sm font-medium leading-tight">{item.title}</p>
            {item.description && (
              <p className="text-xs text-muted-foreground">{item.description}</p>
            )}
          </div>
          <button
            type="button"
            aria-label="Dismiss"
            className="rounded opacity-60 transition-opacity hover:opacity-100"
            onClick={() => dismissToast(item.id)}
          >
            <X className="h-4 w-4" />
          </button>
        </div>
      ))}
    </div>
  );
}
