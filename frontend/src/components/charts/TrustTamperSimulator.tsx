import { useEffect, useMemo, useState, type ReactNode } from 'react';
import { motion } from 'framer-motion';
import { useMutation, useQuery } from '@tanstack/react-query';
import { api, ApiError, type Check, type Dataset, type LedgerVerify, type TamperResult } from '../../lib/api';
import { useDatasets, useReducedMotion } from '../../lib/hooks';
import { shortHash, titleCase, int, sci } from '../../lib/format';
import { HashGlyph } from '../HashRing';
import { ProvenanceTag } from '../Provenance';
import { Skeleton, ErrorState } from '../States';
import { Term } from '../Term';
import { bannerFor, hashDiff, isHex64, issueLabel, summariseDetectors } from './trustLogic';

type FullResult = TamperResult & { original_file_sha?: string; tampered_file_sha?: string };
interface Outcome { r: FullResult; ledger: LedgerVerify | null; ledgerError: boolean }

// Magnitude is a fraction of rows/cells for the data-editing modes only.
const NO_MAGNITUDE = new Set(['bit_flip', 'swap_model', 'ledger_tamper']);
const PHASES = [700, 1000, 900, 900, 1200, 900]; // ms spent on each step of the sequence
const LAST = PHASES.length;

function explainError(e: unknown): { title: string; body: string } {
  if (e instanceof ApiError) {
    if (e.status === 429) return { title: 'RATE LIMIT REACHED', body: 'The simulator allows 20 attacks per minute so the API stays responsive. Wait a few seconds and launch again.' };
    if (e.status === 400) return { title: 'THIS ATTACK CANNOT RUN HERE', body: `${e.message}. Try another attack mode or dataset; nothing was modified.` };
    if (e.status === 404) return { title: 'NOT FOUND', body: `${e.message}. The dataset file or ledger needed for this attack is not available on the server.` };
    if (e.status === 422) return { title: 'INVALID SETTINGS', body: `${e.message}. Check the magnitude is between 0.001 and 0.5.` };
    if (e.status >= 500) return { title: 'THE SIMULATOR FAILED ON THIS COMBINATION', body: 'The server could not complete this attack (internal error). It works on a temporary copy, so no real data or ledger block was touched. Try another dataset or mode.' };
  }
  return { title: 'REQUEST FAILED', body: (e as Error)?.message ?? 'Unknown error' };
}

/* ------------------------------------------------------------------ hash display */
function HashHex({ hash, diff, tone }: { hash: string; diff?: ReturnType<typeof hashDiff>; tone?: string }) {
  if (!isHex64(hash)) return <span className="num text-sm break-all" style={{ color: tone }}>{hash}</span>;
  const chars = diff ? diff.chars : [...hash].map((c) => ({ c, diff: false }));
  const rows = [chars.slice(0, 32), chars.slice(32)];
  return (
    <span className="num block leading-[1.7] tracking-[0.04em] text-[12px] sm:text-[15px]" aria-label={`SHA-256 ${hash}${diff ? `, ${diff.count} characters differ from the original` : ''}`}>
      {rows.map((row, ri) => (
        <span key={ri} className="block">
          {row.map((x, i) => (
            <span key={i} className={x.diff ? 'text-alert font-semibold underline decoration-alert underline-offset-4 bg-alert/15' : 'text-text/80'}>{x.c}</span>
          ))}
        </span>
      ))}
    </span>
  );
}

function Step({ n, label, tone = 'signal', show, instant, children }: { n: string; label: string; tone?: 'signal' | 'alert' | 'biosphere' | 'solar'; show: boolean; instant: boolean; children: ReactNode }) {
  if (!show) return null;
  return (
    <motion.li
      initial={instant ? false : { opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.45, ease: [0.22, 1, 0.36, 1] }}
      className="relative pl-9 md:pl-12 pb-7 list-none min-w-0"
    >
      <span className="absolute left-0 top-0 grid place-items-center w-6 h-6 md:w-8 md:h-8 rounded-full border bg-void num text-[10px] md:text-xs" style={{ borderColor: `var(--${tone})`, color: `var(--${tone})` }}>{n}</span>
      <div className="label mb-2" style={{ color: `var(--${tone})` }}>{label}</div>
      {children}
    </motion.li>
  );
}

