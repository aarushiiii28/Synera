import { useState } from 'react';
import { SENSORS, VARS, derive, qualityOf, timeOf, valueOf, type LiveReading, type LiveStatus, type ProvClass } from '../../lib/live';
import { ProvBadge, QualityChip } from './Badges';

interface Item { id: string; label: string; prov: ProvClass; value: string; source: string; device: string; timestamp: string; units: string; processing: string[]; validation: string; limits: string[] }

/** Every value shown in this lab, where it came from and what is wrong with it. Click a row for the full record. */
export function ProvenancePanel({ status, last, test }: { status: LiveStatus | null; last: LiveReading | null; test: boolean }) {
  const [open, setOpen] = useState<string | null>(null);
  const device = test ? 'SIMULATED-TEST-GENERATOR (no hardware)' : status?.device_id ? `${status.device_id} on ${status.port} at ${status.baud} baud` : 'no device connected';
  const stamp = last ? `${new Date(timeOf(last)).toISOString()} (computer clock, on receipt; device clock ${last.time_ms} ms)` : 'no reading yet';
  const items: Item[] = [];
  for (const s of SENSORS) {
    const v = last ? valueOf(last, s.key) : null;
    items.push({
      id: s.key, label: s.label, prov: test ? 'SIMULATED' : 'REAL SENSOR', value: v === null ? (last ? 'missing' : 'none') : `${v.toFixed(s.digits)} ${s.unit}`,
      source: test ? 'the labelled test generator' : s.sensor, device, timestamp: stamp, units: s.unit,
      processing: ['Read from the serial line as text', 'Parsed as comma-separated numbers', 'Range-checked against what is physically possible and against the sensor\'s rated range', test ? 'Generated, not measured' : 'Stored unchanged: no smoothing, no calibration, no filling of gaps'],
      validation: last ? `quality of the latest value: ${qualityOf(last, s.key).replace(/_/g, ' ').toLowerCase()}` : 'nothing received',
      limits: s.key === 'gas' ? ['Raw ADC counts of an MQ-series module: not ppm, not AQI, not PM2.5', 'Needs a long pre-heat; uncalibrated; responds to several gases at once'] : ['DHT11: whole degrees / whole percent, ±2 °C and ±5 % RH', 'An indoor spot reading is not an outdoor daily mean'],
    });
  }
  const t = last ? valueOf(last, 'temperature') : null, h = last ? valueOf(last, 'humidity') : null;
  if (t !== null && h !== null) {
    const d = derive({ temperature: t, humidity: h });
    items.push({ id: 'hi', label: 'Heat index', prov: 'DERIVED', value: `${d.heatIndex.toFixed(1)} °C`, source: 'NWS Rothfusz regression applied to temperature and humidity', device, timestamp: stamp, units: '°C',
      processing: ['Inputs: the temperature and humidity above', 'Formula valid for T ≥ 27 °C and RH ≥ 40 %; a simple average formula is used elsewhere'], validation: 'computed from valid inputs', limits: ['Inherits the DHT11 error of both inputs', 'A formula, not a measurement of how a person feels'] });
    items.push({ id: 'dp', label: 'Dew point', prov: 'DERIVED', value: `${d.dewPoint.toFixed(1)} °C`, source: 'Magnus formula applied to temperature and humidity', device, timestamp: stamp, units: '°C',
      processing: ['Inputs: the temperature and humidity above'], validation: 'computed from valid inputs', limits: ['Inherits the DHT11 error of both inputs'] });
  }
  for (const v of VARS.filter((x) => x.prov === 'SIMULATED')) {
    items.push({ id: v.key, label: v.label, prov: 'SIMULATED', value: 'set by you', source: v.source, device: 'none', timestamp: 'when you type it', units: v.unit, processing: ['Entered in the scenario builder'], validation: 'not applicable', limits: [v.note] });
  }
  items.push({ id: 'hist', label: 'Outdoor daily observations', prov: 'HISTORICAL', value: 'real dataset', source: 'SYNERA env_panel: Open-Meteo historical archive (ERA5), CC BY 4.0', device: 'none', timestamp: 'Aug 2022 to Dec 2023', units: '°C, %',
    processing: ['Daily means per city', 'Fingerprinted in the evidence ledger'], validation: 'hash checked by the platform', limits: ['Outdoor daily means', 'Eight cities and sixteen months only'] });
  const sel = items.find((i) => i.id === open);
  return (
    <div className="grid lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)] gap-8">
      <ul className="list-none m-0 p-0 border-t border-line">
        {items.map((i) => (
          <li key={i.id} className="border-b border-line">
            <button type="button" onClick={() => setOpen(open === i.id ? null : i.id)} aria-expanded={open === i.id} className={`w-full text-left grid grid-cols-[1fr_auto] gap-x-4 items-center py-2.5 px-2 bg-transparent border-0 cursor-pointer ${open === i.id ? 'bg-signal/5' : 'hover:bg-white/[0.02]'}`}>
              <span className="text-[13.5px] text-text">{i.label}<span className="block num text-[11px] text-muted">{i.value}</span></span>
              <ProvBadge prov={i.prov} />
            </button>
          </li>))}
      </ul>
      <div className="min-w-0" aria-live="polite">
        {sel ? (
          <dl className="m-0 grid gap-3 text-[13px]">
            <div className="flex items-center gap-3"><span className="display text-lg">{sel.label}</span><ProvBadge prov={sel.prov} /></div>
            {([['Source', sel.source], ['Device', sel.device], ['Timestamp', sel.timestamp], ['Units', sel.units], ['Validation', sel.validation]] as const).map(([k, v]) => <div key={k}><dt className="label">{k}</dt><dd className="m-0 text-muted break-words">{v}</dd></div>)}
            <div><dt className="label">Processing steps</dt><dd className="m-0"><ol className="m-0 pl-5 text-muted">{sel.processing.map((p) => <li key={p}>{p}</li>)}</ol></dd></div>
            <div><dt className="label !text-solar">Limitations</dt><dd className="m-0"><ul className="m-0 pl-5 text-solar">{sel.limits.map((p) => <li key={p}>{p}</li>)}</ul></dd></div>
            {last && SENSORS.some((s) => s.key === sel.id) && <div><dt className="label">Latest quality</dt><dd className="m-0"><QualityChip q={qualityOf(last, sel.id as 'temperature' | 'humidity' | 'gas')} /></dd></div>}
          </dl>
        ) : <p className="text-[13px] text-faint m-0">Select a value to see its source, device, timestamp, units, processing steps, validation status and limitations.</p>}
      </div>
    </div>
  );
}
