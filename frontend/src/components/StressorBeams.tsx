import { useState, type ReactNode } from 'react';
import { useReducedMotion } from '../lib/hooks';

interface Node { id: string; label: string; x: number; color: string; about: string; glyph: ReactNode }

const G = { fill: 'none', stroke: 'currentColor', strokeWidth: 1.4, strokeLinecap: 'round' as const, strokeLinejoin: 'round' as const };
const NODES: Node[] = [
  { id: 'heat', label: 'HEAT', x: 10, color: 'var(--solar)', about: 'Heat waves raise the body’s stress load, especially with humidity.',
    glyph: <g {...G}><path d="M10 4a2 2 0 0 1 2 2v7.2a3.5 3.5 0 1 1-4 0V6a2 2 0 0 1 2-2z" transform="translate(2 0)" /><path d="M12 9v5" /></g> },
  { id: 'air', label: 'AIR POLLUTION', x: 26, color: '#9fb4c9', about: 'Fine particles, ozone and NO₂ inflame lungs and blood vessels.',
    glyph: <g {...G}><path d="M7 15a3.5 3.5 0 0 1 .6-6.9A4.5 4.5 0 0 1 16.4 9 3 3 0 0 1 17 15z" /><path d="M8 18.5h8M10 21h5" /></g> },
  { id: 'radiation', label: 'RADIATION', x: 42, color: 'var(--biosphere)', about: 'Ionizing radiation damages DNA; in space it is constant.',
    glyph: <g {...G}><circle cx="12" cy="12" r="1.6" /><path d="M12 4a8 8 0 0 1 6.9 4l-5.5 3.2M4.1 8A8 8 0 0 1 12 4v6.4M18.9 16A8 8 0 0 1 5.1 16l5.5-3.2" /></g> },
  { id: 'drought', label: 'DROUGHT', x: 58, color: '#d8a56b', about: 'Dry spells reduce water, raise dust and compound heat.',
    glyph: <g {...G}><path d="M3 8l5 2 3-3 4 3 3-2 3 2M3 14l6 1 3-3 4 3 5-1M5 20l4-3 3 2 4-2 3 2" /></g> },
  { id: 'weather', label: 'EXTREME WEATHER', x: 74, color: 'var(--signal)', about: 'Storms and extremes disrupt systems that were coping with other stress.',
    glyph: <g {...G}><path d="M7 14a3.5 3.5 0 0 1 .6-6.9A4.5 4.5 0 0 1 16.4 7 3 3 0 0 1 17 14z" /><path d="M12.5 12l-2 4h3l-2 4" /></g> },
];

/** Five stressors emit luminous beams that converge on one cell, as on slide 2 of the deck. */
export function StressorBeams({ className = '' }: { className?: string }) {
  const reduced = useReducedMotion();
  const [hover, setHover] = useState<string | null>(null);
  const cell = { x: 48, y: 60 };
  const top = 13;
  const active = NODES.find((n) => n.id === hover);
  return (
    <div className={className}>
      <svg viewBox="0 0 100 100" preserveAspectRatio="none" className="absolute inset-0 w-full h-full pointer-events-none" aria-hidden>
        <defs>
          {NODES.map((n) => (
            <linearGradient key={n.id} id={`bm-${n.id}`} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0" stopColor={n.color} stopOpacity="0.15" />
              <stop offset="1" stopColor="#6fd65b" stopOpacity="0.95" />
            </linearGradient>
          ))}
          <filter id="bm-blur"><feGaussianBlur stdDeviation="0.6" /></filter>
        </defs>
        {NODES.map((n) => (
          <g key={n.id} opacity={hover && hover !== n.id ? 0.25 : 1}>
            <line x1={n.x} y1={top + 5} x2={cell.x} y2={cell.y - 4} stroke={`url(#bm-${n.id})`} strokeWidth="0.9" filter="url(#bm-blur)" vectorEffect="non-scaling-stroke" />
            <line x1={n.x} y1={top + 5} x2={cell.x} y2={cell.y - 4} stroke={`url(#bm-${n.id})`} strokeWidth="1.2" strokeDasharray="6 42"
              vectorEffect="non-scaling-stroke" style={reduced ? undefined : { animation: 'beam 2.6s linear infinite' }} />
          </g>
        ))}
      </svg>

      {/* The cell */}
      <div className="absolute -translate-x-1/2 -translate-y-1/2" style={{ left: `${cell.x}%`, top: `${cell.y}%` }} aria-label="The cell: where stressors converge">
        <svg width="84" height="84" viewBox="0 0 84 84" fill="none" className={reduced ? '' : 'pulse-soft'}>
          <circle cx="42" cy="42" r="32" fill="rgba(111,214,91,.10)" stroke="var(--biosphere)" strokeWidth="1.4" />
          <circle cx="42" cy="42" r="38" stroke="var(--biosphere)" strokeOpacity=".28" />
          <path d="M26 36c6-6 10 4 16-2s8 6 14 0M26 48c6-5 9 5 15-1s9 5 15-1M32 58c4-3 8 3 12-1" stroke="var(--biosphere)" strokeWidth="1.2" strokeLinecap="round" />
        </svg>
        <div className="num text-[10px] tracking-[0.16em] text-biosphere text-center mt-1 whitespace-nowrap">THE CELL</div>
      </div>

      {NODES.map((n) => (
        <button key={n.id} type="button" onMouseEnter={() => setHover(n.id)} onMouseLeave={() => setHover(null)} onFocus={() => setHover(n.id)} onBlur={() => setHover(null)}
          aria-label={`${n.label}: ${n.about}`}
          className="absolute -translate-x-1/2 -translate-y-1/2 bg-transparent border-0 p-0 cursor-help group" style={{ left: `${n.x}%`, top: `${top}%` }}>
          <span className="block w-12 h-12 rounded-full border bg-void/80 grid place-items-center transition-transform group-hover:scale-110"
            style={{ color: n.color, borderColor: n.color, boxShadow: `0 0 22px -6px ${n.color}` }}>
            <svg width="24" height="24" viewBox="0 0 24 24">{n.glyph}</svg>
          </span>
          <span className="block num text-[9px] tracking-[0.14em] mt-1.5 whitespace-nowrap text-center" style={{ color: n.color }}>{n.label}</span>
        </button>
      ))}

      <div className="absolute left-0 right-0 bottom-[4%] text-center px-6 min-h-[2.6rem]" aria-live="polite">
        <span className={`inline-block max-w-md text-sm text-text/90 bg-void/70 px-3 py-1.5 border-l-2 transition-opacity ${active ? 'opacity-100' : 'opacity-0'}`} style={{ borderColor: active?.color }}>
          {active?.about}
        </span>
      </div>
    </div>
  );
}
