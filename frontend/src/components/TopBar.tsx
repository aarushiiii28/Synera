import { Link } from 'react-router-dom';
import { useClock, useHealth } from '../lib/hooks';
import { useUI } from '../store';
import { HashGlyph } from './HashRing';
import { int, shortHash } from '../lib/format';
import { isStatic } from '../lib/snapshot';

/** Calm instrument strip. States are CHECKING (neutral dashes), LIVE (real values) or OFFLINE (alert). Never shows VALID before data arrives. */
export function TopBar() {
  const h = useHealth();
  const now = useClock();
  const startTour = useUI((s) => s.startTour);
  const state: 'CHECKING' | 'LIVE' | 'OFFLINE' = h.isError ? 'OFFLINE' : h.data ? 'LIVE' : 'CHECKING';
  const led = { CHECKING: 'bg-faint', LIVE: 'bg-biosphere', OFFLINE: 'bg-alert' }[state];
  const l = h.data?.ledger;
  return (
    <div className="h-12 shrink-0 border-b border-line bg-void/70 flex items-center gap-0 text-xs no-print overflow-hidden" role="banner">
      <div className="flex items-center gap-2 px-4 h-full border-r border-line">
        <span className={`w-2 h-2 rounded-full ${led} ${state === 'LIVE' ? 'pulse-soft' : ''}`} aria-hidden />
        <span className={`num tracking-[0.14em] ${state === 'OFFLINE' ? 'text-alert' : state === 'LIVE' ? 'text-text' : 'text-faint'}`}>
          {state === 'OFFLINE' ? 'SIGNAL LOST' : state === 'LIVE' ? (isStatic ? 'RECORDED DEMO' : 'API LIVE') : 'CHECKING…'}
        </span>
      </div>

      <div className="hidden md:flex items-center gap-5 px-4 h-full border-r border-line">
        <span className="label">LEDGER</span>
        <span className="num text-text">{state === 'LIVE' ? int(l?.height) : '——'}</span>
        <span className="label">CHAIN</span>
        <span className={`num tracking-[0.1em] ${state !== 'LIVE' ? 'text-faint' : l?.chain_valid ? 'text-biosphere' : 'text-alert pulse-soft'}`}>
          {state === 'OFFLINE' ? 'UNREACHABLE' : state === 'CHECKING' ? '——' : l?.chain_valid ? 'VALID' : 'BROKEN'}
        </span>
        {state === 'LIVE' && l?.head && (
          <span className="hidden lg:flex items-center gap-2" title={`Head block ${l.head}`}>
            <HashGlyph hash={l.head} size={22} />
            <span className="num text-muted">{shortHash(l.head, 6, 4)}</span>
          </span>
        )}
      </div>

      <div className="flex-1" />
      {h.data?.offline && <span className="num text-[10px] text-solar border border-solar/60 px-1.5 py-0.5 mr-3">OFFLINE / CACHED DATA</span>}
      <button onClick={() => { startTour(); }} className="num text-[11px] tracking-[0.12em] px-3 h-7 mr-3 border border-signal/60 text-signal hover:bg-signal/10 whitespace-nowrap">
        ▶ 3-MIN TOUR
      </button>
      <Link to="/guide" className="hidden sm:block num text-[11px] tracking-[0.12em] text-muted hover:text-text mr-4 whitespace-nowrap">HOW IT WORKS</Link>
      <div className="hidden sm:flex items-center px-4 h-full border-l border-line num text-muted whitespace-nowrap" aria-label="UTC time">
        {now.toISOString().slice(11, 19)} <span className="text-faint ml-1">UTC</span>
      </div>
    </div>
  );
}
