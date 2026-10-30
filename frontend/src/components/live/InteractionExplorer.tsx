import { useMemo, useState } from 'react';
import { interpolateRdBu, scaleDiverging } from 'd3';
import { Link } from 'react-router-dom';
import { DEFAULTS, VARS, contrast, interactionGrid, type VarKey } from '../../lib/live';
import { ProvBadge } from './Badges';

const CONCEPTS = [
  { t: 'SYNERGISTIC', c: 'var(--solar)', d: 'The combined response is larger than the sum of the separate responses.' },
  { t: 'ANTAGONISTIC', c: 'var(--signal)', d: 'The combined response is smaller than the sum of the separate responses.' },
  { t: 'NONLINEAR', c: 'var(--biosphere)', d: 'The response does not follow a straight line: it bends or switches.' },
];

const GW = 360, GH = 260, M = { l: 40, b: 30, t: 8, r: 8 };

/** Exploratory interaction analysis of a DERIVED physical quantity (the heat index) over temperature and humidity. It is arithmetic on a published formula, not a statistical discovery. */
export function InteractionExplorer({ selected, setSelected }: { selected: VarKey[]; setSelected: (k: VarKey[]) => void }) {
  const [tb, setTb] = useState<number>(DEFAULTS.temperature);
  const [rb, setRb] = useState<number>(DEFAULTS.humidity);
  const [th, setTh] = useState<number>(35);
  const [rh, setRh] = useState<number>(70);
  const toggle = (k: VarKey) => setSelected(selected.includes(k) ? selected.filter((x) => x !== k) : [...selected, k]);
  const physical = selected.includes('temperature') && selected.includes('humidity');
  const others = selected.filter((k) => k !== 'temperature' && k !== 'humidity');
  const base = { ...DEFAULTS, temperature: tb, humidity: rb };
  const c = useMemo(() => contrast(base, th, rh), [tb, rb, th, rh]);   // eslint-disable-line react-hooks/exhaustive-deps
  const grid = useMemo(() => interactionGrid({ temperature: tb, humidity: rb }, [Math.min(tb, th) - 5, Math.max(tb, th) + 5], [Math.max(20, Math.min(rb, rh) - 15), Math.min(95, Math.max(rb, rh) + 15)], 21), [tb, rb, th, rh]);
  const color = scaleDiverging(interpolateRdBu).domain([grid.maxAbsGap || 1, 0, -(grid.maxAbsGap || 1)]);
  const n = grid.ts.length, cw = (GW - M.l - M.r) / n, ch = (GH - M.t - M.b) / n;
  const num = 'bg-void border border-line px-2 py-1 text-[13px] num w-20';
  return (
    <div>
      <div className="grid lg:grid-cols-[minmax(0,15rem)_minmax(0,1fr)] gap-8">
        <div>
          <div className="label mb-2">Stressors to explore</div>
          <ul className="list-none m-0 p-0 grid gap-1.5">
            {VARS.map((v) => (
              <li key={v.key}><label className="flex items-center gap-2 text-[13px] cursor-pointer">
                <input type="checkbox" checked={selected.includes(v.key)} onChange={() => toggle(v.key)} className="accent-[var(--signal)]" />
                <span className="flex-1">{v.label}</span><ProvBadge prov={v.prov} /></label></li>))}
          </ul>
          <p className="text-[12px] text-faint mt-3 mb-0 leading-snug">Only temperature and humidity have a physical response formula here (the heat index). Choose both to see the analysis.</p>
        </div>
        <div className="min-w-0">
          {physical ? (
            <>
              <div className="flex flex-wrap gap-x-6 gap-y-2 mb-4 text-[12px] text-muted items-center">
                <span className="label">Baseline</span><label>T <input type="number" value={tb} onChange={(e) => setTb(e.target.valueAsNumber || 0)} className={num} /> °C</label><label>RH <input type="number" value={rb} onChange={(e) => setRb(e.target.valueAsNumber || 0)} className={num} /> %</label>
                <span className="label ml-2">Raised to</span><label>T <input type="number" value={th} onChange={(e) => setTh(e.target.valueAsNumber || 0)} className={num} /> °C</label><label>RH <input type="number" value={rh} onChange={(e) => setRh(e.target.valueAsNumber || 0)} className={num} /> %</label>
              </div>
              <div className="grid xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)] gap-6">
                <div>
                  <div className="flex items-center gap-2 mb-2"><span className="label">Heat index of each condition</span><ProvBadge prov="DERIVED" /></div>
                  <table className="w-full text-[13px] border-collapse">
                    <tbody>
                      {[['Baseline', c.baseline], ['B: hotter only', c.b], ['C: more humid only', c.c], ['A: both raised', c.a]].map(([l, v]) => (
                        <tr key={String(l)} className="border-b border-line/60"><td className="py-1.5 text-muted">{l}</td><td className="py-1.5 num text-right">{(v as number).toFixed(1)} °C</td></tr>))}
                      <tr className="border-b border-line/60"><td className="py-1.5 text-muted">Sum of the separate effects (B + C)</td><td className="py-1.5 num text-right">{c.additive.toFixed(1)} °C</td></tr>
                      <tr><td className="py-1.5">Combined minus sum</td><td className="py-1.5 num text-right text-text">{c.interaction >= 0 ? '+' : ''}{c.interaction.toFixed(2)} °C</td></tr>
                    </tbody>
                  </table>
                  <p className="mt-3 mb-0 text-[14px]" aria-live="polite"><span className="num text-[11px] tracking-[0.12em]" style={{ color: c.klass.startsWith('SUPER') ? 'var(--solar)' : c.klass.startsWith('SUB') ? 'var(--signal)' : 'var(--muted)' }}>{c.klass}</span></p>
                  <p className="text-[12px] text-faint mt-1 mb-0 leading-snug">Curvature along temperature: {c.curvatureT.toFixed(2)} °C (0 means a straight line).</p>
                </div>
                <div>
                  <div className="label mb-1">Where the combination departs from adding</div>
                  <svg viewBox={`0 0 ${GW} ${GH}`} width="100%" role="img" aria-label="Heat map of the combined minus additive heat index over temperature and humidity" style={{ display: 'block' }}>
                    {grid.hs.map((h, j) => grid.ts.map((t, i) => (
                      <rect key={`${i}-${j}`} x={M.l + i * cw} y={GH - M.b - (j + 1) * ch} width={cw + 0.5} height={ch + 0.5} fill={color(grid.gap[j][i])}><title>{`T ${t.toFixed(1)} °C, RH ${h.toFixed(0)} %: ${grid.gap[j][i] >= 0 ? '+' : ''}${grid.gap[j][i].toFixed(2)} °C from additive`}</title></rect>)))}
                    <text x={M.l} y={GH - 8} fontSize="10" fill="var(--faint)">{grid.ts[0].toFixed(0)} °C</text>
                    <text x={GW - M.r} y={GH - 8} fontSize="10" fill="var(--faint)" textAnchor="end">{grid.ts[n - 1].toFixed(0)} °C</text>
                    <text x={M.l - 4} y={GH - M.b} fontSize="10" fill="var(--faint)" textAnchor="end">{grid.hs[0].toFixed(0)}%</text>
                    <text x={M.l - 4} y={M.t + 8} fontSize="10" fill="var(--faint)" textAnchor="end">{grid.hs[n - 1].toFixed(0)}%</text>
                  </svg>
                  <p className="text-[11.5px] text-faint mt-1 mb-0">Red: combined exceeds the sum of the separate changes from the baseline. Blue: falls short. Largest departure in view: {grid.maxAbsGap.toFixed(2)} °C.</p>
                </div>
              </div>
            </>
          ) : selected.length >= 2 ? (
            <div className="border border-dashed border-line px-5 py-6 text-[14px] text-muted leading-relaxed">
              <div className="label mb-1 !text-solar">NO VALIDATED RESPONSE MODEL</div>
              SYNERA has no physical or statistically validated response for {others.map((k) => VARS.find((v) => v.key === k)!.label).join(', ')}{' '}
              together with the others, so no interaction is computed or implied. Combining sensor readings alone does not establish an effect on anything biological. Real interaction discovery runs in the <Link to="/discovery" className="text-signal">Discovery Lab</Link> on datasets with a measured outcome.
            </div>
          ) : <p className="text-[14px] text-faint m-0">Choose two or more stressors.</p>}
        </div>
      </div>
      <div className="grid md:grid-cols-3 gap-4 mt-8">
        {CONCEPTS.map((k) => <div key={k.t} className="border-t pt-2" style={{ borderColor: k.c }}><div className="num text-[11px] tracking-[0.14em]" style={{ color: k.c }}>{k.t}</div><p className="text-[13px] text-muted m-0 mt-1 leading-snug">{k.d}</p></div>)}
      </div>
      <p className="text-[12.5px] text-solar mt-5 mb-0 max-w-3xl leading-relaxed">This is <b>exploratory scenario analysis</b> of a derived formula. It is not a validated interaction discovery: there is no p-value, q-value or biological conclusion here, and environmental sensor readings alone cannot establish biological effects.</p>
    </div>
  );
}
