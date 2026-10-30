import { useMemo, useState } from 'react';
import { useScenarioModel } from '../../lib/hooks';
import { evaluate, weekOfYear } from '../../lib/scenario';
import { heatCategory, heatIndexC, smokeLevel, smokeToPm25, valueOf, type LiveReading } from '../../lib/live';

const MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];
const pct = (x: number, d = 2) => `${x >= 0 ? '+' : ''}${x.toFixed(d)}%`;

/** What the live readings mean: heat comfort, smoke alert, and feeding live sensor data into the Synera predictive engine. */
export function Insights({ readings }: { readings: LiveReading[] }) {
  const last = readings.length ? readings[readings.length - 1] : null;
  const t = last ? valueOf(last, 'temperature') : null;
  const h = last ? valueOf(last, 'humidity') : null;
  const g = last ? valueOf(last, 'gas') : null;
  const hi = t !== null && h !== null ? heatIndexC(t, h) : null;
  const cat = hi === null ? null : heatCategory(hi);
  const smoke = useMemo(() => smokeLevel(readings.map((r) => valueOf(r, 'gas'))), [readings]);

  // Derived PM2.5 proxy from smoke/gas sensor
  const pm25 = useMemo(() => smokeToPm25(g, smoke.baseline, smoke.abovePct), [g, smoke.baseline, smoke.abovePct]);
  const [usePmProxy, setUsePmProxy] = useState(true);

  const mq = useScenarioModel('all');
  const model = mq.data;
  const states = model ? Object.keys(model.locations).sort() : [];
  const [state, setState] = useState('Texas');
  const [month, setMonth] = useState(new Date().getMonth() + 1);
  const st = states.includes(state) ? state : states[0];
  const woy = Math.min(weekOfYear(new Date(Date.UTC(2023, month - 1, 15))), 51);

  // Feed temperature, humidity, and the smoke-derived PM2.5 proxy directly to the engine
  const levels = useMemo(() => {
    const l: Record<string, number> = {};
    if (hi !== null) l.heat_index = hi;
    if (h !== null) l.rh = h;
    if (usePmProxy && pm25 !== null) l.pm25 = pm25;
    return l;
  }, [hi, h, pm25, usePmProxy]);

  const pred = useMemo(
    () => (model && st && hi !== null && h !== null ? evaluate(model, st, woy, levels) : null),
    [model, st, woy, levels]
  );

  const sel = 'bg-void border border-line px-2 py-1 text-[13px] text-text rounded';

  return (
    <div role="region" aria-label="What the live readings mean">
      <div className="grid lg:grid-cols-3 gap-4">
        {/* Card 1: Heat Comfort */}
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

        {/* Card 2: Smoke Alert & PM2.5 Proxy */}
        <div className="border border-line p-4 min-w-0" style={{ borderTop: `2px solid ${smoke.state === 'detected' ? 'var(--alert)' : smoke.state === 'elevated' ? 'var(--solar)' : 'var(--biosphere)'}` }}>
          <div className="flex items-center justify-between mb-2">
            <div className="label">Smoke alert</div>
            {pm25 !== null && (
              <span className="num text-[11px] text-signal font-semibold tracking-wide">
                {pm25.toFixed(1)} µg/m³ PM2.5
              </span>
            )}
          </div>
          {!smoke.ready ? (
            <>
              <div className="display text-3xl leading-none text-muted">Learning</div>
              <div className="h-1.5 bg-line mt-3"><div className="h-full bg-signal" style={{ width: `${Math.min(100, (smoke.learned / smoke.needed) * 100)}%` }} /></div>
              <div className="mt-2.5 text-[12.5px] text-muted flex items-center justify-between">
                <span>Provisional PM2.5 proxy:</span>
                <span className="num font-semibold text-text">{pm25 !== null ? `${pm25.toFixed(1)} µg/m³` : '—'}</span>
              </div>
              <p className="text-[11.5px] text-faint mt-2 mb-0">Measuring room baseline: {smoke.learned} of {smoke.needed} readings.</p>
            </>
          ) : (
            <>
              <div className="display text-3xl leading-none" style={{ color: smoke.state === 'detected' ? 'var(--alert)' : smoke.state === 'elevated' ? 'var(--solar)' : 'var(--biosphere)' }}>
                {smoke.state === 'detected' ? 'Smoke or gas detected' : smoke.state === 'elevated' ? 'Slightly elevated' : 'Clean air'}
              </div>
              <div className="num text-sm text-muted mt-2">{pct(smoke.abovePct ?? 0, 0)} vs room clean-air level</div>
              <div className="mt-3 pt-2.5 border-t border-line/60 flex items-center justify-between text-[12.5px]">
                <span className="text-muted">Smoke → PM2.5 Proxy:</span>
                <span className="num font-bold text-signal">{pm25 !== null ? `${pm25.toFixed(1)} µg/m³` : '—'}</span>
              </div>
              <p className="text-[11px] text-faint mt-2 mb-0 leading-snug">
                The MQ sensor reads raw gas/smoke. SYNERA maps the baseline-relative elevation to an estimated PM2.5 particulate proxy for compound risk prediction.
              </p>
            </>
          )}
        </div>

        {/* Card 3: Engine Estimate */}
        <div className="border border-line p-4 min-w-0 lg:row-span-1" style={{ borderTop: '2px solid var(--signal)' }}>
          <div className="flex items-center justify-between mb-2">
            <div className="label">Engine estimate</div>
            {pm25 !== null && (
              <button
                type="button"
                onClick={() => setUsePmProxy(!usePmProxy)}
                title="Toggle feeding smoke-to-PM proxy into the scenario engine"
                className={`num text-[10px] tracking-[0.08em] px-2 py-0.5 border rounded cursor-pointer transition-colors ${
                  usePmProxy ? 'border-signal text-signal bg-signal/10' : 'border-line text-muted hover:text-text'
                }`}
              >
                PM PROXY: {usePmProxy ? 'ON' : 'OFF'}
              </button>
            )}
          </div>
          {pred && hi !== null ? (
            <>
              <div className="display text-3xl leading-none" style={{ color: pred.lo > 0 ? 'var(--alert)' : pred.hi < 0 ? 'var(--biosphere)' : 'var(--text)' }} aria-live="polite">
                {pct(pred.effect)}
              </div>
              <div className="num text-sm text-muted mt-2">weekly deaths, range {pct(pred.lo)} to {pct(pred.hi)}</div>

              {/* Stressor Breakdown */}
              <div className="grid grid-cols-3 gap-1.5 mt-3 pt-2.5 border-t border-line/60 text-center">
                <div className="border border-line/50 p-1.5 rounded bg-void/40">
                  <div className="text-[10px] text-faint uppercase tracking-wider">Heat</div>
                  <div className="num text-xs text-text font-semibold mt-0.5">{pct(pred.contributions['heat_index'] ?? 0)}</div>
                </div>
                <div className="border border-line/50 p-1.5 rounded bg-void/40">
                  <div className="text-[10px] text-faint uppercase tracking-wider">Humidity</div>
                  <div className="num text-xs text-text font-semibold mt-0.5">{pct(pred.contributions['rh'] ?? 0)}</div>
                </div>
                <div className="border border-line/50 p-1.5 rounded bg-void/40">
                  <div className="text-[10px] text-faint uppercase tracking-wider">Smoke (PM)</div>
                  <div className="num text-xs text-text font-semibold mt-0.5">
                    {usePmProxy && pm25 !== null ? pct(pred.contributions['pm25'] ?? 0) : <span className="text-faint">Off</span>}
                  </div>
                </div>
              </div>

              <p className="text-[12.5px] text-muted mt-3 mb-2 leading-snug">
                If <select aria-label="State" value={st} onChange={(e) => setState(e.target.value)} className={sel}>{states.map((s) => <option key={s}>{s}</option>)}</select>{' '}
                in <select aria-label="Month" value={month} onChange={(e) => setMonth(Number(e.target.value))} className={sel}>{MONTHS.map((m, i) => <option key={m} value={i + 1}>{m}</option>)}</select>{' '}
                had these conditions (heat index {hi.toFixed(0)} °C, humidity {h?.toFixed(0)}%{usePmProxy && pm25 !== null ? `, smoke PM2.5 ${pm25.toFixed(0)} µg/m³` : ''}), versus a typical week.
              </p>
              {pred.support.unusual && <p className="text-[12px] text-solar m-0 mb-1">These conditions are far from anything that state normally sees, so treat this as a rough extrapolation.</p>}
              <p className="text-[11px] text-faint m-0 leading-snug">
                CDC deaths and EPA air model. {usePmProxy && pm25 !== null ? 'Live temperature, humidity, and smoke PM proxy are combined to predict compound impact.' : 'Only temperature and humidity fed to engine.'}
              </p>
            </>
          ) : mq.isLoading ? <p className="text-[13px] text-faint m-0">Loading the engine&rsquo;s model.</p>
            : mq.isError ? <p className="text-[13px] text-solar m-0">The engine&rsquo;s model is not available. Run python scripts/build_scenario_model.py.</p>
            : <p className="text-[13px] text-faint m-0">Waiting for a temperature and humidity reading.</p>}
        </div>
      </div>

      {/* Live Engine Multi-Stressor Banner */}
      {pred && hi !== null && (
        <div className="mt-4 border border-line bg-surface/30 p-3.5 rounded flex flex-wrap items-center justify-between gap-3 text-[13px]">
          <div className="flex items-center gap-2.5">
            <span className="w-2.5 h-2.5 rounded-full bg-signal animate-pulse" />
            <span className="font-semibold text-text uppercase tracking-wider text-xs">Live Engine Feed Active:</span>
            <span className="text-muted">
              Heat Index <b className="text-text">{hi.toFixed(1)}°C</b> · Humidity <b className="text-text">{h?.toFixed(0)}%</b> · Smoke Proxy{' '}
              <b className="text-text">{usePmProxy && pm25 !== null ? `${pm25.toFixed(1)} µg/m³ PM2.5` : 'OFF'}</b>
            </span>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-faint text-xs">Net Predicted Risk:</span>
            <span className="num font-bold text-sm" style={{ color: pred.effect > 0 ? 'var(--alert)' : 'var(--biosphere)' }}>
              {pct(pred.effect)}
            </span>
            <span className="text-[11px] text-faint">[{pct(pred.lo)} to {pct(pred.hi)}]</span>
          </div>
        </div>
      )}
    </div>
  );
}
