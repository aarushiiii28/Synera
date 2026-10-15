import type { BenchSnr } from './benchLogic';
import { pct } from '../../lib/format';
import { TYPE_COLOR } from '../../lib/format';
import { useChartWidth } from './useChartWidth';

const KINDS = ['SYNERGISTIC', 'ANTAGONISTIC', 'NONLINEAR'];
const STAGES: { k: string; label: string }[] = [{ k: 'conditional', label: 'after conditional selection' }, { k: 'full_stack', label: 'full stack' }];

/** Recall by interaction type: share of simulated datasets where the planted interaction was found, and found with the right type. */
export function BenchRecall({ rbt }: { rbt: BenchSnr['recall_by_type'] }) {
  const [ref, w] = useChartWidth(420);
  const kinds = KINDS.filter((k) => Object.values(rbt).some((st) => st[k]));
  const stages = STAGES.filter((s) => rbt[s.k]);
  if (!kinds.length || !stages.length) return null;
  const labelW = 138, bw = Math.max(60, w - labelW - 44), rowH = 20;
  const blockH = stages.length * 2 * rowH + 36;
  const H = kinds.length * blockH + 6;
  return (
    <div ref={ref}>
      <svg width={w} height={H} role="img" aria-label={`Recall by interaction type. ${kinds.map((k) => `${k}: ${stages.map((s) => `${s.label} detected ${pct(rbt[s.k][k]?.detected, 0)}, correct type ${pct(rbt[s.k][k]?.detected_and_typed_correctly, 0)}`).join('; ')}`).join('. ')}`}>
        {kinds.map((k, ki) => (
          <g key={k} transform={`translate(0 ${ki * blockH})`}>
            <text x="0" y="14" className="num" fontSize="11" fill={TYPE_COLOR[k]}>{k}</text>
            {stages.map((s, si) => {
              const d = rbt[s.k]?.[k];
              return [
                { v: d?.detected, lab: 'found', y: (si * 2) * rowH },
                { v: d?.detected_and_typed_correctly, lab: 'right type', y: (si * 2 + 1) * rowH },
              ].map((b) => (
                <g key={`${s.k}${b.lab}`} transform={`translate(${labelW} ${b.y + 24})`}>
                  <rect width={bw} height="12" fill="var(--hull-2)" opacity="0.5" />
                  {b.v !== undefined && <rect width={Math.max(0, b.v) * bw} height="12" fill={TYPE_COLOR[k]} opacity={b.lab === 'found' ? 0.9 : 0.5} />}
                  <text x={bw + 6} y="10.5" className="num" fontSize="11" fill="var(--text)">{b.v === undefined ? '—' : pct(b.v, 0)}</text>
                  <text x="-6" y="10.5" textAnchor="end" className="num" fontSize="10" fill="var(--faint)">{s.k === 'full_stack' ? 'full stack' : 'conditional'} · {b.lab}</text>
                </g>
              ));
            })}
          </g>
        ))}
      </svg>
    </div>
  );
}
