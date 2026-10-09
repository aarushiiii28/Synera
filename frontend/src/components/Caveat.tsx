import React from 'react';

export function Caveat({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex items-start gap-2 bg-solar/10 border border-solar/20 p-3 rounded-[2px] mt-4">
      <svg className="w-4 h-4 text-solar mt-0.5 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
      </svg>
      <div className="text-xs text-solar/90 font-mono">
        {children}
      </div>
    </div>
  );
}