/* ------------------------------------------------------------------ mode specific views */
function ChainBreak({ ledger }: { ledger: NonNullable<TamperResult['ledger']> }) {
  const t = ledger.target_block;
  const idx = [t - 2, t - 1, t, t + 1, t + 2].filter((i) => i >= 0 && i < ledger.before.height);
  const W = 74, GAP = 46;
  const width = idx.length * W + (idx.length - 1) * GAP;
  return (
    <div className="grid md:grid-cols-2 gap-5 [&>*]:min-w-0">
      {[{ k: 'BEFORE', ok: ledger.before.valid, sub: `height ${int(ledger.before.height)} · head ${shortHash(ledger.before.head)}`, issues: [] as { index: number; code: string; detail: string }[] },
        { k: 'AFTER (one payload edited)', ok: ledger.after.valid, sub: `height ${int(ledger.after.height)} · ${ledger.after.issues.length} issue${ledger.after.issues.length === 1 ? '' : 's'}`, issues: ledger.after.issues }].map((s) => (
        <div key={s.k} className={`border px-4 py-3 ${s.ok ? 'border-biosphere/50' : 'border-alert/70 hatch-alert'}`}>
          <div className="label">Copy of the ledger · {s.k}</div>
          <div className={`display text-xl mt-1 ${s.ok ? 'text-biosphere' : 'text-alert'}`}>{s.ok ? '● CHAIN VALID' : '⊘ CHAIN BROKEN'}</div>
          <div className="num text-xs text-muted mt-1">{s.sub}</div>
          {s.issues.map((i) => (
            <div key={i.index + i.code} className="mt-2 border-t border-line pt-2">
              <div className="num text-xs text-alert">BLOCK {i.index} · {i.code}</div>
              <div className="text-[13px] text-text/90">{issueLabel(i.code)}.</div>
              <div className="num text-[10px] text-faint break-all mt-1">{i.detail}</div>
            </div>
          ))}
        </div>
      ))}
      <div className="md:col-span-2 overflow-x-auto" tabIndex={0} aria-label="Chain around the edited block">
        <svg width={width + 20} height="110" viewBox={`-10 0 ${width + 20} 110`} className="block mx-auto" role="img" aria-label={`Blocks ${idx.join(', ')}: block ${t} was edited and its link to the next block is broken`}>
          {idx.map((i, k) => {
            const x = k * (W + GAP), bad = i === t;
            return (
              <g key={i}>
                <rect x={x} y="20" width={W} height="52" fill={bad ? 'rgba(255,77,94,0.16)' : 'var(--void)'} stroke={bad ? 'var(--alert)' : 'var(--line-strong)'} strokeWidth="1.2" />
                <text x={x + W / 2} y="42" textAnchor="middle" className="num" fontSize="11" fill={bad ? 'var(--alert)' : 'var(--muted)'}>BLOCK</text>
                <text x={x + W / 2} y="60" textAnchor="middle" className="num" fontSize="16" fill={bad ? 'var(--alert)' : 'var(--text)'}>{i}</text>
                {bad && <text x={x + W / 2} y="92" textAnchor="middle" className="num" fontSize="10" fill="var(--alert)">PAYLOAD EDITED</text>}
                {k < idx.length - 1 && (
                  i >= t ? (
                    <g>
                      <line x1={x + W} y1="46" x2={x + W + GAP / 2 - 6} y2="46" stroke="var(--alert)" strokeWidth="1.4" strokeDasharray="3 3" />
                      <path d={`M${x + W + GAP / 2 - 3} 40 l6 12 M${x + W + GAP / 2 + 3} 40 l-6 12`} stroke="var(--alert)" strokeWidth="1.6" />
                      <line x1={x + W + GAP / 2 + 6} y1="46" x2={x + W + GAP} y2="46" stroke="var(--alert)" strokeWidth="1.4" strokeDasharray="3 3" />
                    </g>
                  ) : <line x1={x + W} y1="46" x2={x + W + GAP} y2="46" stroke="var(--biosphere)" strokeWidth="1.4" />
                )}
              </g>
            );
          })}
        </svg>
        <p className="text-center text-xs text-muted m-0">Links to and after the edited block can no longer be trusted. Neighbouring blocks are drawn for context only.</p>
      </div>
    </div>
  );
}

