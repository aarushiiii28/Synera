import React from 'react';

export function Logo({ size = 24, className = '' }: { size?: number, className?: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" className={className} fill="none" xmlns="http://www.w3.org/2000/svg">
      <circle cx="12" cy="12" r="10" stroke="var(--line-strong)" strokeWidth="1.5" />
      <circle cx="12" cy="2" r="2" fill="var(--signal)" />
      <path d="M12 2 L12 12" stroke="var(--signal)" strokeWidth="1.5" strokeDasharray="2 2" />
      <circle cx="12" cy="12" r="1.5" fill="var(--biosphere)" />
    </svg>
  );
}

export function Wordmark({ className = '' }: { className?: string }) {
  return (
    <div className={`flex flex-col ${className}`}>
      <div className="font-display font-light text-text" style={{ fontSize: '1.5em', letterSpacing: '0.22em', lineHeight: 1 }}>SYNERA</div>
      <div className="font-sans text-[0.45em] uppercase text-muted tracking-widest mt-1">
        DISCOVER. VALIDATE. VERIFY. <span className="text-biosphere">ACT.</span>
      </div>
    </div>
  );
}
