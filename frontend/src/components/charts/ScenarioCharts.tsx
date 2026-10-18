import { memo, useId, useMemo } from 'react';
import { fmtNum, type ScenarioModel } from '../../lib/scenario';

const MORE = 'var(--alert)';      // more deaths than a typical week
const FEWER = 'var(--teal)';      // fewer
const fx = (v: number, d = 2) => `${v >= 0 ? '+' : '−'}${Math.abs(v).toFixed(d)}%`;

/* ------------------------------------------------------------------------------------------------ US dot map */
const MAP_W = 380, MAP_H = 215;
function project(lat: number, lon: number, state: string): [number, number] {
  if (state === 'Alaska') return [34, 188];
  if (state === 'Hawaii') return [88, 200];
  return [18 + ((lon + 125) / 59) * (MAP_W - 36), 12 + ((50 - lat) / 26) * (MAP_H - 44)];
}

/** One dot per state at its main city: the place the weather and air are measured. A picture of what is selectable, not of borders. */
export function StateMap({ model, selected, onSelect }: { model: ScenarioModel; selected: string; onSelect: (s: string) => void }) {
  const states = Object.entries(model.locations).filter(([, l]) => l.lat !== null && l.lon !== null);
  return (
    <svg viewBox={`0 0 ${MAP_W} ${MAP_H}`} className="w-full h-auto" role="group" aria-label="Choose a state on the map">
      <rect x="1" y="1" width={MAP_W - 2} height={MAP_H - 2} fill="none" stroke="var(--line)" />
      {[0.25, 0.5, 0.75].map((f) => <line key={f} x1="1" x2={MAP_W - 1} y1={MAP_H * f} y2={MAP_H * f} stroke="var(--line)" strokeDasharray="2 6" />)}
      {states.map(([name, l]) => {
        const [x, y] = project(l.lat as number, l.lon as number, name);
        const on = name === selected;
        return (
          <g key={name} role="button" tabIndex={0} aria-label={name} aria-pressed={on} className="cursor-pointer outline-none" onClick={() => onSelect(name)}
            onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onSelect(name); } }}>
            <title>{name}</title>
            <circle cx={x} cy={y} r={11} fill="transparent" />
            <circle cx={x} cy={y} r={on ? 6.5 : 3.6} fill={on ? 'var(--signal)' : 'var(--muted)'} fillOpacity={on ? 1 : 0.7}
              stroke={on ? 'var(--text)' : 'none'} strokeWidth={on ? 1.5 : 0} />
            {on && <circle cx={x} cy={y} r={11} fill="none" stroke="var(--signal)" strokeOpacity="0.5" />}
          </g>
        );
      })}
      {(['Alaska', 'Hawaii'] as const).map((n) => model.locations[n] && <text key={n} x={n === 'Alaska' ? 34 : 88} y={n === 'Alaska' ? 174 : 186} textAnchor="middle" fontSize="8" fill="var(--faint)" className="num">{n === 'Alaska' ? 'AK' : 'HI'}</text>)}
    </svg>
  );
}

/* ------------------------------------------------------------------------------------------------ effect bar with interval */
export function EffectBar({ effect, lo, hi, scale }: { effect: number; lo: number; hi: number; scale: number }) {
  const W = 100;
  const x = (v: number) => 50 + Math.max(-1, Math.min(1, v / scale)) * 50;
  const color = effect >= 0 ? MORE : FEWER;
  return (
    <svg viewBox={`0 0 ${W} 14`} className="w-full h-7" preserveAspectRatio="none" role="img" aria-label={`Estimated effect ${fx(effect)}, range ${fx(lo)} to ${fx(hi)}`}>
      <line x1="0" x2={W} y1="7" y2="7" stroke="var(--line-strong)" strokeWidth="0.4" vectorEffect="non-scaling-stroke" />
      <line x1="50" x2="50" y1="1" y2="13" stroke="var(--muted)" strokeWidth="0.6" vectorEffect="non-scaling-stroke" />
      <rect x={Math.min(x(lo), x(hi))} y="4" width={Math.max(0.6, Math.abs(x(hi) - x(lo)))} height="6" fill={color} fillOpacity="0.28" />
      <line x1={x(effect)} x2={x(effect)} y1="2" y2="12" stroke={color} strokeWidth="2.2" vectorEffect="non-scaling-stroke" />
    </svg>
  );
}

