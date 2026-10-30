import { qualityNote, type Quality } from '../../lib/live';

export function QualityChip({ q }: { q: Quality }) {
  if (q === 'OK') return <span className="num text-[10px] tracking-[0.12em] text-biosphere" title={qualityNote(q)}>VALID</span>;
  const tone = q === 'MISSING' ? 'var(--alert)' : 'var(--solar)';
  return <span className="num text-[10px] tracking-[0.12em]" style={{ color: tone }} title={qualityNote(q)}>{q.replace(/_/g, ' ')}</span>;
}