function ModelChecks({ model }: { model: NonNullable<TamperResult['model']> }) {
  return (
    <div className="grid md:grid-cols-2 gap-5 [&>*]:min-w-0">
      {([['BEFORE', model.before], ['AFTER (weights perturbed)', model.after]] as const).map(([k, m]) => (
        <div key={k} className={`border px-4 py-3 ${m.ok ? 'border-biosphere/50' : 'border-alert/70 hatch-alert'}`}>
          <div className="label">Model verification · {k}</div>
          <div className={`display text-lg mt-1 ${m.ok ? 'text-biosphere' : 'text-alert'}`}>{m.ok ? '● MODEL VERIFIED' : '⊘ MODEL REJECTED'}</div>
          <ul className="m-0 p-0 list-none mt-2 space-y-2">
            {m.checks.map((c) => (
              <li key={c.name} className="border-t border-line pt-2">
                <div className={`num text-xs tracking-[0.1em] ${c.ok ? 'text-biosphere' : 'text-alert'}`}>{c.ok ? '● PASS' : '⊘ FAIL'} · {c.name}</div>
                <div className="text-[12px] text-muted num break-words">{c.detail}</div>
              </li>
            ))}
          </ul>
        </div>
      ))}
    </div>
  );
}

function DetectorCard({ d }: { d: Check }) {
  const fired = d.status !== 'PASS';
  const tone = d.status === 'FAIL' ? 'var(--alert)' : d.status === 'WARN' ? 'var(--solar)' : 'var(--teal)';
  return (
    <li className="border border-line bg-void/50 px-3 py-2.5 list-none" style={{ borderLeft: `2px solid ${tone}` }}>
      <div className="flex items-center gap-2 flex-wrap">
        <span className="num text-xs tracking-[0.1em]" style={{ color: tone }}>{d.status === 'PASS' ? '● PASS' : d.status === 'WARN' ? '▲ WARN' : '⊘ FAIL'}</span>
        <span className="num text-sm">{d.name}</span>
        <span className="flex-1" />
        <span className={`num text-[10px] tracking-[0.14em] border px-1.5 py-0.5 ${d.blocking ? 'text-alert border-alert/70' : 'text-muted border-line-strong'}`} title={d.blocking ? 'An integrity-critical check: a failure blocks the result.' : 'A statistical detector: it warns but cannot block a result on its own.'}>
          {d.blocking ? 'BLOCKING' : 'ADVISORY'}
        </span>
      </div>
      <div className="text-[12px] text-muted mt-1 leading-snug">{d.detail}</div>
      <div className="num text-[10px] text-faint mt-1">score {sci(d.score, 3)}{fired ? ' · fired' : ' · quiet'}</div>
    </li>
  );
}

