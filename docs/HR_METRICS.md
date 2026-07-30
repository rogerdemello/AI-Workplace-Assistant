# MARK — What the HR numbers mean

For HR and People Ops. Every definition here is taken from the code that
produces it, not from intent. Where a number is softer than it looks, it says
so — these figures affect how people are treated, so knowing their limits
matters more than knowing their value.

Sources: `app/services/sentiment_pipeline.py`, `app/services/dashboard_analytics.py`.

---

## The one-paragraph version

An employee chats with MARK. Each of their messages is scored for sentiment
(0–100). Those per-message scores are rolled up per employee into a **sentiment
score**, a **trend**, and a **risk score**. Everything on the Pulse and
Employees screens derives from those three.

---

## Sentiment score (0–100)

Higher is better. 50 is neutral, and also the default when someone has no
history — **a new joiner reads 50 because we know nothing about them, not
because they feel neutral.**

Computed as:

1. `avg7` — mean of this employee's message scores over the last 7 days
2. `avg30` — the same over 30 days
3. Blend: `0.7 × avg7 + 0.3 × avg30` — recent messages dominate
4. Optionally blended again with the last N messages
   (`SENTIMENT_ROLLING_TURNS`, weight `SENTIMENT_ROLLING_BLEND_WEIGHT`)
5. **Smoothing guardrail**: the stored score moves at most **10 points** per
   recalculation

### What the guardrail means for you

A score cannot jump. If someone has a genuinely terrible week, the number walks
toward it over several updates rather than dropping in one step. This is
deliberate — it stops one angry message defining a person — but it means **the
score lags reality on the way down**. If an employee tells you something
serious, believe them over the number.

## Trend (up / stable / down)

Compares the current score against the average of the **7 days before last
week**. `up` at +5 or more, `down` at −5 or less, `stable` between.

Because it is a week-over-week comparison, a quiet week produces a misleading
trend: fewer messages means the average is drawn from a smaller sample.

## Risk score (0–100)

Higher means more attention warranted. A weighted sum:

| Component | Weight | Meaning |
|---|---|---|
| `100 − sentiment score` | 40% | How negative they have been |
| Inactivity | 20% | Days since their last message, ÷10, capped at 100 |
| Complaint frequency | 20% | Signals tagged manager_issue / workload / salary / recognition in 7 days, ÷5 |
| Trend drop | 20% | Size of a downward move, ×4 |

### Read inactivity carefully

Silence contributes 20% of risk, and someone who has not written in 10+ days
scores the maximum on it. **Silence is not distress.** A person on holiday, on
leave, or simply busy will accrue risk for saying nothing.

You do not have to guess which it is. The Employees list shows the top drivers
under each risk score — "Inactivity (20 pts)", "Negative sentiment (24 pts)" —
so a score carried by silence is visible at a glance. The API returns the full
breakdown as `risk_factors`: each component in points, the raw evidence behind
it (days since last message, complaint signals, trend delta), and how many
messages it rests on.

### "thin data"

A score computed from fewer than 5 messages in 30 days is tagged **thin data**
in the list and `low_confidence` in the API. Treat those as a prompt to talk to
the person, never as a finding. Scores stabilise around 20+ messages.

## Top emotion

The most frequent emotion label across recent messages. Indicative only: it is
derived from keyword and model classification of short chat turns, and a single
vivid message can dominate a light week.

---

## Honest limits

- **Not a performance measure.** These scores describe how someone has been
  writing to a chatbot. They are not productivity, capability, or commitment,
  and must never be used in appraisal, pay, or disciplinary decisions.
- **Not clinical.** "Burnout" and "mental health" labels are keyword-and-model
  heuristics over chat text. They are prompts to check in with a person, never
  a diagnosis.
- **Volume-sensitive.** All averages are unweighted, so someone who sends 3
  messages and someone who sends 300 are scored on the same scale. The
  difference is now visible — `risk_confidence`, `risk_calibration_band` and
  the "thin data" tag — but the score itself is not adjusted for it.
- **English-tuned.** The lexicon and prompts are English. Sentiment for
  employees writing in other languages, or heavy code-switching, is less
  reliable. See task.txt for the multilingual work.

## If a number looks wrong

It might be. Open the employee's profile and check which component drives the
risk score before acting. If sentiment disagrees with what someone has actually
told you, the person is the better source — and `/metrics` will show whether
the sentiment pipeline has been failing (`sentiment_pipeline_failures_total`),
which would leave scores stale rather than wrong.
