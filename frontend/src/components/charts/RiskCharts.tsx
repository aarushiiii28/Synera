import { arc, area, extent, line, scaleLinear } from 'd3';
import type { RiskDay } from '../../lib/api';
import { fix } from '../../lib/format';
import { dayHasData, dayName, percentileText, sd, tierColor, tierLabel } from './riskLogic';
import { useChartWidth } from './useChartWidth';

/** Percentile gauge: filled arc up to today's percentile within the region's own history. */
export function RiskGauge({ percentile, tier }: { percentile: number; tier: string }) {
  const size = 220, r = 92, cx = size / 2, cy = 112;
  const a = (p: number) => -Math.PI / 2 + p * Math.PI;
  const bg = arc()({ innerRadius: r - 10, outerRadius: r, startAngle: -Math.PI / 2, endAngle: Math.PI / 2 }) ?? '';
  const fg = arc()({ innerRadius: r - 10, outerRadius: r, startAngle: -Math.PI / 2, endAngle: a(Math.max(0, Math.min(1, percentile))) }) ?? '';
  const tone = tierColor(tier);
  const nx = cx + Math.sin(a(percentile)) * (r + 12), ny = cy - Math.cos(a(percentile)) * (r + 12);
  return (
    <svg viewBox={`0 0 ${size} 140`} className="w-full max-w-[260px]" role="img" aria-label={`Percentile gauge: ${percentileText(percentile)} percentile of ${fix(percentile * 100, 0)} out of 100`}>
      <g transform={`translate(${cx} ${cy})`}>
        <path d={bg} fill="var(--hull-2)" opacity="0.6" />
        <path d={fg} fill={tone} />
        {[0, 0.25, 0.5, 0.75, 1].map((p) => {
          const x1 = Math.sin(a(p)) * (r + 2), y1 = -Math.cos(a(p)) * (r + 2), x2 = Math.sin(a(p)) * (r + 7), y2 = -Math.cos(a(p)) * (r + 7);
          return <line key={p} x1={x1} y1={y1} x2={x2} y2={y2} stroke="var(--line-strong)" />;
        })}
        <text x={-r + 5} y={22} textAnchor="middle" className="num" fontSize="10" fill="var(--faint)">0</text>
        <text x={r - 5} y={22} textAnchor="middle" className="num" fontSize="10" fill="var(--faint)">100</text>
        <text x="0" y="-12" textAnchor="middle" className="num" fontSize="34" fill={tone}>{fix(percentile * 100, 0)}</text>
        <text x="0" y="10" textAnchor="middle" className="num" fontSize="10" fill="var(--muted)" letterSpacing="1.5">PERCENTILE</text>
      </g>
      <circle cx={nx} cy={ny} r="3" fill={tone} />
    </svg>
  );
}

/** Uplift with its uncertainty band drawn as an interval on a zero-centred axis. */
export function RiskInterval({ value, lower, upper, units }: { value: number; lower: number; upper: number; units?: string }) {
  const [ref, w] = useChartWidth(360);
  const h = 82, m = 16;
  const span = Math.max(Math.abs(lower), Math.abs(upper), Math.abs(value), 1e-9);
  const x = scaleLinear().domain([-span * 1.25, span * 1.25]).range([m, w - m]);
  const tone = value >= 0 ? 'var(--solar)' : 'var(--signal)';
  const ticks = x.ticks(4);
  return (
    <div ref={ref} className="w-full">
      <svg width={w} height={h} role="img" aria-label={`Interaction uplift ${sd(value)} ${units ?? ''}, plausible range ${sd(lower)} to ${sd(upper)}`}>
        {ticks.map((t) => (
          <g key={t}>
            <line x1={x(t)} x2={x(t)} y1="36" y2="42" stroke="var(--line-strong)" />
            <text x={x(t)} y="56" textAnchor="middle" className="num" fontSize="10" fill="var(--faint)">{t}</text>
          </g>
        ))}
        <line x1={m} x2={w - m} y1="39" y2="39" stroke="var(--line)" />
        <line x1={x(0)} x2={x(0)} y1="8" y2="48" stroke="var(--muted)" strokeDasharray="2 3" />
        <text x={x(0)} y="6" textAnchor="middle" className="num" fontSize="10" fill="var(--muted)">0 = no interaction</text>
        <rect x={x(Math.min(lower, upper))} width={Math.max(2, Math.abs(x(upper) - x(lower)))} y="30" height="18" fill={tone} opacity="0.28" />
        <line x1={x(lower)} x2={x(lower)} y1="26" y2="52" stroke={tone} strokeWidth="2" />
        <line x1={x(upper)} x2={x(upper)} y1="26" y2="52" stroke={tone} strokeWidth="2" />
        <circle cx={x(value)} cy="39" r="6" fill="var(--void)" stroke={tone} strokeWidth="2.5" />
        <text x={x(lower)} y="76" textAnchor="middle" className="num" fontSize="11" fill={tone}>{sd(lower)}</text>
        <text x={x(upper)} y="76" textAnchor="middle" className="num" fontSize="11" fill={tone}>{sd(upper)}</text>
      </svg>
    </div>
  );
}

