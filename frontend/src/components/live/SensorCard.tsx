import { SENSORS, qualityOf, seriesStats, timeOf, valueOf, type LiveReading, type SensorKey } from '../../lib/live';
import { ProvBadge, QualityChip } from './Badges';

const ARROW = { rising: '▲', falling: '▼', steady: '■' } as const;

/** One sensor: the current value, the previous one, the range seen in this window and a trend, with its provenance and the quality of the latest reading. */
export function SensorCard({ k, readings, test }: { k: SensorKey; readings: LiveReading[]; test: boolean }) {
  const s = SENSORS.find((x) => x.key === k)!;
  const st = seriesStats(readings.map((r) => valueOf(r, k)), k === 'gas' ? 2 : 0.2);
  const last = readings[readings.length - 1];
  const fmt = (v: number | null) => (v === null ? '—' : v.toFixed(s.digits));
  const q = last ? qualityOf(last, k) : null;
  return (
    <div className="border border-line px-4 py-3 min-w-0" style={{ borderTop: `2px solid ${s.color}` }}>
      <div className="flex items-center gap-2 mb-1">
        <span className="label">{s.label}</span><span className="flex-1" />
        <ProvBadge prov={test ? 'SIMULATED' : 'REAL SENSOR'} />
      </div>
      <div className="flex items-baseline gap-2">
        <span key={last?.seq ?? 'none'} className="num text-4xl leading-none tick-in" style={{ color: st.current === null ? 'var(--faint)' : s.color }} aria-live="polite">{fmt(st.current)}</span>
        <span className="num text-sm text-muted">{s.unit}</span>
        {st.trend && <span className="num text-[11px] ml-auto text-muted" title={`trend over the last readings: ${st.trend}`}>{ARROW[st.trend]} {st.trend}</span>}
      </div>
      <dl className="grid grid-cols-3 gap-2 m-0 mt-3 text-[12px]">
        <div><dt className="label !text-[9px]">Previous</dt><dd className="m-0 num text-muted">{fmt(st.previous)}</dd></div>
        <div><dt className="label !text-[9px]">Min</dt><dd className="m-0 num text-muted">{fmt(st.min)}</dd></div>
        <div><dt className="label !text-[9px]">Max</dt><dd className="m-0 num text-muted">{fmt(st.max)}</dd></div>
      </dl>
      <div className="flex items-center gap-2 mt-3 text-[11px] text-faint">
        <span className="truncate">{s.sensor}</span><span className="flex-1" />
        {q && <QualityChip q={q} />}
      </div>
      <div className="num text-[10px] text-faint mt-1">{last ? `updated ${new Date(timeOf(last)).toLocaleTimeString()}` : 'no reading yet'}</div>
      {k === 'gas' && <p className="text-[11px] text-solar m-0 mt-2 leading-snug">Raw ADC counts, 0 to 1023. Not ppm, not AQI, not PM2.5.</p>}
    </div>
  );
}
