import { int } from '../../lib/format';

type Design = { control: number; radiation: number; unloading: number; both: number };

/** Subtle double-helix line art, used once as a header ornament. */
export function SpaceHelix({ className = '' }: { className?: string }) {
  const pts = Array.from({ length: 41 }, (_, i) => i);
  const a = pts.map((i) => `${i === 0 ? 'M' : 'L'}${i * 6},${20 + Math.sin(i / 3.2) * 14}`).join(' ');
  const b = pts.map((i) => `${i === 0 ? 'M' : 'L'}${i * 6},${20 - Math.sin(i / 3.2) * 14}`).join(' ');
  return (
    <svg viewBox="0 0 240 40" className={className} aria-hidden fill="none">
      <path d={a} stroke="var(--signal)" strokeWidth="1" opacity="0.55" />
      <path d={b} stroke="var(--biosphere)" strokeWidth="1" opacity="0.55" />
      {pts.filter((i) => i % 3 === 0).map((i) => (
        <line key={i} x1={i * 6} x2={i * 6} y1={20 + Math.sin(i / 3.2) * 14} y2={20 - Math.sin(i / 3.2) * 14} stroke="var(--line-strong)" strokeWidth="0.8" />
      ))}
    </svg>
  );
}

const CELLS = [
  { key: 'control', title: 'SHAM · GROUND', sub: 'no radiation, normal loading', tone: 'var(--muted)' },
  { key: 'unloading', title: 'SHAM · UNLOADING', sub: 'no radiation, hindlimb unloaded', tone: 'var(--solar)' },
  { key: 'radiation', title: 'RADIATION · GROUND', sub: 'low-dose radiation, normal loading', tone: 'var(--signal)' },
  { key: 'both', title: 'RADIATION · UNLOADING', sub: 'both stressors together', tone: 'var(--alert)' },
] as const;

/** The 2x2 factorial design. Each dot is one animal; counts come from the API. */
export function SpaceDesign2x2({ design }: { design: Design }) {
  const total = design.control + design.radiation + design.unloading + design.both;
  return (
    <figure className="m-0">
      <div className="grid grid-cols-[auto_1fr_1fr] gap-x-0 gap-y-0 items-stretch">
        <span />
        <span className="label text-center pb-2">Ground (loaded)</span>
        <span className="label text-center pb-2">Unloading (microgravity model)</span>
        {[0, 1].map((row) => (
          <div key={row} className="contents">
            <span className="label self-center pr-3 [writing-mode:vertical-rl] rotate-180 text-center">{row === 0 ? 'Sham' : 'Radiation'}</span>
            {CELLS.filter((_, i) => (i < 2 ? 0 : 1) === row).map((c) => {
              const n = design[c.key];
              return (
                <div key={c.key} className="border border-line p-3 md:p-4 bg-void/40 min-h-[132px]" style={{ borderTop: `2px solid ${c.tone}` }}>
                  <div className="num text-[10px] tracking-[0.12em]" style={{ color: c.tone }}>{c.title}</div>
                  <div className="flex items-baseline gap-2 mt-1"><span className="num text-4xl leading-none">{int(n)}</span><span className="num text-xs text-faint">mice</span></div>
                  <div className="flex flex-wrap gap-1 mt-3" aria-hidden>
                    {Array.from({ length: n }, (_, i) => <span key={i} className="w-2.5 h-2.5 rounded-full" style={{ background: c.tone, opacity: 0.8 }} />)}
                  </div>
                  <div className="text-[11px] text-muted mt-2 leading-snug">{c.sub}</div>
                </div>
              );
            })}
          </div>
        ))}
      </div>
      <figcaption className="num text-xs text-muted mt-3">{int(total)} mice in total. The interaction is what the <span className="text-alert">radiation · unloading</span> group does beyond adding up the two single-stressor groups.</figcaption>
    </figure>
  );
}
