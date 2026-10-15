import { useId, useMemo, useRef, useState } from 'react';
import * as d3 from 'd3';
import type { InteractionType, StressorInfo, Surface } from '../../lib/api';
import { TYPE_COLOR, fix } from '../../lib/format';
import { Term } from '../Term';
import { GAP_WORD, peakGap, peakGapIndex, surfaceRange, transect, transectSentence } from './discoveryLogic';

const W = 640, H = 470, M = { l: 62, r: 16, t: 14, b: 54 };
const PW = W - M.l - M.r, PH = H - M.t - M.b;
const TW = 640, TH = 270, TM = { l: 62, r: 18, t: 22, b: 48 };
const TPW = TW - TM.l - TM.r, TPH = TH - TM.t - TM.b;

const TERM_KEY: Record<InteractionType, string> = { SYNERGISTIC: 'synergistic', ANTAGONISTIC: 'antagonistic', NONLINEAR: 'nonlinear' };

interface Props {
  surface: Surface;
  labels?: StressorInfo;
  /** 'split' puts the transect chart beside the surface on large screens; 'stack' always stacks. */
  layout?: 'split' | 'stack';
}

/**
 * Additive expectation (dashed contours) vs fitted surface (solid contours), with the gap shaded.
 * z arrays follow numpy meshgrid(grid_a, grid_b): z[row = grid_b index][col = grid_a index].
 */
