import { useEffect, useMemo, useState } from 'react';
import { DEFAULTS, VARS, derive, factorialScenarios, type Conditions, type Scenario, type VarKey } from '../../lib/live';
import { ProvBadge } from './Badges';

const KEY = 'synera.live.scenarios';
const loadSaved = (): Scenario[] => { try { const v = JSON.parse(localStorage.getItem(KEY) ?? '[]'); return Array.isArray(v) ? v : []; } catch { return []; } };
const store = (s: Scenario[]) => { try { localStorage.setItem(KEY, JSON.stringify(s)); } catch { /* storage unavailable: saving is a convenience only */ } };
const uid = () => Math.random().toString(36).slice(2, 8);

const EXAMPLE = factorialScenarios(DEFAULTS, 35, 70);        // baseline 25 °C / 50 %, A 35 / 70, B 35 / 50, C 25 / 70
const sign = (x: number, d = 1) => `${x > 0 ? '+' : ''}${x.toFixed(d)}`;

/** Build stress scenarios, compare each with the baseline, save them. Derived values (heat index, dew point) are formulas; the rest are the numbers you typed. */
export function ScenarioBuilder({ enabled, live, source }: { enabled: Set<VarKey>; live: Pick<Conditions, 'temperature' | 'humidity' | 'gas'> | null; source: 'REAL' | 'TEST' | null }) {
  const [list, setList] = useState<Scenario[]>(EXAMPLE);
  const [saved, setSaved] = useState<Scenario[]>(loadSaved);
  const [ran, setRan] = useState<{ at: string; list: Scenario[] } | null>(null);
  useEffect(() => { store(saved); }, [saved]);
  const vars = VARS.filter((v) => enabled.has(v.key));
  const edit = (id: string, patch: (s: Scenario) => Scenario) => setList((l) => l.map((s) => (s.id === id ? patch(s) : s)));
  const setVal = (id: string, k: VarKey, x: number) => edit(id, (s) => ({ ...s, values: { ...s.values, [k]: Number.isFinite(x) ? x : s.values[k] } }));
  const useLive = () => {
    if (!live) return;
    // the baseline takes all three sensor values; the other scenarios keep their own temperature and humidity but share the baseline gas level, so only what you changed differs
    setList((l) => l.map((s, i) => (i === 0 ? { ...s, name: source === 'TEST' ? 'Baseline (test feed)' : 'Baseline (sensor now)', fromLive: true, values: { ...s.values, ...live } } : { ...s, values: { ...s.values, gas: live.gas } })));
  };
  const stale = useMemo(() => !!ran && JSON.stringify(ran.list) !== JSON.stringify(list), [ran, list]);
  const shown = ran?.list ?? null;
  const base = shown?.[0];
  const rows: { label: string; unit: string; prov: 'REAL SENSOR' | 'SIMULATED' | 'DERIVED'; get: (s: Scenario) => number; d: number }[] = [
    ...vars.map((v) => ({ label: v.label, unit: v.unit, prov: v.prov === 'REAL SENSOR' && source !== 'REAL' && !base?.fromLive ? ('SIMULATED' as const) : (v.prov as 'REAL SENSOR' | 'SIMULATED'), get: (s: Scenario) => s.values[v.key], d: v.key === 'temperature' ? 1 : 0 })),
    ...(enabled.has('temperature') && enabled.has('humidity') ? [
      { label: 'Heat index', unit: '°C', prov: 'DERIVED' as const, get: (s: Scenario) => derive(s.values).heatIndex, d: 1 },
      { label: 'Dew point', unit: '°C', prov: 'DERIVED' as const, get: (s: Scenario) => derive(s.values).dewPoint, d: 1 }] : []),
  ];
  const numInput = 'bg-void border border-line px-2 py-1 text-[13px] num w-full min-w-0';
  return (
    <div>
      <div className="flex flex-wrap gap-2 mb-4">
        <button type="button" onClick={() => { setList(EXAMPLE); setRan(null); }} className="num text-[11px] tracking-[0.12em] border border-line px-3 py-1.5 hover:border-signal">LOAD THE 2 × 2 EXAMPLE</button>
        <button type="button" onClick={useLive} disabled={!live} title={live ? 'Copy the latest reading into the baseline' : 'Connect the device (or start the test feed) first'} className="num text-[11px] tracking-[0.12em] border border-line px-3 py-1.5 hover:border-biosphere disabled:opacity-40">USE CURRENT READING AS BASELINE</button>
        <button type="button" onClick={() => setList((l) => [...l, { id: uid(), name: `Scenario ${l.length}`, hours: 24, values: { ...l[0].values } }])} disabled={list.length >= 6} className="num text-[11px] tracking-[0.12em] border border-line px-3 py-1.5 hover:border-signal disabled:opacity-40">ADD SCENARIO</button>
        <span className="flex-1" />
        <button type="button" onClick={() => setRan({ at: new Date().toLocaleTimeString(), list: JSON.parse(JSON.stringify(list)) })} className="num text-[11px] tracking-[0.16em] border border-signal bg-signal/10 text-signal px-4 py-1.5 hover:bg-signal/20">RUN COMPARISON</button>
      </div>
      <div className="grid gap-3" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(210px, 1fr))' }}>
        {list.map((s, i) => (
          <div key={s.id} className="border border-line p-3 min-w-0" style={{ borderTop: `2px solid ${i === 0 ? 'var(--biosphere)' : 'var(--signal)'}` }}>
            <div className="flex gap-2 items-center mb-2">
              <input aria-label="Scenario name" value={s.name} onChange={(e) => edit(s.id, (x) => ({ ...x, name: e.target.value.slice(0, 40) }))} className={`${numInput} !text-text font-medium`} />
              {i > 0 && <button type="button" aria-label={`Remove ${s.name}`} onClick={() => setList((l) => l.filter((x) => x.id !== s.id))} className="text-faint hover:text-alert bg-transparent border-0 cursor-pointer text-lg leading-none">×</button>}
            </div>
            {vars.map((v) => (
              <label key={v.key} className="grid grid-cols-[1fr_5.5rem] gap-2 items-center mb-1.5 text-[12px] text-muted">
                <span className="truncate" title={v.note}>{v.label} <span className="text-faint">{v.unit}</span></span>
                <input type="number" inputMode="decimal" min={v.min} max={v.max} step={v.step} value={s.values[v.key]} onChange={(e) => setVal(s.id, v.key, e.target.valueAsNumber)} className={numInput} />
              </label>
            ))}
            <label className="grid grid-cols-[1fr_5.5rem] gap-2 items-center text-[12px] text-muted"><span>Duration <span className="text-faint">hours</span></span>
              <input type="number" min={1} max={720} value={s.hours} onChange={(e) => edit(s.id, (x) => ({ ...x, hours: Math.max(1, Math.min(720, e.target.valueAsNumber || 1)) }))} className={numInput} /></label>
            <button type="button" onClick={() => setSaved((a) => [{ ...s, id: uid() }, ...a].slice(0, 12))} className="mt-2 text-[11px] text-signal underline bg-transparent border-0 p-0 cursor-pointer">Save scenario</button>
          </div>
        ))}
      </div>
      {vars.length === 0 && <p className="text-sm text-solar mt-3">Enable at least one variable in the explorer above.</p>}

      {shown && base && (
        <div className="mt-6" role="region" aria-label="Scenario comparison">
          <div className="flex items-baseline gap-3 mb-2"><span className="label">Comparison with the baseline</span><span className="num text-[10px] text-faint">run at {ran!.at}</span>
            {stale && <span className="num text-[10px] text-solar">EDITED SINCE THIS RUN: run again</span>}</div>
          <div className="overflow-x-auto">
            <table className="w-full text-[13px] border-collapse min-w-[560px]">
              <thead><tr className="text-left text-faint num text-[10px] tracking-[0.12em] uppercase border-b border-line">
                <th className="py-2 pr-3 font-normal">Quantity</th>{shown.map((s) => <th key={s.id} className="py-2 pr-3 font-normal">{s.name}<span className="block normal-case tracking-normal text-faint">{s.hours} h</span></th>)}</tr></thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.label} className="border-b border-line/60">
                    <td className="py-2 pr-3 whitespace-nowrap">{r.label} <span className="text-faint">{r.unit}</span><span className="block"><ProvBadge prov={r.prov} /></span></td>
                    {shown.map((s, i) => { const v = r.get(s), d = v - r.get(base); return (
                      <td key={s.id} className="py-2 pr-3 num"><span className="text-text">{v.toFixed(r.d)}</span>{i > 0 && <span className="block text-[11px]" style={{ color: d === 0 ? 'var(--faint)' : d > 0 ? 'var(--solar)' : 'var(--signal)' }}>{sign(d, r.d)} vs baseline</span>}</td>); })}
                  </tr>))}
              </tbody>
            </table>
          </div>
          <p className="text-[12.5px] text-muted mt-3 mb-0 max-w-3xl leading-relaxed">Heat index and dew point are computed from temperature and humidity by standard formulas (DERIVED). Every other number is exactly what was entered or read. This compares conditions; it does not say what those conditions do to any living thing.</p>
        </div>
      )}
      {!shown && <p className="text-[13px] text-faint mt-4 mb-0">Press RUN COMPARISON to compare the scenarios with the baseline.</p>}

      {saved.length > 0 && (
        <div className="mt-6 border-t border-line pt-4">
          <div className="label mb-2">Saved scenarios <span className="text-faint normal-case tracking-normal">(kept in this browser only)</span></div>
          <ul className="list-none m-0 p-0 flex flex-wrap gap-2">
            {saved.map((s) => (
              <li key={s.id} className="border border-line px-3 py-1.5 text-[12px] flex items-center gap-2">
                <button type="button" onClick={() => setList((l) => (l.length < 6 ? [...l, { ...s, id: uid() }] : l))} className="text-text bg-transparent border-0 p-0 cursor-pointer hover:text-signal" title="Add to the comparison">{s.name} · {s.values.temperature}°C / {s.values.humidity}%</button>
                <button type="button" aria-label={`Delete ${s.name}`} onClick={() => setSaved((a) => a.filter((x) => x.id !== s.id))} className="text-faint hover:text-alert bg-transparent border-0 cursor-pointer">×</button>
              </li>))}
          </ul>
        </div>
      )}
    </div>
  );
}
