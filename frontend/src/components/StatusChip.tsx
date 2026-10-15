import type { Status } from '../lib/api';
import { STATUS_BLURB } from '../lib/format';

const TONE: Record<Status, string> = {
  CANDIDATE: 'text-signal', VALIDATED: 'text-teal', VERIFIED: 'text-biosphere', BLOCKED: 'text-alert', REJECTED: 'text-faint',
};

function Glyph({ status }: { status: Status }) {
  const c = 'currentColor';
  return (
    <svg width="14" height="14" viewBox="0 0 14 14" fill="none" aria-hidden>
      {status === 'CANDIDATE' && <circle cx="7" cy="7" r="5.2" stroke={c} strokeWidth="1.4" />}
      {status === 'VALIDATED' && (<><circle cx="7" cy="7" r="5.2" stroke={c} strokeWidth="1.4" /><path d="M7 1.8a5.2 5.2 0 0 1 0 10.4z" fill={c} /></>)}
      {status === 'VERIFIED' && (<><circle cx="7" cy="7" r="6" fill={c} /><path d="M4 7.2l2 2 4-4.4" stroke="var(--void)" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" /></>)}
      {status === 'BLOCKED' && (<><circle cx="7" cy="7" r="5.2" stroke={c} strokeWidth="1.4" /><path d="M3.3 10.7l7.4-7.4" stroke={c} strokeWidth="1.4" /></>)}
      {status === 'REJECTED' && <path d="M3 7h8" stroke={c} strokeWidth="1.6" strokeLinecap="round" />}
    </svg>
  );
}

/** Always a text label AND a glyph, never colour alone. */
export function StatusChip({ status, large = false }: { status: Status; large?: boolean }) {
  return (
    <span className={`inline-flex items-center gap-1.5 num tracking-[0.14em] ${large ? 'text-sm' : 'text-[10px]'} ${TONE[status]}`} title={STATUS_BLURB[status]}>
      <Glyph status={status} />
      {status}
    </span>
  );
}
