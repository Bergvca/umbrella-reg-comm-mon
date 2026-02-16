import { render, screen } from "@testing-library/react";
import { BrowserRouter } from "react-router";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { DashboardPage } from "@/pages/DashboardPage";
import { describe, it, expect, vi } from "vitest";

// Mock the hook
vi.mock("@/hooks/useAlerts", () => ({
  useAlertStats: () => ({
    data: {
      by_severity: [
        { key: "critical", doc_count: 5 },
        { key: "high", doc_count: 12 },
        { key: "medium", doc_count: 15 },
        { key: "low", doc_count: 10 },
      ],
      by_channel: [
        { key: "email", doc_count: 20 },
        { key: "teams_chat", doc_count: 12 },
        { key: "bloomberg_chat", doc_count: 10 },
      ],
      by_status: [
        { key: "open", doc_count: 30 },
        { key: "in_review", doc_count: 7 },
        { key: "closed", doc_count: 5 },
      ],
      over_time: [
        { key_as_string: "2026-02-10", doc_count: 8 },
        { key_as_string: "2026-02-11", doc_count: 12 },
        { key_as_string: "2026-02-12", doc_count: 10 },
      ],
    },
    isLoading: false,
    isError: false,
  }),
}));

function renderWithProviders(ui: React.ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>{ui}</BrowserRouter>
    </QueryClientProvider>,
  );
}

describe("DashboardPage", () => {
  it("renders stat cards with data", () => {
    renderWithProviders(<DashboardPage />);
    expect(screen.getByText("42")).toBeInTheDocument();
    expect(screen.getByText("5")).toBeInTheDocument(); // critical
    expect(screen.getByText("12")).toBeInTheDocument(); // high
    expect(screen.getByText("25")).toBeInTheDocument(); // medium + low
  });

  it("renders chart titles", () => {
    renderWithProviders(<DashboardPage />);
    expect(screen.getByText("Alerts Over Time")).toBeInTheDocument();
    expect(screen.getByText("Alerts by Severity")).toBeInTheDocument();
    expect(screen.getByText("Alerts by Channel")).toBeInTheDocument();
  });
});
