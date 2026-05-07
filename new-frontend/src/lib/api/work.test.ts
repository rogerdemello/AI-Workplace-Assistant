import { beforeEach, describe, expect, it, vi } from "vitest";
import { getDashboardData } from "@/lib/api/work";
import { getJson } from "@/lib/api/client";

vi.mock("@/lib/api/client", () => ({
  getJson: vi.fn(),
  patchJson: vi.fn(),
  postJson: vi.fn(),
  readStoredSession: vi.fn(),
}));

const mockedGetJson = vi.mocked(getJson);

describe("getDashboardData", () => {
  beforeEach(() => {
    mockedGetJson.mockReset();
  });

  it("maps manager pattern and prioritized employee highlights", async () => {
    mockedGetJson
      .mockResolvedValueOnce({
        metrics: { engagement_score: 72, total_tickets: 18, open_tickets: 4, resolution_rate: 0.8 },
        sentiment: [{ date: "2026-04-01", positive: 60, neutral: 30, negative: 10 }],
        ai_summary: "Signals are trending better this week.",
        manager_pattern: { manager_id: "mgr-1", manager: "Asha", count: 5 },
        employees: [
          { employee_id: "e-1", name: "Riya", risk_score: 82, spike_alert: true, silent_risk: false, narrative: ["Risk rising"] },
          { employee_id: "e-2", name: "Aman", risk_score: 45, spike_alert: false, silent_risk: true, narrative: [] },
        ],
        sentiment_stale_days: 7,
        sustained_risk_window_days: 7,
        sustained_risk_min_negative_turns: 3,
        sentiment_source_drift: {
          window_days: 7,
          total: 2,
          by_source: { lexicon: 2 },
          pct_by_source: { lexicon: 100 },
        },
      } as never)
      .mockResolvedValueOnce([] as never)
      .mockResolvedValueOnce([{ id: "ins-1", title: "Alert", description: "Something changed", severity: "warning" }] as never)
      .mockResolvedValueOnce([] as never);

    const data = await getDashboardData();

    expect(data).not.toBeNull();
    expect(data?.managerPattern).toEqual({ manager_id: "mgr-1", manager: "Asha", count: 5 });
    expect(data?.employeeHighlights.map((h) => h.id)).toEqual(expect.arrayContaining(["e-1", "e-2"]));
    expect(data?.insights).toHaveLength(1);
    expect(data?.sentiment_source_drift?.total).toBe(2);
    expect(data?.sentiment_source_drift?.by_source.lexicon).toBe(2);
  });
});
