import { useDeferredValue, useEffect, useMemo, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { api } from '../../lib/api';
import { useScenarioModel, useScenarioOutcomes } from '../../lib/hooks';
import { compare, evaluate, fmtNum, normalOf, rangeOf, surface, sweep, verdict, type Levels, type ScenarioModel } from '../../lib/scenario';
import { PageHeader } from '../../components/PageHeader';
import { Panel } from '../../components/Panel';
import { Explainer } from '../../components/Explainer';
import { Term } from '../../components/Term';
import { Async, EmptyState } from '../../components/States';
import { ProvenanceTag } from '../../components/Provenance';
import { CalibrationChart, ContributionBars, DoseGrid, EffectBar, StateMap, SurfaceMap, type Curve } from '../../components/charts/ScenarioCharts';

const OUTCOME_IDS = ['all', 'heart', 'stroke'] as const;
const MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];
const GROUPS: { title: string; items: string[] }[] = [
  { title: 'Heat and weather', items: ['heat_index', 'rh', 'wind', 'precip', 'uv', 'drought_index'] },
  { title: 'Air quality', items: ['pm25', 'pm10', 'o3', 'no2'] },
];
const POLLUTANTS = ['pm25', 'pm10', 'o3', 'no2'];
const ORDER = [...GROUPS[1].items, ...GROUPS[0].items];

/** Presets are written as departures from normal, in the state's own usual deviations, so they mean the same everywhere. */
const PRESETS: { id: string; label: string; hint: string; z: Record<string, number> }[] = [
  { id: 'typical', label: 'Typical week', hint: 'Everything at its normal level', z: {} },
  { id: 'heat', label: 'Heatwave', hint: 'Heat index 2.5 usual deviations above normal', z: { heat_index: 2.5 } },
  { id: 'cold', label: 'Cold snap', hint: 'Heat index 2.5 usual deviations below normal', z: { heat_index: -2.5 } },
  { id: 'smoke', label: 'Smoky air', hint: 'Fine and coarse particles far above normal', z: { pm25: 3, pm10: 2.5 } },
  { id: 'heatsmog', label: 'Heat + dirty air', hint: 'Heatwave together with high PM2.5, ozone and NO2', z: { heat_index: 2.5, pm25: 2, o3: 2, no2: 1.5 } },
  { id: 'clean', label: 'Clean-air week', hint: 'Particles and gases below normal', z: { pm25: -1.5, no2: -1.5, pm10: -1, o3: -1 } },
];

const monthWeek = (m: number) => Math.min(Math.floor((Math.round((Date.UTC(2015, m - 1, 15) - Date.UTC(2015, 0, 0)) / 86400000) - 1) / 7), 51);
const sign = (v: number, d = 1) => `${v >= 0 ? '+' : '−'}${Math.abs(v).toFixed(d)}`;
const pct = (v: number, d = 2) => `${v >= 0 ? '+' : '−'}${Math.abs(v).toFixed(d)}%`;
const same = (a: Record<string, number>, b: Record<string, number>) => {
  const keys = new Set([...Object.keys(a), ...Object.keys(b)]);
  return [...keys].every((k) => Math.abs((a[k] ?? 0) - (b[k] ?? 0)) < 1e-9);
};

