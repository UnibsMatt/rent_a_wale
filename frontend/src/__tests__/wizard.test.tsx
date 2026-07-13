import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { CostEstimate } from "@/api/types";
import { DeploymentWizardPage } from "@/pages/deployment-wizard";
import { deploymentsApi } from "@/api/deployments";
import { creditsApi } from "@/api/credits";

vi.mock("@/api/deployments", () => ({
  deploymentsApi: {
    estimate: vi.fn(),
    validateCompose: vi.fn(),
    create: vi.fn(),
    get: vi.fn(),
    platformLogs: vi.fn().mockResolvedValue([]),
  },
}));
vi.mock("@/api/credits", () => ({
  creditsApi: {
    balance: vi.fn().mockResolvedValue({
      balance: "500.0000",
      estimated_hourly_spend: "0",
      runway_hours: null,
    }),
  },
}));

const ESTIMATE: CostEstimate = {
  hourly: "3.0000",
  daily: "72.0000",
  monthly: "2160.0000",
  plan_name: "default",
  breakdown: {
    base: "0.0000",
    cpu: "1.0000",
    memory: "2.0000",
    storage: "0.0000",
    extra_services: "0.0000",
  },
};

function renderWizard() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/deployments/new"]}>
        <DeploymentWizardPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("DeploymentWizardPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(deploymentsApi.estimate).mockResolvedValue(ESTIMATE);
    vi.mocked(creditsApi.balance).mockResolvedValue({
      balance: "500.0000",
      estimated_hourly_spend: "0",
      runway_hours: null,
    });
  });

  it("step 1: requires a type before continuing", async () => {
    const user = userEvent.setup();
    renderWizard();

    const next = screen.getByRole("button", { name: /continue/i });
    expect(next).toBeDisabled();

    await user.click(screen.getByRole("button", { name: /docker image/i }));
    expect(next).toBeEnabled();
  });

  it("navigates from type to configure step for image deployments", async () => {
    const user = userEvent.setup();
    renderWizard();

    await user.click(screen.getByRole("button", { name: /docker image/i }));
    await user.click(screen.getByRole("button", { name: /continue/i }));

    expect(await screen.findByLabelText("Deployment name")).toBeInTheDocument();
    expect(screen.getByLabelText("Docker image")).toBeInTheDocument();
    expect(screen.getByText("Environment variables")).toBeInTheDocument();
  });

  it("reaches the estimate step and shows pricing from the API", async () => {
    const user = userEvent.setup();
    renderWizard();

    await user.click(screen.getByRole("button", { name: /docker image/i }));
    await user.click(screen.getByRole("button", { name: /continue/i }));

    await user.type(await screen.findByLabelText("Deployment name"), "my-nginx");
    await user.type(screen.getByLabelText("Docker image"), "nginx:1.27");
    await user.click(screen.getByRole("button", { name: /continue/i }));

    // Estimate values from the mocked pricing engine.
    expect(await screen.findByText("Estimated cost")).toBeInTheDocument();
    expect(await screen.findByText("72.00")).toBeInTheDocument(); // daily
    expect(screen.getByText(/2,?160\.00/)).toBeInTheDocument(); // monthly
    expect(deploymentsApi.estimate).toHaveBeenCalledWith(
      expect.objectContaining({ service_count: 1 }),
    );

    // Deploy stays locked behind the explicit confirmation checkbox.
    const deploy = screen.getByRole("button", { name: /deploy/i });
    expect(deploy).toBeDisabled();
    await user.click(screen.getByLabelText(/I understand credits are deducted/i));
    expect(deploy).toBeEnabled();
  });
});
