import React from 'react';

export function HashRing({ hash, size = 56 }: { hash: string; size?: number }) {
  const bytes = (hash.match(/.{2}/g) ?? []).slice(0, 32).map((h) => parseInt(h, 16));
  const c = size / 2;
  const r0 = size * 0.28;
  const r1 = size * 0.48;

  return (
    <div className="flex items-center gap-3">
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} role="img" aria-label={`Fingerprint ${hash.slice(0, 8)}`}>
        <circle cx={c} cy={c} r={r0 - 2} fill="none" stroke="var(--line-strong)" strokeWidth="1" />
        {bytes.map((b, i) => {
          const a = (i / 32) * Math.PI * 2 - Math.PI / 2;
          const len = r0 + (b / 255) * (r1 - r0);
          const t = b / 255;
          const color = `color-mix(in srgb, var(--signal) ${Math.round((1 - t) * 100)}%, var(--biosphere))`;
          
          return (
            <line 
              key={i} 
              x1={c + Math.cos(a) * r0} 
              y1={c + Math.sin(a) * r0} 
              x2={c + Math.cos(a) * len} 
              y2={c + Math.sin(a) * len}
              stroke={color} 
              strokeWidth={1.5} 
              strokeLinecap="round" 
            />
          );
        })}
      </svg>
      <div 
        className="font-mono text-xs text-muted cursor-pointer hover:text-text transition-colors"
        onClick={() => navigator.clipboard.writeText(hash)}
        onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') navigator.clipboard.writeText(hash); }}
        role="button"
        tabIndex={0}
        title="Click to copy full hash"
      >
        {hash.slice(0, 8)}...{hash.slice(-4)}
      </div>
    </div>
  );
}