/** 7-day chart: additive expectation vs modelled response, uplift shaded, and a chip per day. */
export function RiskForecast({ days }: { days: RiskDay[] }) {
  const [ref, w] = useChartWidth(640);
  const h = 230, m = { t: 14, b: 22 };
  const n = days.length;
  const colW = w / n;
  const cxs = (i: number) => colW * (i + 0.5);
  const [lo, hi] = (extent(days.flatMap((d) => [d.additive, d.modelled]).filter((v) => typeof v === 'number' && Number.isFinite(v))) as [number, number]);
  const pad = Math.max((hi - lo) * 0.15, 1e-6);
  const y = scaleLinear().domain([lo - pad, hi + pad]).range([h - m.b, m.t]);
  const ok = (v: number | null | undefined) => typeof v === 'number' && Number.isFinite(v);
  const ln = (k: 'additive' | 'modelled') => line<RiskDay>().defined((d) => ok(d[k])).x((_, i) => cxs(i)).y((d) => y(d[k]))(days) ?? '';
  const ar = area<RiskDay>().defined((d) => ok(d.additive) && ok(d.modelled)).x((_, i) => cxs(i)).y0((d) => y(d.additive)).y1((d) => y(d.modelled))(days) ?? '';
  return (
    <div ref={ref} className="w-full">
      <svg width={w} height={h} role="img" aria-label={`Seven-day forecast of additive and modelled outcome. ${days.map((d) => `${dayName(d.date)}: additive ${fix(d.additive, 2)}, modelled ${fix(d.modelled, 2)}, uplift ${sd(d.uplift)}`).join('. ')}`}>
        {y.ticks(4).map((t) => (
          <g key={t}>
            <line x1="0" x2={w} y1={y(t)} y2={y(t)} stroke="var(--line)" />
            <text x="2" y={y(t) - 4} className="num" fontSize="10" fill="var(--faint)">{t}</text>
          </g>
        ))}
        <path d={ar} fill="var(--solar)" opacity="0.22" />
        <path d={ln('additive')} fill="none" stroke="var(--signal)" strokeWidth="2" strokeDasharray="6 4" />
        <path d={ln('modelled')} fill="none" stroke="var(--sun)" strokeWidth="2.4" />
        {days.map((d, i) => (
          <g key={d.date}>
            <circle cx={cxs(i)} cy={y(d.additive)} r="3" fill="var(--void)" stroke="var(--signal)" strokeWidth="1.6" />
            <circle cx={cxs(i)} cy={y(d.modelled)} r="3.4" fill="var(--sun)" />
            <line x1={cxs(i)} x2={cxs(i)} y1={y(d.additive)} y2={y(d.modelled)} stroke="var(--solar)" strokeWidth="1" opacity="0.6" />
          </g>
        ))}
        <text x={w - 2} y={h - 6} textAnchor="end" className="num" fontSize="10" fill="var(--faint)">outcome SD (model units)</text>
      </svg>
      <ul className="m-0 mb-3 p-0 list-none flex flex-wrap gap-x-6 gap-y-1 text-[12px] text-muted">
        <li className="flex items-center gap-2"><svg width="24" height="8" aria-hidden><line x1="0" x2="24" y1="4" y2="4" stroke="var(--signal)" strokeWidth="2" strokeDasharray="6 4" /></svg>Additive: each stressor acting alone</li>
        <li className="flex items-center gap-2"><svg width="24" height="8" aria-hidden><line x1="0" x2="24" y1="4" y2="4" stroke="var(--sun)" strokeWidth="2.4" /></svg>Modelled: with the interactions</li>
        <li className="flex items-center gap-2"><span className="w-3 h-3 inline-block" style={{ background: 'var(--solar)', opacity: 0.4 }} aria-hidden />Shaded gap = interaction uplift</li>
      </ul>
      <ol className="m-0 p-0 list-none grid" style={{ gridTemplateColumns: `repeat(${n}, minmax(0, 1fr))` }}>
        {days.map((d) => {
          const c = tierColor(d.tier);
          return (
            <li key={d.date} className="text-center border-t px-0.5 pt-2" style={{ borderColor: c }}>
              <div className="num text-[10px] md:text-[11px] text-faint leading-tight">{dayName(d.date)}</div>
              <div className="num text-[10px] md:text-[11px] tracking-[0.04em] md:tracking-[0.1em] mt-1 break-words" style={{ color: c }}>
                {dayHasData(d) ? tierLabel(d.tier) : 'no data'}
              </div>
              <div className="num text-[10px] md:text-[11px] text-muted">{d.percentile === null ? '—' : percentileText(d.percentile)}</div>
              <div className="num text-[10px] md:text-[11px] text-faint">{sd(d.uplift, 2)}</div>
            </li>
          );
        })}
      </ol>
    </div>
  );
}
