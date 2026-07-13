import { Link, useNavigate } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { Coins, LogOut, Menu, Settings, UserRound } from "lucide-react";
import { authApi } from "@/api/auth";
import { authStore } from "@/lib/auth-store";
import { useBalance } from "@/hooks/use-credits";
import { useMe } from "@/hooks/use-users";
import { formatCredits, formatRunway } from "@/lib/format";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

function BalanceChip() {
  const { data, isLoading } = useBalance({ refetchInterval: 30_000 });

  if (isLoading) return <Skeleton className="h-8 w-28 rounded-full" />;
  if (!data) return null;

  const low = Number(data.balance) < Number(data.estimated_hourly_spend);

  return (
    <Link
      to="/credits"
      className="inline-flex items-center gap-2 rounded-full border bg-secondary/50 px-3 py-1.5 text-sm transition-colors hover:bg-accent"
      title={`Runway: ${formatRunway(data.runway_hours)}`}
    >
      <Coins className={low ? "h-4 w-4 text-red-500" : "h-4 w-4 text-primary"} aria-hidden />
      <span className="font-medium tabular-nums">{formatCredits(data.balance)}</span>
      <span className="hidden text-xs text-muted-foreground sm:inline">credits</span>
    </Link>
  );
}

export function Topbar({ onMenuClick }: { onMenuClick: () => void }) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { data: me } = useMe();

  async function handleLogout() {
    const refreshToken = authStore.getRefreshToken();
    try {
      if (refreshToken) await authApi.logout(refreshToken);
    } catch {
      // best-effort server-side revocation
    }
    authStore.clearTokens();
    queryClient.clear();
    navigate("/login", { replace: true });
  }

  return (
    <header className="sticky top-0 z-30 flex h-16 items-center gap-3 border-b bg-background/80 px-4 backdrop-blur lg:px-8">
      <Button
        variant="ghost"
        size="icon"
        className="lg:hidden"
        onClick={onMenuClick}
        aria-label="Open menu"
      >
        <Menu />
      </Button>

      <div className="ml-auto flex items-center gap-3">
        <BalanceChip />
        <DropdownMenu>
          <DropdownMenuTrigger
            aria-label="User menu"
            className="flex h-9 w-9 items-center justify-center rounded-full border bg-secondary/50 transition-colors hover:bg-accent"
          >
            <UserRound className="h-4 w-4" aria-hidden />
          </DropdownMenuTrigger>
          <DropdownMenuContent className="w-56">
            <DropdownMenuLabel className="truncate">
              {me?.email ?? "Signed in"}
            </DropdownMenuLabel>
            <DropdownMenuSeparator />
            <DropdownMenuItem onClick={() => navigate("/settings")}>
              <Settings aria-hidden /> Settings
            </DropdownMenuItem>
            <DropdownMenuItem onClick={handleLogout} destructive>
              <LogOut aria-hidden /> Log out
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </header>
  );
}
