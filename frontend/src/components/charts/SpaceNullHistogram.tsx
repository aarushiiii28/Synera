import { int } from '../../lib/format';

/** Histogram of p-values pooled over label permutations. Honest p-values give flat bars; the dashed line is the flat expectation (the mean bar). */
export function SpaceNullHistogram({ bins }: { bins: number[] }) {
  const W = 360, H = 190, m = { l: 14, r: 10, t: 14, b: 34 };
  const total = bins.reduce((a, b) => a + b, 0);
  const mean = total / bins.length;
  const max = Math.max(...bins, mean) * 1.1;
  const bw = (W - m.l - m.r) / bins.length;
  const y = (v: number) => H - m.b - (v / max) * (H - m.b - m.t);
  return (
    <figure className="m-0">
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full block" role="img" aria-label={`Histogram of ${int(total)} permutation p-values in ${bins.length} bins`}>
        {bins.map((b, i) => (
          <g key={i}>
            <rect x={m.l + i * bw + 1} y={y(b)} width={bw - 2} height={H - m.b - y(b)} fill="var(--signal)" opacity="0.7" />
            <text x={m.l + i * bw + bw / 2} y={H - m.b + 14} textAnchor="middle" className="num" fontSize="9" fill="var(--faint)">{(i / bins.length).toFixed(1)}</text>
          </g>
        ))}
        <line x1={m.l} x2={W - m.r} y1={y(mean)} y2={y(mean)} stroke="var(--solar)" strokeDasharray="4 3" />
        <text x={m.l} y={H - 6} className="num" fontSize="10" fill="var(--muted)">permutation p-value (0 to 1)</text>
        <text x={W - m.r} y={y(mean) - 4} textAnchor="end" className="num" fontSize="10" fill="var(--solar)">flat = honest</text>
      </svg>
    </figure>
  );
}
