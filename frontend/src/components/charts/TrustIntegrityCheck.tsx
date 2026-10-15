import { useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { api, type DatasetVerify } from '../../lib/api';
import { useDatasets } from '../../lib/hooks';
import { Async } from '../States';
import { ProvenanceTag } from '../Provenance';
import { HashGlyph } from '../HashRing';
import { hashDiff, isHex64 } from './trustLogic';
import { utc } from '../../lib/format';

function Hex({ hash, diff }: { hash: string; diff: ReturnType<typeof hashDiff> }) {
  const chars = diff ? diff.chars : [...hash].map((c) => ({ c, diff: false }));
  return (
    <span className="num block text-[12px] leading-[1.7] break-all">
      {chars.map((x, i) => <span key={i} className={x.diff ? 'text-alert font-semibold underline decoration-alert underline-offset-4' : 'text-text/80'}>{x.c}</span>)}
    </span>
  );
}

export function TrustIntegrityCheck() {
  const ds = useDatasets();
  const [id, setId] = useState<string | null>(null);
  const check = useMutation<DatasetVerify, unknown, string>({ mutationFn: (i) => api.verifyDataset(i) });
  const r = check.data;
  const diff = r && isHex64(r.expected_hash) && isHex64(r.actual_hash) ? hashDiff(r.expected_hash, r.actual_hash) : null;
  return (
    <div>
      <Async q={ds} h={80}>
        {(list) => {
          const cur = id ?? list[0]?.id ?? '';
          return (
            <div className="flex flex-wrap items-end gap-4">
              <div role="radiogroup" aria-label="Dataset to check" className="flex flex-wrap gap-2">
                {list.map((d) => (
                  <button key={d.id} type="button" role="radio" aria-checked={cur === d.id} onClick={() => { setId(d.id); check.reset(); }}
                    className={`border px-3 py-2 text-left cursor-pointer ${cur === d.id ? 'border-signal bg-signal/10' : 'border-line hover:border-line-strong'}`}>
                    <span className="num text-sm block">{d.id}</span>
                    <ProvenanceTag provenance={d.provenance} />
                  </button>
                ))}
              </div>
              <button type="button" disabled={!cur || check.isPending} onClick={() => check.mutate(cur)}
                className="num text-sm tracking-[0.14em] px-5 py-2.5 border border-teal bg-teal/10 text-teal hover:bg-teal/20 disabled:opacity-50 cursor-pointer">
                {check.isPending ? 'RECOMPUTING…' : 'RECOMPUTE AND COMPARE'}
              </button>
            </div>
          );
        }}
      </Async>
      <div className="mt-6" aria-live="polite">
        {check.isError && <div className="hatch-alert border border-alert/60 px-5 py-4 text-sm" role="alert">{(check.error as Error).message}</div>}
        {r && (
          <div>
            <div className={`display text-2xl md:text-3xl uppercase ${r.match ? 'text-biosphere' : 'text-alert'}`}>{r.match ? '● Hashes match' : '⊘ Hash mismatch'}</div>
            <p className="text-sm text-muted mt-1 mb-5 max-w-2xl">{r.detail}</p>
            <div className="grid md:grid-cols-2 gap-6">
              {[['EXPECTED · registered in the ledger' + (r.ledger_block !== null ? ` (block ${r.ledger_block})` : ''), r.expected_hash, false], ['RECOMPUTED · read from the file just now', r.actual_hash, true]].map(([label, h, isActual]) => (
                <div key={String(label)} className="border-l-2 pl-4" style={{ borderColor: r.match ? 'var(--biosphere)' : isActual ? 'var(--alert)' : 'var(--signal)' }}>
                  <div className="label mb-2">{label}</div>
                  <div className="flex items-start gap-3">
                    {isHex64(h) && <HashGlyph hash={String(h)} size={44} tone={isActual && !r.match ? 'var(--alert)' : undefined} />}
                    <Hex hash={String(h)} diff={isActual ? diff : null} />
                  </div>
                </div>
              ))}
            </div>
            <div className="num text-[11px] text-faint mt-4">checked {utc(r.checked_at)}{r.match ? '' : ' · a real mismatch is recorded in the ledger as an INTEGRITY_ALERT block'}</div>
            {r.verdict && <div className="mt-3 num text-sm text-alert tracking-[0.1em]">{r.verdict}</div>}
          </div>
        )}
      </div>
    </div>
  );
}
