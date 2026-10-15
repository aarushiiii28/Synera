import type { NullCal } from '../../lib/api';
import { fix, int, pct } from '../../lib/format';
import { CAL_TONE, CAL_WORD, calClass } from './benchLogic';
import { useChartWidth } from './useChartWidth';

/** p-value histogram under the null. Flat (every bar at the dashed line) is honest; a pile on the left is over-confidence. */
export function BenchHist({ title, d }: { title: string; d: NullCal }) {
  const [ref, w] = useChartWidth(240);
  const h = 130, m = { l: 4, r: 4, t: 14, b: 22 };
  const bins = d.p_histogram_10bins;
  const total = bins.reduce((a, b) => a + b, 0);
  const max = Math.max(1, ...bins), expected = total / bins.length;
  const bw = (w - m.l - m.r) / bins.length;
  const sy = (v: number) => h - m.b - (v / max) * (h - m.b - m.t);
  const c = calClass(d.lambda_median), tone = CAL_TONE[c];
  return (
    <figure className="m-0" ref={ref}>
      <figcaption className="flex items-baseline justify-between gap-2 mb-1">
        <span className="display font-semibold text-[14px]">{title}</span>
        <span className="num text-[12px]" style={{ color: tone }}>λ {fix(d.lambda_median, 2)} · {CAL_WORD[c]}</span>
      </figcaption>
      <svg width={w} height={h} role="img" aria-label={`${title} null p-value histogram, 10 bins, ${int(total)} p-values. ${pct(d.frac_p_lt_05_pooled, 1)} fall below 0.05.`}>
        {bins.map((v, i) => (
          <rect key={i} x={m.l + i * bw + 1} width={Math.max(bw - 2, 1)} y={sy(v)} height={h - m.b - sy(v)} fill={i === 0 ? tone : 'var(--signal)'} opacity={i === 0 ? 0.95 : 0.45} />
        ))}
        <line x1={m.l} x2={w - m.r} y1={sy(expected)} y2={sy(expected)} stroke="var(--biosphere)" strokeDasharray="4 3" />
        <line x1={m.l} x2={w - m.r} y1={h - m.b + 0.5} y2={h - m.b + 0.5} stroke="var(--line-strong)" />
        <text x={m.l} y={h - 6} className="num" fontSize="10" fill="var(--faint)">p = 0</text>
        <text x={w - m.r} y={h - 6} textAnchor="end" className="num" fontSize="10" fill="var(--faint)">p = 1</text>
        <text x={w - m.r} y={sy(expected) - 4} textAnchor="end" className="num" fontSize="10" fill="var(--biosphere)">flat = honest</text>
      </svg>
      <div className="num text-[12px] text-muted">p &lt; 0.05: <span style={{ color: tone }}>{pct(d.frac_p_lt_05_pooled, 1)}</span> <span className="text-faint">(honest = 5.0%)</span></div>
    </figure>
  );
}