function Slider({ model, state, woy, s, z, onChange }: { model: ScenarioModel; state: string; woy: number; s: string; z: number; onChange: (z: number) => void }) {
  const { normal, sd } = normalOf(model, state, woy, s);
  const [lo, hi] = rangeOf(model, state, woy, s);
  const level = Math.min(hi, Math.max(lo, normal + z * sd));
  const dz = (level - normal) / sd;
  const unit = model.units[s];
  const delta = level - normal;
  return (
    <div className="grid grid-cols-[minmax(0,1fr)] gap-1">
      <div className="flex items-baseline justify-between gap-2">
        <label htmlFor={`sl-${s}`} className="text-[13px] text-text">{model.labels[s]}</label>
        <span className="num text-[13px]">{fmtNum(level)} <span className="text-faint text-[10px]">{unit}</span></span>
      </div>
      <input id={`sl-${s}`} type="range" min={lo} max={hi} step={(hi - lo) / 200} value={level} aria-valuetext={`${fmtNum(level)} ${unit}, ${dz >= 0 ? '' : '−'}${Math.abs(dz).toFixed(1)} usual deviations ${dz >= 0 ? 'above' : 'below'} normal`}
        onChange={(e) => onChange((Number(e.target.value) - normal) / sd)} className="w-full accent-[var(--signal)]" />
      <div className="flex items-center justify-between num text-[10px] text-faint">
        <span>{Math.abs(dz) < 0.02 ? `normal here: ${fmtNum(normal)}` : `${sign(delta, Math.abs(delta) < 10 ? 1 : 0)} ${unit} vs normal ${fmtNum(normal)} · ${sign(dz)} usual dev.`}</span>
        {Math.abs(dz) > 0.02 && <button type="button" onClick={() => onChange(0)} className="text-signal hover:underline cursor-pointer" aria-label={`Reset ${model.labels[s]} to normal`}>reset</button>}
      </div>
    </div>
  );
}

function RealDataCheck() {
  const runs = useQuery({ queryKey: ['runs', 'all'], queryFn: () => api.runs() });
  return (
    <Async q={runs} h={120}>
      {(all) => {
        const rows = ['us_mortality', 'us_heart', 'us_stroke'].map((id) => all.find((r) => r.dataset_id === id && r.status === 'COMPLETED')).filter((r) => !!r);
        if (!rows.length) return <p className="text-sm text-muted m-0">The engine has not been run on the real mortality data yet.</p>;
        const labels: Record<string, string> = { us_mortality: 'All causes', us_heart: 'Heart disease', us_stroke: 'Stroke' };
        return (
          <div className="grid grid-cols-[minmax(0,1fr)] gap-3">
            <ul className="m-0 p-0 list-none grid gap-2">
              {rows.map((r) => r && (
                <li key={r.id} className="grid grid-cols-[7rem_1fr] sm:grid-cols-[8rem_1fr_auto] gap-x-4 gap-y-1 items-baseline border-t border-line pt-2">
                  <span className="text-[13px] text-text">{labels[r.dataset_id]}</span>
                  <span className="num text-[12px] text-muted">45 pairs tested → {r.stage_counts?.marginal_bh ?? 0} pass FDR → {r.stage_counts?.after_backward ?? 0} after conditional selection</span>
                  <span className="num text-[12px]" style={{ color: Object.values(r.summary ?? {}).some((v) => v > 0) ? 'var(--teal)' : 'var(--muted)' }}>
                    {Object.values(r.summary ?? {}).reduce((a, b) => a + b, 0)} findings
                  </span>
                </li>
              ))}
            </ul>
            <p className="text-[13px] text-muted m-0 leading-relaxed">
              The discovery engine searched every pair of the ten stressors for effects beyond adding up. After removing nationwide flu and weather waves, none survived the false-discovery and conditional-selection tests.
              An earlier pass that did <em>not</em> remove them flagged an ozone × UV pattern; it disappeared once the calendar was accounted for. That is why combinations are shown as
              mostly additive below, not as hidden synergies. <Link to="/discovery" className="text-signal hover:underline">Run the engine yourself →</Link>
            </p>
          </div>
        );
      }}
    </Async>
  );
}