/* ------------------------------------------------------------------------------------------------ contributions */
export function ContributionBars({ model, contributions, interaction, interactionLo, interactionHi }: {
  model: ScenarioModel; contributions: Record<string, number>; interaction: number; interactionLo: number; interactionHi: number;
}) {
  const rows = Object.entries(contributions).filter(([, v]) => Math.abs(v) > 0.0005).sort((a, b) => Math.abs(b[1]) - Math.abs(a[1]));
  const max = Math.max(0.05, ...rows.map(([, v]) => Math.abs(v)), Math.abs(interactionLo), Math.abs(interactionHi));
  const bar = (v: number, key: string, label: string, hatch = false) => (
    <li key={key} className="grid grid-cols-[minmax(7rem,10rem)_1fr_4.2rem] items-center gap-3">
      <span className="text-[13px] text-muted truncate">{label}</span>
      <span className="relative h-3 block" role="img" aria-label={`${label} ${fx(v, 3)}`}>
        <span className="absolute inset-y-0 left-1/2 w-px bg-line-strong" />
        <span className="absolute inset-y-0" style={{ left: v >= 0 ? '50%' : `${50 - (Math.abs(v) / max) * 50}%`, width: `${(Math.abs(v) / max) * 50}%`,
          background: v >= 0 ? MORE : FEWER, opacity: hatch ? 0.45 : 0.85 }} />
      </span>
      <span className="num text-[12px] text-right" style={{ color: v >= 0 ? MORE : FEWER }}>{fx(v, 3)}</span>
    </li>
  );
  if (!rows.length) return <p className="text-sm text-muted m-0">Nothing is changed from a typical week, so no stressor contributes.</p>;
  return (
    <ul className="m-0 p-0 list-none grid grid-cols-[minmax(0,1fr)] gap-2">
      {rows.map(([s, v]) => bar(v, s, model.labels[s] ?? s))}
      <li className="border-t border-line pt-2 mt-1">
        <div className="grid grid-cols-[minmax(7rem,10rem)_1fr_4.2rem] items-center gap-3">
          <span className="text-[13px] text-text">Interactions</span>
          <span className="relative h-3 block" role="img" aria-label={`Interaction part ${fx(interaction, 3)}, range ${fx(interactionLo, 3)} to ${fx(interactionHi, 3)}`}>
            <span className="absolute inset-y-0 left-1/2 w-px bg-line-strong" />
            <span className="absolute inset-y-[3px]" style={{ left: `${50 + (Math.min(interactionLo, interactionHi) / max) * 50}%`, width: `${Math.max(0.5, (Math.abs(interactionHi - interactionLo) / max) * 50)}%`, background: 'var(--solar)', opacity: 0.35 }} />
            <span className="absolute inset-y-0 w-[3px]" style={{ left: `calc(${50 + (interaction / max) * 50}% - 1.5px)`, background: 'var(--solar)' }} />
          </span>
          <span className="num text-[12px] text-right text-solar">{fx(interaction, 3)}</span>
        </div>
      </li>
    </ul>
  );
}

/* ------------------------------------------------------------------------------------------------ dose-response */
export interface Curve { s: string; pts: { x: number; effect: number; lo: number; hi: number }[]; current: number; currentEffect: number }

