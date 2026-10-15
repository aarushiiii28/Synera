import { fix } from '../../lib/format';

/** Point estimate with its confidence interval on a shared scale. Renders nothing when no interval exists. */
export function FindingsMiniForest({ point, lo, hi, max, width = 110, label }: { point: number; lo: number; hi: number; max: number; width?: number; label: string }) {
  if (!(max > 0)) return null;
  const x = (v: number) => 4 + (Math.min(Math.max(v, 0), max) / max) * (width - 8);
  return (
    <svg width={width} height="18" viewBox={`0 0 ${width} 18`} role="img" aria-label={label} className="block">
      <line x1={x(0)} x2={x(0)} y1="2" y2="16" stroke="var(--line-strong)" />
      <line x1={x(lo)} x2={x(hi)} y1="9" y2="9" stroke="var(--muted)" strokeWidth="1.4" />
      <line x1={x(lo)} x2={x(lo)} y1="5" y2="13" stroke="var(--muted)" /><line x1={x(hi)} x2={x(hi)} y1="5" y2="13" stroke="var(--muted)" />
      <circle cx={x(point)} cy="9" r="3.4" fill="var(--text)" />
    </svg>
  );
}

/** Thin 270-degree arc filled to the confidence score, with one tick per component. */
export function FindingsConfidenceArc({ score, components, size = 40 }: { score: number; components: Record<string, number>; size?: number }) {
  const c = size / 2, r = size / 2 - 5, sweep = 270, start = 135;
  const pt = (frac: number, rr: number) => {
    const a = ((start + frac * sweep) * Math.PI) / 180;
    return [c + Math.cos(a) * rr, c + Math.sin(a) * rr] as const;
  };
  const arc = (f: number) => {
    const [x0, y0] = pt(0, r), [x1, y1] = pt(f, r);
    return `M${x0},${y0}A${r},${r} 0 ${f * sweep > 180 ? 1 : 0} 1 ${x1},${y1}`;
  };
  const title = `Confidence ${fix(score, 2)}: ` + Object.entries(components).map(([k, v]) => `${k} ${fix(v, 2)}`).join(', ');
  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} role="img" aria-label={title}>
      <title>{title}</title>
      <path d={arc(1)} fill="none" stroke="var(--line-strong)" strokeWidth="1.5" strokeLinecap="round" />
      {score > 0 && <path d={arc(Math.min(1, score))} fill="none" stroke="var(--teal)" strokeWidth="2.5" strokeLinecap="round" />}
      {Object.values(components).map((v, i) => {
        const [x0, y0] = pt(Math.min(1, v), r - 4), [x1, y1] = pt(Math.min(1, v), r + 4);
        return <line key={i} x1={x0} y1={y0} x2={x1} y2={y1} stroke="var(--sun)" strokeWidth="1" opacity="0.8" />;
      })}
      <text x={c} y={c + 3.5} textAnchor="middle" className="num" fontSize="10" fill="var(--text)">{fix(score * 100, 0)}</text>
    </svg>
  );
}
