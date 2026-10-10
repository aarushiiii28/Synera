import React, { useEffect, useState, useRef } from 'react';

interface ReadoutProps {
  value: number | string;
  caption: string;
  unit?: string;
  delta?: string;
  format?: 'int' | 'float' | 'percent';
}

export function Readout({ value, caption, unit, delta, format = 'int' }: ReadoutProps) {
  const [displayValue, setDisplayValue] = useState<number | string>(value);
  const mounted = useRef(false);

  useEffect(() => {
    const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (typeof value !== 'number' || reducedMotion || mounted.current) {
      setDisplayValue(value);
      mounted.current = true;
      return;
    }
    
    // Animate only on first mount
    mounted.current = true;
    const duration = 800;
    const startTime = performance.now();
    
    const tick = (now: number) => {
      const elapsed = now - startTime;
      const progress = Math.min(elapsed / duration, 1);
      const easeOutQuart = 1 - Math.pow(1 - progress, 4);
      
      const current = value * easeOutQuart;
      setDisplayValue(current);
      
      if (progress < 1) {
        requestAnimationFrame(tick);
      } else {
        setDisplayValue(value);
      }
    };
    
    requestAnimationFrame(tick);
  }, [value]);

  const formatted = typeof displayValue === 'number' 
    ? (format === 'float' ? displayValue.toFixed(3) : format === 'percent' ? `${Math.round(displayValue * 100)}` : Math.round(displayValue).toString())
    : displayValue;

  return (
    <div className="flex flex-col relative w-fit">
      <div className="flex items-baseline gap-2 pb-1 border-b border-line">
        <span className="font-mono text-4xl text-text leading-none">{formatted}</span>
        {(unit || format === 'percent') && (
          <span className="font-sans text-sm text-muted">{unit || '%'}</span>
        )}
        {delta && <span className="font-mono text-[10px] text-signal ml-2">{delta}</span>}
      </div>
      <span className="font-sans text-[10px] uppercase tracking-widest text-muted mt-2">
        {caption}
      </span>
    </div>
  );
}