export const DoseGrid = memo(function DoseGrid({ model, curves }: { model: ScenarioModel; curves: Curve[] }) {
  const gid = useId();
  const [ymin, ymax] = useMemo(() => {
    let lo = -0.1, hi = 0.1;
    curves.forEach((c) => c.pts.forEach((p) => { lo = Math.min(lo, p.lo); hi = Math.max(hi, p.hi); }));
    const pad = (hi - lo) * 0.08;
    return [lo - pad, hi + pad];
  }, [curves]);
  const W = 150, H = 78, L = 4, R = 4, T = 4, B = 4;
  const sx = (c: Curve, v: number) => L + ((v - c.pts[0].x) / (c.pts[c.pts.length - 1].x - c.pts[0].x || 1)) * (W - L - R);
  const sy = (v: number) => T + (1 - (v - ymin) / (ymax - ymin)) * (H - T - B);
  return (
    <ul className="m-0 p-0 list-none grid grid-cols-2 sm:grid-cols-3 xl:grid-cols-5 gap-3">
      {curves.map((c) => {
        const band = `${c.pts.map((p) => `${sx(c, p.x)},${sy(p.hi)}`).join(' ')} ${[...c.pts].reverse().map((p) => `${sx(c, p.x)},${sy(p.lo)}`).join(' ')}`;
        const line = c.pts.map((p) => `${sx(c, p.x)},${sy(p.effect)}`).join(' ');
        return (
          <li key={c.s} className="border border-line bg-void/40 px-2 pt-2 pb-1">
            <div className="flex items-baseline justify-between gap-1">
              <span className="text-[12px] text-text truncate">{model.labels[c.s]}</span>
              <span className="num text-[10px] text-faint">{model.units[c.s]}</span>
            </div>
            <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-auto" role="img"
              aria-label={`${model.labels[c.s]} against effect on deaths: at the current setting ${fx(c.currentEffect)}`}>
              <clipPath id={`${gid}-${c.s}`}><rect x="0" y="0" width={W} height={H} /></clipPath>
              <g clipPath={`url(#${gid}-${c.s})`}>
                <line x1={L} x2={W - R} y1={sy(0)} y2={sy(0)} stroke="var(--line-strong)" strokeDasharray="3 3" />
                <polygon points={band} fill="var(--signal)" fillOpacity="0.16" />
                <polyline points={line} fill="none" stroke="var(--signal)" strokeWidth="1.6" />
                <line x1={sx(c, c.current)} x2={sx(c, c.current)} y1={T} y2={H - B} stroke="var(--solar)" strokeWidth="1" strokeDasharray="2 2" />
                <circle cx={sx(c, c.current)} cy={sy(c.currentEffect)} r="3.2" fill="var(--solar)" />
              </g>
            </svg>
            <div className="flex justify-between num text-[9px] text-faint"><span>{fmtNum(c.pts[0].x)}</span><span>{fmtNum(c.pts[c.pts.length - 1].x)}</span></div>
          </li>
        );
      })}
    </ul>
  );
});

/* ------------------------------------------------------------------------------------------------ interaction surface */
export interface SurfaceData { xs: number[]; ys: number[]; cells: { effect: number; sure: boolean; interaction: number }[][] }

