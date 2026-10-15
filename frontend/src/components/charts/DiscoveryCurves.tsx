import * as d3 from 'd3';
import type { InteractionType } from '../../lib/api';
import { TYPE_BLURB, TYPE_COLOR } from '../../lib/format';
import { Term } from '../Term';

// Schematic shapes only (a teaching picture, not data): dashed = sum of the separate effects, solid = combined response.
const SHAPE: Record<InteractionType, (t: number) => number> = {
  SYNERGISTIC: (t) => 0.1 + 0.8 * t + 0.25 * t * t,
  ANTAGONISTIC: (t) => 0.1 + 0.8 * t - 0.4 * Math.pow(t, 1.4),
  NONLINEAR: (t) => 0.1 + 0.8 / (1 + Math.exp(-11 * (t - 0.55))),
};
const SUM = (t: number) => 0.1 + 0.8 * t;

/** Small curve glyph for an interaction type. */
export function TypeGlyph({ type, size = 28 }: { type: InteractionType; size?: number }) {
  const ts = d3.range(0, 1.001, 0.05);
  const sx = (t: number) => 3 + t * 22, sy = (v: number) => 25 - v * 19;
  const line = d3.line<number>().x(sx).y((t) => sy(SHAPE[type](t)))(ts) ?? '';
  const sum = d3.line<number>().x(sx).y((t) => sy(SUM(t)))(ts) ?? '';
  return (
    <svg width={size} height={size} viewBox="0 0 28 28" aria-hidden className="shrink-0">
      <path d={sum} fill="none" stroke="var(--muted)" strokeWidth="1" strokeDasharray="2 2" />
      <path d={line} fill="none" stroke={TYPE_COLOR[type]} strokeWidth="2" strokeLinecap="round" />
    </svg>
  );
}

const DEFS: { type: InteractionType; term: string; word: string; sum: string }[] = [
  { type: 'SYNERGISTIC', term: 'synergistic', word: 'Combined > sum', sum: '1 + 1 > 2' },
  { type: 'ANTAGONISTIC', term: 'antagonistic', word: 'Combined < sum', sum: '1 + 1 < 2' },
  { type: 'NONLINEAR', term: 'nonlinear', word: 'Unpredictable response', sum: 'it switches or bends' },
];

export function DiscoveryCurves() {
  const ts = d3.range(0, 1.001, 0.02);
  const sx = (t: number) => 12 + t * 176, sy = (v: number) => 108 - v * 80;
  return (
    <ul className="list-none p-0 m-0 grid md:grid-cols-3 gap-x-8 gap-y-6">
      {DEFS.map((d) => {
        const col = TYPE_COLOR[d.type];
        const comb = d3.line<number>().x(sx).y((t) => sy(SHAPE[d.type](t)))(ts) ?? '';
        const sum = d3.line<number>().x(sx).y((t) => sy(SUM(t)))(ts) ?? '';
        return (
          <li key={d.type}>
            <svg viewBox="0 0 200 124" className="w-full max-w-[260px] h-auto" role="img" aria-label={`Schematic: ${d.word.toLowerCase()}. Dashed line is the sum of separate effects, solid is the combined response.`}>
              <line x1="12" y1="108" x2="190" y2="108" stroke="var(--line-strong)" /><line x1="12" y1="8" x2="12" y2="108" stroke="var(--line-strong)" />
              <path d={sum} fill="none" stroke="var(--muted)" strokeDasharray="4 3" />
              <path d={comb} fill="none" stroke={col} strokeWidth="2.4" />
              <text x="188" y="121" textAnchor="end" fontSize="9" fill="var(--faint)">both stressors rise</text>
              <text x="16" y="14" fontSize="9" fill="var(--faint)">response</text>
            </svg>
            <div className="mt-2 display font-semibold uppercase tracking-[0.1em] text-[13px]" style={{ color: col }}><Term k={d.term} /></div>
            <div className="num text-[12px] text-text/90">{d.word} <span className="text-faint">({d.sum})</span></div>
            <p className="text-[13.5px] text-muted leading-snug mt-1 mb-0 max-w-[16rem]">{TYPE_BLURB[d.type]}</p>
          </li>
        );
      })}
    </ul>
  );
}
