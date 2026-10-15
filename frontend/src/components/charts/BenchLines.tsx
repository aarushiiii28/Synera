import { area, line, scaleLinear } from 'd3';
import { useChartWidth } from './useChartWidth';

export interface LinePoint { x: number; y: number | null; lo?: number; hi?: number }
export interface LineSeries { key: string; label: string; color: string; dash?: string; points: LinePoint[] }

/** Generic line chart with optional 95% bands. A null y breaks the line (not computed), it is never drawn as zero. */
export function BenchLines({ series, xLabel, yLabel, yMax = 1, target: refLine, xFmt = (v: number) => String(v), yFmt = (v: number) => `${Math.round(v * 100)}%`, height = 240, ariaLabel }: {
  series: LineSeries[]; xLabel: string; yLabel: string; yMax?: number; target?: { y: number; label: string };
  xFmt?: (v: number) => string; yFmt?: (v: number) => string; height?: number; ariaLabel: string;
}) {
  const [cref, w] = useChartWidth(520);
  const m = { t: 14, r: 14, b: 42, l: 44 };
  const xs = [...new Set(series.flatMap((s) => s.points.map((p) => p.x)))].sort((a, b) => a - b);
  const x = scaleLinear().domain([xs[0], xs[xs.length - 1]]).range([m.l, w - m.r]);
  const y = scaleLinear().domain([0, yMax]).range([height - m.b, m.t]);
  const yt = y.ticks(5);
  return (
    <div ref={cref} className="w-full">
      <svg width={w} height={height} role="img" aria-label={ariaLabel}>
        {yt.map((t) => (
          <g key={t}>
            <line x1={m.l} x2={w - m.r} y1={y(t)} y2={y(t)} stroke="var(--line)" />
            <text x={m.l - 8} y={y(t) + 4} textAnchor="end" className="num" fontSize="11" fill="var(--faint)">{yFmt(t)}</text>
          </g>
        ))}
        {xs.map((t) => (
          <g key={t}>
            <line x1={x(t)} x2={x(t)} y1={height - m.b} y2={height - m.b + 4} stroke="var(--line-strong)" />
            <text x={x(t)} y={height - m.b + 17} textAnchor="middle" className="num" fontSize="11" fill="var(--faint)">{xFmt(t)}</text>
          </g>
        ))}
        <text x={(m.l + w - m.r) / 2} y={height - 6} textAnchor="middle" fontSize="11" fill="var(--muted)">{xLabel}</text>
        <text transform={`translate(11 ${(m.t + height - m.b) / 2}) rotate(-90)`} textAnchor="middle" fontSize="11" fill="var(--muted)">{yLabel}</text>
        {refLine && (
          <g>
            <line x1={m.l} x2={w - m.r} y1={y(refLine.y)} y2={y(refLine.y)} stroke="var(--biosphere)" strokeDasharray="4 4" opacity="0.8" />
            <text x={w - m.r - 2} y={y(refLine.y) - 5} textAnchor="end" className="num" fontSize="10" fill="var(--biosphere)">{refLine.label}</text>
          </g>
        )}
        {series.map((s) => {
          const ok = s.points.filter((p) => p.y !== null);
          const band = ok.filter((p) => p.lo !== undefined && p.hi !== undefined);
          const ln = line<LinePoint>().defined((p) => p.y !== null).x((p) => x(p.x)).y((p) => y(p.y as number));
          const ar = area<LinePoint>().defined((p) => p.lo !== undefined && p.hi !== undefined).x((p) => x(p.x)).y0((p) => y(p.lo as number)).y1((p) => y(p.hi as number));
          return (
            <g key={s.key}>
              {band.length > 1 && <path d={ar(s.points) ?? ''} fill={s.color} opacity="0.14" />}
              <path d={ln(s.points) ?? ''} fill="none" stroke={s.color} strokeWidth="2" strokeDasharray={s.dash} />
              {ok.map((p) => <circle key={p.x} cx={x(p.x)} cy={y(p.y as number)} r="3.2" fill="var(--void)" stroke={s.color} strokeWidth="1.8" />)}
            </g>
          );
        })}
      </svg>
      <ul className="m-0 mt-1 p-0 list-none flex flex-wrap gap-x-5 gap-y-1">
        {series.map((s) => (
          <li key={s.key} className="flex items-center gap-2 text-[12px] text-muted">
            <svg width="22" height="8" aria-hidden><line x1="0" x2="22" y1="4" y2="4" stroke={s.color} strokeWidth="2" strokeDasharray={s.dash} /></svg>{s.label}
          </li>
        ))}
      </ul>
    </div>
  );
}

