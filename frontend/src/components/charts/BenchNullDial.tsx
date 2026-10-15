import { scaleLog } from 'd3';
import type { NullCal } from '../../lib/api';
import { fix } from '../../lib/format';
import { CAL_TONE, CAL_WORD, calClass } from './benchLogic';
import { useChartWidth } from './useChartWidth';

const ROWS: { k: 'naive' | 'hac' | 'boot'; name: string }[] = [
  { k: 'naive', name: 'Naive test' },
  { k: 'hac', name: 'HAC test (autocorrelation-robust)' },
  { k: 'boot', name: 'Block-bootstrap test' },
];

/** Log-scale lambda dial: one bar per method, median dot, simulation range, and the honest target at 1.0. */
export function BenchNullDial({ nc }: { nc: { naive: NullCal; hac: NullCal; boot: NullCal } }) {
  const [ref, w] = useChartWidth(520);
  const lows = ROWS.map((r) => nc[r.k].lambda_range[0]);
  const highs = ROWS.map((r) => nc[r.k].lambda_range[1]);
  const lo = Math.min(0.5, ...lows) * 0.85, hi = Math.max(2, ...highs) * 1.2;
  const padL = 8, padR = 12;
  const x = scaleLog().domain([lo, hi]).range([padL, w - padR]);
  const rowH = 74, top = 26, H = top + rowH * ROWS.length + 28;
  const ticks = [0.25, 0.5, 1, 2, 4, 8, 16, 32, 64, 128].filter((t) => t >= lo && t <= hi);
  return (
    <div ref={ref} className="w-full">
      <svg width={w} height={H} role="img" aria-label={`Null calibration on a log scale. ${ROWS.map((r) => `${r.name}: median lambda ${fix(nc[r.k].lambda_median, 2)}, range ${fix(nc[r.k].lambda_range[0], 2)} to ${fix(nc[r.k].lambda_range[1], 2)}`).join('. ')}. Honest target is 1.0.`}>
        <defs>
          <linearGradient id="nd-target" x1="0" x2="0" y1="0" y2="1">
            <stop offset="0" stopColor="var(--biosphere)" stopOpacity="0.9" /><stop offset="1" stopColor="var(--biosphere)" stopOpacity="0.25" />
          </linearGradient>
        </defs>
        {/* target band: honest zone 0.8 - 1.25 */}
        <rect x={x(0.8)} width={x(1.25) - x(0.8)} y={top - 8} height={rowH * ROWS.length + 8} fill="var(--biosphere)" opacity="0.07" />
        <line x1={x(1)} x2={x(1)} y1={top - 12} y2={top + rowH * ROWS.length} stroke="url(#nd-target)" strokeWidth="1.5" strokeDasharray="3 3" />
        <text x={x(1)} y={top - 15} textAnchor="middle" className="num" fontSize="11" fill="var(--biosphere)">TARGET 1.0 = HONEST</text>
        {ROWS.map((r, i) => {
          const d = nc[r.k], y = top + i * rowH + 36, c = calClass(d.lambda_median), tone = CAL_TONE[c];
          const xm = x(d.lambda_median);
          const labelRight = xm < w * 0.55;
          return (
            <g key={r.k}>
              <text x={padL} y={y - 22} fontSize="13" fill="var(--text)">{r.name}</text>
              <line x1={padL} x2={w - padR} y1={y} y2={y} stroke="var(--line)" />
              <line x1={x(d.lambda_range[0])} x2={x(d.lambda_range[1])} y1={y} y2={y} stroke={tone} strokeWidth="5" opacity="0.4" strokeLinecap="butt" />
              <line x1={x(d.lambda_range[0])} x2={x(d.lambda_range[0])} y1={y - 6} y2={y + 6} stroke={tone} />
              <line x1={x(d.lambda_range[1])} x2={x(d.lambda_range[1])} y1={y - 6} y2={y + 6} stroke={tone} />
              <circle cx={xm} cy={y} r="7" fill="var(--void)" stroke={tone} strokeWidth="2.5" />
              <text x={labelRight ? xm + 14 : xm - 14} y={y + 5} textAnchor={labelRight ? 'start' : 'end'} className="num" fontSize="16" fill={tone} stroke="var(--void)" strokeWidth="5" paintOrder="stroke">
                λ {fix(d.lambda_median, 2)}
              </text>
              <text x={w - padR} y={y - 22} textAnchor="end" className="num" fontSize="11" fill={tone}>{CAL_WORD[c].toUpperCase()}</text>
              <text x={x(d.lambda_range[1])} y={y + 22} textAnchor="end" className="num" fontSize="10" fill="var(--faint)">
                range {fix(d.lambda_range[0], 2)} – {fix(d.lambda_range[1], 2)}
              </text>
            </g>
          );
        })}
        <g transform={`translate(0 ${top + rowH * ROWS.length + 6})`}>
          {ticks.map((t) => (
            <g key={t}>
              <line x1={x(t)} x2={x(t)} y1="0" y2="5" stroke="var(--line-strong)" />
              <text x={x(t)} y="18" textAnchor="middle" className="num" fontSize="10" fill="var(--faint)">{t}</text>
            </g>
          ))}
          <text x={w - padR} y="18" textAnchor="end" className="num" fontSize="10" fill="var(--faint)" />
        </g>
      </svg>
      <div className="num text-[11px] text-faint">λ on a log scale. Left of 1: too cautious. Right of 1: too many false alarms. Bar = range across simulations, ring = median.</div>
    </div>
  );
}
