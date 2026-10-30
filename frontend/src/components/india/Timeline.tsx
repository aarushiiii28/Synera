import { useEffect, useMemo, useRef, useState } from 'react';
import { line, scaleLinear } from 'd3';
import { color, fmt, type DailyPoint, type IndiaCity, type Series } from '../../lib/india';

type Key = 'aqi' | 'pm25' | 'temperature_c' | 'humidity_pct' | 'precip_mm' | 'wind_kmh';
const PARAMS: { key: Key; label: string; unit: string; layer?: 'aqi' | 'temperature' | 'humidity' | 'rainfall' | 'wind' }[] = [
  { key: 'aqi', label: 'AQI', unit: '', layer: 'aqi' }, { key: 'pm25', label: 'PM2.5', unit: 'µg/m³' }, { key: 'temperature_c', label: 'Temperature', unit: '°C', layer: 'temperature' },
  { key: 'humidity_pct', label: 'Humidity', unit: '%', layer: 'humidity' }, { key: 'precip_mm', label: 'Rain', unit: 'mm/h', layer: 'rainfall' }, { key: 'wind_kmh', label: 'Wind', unit: 'km/h', layer: 'wind' },
];
const AQI_BANDS: [number, number, string][] = [[0, 50, '#39B980'], [50, 100, '#A3D65C'], [100, 200, '#E9B44C'], [200, 300, '#EE8A3A'], [300, 400, '#E45D5D'], [400, 500, '#A8325E']];

function useSize(ref: React.RefObject<HTMLElement | null>) {
  const [s, set] = useState({ w: 0, h: 0 });
  useEffect(() => { const el = ref.current; if (!el) return; const ro = new ResizeObserver(([e]) => set({ w: Math.round(e.contentRect.width), h: Math.round(e.contentRect.height) })); ro.observe(el); return () => ro.disconnect(); }, [ref]);
  return s;
}

const m = { l: 40, r: 12, t: 10, b: 22 };

function Chart({ s, k }: { s: Series; k: Key }) {
  const box = useRef<HTMLDivElement>(null), { w, h } = useSize(box), height = Math.max(h, 96);
  const [hi, setHi] = useState<number | null>(null);
  const vals = useMemo(() => (s[k] ?? []) as (number | null)[], [s, k]);
  const geom = useMemo(() => {
    const ok = vals.filter((v): v is number => v !== null);
    if (!ok.length || w < 80) return null;
    let lo = Math.min(...ok), hi2 = Math.max(...ok);
    if (k === 'aqi') { lo = Math.min(lo, 0); hi2 = Math.max(hi2, 100); }
    if (k === 'precip_mm') { lo = 0; hi2 = Math.max(hi2, 2); }
    if (k === 'pm25') { lo = 0; hi2 = Math.max(hi2, 65); }
    const pad = (hi2 - lo) * 0.08 || 1;
    const x = scaleLinear().domain([0, vals.length - 1]).range([m.l, w - m.r]);
    const floor = k === 'aqi' || k === 'pm25' || k === 'precip_mm' || k === 'wind_kmh' ? 0 : k === 'humidity_pct' ? Math.max(0, lo - pad) : lo - pad;
    const y = scaleLinear().domain([floor, hi2 + pad]).range([height - m.b, m.t]).nice();
    const gen = line<number | null>().defined((d) => d !== null).x((_, i) => x(i)).y((d) => y(d as number));
    const past = vals.map((v, i) => (i <= s.now_index ? v : null)), fut = vals.map((v, i) => (i >= s.now_index ? v : null));
    return { x, y, past: gen(past), fut: gen(fut), ticks: y.ticks(4) };
  }, [vals, w, height, k, s.now_index]);
  const p = PARAMS.find((x) => x.key === k)!;
  const dayTicks = useMemo(() => s.time.map((t, i) => ({ t, i })).filter((o) => o.t.endsWith('T00:00')), [s.time]);
  if (!vals.some((v) => v !== null)) return <div ref={box} className="h-full grid place-items-center text-[12.5px] text-[var(--in-muted)]">No {p.label} data from the provider for this city right now.</div>;
  const hv = hi !== null ? vals[hi] : null;
  return (
    <div ref={box} className="relative w-full h-full">
      {geom && (
        <svg width={w} height={height} role="img" aria-label={`${p.label} over the past 3 days and next 3 days. Range ${fmt(Math.min(...(vals.filter((v) => v !== null) as number[])), 1)} to ${fmt(Math.max(...(vals.filter((v) => v !== null) as number[])), 1)} ${p.unit}.`}
          onPointerMove={(e) => { const r = e.currentTarget.getBoundingClientRect(); setHi(Math.max(0, Math.min(vals.length - 1, Math.round(geom.x.invert(e.clientX - r.left))))); }} onPointerLeave={() => setHi(null)}>
          {k === 'aqi' && AQI_BANDS.map(([a, b, c]) => { const y0 = geom.y(Math.min(b, geom.y.domain()[1])), y1 = geom.y(Math.max(a, geom.y.domain()[0])); return b > geom.y.domain()[0] && a < geom.y.domain()[1] ? <rect key={a} x={m.l} width={w - m.l - m.r} y={y0} height={Math.max(0, y1 - y0)} fill={c} opacity={0.1} /> : null; })}
          <rect x={geom.x(s.now_index)} width={Math.max(0, w - m.r - geom.x(s.now_index))} y={m.t} height={height - m.t - m.b} fill="rgba(99,179,237,0.06)" />
          {geom.ticks.map((t) => <g key={t}><line x1={m.l} x2={w - m.r} y1={geom.y(t)} y2={geom.y(t)} stroke="rgba(237,242,244,0.07)" /><text x={m.l - 6} y={geom.y(t) + 3.5} textAnchor="end" fontSize={10} fill="#5D6B73" className="num">{t}</text></g>)}
          {k === 'pm25' && [[60, 'India 24 h standard 60'], [15, 'WHO 15']].map(([v, l]) => geom.y(v as number) > m.t ? <g key={l}><line x1={m.l} x2={w - m.r} y1={geom.y(v as number)} y2={geom.y(v as number)} stroke="#E9B44C" strokeDasharray="3 4" opacity={0.6} /><text x={w - m.r - 2} y={geom.y(v as number) - 3} textAnchor="end" fontSize={9.5} fill="#E9B44C">{l}</text></g> : null)}
          {dayTicks.map(({ t, i }) => <g key={t}><line x1={geom.x(i)} x2={geom.x(i)} y1={m.t} y2={height - m.b} stroke="rgba(237,242,244,0.08)" /><text x={geom.x(i) + 3} y={height - 7} fontSize={10} fill="#5D6B73">{new Date(t).toLocaleDateString(undefined, { weekday: 'short', day: 'numeric' })}</text></g>)}
          <line x1={geom.x(s.now_index)} x2={geom.x(s.now_index)} y1={m.t} y2={height - m.b} stroke="#63B3ED" strokeWidth={1} />
          <text x={geom.x(s.now_index) + 4} y={m.t + 9} fontSize={9.5} fill="#63B3ED" className="num">NOW</text>
          <text x={w - m.r - 2} y={m.t + 9} fontSize={9.5} fill="#63B3ED" textAnchor="end" className="num" opacity={0.8}>FORECAST →</text>
          {k === 'precip_mm'
            ? vals.map((v, i) => v ? <rect key={i} x={geom.x(i) - 1.4} width={2.8} y={geom.y(v)} height={Math.max(0, geom.y(0) - geom.y(v))} fill="#3F8CC9" opacity={i > s.now_index ? 0.6 : 1} /> : null)
            : <><path d={geom.past ?? ''} fill="none" stroke="#EDF2F4" strokeWidth={1.8} /><path d={geom.fut ?? ''} fill="none" stroke="#63B3ED" strokeWidth={1.8} strokeDasharray="5 3" /></>}
          {hi !== null && hv !== null && <g><line x1={geom.x(hi)} x2={geom.x(hi)} y1={m.t} y2={height - m.b} stroke="rgba(237,242,244,0.5)" /><circle cx={geom.x(hi)} cy={geom.y(hv)} r={3.5} fill={p.layer ? color(p.layer, hv) : '#EDF2F4'} stroke="#0B1014" /></g>}
        </svg>)}
      {hi !== null && hv !== null && geom && (
        <div className="pointer-events-none absolute border border-[var(--in-line2)] bg-[#0B1014]/95 px-2.5 py-1.5 text-[11.5px]" style={{ left: Math.min(Math.max(geom.x(hi) + 10, 4), w - 168), top: 4 }}>
          <div className="num"><b>{fmt(hv, k === 'aqi' || k === 'pm25' ? 0 : 1)}</b> {p.unit}</div>
          <div className="num text-[10.5px] text-[var(--in-faint)]">{new Date(s.time[hi]).toLocaleString(undefined, { weekday: 'short', hour: '2-digit', minute: '2-digit' })} · {hi > s.now_index ? 'forecast' : 'model analysis'}</div>
        </div>)}
    </div>
  );
}

