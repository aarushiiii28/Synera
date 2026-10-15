/** SYNERA mark: an orbit ring, a bright node on it, and a hairline converging on the cell at the centre. */
export function Logo({ size = 24, className = '' }: { size?: number; className?: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" className={className} fill="none" aria-hidden>
      <circle cx="12" cy="12" r="10" stroke="var(--line-strong)" strokeWidth="1.2" />
      <path d="M12 2.4V11" stroke="var(--signal)" strokeWidth="1.2" strokeDasharray="1.6 1.6" />
      <circle cx="12" cy="2.2" r="1.9" fill="var(--signal)" />
      <circle cx="12" cy="12" r="2.1" fill="var(--biosphere)" />
      <circle cx="12" cy="12" r="4.2" stroke="var(--biosphere)" strokeOpacity="0.35" strokeWidth="0.8" />
    </svg>
  );
}

export function Wordmark({ size = 22, tagline = true }: { size?: number; tagline?: boolean }) {
  return (
    <div className="flex flex-col leading-none">
      <span className="display font-light text-text" style={{ fontSize: size, letterSpacing: '0.24em' }}>SYNERA</span>
      {tagline && (
        <span className="mt-1.5 text-[8.5px] tracking-[0.2em] text-muted uppercase whitespace-nowrap">
          Discover. Validate. Verify. <span className="text-biosphere">Act.</span>
        </span>
      )}
    </div>
  );
}
