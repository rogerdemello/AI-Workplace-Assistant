import { cn } from "@/lib/utils";

interface SparkProps {
  data: { day?: string; value: number }[];
  className?: string;
  color?: string;
  fill?: boolean;
  height?: number;
}

export function Sparkline({ data, className, color = "hsl(var(--accent))", fill = true, height = 60 }: SparkProps) {
  if (!data.length) return null;
  const max = Math.max(...data.map(d => d.value));
  const min = Math.min(...data.map(d => d.value));
  const range = max - min || 1;
  const w = 100;
  const step = w / (data.length - 1 || 1);
  const points = data.map((d, i) => {
    const x = i * step;
    const y = 100 - ((d.value - min) / range) * 100;
    return [x, y] as const;
  });
  const path = points.map(([x, y], i) => `${i === 0 ? "M" : "L"}${x},${y}`).join(" ");
  const area = `${path} L${points[points.length - 1][0]},100 L0,100 Z`;
  return (
    <svg viewBox="0 0 100 100" preserveAspectRatio="none" className={cn("w-full", className)} style={{ height }}>
      {fill && <path d={area} fill={color} opacity="0.12" />}
      <path d={path} fill="none" stroke={color} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
      {points.map(([x, y], i) => (
        <circle key={i} cx={x} cy={y} r="0.8" fill={color} opacity={i === points.length - 1 ? 1 : 0} />
      ))}
    </svg>
  );
}

export function BarMini({ data, className, height = 60 }: SparkProps) {
  const max = Math.max(...data.map(d => d.value)) || 1;
  return (
    <div className={cn("flex items-end gap-1", className)} style={{ height }}>
      {data.map((d, i) => (
        <div key={i} className="flex-1 flex flex-col items-center gap-1">
          <div className="w-full rounded-sm bg-teal-grad" style={{ height: `${(d.value / max) * 100}%`, minHeight: 2 }} />
          {d.day && <span className="text-[9px] text-muted-foreground">{d.day}</span>}
        </div>
      ))}
    </div>
  );
}
