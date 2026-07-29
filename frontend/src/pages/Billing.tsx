import { useEffect, useState } from "react";
import { AppLayout } from "@/components/layout/AppLayout";
import { getBillingSubscription, type SubscriptionSummary } from "@/lib/services";
import { CreditCard, Users } from "lucide-react";

export default function Billing() {
  const [sub, setSub] = useState<SubscriptionSummary | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getBillingSubscription().then((row) => {
      setSub(row);
      setLoading(false);
    });
  }, []);

  return (
    <AppLayout
      title="Billing"
      subtitle={
        sub?.source === "stripe"
          ? "Subscription overview — live from Stripe"
          : "Subscription overview — set STRIPE_API_KEY for live data"
      }
    >
      <div className="px-6 lg:px-10 py-8 max-w-3xl space-y-6">
        {loading && <p className="text-sm text-muted-foreground">Loading…</p>}
        {!loading && !sub && (
          <p className="text-sm text-muted-foreground">Billing data is unavailable. Check that you are signed in as HR and the API is reachable.</p>
        )}
        {!loading && sub && (
          <>
            <div className="rounded-2xl border border-border bg-card p-6 flex items-start gap-4">
              <div className="size-12 rounded-xl bg-teal-soft text-accent grid place-items-center shrink-0">
                <CreditCard className="size-6" />
              </div>
              <div>
                <div className="text-xs uppercase tracking-[0.18em] text-muted-foreground">Current plan</div>
                <h2 className="font-display text-2xl mt-1">{sub.planName}</h2>
                <p className="text-sm text-muted-foreground mt-1 capitalize">
                  {sub.planTier} · {sub.billingCycle} billing
                </p>
              </div>
            </div>

            <div className="grid sm:grid-cols-2 gap-4">
              <div className="rounded-2xl border border-border bg-card p-5">
                <div className="flex items-center gap-2 text-xs text-muted-foreground uppercase tracking-[0.12em]">
                  <Users className="size-3.5" /> Seats
                </div>
                <div className="font-display text-3xl mt-2">
                  {sub.seatsUsed}
                  <span className="text-lg text-muted-foreground font-sans font-normal"> / {sub.seatLimit}</span>
                </div>
              </div>
              <div className="rounded-2xl border border-border bg-card p-5">
                <div className="text-xs text-muted-foreground uppercase tracking-[0.12em]">Renews on</div>
                <div className="font-display text-2xl mt-2">{sub.renewsOn}</div>
                <div className="text-xs text-muted-foreground mt-2">
                  Est. {sub.currency} {sub.monthlyEstimate.toFixed(2)} / month{sub.source === "stripe" ? "" : " (demo)"}
                </div>
              </div>
            </div>

            <div className="rounded-2xl border border-border bg-card p-6">
              <div className="text-xs uppercase tracking-[0.18em] text-muted-foreground mb-4">Included</div>
              <ul className="space-y-2 text-sm">
                {sub.features.map((f) => (
                  <li key={f} className="flex items-center gap-2">
                    <span className="size-1.5 rounded-full bg-accent shrink-0" />
                    {f}
                  </li>
                ))}
              </ul>
            </div>
          </>
        )}
      </div>
    </AppLayout>
  );
}
