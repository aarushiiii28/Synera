import { useEffect, useRef, useState, type ReactNode } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useMutation, useQuery } from '@tanstack/react-query';
import { api, ApiError, type Block, type LedgerVerify } from '../../lib/api';
import { useReducedMotion } from '../../lib/hooks';
import { HashGlyph } from '../HashRing';
import { Async, ErrorState, Skeleton, EmptyState } from '../States';
import { Term } from '../Term';
import { shortHash, utc, int, titleCase } from '../../lib/format';
import { issueLabel } from './trustLogic';

const BLOCK_TONE: Record<string, string> = {
  DATASET_REGISTERED: 'var(--signal)', MODEL_REGISTERED: 'var(--sun)', EXPERIMENT_RUN: 'var(--solar)',
  FINDING_VALIDATED: 'var(--teal)', FINDING_VERIFIED: 'var(--biosphere)', FINDING_REJECTED: 'var(--faint)', INTEGRITY_ALERT: 'var(--alert)',
};
const tone = (t: string) => BLOCK_TONE[t] ?? 'var(--muted)';
const CARD_W = 168, GAP = 36;

function KV({ k, children, mono = true }: { k: string; children: ReactNode; mono?: boolean }) {
  return (
    <div className="grid grid-cols-[110px_1fr] gap-3 py-1.5 border-b border-line items-baseline">
      <dt className="label">{k}</dt>
      <dd className={`m-0 text-[13px] break-all ${mono ? 'num' : ''}`}>{children}</dd>
    </div>
  );
}

