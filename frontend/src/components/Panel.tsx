import React from 'react';

interface PanelProps extends React.HTMLAttributes<HTMLDivElement> {
  indexLabel?: string;
  provenance?: 'REAL' | 'SIMULATED';
}

export function Panel({ indexLabel, provenance, children, className = '', ...props }: PanelProps) {
  return (
    <div className={`relative border border-line bg-hull p-4 rounded-[2px] ${className}`} {...props}>
      {/* Corner Brackets */}
      <svg className="absolute top-[-1px] left-[-1px] w-2 h-2 text-line-strong pointer-events-none" viewBox="0 0 8 8" fill="none">
        <path d="M0 8V0H8" stroke="currentColor" strokeWidth="1" />
      </svg>
      <svg className="absolute top-[-1px] right-[-1px] w-2 h-2 text-line-strong pointer-events-none" viewBox="0 0 8 8" fill="none">
        <path d="M0 0H8V8" stroke="currentColor" strokeWidth="1" />
      </svg>
      <svg className="absolute bottom-[-1px] left-[-1px] w-2 h-2 text-line-strong pointer-events-none" viewBox="0 0 8 8" fill="none">
        <path d="M8 8H0V0" stroke="currentColor" strokeWidth="1" />
      </svg>
      <svg className="absolute bottom-[-1px] right-[-1px] w-2 h-2 text-line-strong pointer-events-none" viewBox="0 0 8 8" fill="none">
        <path d="M0 8H8V0" stroke="currentColor" strokeWidth="1" />
      </svg>

      {/* Header Strip */}
      {(indexLabel || provenance) && (
        <div className="flex items-center justify-between mb-4 pb-2 border-b border-line">
          {indexLabel && <span className="font-mono text-xs text-muted tracking-widest">{indexLabel}</span>}
          {provenance && (
            <div className="flex items-center gap-2">
              <span className={`w-2 h-2 rounded-full ${provenance === 'REAL' ? 'bg-biosphere' : 'bg-solar'}`} />
              {provenance === 'SIMULATED' && <span className="font-mono text-[10px] text-solar tracking-widest uppercase">SIMULATED</span>}
            </div>
          )}
        </div>
      )}

      {children}
    </div>
  );
}
