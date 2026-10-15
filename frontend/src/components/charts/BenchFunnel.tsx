import type { BenchSnr } from './benchLogic';
import { FUNNEL_ORDER, SEGMENTS, STAGE_LABEL, fdrText, fdrVerdict, recallText, VERDICT_TONE, VERDICT_WORD } from './benchLogic';
import { useChartWidth } from './useChartWidth';
import { int } from '../../lib/format';

/** Where false discoveries die: one stacked bar per stage (true / proxy / hard decoy / easy decoy). */
export function BenchFunnel({ stages, target }: { stages: BenchSnr['stages']; target: number }) {
  const [ref, w] = useChartWidth(640);
  const rows = FUNNEL_ORDER.filter((k) => stages[k]);
  const max = Math.max(1, ...rows.map((k) => stages[k].discoveries));
  const barX = 0, barW = Math.max(120, w);
  return (
    <div ref={ref} className="w-full">
      <ol className="m-0 p-0 list-none grid gap-5">
        {rows.map((k, i) => {
          const s = stages[k];
          const v = fdrVerdict(s.fdr_strict, target);
          const total = s.discoveries;
          let acc = 0;
          return (
            <li key={k} className="grid gap-1.5">
              <div className="flex flex-wrap items-baseline gap-x-3">
                <span className="num text-[11px] text-signal">{String(i + 1).padStart(2, '0')}</span>
                <span className="display font-semibold text-[15px]">{STAGE_LABEL[k].short}</span>
                <span className="text-[12px] text-faint">{STAGE_LABEL[k].long}</span>
              </div>
              <svg width={barW} height="30" role="img"
                aria-label={`${STAGE_LABEL[k].short}: ${total} discoveries: ${SEGMENTS.map((g) => `${s[g.key]} ${g.label}`).join(', ')}`}>
                <line x1={barX} x2={barX + barW} y1="29.5" y2="29.5" stroke="var(--line)" />
                {total === 0 && <text x={barX + 2} y="19" className="num" fontSize="12" fill="var(--faint)">0 discoveries</text>}
                {SEGMENTS.map((g) => {
                  const n = s[g.key];
                  if (!n) return null;
                  const sw = (n / max) * (barW - 2);
                  const x0 = barX + (acc / max) * (barW - 2);
                  acc += n;
                  return (
                    <g key={g.key}>
                      <rect x={x0} y="2" width={Math.max(sw, 1)} height="24" fill={g.color} opacity={g.key === 'easy_decoy' ? 0.55 : 0.9} />
                      {sw > 34 && <text x={x0 + sw / 2} y="19" textAnchor="middle" className="num" fontSize="12" fontWeight="600" fill="var(--void)">{n}</text>}
                    </g>
                  );
                })}
              </svg>
              <dl className="m-0 grid grid-cols-2 sm:grid-cols-4 gap-x-6 gap-y-1 num text-[12px]">
                <div><dt className="label">Discoveries</dt><dd className="m-0 text-[15px]">{int(total)}</dd></div>
                <div><dt className="label">Strict FDR</dt><dd className="m-0 text-[15px]" style={{ color: VERDICT_TONE[v] }}>{fdrText(s.fdr_strict)} <span className="text-[10px] tracking-[0.1em]">{VERDICT_WORD[v]}</span></dd></div>
                <div><dt className="label">Proxy-aware FDR</dt><dd className="m-0 text-[15px]">{fdrText(s.fdr_proxy_aware)}</dd></div>
                <div><dt className="label">Recall</dt><dd className="m-0 text-[15px]">{recallText(s.recall)}</dd></div>
              </dl>
            </li>
          );
        })}
      </ol>
    </div>
  );
}
