import { color, fmt, URGENCY_STYLE, type IndiaOverview } from '../../lib/india';

const AQI_ORDER: [string, string][] = [['Good', '#39B980'], ['Satisfactory', '#A3D65C'], ['Moderate', '#E9B44C'], ['Poor', '#EE8A3A'], ['Very Poor', '#E45D5D'], ['Severe', '#A8325E']];

export function LeftBar({ data, loading, error, onSelect, selectedId }: { data?: IndiaOverview; loading: boolean; error: string | null; onSelect: (id: string) => void; selectedId: string | null }) {
  if (loading) return <div className="p-5 grid gap-3" aria-busy="true" aria-label="Loading national summary">{[90, 140, 110].map((h) => <div key={h} className="india-skel" style={{ height: h }} />)}</div>;
  if (error || !data?.available || !data.national) return (
    <div className="p-5 text-[13px] leading-relaxed" role="alert"><div className="lbl text-[var(--in-crit)]">No live data</div>
      <p className="mt-2 text-[var(--in-muted)]">{error ?? data?.reason ?? 'The live data could not be loaded.'} Nothing is shown in its place: SYNERA does not substitute guessed readings.</p></div>);
  const n = data.national, total = n.cities_with_air_data || 1;
  return (
    <div className="p-5 grid gap-6">
      <section aria-labelledby="in-nat">
        <div className="flex items-baseline justify-between"><h2 id="in-nat" className="lbl m-0">National picture</h2><span className="num text-[10px] text-[var(--in-faint)]">{data.cities.length} cities</span></div>
        <div className="mt-3 flex items-end gap-3"><span className="display text-[34px] leading-none font-light">{fmt(n.median_aqi)}</span><span className="text-[12px] text-[var(--in-muted)] pb-1">median AQI across cities<br />(PM-based, modelled)</span></div>
        <div className="mt-3 flex h-2 overflow-hidden" role="img" aria-label={`Cities by air quality: ${AQI_ORDER.map(([k]) => `${n.aqi_categories[k] ?? 0} ${k}`).join(', ')}`}>
          {AQI_ORDER.map(([k, c]) => (n.aqi_categories[k] ? <div key={k} style={{ width: `${(n.aqi_categories[k] / total) * 100}%`, background: c }} title={`${k}: ${n.aqi_categories[k]}`} /> : null))}
        </div>
        <div className="mt-2 flex flex-wrap gap-x-3 gap-y-1">{AQI_ORDER.filter(([k]) => n.aqi_categories[k]).map(([k, c]) => <span key={k} className="text-[11px] text-[var(--in-muted)]"><i className="inline-block w-2 h-2 mr-1 align-middle" style={{ background: c }} />{k} <span className="num">{n.aqi_categories[k]}</span></span>)}</div>
      </section>

      <section aria-labelledby="in-alert">
        <h2 id="in-alert" className="lbl m-0">Critical alerts</h2>
        {n.alerts.length === 0
          ? <p className="mt-2 mb-0 text-[12.5px] leading-relaxed text-[var(--in-muted)]">No city currently meets an official alert threshold (AQI Very Poor or worse, IMD heat-wave criteria, or 64.5 mm of rain in a day).</p>
          : <ul className="mt-2 m-0 p-0 list-none grid gap-px">{n.alerts.map((a, i) => (
            <li key={`${a.id}${a.kind}${i}`}><button type="button" onClick={() => onSelect(a.id)} className="w-full text-left px-2 py-2 hover:bg-white/[0.04] flex gap-2 items-start">
              <i className="mt-1.5 w-2 h-2 shrink-0" style={{ background: URGENCY_STYLE[a.level].color }} />
              <span className="text-[12.5px] leading-snug"><b className="font-medium">{a.city}</b> <span className="text-[var(--in-faint)]">· {a.kind.toLowerCase()}</span><br /><span className="text-[var(--in-muted)]">{a.text}</span></span></button></li>))}</ul>}
      </section>

      <section aria-labelledby="in-hot">
        <h2 id="in-hot" className="lbl m-0">Air-quality hotspots</h2>
        <ol className="mt-2 m-0 p-0 list-none">{n.hotspots_air.map((h, i) => (
          <li key={h.id}><button type="button" onClick={() => onSelect(h.id)} aria-current={selectedId === h.id} className={`w-full flex items-center gap-3 px-2 py-2 text-left hover:bg-white/[0.04] ${selectedId === h.id ? 'bg-white/[0.06]' : ''}`}>
            <span className="num text-[10px] text-[var(--in-faint)] w-3">{i + 1}</span><span className="flex-1 text-[13px]">{h.name}</span>
            <span className="num text-[13px]" style={{ color: color('aqi', h.value) }}>{h.value.toFixed(0)}</span><span className="text-[10px] text-[var(--in-faint)] w-[68px] text-right truncate">{h.category}</span></button></li>))}</ol>
        <p className="mt-2 mb-0 text-[11px] leading-snug text-[var(--in-faint)]">Ranked from modelled PM2.5 and PM10. These are places to investigate, not confirmed monitor readings.</p>
      </section>

      <section aria-labelledby="in-src">
        <h2 id="in-src" className="lbl m-0">Data</h2>
        <ul className="mt-2 m-0 p-0 list-none grid gap-1.5 text-[11.5px] text-[var(--in-muted)]">{(data.sources ?? []).map((s) => (
          <li key={s.name} className="flex gap-2"><i className="mt-1.5 w-1.5 h-1.5 shrink-0 india-live-dot" style={{ background: s.status === 'live' || s.status === 'cached' ? '#39B980' : s.status === 'stale' ? '#E9B44C' : '#E45D5D' }} />
            <span>{s.name}<br /><span className="text-[var(--in-faint)]">{s.status}{s.fetched_at ? ` · ${new Date(s.fetched_at).toLocaleTimeString()}` : ''}</span></span></li>))}</ul>
      </section>
    </div>
  );
}
