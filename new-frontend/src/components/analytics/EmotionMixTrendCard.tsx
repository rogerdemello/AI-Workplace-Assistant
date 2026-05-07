import { useMemo } from "react";
import { ChartContainer, ChartLegend, ChartLegendContent, ChartTooltip, ChartTooltipContent } from "@/components/chart";
import { CartesianGrid, Line, LineChart, XAxis } from "recharts";

export interface EmotionTrendPoint {
  date: string;
  emotions?: Record<string, number>;
  /** When variant is "sources", daily classifier-path percentages (llm, lexicon, …). */
  sources?: Record<string, number>;
}

const emotionColorByKey: Record<string, string> = {
  stress: "hsl(var(--danger))",
  frustration: "hsl(var(--warning))",
  anxiety: "hsl(var(--accent))",
};

const classifierSourceColorByKey: Record<string, string> = {
  llm: "hsl(var(--accent))",
  hybrid: "hsl(var(--warning))",
  lexicon: "hsl(var(--emerald))",
  provided: "hsl(var(--foreground))",
  unknown: "hsl(var(--muted-foreground))",
};

type Props = {
  points: EmotionTrendPoint[];
  eyebrow: string;
  title: string;
  emptyMessage?: string;
  /** "emotions" = wellbeing emotion mix; "sources" = LLM/lexicon/hybrid classifier mix. */
  variant?: "emotions" | "sources";
};

export function EmotionMixTrendCard({
  points,
  eyebrow,
  title,
  emptyMessage = "Emotion trend data is not available yet.",
  variant = "emotions",
}: Props) {
  const colorForKey = variant === "sources" ? classifierSourceColorByKey : emotionColorByKey;

  const bucketForPoint = (day: EmotionTrendPoint) =>
    variant === "sources" ? day.sources ?? {} : day.emotions ?? {};

  const topEmotionSummary = useMemo(() => {
    const counts = new Map<string, number>();
    points.forEach((day) => {
      Object.entries(bucketForPoint(day)).forEach(([emotion, pct]) => {
        counts.set(emotion, (counts.get(emotion) || 0) + Number(pct || 0));
      });
    });
    return [...counts.entries()]
      .sort((a, b) => b[1] - a[1])
      .slice(0, 3)
      .map(([emotion]) => emotion);
  }, [points, variant]);

  const emotionSeriesKeys = useMemo(() => topEmotionSummary.slice(0, 3), [topEmotionSummary]);

  const emotionSeriesData = useMemo(
    () =>
      points.map((point, index) => {
        const row: Record<string, string | number> = {
          day: String(index + 1),
        };
        const bucket = bucketForPoint(point);
        emotionSeriesKeys.forEach((emotion) => {
          row[emotion] = Number(bucket[emotion] ?? 0);
        });
        return row;
      }),
    [points, emotionSeriesKeys, variant],
  );

  const hasChart = emotionSeriesData.length > 0 && emotionSeriesKeys.length > 0;

  return (
    <div className="rounded-2xl border border-border bg-card p-6">
      <div className="flex items-center justify-between mb-4">
        <div>
          <div className="text-xs uppercase tracking-[0.18em] text-muted-foreground">{eyebrow}</div>
          <div className="font-medium mt-1">{title}</div>
        </div>
      </div>
      {hasChart ? (
        <>
          <ChartContainer
            className="h-[180px] w-full"
            config={emotionSeriesKeys.reduce(
              (acc, key) => ({
                ...acc,
                [key]: {
                  label: key.replace(/_/g, " "),
                  color: colorForKey[key] || "hsl(var(--foreground))",
                },
              }),
              {} as Record<string, { label: string; color: string }>,
            )}
          >
            <LineChart data={emotionSeriesData} margin={{ left: 8, right: 8, top: 8, bottom: 8 }}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} />
              <XAxis dataKey="day" tickLine={false} axisLine={false} />
              <ChartTooltip content={<ChartTooltipContent indicator="line" />} />
              <ChartLegend content={<ChartLegendContent />} />
              {emotionSeriesKeys.map((key) => (
                <Line
                  key={key}
                  type="monotone"
                  dataKey={key}
                  stroke={colorForKey[key] || "hsl(var(--foreground))"}
                  strokeWidth={2}
                  dot={false}
                />
              ))}
            </LineChart>
          </ChartContainer>
          <div className="mt-3 flex flex-wrap gap-2">
            {topEmotionSummary.map((emotion) => (
              <span
                key={emotion}
                className="text-[11px] px-2 py-1 rounded-md border border-border bg-secondary text-foreground"
              >
                {emotion.replace(/_/g, " ")}
              </span>
            ))}
          </div>
        </>
      ) : (
        <p className="text-sm text-muted-foreground">{emptyMessage}</p>
      )}
    </div>
  );
}
