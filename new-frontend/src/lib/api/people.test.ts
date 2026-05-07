import { beforeEach, describe, expect, it, vi } from "vitest";
import { getEmployees, getUserDetail } from "@/lib/api/people";
import { getJson } from "@/lib/api/client";

vi.mock("@/lib/api/client", () => ({
  getJson: vi.fn(),
}));

const mockedGetJson = vi.mocked(getJson);

describe("people analytics mapping", () => {
  beforeEach(() => {
    mockedGetJson.mockReset();
  });

  it("merges analytics flags and narrative in getEmployees", async () => {
    mockedGetJson
      .mockResolvedValueOnce([
        { id: "u-1", role: "employee", name: "Nina Roy", department: "Product", designation: "Engineer", manager_id: "mgr-7" },
      ] as never)
      .mockResolvedValueOnce([
        {
          employee_id: "u-1",
          sentiment_score: 38,
          trend: "down",
          delta: -12,
          risk_score: 78,
          risk_label: "High",
          spike_alert: true,
          silent_risk: true,
          top_topic: "manager_issue",
          complaints_5d: 3,
          narrative: ["Drop in sentiment in 72h"],
        },
      ] as never);

    const rows = await getEmployees();
    expect(rows).toHaveLength(1);
    expect(rows[0]).toMatchObject({
      id: "u-1",
      managerId: "mgr-7",
      spikeAlert: true,
      silentRisk: true,
      topTopic: "manager_issue",
      complaints5d: 3,
      riskLabel: "High",
    });
    expect(rows[0].narrative).toEqual(["Drop in sentiment in 72h"]);
  });

  it("maps analytics narrative fields in getUserDetail", async () => {
    mockedGetJson
      .mockResolvedValueOnce({ id: "u-5", name: "Arjun", designation: "Analyst", department: "People Ops" } as never)
      .mockResolvedValueOnce({ confidence: 0.77, calibration_band: "good", factors: [] } as never)
      .mockResolvedValueOnce([
        {
          employee_id: "u-5",
          sentiment_score: 44,
          risk_score: 69,
          risk_label: "Medium",
          narrative: ["Complaints climbed this week"],
          spike_alert: false,
          silent_risk: true,
          top_topic: "workload",
        },
      ] as never);

    const detail = await getUserDetail("u-5");

    expect(detail).not.toBeNull();
    expect(detail?.narrative).toEqual(["Complaints climbed this week"]);
    expect(detail?.silentRisk).toBe(true);
    expect(detail?.topTopic).toBe("workload");
  });
});
