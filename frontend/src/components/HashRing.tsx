import { useState } from 'react';
import { shortHash } from '../lib/format';

/** Deterministic fingerprint: 32 radial ticks, length and colour from the hash bytes. */
export function HashGlyph({ hash, size = 40, tone }: { hash: string; size?: number; tone?: string }) {
  const bytes = (hash.match(/.{2}/g) ?? []).slice(0, 32).map((h) => parseInt(h, 16) || 0);
  const c = size / 2, r0 = size * 0.28, r1 = size * 0.48;
  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} role="img" aria-label={`Fingerprint ${hash.slice(0, 8)}`}>
      <circle cx={c} cy={c} r={r0 - 2} fill="none" stroke={tone ?? 'var(--line-strong)'} strokeWidth="1" />
      {bytes.map((b, i) => {
        const a = (i / 32) * Math.PI * 2 - Math.PI / 2, t = b / 255, len = r0 + t * (r1 - r0);
        return (
          <line key={i} x1={c + Math.cos(a) * r0} y1={c + Math.sin(a) * r0} x2={c + Math.cos(a) * len} y2={c + Math.sin(a) * len}
            stroke={tone ?? `color-mix(in srgb, var(--signal) ${Math.round((1 - t) * 100)}%, var(--biosphere))`} strokeWidth={1.4} strokeLinecap="round" />
        );
      })}
    </svg>
  );
}

/** Fingerprint + short mono hash; click copies the full SHA-256. */
export function HashRing({ hash, size = 40, full = false, label }: { hash: string; size?: number; full?: boolean; label?: string }) {
  const [copied, setCopied] = useState(false);
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(hash);
    } catch {
      // Clipboard API unavailable or denied (insecure origin, permissions): fall back to a hidden textarea.
      const ta = document.createElement('textarea');
      ta.value = hash; ta.style.position = 'fixed'; ta.style.opacity = '0';
      document.body.appendChild(ta); ta.select();
      try { document.execCommand('copy'); } catch { /* nothing more to try */ }
      document.body.removeChild(ta);
    }
    setCopied(true); setTimeout(() => setCopied(false), 1200);
  };
  return (
    <div className="inline-flex items-center gap-3">
      <HashGlyph hash={hash} size={size} />
      <button type="button" onClick={copy} title="Copy full SHA-256" className="text-left bg-transparent p-0 border-0 cursor-pointer group">
        {label && <span className="label block">{label}</span>}
        <span className="num text-xs text-muted group-hover:text-text break-all">{full ? hash : shortHash(hash)}</span>
        <span className="num text-[10px] text-biosphere ml-2">{copied ? 'COPIED' : ''}</span>
      </button>
    </div>
  );
}
