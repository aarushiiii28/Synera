import { useId, useState, type ReactNode } from 'react';
import { GLOSSARY } from '../lib/glossary';

/** Inline jargon with a plain-language definition on hover or keyboard focus. */
export function Term({ k, children }: { k: keyof typeof GLOSSARY | string; children?: ReactNode }) {
  const [open, setOpen] = useState(false);
  const id = useId();
  const g = GLOSSARY[k as string];
  if (!g) return <>{children}</>;
  return (
    <span className="relative inline-block">
      <button
        type="button"
        aria-describedby={open ? id : undefined}
        onMouseEnter={() => setOpen(true)} onMouseLeave={() => setOpen(false)}
        onFocus={() => setOpen(true)} onBlur={() => setOpen(false)}
        onKeyDown={(e) => e.key === 'Escape' && setOpen(false)}
        className="border-b border-dotted border-signal/70 text-inherit cursor-help bg-transparent p-0 font-[inherit]"
      >
        {children ?? g.title}
      </button>
      {open && (
        <span id={id} role="tooltip" className="absolute z-50 left-0 top-full mt-2 w-64 border border-line-strong bg-void p-3 text-[13px] leading-snug text-text normal-case tracking-normal font-sans text-left">
          <span className="block label !text-signal mb-1">{g.title}</span>
          {g.text}
        </span>
      )}
    </span>
  );
}
