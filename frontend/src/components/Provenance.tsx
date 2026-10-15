import type { Provenance, EvidenceLevel } from '../lib/api';

/** REAL = green dot. SIMULATED = amber dot with the word, on every relevant panel. */
export function ProvenanceTag({ provenance, className = '' }: { provenance: Provenance; className?: string }) {
  const real = provenance === 'REAL';
  return (
    <span
      className={`inline-flex items-center gap-1.5 num text-[10px] tracking-[0.14em] ${real ? 'text-biosphere' : 'text-solar'} ${className}`}
      title={real ? 'Measured data' : 'Simulated by SYNERA with a known answer — measures the engine, not nature'}
    >
      <span className={`w-1.5 h-1.5 rounded-full ${real ? 'bg-biosphere' : 'bg-solar'}`} aria-hidden />
      {real ? 'REAL DATA' : 'SIMULATED'}
    </span>
  );
}

const EV: Record<EvidenceLevel, { label: string; tone: string; tip: string }> = {
  INDEPENDENT_REPLICATION: { label: 'INDEPENDENT REPLICATION', tone: 'text-biosphere', tip: 'Replicated in a separate dataset.' },
  CROSS_TISSUE_SAME_COHORT: { label: 'CROSS-TISSUE · SAME COHORT', tone: 'text-solar', tip: 'Same animals, two tissues: a consistency check, not independent replication.' },
  INTERNAL_REPLICATION: { label: 'INTERNAL REPLICATION', tone: 'text-solar', tip: 'Replicated inside the same dataset (e.g. held-out cities).' },
  HYPOTHESIS_ONLY: { label: 'HYPOTHESIS ONLY', tone: 'text-alert', tip: 'No replication. A hypothesis, not a result.' },
};

export function EvidenceTag({ level }: { level: EvidenceLevel }) {
  const e = EV[level];
  return (
    <span className={`num text-[10px] tracking-[0.14em] border border-current px-1.5 py-0.5 ${e.tone}`} title={e.tip}>
      {e.label}
    </span>
  );
}