function BlockDetail({ index, onProve, onClose }: { index: number; onProve: (h: string) => void; onClose: () => void }) {
  const q = useQuery({ queryKey: ['ledger-block', index], queryFn: () => api.ledgerBlock(index), retry: false });
  if (q.isLoading) return <Skeleton h={200} />;
  if (q.isError) {
    const nf = q.error instanceof ApiError && q.error.status === 404;
    return nf ? <EmptyState title={`No block ${index}`} tone="solar">The ledger has no block with that index.</EmptyState> : <ErrorState error={q.error} retry={() => q.refetch()} />;
  }
  const b = q.data as Block;
  const arts = Array.isArray(b.payload.artifact_hashes) ? (b.payload.artifact_hashes as string[]) : [];
  const { artifact_hashes: _omit, ...rest } = b.payload;
  void _omit;
  return (
    <div className="grid lg:grid-cols-[minmax(0,1.15fr)_minmax(0,1fr)] gap-8">
      <div>
        <div className="flex items-center gap-4 mb-3">
          <HashGlyph hash={b.block_hash} size={64} tone={tone(b.block_type)} />
          <div className="min-w-0">
            <div className="display text-2xl">BLOCK {b.index}</div>
            <div className="num text-xs tracking-[0.14em]" style={{ color: tone(b.block_type) }}>{b.block_type}</div>
          </div>
          <span className="flex-1" />
          <button type="button" onClick={onClose} className="num text-[11px] tracking-[0.14em] border border-line-strong px-2.5 py-1 text-muted hover:text-text cursor-pointer">CLOSE</button>
        </div>
        <dl className="m-0">
          <KV k="Time">{utc(b.timestamp)}</KV>
          <KV k="Block hash">{b.block_hash}</KV>
          <KV k="Prev hash">{b.prev_hash}</KV>
          <KV k={'Merkle root'}>{b.merkle_root}</KV>
          <KV k="Payload hash">{b.payload_hash}</KV>
          <KV k="Signature">{shortHash(b.signature, 16, 8)}</KV>
          <KV k="Signer">{shortHash(b.signer, 16, 8)}</KV>
          <KV k="Artifacts">{int(b.artifact_count)}</KV>
        </dl>
      </div>
      <div className="min-w-0">
        <div className="label mb-2">Payload (what this block recorded)</div>
        <dl className="m-0 mb-3">
          {Object.entries(rest).map(([k, v]) => (
            <KV key={k} k={titleCase(k)} mono={typeof v !== 'string'}>
              {typeof v === 'object' && v !== null ? <pre className="m-0 whitespace-pre-wrap text-[12px] text-muted font-[inherit]">{JSON.stringify(v, null, 1)}</pre> : String(v)}
            </KV>
          ))}
        </dl>
        {arts.length > 0 && (
          <div>
            <div className="label mb-1">Artifact hashes · <Term k="merkle">prove inclusion</Term></div>
            <ul className="m-0 p-0 list-none">
              {arts.map((h) => (
                <li key={h} className="flex items-center gap-2 py-1 border-b border-line">
                  <span className="num text-[11px] text-muted truncate">{shortHash(h, 14, 8)}</span>
                  <span className="flex-1" />
                  <button type="button" onClick={() => onProve(h)} className="num text-[10px] tracking-[0.12em] border border-signal text-signal px-2 py-0.5 hover:bg-signal/10 cursor-pointer">PROVE</button>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </div>
  );
}

export function TrustLedgerExplorer({ onProve }: { onProve: (hash: string) => void }) {
  const reduced = useReducedMotion();
  const [params, setParams] = useSearchParams();
  const blocksQ = useQuery({ queryKey: ['ledger-blocks-asc'], queryFn: () => api.ledgerBlocks({ order: 'asc', limit: 200 }) });
  const sel = params.get('block') !== null && /^\d+$/.test(params.get('block') ?? '') ? Number(params.get('block')) : null;
  const scroller = useRef<HTMLDivElement>(null);
  const [progress, setProgress] = useState<number | null>(null); // 0..1 while the verification sweep runs
  const [result, setResult] = useState<LedgerVerify | null>(null);

  const select = (i: number | null) => setParams((p) => { const n = new URLSearchParams(p); if (i === null) n.delete('block'); else n.set('block', String(i)); return n; }, { replace: true });

  const verify = useMutation<LedgerVerify, unknown, void>({
    mutationFn: async () => {
      setResult(null);
      const sweepMs = reduced ? 0 : 2400;
      const t0 = performance.now();
      let raf = 0;
      if (sweepMs) {
        const tick = (t: number) => {
          const k = Math.min(1, (t - t0) / sweepMs);
          setProgress(k);
          const el = scroller.current;
          if (el) el.scrollLeft = k * (el.scrollWidth - el.clientWidth);
          if (k < 1) raf = requestAnimationFrame(tick);
        };
        raf = requestAnimationFrame(tick);
      }
      const [v] = await Promise.all([api.ledgerVerify(), new Promise((r) => setTimeout(r, sweepMs))]);
      cancelAnimationFrame(raf);
      return v;
    },
    onSuccess: (v) => { setResult(v); setProgress(null); },
    onError: () => setProgress(null),
  });

  // Scroll a deep-linked block into view once the chain has loaded.
  useEffect(() => {
    if (sel === null || !blocksQ.data) return;
    const pos = blocksQ.data.items.findIndex((b) => b.index === sel);
    if (pos >= 0 && scroller.current) scroller.current.scrollTo({ left: Math.max(0, pos * (CARD_W + GAP) - 120), behavior: reduced ? 'auto' : 'smooth' });
  }, [sel, blocksQ.data, reduced]);

  return (
    <Async q={blocksQ} h={260}>
      {({ items, total }) => {
        const bad = new Set((result?.issues ?? []).map((i) => i.index));
        const types = [...new Set(items.map((b) => b.block_type))];
        const width = items.length * CARD_W + (items.length - 1) * GAP;
        return (
          <div>
            <div className="flex flex-wrap items-center gap-x-6 gap-y-3 mb-3">
              <button type="button" onClick={() => verify.mutate()} disabled={verify.isPending}
                className="num text-sm tracking-[0.14em] px-5 py-2.5 border border-teal bg-teal/10 text-teal hover:bg-teal/20 disabled:opacity-60 cursor-pointer">
                {verify.isPending ? 'SCANNING CHAIN…' : '⟲ VERIFY ENTIRE CHAIN'}
              </button>
              <span className="num text-xs text-muted">{int(total)} blocks · hash-linked · signed</span>
              <span className="flex-1" />
              <ul className="m-0 p-0 list-none flex flex-wrap gap-x-4 gap-y-1" aria-label="Block types">
                {types.map((t) => <li key={t} className="num text-[10px] tracking-[0.1em] flex items-center gap-1.5" style={{ color: tone(t) }}><span className="w-2 h-2" style={{ background: tone(t) }} aria-hidden />{t.replace(/_/g, ' ')}</li>)}
              </ul>
            </div>

            <div aria-live="polite" className="min-h-[2.25rem] mb-2">
              {verify.isError && <ErrorState error={verify.error} retry={() => verify.mutate()} />}
              {result && (
                <div className={`border px-4 py-2.5 ${result.valid ? 'border-biosphere/60' : 'border-alert hatch-alert'}`} role="status">
                  <span className={`num text-sm tracking-[0.14em] ${result.valid ? 'text-biosphere' : 'text-alert'}`}>{result.valid ? '● CHAIN VALID' : '⊘ CHAIN BROKEN'}</span>
                  <span className="num text-xs text-muted ml-4">block height {int(result.height)} · head {shortHash(result.head)} · {result.issues.length} issue{result.issues.length === 1 ? '' : 's'}</span>
                  {result.issues.map((i) => <div key={i.index + i.code} className="num text-xs text-alert mt-1">block {i.index} · {i.code}: {issueLabel(i.code)}</div>)}
                </div>
              )}
            </div>

            <div ref={scroller} tabIndex={0} aria-label="Evidence ledger, scroll horizontally" className="overflow-x-auto pb-4 border-y border-line bg-void/30">
              <div className="relative py-6 px-6" style={{ width: width + 48 }}>
                {/* the chain line */}
                <div className="absolute left-6 right-6 top-[74px] h-px bg-line-strong" aria-hidden />
                {progress !== null && <div className="absolute top-0 bottom-0 w-px bg-teal" style={{ left: 24 + progress * width, boxShadow: '0 0 14px 2px var(--teal)' }} aria-hidden />}
                <ol className="m-0 p-0 list-none flex relative" style={{ gap: GAP }}>
                  {items.map((b, k) => {
                    const checked = result ? true : progress !== null && (k + 0.5) / items.length <= progress;
                    const isBad = bad.has(b.index);
                    return (
                      <li key={b.index} style={{ width: CARD_W }} className="shrink-0">
                        <button type="button" onClick={() => select(sel === b.index ? null : b.index)} aria-pressed={sel === b.index} aria-label={`Block ${b.index}, ${b.block_type.replace(/_/g, ' ')}, ${utc(b.timestamp)}`}
                          className={`w-full text-left bg-void border px-3 py-3 cursor-pointer ${sel === b.index ? 'border-text' : isBad ? 'border-alert hatch-alert' : 'border-line hover:border-line-strong'}`}
                          style={{ borderTop: `2px solid ${isBad ? 'var(--alert)' : tone(b.block_type)}` }}>
                          <div className="flex items-center justify-between">
                            <span className="num text-xs text-faint">#{b.index}</span>
                            <span className={`num text-[10px] ${isBad ? 'text-alert' : 'text-teal'}`}>{isBad ? '⊘' : checked ? '✓' : ''}</span>
                          </div>
                          <div className="my-2"><HashGlyph hash={b.block_hash} size={52} tone={isBad ? 'var(--alert)' : undefined} /></div>
                          <div className="num text-[10px] tracking-[0.06em] leading-tight min-h-[2.4em]" style={{ color: tone(b.block_type) }}>{b.block_type.replace(/_/g, ' ')}</div>
                          <div className="num text-[10px] text-muted mt-1">{utc(b.timestamp).slice(5, 16)}</div>
                          <div className="num text-[10px] text-faint">{shortHash(b.block_hash, 6, 4)}</div>
                        </button>
                      </li>
                    );
                  })}
                </ol>
              </div>
            </div>

            <div className="mt-6">
              {sel !== null ? <BlockDetail key={sel} index={sel} onProve={onProve} onClose={() => select(null)} /> : <p className="text-sm text-muted m-0">Select a block to read what it recorded, how it links to the one before it, and who signed it.</p>}
            </div>
          </div>
        );
      }}
    </Async>
  );
}