export function ResponseSurface({ surface: s, labels, layout = 'split' }: Props) {
  const uid = useId().replace(/:/g, '');
  const color = TYPE_COLOR[s.type];
  const n = s.grid_a.length, m = s.grid_b.length;
  const la = labels?.[s.a]?.label ?? s.a, lb = labels?.[s.b]?.label ?? s.b;
  const ua = labels?.[s.a]?.unit ?? '', ub = labels?.[s.b]?.unit ?? '';
  const unitOf = (k: string) => labels?.[k]?.unit ?? '';
  const range = useMemo(() => surfaceRange(s), [s]);

  // scrub = the stressor whose value is held fixed on the transect (the line runs along the other one)
  const [scrub, setScrub] = useState<'a' | 'b'>('b');
  const [idx, setIdx] = useState(() => peakGapIndex(s, 'a'));
  const axis: 'a' | 'b' = scrub === 'b' ? 'a' : 'b';
  const held = scrub === 'b' ? m : n;
  const t = useMemo(() => transect(s, axis, idx), [s, axis, idx]);
  const peak = useMemo(() => peakGap(t), [t]);

  const x = useMemo(() => d3.scaleLinear([s.grid_a[0], s.grid_a[n - 1]], [0, PW]), [s, n]);
  const y = useMemo(() => d3.scaleLinear([s.grid_b[0], s.grid_b[m - 1]], [PH, 0]), [s, m]);

  const path = useMemo(() => d3.geoPath(d3.geoTransform({
    point(px, py) { this.stream.point(((px - 0.5) / (n - 1)) * PW, PH - ((py - 0.5) / (m - 1)) * PH); },
  })), [n, m]);

  const layers = useMemo(() => {
    const flat = (z: number[][]) => z.flat();
    const gen = d3.contours().size([n, m]);
    const levels = d3.ticks(range.zMin, range.zMax, 8);
    const gm = range.gapMax;
    const gl = [0.12, 0.32, 0.52, 0.72, 0.9].map((k) => k * gm);
    return {
      levels,
      step: levels.length > 1 ? levels[1] - levels[0] : null,
      add: gen.thresholds(levels)(flat(s.z_additive)).map((c) => path(c) ?? ''),
      full: gen.thresholds(levels)(flat(s.z_full)).map((c) => path(c) ?? ''),
      pos: gl.map((th) => path(gen.thresholds([th])(flat(s.z_gap))[0]) ?? ''),
      neg: gl.map((th) => path(gen.thresholds([th])(flat(s.z_gap).map((v) => -v))[0]) ?? ''),
    };
  }, [s, n, m, range, path]);

  // transect chart scales
  const tx = d3.scaleLinear([t.xs[0], t.xs[t.xs.length - 1]], [0, TPW]);
  const lo = Math.min(...t.add, ...t.full), hi = Math.max(...t.add, ...t.full);
  const pad = (hi - lo) * 0.12 || 0.1;
  const ty = d3.scaleLinear([lo - pad, hi + pad], [TPH, 0]);
  const line = d3.line<number>().x((_, i) => tx(t.xs[i])).curve(d3.curveMonotoneX);
  const addPath = line.y((v) => ty(v))(t.add) ?? '';
  const fullPath = line.y((v) => ty(v))(t.full) ?? '';
  const areaPath = d3.area<number>().x((_, i) => tx(t.xs[i])).y0((_, i) => ty(t.add[i])).y1((_, i) => ty(t.full[i])).curve(d3.curveMonotoneX)(t.full) ?? '';

  const svgRef = useRef<SVGSVGElement>(null);
  const drag = useRef(false);
  const setFromPointer = (e: React.PointerEvent) => {
    const r = svgRef.current?.getBoundingClientRect();
    if (!r) return;
    const px = ((e.clientX - r.left) / r.width) * W - M.l, py = ((e.clientY - r.top) / r.height) * H - M.t;
    const frac = scrub === 'b' ? 1 - Math.min(1, Math.max(0, py / PH)) : Math.min(1, Math.max(0, px / PW));
    setIdx(Math.round(frac * (held - 1)));
  };

  const heldFrac = held > 1 ? t.index / (held - 1) : 0;
  const lineY = M.t + PH - heldFrac * PH, lineX = M.l + heldFrac * PW;
  const heldLabel = scrub === 'b' ? lb : la;
  const runLabel = scrub === 'b' ? la : lb;
  const runUnit = scrub === 'b' ? ua : ub;
  const heldUnit = scrub === 'b' ? ub : ua;
  const sign = peak.gap >= 0 ? '+' : '−';
  const toggleBtn = (k: 'a' | 'b', label: string) => (
    <button type="button" aria-pressed={scrub === k} onClick={() => { setScrub(k); setIdx(peakGapIndex(s, k === 'b' ? 'a' : 'b')); }}
      className={`num text-[11px] tracking-[0.1em] px-2.5 py-1 border ${scrub === k ? 'border-signal text-signal bg-signal/10' : 'border-line text-muted hover:text-text'}`}>
      {label.toUpperCase()}
    </button>
  );

  return (
    <div className={layout === 'split' ? 'grid xl:grid-cols-[1.25fr_1fr] gap-6 items-start' : 'grid gap-6'}>
      <figure className="m-0 min-w-0">
        <svg ref={svgRef} viewBox={`0 0 ${W} ${H}`} className="w-full h-auto touch-none select-none" role="img"
          aria-label={`Response surface of the outcome over ${la} and ${lb}. Dashed lines show the additive expectation, solid lines the fitted surface, shading the gap between them.`}
          onPointerDown={(e) => { drag.current = true; (e.currentTarget as Element).setPointerCapture?.(e.pointerId); setFromPointer(e); }}
          onPointerMove={(e) => drag.current && setFromPointer(e)}
          onPointerUp={() => { drag.current = false; }} onPointerCancel={() => { drag.current = false; }}>
          <defs>
            <pattern id={`${uid}h`} width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
              <line x1="0" y1="0" x2="0" y2="6" stroke={color} strokeWidth="1.3" opacity="0.55" />
            </pattern>
            <clipPath id={`${uid}c`}><rect width={PW} height={PH} /></clipPath>
          </defs>
          <g transform={`translate(${M.l},${M.t})`}>
            <rect width={PW} height={PH} fill="var(--void)" fillOpacity="0.5" stroke="var(--line)" />
            <g clipPath={`url(#${uid}c)`}>
              {layers.pos.map((d, i) => <path key={`p${i}`} d={d} fill={color} fillOpacity="0.13" />)}
              {layers.neg.map((d, i) => <path key={`n${i}`} d={d} fill={`url(#${uid}h)`} fillOpacity={0.5} />)}
              {layers.add.map((d, i) => <path key={`a${i}`} d={d} fill="none" stroke="var(--muted)" strokeWidth="1" strokeDasharray="4 3" opacity="0.9" />)}
              {layers.full.map((d, i) => <path key={`f${i}`} d={d} fill="none" stroke="var(--text)" strokeWidth="1.4" />)}
              {/* transect line */}
              {scrub === 'b'
                ? <line x1="0" x2={PW} y1={lineY - M.t} y2={lineY - M.t} stroke={color} strokeWidth="1.6" />
                : <line y1="0" y2={PH} x1={lineX - M.l} x2={lineX - M.l} stroke={color} strokeWidth="1.6" />}
              <circle cx={scrub === 'b' ? x(peak.x) : lineX - M.l} cy={scrub === 'b' ? lineY - M.t : y(peak.x)} r="6" fill="none" stroke={color} strokeWidth="1.6" />
              <circle cx={scrub === 'b' ? x(peak.x) : lineX - M.l} cy={scrub === 'b' ? lineY - M.t : y(peak.x)} r="2" fill={color} />
            </g>
            {/* axes */}
            {x.ticks(6).map((v) => (
              <g key={`x${v}`} transform={`translate(${x(v)},${PH})`}><line y2="5" stroke="var(--line-strong)" /><text y="19" textAnchor="middle" className="num" fontSize="11" fill="var(--muted)">{fix(v, 1)}</text></g>
            ))}
            {y.ticks(6).map((v) => (
              <g key={`y${v}`} transform={`translate(0,${y(v)})`}><line x2="-5" stroke="var(--line-strong)" /><text x="-9" y="4" textAnchor="end" className="num" fontSize="11" fill="var(--muted)">{fix(v, 1)}</text></g>
            ))}
            <text x={PW / 2} y={PH + 44} textAnchor="middle" fontSize="12.5" fill="var(--text)">{la} <tspan fill="var(--faint)">({ua || 'standardised'})</tspan></text>
            <text transform={`translate(-46,${PH / 2}) rotate(-90)`} textAnchor="middle" fontSize="12.5" fill="var(--text)">{lb} <tspan fill="var(--faint)">({ub || 'standardised'})</tspan></text>
            {/* drag handle */}
            {scrub === 'b'
              ? <path d={`M${PW + 1},${lineY - M.t} l8,-6 v12 z`} fill={color} />
              : <path d={`M${lineX - M.l},${PH + 1} l-6,8 h12 z`} fill={color} />}
          </g>
        </svg>
        <figcaption className="mt-2 flex flex-wrap gap-x-5 gap-y-1 text-[12px] text-muted items-center">
          <span className="inline-flex items-center gap-2"><svg width="26" height="8" aria-hidden><line x1="0" y1="4" x2="26" y2="4" stroke="var(--muted)" strokeDasharray="4 3" /></svg>additive expectation</span>
          <span className="inline-flex items-center gap-2"><svg width="26" height="8" aria-hidden><line x1="0" y1="4" x2="26" y2="4" stroke="var(--text)" strokeWidth="1.4" /></svg>fitted surface</span>
          <span className="inline-flex items-center gap-2"><svg width="16" height="12" aria-hidden><rect width="16" height="12" fill={color} fillOpacity="0.3" /></svg>fitted above additive</span>
          <span className="inline-flex items-center gap-2"><svg width="16" height="12" aria-hidden><defs><pattern id={`${uid}l`} width="5" height="5" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><line y2="5" stroke={color} strokeWidth="1.2" /></pattern></defs><rect width="16" height="12" fill={`url(#${uid}l)`} stroke="var(--line)" /></svg>fitted below additive</span>
          {layers.step !== null && <span className="num text-faint">lines every {fix(layers.step, 2)} SD</span>}
        </figcaption>
      </figure>

      <div className="min-w-0">
        <div className="flex flex-wrap items-center gap-2 mb-2">
          <span className="label">Hold fixed</span>
          {toggleBtn('b', lb)}{toggleBtn('a', la)}
        </div>
        <label className="block">
          <span className="sr-only">{`Position of ${heldLabel}`}</span>
          <input type="range" min={0} max={held - 1} step={1} value={t.index} onChange={(e) => setIdx(Number(e.target.value))}
            aria-label={`Position of ${heldLabel} for the transect`} aria-valuetext={`${heldLabel} ${fix(t.at, 2)} ${heldUnit}`}
            className="w-full accent-[var(--signal)]" />
        </label>
        <div className="num text-[12px] text-muted mb-3">{heldLabel} = <span className="text-text">{fix(t.at, 2)}</span> {heldUnit}</div>

        <svg viewBox={`0 0 ${TW} ${TH}`} className="w-full h-auto" role="img"
          aria-label={`Additive versus fitted response along ${runLabel} with ${heldLabel} fixed at ${fix(t.at, 2)}. Largest gap ${sign}${fix(Math.abs(peak.gap), 2)} outcome SD.`}>
          <g transform={`translate(${TM.l},${TM.t})`}>
            <path d={areaPath} fill={color} fillOpacity="0.28" />
            <path d={addPath} fill="none" stroke="var(--muted)" strokeWidth="1.5" strokeDasharray="5 4" />
            <path d={fullPath} fill="none" stroke="var(--text)" strokeWidth="2" />
            <line x1={tx(peak.x)} x2={tx(peak.x)} y1={ty(t.add[peak.i])} y2={ty(t.full[peak.i])} stroke={color} strokeWidth="2.4" />
            <circle cx={tx(peak.x)} cy={ty(t.full[peak.i])} r="3.5" fill={color} />
            <text x={tx(peak.x) + (tx(peak.x) > TPW * 0.6 ? -8 : 8)} y={(ty(t.add[peak.i]) + ty(t.full[peak.i])) / 2 + 4} textAnchor={tx(peak.x) > TPW * 0.6 ? 'end' : 'start'} fontSize="12.5" fill={color} className="num">
              gap {sign}{fix(Math.abs(peak.gap), 2)} SD
            </text>
            {tx.ticks(5).map((v) => (
              <g key={`tx${v}`} transform={`translate(${tx(v)},${TPH})`}><line y2="5" stroke="var(--line-strong)" /><text y="19" textAnchor="middle" className="num" fontSize="11" fill="var(--muted)">{fix(v, 1)}</text></g>
            ))}
            {ty.ticks(4).map((v) => (
              <g key={`ty${v}`} transform={`translate(0,${ty(v)})`}><line x2="-5" stroke="var(--line-strong)" /><text x="-9" y="4" textAnchor="end" className="num" fontSize="11" fill="var(--muted)">{fix(v, 1)}</text></g>
            ))}
            <line x1="0" x2="0" y1="0" y2={TPH} stroke="var(--line-strong)" /><line x1="0" x2={TPW} y1={TPH} y2={TPH} stroke="var(--line-strong)" />
            <text x={TPW / 2} y={TPH + 40} textAnchor="middle" fontSize="12.5" fill="var(--text)">{runLabel} <tspan fill="var(--faint)">({runUnit || 'standardised'})</tspan></text>
            <text transform={`translate(-46,${TPH / 2}) rotate(-90)`} textAnchor="middle" fontSize="12.5" fill="var(--text)">outcome (SD)</text>
            <text x={TPW} y="-6" textAnchor="end" fontSize="11.5" fill="var(--muted)">- - additive</text>
            <text x={TPW - 90} y="-6" textAnchor="end" fontSize="11.5" fill="var(--text)">&mdash; fitted</text>
          </g>
        </svg>
        <p className="text-[14px] text-muted leading-snug mt-2 mb-0" aria-live="polite">
          {transectSentence(t, la, lb, unitOf, s.a, s.b)}{' '}
          Here the combined effect is <span style={{ color }}>{GAP_WORD[s.type]}</span> (<Term k={TERM_KEY[s.type]} />). Units are outcome standard deviations.
        </p>
      </div>
    </div>
  );
}
