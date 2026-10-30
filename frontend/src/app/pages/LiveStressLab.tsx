import { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { useLiveFeed } from '../../lib/hooks';
import { SENSORS, timeOf, valueOf, windowOf, type LiveReading } from '../../lib/live';
import { PageHeader } from '../../components/PageHeader';
import { Panel } from '../../components/Panel';
import { EmptyState } from '../../components/States';
import { ConnectionPanel, StateDot } from '../../components/live/ConnectionPanel';
import { SensorCard } from '../../components/live/SensorCard';
import { LiveChart } from '../../components/live/LiveChart';
import { Insights } from '../../components/live/Insights';
import { InteractionCheck } from '../../components/live/InteractionCheck';

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
  const shownAll = paused ? frozen ?? readings : readings;
  const shown = useMemo(() => windowOf(shownAll, win), [shownAll, win]);
  const last = readings.length ? readings[readings.length - 1] : null;
  const state = status?.state ?? 'DISCONNECTED';
  const togglePause = () => { setFrozen(paused ? null : readings); setPaused(!paused); };
  const empty = unavailable ? 'This copy of SYNERA runs without a server, so there is no device to read. Run it locally with the Arduino plugged in.'
    : state === 'ERROR' ? 'The device is not delivering valid data. See the connection panel.' : state === 'DISCONNECTED' ? 'Not connected. Connect the device above; nothing is drawn until real readings arrive.' : 'Waiting for the first valid reading.';

  return (
    <div className="pb-20">
      <PageHeader kicker="LIVE STRESS LAB" title={<>Live air, <span className="serif normal-case font-normal text-sun" style={{ fontSize: '1.08em' }}>live prediction</span></>}
        standfirst="An Arduino with a temperature and humidity sensor and a smoke and gas sensor streams into SYNERA. The engine reads those conditions and tells you what they mean: how it feels, whether there is smoke, and what the same conditions have meant for people in the past."
        right={<div className="hidden md:grid gap-1 justify-items-end"><StateDot state={state} receiving={status?.receiving} />
          <span className="num text-[10px] text-faint">{paused ? 'PAUSED' : state === 'CONNECTED' ? 'LIVE' : 'NOT LIVE'} · last update {last ? new Date(timeOf(last)).toLocaleTimeString() : '—'}</span></div>} />

      <Section n="01" title="Connect the device" lead="Choose the Arduino's serial port and open it. It shows CONNECTED only once real readings arrive.">
        <Panel variant="bracketed" title="Arduino Uno" index="A" right={<span className="num text-[10px] tracking-[0.14em] text-faint">USB · 9600 BAUD</span>}>
          {unavailable ? <EmptyState title="Run SYNERA locally to use the device">Start the API (dev.cmd), plug in the Arduino and open this page there. <Link to="/guide" className="text-signal">How SYNERA works</Link>.</EmptyState>
            : <ConnectionPanel status={status} apiError={apiError} />}
        </Panel>
        <details className="mt-3 text-[13px] text-muted"><summary className="cursor-pointer text-signal">Wiring and firmware</summary>
          <ul className="mt-2 mb-0 pl-5 leading-relaxed"><li>DHT11: VCC to 5V, GND to GND, OUT to digital pin 2. Gas module: VCC to 5V, GND to GND, AO to A0.</li>
            <li>Keep pins 0 and 1 free. Upload <span className="num">firmware/synera_live_stress_lab</span> to the Uno; it sends a reading every two seconds.</li></ul></details>
      </Section>

      <Section n="02" title="What this means" lead="Worked out automatically from the live readings. There is nothing to adjust.">
        {last ? <Insights readings={readings} /> : <EmptyState title="Waiting for readings">Connect the device above. The heat comfort, smoke alert and engine estimate appear as soon as it sends data.</EmptyState>}
      </Section>

      <Section n="03" title="Interaction check" lead="The same engine that searches real health and electricity data, pointed at what your device collects: do temperature and humidity act together on the gas sensor's reading?">
        <Panel variant="ruled" title="Does the gas reading depend on temperature and humidity together?" index="B" right={<span className="num text-[10px] tracking-[0.14em] text-solar">EXPLORATORY · ONE DEVICE</span>}>
          <InteractionCheck readings={readings} unavailable={unavailable || !last} />
        </Panel>
      </Section>

      <Section n="04" title="Live readings">
        <div className="grid sm:grid-cols-3 gap-4">{SENSORS.map((s) => <SensorCard key={s.key} k={s.key} readings={shown} />)}</div>
      </Section>

      <Section n="05" title="Live charts" lead="Everything that actually arrived. Hover for exact values."
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
    </div>
  );
}
