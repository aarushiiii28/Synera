import { useState } from 'react';
import { pct, fix } from '../../lib/format';
import { linearScale } from './trustLogic';
import type { SpaceOverview } from '../../lib/api';

/** Power curve: chance of detecting a real interaction of a given size (log2 fold). Spike-in simulation, drawn from the API values. */
export function SpacePower({ power }: { power: SpaceOverview['power'] }) {
  const [hover, setHover] = useState<number | null>(null);
  const pts = Object.entries(power.by_log2_effect).map(([k, v]) => ({ x: Number(k), ...v })).sort((a, b) => a.x - b.x);
  const W = 640, H = 300, m = { l: 52, r: 18, t: 16, b: 46 };
  const xMax = Math.max(...pts.map((p) => p.x), power.minimum_detectable_log2_80pct_power ?? 0);
  const sx = linearScale(0, xMax, m.l, W - m.r), sy = linearScale(0, 1, H - m.b, m.t);
  const mde = power.minimum_detectable_log2_80pct_power;
  const line = pts.map((p, i) => `${i ? 'L' : 'M'}${sx(p.x)},${sy(p.power_mean)}`).join(' ');
  const band = [...pts.map((p) => `${sx(p.x)},${sy(p.power_range[1])}`), ...[...pts].reverse().map((p) => `${sx(p.x)},${sy(p.power_range[0])}`)].join(' ');
  const h = hover !== null ? pts[hover] : null;
  return (
    <figure className="m-0">
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full block" role="img" aria-label={`Power curve. ${mde === null ? 'No tested effect size reaches 80% power.' : `80% power is reached at a log2 interaction of ${mde}.`}`}>
        {[0, 0.25, 0.5, 0.75, 1].map((t) => (
          <g key={t}><line x1={m.l} x2={W - m.r} y1={sy(t)} y2={sy(t)} stroke="var(--line)" /><text x={m.l - 8} y={sy(t) + 4} textAnchor="end" className="num" fontSize="11" fill="var(--faint)">{pct(t)}</text></g>
        ))}
        {pts.map((p) => <text key={p.x} x={sx(p.x)} y={H - m.b + 18} textAnchor="middle" className="num" fontSize="11" fill="var(--faint)">{fix(p.x, 1)}</text>)}
        <text x={(m.l + W - m.r) / 2} y={H - 6} textAnchor="middle" className="num" fontSize="11" fill="var(--muted)">true size of the interaction (log2 fold change)</text>
        <text x="14" y={(m.t + H - m.b) / 2} transform={`rotate(-90 14 ${(m.t + H - m.b) / 2})`} textAnchor="middle" className="num" fontSize="11" fill="var(--muted)">chance of detecting it</text>
        <polygon points={band} fill="var(--signal)" opacity="0.14" />
        <line x1={m.l} x2={W - m.r} y1={sy(0.8)} y2={sy(0.8)} stroke="var(--biosphere)" strokeDasharray="5 4" />
        <text x={m.l + 6} y={sy(0.8) - 6} className="num" fontSize="11" fill="var(--biosphere)">80% = the usual bar for a reliable test</text>
        {mde !== null && (
          <g>
            <line x1={sx(mde)} x2={sx(mde)} y1={m.t} y2={H - m.b} stroke="var(--solar)" strokeWidth="1.2" />
            <circle cx={sx(mde)} cy={sy(0.8)} r="5" fill="var(--void)" stroke="var(--solar)" strokeWidth="2" />
            <text x={sx(mde) - 8} y={m.t + 14} textAnchor="end" className="num" fontSize="11" fill="var(--solar)">smallest reliably detectable: {fix(mde, 1)} log2 (about {fix(Math.pow(2, mde), 0)}-fold)</text>
          </g>
        )}
        <path d={line} fill="none" stroke="var(--signal)" strokeWidth="2" />
        {pts.map((p, i) => (
          <g key={p.x}>
            <circle cx={sx(p.x)} cy={sy(p.power_mean)} r={hover === i ? 6 : 4} fill="var(--void)" stroke="var(--signal)" strokeWidth="2" />
            <circle cx={sx(p.x)} cy={sy(p.power_mean)} r="16" fill="transparent" tabIndex={0} role="img" aria-label={`Log2 effect ${p.x}: power ${pct(p.power_mean, 1)}, range ${pct(p.power_range[0], 1)} to ${pct(p.power_range[1], 1)}`}
              onMouseEnter={() => setHover(i)} onMouseLeave={() => setHover(null)} onFocus={() => setHover(i)} onBlur={() => setHover(null)} />
          </g>
        ))}
        {h && (
          <g transform={`translate(${Math.min(sx(h.x) + 10, W - 160)},${Math.min(sy(h.power_mean) + 8, H - m.b - 44)})`}>
            <rect width="150" height="40" fill="var(--void)" stroke="var(--line-strong)" />
            <text x="8" y="16" className="num" fontSize="11" fill="var(--text)">effect {fix(h.x, 1)} log2: {pct(h.power_mean, 1)}</text>
            <text x="8" y="31" className="num" fontSize="10" fill="var(--muted)">range {pct(h.power_range[0], 0)} to {pct(h.power_range[1], 0)}</text>
          </g>
        )}
      </svg>
      <figcaption className="text-xs text-muted mt-1">Line: mean power. Band: range across simulation repeats.</figcaption>
    </figure>
  );
}
