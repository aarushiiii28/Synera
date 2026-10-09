import React from 'react';

type Status = 'CANDIDATE' | 'VALIDATED' | 'VERIFIED' | 'BLOCKED' | 'REJECTED';

export function StatusChip({ status }: { status: Status }) {
  let color = 'text-faint';
  let glyph = <div className="w-3 h-3 border-2 border-faint" />; // fallback

  if (status === 'CANDIDATE') {
    color = 'text-signal';
    glyph = <div className="w-3 h-3 border-[1.5px] border-signal rounded-full" />;
  } else if (status === 'VALIDATED') {
    color = 'text-teal';
    glyph = (
      <div className="w-3 h-3 border-[1.5px] border-teal rounded-full overflow-hidden flex">
        <div className="w-1/2 h-full bg-teal" />
      </div>
    );
  } else if (status === 'VERIFIED') {
    color = 'text-biosphere';
    glyph = (
      <div className="w-3 h-3 bg-biosphere rounded-full flex items-center justify-center">
        <svg viewBox="0 0 12 12" className="w-2 h-2 text-void" fill="none">
          <path d="M2 6L5 9L10 3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
        </svg>
      </div>
    );
  } else if (status === 'BLOCKED') {
    color = 'text-alert';
    glyph = (
      <div className="w-3 h-3 border-[1.5px] border-alert rounded-full relative overflow-hidden flex items-center justify-center">
        <div className="absolute w-[150%] h-[1.5px] bg-alert transform rotate-45" />
      </div>
    );
  } else if (status === 'REJECTED') {
    color = 'text-faint';
    glyph = <div className="w-3 h-[1.5px] bg-faint" />;
  }

  return (
    <div className={`flex items-center gap-2 font-mono text-[10px] tracking-widest uppercase ${color}`}>
      {glyph}
      {status}
    </div>
  );
}
