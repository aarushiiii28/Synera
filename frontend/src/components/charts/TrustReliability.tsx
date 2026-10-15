import { useQuery } from '@tanstack/react-query';
import { api, type FalseAlarm } from '../../lib/api';
import { EmptyState, Async } from '../States';
import { Term } from '../Term';
import { pct, titleCase } from '../../lib/format';
import { heatModel } from './trustLogic';

const LABEL: Record<string, string> = { hash: 'SHA-256 hash', any_statistical: 'Any statistical detector', any_detector_warns: 'Any detector warns' };
const nice = (k: string) => LABEL[k] ?? titleCase(k);

/** Blue (silent) -> amber (fires). Value 0..1 mapped to opacity so zero is visibly empty. */
const cellColor = (v: number, hash: boolean) => `color-mix(in srgb, ${hash ? 'var(--biosphere)' : 'var(--solar)'} ${Math.round(8 + v * 80)}%, transparent)`;

function Body({ far }: { far: FalseAlarm }) {
  const m = heatModel(far);
  if (!m) return <EmptyState title="No measured reliability data" tone="solar">The API reported the benchmark as available but returned no attack grid.</EmptyState>;
  return (
    <div className="grid gap-10">
      <div className="grid lg:grid-cols-[minmax(0,360px)_1fr] gap-10">
        <div>
          <div className="label mb-3">Clean-data false alarms: how often each detector cries wolf on untouched data</div>
          <ul className="m-0 p-0 list-none space-y-2.5">
            {m.clean.map((c) => (
              <li key={c.name} className="grid grid-cols-[130px_1fr_46px] items-center gap-3" title={c.hits !== undefined ? `${c.hits} of ${c.trials} clean datasets raised this alarm${c.upper !== undefined ? ` (95% upper bound ${pct(c.upper, 1)})` : ''}` : undefined}>
                <span className="num text-[11px] text-muted truncate" title={nice(c.name)}>{c.name}</span>
                <span className="h-2 bg-line relative" role="img" aria-label={`${nice(c.name)} false-alarm rate ${pct(c.rate, 1)}`}>
                  <span className="absolute inset-y-0 left-0 bg-solar" style={{ width: `${Math.max(c.rate * 100, c.rate > 0 ? 1 : 0)}%` }} />
                </span>
                <span className="num text-xs text-right">{pct(c.rate, 1)}</span>
              </li>
            ))}
          </ul>
          <p className="text-xs text-faint mt-3">Measured on {far.clean_seeds ?? '—'} clean datasets. Each was a held-out half of the real weather panel that the detector's baseline had not seen. Hover a row for the count and its 95% upper bound. Zero means no alarm in those datasets, not that false alarms are impossible.</p>
        </div>

        <div className="border-l-2 border-solar pl-5 self-start">
          <div className="label !text-solar mb-1">Hash-only attacks</div>
          {far.hash_only_attacks && far.hash_only_attacks.length > 0 ? (
            <>
              <p className="text-sm text-muted m-0 mb-3">These attack and contamination levels were caught by the <Term k="hash">cryptographic hash</Term> every time, but by no statistical detector more than half of the time:</p>
              <ul className="m-0 p-0 list-none grid sm:grid-cols-2 gap-x-6 gap-y-1">
                {far.hash_only_attacks.map((h) => (
                  <li key={h.mode + h.contamination} className="num text-xs flex justify-between gap-3 border-b border-line py-1">
                    <span>{h.mode} @ {pct(h.contamination, h.contamination < 0.01 ? 1 : 0)}</span>
                    <span className="text-faint">best detector {pct(h.best_statistical_detection, 0)}</span>
                  </li>
                ))}
              </ul>
            </>
          ) : <p className="text-sm text-muted m-0">No attack cell was caught by the hash alone in this benchmark.</p>}
        </div>
      </div>

      <div>
        <div className="label mb-1">Detection rate: attack type (rows) by share of data contaminated (columns)</div>
        <p className="text-xs text-faint m-0 mb-4">Each small grid is one detector. A number is the share of trials in which it fired. Dark cells: it missed.</p>
        <div className="grid sm:grid-cols-2 xl:grid-cols-3 gap-x-8 gap-y-7">
          {m.detectors.map((d) => (
            <figure key={d} className="m-0 min-w-0">
              <figcaption className={`num text-[11px] tracking-[0.1em] mb-1.5 ${d === 'hash' ? 'text-biosphere' : 'text-muted'}`}>{nice(d).toUpperCase()}</figcaption>
              <div className="overflow-x-auto" role="table" aria-label={`Detection rate of ${nice(d)} by attack and contamination`}>
                <div className="grid gap-px min-w-[250px]" style={{ gridTemplateColumns: `minmax(86px,auto) repeat(${m.levels.length}, minmax(0,1fr))` }} role="row">
                  <span />
                  {m.levels.map((l) => <span key={l} className="num text-[10px] text-faint text-center" role="columnheader">{pct(Number(l), Number(l) < 0.01 ? 1 : 0)}</span>)}
                  {m.modes.map((mode) => (
                    <div key={mode} className="contents" role="row">
                      <span className="num text-[10px] text-muted self-center pr-2" role="rowheader">{mode}</span>
                      {m.levels.map((l) => {
                        const v = m.cell(d, mode, l);
                        return (
                          <span key={l} role="cell" className="num text-[10px] text-center py-1.5 border border-void" style={{ background: v === null ? 'transparent' : cellColor(v, d === 'hash') }} title={`${nice(d)} · ${mode} · ${pct(Number(l), 1)} contaminated: ${v === null ? 'not measured' : pct(v, 0)}`}>
                            {v === null ? '—' : Math.round(v * 100)}
                          </span>
                        );
                      })}
                    </div>
                  ))}
                </div>
              </div>
            </figure>
          ))}
        </div>
      </div>

      <div className="border border-line-strong px-5 py-4 bg-void/50">
        <div className="label !text-signal mb-1">The policy this measurement justifies</div>
        <p className="m-0 text-[15px] leading-relaxed">{far.policy ?? 'Statistical detectors are advisory; only integrity-critical checks can block a result.'}</p>
      </div>
    </div>
  );
}

export function TrustReliability() {
  const q = useQuery({ queryKey: ['false-alarms'], queryFn: api.falseAlarms });
  return (
    <Async q={q} h={240}>
      {(far) => far.available ? <Body far={far} /> : (
        <div className="grid gap-6">
          <EmptyState title="The reliability benchmark has not finished" tone="solar">
            Detection and false-alarm rates are measured by a long benchmark job (about 30 minutes). When it completes, a heatmap of every detector against every attack appears here. Until then no rates are shown rather than estimated ones.
          </EmptyState>
          <div className="border border-line-strong px-5 py-4 bg-void/50">
            <div className="label !text-signal mb-1">The policy, independent of the measurement</div>
            <p className="m-0 text-[15px] leading-relaxed">Statistical detectors are advisory: they warn. Only integrity-critical checks (hash, ledger chain, physical range, replay) can block a result.</p>
          </div>
        </div>
      )}
    </Async>
  );
}
