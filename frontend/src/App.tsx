import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { AuthProvider } from "@/lib/auth-context";
import { Toaster } from "@/components/ui/toast";
import {
  RedirectIfAuthenticated,
  RequireAdmin,
  RequireAuth,
} from "@/components/route-guards";
import { AppLayout } from "@/components/layout/app-layout";
import { LoginPage } from "@/pages/login";
import { RegisterPage } from "@/pages/register";
import { DashboardPage } from "@/pages/dashboard";
import { DeploymentWizardPage } from "@/pages/deployment-wizard";
import { DeploymentDetailPage } from "@/pages/deployment-detail";
import { CreditsPage } from "@/pages/credits";
import { TemplatesPage } from "@/pages/templates";
import { SettingsPage } from "@/pages/settings";
import { AdminPage } from "@/pages/admin";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      staleTime: 10_000,
      refetchOnWindowFocus: false,
    },
  },
});

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <BrowserRouter>
          <Routes>
            <Route element={<RedirectIfAuthenticated />}>
              <Route path="/login" element={<LoginPage />} />
              <Route path="/register" element={<RegisterPage />} />
            </Route>

            <Route element={<RequireAuth />}>
              <Route element={<AppLayout />}>
                <Route path="/dashboard" element={<DashboardPage />} />
                <Route path="/deployments/new" element={<DeploymentWizardPage />} />
                <Route path="/deployments/:id" element={<DeploymentDetailPage />} />
                <Route path="/credits" element={<CreditsPage />} />
                <Route path="/templates" element={<TemplatesPage />} />
                <Route path="/settings" element={<SettingsPage />} />
                <Route element={<RequireAdmin />}>
                  <Route path="/admin" element={<AdminPage />} />
                </Route>
              </Route>
            </Route>

            <Route path="/" element={<Navigate to="/dashboard" replace />} />
            <Route path="*" element={<Navigate to="/dashboard" replace />} />
          </Routes>
        </BrowserRouter>
        <Toaster />
      </AuthProvider>
    </QueryClientProvider>
  );
}
