import { useMemo, useRef, useState } from 'react';
import { scaleLinear, scaleTime } from 'd3';
import { line as d3line } from 'd3';

export interface Point { t: number; v: number | null }

const W = 420, H = 200, M = { l: 40, r: 10, t: 14, b: 26 };      // a compact viewBox so axis text stays legible when three charts share a row

/** A bounded, honest time series: gaps stay gaps (a missing value is never interpolated) and an empty series says so. */
export function LiveChart({ points, unit, label, color, digits = 1, empty, includeZero = false }: {
  points: Point[]; unit: string; label: string; color: string; digits?: number; empty: string; includeZero?: boolean;
}) {
  const [hover, setHover] = useState<number | null>(null);
  const ref = useRef<SVGSVGElement>(null);
  const valid = points.filter((p) => p.v !== null) as { t: number; v: number }[];
  const geo = useMemo(() => {
    if (!valid.length) return null;
    const t0 = points[0].t, t1 = points[points.length - 1].t;
    const vs = valid.map((p) => p.v);
    let lo = Math.min(...vs), hi = Math.max(...vs);
    if (includeZero) lo = Math.min(lo, 0);
    const pad = hi === lo ? Math.max(1, Math.abs(hi) * 0.05) : (hi - lo) * 0.15;
    const x = scaleTime().domain([t0, t1 === t0 ? t0 + 1000 : t1]).range([M.l, W - M.r]);
    const y = scaleLinear().domain([lo - pad, hi + pad]).nice().range([H - M.b, M.t]);
    const gen = d3line<Point>().defined((p) => p.v !== null).x((p) => x(p.t)).y((p) => y(p.v as number));
    return { x, y, path: gen(points) ?? '', yt: y.ticks(4), xt: x.ticks(3) };
  }, [points, valid.length, includeZero]); // eslint-disable-line react-hooks/exhaustive-deps

  if (!geo) {
    return (
      <div role="img" aria-label={`${label}: no data`} className="border border-dashed border-line grid place-items-center text-center px-6" style={{ height: H }}>
        <div><div className="label mb-1">{label}</div><p className="text-[13px] text-faint m-0 max-w-xs">{empty}</p></div>
      </div>
    );
  }
  const fmt = (v: number) => v.toFixed(digits);
  const onMove = (e: React.PointerEvent<SVGSVGElement>) => {
    const r = ref.current?.getBoundingClientRect();
    if (!r || !valid.length) return;
    const px = ((e.clientX - r.left) / r.width) * W;
    let best = 0, bd = Infinity;
    valid.forEach((p, i) => { const d = Math.abs(geo.x(p.t) - px); if (d < bd) { bd = d; best = i; } });
    setHover(best);
  };
  const hp = hover !== null ? valid[Math.min(hover, valid.length - 1)] : null;
  return (
    <figure className="m-0">
      <svg ref={ref} viewBox={`0 0 ${W} ${H}`} width="100%" role="img" aria-label={`${label} over time, ${valid.length} readings, latest ${fmt(valid[valid.length - 1].v)} ${unit}`}
        onPointerMove={onMove} onPointerLeave={() => setHover(null)} style={{ display: 'block', touchAction: 'pan-y' }}>
        {geo.yt.map((v) => (<g key={v}><line x1={M.l} x2={W - M.r} y1={geo.y(v)} y2={geo.y(v)} stroke="var(--line)" strokeDasharray="2 4" /><text x={M.l - 6} y={geo.y(v) + 3} textAnchor="end" fontSize="11" fill="var(--faint)">{fmt(v)}</text></g>))}
        {geo.xt.map((t) => (<text key={+t} x={geo.x(t)} y={H - 6} textAnchor="middle" fontSize="11" fill="var(--faint)">{t.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}</text>))}
        <text x={10} y={M.t + 4} fontSize="11" fill="var(--muted)">{unit}</text>
        <path d={geo.path} fill="none" stroke={color} strokeWidth="1.8" strokeLinejoin="round" />
        {valid.length < 60 && valid.map((p) => <circle key={p.t} cx={geo.x(p.t)} cy={geo.y(p.v)} r="2.2" fill={color} />)}
        {hp && (<g pointerEvents="none">
          <line x1={geo.x(hp.t)} x2={geo.x(hp.t)} y1={M.t} y2={H - M.b} stroke="var(--muted)" strokeDasharray="3 3" />
          <circle cx={geo.x(hp.t)} cy={geo.y(hp.v)} r="4" fill={color} stroke="var(--void)" strokeWidth="1.5" />
        </g>)}
      </svg>
      <figcaption className="num text-[11px] text-muted min-h-[18px] px-1" aria-live="off">
        {hp ? <>{new Date(hp.t).toLocaleTimeString()} · <span className="text-text">{fmt(hp.v)} {unit}</span></> : <span className="text-faint">hover for the value at a moment · {valid.length} valid readings shown</span>}
      </figcaption>
    </figure>
  );
}
