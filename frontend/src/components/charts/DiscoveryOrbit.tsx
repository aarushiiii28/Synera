import { fix } from '../../lib/format';

/** Ring progress with a satellite dot riding the arc. Static (no spin) when reduced motion is requested. */
export function DiscoveryOrbit({ progress, state, reduced, size = 150 }: { progress: number; state: 'idle' | 'running' | 'done' | 'failed'; reduced: boolean; size?: number }) {
  const c = size / 2, r = size * 0.36;
  const circ = 2 * Math.PI * r;
  const p = Math.max(0, Math.min(1, progress));
  const ang = p * Math.PI * 2 - Math.PI / 2;
  const tone = state === 'failed' ? 'var(--alert)' : state === 'done' ? 'var(--teal)' : 'var(--signal)';
  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} role="img" aria-label={`Run progress ${Math.round(p * 100)} percent`}>
      <circle cx={c} cy={c} r={r + 12} fill="none" stroke="var(--line)" strokeDasharray="1 5" />
      <circle cx={c} cy={c} r={r} fill="none" stroke="var(--line-strong)" strokeWidth="1" />
      <circle cx={c} cy={c} r={r} fill="none" stroke={tone} strokeWidth="2.5" strokeLinecap="round" strokeDasharray={`${circ * p} ${circ}`}
        transform={`rotate(-90 ${c} ${c})`} style={{ transition: reduced ? 'none' : 'stroke-dasharray 0.6s ease-out' }} />
      {state === 'running' && !reduced && (
        <g>
          <circle cx={c} cy={c - r - 12} r="2.5" fill="var(--sun)" />
          <animateTransform attributeName="transform" type="rotate" from={`0 ${c} ${c}`} to={`360 ${c} ${c}`} dur="14s" repeatCount="indefinite" />
        </g>
      )}
      <circle cx={c + Math.cos(ang) * r} cy={c + Math.sin(ang) * r} r="5" fill={tone} />
      <circle cx={c + Math.cos(ang) * r} cy={c + Math.sin(ang) * r} r="9" fill="none" stroke={tone} strokeOpacity="0.4" />
      <text x={c} y={c + 2} textAnchor="middle" className="num" fontSize={size * 0.2} fill="var(--text)">{fix(p * 100, 0)}</text>
      <text x={c} y={c + size * 0.15} textAnchor="middle" className="num" fontSize="9" letterSpacing="1.5" fill="var(--faint)">{state === 'idle' ? 'READY' : state === 'done' ? 'COMPLETE' : state === 'failed' ? 'STOPPED' : 'PERCENT'}</text>
    </svg>
  );
}
