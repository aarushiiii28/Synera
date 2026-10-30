import { PROV, qualityNote, type ProvClass, type Quality } from '../../lib/live';

/** The provenance of a value, on every value: REAL SENSOR, SIMULATED, HISTORICAL or DERIVED. */
export function ProvBadge({ prov, className = '' }: { prov: ProvClass; className?: string }) {
  const p = PROV[prov];
  return (
    <span title={p.tip} className={`inline-flex items-center gap-1.5 num text-[10px] tracking-[0.14em] whitespace-nowrap ${className}`} style={{ color: p.tone }}>
      <span aria-hidden className="w-1.5 h-1.5 rounded-full" style={{ background: p.tone }} />{prov}
    </span>
  );
}

export function QualityChip({ q }: { q: Quality }) {
  if (q === 'OK') return <span className="num text-[10px] tracking-[0.12em] text-biosphere" title={qualityNote(q)}>VALID</span>;
  const tone = q === 'MISSING' ? 'var(--alert)' : 'var(--solar)';
  return <span className="num text-[10px] tracking-[0.12em]" style={{ color: tone }} title={qualityNote(q)}>{q.replace(/_/g, ' ')}</span>;
}
