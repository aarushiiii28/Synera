import { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { useLiveFeed } from '../../lib/hooks';
import { SENSORS, VARS, qualityOf, timeOf, valueOf, windowOf, type LiveReading, type VarKey } from '../../lib/live';
import { PageHeader } from '../../components/PageHeader';
import { Panel } from '../../components/Panel';
import { EmptyState } from '../../components/States';
import { Explainer } from '../../components/Explainer';
import { ConnectionPanel, StateDot } from '../../components/live/ConnectionPanel';
import { SensorCard } from '../../components/live/SensorCard';
import { LiveChart } from '../../components/live/LiveChart';
import { ScenarioBuilder } from '../../components/live/ScenarioBuilder';
import { InteractionExplorer } from '../../components/live/InteractionExplorer';
import { HistoryCompare } from '../../components/live/HistoryCompare';
import { ProvenancePanel } from '../../components/live/ProvenancePanel';
import { ProvBadge } from '../../components/live/Badges';

const WINDOWS: { label: string; s: number | null }[] = [{ label: '1 min', s: 60 }, { label: '5 min', s: 300 }, { label: '15 min', s: 900 }, { label: 'All', s: null }];

function Section({ n, title, lead, children, right }: { n: string; title: string; lead?: string; children: React.ReactNode; right?: React.ReactNode }) {
  return (
    <section className="px-6 md:px-10 mt-12" aria-labelledby={`s-${n}`}>
      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-2 mb-1"><span className="num text-signal text-xs">{n}</span><h2 id={`s-${n}`} className="display font-semibold uppercase tracking-tight text-xl md:text-2xl m-0">{title}</h2><span className="flex-1" />{right}</div>
      {lead && <p className="text-[15px] text-muted max-w-3xl mt-1 mb-5 leading-relaxed">{lead}</p>}
      {children}
    </section>
  );
}

export default function LiveStressLab() {
  const feed = useLiveFeed();
  const { status, readings, apiError, unavailable } = feed;
  const [paused, setPaused] = useState(false);
  const [frozen, setFrozen] = useState<LiveReading[] | null>(null);
  const [win, setWin] = useState<number | null>(300);
  const [enabled, setEnabled] = useState<Set<VarKey>>(new Set<VarKey>(['temperature', 'humidity', 'gas']));
  const [explore, setExplore] = useState<VarKey[]>(['temperature', 'humidity']);
  const test = status?.state === 'TEST_MODE';
  const shownAll = paused ? frozen ?? readings : readings;
  const shown = useMemo(() => windowOf(shownAll, win), [shownAll, win]);
  const last = readings.length ? readings[readings.length - 1] : null;
  const lastShown = shown.length ? shown[shown.length - 1] : null;
  const state = status?.state ?? 'DISCONNECTED';
  const t = last ? valueOf(last, 'temperature') : null, h = last ? valueOf(last, 'humidity') : null, g = last ? valueOf(last, 'gas') : null;
  const live = t !== null && h !== null && g !== null ? { temperature: t, humidity: h, gas: g } : null;
  const toggleVar = (k: VarKey) => setEnabled((s) => { const n = new Set(s); if (n.has(k)) n.delete(k); else n.add(k); return n; });
  const togglePause = () => { setFrozen(paused ? null : readings); setPaused(!paused); };
  const empty = unavailable ? 'This recorded demo has no hardware. Run SYNERA locally with the Arduino connected to see live readings.'
    : state === 'DISCONNECTED' ? 'Not connected. Connect the device above; nothing is drawn until real packets arrive.' : state === 'ERROR' ? 'The device is not delivering valid data. See the connection panel.' : 'Waiting for the first valid packet.';

  return (
    <div className="pb-20">
      <PageHeader kicker="LIVE STRESS LAB" title={<>Real sensors, <span className="serif normal-case font-normal text-sun" style={{ fontSize: '1.08em' }}>real conditions</span></>}
        standfirst="An Arduino with a temperature and humidity sensor and a gas sensor streams physical measurements into SYNERA. Watch them, build stress scenarios around them, and see exactly where every number came from. Nothing on this page is invented: if the device is silent, the page says so."
        right={<div className="hidden md:grid gap-1 justify-items-end"><StateDot state={state} receiving={status?.receiving} />
          <span className="num text-[10px] text-faint">{paused ? 'PAUSED' : state === 'CONNECTED' || test ? 'LIVE' : 'NOT LIVE'} · last update {last ? new Date(timeOf(last)).toLocaleTimeString() : '—'}</span>
          <span className="num text-[10px]" style={{ color: test ? 'var(--solar)' : 'var(--biosphere)' }}>{test ? 'SIMULATED TEST DATA' : last ? 'REAL SENSOR DATA' : 'NO DATA'}</span></div>} />

      {test && (
        <div role="alert" className="mx-6 md:mx-10 mb-2 hatch-alert border border-solar/70 px-4 py-3">
          <div className="num text-solar text-xs tracking-[0.18em]">SIMULATED TEST DATA</div>
          <div className="text-sm">Every value below comes from a test generator, not from a sensor. It exists only to check the interface. Stop it and connect the device for real readings.</div>
        </div>)}
      {unavailable && (
        <div className="mx-6 md:mx-10 mb-2 border border-line px-4 py-3 text-sm text-muted">
          <span className="num text-xs tracking-[0.16em] text-solar">RECORDED DEMO</span> This copy of SYNERA runs without a server, so it cannot reach hardware. The scenario builder and the interaction explorer below work locally in your browser; live sensors need SYNERA running on the computer the Arduino is plugged into.
        </div>)}

      <Section n="01" title="Connect the device" lead="Choose the serial port of the Arduino Uno and open it. The status turns to CONNECTED only when valid readings arrive, not when a port is merely found.">
        <Panel variant="bracketed" title="Physical device" index="A" right={<span className="num text-[10px] tracking-[0.14em] text-faint">USB · SERIAL · 9600 BAUD</span>}>
          {unavailable ? <EmptyState title="No device in the recorded demo">Start the API locally (dev.cmd), plug in the Arduino, and open this page there. <Link to="/guide" className="text-signal">How SYNERA works</Link>.</EmptyState>
            : <ConnectionPanel status={status} apiError={apiError} />}
        </Panel>
        <details className="mt-3 text-[13px] text-muted"><summary className="cursor-pointer text-signal">Expected wiring and firmware</summary>
          <ul className="mt-2 mb-0 pl-5 leading-relaxed"><li>DHT11: VCC to 5V, GND to GND, OUT to digital pin 2.</li><li>Gas module: VCC to 5V, GND to GND, AO to A0 (check the printed pin labels: the order differs between modules). DO is not used.</li>
            <li>Keep pins 0 and 1 free: they carry the USB serial line.</li><li>Upload <span className="num">firmware/synera_live_stress_lab</span> to the Uno. It prints <span className="num">time_ms,temperature_C,humidity_pct,gas_raw</span> every two seconds.</li></ul></details>
      </Section>

      <Section n="02" title="Real-time readings" lead="The latest value of each sensor, with the range seen in the chart window and the quality of the newest reading."
        right={<ProvBadge prov={test ? 'SIMULATED' : 'REAL SENSOR'} />}>
        <div className="grid sm:grid-cols-3 gap-4">{SENSORS.map((s) => <SensorCard key={s.key} k={s.key} readings={shown} test={test} />)}</div>
        {lastShown && SENSORS.some((s) => qualityOf(lastShown, s.key) === 'MISSING') && <p className="text-[13px] text-solar mt-3 mb-0">The DHT11 did not answer on the latest reading. It is shown as missing and was not filled in.</p>}
      </Section>

      <Section n="03" title="Live charts" lead="Bounded history of what actually arrived. Hover for exact values. Gaps stay gaps."
        right={<div className="flex flex-wrap items-center gap-2">
          <div role="group" aria-label="Time window" className="flex">{WINDOWS.map((w) => <button key={w.label} type="button" aria-pressed={win === w.s} onClick={() => setWin(w.s)} className={`num text-[10px] tracking-[0.1em] px-2.5 py-1 border ${win === w.s ? 'border-signal text-signal bg-signal/10' : 'border-line text-muted hover:text-text'}`}>{w.label}</button>)}</div>
          <button type="button" onClick={togglePause} disabled={unavailable || (!readings.length && !paused)} className={`num text-[10px] tracking-[0.12em] px-3 py-1 border disabled:opacity-40 ${paused ? 'border-solar text-solar' : 'border-line text-muted hover:text-text'}`}>{paused ? 'RESUME' : 'PAUSE'}</button></div>}>
        <div className="grid lg:grid-cols-3 gap-4">
          {SENSORS.map((s) => (
            <div key={s.key} className="border border-line p-3 min-w-0"><div className="flex items-center mb-1"><span className="label">{s.label}</span><span className="flex-1" /><span className="num text-[10px] text-faint">{s.unit}</span></div>
              <LiveChart points={shown.map((r) => ({ t: timeOf(r), v: valueOf(r, s.key) }))} unit={s.unit} label={s.label} color={s.color} digits={s.digits} empty={empty} includeZero={s.key === 'gas'} /></div>))}
        </div>
        {paused && <p className="text-[12px] text-solar mt-2 mb-0">Paused: the charts are frozen. Readings keep arriving in the background and appear when you resume.</p>}
      </Section>

      <Section n="04" title="Stressor explorer" lead="Every variable you can use in an experiment, with where it comes from. Real sensor values are measured; the others are inputs you set, or observations from a real historical dataset. Switch variables on or off for the scenario builder.">
        <div className="overflow-x-auto"><table className="w-full text-[13px] border-collapse min-w-[640px]">
          <thead><tr className="text-left text-faint num text-[10px] tracking-[0.12em] uppercase border-b border-line"><th className="py-2 pr-3 font-normal">Use</th><th className="py-2 pr-3 font-normal">Variable</th><th className="py-2 pr-3 font-normal">Category</th><th className="py-2 pr-3 font-normal">Source</th><th className="py-2 font-normal text-right">Now</th></tr></thead>
          <tbody>
            {VARS.map((v) => { const sens = SENSORS.find((s) => s.key === v.key); const now = sens && last ? valueOf(last, sens.key) : null; return (
              <tr key={v.key} className="border-b border-line/60">
                <td className="py-2 pr-3"><input type="checkbox" aria-label={`Use ${v.label}`} checked={enabled.has(v.key)} onChange={() => toggleVar(v.key)} className="accent-[var(--signal)]" /></td>
                <td className="py-2 pr-3">{v.label} <span className="text-faint">{v.unit}</span></td>
                <td className="py-2 pr-3"><ProvBadge prov={sens && test ? 'SIMULATED' : v.prov} /></td>
                <td className="py-2 pr-3 text-muted">{v.source}</td>
                <td className="py-2 num text-right">{sens ? (now === null ? <span className="text-faint">no reading</span> : now.toFixed(sens.digits)) : <span className="text-faint">you set it</span>}</td>
              </tr>); })}
            <tr><td className="py-2 pr-3"><input type="checkbox" checked disabled aria-label="Historical comparison is always available" /></td><td className="py-2 pr-3">Outdoor temperature and humidity, daily</td><td className="py-2 pr-3"><ProvBadge prov="HISTORICAL" /></td><td className="py-2 pr-3 text-muted">SYNERA env_panel (Open-Meteo / ERA5), compared in section 07</td><td className="py-2 num text-right text-faint">dataset</td></tr>
          </tbody></table></div>
      </Section>

      <Section n="05" title="Scenario builder" lead="Describe a baseline and some stressed conditions, then compare them. The baseline can be the reading your sensor is giving right now.">
        <Panel variant="bracketed" title="Multi-stressor scenarios" index="B" right={<ProvBadge prov="DERIVED" />}>
          <ScenarioBuilder enabled={enabled} live={live} source={test ? 'TEST' : last ? 'REAL' : null} />
        </Panel>
      </Section>

      <Section n="06" title="Interaction explorer" lead="Do two stressors act together in a way that is more, less, or different from adding them up? Explore it on a physical formula, and be clear about what that does not prove.">
        <Panel variant="ruled" title="Exploratory scenario analysis" index="C" right={<span className="num text-[10px] tracking-[0.14em] text-solar">NOT A VALIDATED DISCOVERY</span>}>
          <InteractionExplorer selected={explore} setSelected={setExplore} />
        </Panel>
        <Explainer className="mt-5" tone="solar" title="Where real interaction discovery happens">
          SYNERA&rsquo;s statistical interaction engine needs an outcome that was measured, many observations and strict error control: see the <Link to="/discovery" className="text-signal">Discovery Lab</Link> and the <Link to="/findings" className="text-signal">Findings</Link>. A few hours of room readings cannot do that, and this page does not pretend to.
        </Explainer>
      </Section>

      <Section n="07" title="Historical comparison" lead="Where your reading sits among real outdoor observations already in SYNERA, with every difference between the two stated.">
        <Panel variant="inset" title="Current reading against real data" index="D" right={<ProvBadge prov="HISTORICAL" />}>
          <HistoryCompare temperature={test ? null : t} humidity={test ? null : h} unavailable={unavailable} />
        </Panel>
      </Section>

      <Section n="08" title="Provenance and trust" lead="Select any value to see its source, device, timestamp, units, processing steps, validation and limitations.">
        <Panel variant="bracketed" title="Where every number comes from" index="E">
          <ProvenancePanel status={status} last={last} test={test} />
        </Panel>
        <div className="mt-4 border-l-2 border-solar pl-4 max-w-3xl text-[13px] text-muted leading-relaxed">
          This module is separate from SYNERA&rsquo;s NASA GeneLab space-biology analysis. A DHT11 and a gas sensor do not reproduce radiation or microgravity, and nothing measured here says anything about gene expression. Sensor readings describe air in a room, not a biological effect.
        </div>
      </Section>
    </div>
  );
}
