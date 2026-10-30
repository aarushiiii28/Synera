import { useMemo, useState } from 'react';
import { useScenarioModel } from '../../lib/hooks';
import { evaluate, weekOfYear } from '../../lib/scenario';
import { heatCategory, heatIndexC, smokeLevel, valueOf, type LiveReading } from '../../lib/live';

const MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];
const pct = (x: number, d = 2) => `${x >= 0 ? '+' : ''}${x.toFixed(d)}%`;

/** What the live readings mean, with no controls to adjust: heat comfort, a smoke alert, and the engine's estimate for those conditions. */
export function Insights({ readings }: { readings: LiveReading[] }) {
  const last = readings.length ? readings[readings.length - 1] : null;
  const t = last ? valueOf(last, 'temperature') : null, h = last ? valueOf(last, 'humidity') : null;
  const hi = t !== null && h !== null ? heatIndexC(t, h) : null;
  const cat = hi === null ? null : heatCategory(hi);
  const smoke = useMemo(() => smokeLevel(readings.map((r) => valueOf(r, 'gas'))), [readings]);
  const mq = useScenarioModel('all');
  const model = mq.data;
  const states = model ? Object.keys(model.locations).sort() : [];
  const [state, setState] = useState('Texas');
  const [month, setMonth] = useState(new Date().getMonth() + 1);
  const st = states.includes(state) ? state : states[0];
  const woy = Math.min(weekOfYear(new Date(Date.UTC(2023, month - 1, 15))), 51);
  const pred = useMemo(() => (model && st && hi !== null && h !== null ? evaluate(model, st, woy, { heat_index: hi, rh: h }) : null), [model, st, woy, hi, h]);
  const sel = 'bg-void border border-line px-2 py-1 text-[13px] text-text';
  return (
    <div className="grid lg:grid-cols-3 gap-4" role="region" aria-label="What the live readings mean">
      <div className="border border-line p-4 min-w-0" style={{ borderTop: `2px solid ${cat?.tone ?? 'var(--line)'}` }}>
        <div className="label mb-2">Heat comfort</div>
        {cat && hi !== null ? (
          <>
            <div className="display text-3xl leading-none" style={{ color: cat.tone }}>{cat.label}</div>
            <div className="num text-sm text-muted mt-2">heat index {hi.toFixed(1)} °C</div>
            <p className="text-[13px] text-muted mt-3 mb-0 leading-snug">{cat.advice}</p>
            <p className="text-[11.5px] text-faint mt-2 mb-0">From the temperature and humidity just measured, by the US National Weather Service heat-index formula.</p>
          </>
        ) : <p className="text-[13px] text-faint m-0">Waiting for a temperature and humidity reading.</p>}
      </div>

      <div className="border border-line p-4 min-w-0" style={{ borderTop: `2px solid ${smoke.state === 'detected' ? 'var(--alert)' : smoke.state === 'elevated' ? 'var(--solar)' : 'var(--biosphere)'}` }}>
        <div className="label mb-2">Smoke alert</div>
        {!smoke.ready ? (
          <>
            <div className="display text-3xl leading-none text-muted">Learning</div>
            <div className="h-1.5 bg-line mt-3"><div className="h-full bg-signal" style={{ width: `${Math.min(100, (smoke.learned / smoke.needed) * 100)}%` }} /></div>
            <p className="text-[12px] text-faint mt-2 mb-0">Measuring this room&rsquo;s clean-air level: {smoke.learned} of {smoke.needed} readings.</p>
          </>
        ) : (
          <>
            <div className="display text-3xl leading-none" style={{ color: smoke.state === 'detected' ? 'var(--alert)' : smoke.state === 'elevated' ? 'var(--solar)' : 'var(--biosphere)' }}>
              {smoke.state === 'detected' ? 'Smoke or gas detected' : smoke.state === 'elevated' ? 'Slightly elevated' : 'Clean air'}</div>
            <div className="num text-sm text-muted mt-2">{pct(smoke.abovePct ?? 0, 0)} vs this room&rsquo;s clean-air level</div>
            <p className="text-[11.5px] text-faint mt-3 mb-0 leading-snug">The MQ sensor reacts to smoke and several other gases. This compares it with its own baseline ({smoke.baseline} raw counts); it is not a particle count.</p>
          </>
        )}
      </div>

      <div className="border border-line p-4 min-w-0 lg:row-span-1" style={{ borderTop: '2px solid var(--signal)' }}>
        <div className="label mb-2">Engine estimate</div>
        {pred && hi !== null ? (
          <>
            <div className="display text-3xl leading-none" style={{ color: pred.lo > 0 ? 'var(--alert)' : pred.hi < 0 ? 'var(--biosphere)' : 'var(--text)' }} aria-live="polite">{pct(pred.effect)}</div>
            <div className="num text-sm text-muted mt-2">weekly deaths, range {pct(pred.lo)} to {pct(pred.hi)}</div>
            <p className="text-[13px] text-muted mt-3 mb-2 leading-snug">
              If <select aria-label="State" value={st} onChange={(e) => setState(e.target.value)} className={sel}>{states.map((s) => <option key={s}>{s}</option>)}</select>{' '}
              in <select aria-label="Month" value={month} onChange={(e) => setMonth(Number(e.target.value))} className={sel}>{MONTHS.map((m, i) => <option key={m} value={i + 1}>{m}</option>)}</select>{' '}
              had these conditions (heat index {hi.toFixed(0)} °C, humidity {h?.toFixed(0)}%), versus a typical week.
            </p>
            {pred.support.unusual && <p className="text-[12px] text-solar m-0 mb-1">These conditions are far from anything that state normally sees, so treat this as a rough extrapolation.</p>}
            <p className="text-[11.5px] text-faint m-0 leading-snug">A model learned from real CDC deaths, EPA air and weather data for 46 US states, 2014 to 2019. An average association, not a forecast for any person, and your readings come from one room.</p>
          </>
        ) : mq.isLoading ? <p className="text-[13px] text-faint m-0">Loading the engine&rsquo;s model.</p>
          : mq.isError ? <p className="text-[13px] text-solar m-0">The engine&rsquo;s model is not available. Run  python scripts/build_scenario_model.py.</p>
          : <p className="text-[13px] text-faint m-0">Waiting for a temperature and humidity reading.</p>}
      </div>
    </div>
  );
}
