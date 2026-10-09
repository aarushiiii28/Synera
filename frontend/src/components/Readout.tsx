import React, { useEffect, useState } from 'react';

interface ReadoutProps {
  value: number | string;
  caption: string;
  delta?: string;
  format?: 'int' | 'float' | 'percent';
}

export function Readout({ value, caption, delta, format = 'int' }: ReadoutProps) {
  const reducedMotion = typeof window !== 'undefined' ? window.matchMedia('(prefers-reduced-motion: reduce)').matches : false;
  
  const [displayValue, setDisplayValue] = useState<number | string>(
    typeof value === 'number' && !reducedMotion ? 0 : value
  );

  useEffect(() => {
    if (typeof value !== 'number') return;
    
    // Simple count-up animation
    const duration = 800; // ms
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
    
    if (!reducedMotion) {
      requestAnimationFrame(tick);
    }
  }, [value]);

  const formatted = typeof displayValue === 'number' 
    ? (format === 'float' ? displayValue.toFixed(3) : format === 'percent' ? `${Math.round(displayValue * 100)}%` : Math.round(displayValue).toString())
    : displayValue;

  return (
    <div className="flex flex-col">
      <div className="flex items-baseline gap-3">
        <span className="font-mono text-[28px] text-text">{formatted}</span>
        {delta && <span className="font-mono text-[10px] text-signal">{delta}</span>}
      </div>
      <span className="font-sans text-[10px] uppercase tracking-widest text-muted mt-1">{caption}</span>
    </div>
  );
}
