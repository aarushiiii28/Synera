import { useState } from 'react';
import { Term } from '../Term';

// Descriptive labels only (no data): the stages of a result's life and the real check that covers each attack.
const STAGES = ['DATA', 'MODEL', 'CODE', 'PIPELINE', 'VERSION', 'REPRODUCIBILITY'] as const;

const ATTACKS = [
  { stage: 0, at: 'on', name: 'Data tampering', short: 'SHA-256 dataset hash', covered: 'the SHA-256 dataset hash. Change one bit of the file and the fingerprint no longer matches the one registered in the ledger.' },
  { stage: 0, at: 'after', name: 'Data poisoning', short: 'Anomaly detectors', covered: 'the anomaly detectors (isolation forest, robust Mahalanobis, autoencoder, drift, duplicates). They are advisory: they warn, the hash is what blocks.' },
  { stage: 1, at: 'on', name: 'Model manipulation', short: 'Model hash + behaviour', covered: 'the model hash plus behavioural verification: the weights hash, the hold-out metric and a fixed set of probe predictions must all match.' },
  { stage: 3, at: 'before', name: 'Pipeline manipulation', short: 'Source-tree hash', covered: 'the source-tree hash and code-drift check. Every run records a hash of the code that produced it.' },
  { stage: 4, at: 'on', name: 'Version mismatch', short: 'Ledger chain', covered: 'the ledger chain. Dataset, model and experiment versions are recorded in order, each block carrying the hash of the one before.' },
  { stage: 5, at: 'on', name: 'Reproducibility failure', short: 'Replay', covered: 'replay. Every run is executed a second time from its recorded configuration and the two result hashes must be identical.' },
] as const;

/** Positions (0..1 across the strip) for each attack marker: on a stage, or on the link just after/before it. */
const posOf = (a: (typeof ATTACKS)[number]) => (a.stage + (a.at === 'after' ? 0.5 : a.at === 'before' ? -0.5 : 0)) / (STAGES.length - 1);

const ROW = [0, 1, 0, 1, 0, 1];

export function TrustAttackPath() {
  const [sel, setSel] = useState(0);
  const a = ATTACKS[sel];
  return (
    <div>
      <ol className="md:hidden m-0 p-0 list-none border-l border-line-strong ml-3" aria-label="Attack points along the path">
        {ATTACKS.map((x, i) => (
          <li key={x.name} className="pl-4 py-1.5 relative">
            <span className="absolute -left-[5px] top-[1.15rem] w-[9px] h-[9px] rounded-full bg-alert pulse-soft" aria-hidden />
            <button type="button" onClick={() => setSel(i)} onFocus={() => setSel(i)} aria-pressed={sel === i} className={`bg-transparent border-0 p-0 text-left cursor-pointer num text-xs tracking-[0.08em] ${sel === i ? 'text-alert' : 'text-muted'}`}>
              {i + 1}. {x.name.toUpperCase()} <span className="text-faint">· {STAGES[x.stage]}</span>
            </button>
          </li>
        ))}
      </ol>
      <div className="hidden md:block">
        <div className="relative mx-16" style={{ height: 250 }}>
          {/* The path itself */}
          <div className="absolute left-0 right-0 top-[46px] h-px bg-line-strong" aria-hidden />
          <svg className="absolute left-0 right-0 top-[40px] w-full h-3" preserveAspectRatio="none" viewBox="0 0 100 2" aria-hidden>
            <line x1="0" y1="1" x2="100" y2="1" stroke="var(--signal)" strokeWidth="1" strokeDasharray="1.5 2.5" vectorEffect="non-scaling-stroke" opacity="0.7" />
          </svg>
          {STAGES.map((s, i) => (
            <div key={s} className="absolute top-0 -translate-x-1/2 text-center" style={{ left: `${(i / (STAGES.length - 1)) * 100}%` }}>
              <div className="mx-auto grid place-items-center w-[44px] h-[44px] rounded-full border border-signal bg-void num text-[11px] text-signal">{String(i + 1).padStart(2, '0')}</div>
              <div className="num text-[10px] tracking-[0.12em] text-muted mt-2 whitespace-nowrap">{s}</div>
            </div>
          ))}
          {ATTACKS.map((x, i) => (
            <button
              key={x.name}
              type="button"
              aria-label={`Attack point ${i + 1}: ${x.name}. Covered by ${x.short}`}
              aria-pressed={sel === i}
              onMouseEnter={() => setSel(i)}
              onFocus={() => setSel(i)}
              onClick={() => setSel(i)}
              className="absolute -translate-x-1/2 bg-transparent border-0 p-0 cursor-pointer text-center group"
              style={{ left: `${posOf(x) * 100}%`, top: 84 }}
            >
              <span className="block mx-auto w-px bg-alert/60" style={{ height: ROW[i] ? 70 : 8 }} aria-hidden />
              <span className="relative grid place-items-center w-7 h-7 mx-auto">
                <span className="absolute inset-0 rounded-full bg-alert/30 pulse-soft" aria-hidden />
                <span className={`relative w-3.5 h-3.5 rounded-full border-2 ${sel === i ? 'bg-alert border-text' : 'bg-void border-alert'}`} />
              </span>
              <span className={`block num text-[10px] tracking-[0.08em] mt-1.5 max-w-[104px] leading-tight ${sel === i ? 'text-alert' : 'text-muted'}`}>
                {i + 1}. {x.name.toUpperCase()}
              </span>
            </button>
          ))}
        </div>
      </div>
      <div className="mt-2 border-l-2 border-biosphere pl-4 py-1 min-h-[4.5rem]" aria-live="polite">
        <div className="label !text-alert">ATTACK {sel + 1} · {a.name}</div>
        <p className="m-0 mt-1 text-[15px] leading-relaxed text-text/90 max-w-3xl">
          <span className="num text-biosphere text-xs tracking-[0.14em] mr-2">COVERED BY</span>
          {a.covered}
        </p>
      </div>
      <p className="mt-3 text-xs text-faint max-w-3xl">
        Hover, focus or tap a red point. The <Term k="hash">SHA-256 hash</Term> and the <Term k="ledger">ledger</Term> are what actually block a result; the anomaly detectors only warn.
      </p>
    </div>
  );
}

