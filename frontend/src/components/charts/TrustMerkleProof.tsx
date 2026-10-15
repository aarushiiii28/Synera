import { useEffect, useRef, useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { api, ApiError, type MerkleProof } from '../../lib/api';
import { useDatasets, useReducedMotion } from '../../lib/hooks';
import { shortHash } from '../../lib/format';
import { Term } from '../Term';
import { isHex64 } from './trustLogic';

/** Leaf at the bottom, one sibling per level, root at the top. Intermediate digests are not returned by the API, so none are drawn. */
function ProofTree({ p, reveal }: { p: MerkleProof; reveal: number }) {
  const steps = p.merkle_proof;
  const rowH = 78, W = 640, cx = W / 2, top = 10;
  const levels = Math.max(steps.length, 1);
  const H = top + (levels + 1) * rowH + 40;
  const yOf = (lvl: number) => H - 50 - lvl * rowH; // lvl 0 = leaf
  const boxW = 200;
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full max-w-[640px] block" role="img" aria-label={`Merkle proof path: leaf, ${steps.length} sibling hashes, then the root of block ${p.block_index}`}>
      {/* path */}
      <line x1={cx} y1={yOf(0)} x2={cx} y2={yOf(levels)} stroke="var(--signal)" strokeWidth="1.4" />
      {/* root */}
      <g opacity={reveal > steps.length ? 1 : 0.25}>
        <rect x={cx - boxW / 2} y={yOf(levels) - 18} width={boxW} height="36" fill="var(--void)" stroke="var(--biosphere)" />
        <text x={cx} y={yOf(levels) - 3} textAnchor="middle" className="num" fontSize="9" fill="var(--biosphere)" letterSpacing="1.4">MERKLE ROOT · BLOCK {p.block_index}</text>
        <text x={cx} y={yOf(levels) + 11} textAnchor="middle" className="num" fontSize="11" fill="var(--text)">{shortHash(p.merkle_root, 12, 8)}</text>
      </g>
      {steps.map((s, i) => {
        const y = yOf(i + 1) + rowH / 2 + 0; // sibling joins the path between levels
        const left = s.side === 'L';
        const bx = left ? cx - 70 - boxW : cx + 70;
        const shown = reveal > i;
        return (
          <g key={i} opacity={shown ? 1 : 0.15}>
            <line x1={left ? bx + boxW : bx} y1={y} x2={cx} y2={y} stroke="var(--line-strong)" strokeWidth="1.2" />
            <rect x={bx} y={y - 18} width={boxW} height="36" fill="var(--void)" stroke="var(--line-strong)" />
            <text x={bx + 8} y={y - 4} className="num" fontSize="9" fill="var(--faint)" letterSpacing="1.4">SIBLING · LEVEL {i + 1} · {left ? 'LEFT' : 'RIGHT'}</text>
            <text x={bx + 8} y={y + 11} className="num" fontSize="11" fill="var(--muted)">{shortHash(s.hash, 10, 6)}</text>
            <circle cx={cx} cy={y} r="4" fill="var(--signal)" />
            <circle cx={cx} cy={yOf(i + 1)} r="0" />
          </g>
        );
      })}
      {/* leaf */}
      <g>
        <rect x={cx - boxW / 2} y={yOf(0) - 18} width={boxW} height="36" fill="var(--void)" stroke="var(--signal)" /><rect x={cx - boxW / 2} y={yOf(0) - 18} width={boxW} height="36" fill="rgba(22,181,255,0.1)" />
        <text x={cx} y={yOf(0) - 3} textAnchor="middle" className="num" fontSize="9" fill="var(--signal)" letterSpacing="1.4">LEAF · YOUR ARTIFACT</text>
        <text x={cx} y={yOf(0) + 11} textAnchor="middle" className="num" fontSize="11" fill="var(--text)">{shortHash(p.artifact_hash, 12, 8)}</text>
      </g>
    </svg>
  );
}