/* ------------------------------------------------------------------ the animated sequence */
function Sequence({ o, instant, onDone }: { o: Outcome; instant: boolean; onDone: () => void }) {
  const { r, ledger } = o;
  const [step, setPhase] = useState(0);
  const [cmpOpen, setCmpOpen] = useState(false);
  const phase = instant ? LAST : step;
  useEffect(() => {
    if (instant) return;
    if (phase >= LAST) { onDone(); return; }
    const t = setTimeout(() => setPhase((p) => p + 1), PHASES[phase]);
    return () => clearTimeout(t);
  }, [phase, instant, onDone]);

  const diff = useMemo(() => hashDiff(r.original_hash, r.tampered_hash), [r]);
  const banner = bannerFor(r);
  const sum = summariseDetectors(r.detectors ?? []);
  const ledgerMode = !!r.ledger, modelMode = !!r.model;
  const animate = !instant;
  const done = phase >= LAST;

  return (
    <div>
      <div className="flex items-center gap-3 mb-4">
        <span className="label !text-alert">LIVE RESPONSE · {titleCase(r.mode)} on {r.dataset_id}</span>
        <span className="flex-1 h-px bg-line" />
        {!done && <button type="button" onClick={() => setPhase(LAST)} className="num text-[11px] tracking-[0.14em] border border-line-strong px-2.5 py-1 text-muted hover:text-text">SKIP ANIMATION</button>}
      </div>
      <ol className="m-0 p-0 relative min-w-0">
        <span className="absolute left-[11px] md:left-[15px] top-2 bottom-4 w-px bg-line-strong" aria-hidden />
        <Step n="1" label={ledgerMode ? 'LEDGER HEAD HASH (COPY, BEFORE)' : modelMode ? 'REGISTERED MODEL WEIGHTS HASH' : 'ORIGINAL HASH · RECORDED IN THE LEDGER'} show={phase >= 0} instant={!animate}>
          <div className="flex items-start gap-4">
            <HashGlyph hash={isHex64(r.original_hash) ? r.original_hash : ''} size={56} />
            <div className="min-w-0"><HashHex hash={r.original_hash} /></div>
          </div>
          <div className="num text-xs text-signal mt-3 tracking-[0.14em]">ANALYSIS {done || phase >= 1 ? '→ RECOMPUTE THE FINGERPRINT' : '…'}</div>
        </Step>

        <Step n="2" label={ledgerMode ? 'WHAT THE CHAIN CHECK REPORTED' : modelMode ? 'WHAT THE MODEL CHECK FOUND' : 'MODIFIED HASH · AFTER THE ATTACK'} tone="alert" show={phase >= 1} instant={!animate}>
          <div className="flex items-start gap-4">
            {diff && <HashGlyph hash={r.tampered_hash} size={56} tone="var(--alert)" />}
            <div className="min-w-0"><HashHex hash={r.tampered_hash} diff={diff} tone="var(--alert)" /></div>
          </div>
          {diff ? (
            <div className="num text-sm mt-3"><span className="text-alert text-xl">{diff.count}</span> <span className="text-muted">of 64 characters differ from the original ({Math.round((diff.count / 64) * 100)}%). One small edit rewrote almost the whole fingerprint.</span></div>
          ) : (
            <div className="text-xs text-muted mt-2">This attack is not a file edit, so there is no second digest to compare character by character; the value above is what the verifier reported.</div>
          )}
          {r.original_file_sha && r.tampered_file_sha && (
            <div className="num text-[10px] text-faint mt-2 break-all">file SHA-256 {shortHash(r.original_file_sha, 10, 6)} → {shortHash(r.tampered_file_sha, 10, 6)}</div>
          )}
        </Step>

        <Step n="3" label="COMPARE" tone="alert" show={phase >= 2} instant={!animate}>
          <button type="button" aria-expanded={cmpOpen} aria-controls="cmp-detail" onClick={() => setCmpOpen((o) => !o)}
            className={`inline-flex items-center gap-3 num text-sm tracking-[0.14em] border px-4 py-2 cursor-pointer hover:bg-white/[0.04] ${r.hash_match ? 'text-biosphere border-biosphere' : 'text-alert border-alert hatch-alert'}`}>
            <svg width="38" height="14" viewBox="0 0 38 14" aria-hidden><path d="M0 7h32M26 1l7 6-7 6" fill="none" stroke="currentColor" strokeWidth="1.6" /></svg>
            {r.hash_match ? 'HASHES MATCH' : 'HASH MISMATCH'}
            <span aria-hidden className="text-xs">{cmpOpen ? '▲' : '▼'}</span>
          </button>
          {cmpOpen && (
            <div id="cmp-detail" className="mt-3 max-w-xl border-l-2 border-line-strong pl-4 text-[13px] text-muted leading-relaxed">
              {r.hash_match
                ? 'The fingerprint recomputed after the attack is identical to the one recorded in the ledger, so nothing the fingerprint covers has changed.'
                : <>SYNERA recomputed the fingerprint and compared it with the one recorded in the ledger. They are different{diff ? <>: <span className="num text-alert">{diff.count} of 64</span> characters changed</> : ''}. Any difference at all, even one flipped bit, means the data is not what was registered, so the result is blocked from VERIFIED.</>}
            </div>
          )}        </Step>

        <Step n="4" label="ALERT" tone="alert" show={phase >= 3} instant={!animate}>
          <div className={`display text-2xl md:text-4xl font-semibold uppercase ${r.hash_match ? 'text-biosphere' : 'text-alert'}`} role="alert">
            {r.hash_match ? 'No integrity alert' : 'Integrity alert'}
          </div>
          <p className="text-sm text-muted m-0 mt-1 max-w-xl">{r.description}</p>
        </Step>

        <Step n="5" label={ledgerMode ? 'LEDGER COPY: BEFORE AND AFTER' : modelMode ? 'MODEL CHECKS: BEFORE AND AFTER' : 'DID THE STATISTICAL DETECTORS NOTICE?'} tone="solar" show={phase >= 4} instant={!animate}>
          {r.ledger && <ChainBreak ledger={r.ledger} />}
          {r.model && <ModelChecks model={r.model} />}
          {!ledgerMode && !modelMode && (
            <div>
              {sum.total > 0 ? (
                <>
                  <p className="m-0 mb-3 text-[15px]">
                    <span className="num text-2xl" style={{ color: sum.fired ? 'var(--solar)' : 'var(--muted)' }}>{sum.fired}</span>
                    <span className="num text-muted"> of {sum.total} statistical detectors fired</span>
                    <span className="text-muted"> ({sum.blockingFired} blocking, {sum.advisoryFired} advisory). Statistical detectors are <Term k="baseline">baseline</Term> comparisons: they can warn, but only integrity checks can block.</span>
                  </p>
                  <ul className="m-0 p-0 grid sm:grid-cols-2 xl:grid-cols-3 gap-2">{r.detectors.map((d) => <DetectorCard key={d.name} d={d} />)}</ul>
                </>
              ) : <p className="m-0 text-sm text-muted">No statistical detector ran for this attack: the cryptographic check is the whole defence here.</p>}
              {r.hash_only && (
                <div className="mt-4 border border-solar px-4 py-3 bg-solar/10" role="status">
                  <div className="display text-lg text-solar tracking-wide">ONLY THE CRYPTOGRAPHIC HASH CAUGHT THIS</div>
                  <div className="text-[13px] text-text/90">{banner.sub}</div>
                </div>
              )}
              {r.scan_notes && <div className="mt-3 border-l-2 border-line-strong pl-3"><div className="label">Scan notes</div><p className="m-0 text-[13px] text-muted num break-words">{r.scan_notes}</p></div>}
            </div>
          )}
          {(ledgerMode || modelMode) && r.scan_notes && <p className="mt-3 text-[13px] text-muted num">{r.scan_notes}</p>}
        </Step>

        <Step n="6" label="VERDICT" tone="alert" show={phase >= 5} instant={!animate}>
          <div className={`border-2 px-4 py-4 md:px-6 md:py-5 ${banner.blocked ? 'border-alert hatch-alert' : 'border-biosphere'}`}>
            <div className={`display font-semibold uppercase tracking-wide text-base md:text-2xl leading-snug ${banner.blocked ? 'text-alert' : 'text-biosphere'}`}>{banner.stamp}</div>
          </div>
          <LedgerLine ledger={ledger} error={o.ledgerError} r={r} />
        </Step>
      </ol>
    </div>
  );
}

