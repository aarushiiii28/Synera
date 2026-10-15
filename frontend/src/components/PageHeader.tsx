import type { ReactNode } from 'react';

/** Asymmetric editorial header: index number, large title, one-line standfirst, hairline running to the edge. */
export function PageHeader({ index, kicker, title, standfirst, right }: { index?: string; kicker?: string; title: ReactNode; standfirst: ReactNode; right?: ReactNode }) {
  return (
    <header className="px-6 md:px-10 pt-8 pb-6 rise">
      <div className="flex items-end gap-4">
        {index && <span className="num text-signal text-sm pb-2">{index}</span>}
        <div className="flex-1 min-w-0">
          {kicker && <div className="label !text-biosphere mb-1">{kicker}</div>}
          <h1 className="display font-semibold uppercase tracking-tight text-[clamp(1.6rem,3.2vw,2.6rem)] leading-[1.05] m-0">{title}</h1>
        </div>
        {right}
      </div>
      <p className="mt-3 max-w-3xl text-[16px] text-muted leading-relaxed">{standfirst}</p>
      <div className="mt-5 h-px bg-gradient-to-r from-signal/60 via-line to-transparent" />
    </header>
  );
}
