import { useId, useMemo, useRef, useState } from 'react';
import type { InteractionMatrix, MatrixCell, StressorInfo } from '../../lib/api';
import { TYPE_COLOR, fix, sci } from '../../lib/format';
import { StatusChip } from '../StatusChip';
import { Term } from '../Term';
import { cellAriaLabel, cellLookup, diamondRadius } from './discoveryLogic';

const CELL = 50, ML = 128, MT = 108;
const diamond = (cx: number, cy: number, r: number) => `M${cx},${cy - r}L${cx + r},${cy}L${cx},${cy + r}L${cx - r},${cy}Z`;

interface Props {
  matrix: InteractionMatrix;
  labels?: StressorInfo;
  selectedId: string | null;
  onSelect: (c: MatrixCell) => void;
}

/** Upper-triangle interaction grid. Diamond size = effect size (outcome SD), colour = interaction type, style = what the statistics concluded. */
export function DiscoveryMatrix({ matrix, labels, selectedId, onSelect }: Props) {
  const uid = useId().replace(/:/g, '');
  const S = matrix.stressors, n = S.length;
  const look = useMemo(() => cellLookup(matrix.cells), [matrix.cells]);
  const maxEffect = useMemo(() => Math.max(0, ...matrix.cells.map((c) => c.effect_size ?? 0)), [matrix.cells]);
  const lab = (k: string) => labels?.[k]?.label ?? k;
  const first = matrix.cells.find((c) => c.finding_id === selectedId) ?? matrix.cells.find((c) => c.category === 'selected') ?? matrix.cells[0];
  const [active, setActive] = useState<MatrixCell | undefined>(first);
  // grid geometry: row r = stressor r, column k = stressor k+1, valid when k >= r
  const pos = (a: string, b: string) => {
    const i = S.indexOf(a), j = S.indexOf(b);
    return { r: Math.min(i, j), k: Math.max(i, j) - 1 };
  };
  const [rover, setRover] = useState<string>(() => { const p = first ? pos(first.a, first.b) : { r: 0, k: 0 }; return `${p.r}-${p.k}`; });
  const svgRef = useRef<SVGSVGElement>(null);
  const entries: { r: number; k: number; cell: MatrixCell }[] = [];
  for (let r = 0; r < n - 1; r++) for (let k = r; k < n - 1; k++) {
    const c = look.get([S[r], S[k + 1]].sort().join('|'));
    if (c) entries.push({ r, k, cell: c });
  }
  const roverKey = entries.some((e) => `${e.r}-${e.k}` === rover) ? rover : entries.length ? `${entries[0].r}-${entries[0].k}` : '';
  const focusCell = (r: number, k: number) => {
    const el = svgRef.current?.querySelector<SVGGElement>(`[data-cell="${r}-${k}"]`);
    if (el) { el.focus(); setRover(`${r}-${k}`); }
  };
  const onKey = (e: React.KeyboardEvent, r: number, k: number, c: MatrixCell) => {
    const move: Record<string, [number, number]> = { ArrowRight: [r, k + 1], ArrowLeft: [r, k - 1], ArrowUp: [r - 1, k], ArrowDown: [r + 1, k] };
    if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); if (c.category === 'selected') onSelect(c); return; }
    const m = move[e.key];
    if (!m) return;
    e.preventDefault();
    const [nr, nk] = m;
    if (nr >= 0 && nk >= nr && nk <= n - 2) focusCell(nr, nk);
  };

  const W = ML + (n - 1) * CELL + 12, H = MT + (n - 1) * CELL + 10;
  const ac = active;

  return (
    <div className="grid lg:grid-cols-[minmax(0,1fr)_300px] gap-6 items-start">
      <svg ref={svgRef} viewBox={`0 0 ${W} ${H}`} className="w-full h-auto max-w-[640px]" role="group" aria-label="Interaction matrix. Use arrow keys to move between pairs, Enter to open a selected finding.">
        <defs>
          <filter id={`${uid}g`} x="-80%" y="-80%" width="260%" height="260%"><feGaussianBlur stdDeviation="3.5" result="b" /><feMerge><feMergeNode in="b" /><feMergeNode in="SourceGraphic" /></feMerge></filter>
        </defs>
        {S.slice(0, n - 1).map((k, r) => (
          <text key={`r${k}`} x={ML - 10} y={MT + r * CELL + CELL / 2 + 4} textAnchor="end" fontSize="13" fill="var(--muted)">{lab(k)}</text>
        ))}
        {S.slice(1).map((k, c) => (
          <text key={`c${k}`} transform={`translate(${ML + c * CELL + CELL / 2},${MT - 10}) rotate(-42)`} fontSize="13" fill="var(--muted)">{lab(k)}</text>
        ))}
        {entries.map(({ r, k, cell }) => {
          const cx = ML + k * CELL + CELL / 2, cy = MT + r * CELL + CELL / 2;
          const sel = cell.category === 'selected';
          const color = cell.type ? TYPE_COLOR[cell.type] : 'var(--muted)';
          const isCurrent = sel && cell.finding_id === selectedId;
          return (
            <g key={`${r}-${k}`} data-cell={`${r}-${k}`} role="button" tabIndex={roverKey === `${r}-${k}` ? 0 : -1} aria-disabled={!sel}
              aria-pressed={sel ? isCurrent : undefined} aria-label={cellAriaLabel(cell, lab(cell.a), lab(cell.b))}
              className="outline-none cursor-pointer group" style={{ cursor: sel ? 'pointer' : 'help' }}
              onMouseEnter={() => setActive(cell)} onFocus={() => { setActive(cell); setRover(`${r}-${k}`); }}
              onClick={() => { setActive(cell); if (sel) onSelect(cell); }} onKeyDown={(e) => onKey(e, r, k, cell)}>
              <rect x={cx - CELL / 2} y={cy - CELL / 2} width={CELL} height={CELL} fill="transparent" stroke="var(--line)" strokeWidth="0.5" className="group-focus-visible:stroke-[var(--signal)]" />
              {ac && ac === cell && <rect x={cx - CELL / 2 + 1} y={cy - CELL / 2 + 1} width={CELL - 2} height={CELL - 2} fill="none" stroke="var(--signal)" strokeWidth="1.5" />}
              {sel && <path d={diamond(cx, cy, diamondRadius(cell.effect_size, maxEffect, 8, 21))} fill={color} filter={`url(#${uid}g)`} />}
              {sel && isCurrent && <path d={diamond(cx, cy, diamondRadius(cell.effect_size, maxEffect, 8, 21) + 5)} fill="none" stroke={color} strokeWidth="1.2" />}
              {cell.category === 'explained_away' && <path d={diamond(cx, cy, 9)} fill="none" stroke="var(--muted)" strokeWidth="1.3" strokeDasharray="3 2.5" />}
              {cell.category === 'not_significant' && <circle cx={cx} cy={cy} r="2.5" fill="var(--faint)" opacity="0.7" />}
            </g>
          );
        })}
        {/* legend in the empty lower triangle */}
        <g transform={`translate(${ML + 6},${MT + 5.4 * CELL})`} fontSize="12" fill="var(--muted)">
          <text y="0" className="label" fontSize="10" letterSpacing="1.6" fill="var(--faint)">KEY</text>
          {(['SYNERGISTIC', 'ANTAGONISTIC', 'NONLINEAR'] as const).map((t, i) => (
            <g key={t} transform={`translate(8,${16 + i * 20})`}><path d={diamond(0, 0, 7)} fill={TYPE_COLOR[t]} /><text x="16" y="4">{t.toLowerCase()}</text></g>
          ))}
          <g transform="translate(8,80)"><path d={diamond(0, 0, 7)} fill="none" stroke="var(--muted)" strokeDasharray="3 2.5" /><text x="16" y="4">explained away</text></g>
          <g transform="translate(8,100)"><circle r="2.5" fill="var(--faint)" /><text x="16" y="4">not significant</text></g>
          <text y="132" fontSize="11" fill="var(--faint)">size = effect (SD)</text>
        </g>
      </svg>

      <aside className="border border-line bg-void/50 p-4 lg:sticky lg:top-20" aria-live="polite" aria-label="Pair inspector">
        <div className="label mb-2">Pair inspector</div>
        {ac ? (
          <>
            <div className="display text-lg leading-tight mb-1">{lab(ac.a)} <span className="text-faint">x</span> {lab(ac.b)}</div>
            <div className="flex items-center gap-2 mb-2">
              {ac.category === 'selected' && ac.status ? <StatusChip status={ac.status} /> : null}
              <span className="num text-[10px] tracking-[0.14em]" style={{ color: ac.type ? TYPE_COLOR[ac.type] : 'var(--muted)' }}>
                {ac.type ?? ac.category.replace('_', ' ').toUpperCase()}
              </span>
            </div>
            <p className="text-[13px] text-muted leading-snug mt-0 mb-3">{matrix.explanation[ac.category]}</p>
            <dl className="grid grid-cols-[1fr_auto] gap-x-3 gap-y-1.5 text-[13px] m-0">
              <dt className="text-muted"><Term k="qvalue">Marginal q</Term></dt><dd className="num m-0 text-right">{sci(ac.q_marginal)}</dd>
              <dt className="text-muted"><Term k="conditional">Conditional p</Term></dt><dd className="num m-0 text-right">{ac.p_conditional === null ? 'removed' : sci(ac.p_conditional)}</dd>
              <dt className="text-muted"><Term k="effect">Effect size</Term></dt><dd className="num m-0 text-right">{ac.effect_size === null ? '—' : `${fix(ac.effect_size, 2)} SD`}</dd>
            </dl>
            <div className="label mt-4 mb-1">Method agreement</div>
            <ul className="list-none p-0 m-0 text-[13px] grid gap-1">
              <li className="flex justify-between"><span className="text-muted">Parametric test</span><span className="num">{ac.methods ? (ac.methods.parametric ? 'agrees' : 'disagrees') : 'not run'}</span></li>
              <li className="flex justify-between"><span className="text-muted">GBM rank</span><span className="num">{ac.gbm_rank ?? '—'} of {matrix.cells.length}</span></li>
              <li className="flex justify-between"><span className="text-muted">NID rank</span><span className="num">{ac.nid_rank ?? '—'} of {matrix.cells.length}</span></li>
            </ul>
            {ac.category === 'selected' && <div className="num text-[11px] text-signal mt-3">CLICK TO OPEN THE RESPONSE SURFACE</div>}
          </>
        ) : <p className="text-sm text-muted m-0">Hover or focus a cell.</p>}
      </aside>
    </div>
  );
}

