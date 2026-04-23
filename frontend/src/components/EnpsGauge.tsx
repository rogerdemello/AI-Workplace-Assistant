"use client";

/**
 * EnpsGauge — SVG arc gauge visualising eNPS from -100 to +100.
 * Transitions through red → amber → green.
 */

interface EnpsGaugeProps {
  enps: number;
  size?: number;
}

function scoreToColor(score: number): string {
  if (score >= 30) return "#10b981";   // green
  if (score >= 0)  return "#f59e0b";   // amber
  return "#ef4444";                    // red
}

function scoreToLabel(score: number): string {
  if (score >= 50) return "Excellent";
  if (score >= 30) return "Good";
  if (score >= 10) return "Neutral";
  if (score >= -10) return "Passive";
  return "At Risk";
}

export function EnpsGauge({ enps, size = 160 }: EnpsGaugeProps) {
  const clampedScore = Math.max(-100, Math.min(100, enps));
  const center = size / 2;
  const radius = (size * 0.38);
  const strokeWidth = size * 0.09;

  // Arc from 210° to 330° (240° sweep = -120 to +120 deg relative to bottom)
  const startAngleDeg = 210;
  const sweepDeg = 120; // half is 120 each side
  const totalArcDeg = 240;

  function polarToXY(angleDeg: number, r: number) {
    const rad = (angleDeg * Math.PI) / 180;
    return {
      x: center + r * Math.cos(rad),
      y: center + r * Math.sin(rad),
    };
  }

  function arcPath(startDeg: number, endDeg: number, r: number, cw: boolean) {
    const s = polarToXY(startDeg, r);
    const e = polarToXY(endDeg, r);
    const large = Math.abs(endDeg - startDeg) > 180 ? 1 : 0;
    const sweep = cw ? 1 : 0;
    return `M ${s.x} ${s.y} A ${r} ${r} 0 ${large} ${sweep} ${e.x} ${e.y}`;
  }

  // Needle angle: map [-100, 100] to [210°, 210° + 240°] = [210°, 450°]
  const needleAngle = startAngleDeg + ((clampedScore + 100) / 200) * totalArcDeg;
  const needleEnd = polarToXY(needleAngle, radius * 0.72);

  const trackPath = arcPath(startAngleDeg, startAngleDeg + totalArcDeg, radius, true);
  const fillEnd = startAngleDeg + ((clampedScore + 100) / 200) * totalArcDeg;
  const fillPath = arcPath(startAngleDeg, fillEnd, radius, true);

  const color = scoreToColor(clampedScore);
  const label = scoreToLabel(clampedScore);

  return (
    <div className="flex flex-col items-center gap-2">
      <svg width={size} height={size * 0.72} viewBox={`0 0 ${size} ${size}`} overflow="visible">
        {/* Track */}
        <path
          d={trackPath}
          fill="none"
          stroke="#e2e8f0"
          strokeWidth={strokeWidth}
          strokeLinecap="round"
        />
        {/* Filled portion */}
        <path
          d={fillPath}
          fill="none"
          stroke={color}
          strokeWidth={strokeWidth}
          strokeLinecap="round"
          style={{ transition: "stroke 0.5s, d 0.6s" }}
        />
        {/* Needle */}
        <line
          x1={center}
          y1={center}
          x2={needleEnd.x}
          y2={needleEnd.y}
          stroke={color}
          strokeWidth={strokeWidth * 0.28}
          strokeLinecap="round"
          style={{ transition: "all 0.6s cubic-bezier(0.22,1,0.36,1)" }}
        />
        {/* Centre hub */}
        <circle cx={center} cy={center} r={strokeWidth * 0.38} fill={color} />
        {/* Score label */}
        <text
          x={center}
          y={center + radius * 0.28}
          textAnchor="middle"
          fontSize={size * 0.17}
          fontWeight="700"
          fill="#0f172a"
          fontFamily="Inter, system-ui, sans-serif"
        >
          {clampedScore > 0 ? `+${clampedScore}` : clampedScore}
        </text>
        {/* "eNPS" sub-label */}
        <text
          x={center}
          y={center + radius * 0.52}
          textAnchor="middle"
          fontSize={size * 0.085}
          fill="#94a3b8"
          fontFamily="Inter, system-ui, sans-serif"
        >
          eNPS
        </text>
      </svg>

      <span
        className="text-xs font-semibold uppercase tracking-widest px-3 py-1 rounded-full"
        style={{
          background: `${color}1a`,
          color: color,
        }}
      >
        {label}
      </span>
    </div>
  );
}
