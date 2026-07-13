import { Navigate, Outlet, useLocation } from "react-router-dom";
import { Loader2 } from "lucide-react";
import { useAuth } from "@/lib/auth-context";

function FullPageLoader() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-background">
      <div className="flex flex-col items-center gap-3 text-muted-foreground">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
        <span className="text-sm">Loading Rent-a-Whale…</span>
      </div>
    </div>
  );
}

/** Unauthenticated visitors are sent to /login. */
export function RequireAuth() {
  const { ready, isAuthenticated } = useAuth();
  const location = useLocation();

  if (!ready) return <FullPageLoader />;
  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location.pathname }} replace />;
  }
  return <Outlet />;
}

/** Non-admins hitting /admin are bounced to the dashboard. */
export function RequireAdmin() {
  const { role } = useAuth();
  if (role !== "admin") return <Navigate to="/dashboard" replace />;
  return <Outlet />;
}

/** Logged-in users hitting /login or /register go straight to the dashboard. */
export function RedirectIfAuthenticated() {
  const { ready, isAuthenticated } = useAuth();
  if (!ready) return <FullPageLoader />;
  if (isAuthenticated) return <Navigate to="/dashboard" replace />;
  return <Outlet />;
}