export function TrustMerkleProof({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  const reduced = useReducedMotion();
  const ds = useDatasets();
  const [reveal, setReveal] = useState(0);
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);
  const prove = useMutation<MerkleProof, unknown, string>({ mutationFn: (h) => api.ledgerProof(h.trim().toLowerCase()), onSuccess: () => setReveal(0) });
  const hash = value.trim();
  const valid = isHex64(hash);

  const data = prove.data;
  useEffect(() => {
    if (timer.current) clearInterval(timer.current);
    if (!data) return;
    const n = data.merkle_proof.length + 1;
    if (reduced) return;
    let k = 0;
    timer.current = setInterval(() => { k += 1; setReveal(k); if (k > n && timer.current) clearInterval(timer.current); }, 500);
    return () => { if (timer.current) clearInterval(timer.current); };
  }, [data, reduced]);

  const notRecorded = prove.error instanceof ApiError && prove.error.status === 404;
  return (
    <div className="grid lg:grid-cols-[minmax(0,420px)_1fr] gap-10">
      <div>
        <p className="text-sm text-muted mt-0 mb-4 max-w-md">A <Term k="merkle">Merkle proof</Term> shows that one artifact is included in a signed block, using only a handful of hashes instead of the whole block.</p>
        <label htmlFor="mp-hash" className="label block mb-1">Artifact SHA-256</label>
        <input id="mp-hash" value={value} onChange={(e) => onChange(e.target.value)} spellCheck={false} placeholder="paste a 64-character hash"
          className="num w-full bg-void border border-line-strong px-3 py-2 text-xs" aria-invalid={value !== '' && !valid} aria-describedby="mp-help" />
        <div id="mp-help" className="text-[11px] mt-1 min-h-[1.2em]" style={{ color: value && !valid ? 'var(--solar)' : 'var(--faint)' }}>
          {value && !valid ? `Needs 64 hexadecimal characters (has ${hash.length}).` : 'Or pick a registered dataset below.'}
        </div>
        <div className="flex flex-wrap gap-2 mt-2" role="group" aria-label="Registered datasets">
          {(ds.data ?? []).map((d) => (
            <button key={d.id} type="button" onClick={() => onChange(d.hash)} className={`num text-[11px] border px-2.5 py-1 cursor-pointer ${hash === d.hash ? 'border-signal text-signal bg-signal/10' : 'border-line-strong text-muted hover:text-text'}`}>{d.id}</button>
          ))}
        </div>
        <button type="button" disabled={!valid || prove.isPending} onClick={() => prove.mutate(hash)}
          className="mt-5 num text-sm tracking-[0.14em] px-5 py-2.5 border border-signal bg-signal/10 text-signal hover:bg-signal/20 disabled:opacity-50 cursor-pointer">
          {prove.isPending ? 'FETCHING PROOF…' : 'PROVE INCLUSION'}
        </button>
      </div>

      <div aria-live="polite" className="min-w-0">
        {!data && !prove.isError && <div className="border border-dashed border-line-strong px-5 py-8 text-sm text-muted">The proof path will be drawn here: your artifact at the bottom, the sibling hashes that lead upward, and the signed root at the top.</div>}
        {notRecorded && (
          <div className="border border-solar px-5 py-5 bg-solar/10" role="alert">
            <div className="num text-solar text-sm tracking-[0.14em] mb-1">NOT RECORDED IN THE LEDGER</div>
            <p className="m-0 text-sm text-text/90">No block contains this hash. Either the file was never registered, or it is not the exact registered file: any changed byte gives a different hash.</p>
          </div>
        )}
        {prove.isError && !notRecorded && <div className="hatch-alert border border-alert/60 px-5 py-4 text-sm" role="alert">{(prove.error as Error).message}</div>}
        {data && (
          <div>
            <div className="flex flex-wrap items-center gap-x-5 gap-y-1 mb-3">
              <span className={`num text-sm tracking-[0.14em] ${data.verified ? 'text-biosphere' : 'text-alert'}`}>{data.verified ? '● PROOF VERIFIED' : '⊘ PROOF DOES NOT VERIFY'}</span>
              <span className="num text-xs text-muted">block {data.block_index} · {data.block_type.replace(/_/g, ' ')} · {data.merkle_proof.length} sibling hash{data.merkle_proof.length === 1 ? '' : 'es'}</span>
            </div>
            <ProofTree p={data} reveal={reduced ? data.merkle_proof.length + 2 : reveal} />
            {data.merkle_proof.length === 0 && <p className="text-xs text-muted m-0">This block holds a single artifact, so the leaf is the root and no sibling is needed.</p>}
          </div>
        )}
      </div>
    </div>
  );
}