export const SurfaceMap = memo(function SurfaceMap({ model, a, b, data, current, onPick }: {
  model: ScenarioModel; a: string; b: string; data: SurfaceData; current: [number, number]; onPick: (x: number, y: number) => void;
}) {
  const n = data.xs.length;
  const max = Math.max(0.05, ...data.cells.flat().map((c) => Math.abs(c.effect)));
  const S = 280, pad = 34;
  const cw = (S - pad) / n;
  const px = (v: number) => pad + ((v - data.xs[0]) / (data.xs[n - 1] - data.xs[0] || 1)) * (S - pad - cw) + cw / 2;
  const py = (v: number) => S - pad - ((v - data.ys[0]) / (data.ys[n - 1] - data.ys[0] || 1)) * (S - pad - cw) - cw / 2;
  return (
    <figure className="m-0">
      <svg viewBox={`0 0 ${S + 8} ${S + 14}`} className="w-full max-w-[420px] h-auto" role="img"
        aria-label={`Effect on deaths for every combination of ${model.labels[a]} and ${model.labels[b]}. Click a cell to set both sliders.`}>
        {data.cells.map((row, j) => row.map((c, i) => {
          const t = Math.min(1, Math.abs(c.effect) / max);
          return (
            <rect key={`${i}-${j}`} x={pad + i * cw} y={S - pad - (j + 1) * cw} width={cw + 0.4} height={cw + 0.4} className="cursor-pointer"
              fill={c.effect >= 0 ? MORE : FEWER} fillOpacity={(c.sure ? 0.15 : 0.05) + t * (c.sure ? 0.8 : 0.3)}
              onClick={() => onPick(data.xs[i], data.ys[j])}>
              <title>{`${model.labels[a]} ${data.xs[i].toFixed(1)} ${model.units[a]}, ${model.labels[b]} ${data.ys[j].toFixed(1)} ${model.units[b]}: ${fx(c.effect)}${c.sure ? '' : ' (not clearly different from zero)'}`}</title>
            </rect>
          );
        }))}
        <rect x={pad} y={S - pad - n * cw} width={n * cw} height={n * cw} fill="none" stroke="var(--line-strong)" />
        <line x1={px(current[0])} x2={px(current[0])} y1={S - pad - n * cw} y2={S - pad} stroke="var(--solar)" strokeDasharray="3 3" />
        <line x1={pad} x2={S} y1={py(current[1])} y2={py(current[1])} stroke="var(--solar)" strokeDasharray="3 3" />
        <circle cx={px(current[0])} cy={py(current[1])} r="4" fill="var(--solar)" stroke="var(--void)" />
        <text x={pad + (n * cw) / 2} y={S - 14} textAnchor="middle" fontSize="9.5" fill="var(--muted)" className="num">{model.labels[a]} ({model.units[a]}) →</text>
        <text transform={`translate(11 ${S - pad - (n * cw) / 2}) rotate(-90)`} textAnchor="middle" fontSize="9.5" fill="var(--muted)" className="num">{model.labels[b]} ({model.units[b]}) →</text>
        <text x={pad} y={S - 3} fontSize="8.5" fill="var(--faint)" className="num">{data.xs[0].toFixed(1)}</text>
        <text x={S} y={S - 3} textAnchor="end" fontSize="8.5" fill="var(--faint)" className="num">{data.xs[n - 1].toFixed(1)}</text>
      </svg>
      <figcaption className="text-[12px] text-muted mt-1 flex flex-wrap gap-x-4 gap-y-1">
        <span><span className="inline-block w-2.5 h-2.5 align-middle mr-1" style={{ background: MORE }} />more deaths</span>
        <span><span className="inline-block w-2.5 h-2.5 align-middle mr-1" style={{ background: FEWER }} />fewer</span>
        <span className="text-faint">faint cells: not clearly different from zero · scale ±{max.toFixed(2)}%</span>
      </figcaption>
    </figure>
  );
});

/* ------------------------------------------------------------------------------------------------ calibration */
export function CalibrationChart({ deciles }: { deciles: { predicted: number; observed: number; weeks: number }[] }) {
  const S = 220, P = 30;
  const lim = Math.max(...deciles.flatMap((d) => [Math.abs(d.predicted), Math.abs(d.observed)])) * 1.25;
  const sx = (v: number) => P + ((v + lim) / (2 * lim)) * (S - P - 8);
  const sy = (v: number) => S - P - ((v + lim) / (2 * lim)) * (S - P - 8);
  return (
    <svg viewBox={`0 0 ${S} ${S}`} className="w-full max-w-[260px] h-auto" role="img"
      aria-label="Predicted against observed excess deaths in ten groups of weeks, for states the model was not fitted on. Points near the diagonal mean good calibration.">
      <line x1={sx(-lim)} y1={sy(-lim)} x2={sx(lim)} y2={sy(lim)} stroke="var(--line-strong)" strokeDasharray="4 4" />
      <line x1={sx(0)} x2={sx(0)} y1={8} y2={S - P} stroke="var(--line)" /><line x1={P} x2={S - 8} y1={sy(0)} y2={sy(0)} stroke="var(--line)" />
      {deciles.map((d, i) => <circle key={i} cx={sx(d.predicted)} cy={sy(d.observed)} r="4.2" fill="var(--biosphere)" fillOpacity="0.85" stroke="var(--void)"><title>{`group ${i + 1}: predicted ${fx(d.predicted)}, observed ${fx(d.observed)}`}</title></circle>)}
      <text x={(S + P) / 2} y={S - 8} textAnchor="middle" fontSize="9.5" fill="var(--muted)" className="num">predicted excess deaths →</text>
      <text transform={`translate(10 ${(S - P) / 2 + 6}) rotate(-90)`} textAnchor="middle" fontSize="9.5" fill="var(--muted)" className="num">observed →</text>
    </svg>
  );
}
