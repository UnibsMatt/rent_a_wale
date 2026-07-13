import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { Balance, Deployment } from "@/api/types";
import { DashboardPage } from "@/pages/dashboard";
import { deploymentsApi } from "@/api/deployments";
import { creditsApi } from "@/api/credits";

vi.mock("@/api/deployments", () => ({
  deploymentsApi: { list: vi.fn(), action: vi.fn(), remove: vi.fn() },
}));
vi.mock("@/api/credits", () => ({
  creditsApi: { balance: vi.fn() },
}));

const BALANCE: Balance = {
  balance: "150.0000",
  estimated_hourly_spend: "3.0000",
  runway_hours: "50.0",
};

function deployment(overrides: Partial<Deployment>): Deployment {
  return {
    id: "d-1",
    name: "my-nginx",
    slug: "my-nginx-ab12",
    kind: "image",
    status: "running",
    cpu_cores: 1,
    memory_mb: 2048,
    storage_gb: 1,
    estimated_hourly_cost: "3.0000",
    public_url: "http://my-nginx-ab12.localhost",
    failure_reason: null,
    started_at: "2026-07-13T10:00:00Z",
    stopped_at: null,
    created_at: "2026-07-13T09:59:00Z",
    services: [],
    ...overrides,
  };
}

function renderDashboard() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <DashboardPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("DashboardPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(creditsApi.balance).mockResolvedValue(BALANCE);
  });

  it("renders balance stats and the deployments table", async () => {
    vi.mocked(deploymentsApi.list).mockResolvedValue([
      deployment({ id: "d-1", name: "my-nginx", status: "running" }),
      deployment({
        id: "d-2",
        name: "old-app",
        status: "stopped",
        public_url: null,
      }),
    ]);
    renderDashboard();

    expect(await screen.findByText("my-nginx")).toBeInTheDocument();
    expect(screen.getByText("old-app")).toBeInTheDocument();
    // status badges
    expect(screen.getByText("running")).toBeInTheDocument();
    expect(screen.getByText("stopped")).toBeInTheDocument();
    // balance stat
    expect(await screen.findByText("150.00")).toBeInTheDocument();
    // running / total
    expect(screen.getByText("1 / 2")).toBeInTheDocument();
    // public URL link
    expect(
      screen.getByRole("link", { name: /my-nginx-ab12.localhost/i }),
    ).toHaveAttribute("href", "http://my-nginx-ab12.localhost");
  });

  it("shows the empty state when there are no deployments", async () => {
    vi.mocked(deploymentsApi.list).mockResolvedValue([]);
    renderDashboard();
    expect(await screen.findByText("No deployments yet")).toBeInTheDocument();
  });

  it("humanizes the credit_exhausted status", async () => {
    vi.mocked(deploymentsApi.list).mockResolvedValue([
      deployment({ status: "credit_exhausted", public_url: null }),
    ]);
    renderDashboard();
    expect(await screen.findByText("credit exhausted")).toBeInTheDocument();
  });
});
