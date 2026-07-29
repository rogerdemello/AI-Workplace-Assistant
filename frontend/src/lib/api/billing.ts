import { getJson } from "@/lib/api/client";

export interface SubscriptionSummary {
  planName: string;
  planTier: string;
  billingCycle: string;
  seatLimit: number;
  seatsUsed: number;
  renewsOn: string;
  currency: string;
  monthlyEstimate: number;
  features: string[];
  source: "stripe" | "config";
}

export async function getBillingSubscription(): Promise<SubscriptionSummary | null> {
  const row = await getJson<Record<string, unknown>>("/api/v1/billing/subscription");
  if (!row) return null;
  return {
    planName: String(row.plan_name ?? ""),
    planTier: String(row.plan_tier ?? ""),
    billingCycle: String(row.billing_cycle ?? ""),
    seatLimit: Number(row.seat_limit ?? 0),
    seatsUsed: Number(row.seats_used ?? 0),
    renewsOn: String(row.renews_on ?? ""),
    currency: String(row.currency ?? "USD"),
    monthlyEstimate: Number(row.monthly_estimate ?? 0),
    features: Array.isArray(row.features) ? row.features.map(String) : [],
    source: row.source === "stripe" ? "stripe" : "config",
  };
}