function LedgerLine({ ledger, error, r }: { ledger: LedgerVerify | null; error: boolean; r: TamperResult }) {
  return (
    <div className="mt-4 flex flex-wrap items-center gap-x-6 gap-y-2 border-t border-line pt-3">
      {ledger ? (
        <div className={`num text-sm tracking-[0.12em] ${ledger.valid ? 'text-biosphere' : 'text-alert'}`} role="status">
          {ledger.valid ? '● REAL LEDGER STILL VALID' : '⊘ REAL LEDGER BROKEN'}
          <span className="text-muted ml-3">block height {int(ledger.height)}{ledger.issues.length ? ` · ${ledger.issues.length} issue(s)` : ''}</span>
        </div>
      ) : (
        <div className="num text-sm text-solar" role="status">{error ? 'The live ledger check could not be completed.' : 'Checking ledger…'}</div>
      )}
      <div className="text-xs text-muted">
        {r.original_untouched && r.temporary_copy
          ? 'This ran on a temporary copy; no real data or ledger block was touched.'
          : 'WARNING: the API did not confirm that the original was untouched.'}
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ the simulator */
export function TrustTamperSimulator() {
  const reduced = useReducedMotion();
  const ds = useDatasets();
  const modes = useQuery({ queryKey: ['security-modes'], queryFn: api.tamperModes, staleTime: Infinity });
  const [datasetId, setDatasetId] = useState<string | null>(null);
  const [mode, setMode] = useState<string | null>(null);
  const [magnitude, setMagnitude] = useState(0.05);
  const [seed, setSeed] = useState(1);
  const [runKey, setRunKey] = useState(0);
  const [animating, setAnimating] = useState(false);

  const run = useMutation<Outcome, unknown, { dataset_id: string; mode: string; magnitude: number; seed: number }>({
    mutationFn: async (b) => {
      const r = (await api.simulateTamper(b)) as FullResult;
      let ledger: LedgerVerify | null = null, ledgerError = false;
      try { ledger = await api.ledgerVerify(); } catch { ledgerError = true; } // live, after every simulation
      return { r, ledger, ledgerError };
    },
    onSuccess: () => { setRunKey((k) => k + 1); setAnimating(true); },
  });

  if (ds.isLoading || modes.isLoading) return <Skeleton h={260} />;
  if (ds.isError || modes.isError) return <ErrorState error={ds.error ?? modes.error} retry={() => { ds.refetch(); modes.refetch(); }} />;
  const datasets: Dataset[] = ds.data ?? [];
  const modeList = modes.data ?? [];
  const dsId = datasetId ?? (datasets.find((d) => d.provenance === 'REAL' && d.runnable) ?? datasets[0])?.id ?? '';
  const mId = mode ?? (modeList.find((m) => m.mode === 'subtle_edit') ?? modeList[0])?.mode ?? '';
  const noMag = NO_MAGNITUDE.has(mId);

  return (
    <div className="grid gap-8">
      {/* 1. dataset */}
      <fieldset className="border-0 p-0 m-0 min-w-0">
        <legend className="label mb-2 !text-signal p-0">1 · Choose what to attack</legend>
        <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-2" role="radiogroup" aria-label="Dataset">
          {datasets.map((d) => (
            <button key={d.id} type="button" role="radio" aria-checked={dsId === d.id} onClick={() => setDatasetId(d.id)}
              className={`text-left border px-3 py-2.5 cursor-pointer bg-void/40 ${dsId === d.id ? 'border-signal bg-signal/10' : 'border-line hover:border-line-strong'}`}>
              <div className="flex items-center gap-2"><span className="num text-sm">{d.id}</span><span className="flex-1" /><ProvenanceTag provenance={d.provenance} /></div>
              <div className="text-[12px] text-muted leading-snug mt-1 min-h-[2.4em]">{d.name}</div>
              <div className="num text-[10px] text-faint mt-1">SHA-256 {shortHash(d.hash, 10, 6)}</div>
            </button>
          ))}
        </div>
      </fieldset>

      {/* 2. mode */}
      <fieldset className="border-0 p-0 m-0 min-w-0">
        <legend className="label mb-2 !text-signal p-0">2 · Choose the attack</legend>
        <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-2" role="radiogroup" aria-label="Attack mode">
          {modeList.map((m) => (
            <button key={m.mode} type="button" role="radio" aria-checked={mId === m.mode} onClick={() => setMode(m.mode)}
              className={`text-left border px-3 py-2.5 cursor-pointer ${mId === m.mode ? 'border-alert bg-alert/10' : 'border-line hover:border-line-strong bg-void/40'}`}>
              <div className={`num text-xs tracking-[0.12em] ${mId === m.mode ? 'text-alert' : 'text-text'}`}>{m.mode.toUpperCase()}</div>
              <div className="text-[12px] text-muted leading-snug mt-1">{m.description}</div>
            </button>
          ))}
        </div>
      </fieldset>

      {/* 3. magnitude + launch */}
      <div className="flex flex-wrap items-end gap-x-8 gap-y-4">
        <div className={`flex-1 min-w-[240px] max-w-md ${noMag ? 'opacity-50' : ''}`}>
          <label htmlFor="trust-mag" className="label !text-signal block mb-1">3 · How much to change</label>
          <div className="flex items-center gap-4">
            <input id="trust-mag" type="range" min={0.001} max={0.5} step={0.001} value={magnitude} disabled={noMag} onChange={(e) => setMagnitude(Number(e.target.value))} className="flex-1 accent-[var(--alert)]" aria-valuetext={`${(magnitude * 100).toFixed(1)} percent of rows or cells`} />
            <span className="num text-lg w-20 text-right">{(magnitude * 100).toFixed(1)}%</span>
          </div>
          <div className="text-[11px] text-faint mt-1">{noMag ? 'This attack does not use a magnitude.' : 'Fraction of rows / cells altered (0.1% to 50%).'}</div>
        </div>
        <div>
          <label htmlFor="trust-seed" className="label block mb-1">Seed</label>
          <input id="trust-seed" type="number" min={0} step={1} value={seed} onChange={(e) => setSeed(Math.max(0, Math.floor(Number(e.target.value) || 0)))} className="num w-20 bg-void border border-line-strong px-2 py-1.5 text-sm" />
        </div>
        <button type="button" disabled={run.isPending || !dsId || !mId} onClick={() => run.mutate({ dataset_id: dsId, mode: mId, magnitude: noMag ? 0.05 : magnitude, seed })}
          className="num text-sm tracking-[0.14em] px-6 py-3 border border-alert bg-alert/15 text-alert hover:bg-alert/25 disabled:opacity-50 cursor-pointer">
          {run.isPending ? 'ATTACKING A COPY…' : '⚠ LAUNCH ATTACK'}
        </button>
      </div>

      {/* result */}
      <div aria-live="polite">
        {run.isPending && <Skeleton h={120} label="ATTACKING A TEMPORARY COPY" />}
        {run.isError && !run.isPending && (() => { const m = explainError(run.error); return (
          <div className="hatch-alert border border-alert/60 px-5 py-4" role="alert">
            <div className="num text-alert text-xs tracking-[0.16em] mb-1">{m.title}</div>
            <div className="text-sm text-text">{m.body}</div>
          </div>); })()}
        {run.data && !run.isPending && !run.isError && (
          <Sequence key={runKey} o={run.data} instant={reduced} onDone={() => setAnimating(false)} />
        )}
        {!run.data && !run.isPending && !run.isError && (
          <div className="border border-dashed border-line-strong px-5 py-6 text-sm text-muted">
            Pick a dataset and an attack, then launch. The sequence below replays what the API really returned: the two fingerprints, the alert, every detector, and a live re-check of the real ledger.
          </div>
        )}
        <span className="sr-only">{animating ? 'Simulation sequence playing' : ''}</span>
      </div>
    </div>
  );
}

