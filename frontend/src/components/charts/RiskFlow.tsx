import { FLOW, OUTCOMES } from './riskLogic';

const W = 1200, BOX_W = 148, GAP = (W - 7 * BOX_W) / 6, BOX_Y = 8, BOX_H = 92, NODE_Y = 372;

/** Naive greedy word wrap for SVG text. */
function wrap(s: string, max: number): string[] {
  const out: string[] = [];
  let cur = '';
  s.split(' ').forEach((w) => {
    if ((cur + ' ' + w).trim().length > max && cur) { out.push(cur); cur = w; } else cur = (cur + ' ' + w).trim();
  });
  if (cur) out.push(cur);
  return out;
}

/** Slide 6 as an open diagram: seven-step chain, with seven outcome nodes converging on the last box. */
export function RiskFlow() {
  const lastX = 6 * (BOX_W + GAP), lastCx = lastX + BOX_W / 2;
  const nodeCx = (i: number) => 85 + i * ((W - 170) / 6);
  return (
    <div>
      {/* Desktop diagram */}
      <svg viewBox={`0 0 ${W} 470`} className="hidden md:block w-full h-auto" role="img"
        aria-label={`From environmental complexity to trusted action: ${FLOW.map((f) => f.t).join(', then ')}. Outcomes: ${OUTCOMES.join(', ')}.`}>
        <defs>
          <filter id="rf-glow" x="-60%" y="-60%" width="220%" height="220%"><feGaussianBlur stdDeviation="5" /></filter>
          <radialGradient id="rf-node" cx="50%" cy="50%" r="50%">
            <stop offset="0" stopColor="#d6ffcc" /><stop offset="0.45" stopColor="var(--biosphere)" /><stop offset="1" stopColor="var(--biosphere)" stopOpacity="0.2" />
          </radialGradient>
          <linearGradient id="rf-box" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stopColor="var(--hull)" stopOpacity="0.8" /><stop offset="1" stopColor="var(--void)" stopOpacity="0.6" /></linearGradient>
        </defs>
        {/* converging curves */}
        {OUTCOMES.map((o, i) => {
          const x0 = nodeCx(i), x1 = lastCx + (i - 3) * 16;
          const d = `M ${x0} ${NODE_Y - 14} C ${x0} 250, ${x1} 220, ${x1} ${BOX_Y + BOX_H + 4}`;
          return (
            <g key={o}>
              <path d={d} fill="none" stroke="var(--biosphere)" strokeWidth="3" opacity="0.25" filter="url(#rf-glow)" />
              <path d={d} fill="none" stroke="var(--biosphere)" strokeWidth="1" opacity="0.7" />
              <path d={d} fill="none" stroke="#d6ffcc" strokeWidth="1.4" strokeDasharray="3 45" style={{ animation: `beam ${3 + (i % 3) * 0.6}s linear infinite` }} />
            </g>
          );
        })}
        {/* chain */}
        {FLOW.map((f, i) => {
          const x = i * (BOX_W + GAP), last = i === FLOW.length - 1;
          const tone = last ? 'var(--biosphere)' : i === 4 ? 'var(--alert)' : i === 3 ? 'var(--teal)' : i === 5 ? 'var(--biosphere)' : 'var(--signal)';
          const lines = wrap(f.t, last ? 16 : 17);
          return (
            <g key={f.t}>
              {last && <rect x={x - 3} y={BOX_Y - 3} width={BOX_W + 6} height={BOX_H + 6} fill="none" stroke="var(--biosphere)" opacity="0.5" filter="url(#rf-glow)" />}
              <rect x={x} y={BOX_Y} width={BOX_W} height={BOX_H} fill="url(#rf-box)" stroke={tone} strokeWidth={last ? 1.6 : 1} opacity="0.95" />
              <path d={`M ${x} ${BOX_Y + 12} V ${BOX_Y} H ${x + 12}`} fill="none" stroke={tone} strokeWidth="2" />
              <text x={x + 10} y={BOX_Y + 28} className="num" fontSize="11" fill={tone}>{String(i + 1).padStart(2, '0')}</text>
              {lines.map((l, li) => <text key={li} x={x + 10} y={BOX_Y + 48 + li * 17} fontSize="14" fontWeight="600" fill="var(--text)" className="display">{l}</text>)}
              {i < FLOW.length - 1 && (
                <path d={`M ${x + BOX_W + 5} ${BOX_Y + BOX_H / 2 - 6} l 8 6 l -8 6`} fill="none" stroke="var(--signal)" strokeWidth="1.5" />
              )}
            </g>
          );
        })}
        <text x="0" y="300" className="num" fontSize="11" fill="var(--biosphere)" letterSpacing="2">SEVEN OUTCOMES CONVERGE ON RESILIENCE</text>
        {/* outcome nodes */}
        {OUTCOMES.map((o, i) => {
          const cx = nodeCx(i);
          const lines = wrap(o, 20);
          return (
            <g key={o}>
              <circle cx={cx} cy={NODE_Y} r="22" fill="var(--biosphere)" opacity="0.35" filter="url(#rf-glow)" />
              <circle cx={cx} cy={NODE_Y} r="11" fill="url(#rf-node)" />
              {lines.map((l, li) => <text key={li} x={cx} y={NODE_Y + 40 + li * 16} textAnchor="middle" fontSize="13" fill="var(--text)">{l}</text>)}
            </g>
          );
        })}
      </svg>

      {/* Mobile: vertical list */}
      <ol className="md:hidden m-0 p-0 list-none grid gap-0 border-l border-line-strong ml-2">
        {FLOW.map((f, i) => (
          <li key={f.t} className="relative pl-5 pb-4">
            <span className="absolute -left-[5px] top-1.5 w-2.5 h-2.5 rounded-full border border-signal bg-void" aria-hidden />
            <div className="num text-[11px] text-signal">{String(i + 1).padStart(2, '0')}</div>
            <div className="display font-semibold text-[15px] leading-tight">{f.t}</div>
            <div className="text-[13px] text-muted">{f.d}</div>
          </li>
        ))}
        <li className="relative pl-5">
          <span className="absolute -left-[5px] top-1.5 w-2.5 h-2.5 rounded-full bg-biosphere" style={{ boxShadow: '0 0 10px var(--biosphere)' }} aria-hidden />
          <div className="label !text-biosphere mb-1.5">Seven outcomes</div>
          <ul className="m-0 p-0 list-none grid gap-1">{OUTCOMES.map((o) => <li key={o} className="text-[14px] flex items-center gap-2"><span className="w-1.5 h-1.5 rounded-full bg-biosphere" style={{ boxShadow: '0 0 6px var(--biosphere)' }} aria-hidden />{o}</li>)}</ul>
        </li>
      </ol>
    </div>
  );
}