function Daily({ days }: { days: DailyPoint[] }) {
  const f = days.filter((d) => d.is_today || d.is_future);
  if (!f.length) return null;
  return (
    <div className="flex gap-3 text-[11px] text-[var(--in-muted)] overflow-x-auto">{f.map((d) => (
      <div key={d.date} className="num whitespace-nowrap border-l border-[var(--in-line)] pl-3"><div className="text-[var(--in-text)]">{d.is_today ? 'Today' : new Date(d.date).toLocaleDateString(undefined, { weekday: 'short', day: 'numeric' })}</div>
        <div>{fmt(d.tmin_c)}–{fmt(d.tmax_c)}°C · rain {fmt(d.precip_mm, 1)} mm · UV {fmt(d.uv_max)}</div></div>))}</div>
  );
}

export function Timeline({ data, loading }: { data?: IndiaCity; loading: boolean }) {
  const [k, setK] = useState<Key>('aqi');
  const s = data?.series;
  return (
    <section aria-label="Environmental timeline" className="h-full min-h-0 flex flex-col px-5 pt-2.5 pb-2.5 overflow-hidden">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1.5">
        <h2 className="lbl m-0">Timeline · {data?.available ? data.city.name : '—'}</h2>
        <div role="group" aria-label="Parameter" className="flex flex-wrap gap-1">{PARAMS.map((p) => <button key={p.key} type="button" aria-pressed={k === p.key} onClick={() => setK(p.key)} className={`px-2 py-0.5 text-[11.5px] border ${k === p.key ? 'border-[var(--in-accent)] bg-[var(--in-accent)]/10' : 'border-transparent text-[var(--in-muted)] hover:text-[var(--in-text)]'}`}>{p.label}</button>)}</div>
        <span className="flex-1" />
        <span className="num text-[10px] text-[var(--in-faint)]">3 days of model analysis · 3 days of forecast · IST{k === 'aqi' ? ' · 24 h rolling PM index' : ''}</span>
      </div>
      <div className="flex-1 min-h-[110px] mt-1">
        {loading ? <div className="india-skel h-full" aria-busy="true" /> : s ? <Chart s={s} k={k} /> :
          <div className="h-full grid place-items-center text-[12.5px] text-[var(--in-muted)]">{data && !data.available ? 'No series available for this city.' : 'Select a city to see its recent and forecast conditions.'}</div>}
      </div>
      {data?.daily && <Daily days={data.daily} />}
    </section>
  );
}
