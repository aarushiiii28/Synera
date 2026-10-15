import { useEffect, useRef, useState } from 'react';
import { useReducedMotion } from '../lib/hooks';

/** Big tabular number with a thin unit label and a 1px baseline. Counts up once on mount. */
export function Readout({ label, value, unit, hint, tone = 'text', decimals = 0, display }: {
  label: string; value: number | null | undefined; unit?: string; hint?: string; tone?: 'text' | 'signal' | 'biosphere' | 'solar' | 'alert' | 'teal'; decimals?: number; display?: string;
}) {
  const reduced = useReducedMotion();
  const [shown, setShown] = useState(reduced ? (value ?? 0) : 0);
  const first = useRef(true);
  useEffect(() => {
    if (value === null || value === undefined) return;
    if (!first.current || reduced) { setShown(value); first.current = false; return; }
    first.current = false;
    const t0 = performance.now();
    let raf = 0;
    const tick = (t: number) => {
      const k = Math.max(0, Math.min(1, (t - t0) / 900));
      setShown(value * (1 - Math.pow(1 - k, 3)));
      if (k < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    // rAF is throttled in background tabs; always land on the real value.
    const done = window.setTimeout(() => setShown(value), 1000);
    return () => { cancelAnimationFrame(raf); window.clearTimeout(done); };
  }, [value, reduced]);
  const color = { text: 'var(--text)', signal: 'var(--signal)', biosphere: 'var(--biosphere)', solar: 'var(--solar)', alert: 'var(--alert)', teal: 'var(--teal)' }[tone];
  return (
    <div className="min-w-[8rem]">
      <div className="label mb-1">{label}</div>
      <div className="flex items-baseline gap-2 border-b border-line pb-1">
        <span className="num text-4xl md:text-5xl leading-none" style={{ color }}>
          {display ?? (value === null || value === undefined ? '—' : shown.toLocaleString('en-US', { minimumFractionDigits: decimals, maximumFractionDigits: decimals }))}
        </span>
        {unit && <span className="num text-xs text-faint">{unit}</span>}
      </div>
      {hint && <div className="text-xs text-muted mt-1 max-w-[16rem] leading-snug">{hint}</div>}
    </div>
  );
}