function Lab({ model, outcome }: { model: ScenarioModel; outcome: string }) {
  const [sp, setSp] = useSearchParams();
  const states = useMemo(() => Object.keys(model.locations).sort(), [model]);
  // State and month live in local state so the page answers at once; the link is updated in the background for sharing.
  const [state, setStateLocal] = useState(() => { const w = sp.get('state') ?? ''; return states.includes(w) ? w : states.includes('Texas') ? 'Texas' : states[0]; });
  const [month, setMonthLocal] = useState(() => Math.min(12, Math.max(1, Number(sp.get('month')) || 7)));
  const woy = monthWeek(month);
  const [z, setZ] = useState<Record<string, number>>(PRESETS[4].z);
  const [pair, setPair] = useState<[string, string]>(['heat_index', 'pm25']);

  const setParam = (k: string, v: string) => setSp((p) => { const n = new URLSearchParams(p); n.set(k, v); return n; }, { replace: true });
  const setState = (s: string) => { setStateLocal(s); setParam('state', s); };
  const setMonth = (m: number) => { setMonthLocal(m); setParam('month', String(m)); };
  useEffect(() => { if (sp.get('state') !== state) setParam('state', state); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const levels: Levels = useMemo(() => {
    const out: Levels = {};
    model.stressors.forEach((s) => {
      const zi = z[s] ?? 0;
      if (Math.abs(zi) < 1e-9) return;
      const { normal, sd } = normalOf(model, state, woy, s);
      const [lo, hi] = rangeOf(model, state, woy, s);
      out[s] = Math.min(hi, Math.max(lo, normal + zi * sd));
    });
    return out;
  }, [z, model, state, woy]);

  const r = useMemo(() => evaluate(model, state, woy, levels), [model, state, woy, levels]);
  const v = verdict(r);
  // The headline above updates at once; the charts below (hundreds of model evaluations) follow a beat later, so dragging stays smooth.
  const dLevels = useDeferredValue(levels);
  const dState = useDeferredValue(state), dWoy = useDeferredValue(woy);
  const dEffect = useMemo(() => evaluate(model, dState, dWoy, dLevels).effect, [model, dState, dWoy, dLevels]);
  const cleanLevels = useMemo(() => { const o = { ...dLevels }; POLLUTANTS.forEach((s) => delete o[s]); return o; }, [dLevels]);
  const polluted = POLLUTANTS.some((s) => dLevels[s] !== undefined);
  const cleaner = useMemo(() => (polluted ? compare(model, dState, dWoy, dLevels, cleanLevels) : null), [polluted, model, dState, dWoy, dLevels, cleanLevels]);
  const curves: Curve[] = useMemo(() => ORDER.map((s) => ({
    s, pts: sweep(model, dState, dWoy, dLevels, s, 25), current: dLevels[s] ?? normalOf(model, dState, dWoy, s).normal, currentEffect: dEffect,
  })), [model, dState, dWoy, dLevels, dEffect]);
  const surf = useMemo(() => surface(model, dState, dWoy, dLevels, pair[0], pair[1], 15), [model, dState, dWoy, dLevels, pair]);
  const setOne = (s: string, zi: number) => setZ((p) => ({ ...p, [s]: zi }));
  const interSure = r.interactionLo > 0 || r.interactionHi < 0;
  const farthest = Math.max(...Object.values(r.anomalies).map(Math.abs));
  const val = model.validation;
  const ic = model.interaction_check;
  const scale = Math.max(0.5, ...model.headline.map((h) => Math.max(Math.abs(h.lo), Math.abs(h.hi))));
  const tone = { calm: 'var(--teal)', watch: 'var(--solar)', alert: 'var(--alert)' }[v.tone];

  return (
    <div className="px-6 md:px-10 pb-16 grid gap-10">
      <div className="grid grid-cols-[minmax(0,1fr)] lg:grid-cols-[minmax(0,390px)_minmax(0,1fr)] gap-8 items-start">
        {/* ------------------------------------------------------------ controls */}
        <div className="grid grid-cols-[minmax(0,1fr)] gap-6 lg:sticky lg:top-4">
          <a href="#results" className="lg:hidden sticky top-0 z-30 -mx-6 px-6 py-2 bg-void/95 backdrop-blur border-b border-line flex items-baseline justify-between gap-3 no-underline text-text" aria-label="Live estimate: jump to the full result">
            <span className="num text-2xl leading-none" style={{ color: tone }}>{pct(r.effect)}</span>
            <span className="text-[12px] text-muted truncate">{pct(r.lo)} to {pct(r.hi)} · {state}, {MONTHS[month - 1]}</span>
            <span className="num text-[10px] tracking-[0.12em] text-signal whitespace-nowrap">DETAILS ↓</span>
          </a>
          <Panel title="1 · Where and when" variant="bracketed" provenance="REAL">
            <div className="grid grid-cols-[minmax(0,1fr)] gap-4">
              <StateMap model={model} selected={state} onSelect={setState} />
              <div className="grid grid-cols-2 gap-3">
                <label className="grid grid-cols-[minmax(0,1fr)] gap-1 text-[12px] text-muted">State
                  <select value={state} onChange={(e) => setState(e.target.value)} className="num bg-void border border-line-strong px-2 py-1.5 text-sm text-text">
                    {states.map((s) => <option key={s}>{s}</option>)}
                  </select>
                </label>
                <label className="grid grid-cols-[minmax(0,1fr)] gap-1 text-[12px] text-muted">Time of year
                  <select value={month} onChange={(e) => setMonth(Number(e.target.value))} className="num bg-void border border-line-strong px-2 py-1.5 text-sm text-text">
                    {MONTHS.map((m, i) => <option key={m} value={i + 1}>{m}</option>)}
                  </select>
                </label>
              </div>
              <div>
                <div className="label mb-1.5">Consequence to look at</div>
                <div className="flex flex-wrap gap-2" role="group" aria-label="Outcome">
                  {OUTCOME_IDS.map((o) => (
                    <button key={o} type="button" aria-pressed={o === outcome} onClick={() => setParam('outcome', o)}
                      className={`num text-[11px] tracking-[0.1em] px-3 py-1.5 border cursor-pointer ${o === outcome ? 'border-signal text-signal bg-signal/10' : 'border-line-strong text-muted hover:text-text'}`}>
                      {o === 'all' ? 'ALL DEATHS' : o === 'heart' ? 'HEART DISEASE' : 'STROKE'}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          </Panel>

          <Panel title="2 · Set the conditions" variant="inset">
            <div className="grid grid-cols-[minmax(0,1fr)] gap-4">
              <div className="flex flex-wrap gap-2" role="group" aria-label="Quick scenarios">
                {PRESETS.map((p) => (
                  <button key={p.id} type="button" title={p.hint} aria-pressed={same(z, p.z)} onClick={() => setZ(p.z)}
                    className={`num text-[11px] tracking-[0.08em] px-2.5 py-1.5 border cursor-pointer ${same(z, p.z) ? 'border-solar text-solar bg-solar/10' : 'border-line-strong text-muted hover:text-text'}`}>
                    {p.label}
                  </button>
                ))}
              </div>
              {GROUPS.map((g) => (
                <div key={g.title} className="grid grid-cols-[minmax(0,1fr)] gap-4">
                  <div className="label !text-biosphere border-t border-line pt-3">{g.title}</div>
                  {g.items.map((s) => <Slider key={s} model={model} state={state} woy={woy} s={s} z={z[s] ?? 0} onChange={(zi) => setOne(s, zi)} />)}
                </div>
              ))}
              <p className="text-[12px] text-faint m-0 leading-snug">Sliders run from four <Term k="usualdev">usual deviations</Term> below to four above what is normal for {state} in {MONTHS[month - 1]}. Anything not moved stays normal.</p>
            </div>
          </Panel>
        </div>

        {/* ------------------------------------------------------------ results */}
        <div id="results" className="grid grid-cols-[minmax(0,1fr)] gap-8 min-w-0 scroll-mt-14">
          <Panel title={`Estimated consequence · ${state} · ${MONTHS[month - 1]} · ${model.outcome.label.toLowerCase()}`} variant="bracketed" provenance="REAL"
            right={<span className="num text-[10px] tracking-[0.14em] text-faint hidden sm:inline">90% INTERVAL</span>}>
            <div className="grid grid-cols-[minmax(0,1fr)] gap-5" aria-live="polite">
              <div className="grid grid-cols-[minmax(0,1fr)] sm:grid-cols-[auto_minmax(0,1fr)] gap-x-8 gap-y-3 items-end">
                <div className="num leading-none" style={{ color: tone, fontSize: 'clamp(2.6rem, 6vw, 4.2rem)' }}>{pct(r.effect)}</div>
                <div>
                  <div className="display text-xl leading-tight" style={{ color: tone }}>{v.headline}</div>
                  <p className="m-0 mt-1 text-[14px] text-muted leading-relaxed max-w-xl">{v.detail}</p>
                </div>
              </div>
              <EffectBar effect={r.effect} lo={r.lo} hi={r.hi} scale={Math.max(0.6, Math.abs(r.lo), Math.abs(r.hi)) * 1.15} />
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 border-t border-line pt-4">
                {[
                  ['Range', `${pct(r.lo)} to ${pct(r.hi)}`],
                  ['Per week here', `${sign(r.extraDeaths, Math.abs(r.extraDeaths) < 10 ? 1 : 0)} deaths`],
                  ['Typical week', `${Math.round(r.expectedDeaths).toLocaleString('en-US')} deaths`],
                  ['Furthest from normal', `${farthest.toFixed(1)} usual dev.`],
                ].map(([k, val2]) => (
                  <div key={k}><div className="label">{k}</div><div className="num text-[15px] mt-0.5">{val2}</div></div>
                ))}
              </div>
              {(r.support.unusual || farthest > 3.5) && (
                <div role="alert" className="border border-solar/70 bg-solar/10 px-4 py-2.5 text-[13px] leading-snug"><span className="num text-[10px] tracking-[0.16em] text-solar mr-2">EXTRAPOLATION</span>
                  Conditions this far from normal for {state} have hardly occurred in the data (the most extreme setting is {farthest.toFixed(1)} usual deviations out). The number above is a stretch of the model, not an observation.</div>
              )}
              {!r.seasonCovered && (
                <div role="alert" className="border border-solar/70 bg-solar/10 px-4 py-2.5 text-[13px] leading-snug"><span className="num text-[10px] tracking-[0.16em] text-solar mr-2">THIN DATA</span>
                  {state} has few measured weeks around {MONTHS[month - 1]}, so the normal levels used here are less certain.</div>
              )}
            </div>
          </Panel>

          <Panel title="Where the consequence comes from" variant="ruled">
            <div className="grid grid-cols-[minmax(0,1fr)] xl:grid-cols-2 gap-8">
              <div className="grid grid-cols-[minmax(0,1fr)] gap-3 content-start">
                <Explainer>Each bar is how much one stressor moves deaths in this scenario. The last row is the extra effect of stressors acting <em>together</em>, beyond adding up their separate effects.</Explainer>
                <ContributionBars model={model} contributions={r.contributions} interaction={r.interaction} interactionLo={r.interactionLo} interactionHi={r.interactionHi} />
              </div>
              <div className="grid grid-cols-[minmax(0,1fr)] gap-4 content-start">
                <div className="grid grid-cols-2 gap-4">
                  <div className="border border-line px-4 py-3"><div className="label">Separate effects added up</div><div className="num text-xl mt-1">{pct(r.additive)}</div></div>
                  <div className="border border-line px-4 py-3"><div className="label">Extra from interaction</div><div className="num text-xl mt-1 text-solar">{pct(r.interaction)}</div>
                    <div className="num text-[11px] text-faint">{pct(r.interactionLo)} to {pct(r.interactionHi)}</div></div>
                </div>
                <p className="m-0 text-[14px] leading-relaxed text-muted">
                  {Math.abs(r.interaction) < 0.0005 && Object.keys(levels).length < 2
                    ? 'Move two or more stressors to see whether they act together.'
                    : interSure
                      ? <>The combination adds a small <Term k="interaction">interaction</Term> ({pct(r.interaction)}) on top of the separate effects. Treat it with care: the engine did not confirm any interaction as a finding.</>
                      : <>Together these stressors behave almost exactly like the sum of their separate effects: the interaction part ({pct(r.interaction)}) is not clearly different from zero.</>}
                </p>
                {cleaner && Math.abs(cleaner.effect) > 0.0005 && (
                  <div className="border border-biosphere/60 bg-biosphere/5 px-4 py-3">
                    <div className="label !text-biosphere">What cleaner air would change</div>
                    <p className="m-0 mt-1 text-[14px] leading-relaxed">If PM2.5, PM10, ozone and NO2 stayed at their normal levels while everything else in this scenario stayed the same, deaths would be about <b className="num">{pct(-cleaner.effect)}</b> ({pct(-cleaner.hi)} to {pct(-cleaner.lo)}), roughly {Math.abs(Math.round((cleaner.effect / 100) * r.expectedDeaths))} deaths a week in {state}.</p>
                  </div>
                )}
              </div>
            </div>
          </Panel>

          <Panel title="Every weight of every stressor" variant="ruled">
            <div className="grid grid-cols-[minmax(0,1fr)] gap-3">
              <Explainer>Each small chart moves <em>one</em> stressor from low to high while everything else stays as you set it. The line is the best estimate, the shaded band the 90% range, the orange dot your scenario. All charts share one vertical scale, so steeper means more consequential.</Explainer>
              <DoseGrid model={model} curves={curves} />
            </div>
          </Panel>

          <Panel title="Two stressors at once" variant="ruled">
            <div className="flex flex-wrap items-center gap-2 mb-4 text-[12px] text-muted"><span>Compare</span>
              {[0, 1].map((i) => (
                <select key={i} aria-label={i === 0 ? 'Horizontal stressor' : 'Vertical stressor'} value={pair[i]} onChange={(e) => setPair((p) => (i === 0 ? [e.target.value, p[1]] : [p[0], e.target.value]) as [string, string])}
                  className="num bg-void border border-line-strong px-2 py-1 text-[12px] text-text">
                  {model.stressors.filter((s) => s !== pair[1 - i]).map((s) => <option key={s} value={s}>{model.labels[s]}</option>)}
                </select>
              ))}
              <span>(horizontal, vertical)</span>
            </div>
            <div className="grid grid-cols-[minmax(0,1fr)] lg:grid-cols-[auto_minmax(0,1fr)] gap-8 items-start">
              <SurfaceMap model={model} a={pair[0]} b={pair[1]} data={surf}
                current={[dLevels[pair[0]] ?? normalOf(model, dState, dWoy, pair[0]).normal, dLevels[pair[1]] ?? normalOf(model, dState, dWoy, pair[1]).normal]}
                onPick={(x, y) => setZ((p) => ({ ...p, [pair[0]]: (x - normalOf(model, state, woy, pair[0]).normal) / normalOf(model, state, woy, pair[0]).sd, [pair[1]]: (y - normalOf(model, state, woy, pair[1]).normal) / normalOf(model, state, woy, pair[1]).sd }))} />
              <Explainer>Every cell is one combination of the two stressors you picked (everything else as set). Red means more deaths than a typical week, green fewer. Click a cell to move both sliders there. If the colours form straight bands, the stressors simply add up; a bent pattern would signal an interaction.</Explainer>
            </div>
          </Panel>
        </div>
      </div>

      {/* ------------------------------------------------------------ trust */}
      <div className="grid grid-cols-[minmax(0,1fr)] gap-8">
        <div>
          <div className="label !text-biosphere mb-1">CAN YOU TRUST THIS?</div>
          <h2 className="display text-2xl font-semibold uppercase m-0">What the real data say, and how well the model checks out</h2>
        </div>
        <div className="grid grid-cols-[minmax(0,1fr)] xl:grid-cols-2 gap-8">
          <Panel title="Effects of each stressor on its own" variant="bracketed" provenance="REAL">
            <div className="grid grid-cols-[minmax(0,1fr)] gap-3">
              <Explainer tone="biosphere">Change in weekly deaths when one stressor moves by the amount shown, estimated from {model.training.rows.toLocaleString('en-US')} state-weeks. Bars show the 90% range; a bar that does not cross zero is a clear effect.</Explainer>
              <ul className="m-0 p-0 list-none grid gap-1.5">
                {model.headline.map((h) => {
                  const clear = h.lo > 0 || h.hi < 0;
                  return (
                    <li key={h.label} className="grid grid-cols-[minmax(10rem,15rem)_1fr_7rem] items-center gap-3 border-t border-line pt-1.5">
                      <span className="text-[12.5px] text-text leading-tight">{h.label}</span>
                      <EffectBar effect={h.effect} lo={h.lo} hi={h.hi} scale={scale} />
                      <span className="num text-[12px] text-right" style={{ color: clear ? (h.effect >= 0 ? 'var(--alert)' : 'var(--teal)') : 'var(--faint)' }}>{pct(h.effect)}{clear ? '' : ' ·  unclear'}</span>
                    </li>
                  );
                })}
              </ul>
            </div>
          </Panel>

          <Panel title="Does the model work on states it never saw?" variant="bracketed">
            <div className="grid grid-cols-[minmax(0,1fr)] sm:grid-cols-[auto_minmax(0,1fr)] gap-6 items-start">
              <CalibrationChart deciles={val.deciles} />
              <div className="grid grid-cols-[minmax(0,1fr)] gap-3 content-start">
                <Explainer tone="biosphere">Weeks from states left out of the fitting were sorted into ten groups by predicted risk. If the model is honest, observed excess deaths sit on the diagonal.</Explainer>
                <dl className="m-0 grid grid-cols-2 gap-x-4 gap-y-2 text-[13px]">
                  <dt className="text-muted"><Term k="calibration">Calibration slope</Term></dt>
                  <dd className="num m-0 text-right">{val.calibration_slope.toFixed(2)} <span className="text-faint">[{val.calibration_slope_ci[0].toFixed(2)}, {val.calibration_slope_ci[1].toFixed(2)}]</span></dd>
                  <dt className="text-muted">Safest vs riskiest group</dt>
                  <dd className="num m-0 text-right">{pct(val.deciles[0].observed)} vs {pct(val.deciles[9].observed)} <span className="text-faint">observed</span></dd>
                  <dt className="text-muted">Share of week-to-week variation explained</dt>
                  <dd className="num m-0 text-right">{(val.leave_states_out.with_interactions * 100).toFixed(1)}%</dd>
                  <dt className="text-muted">Gradient boosting (second opinion)</dt>
                  <dd className="num m-0 text-right">{(val.leave_states_out.gradient_boosting * 100).toFixed(1)}%</dd>
                </dl>
                <p className="m-0 text-[13px] text-muted leading-relaxed">The model ranks risky and safe weeks correctly, but weather and air quality explain only a small slice of what moves weekly deaths (flu, ageing, chance and much else are outside it). It estimates average effects, and a more complex machine-learning model does not do better.</p>
              </div>
            </div>
          </Panel>
        </div>

        <div className="grid grid-cols-[minmax(0,1fr)] xl:grid-cols-2 gap-8">
          <Panel title="Did the engine find hidden combined effects in real deaths?" variant="bracketed" provenance="REAL">
            <div className="grid grid-cols-[minmax(0,1fr)] gap-4">
              <RealDataCheck />
              <p className="m-0 text-[13px] text-muted leading-relaxed border-t border-line pt-3">
                A second look with the unshrunken model: {ic.pairs_excluding_zero} of {ic.pairs_tested} pairs differ from zero at the 90% level where about {ic.expected_by_chance} would by chance alone, and interactions larger than roughly {ic.largest_plausible_pct_per_sd2.toFixed(1)}% per usual-deviation² would very likely have been seen.
                Real interactions, if any, are small.
              </p>
            </div>
          </Panel>

          <Panel title="Where this comes from" variant="inset">
            <dl className="m-0 grid grid-cols-[8.5rem_1fr] gap-x-4 gap-y-2 text-[13px]">
              <dt className="text-muted">Deaths</dt><dd className="m-0">CDC NCHS weekly counts by state, {model.training.date_start.slice(0, 4)}–{model.training.date_end.slice(0, 4)} (before COVID-19)</dd>
              <dt className="text-muted">Air pollution</dt><dd className="m-0">US EPA monitors: PM2.5, PM10, ozone, NO2</dd>
              <dt className="text-muted">Weather</dt><dd className="m-0">Open-Meteo / ERA5 reanalysis; UV from NASA POWER</dd>
              <dt className="text-muted">Training data</dt><dd className="m-0">{model.training.rows.toLocaleString('en-US')} state-weeks, {model.training.states} states <ProvenanceTag provenance="REAL" /></dd>
              <dt className="text-muted">Dataset</dt><dd className="m-0 num text-[12px] break-all">{model.dataset.id}{model.dataset.sha256 ? ` · ${model.dataset.sha256.slice(0, 16)}…` : ''}{model.dataset.ledger_block != null && <> · <Link to={`/trust?block=${model.dataset.ledger_block}`} className="text-signal hover:underline whitespace-nowrap">ledger block #{model.dataset.ledger_block}</Link></>}</dd>
              <dt className="text-muted">This model</dt><dd className="m-0 num text-[12px] break-all">{model.registered ? <>{model.registered.sha256.slice(0, 16)}…{model.registered.ledger_block != null && <> · <Link to={`/trust?block=${model.registered.ledger_block}`} className="text-signal hover:underline whitespace-nowrap">ledger block #{model.registered.ledger_block}</Link></>}</> : 'fingerprint available when served by the API'}</dd>
              <dt className="text-muted">Method</dt><dd className="m-0">Transparent regression (<Term k="weekfe">same-week comparisons</Term>, heat curve that changes with the season, penalised pairwise products), {model.training.bootstrap_replicates} state-level bootstrap refits for the intervals</dd>
            </dl>
          </Panel>
        </div>

        <Panel title="Read this before using a number" variant="alert">
          <ul className="m-0 pl-5 grid gap-2 text-[14px] text-muted leading-relaxed">
            <li>These are <b className="text-text">average associations</b> between local conditions and weekly state deaths in 2014–2019. They are not a forecast for any person and not proof of cause.</li>
            <li>Weather is measured in each state's largest metro area and pollution as the state's monitor average, so people's true exposure is blurred. That tends to hide real effects, so true effects are probably somewhat larger.</li>
            <li>Weekly totals cannot show short spikes, and the model does not know about air conditioning, age structure, flu or health-care changes. Conditions far outside what a state has experienced are flagged as extrapolation.</li>
            <li>No finding here is VERIFIED: that needs independent replication in another dataset, which this data cannot give.</li>
          </ul>
        </Panel>
      </div>
    </div>
  );
}

export default function Scenario() {
  const [sp] = useSearchParams();
  const outs = useScenarioOutcomes();
  const requested = sp.get('outcome') ?? 'all';
  const outcome = (OUTCOME_IDS as readonly string[]).includes(requested) ? requested : 'all';
  const mq = useScenarioModel(outcome);
  return (
    <div>
      <PageHeader kicker="SCENARIO LAB" title={<>What if the air, heat and weather <span className="serif normal-case font-normal text-sun" style={{ fontSize: '1.08em' }}>combine?</span></>}
        standfirst="Pick a US state and a time of year, set any mix of heat, weather and air pollution, and see the estimated consequence for deaths, with an honest range, a breakdown of where it comes from and a check of how far to trust it. Everything is learned from real data and updates as you move."
        right={outs.data ? <span className="num text-[10px] tracking-[0.14em] text-biosphere hidden md:inline">REAL DATA · {outs.data.find((o) => o.id === outcome)?.states ?? '—'} STATES</span> : undefined} />
      <Async q={mq} h={420}>
        {(model) => (model.stressors?.length ? <Lab key={outcome} model={model} outcome={outcome} /> : <div className="px-6 md:px-10"><EmptyState title="Scenario model not built">Run  python scripts/build_scenario_model.py  to build it from the real mortality panels.</EmptyState></div>)}
      </Async>
    </div>
  );
}
