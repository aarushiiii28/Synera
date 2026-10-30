import { useEffect, useState } from 'react';
import { NavLink } from 'react-router-dom';
import { Logo, Wordmark } from './Logo';
import { IconBenchmark, IconBiology, IconDiscovery, IconFindings, IconGuide, IconLive, IconObservatory, IconRisk, IconScenario, IconTrust } from './NavIcons';

export const NAV = [
  { to: '/', icon: <IconObservatory />, title: 'Observatory', sub: 'The big picture', step: '' },
  { to: '/scenario', icon: <IconScenario />, title: 'Scenario Lab', sub: 'What if they combine?', step: '' },
  { to: '/live-stress-lab', icon: <IconLive />, title: 'Live Stress Lab', sub: 'Real sensors, real air', step: '' },
  { to: '/discovery', icon: <IconDiscovery />, title: 'Discovery Lab', sub: 'Find interactions', step: '01' },
  { to: '/findings', icon: <IconFindings />, title: 'Findings', sub: 'What survived', step: '02' },
  { to: '/trust', icon: <IconTrust />, title: 'Trust Center', sub: 'Break it on purpose', step: '03' },
  { to: '/space-biology', icon: <IconBiology />, title: 'Space Biology', sub: 'Real NASA data', step: '' },
  { to: '/benchmark', icon: <IconBenchmark />, title: 'Report Card', sub: 'How accurate is it?', step: '' },
  { to: '/risk', icon: <IconRisk />, title: 'Risk Brief', sub: 'From science to action', step: '04' },
  { to: '/guide', icon: <IconGuide />, title: 'How it works', sub: 'The 7 layers', step: '' },
];

const RAIL_MAX = 232;   // full width: icon, title, subtitle, step number
const RAIL_MIN = 64;    // icons only
const RAIL_COMPACT = 150; // below this the text no longer fits, so only icons are shown
const RAIL_KEY = 'synera.rail.width';
const clampRail = (w: number) => Math.min(RAIL_MAX, Math.max(RAIL_MIN, Math.round(w)));

function useRailWidth() {
  const [width, setWidth] = useState(() => {
    try { const v = Number(localStorage.getItem(RAIL_KEY)); return v ? clampRail(v) : RAIL_MAX; } catch { return RAIL_MAX; }
  });
  useEffect(() => { try { localStorage.setItem(RAIL_KEY, String(width)); } catch { /* storage unavailable */ } }, [width]);
  return [width, (w: number) => setWidth(clampRail(w))] as const;
}

/** Desktop rail: full labels by default; drag its right edge to shrink it down to icons only. */
export function Rail() {
  const [width, setWidth] = useRailWidth();
  const [dragging, setDragging] = useState(false);
  const compact = width < RAIL_COMPACT;
  const onDown = (e: React.PointerEvent<HTMLDivElement>) => {
    e.preventDefault();
    const startX = e.clientX, startW = width;
    setDragging(true);
    const move = (ev: PointerEvent) => setWidth(startW + ev.clientX - startX);
    const up = () => { setDragging(false); window.removeEventListener('pointermove', move); window.removeEventListener('pointerup', up); };
    window.addEventListener('pointermove', move);
    window.addEventListener('pointerup', up);
  };
  const onKey = (e: React.KeyboardEvent) => {
    if (e.key === 'ArrowLeft') { e.preventDefault(); setWidth(width - 24); }
    if (e.key === 'ArrowRight') { e.preventDefault(); setWidth(width + 24); }
    if (e.key === 'Home') { e.preventDefault(); setWidth(RAIL_MIN); }
    if (e.key === 'End') { e.preventDefault(); setWidth(RAIL_MAX); }
  };
  return (
    <nav aria-label="Primary" style={{ width }} className={`hidden lg:flex flex-col shrink-0 h-screen sticky top-0 border-r border-line bg-void/80 no-print ${dragging ? '' : 'transition-[width] duration-150'}`}>
      <div className={`flex items-center gap-3 pt-6 pb-5 ${compact ? 'justify-center px-0' : 'px-5'} overflow-hidden`}>
        <Logo size={30} />
        {!compact && <Wordmark size={19} tagline={width >= RAIL_MAX - 6} />}
      </div>
      <div className={`h-px bg-gradient-to-r from-signal/40 to-transparent mb-3 ${compact ? 'mx-3' : 'mx-5'}`} />
      <ul className="flex-1 overflow-y-auto overflow-x-hidden m-0 p-0 list-none">
        {NAV.map((n) => (
          <li key={n.to}>
            <NavLink to={n.to} end={n.to === '/'} title={compact ? `${n.title}${n.step ? ` (step ${Number(n.step)})` : ''}` : undefined} aria-label={n.title} className={({ isActive }) =>
              `group relative flex items-center gap-3 py-2.5 transition-colors ${compact ? 'justify-center px-0' : 'px-5'} ${isActive ? 'text-text bg-signal/[0.07]' : 'text-muted hover:text-text hover:bg-white/[0.02]'}`}>
              {({ isActive }) => (
                <>
                  <span className={`absolute left-0 top-1.5 bottom-1.5 w-[2px] ${isActive ? 'bg-signal shadow-[0_0_10px_var(--signal)]' : 'bg-transparent'}`} />
                  <span className={`shrink-0 ${isActive ? 'text-signal' : 'text-faint group-hover:text-muted'}`}>{n.icon}</span>
                  {!compact && (
                    <>
                      <span className="flex-1 min-w-0">
                        <span className="block text-[14px] leading-tight truncate">{n.title}</span>
                        <span className="block text-[11px] text-faint leading-tight mt-0.5 truncate">{n.sub}</span>
                      </span>
                      {n.step && <span className="num text-[9px] tracking-[0.12em] text-biosphere/80">{n.step}</span>}
                    </>
                  )}
                </>
              )}
            </NavLink>
          </li>
        ))}
      </ul>
      <div role="separator" aria-orientation="vertical" aria-label="Resize sidebar" aria-valuemin={RAIL_MIN} aria-valuemax={RAIL_MAX} aria-valuenow={width} tabIndex={0}
        onPointerDown={onDown} onKeyDown={onKey} onDoubleClick={() => setWidth(compact ? RAIL_MAX : RAIL_MIN)} title="Drag to resize · double-click to collapse or expand"
        className={`absolute top-0 -right-[3px] h-full w-[7px] cursor-col-resize z-20 touch-none after:absolute after:inset-y-0 after:left-[3px] after:w-px hover:after:bg-signal focus-visible:after:bg-signal ${dragging ? 'after:bg-signal' : ''}`} />
    </nav>
  );
}
/** Mobile bottom bar. */
export function BottomBar() {
  return (
    <nav aria-label="Primary" className="lg:hidden fixed bottom-0 inset-x-0 z-40 border-t border-line bg-void/95 flex overflow-x-auto no-print">
      {NAV.map((n) => (
        <NavLink key={n.to} to={n.to} end={n.to === '/'} aria-label={n.title}
          className={({ isActive }) => `flex-1 min-w-[64px] flex flex-col items-center gap-0.5 py-2 text-[10px] ${isActive ? 'text-signal' : 'text-faint'}`}>
          {n.icon}
          <span className="truncate max-w-[60px]">{n.title.split(' ')[0]}</span>
        </NavLink>
      ))}
    </nav>
  );
}
