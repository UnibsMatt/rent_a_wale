import { NavLink } from "react-router-dom";
import {
  Coins,
  FileCode2,
  LayoutDashboard,
  Rocket,
  Settings,
  ShieldCheck,
  X,
} from "lucide-react";
import { useAuth } from "@/lib/auth-context";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";

const NAV_ITEMS = [
  { to: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { to: "/deployments/new", label: "New Deployment", icon: Rocket },
  { to: "/credits", label: "Credits", icon: Coins },
  { to: "/templates", label: "Templates", icon: FileCode2 },
  { to: "/settings", label: "Settings", icon: Settings },
];

function NavItem({
  to,
  label,
  icon: Icon,
  onNavigate,
}: {
  to: string;
  label: string;
  icon: typeof LayoutDashboard;
  onNavigate: () => void;
}) {
  return (
    <NavLink
      to={to}
      onClick={onNavigate}
      className={({ isActive }) =>
        cn(
          "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors",
          isActive
            ? "bg-primary/15 text-primary"
            : "text-muted-foreground hover:bg-accent hover:text-foreground",
        )
      }
    >
      <Icon className="h-4 w-4 shrink-0" aria-hidden />
      {label}
    </NavLink>
  );
}

export function Sidebar({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { role } = useAuth();

  return (
    <>
      {/* Mobile overlay */}
      {open && (
        <div
          className="fixed inset-0 z-40 bg-black/60 lg:hidden"
          aria-hidden
          onClick={onClose}
        />
      )}
      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-50 flex w-64 flex-col border-r bg-card transition-transform duration-200 lg:translate-x-0",
          open ? "translate-x-0" : "-translate-x-full",
        )}
      >
        <div className="flex h-16 items-center justify-between border-b px-5">
          <NavLink to="/dashboard" className="flex items-center gap-2 font-semibold">
            <span className="text-xl" aria-hidden>
              🐳
            </span>
            <span className="tracking-tight">Rent-a-Whale</span>
          </NavLink>
          <Button
            variant="ghost"
            size="icon"
            className="lg:hidden"
            onClick={onClose}
            aria-label="Close menu"
          >
            <X />
          </Button>
        </div>

        <nav className="flex-1 space-y-1 overflow-y-auto p-3">
          {NAV_ITEMS.map((item) => (
            <NavItem key={item.to} {...item} onNavigate={onClose} />
          ))}

          {role === "admin" && (
            <div className="pt-4">
              <p className="px-3 pb-1 text-xs font-medium uppercase tracking-wider text-muted-foreground">
                Admin
              </p>
              <NavItem
                to="/admin"
                label="Administration"
                icon={ShieldCheck}
                onNavigate={onClose}
              />
            </div>
          )}
        </nav>

        <div className="border-t p-4 text-xs text-muted-foreground">
          Containers on demand · v1.0
        </div>
      </aside>
    </>
  );
}
