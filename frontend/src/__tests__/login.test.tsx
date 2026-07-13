import { MemoryRouter, Route, Routes } from "react-router-dom";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { LoginPage } from "@/pages/login";
import { authStore } from "@/lib/auth-store";
import { authApi } from "@/api/auth";

vi.mock("@/api/auth", () => ({
  authApi: {
    login: vi.fn(),
  },
}));

function renderLogin() {
  return render(
    <MemoryRouter initialEntries={["/login"]}>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/dashboard" element={<p>dashboard page</p>} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("LoginPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    authStore.clearTokens();
  });

  it("renders the sign-in form", () => {
    renderLogin();
    expect(screen.getByText("Rent-a-Whale")).toBeInTheDocument();
    expect(screen.getByLabelText("Email")).toBeInTheDocument();
    expect(screen.getByLabelText("Password")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /sign in/i })).toBeInTheDocument();
  });

  it("shows validation errors and does not call the API", async () => {
    const user = userEvent.setup();
    renderLogin();
    await user.click(screen.getByRole("button", { name: /sign in/i }));
    expect(await screen.findByText("Email is required")).toBeInTheDocument();
    expect(screen.getByText("Password is required")).toBeInTheDocument();
    expect(authApi.login).not.toHaveBeenCalled();
  });

  it("submits credentials, stores the token pair and navigates", async () => {
    vi.mocked(authApi.login).mockResolvedValue({
      access_token: "access-token",
      refresh_token: "refresh-token",
      token_type: "bearer",
    });
    const user = userEvent.setup();
    renderLogin();

    await user.type(screen.getByLabelText("Email"), "user@example.com");
    await user.type(screen.getByLabelText("Password"), "s3cret-password");
    await user.click(screen.getByRole("button", { name: /sign in/i }));

    await waitFor(() => expect(screen.getByText("dashboard page")).toBeInTheDocument());
    expect(authApi.login).toHaveBeenCalledWith({
      email: "user@example.com",
      password: "s3cret-password",
    });
    expect(authStore.getAccessToken()).toBe("access-token");
    expect(authStore.getRefreshToken()).toBe("refresh-token");
  });

  it("surfaces API errors without navigating", async () => {
    vi.mocked(authApi.login).mockRejectedValue(new Error("Invalid email or password"));
    const user = userEvent.setup();
    renderLogin();

    await user.type(screen.getByLabelText("Email"), "user@example.com");
    await user.type(screen.getByLabelText("Password"), "wrong");
    await user.click(screen.getByRole("button", { name: /sign in/i }));

    await waitFor(() => expect(authApi.login).toHaveBeenCalled());
    expect(screen.queryByText("dashboard page")).not.toBeInTheDocument();
    expect(authStore.getAccessToken()).toBeNull();
  });
});
