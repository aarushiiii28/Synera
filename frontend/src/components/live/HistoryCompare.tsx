import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api, type LiveDist } from '../../lib/api';
import { Async } from '../States';
import { ProvBadge } from './Badges';

function Band({ d, label, color }: { d: LiveDist; label: string; color: string }) {
  const lo = d.min, hi = d.max, pos = (v: number) => `${Math.max(0, Math.min(100, ((v - lo) / (hi - lo || 1)) * 100))}%`;
  const q = d.quantiles;
  return (
    <div className="mb-5">
      <div className="flex items-baseline gap-3 mb-1"><span className="label">{label}</span><span className="num text-[11px] text-faint">{d.n_days} days · {d.min.toFixed(1)} to {d.max.toFixed(1)} {d.unit}</span></div>
      <div className="relative h-7" role="img" aria-label={`${label}: ${d.reading === null ? 'no reading' : `reading ${d.reading} ${d.unit}, higher than ${d.percentile_of_reading?.toFixed(0)}% of days`}`}>
        <div className="absolute inset-x-0 top-3 h-px bg-line" />
        <div className="absolute top-2 h-3 opacity-25" style={{ left: pos(q['5']), width: `calc(${pos(q['95'])} - ${pos(q['5'])})`, background: color }} title="5th to 95th percentile of days" />
        <div className="absolute top-1.5 h-4 opacity-45" style={{ left: pos(q['25']), width: `calc(${pos(q['75'])} - ${pos(q['25'])})`, background: color }} title="25th to 75th percentile" />
        <div className="absolute top-1 h-5 w-px" style={{ left: pos(q['50']), background: color }} title={`median ${q['50'].toFixed(1)} ${d.unit}`} />
        {d.reading !== null && <div className="absolute top-0 h-7 w-0.5 bg-text" style={{ left: pos(d.reading) }} title={`your reading: ${d.reading} ${d.unit}`}><span className="absolute -top-4 -translate-x-1/2 num text-[10px] text-text whitespace-nowrap">now</span></div>}
      </div>
      <div className="num text-[11px] text-muted">{d.reading === null ? 'No live reading to place on this band.' : <>Your reading ({d.reading} {d.unit}) is at the <span className="text-text">{d.percentile_of_reading?.toFixed(0)}th</span> percentile of these daily values.</>}</div>
    </div>
  );
}

/** Where the current reading sits among REAL outdoor daily observations already in SYNERA, with every limitation of that comparison stated. */
export function HistoryCompare({ temperature, humidity, unavailable }: { temperature: number | null; humidity: number | null; unavailable: boolean }) {
  const [city, setCity] = useState('Ludhiana');
  const t = temperature === null ? null : Math.round(temperature), h = humidity === null ? null : Math.round(humidity);
  const q = useQuery({ queryKey: ['live-history', city, t, h], queryFn: () => api.liveHistory({ city, temperature: t, humidity: h }), enabled: !unavailable, retry: false });
  if (unavailable) return <p className="text-sm text-muted m-0">Historical comparison needs the local API. This recorded demo has no live device and no query service, so nothing is compared.</p>;
  return (
    <Async q={q} h={180}>
      {(d) => (
        <div>
          <div className="flex flex-wrap items-center gap-3 mb-4">
            <label className="flex items-center gap-2 text-[13px] text-muted">City <select value={city} onChange={(e) => setCity(e.target.value)} className="bg-void border border-line px-2 py-1 text-text">{d.dataset.cities.map((c) => <option key={c}>{c}</option>)}</select></label>
            <ProvBadge prov="HISTORICAL" />
            <span className="num text-[11px] text-faint">{d.dataset.name} · {d.dataset.date_start} to {d.dataset.date_end}</span>
          </div>
          <div className="grid md:grid-cols-2 gap-x-10">
            <Band d={d.temperature} label="Temperature" color="var(--solar)" />
            <Band d={d.humidity} label="Relative humidity" color="var(--signal)" />
          </div>
          <dl className="grid sm:grid-cols-2 gap-x-8 gap-y-2 m-0 text-[12.5px] text-muted">
            <div><dt className="label">Source</dt><dd className="m-0">{d.dataset.source}</dd></div>
            <div><dt className="label">Fingerprint</dt><dd className="m-0 num break-all">{d.dataset.sha256?.slice(0, 24) ?? 'n/a'}…</dd></div>
          </dl>
          <ul className="m-0 mt-4 pl-5 text-[12.5px] text-solar leading-relaxed">{d.caveats.map((c) => <li key={c}>{c}</li>)}</ul>
        </div>
      )}
    </Async>
  );
}
