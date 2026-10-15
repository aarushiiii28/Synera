import { useId, useMemo } from 'react';
import * as d3 from 'd3';
import type { NetworkGraph, StressorInfo } from '../../lib/api';
import { TYPE_COLOR, fix } from '../../lib/format';

const W = 640, H = 430;
// Stars are coloured by stressor group. Neutral hues on purpose: interaction type already owns green/cyan/amber.
const GROUP_COLOR: Record<string, string> = { heat: '#ffd9a0', air: '#9db7d1', weather: '#e9f0f7', drought: '#d1a46b' };
const groupColor = (g: string) => GROUP_COLOR[g] ?? 'var(--muted)';

interface SimNode extends d3.SimulationNodeDatum { id: string; label: string; group: string; degree: number; in_finding: boolean }

const star = (r: number) => {
  const pts: string[] = [];
  for (let i = 0; i < 8; i++) {
    const a = (i * Math.PI) / 4 - Math.PI / 2, rr = i % 2 === 0 ? r : r * 0.38;
    pts.push(`${(Math.cos(a) * rr).toFixed(1)},${(Math.sin(a) * rr).toFixed(1)}`);
  }
  return `M${pts.join('L')}Z`;
};

export function DiscoveryConstellation({ network, labels, selectedId, onSelect }: { network: NetworkGraph; labels?: StressorInfo; selectedId: string | null; onSelect: (findingId: string, a: string, b: string) => void }) {
  const uid = useId().replace(/:/g, '');
  const layout = useMemo(() => {
    const nodes: SimNode[] = network.nodes.map((n) => ({ ...n }));
    const links = network.edges.map((e) => ({ source: e.source, target: e.target }));
    const sim = d3.forceSimulation(nodes)
      .force('link', d3.forceLink<SimNode, { source: string; target: string }>(links).id((d) => d.id).distance(120).strength(0.35))
      .force('charge', d3.forceManyBody().strength(-260))
      .force('x', d3.forceX(W / 2).strength(0.07)).force('y', d3.forceY(H / 2).strength(0.1))
      .force('collide', d3.forceCollide(34)).stop();
    for (let i = 0; i < 320; i++) sim.tick();
    nodes.forEach((n) => { n.x = Math.max(60, Math.min(W - 60, n.x ?? W / 2)); n.y = Math.max(34, Math.min(H - 44, n.y ?? H / 2)); });
    return nodes;
  }, [network]);
  const byId = new Map(layout.map((n) => [n.id, n]));
  const maxV = Math.max(0.0001, ...network.edges.map((e) => e.value));
  const groups = [...new Set(network.nodes.map((n) => n.group))];
  const lab = (k: string) => labels?.[k]?.label ?? k;

  return (
    <div>
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-auto" role="group" aria-label="Constellation of stressors. Stars are stressors; arcs are selected interactions.">
        <defs>
          <radialGradient id={`${uid}s`}><stop offset="0" stopColor="#fff" stopOpacity="0.5" /><stop offset="1" stopColor="#fff" stopOpacity="0" /></radialGradient>
        </defs>
        {network.edges.map((e) => {
          const s = byId.get(e.source), t = byId.get(e.target);
          if (!s || !t) return null;
          const mx = ((s.x ?? 0) + (t.x ?? 0)) / 2, my = ((s.y ?? 0) + (t.y ?? 0)) / 2;
          const dx = (t.x ?? 0) - (s.x ?? 0), dy = (t.y ?? 0) - (s.y ?? 0);
          const cxp = mx - dy * 0.22, cyp = my + dx * 0.22;
          const d = `M${s.x},${s.y}Q${cxp},${cyp} ${t.x},${t.y}`;
          const lx = 0.25 * (s.x ?? 0) + 0.5 * cxp + 0.25 * (t.x ?? 0), ly = 0.25 * (s.y ?? 0) + 0.5 * cyp + 0.25 * (t.y ?? 0);
          const w = 1.6 + (e.value / maxV) * 7;
          const col = TYPE_COLOR[e.type];
          const cur = e.finding_id === selectedId;
          return (
            <g key={e.finding_id} role="button" tabIndex={0} aria-pressed={cur} aria-label={`${lab(e.source)} by ${lab(e.target)}, ${e.type.toLowerCase()}, ${e.status.toLowerCase()}, effect ${fix(e.value, 2)} SD`}
              className="outline-none cursor-pointer group" onClick={() => onSelect(e.finding_id, e.source, e.target)}
              onKeyDown={(ev) => { if (ev.key === 'Enter' || ev.key === ' ') { ev.preventDefault(); onSelect(e.finding_id, e.source, e.target); } }}>
              <path d={d} fill="none" stroke="transparent" strokeWidth="22" />
              {e.status === 'VERIFIED' && <path d={d} fill="none" stroke={col} strokeOpacity="0.35" strokeWidth={w + 8} />}
              <path d={d} fill="none" stroke={col} strokeWidth={w} strokeLinecap="round" strokeDasharray={e.status === 'CANDIDATE' ? '6 6' : undefined} opacity={cur ? 1 : 0.8} className="group-focus-visible:stroke-[var(--text)]" />
              <text x={lx} y={ly - w / 2 - 6} textAnchor="middle" fontSize="12" fill={col} className="num" stroke="var(--void)" strokeWidth="3" paintOrder="stroke">{fix(e.value, 2)} SD</text>
            </g>
          );
        })}
        {layout.map((n) => {
          const r = 8 + n.degree * 3;
          const c = groupColor(n.group);
          return (
            <g key={n.id} transform={`translate(${n.x},${n.y})`} opacity={n.in_finding ? 1 : 0.55}>
              <circle r={r * 2.4} fill={`url(#${uid}s)`} opacity={n.in_finding ? 0.7 : 0.3} />
              <path d={star(r + 4)} fill={c} />
              <text y={r + 20} textAnchor="middle" fontSize="13" fill="var(--text)">{lab(n.id)}</text>
              <title>{`${lab(n.id)}: ${n.in_finding ? `in ${n.degree} selected interaction${n.degree === 1 ? '' : 's'}` : 'not part of any selected interaction'}`}</title>
            </g>
          );
        })}
      </svg>
      <ul className="list-none p-0 m-0 mt-3 flex flex-wrap gap-x-5 gap-y-1.5 text-[12px] text-muted items-center">
        {groups.map((g) => (
          <li key={g} className="inline-flex items-center gap-1.5"><svg width="14" height="14" viewBox="-8 -8 16 16" aria-hidden><path d={star(7)} fill={groupColor(g)} /></svg>{g} stressors</li>
        ))}
        {(['SYNERGISTIC', 'ANTAGONISTIC', 'NONLINEAR'] as const).map((t) => (
          <li key={t} className="inline-flex items-center gap-1.5"><svg width="22" height="8" aria-hidden><line x1="0" y1="4" x2="22" y2="4" stroke={TYPE_COLOR[t]} strokeWidth="3" /></svg>{t.toLowerCase()}</li>
        ))}
        <li className="inline-flex items-center gap-1.5"><svg width="22" height="8" aria-hidden><line x1="0" y1="4" x2="22" y2="4" stroke="var(--muted)" strokeWidth="2" strokeDasharray="5 4" /></svg>candidate (dashed)</li>
        <li className="inline-flex items-center gap-1.5"><svg width="22" height="8" aria-hidden><line x1="0" y1="4" x2="22" y2="4" stroke="var(--muted)" strokeWidth="2" /></svg>validated (solid)</li>
        <li className="inline-flex items-center gap-1.5"><svg width="22" height="12" aria-hidden><line x1="0" y1="6" x2="22" y2="6" stroke="var(--muted)" strokeOpacity="0.4" strokeWidth="9" /><line x1="0" y1="6" x2="22" y2="6" stroke="var(--muted)" strokeWidth="2" /></svg>verified (ringed)</li>
        <li className="text-faint">thickness = effect size, dim stars take part in no selected interaction</li>
      </ul>
    </div>
  );
}
