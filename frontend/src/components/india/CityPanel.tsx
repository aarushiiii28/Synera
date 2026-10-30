import { useState } from 'react';
import { color, compass, fmt, KIND_LABEL, URGENCY_STYLE, WINDOW_LABEL, type Explain, type IndiaCity, type Kind, type Metric, type Recommendation } from '../../lib/india';

const TABS = ['Actions', 'Conditions', 'Evidence', 'Sources'] as const;
type Tab = (typeof TABS)[number];
const kindTag = (k: Kind) => ({ OBSERVATION: 'STATION', MODEL_ANALYSIS: 'MODEL', FORECAST: 'FORECAST', DERIVED: 'DERIVED' } as Record<string, string>)[k] ?? k;
const tierColor = (t: string | null) => (t === 'SEVERE' ? '#E45D5D' : t === 'HIGH' ? '#EE8A3A' : t === 'MODERATE' ? '#E9B44C' : t === 'LOW' ? '#39B980' : '#84939C');
const NAMES: Record<string, string> = { heat_index: 'Heat', pm25: 'PM2.5', pm10: 'PM10', rh: 'Humidity', o3: 'Ozone', no2: 'NO₂', wind: 'Wind', precip: 'Rain', uv: 'UV', drought_index: 'Drought' };

function Chip({ children, c, title }: { children: React.ReactNode; c?: string; title?: string }) {
  return <span title={title} className="num text-[9.5px] tracking-[0.1em] uppercase px-1.5 py-0.5 border whitespace-nowrap" style={{ color: c ?? 'var(--in-muted)', borderColor: c ? `${c}88` : 'var(--in-line2)' }}>{children}</span>;
}

function RecCard({ r }: { r: Recommendation }) {
  const u = URGENCY_STYLE[r.urgency], cc = r.confidence.level === 'HIGH' ? '#39B980' : r.confidence.level === 'MEDIUM' ? '#E9B44C' : '#84939C';
  return (
    <article className="india-rise border border-[var(--in-line)] bg-[var(--in-bg2)]" style={{ borderLeft: `3px solid ${u.color}` }} aria-label={`Recommendation ${r.rank}: ${u.label}`}>
      <div className="px-4 pt-3 flex flex-wrap items-center gap-2">
        <span className="num text-[11px] text-[var(--in-faint)]">{String(r.rank).padStart(2, '0')}</span>
        <Chip c={u.color}>{u.label}</Chip><Chip>{WINDOW_LABEL[r.window]}</Chip>
        <span className="flex-1" />
        <Chip c={r.basis === 'ENGINE' ? '#63B3ED' : undefined} title={r.basis === 'ENGINE' ? 'Rests on the SYNERA engine output' : 'Rests on an official threshold (CPCB, IMD, WHO, NWS)'}>{r.basis === 'ENGINE' ? 'SYNERA engine' : 'Official threshold'}</Chip>
      </div>
      <div className="px-4 pt-2 pb-3 grid gap-2.5">
        <div><div className="lbl">Action</div><p className="m-0 text-[14px] leading-snug font-medium">{r.action}</p></div>
        <div><div className="lbl">Reason</div><p className="m-0 text-[12.5px] leading-relaxed text-[var(--in-muted)]">{r.what_is_happening} {r.why}</p></div>
        <div className="flex flex-wrap gap-x-5 gap-y-2 items-start">
          <div className="min-w-0"><div className="lbl">Affected</div><div className="mt-1 flex flex-wrap gap-1">{r.who.map((w) => <span key={w} className="text-[11px] px-1.5 py-0.5 bg-white/[0.06]">{w}</span>)}</div></div>
          <div><div className="lbl">Confidence</div><div className="mt-1 text-[12px]"><b style={{ color: cc }}>{r.confidence.level}</b> <span className="num text-[var(--in-faint)]">{r.confidence.score.toFixed(2)}</span></div></div>
        </div>
        <p className="m-0 text-[11px] leading-snug text-[var(--in-faint)]">Confidence reflects data completeness and provenance, not a probability: {r.confidence.why}.</p>
        <details><summary className="cursor-pointer text-[12px] text-[var(--in-accent)]">Supporting data and thresholds</summary>
          <table className="mt-2 w-full text-[11.5px] border-collapse"><tbody>{r.evidence.map((e) => (
            <tr key={e.label} className="border-t rule align-top"><td className="py-1.5 pr-2 text-[var(--in-muted)]">{e.label}</td><td className="py-1.5 pr-2 num whitespace-nowrap">{e.value ?? '—'}</td><td className="py-1.5 pr-2 text-[var(--in-faint)]">{e.threshold ?? ''}</td><td className="py-1.5 text-[var(--in-faint)]">{e.source}</td></tr>))}</tbody></table></details>
      </div>
    </article>
  );
}

function Tile({ label, m, d = 0, suffix, extra, tone }: { label: string; m?: Metric; d?: number; suffix?: string; extra?: string; tone?: string }) {
  const v = m?.value ?? null;
  return (
    <div className="border border-[var(--in-line)] bg-[var(--in-bg2)] px-3 py-2.5" title={v === null ? 'Not available from the providers right now' : `${KIND_LABEL[m!.kind]} · ${m!.source}`}>
      <div className="flex items-baseline justify-between"><span className="lbl">{label}</span>{m && v !== null && <span className="num text-[8.5px] tracking-[0.1em] text-[var(--in-faint)]">{kindTag(m.kind)}</span>}</div>
      <div className="mt-1 flex items-baseline gap-1"><span className="num text-[21px] leading-none" style={{ color: tone }}>{fmt(v, d)}</span><span className="text-[11px] text-[var(--in-muted)]">{v === null ? 'n/a' : (suffix ?? m?.unit)}</span></div>
      {extra && <div className="mt-1 text-[11px] text-[var(--in-faint)]">{extra}</div>}
    </div>
  );
}

function Conditions({ c }: { c: IndiaCity }) {
  const m = c.metrics!, d = c.derived!;
  const today = c.daily?.find((x) => x.is_today);
  return (
    <div className="grid gap-3">
      <div className="border border-[var(--in-line)] bg-[var(--in-bg2)] px-4 py-3 flex items-center gap-4">
        <div className="num text-[44px] leading-none font-light" style={{ color: color('aqi', d.aqi.index) }}>{fmt(d.aqi.index)}</div>
        <div className="min-w-0"><div className="lbl">India AQI (PM-based)</div><div className="text-[15px]">{d.aqi.category ?? 'Not available'}</div>
          <div className="text-[11px] leading-snug text-[var(--in-faint)]">{d.aqi.index === null ? 'PM2.5 and PM10 are both missing.' : `driven by ${d.aqi.driver === 'pm25' ? 'PM2.5' : 'PM10'} · ${d.aqi.basis}`}</div></div>
      </div>
      <div className="grid grid-cols-2 gap-2">
        <Tile label="PM2.5" m={m.pm25} d={0} extra={d.aqi.pm25_24h !== null ? `24 h mean ${d.aqi.pm25_24h.toFixed(0)}` : undefined} />
        <Tile label="PM10" m={m.pm10} d={0} extra={d.aqi.pm10_24h !== null ? `24 h mean ${d.aqi.pm10_24h.toFixed(0)}` : undefined} />
        {m.pm25_station && <Tile label="PM2.5 station" m={m.pm25_station} d={0} />}
        <Tile label="Temperature" m={m.temperature_c} d={1} extra={today ? `today ${fmt(today.tmin_c)}–${fmt(today.tmax_c)} °C` : undefined} />
        <Tile label="Heat stress today" m={{ value: d.heat_stress_c, unit: '°C', label: '', kind: 'DERIVED', source: 'NWS heat index / peak apparent temperature', time: null }} d={0} extra={d.heat_index?.category} tone={d.heat_index && d.heat_index.level >= 2 ? '#EE8A3A' : undefined} />
        <Tile label="Humidity" m={m.humidity_pct} />
        <Tile label="Wind" m={m.wind_kmh} d={0} extra={m.wind_dir_deg?.value != null ? `from ${compass(m.wind_dir_deg.value)}${m.gust_kmh?.value != null ? ` · gusts ${m.gust_kmh.value.toFixed(0)}` : ''}` : undefined} />
        <Tile label="Rain, 24 h" m={{ value: d.rain_24h_mm, unit: 'mm', label: '', kind: 'MODEL_ANALYSIS', source: 'Open-Meteo hourly precipitation', time: null }} d={1} extra={d.rain?.category} />
        <Tile label="Pressure" m={m.pressure_hpa} />
        <Tile label="UV index today" m={{ value: d.uv_max, unit: '', label: '', kind: 'FORECAST', source: 'Open-Meteo daily maximum', time: null }} d={1} extra={d.uv?.category} />
        <Tile label="NO₂" m={m.no2} /><Tile label="Ozone" m={m.o3} />
      </div>
      {d.aqi.note && <p className="m-0 text-[11.5px] leading-snug text-[var(--in-faint)]">{d.aqi.note}</p>}
      {c.fires && <div className="border border-[var(--in-line)] px-3 py-2 text-[12px] text-[var(--in-muted)]"><span className="lbl">Satellite fire detections</span><br />{c.fires.count} in the last {c.fires.days} days within about {c.fires.box_deg.toFixed(1)}° ({c.fires.high_confidence} high confidence){c.fires.latest ? `, latest ${c.fires.latest}` : ''}. Detections are heat signatures seen from orbit, not confirmed fires.</div>}
      {c.quality && c.quality.issues.length > 0 && <ul className="m-0 pl-4 text-[11.5px] text-[var(--in-warn)]">{c.quality.issues.map((i) => <li key={i}>{i}</li>)}</ul>}
    </div>
  );
}

function Bar({ v, max, c }: { v: number; max: number; c: string }) {
  return <div className="h-1.5 bg-white/[0.07] w-full"><div className="h-full" style={{ width: `${(v / max) * 100}%`, background: c }} /></div>;
}

function Evidence({ e, c }: { e: Explain; c: IndiaCity }) {
  const sc = c.engine!.scenario, sm = e.engine.scenario_model;
  return (
    <div className="grid gap-5 text-[12.5px] leading-relaxed">
      <section><h3 className="lbl m-0 mb-2">What drove the assessment</h3>
        {e.drivers.length === 0 ? <p className="m-0 text-[var(--in-muted)]">No driver could be computed because the inputs are missing.</p> :
          <ul className="m-0 p-0 list-none grid gap-2.5">{e.drivers.map((d) => <li key={d.parameter}><div className="flex justify-between gap-3"><span>{d.parameter}: <span className="text-[var(--in-muted)]">{d.value}</span></span><span className="num text-[var(--in-faint)]">{d.level}/{d.max}</span></div>
            <Bar v={d.level} max={d.max} c={tierColor(d.level / d.max < 0.25 ? 'LOW' : d.level / d.max < 0.5 ? 'MODERATE' : d.level / d.max < 0.75 ? 'HIGH' : 'SEVERE')} /><div className="text-[10.5px] text-[var(--in-faint)] mt-0.5">{d.basis}</div></li>)}</ul>}
        <p className="m-0 mt-2 text-[11.5px] text-[var(--in-faint)]">Composite risk is the worst single hazard on a common scale, so it is never hidden by an average. Here: <b style={{ color: tierColor(e.composite.tier) }}>{e.composite.tier ?? 'n/a'}</b>{e.composite.driver ? `, driven by ${e.composite.driver}` : ''}.</p></section>

      <section><h3 className="lbl m-0 mb-2">Interactions the engine looked for</h3>
        {e.conditions.length === 0 ? <p className="m-0 text-[var(--in-muted)]">None of the combinations SYNERA watches (heat with PM2.5, humidity with poor air, low wind with poor air, heat with low wind) is present now.</p> :
          <ul className="m-0 p-0 list-none grid gap-2">{e.conditions.map((x) => <li key={x.condition} className="border-l-2 pl-3" style={{ borderColor: x.engine_term?.supported ? '#39B980' : 'var(--in-line2)' }}><b className="font-medium capitalize">{x.condition}</b><br /><span className="text-[var(--in-muted)]">{x.verdict}</span>
            {x.engine_term && <div className="num text-[11px] text-[var(--in-faint)]">learned term {x.engine_term.label}: {x.engine_term.contribution_pct >= 0 ? '+' : ''}{x.engine_term.contribution_pct.toFixed(3)}% (90% range {x.engine_term.lo_pct.toFixed(3)} to {x.engine_term.hi_pct.toFixed(3)})</div>}</li>)}</ul>}
        <p className="m-0 mt-2 text-[11.5px] text-[var(--in-faint)]">These are associations in data, never proof of cause.</p></section>

      <section><h3 className="lbl m-0 mb-2">SYNERA scenario model on this city</h3>
        {!sm.available ? <p className="m-0 text-[var(--in-muted)]">Not run: {sm.reason}.</p> : <>
          <p className="m-0">This week's conditions, set against {c.city.name}'s own normal, are associated with <b className="num">{sc.effect_pct! >= 0 ? '+' : ''}{sc.effect_pct!.toFixed(2)}%</b> weekly deaths versus a typical week (90% range {sc.lo_pct!.toFixed(2)} to {sc.hi_pct!.toFixed(2)}), as learned from 46 US states, 2014 to 2019.</p>
          <ul className="m-0 mt-2 p-0 list-none grid gap-1.5">{Object.entries(sm.decomposition!).filter(([, v]) => Math.abs(v) > 0.0005).sort((a, b) => Math.abs(b[1]) - Math.abs(a[1])).slice(0, 6).map(([k, v]) => (
            <li key={k} className="flex items-center gap-2"><span className="w-20 text-[var(--in-muted)]">{NAMES[k] ?? k}</span><div className="flex-1"><Bar v={Math.abs(v)} max={Math.max(...Object.values(sm.decomposition!).map(Math.abs))} c={v >= 0 ? '#E45D5D' : '#63B3ED'} /></div><span className="num w-16 text-right text-[11.5px]">{v >= 0 ? '+' : ''}{v.toFixed(3)}%</span></li>))}</ul>
          <p className="m-0 mt-2 text-[11.5px] text-[var(--in-faint)]">{sm.method}</p>
          <div className="mt-3 border border-[var(--in-warn)]/50 px-3 py-2 text-[12px] text-[var(--in-muted)]"><b className="text-[var(--in-warn)]">How much to trust it.</b> {sm.plain} It was learned in the US and is applied here in standardised units, so treat it as indicative, not validated for India, and never as a statement about any person.</div>
          {sc.left_at_normal && <p className="m-0 mt-2 text-[11px] text-[var(--in-faint)]">Inputs left at normal: {Object.entries(sc.left_at_normal).map(([k, v]) => `${NAMES[k] ?? k} (${v})`).join('; ')}.</p>}</>}</section>

      <section><h3 className="lbl m-0 mb-2">SYNERA findings on real Indian data</h3>
        {!e.engine.grid_findings.available ? <p className="m-0 text-[var(--in-muted)]">{e.engine.grid_findings.reason}.</p> : e.engine.grid_findings.results!.map((g) => (
          <div key={g.finding_id} className="border-l-2 pl-3 mb-2" style={{ borderColor: g.status === 'VERIFIED' ? '#39B980' : '#63B3ED' }}>
            <b className="font-medium">Heat × humidity on {g.state}'s electricity demand</b> <Chip c={g.status === 'VERIFIED' ? '#39B980' : '#63B3ED'}>{g.status}</Chip><br />
            <span className="text-[var(--in-muted)]">Today's heat and humidity sit at the <b className="num">{g.state_percentile !== null ? `${Math.round(g.state_percentile * 100)}th` : 'n/a'}</b> percentile of {g.state}'s history of this interaction effect. The learned interaction changes demand by about <b className="num">{g.uplift_pp !== null ? `${g.uplift_pp >= 0 ? '+' : ''}${g.uplift_pp.toFixed(2)}` : 'n/a'}</b> percentage points compared with adding the two separate effects.</span>
            <div className="num text-[11px] text-[var(--in-faint)]">finding {g.finding_id} · {g.dataset_id} · {g.replication.replaceAll('_', ' ').toLowerCase()}</div></div>))}
        <p className="m-0 text-[11.5px] text-[var(--in-faint)]">Grid stress is about the power system, not health. Evidence level and replication are shown on the Findings page.</p></section>

      <section><h3 className="lbl m-0 mb-2">Where each recommendation comes from</h3>
        <p className="m-0 text-[var(--in-muted)]"><b className="num">{e.basis_count.THRESHOLD}</b> rest on official thresholds (CPCB, IMD, WHO, NWS); <b className="num">{e.basis_count.ENGINE}</b> rest on the SYNERA engine.</p>
        <ul className="m-0 mt-2 pl-4 text-[11.5px] text-[var(--in-faint)]">{e.not_done.map((n) => <li key={n}>{n}</li>)}</ul></section>
    </div>
  );
}

function Sources({ c }: { c: IndiaCity }) {
  return (
    <div className="grid gap-2">
      {c.sources!.map((s) => (
        <div key={s.name} className="border border-[var(--in-line)] bg-[var(--in-bg2)] px-3 py-2.5">
          <div className="flex items-baseline justify-between gap-2"><b className="text-[13px] font-medium">{s.name}</b>
            <span className="num text-[10px]" style={{ color: s.status === 'live' || s.status === 'cached' ? '#39B980' : s.status === 'stale' ? '#E9B44C' : s.status === 'NOT_CONFIGURED' || s.status === 'USED_AS_THRESHOLDS' ? '#84939C' : '#E45D5D' }}>{s.status}</span></div>
          <div className="text-[11.5px] text-[var(--in-muted)]">{s.role} · {KIND_LABEL[s.kind.split(' and ')[0].replace(' ', '_')] ?? s.kind}</div>
          {s.fetched_at && <div className="num text-[10.5px] text-[var(--in-faint)]">fetched {new Date(s.fetched_at).toLocaleString()}</div>}
          {s.note && <div className="text-[11px] text-[var(--in-faint)] mt-0.5">{s.note}</div>}
          {s.docs && <a className="text-[11px] text-[var(--in-accent)]" href={s.docs} target="_blank" rel="noreferrer">documentation</a>}
        </div>))}
      <p className="m-0 text-[11px] leading-snug text-[var(--in-faint)]">Station feeds (CPCB, OpenAQ) and satellite fires (NASA FIRMS) need free keys; see docs/INDIA_LIVE.md. Without them SYNERA says so here rather than filling the gap.</p>
    </div>
  );
}

export function CityPanel({ id, data, loading, error, onRetry, onPick }: { id: string | null; data?: IndiaCity; loading: boolean; error: string | null; onRetry: () => void; onPick: (id: string) => void }) {
  const [tab, setTab] = useState<Tab>('Actions');
  const [all, setAll] = useState(false);
  if (!id) return (
    <div className="p-6 grid gap-4 content-start">
      <div className="lbl">City intelligence</div>
      <h2 className="display m-0 text-[22px] font-light leading-tight">Select a city on the map</h2>
      <p className="m-0 text-[13.5px] leading-relaxed text-[var(--in-muted)]">SYNERA fetches that city's live readings, checks them, runs them through the engine and tells you what to do now, with the evidence for each action.</p>
      <div className="flex flex-wrap gap-2">{[['amritsar', 'Amritsar'], ['delhi', 'Delhi'], ['mumbai', 'Mumbai'], ['bengaluru', 'Bengaluru'], ['kolkata', 'Kolkata']].map(([k, n]) => <button key={k} type="button" onClick={() => onPick(k)} className="px-3 py-1.5 text-[12.5px] border border-[var(--in-line2)] hover:bg-white/[0.06]">{n}</button>)}</div>
    </div>);
  if (loading) return <div className="p-6 grid gap-3" aria-busy="true" aria-label="Loading city intelligence"><div className="lbl">Fetching live readings and running the engine…</div>{[60, 120, 160, 160].map((h, i) => <div key={i} className="india-skel" style={{ height: h }} />)}</div>;
  if (error || !data) return <div className="p-6" role="alert"><div className="lbl text-[var(--in-crit)]">Could not load</div><p className="text-[13px] text-[var(--in-muted)]">{error ?? 'No response.'}</p><button type="button" onClick={onRetry} className="px-3 py-1.5 text-[12.5px] border border-[var(--in-line2)] hover:bg-white/[0.06]">Try again</button></div>;
  if (!data.available) return <div className="p-6" role="alert"><div className="lbl text-[var(--in-warn)]">Unavailable</div><h2 className="display text-[20px] font-light m-0 mt-1">{data.city.name}</h2><p className="text-[13px] leading-relaxed text-[var(--in-muted)]">{data.reason}</p><button type="button" onClick={onRetry} className="px-3 py-1.5 text-[12.5px] border border-[var(--in-line2)] hover:bg-white/[0.06]">Try again</button></div>;
  const d = data.derived!, recs = data.recommendations!, shown = all ? recs : recs.slice(0, 4);
  const comp = d.composite;
  return (
    <div className="flex flex-col min-h-0 h-full">
      <header className="px-5 pt-4 pb-3 border-b rule">
        <div className="flex items-start gap-3"><div className="min-w-0 flex-1"><div className="lbl">{data.city.state}</div><h2 className="display m-0 text-[26px] leading-tight font-light">{data.city.name}</h2>
          <div className="num text-[10.5px] text-[var(--in-faint)]">model time {data.as_of?.replace('T', ' ')} IST</div></div>
          <div className="text-right"><div className="lbl">Risk</div><div className="num text-[15px]" style={{ color: tierColor(comp.tier) }}>{comp.tier ?? 'n/a'}</div><div className="text-[10.5px] text-[var(--in-faint)]">{comp.driver ? `driver: ${comp.driver}` : ''}</div></div></div>
        {data.quality && data.quality.missing.length > 0 && <p className="m-0 mt-2 text-[11.5px] text-[var(--in-warn)]">Missing right now: {data.quality.missing.join(', ')}. Recommendations that need them are marked lower confidence or left out.</p>}
        <div role="tablist" aria-label="City intelligence sections" className="mt-3 flex gap-1">{TABS.map((t) => <button key={t} role="tab" type="button" aria-selected={tab === t} onClick={() => setTab(t)} className={`px-3 py-1.5 text-[12px] border ${tab === t ? 'border-[var(--in-accent)] text-[var(--in-text)] bg-[var(--in-accent)]/10' : 'border-transparent text-[var(--in-muted)] hover:text-[var(--in-text)]'}`}>{t}</button>)}</div>
      </header>
      <div className="flex-1 min-h-0 overflow-y-auto scroll px-5 py-4" role="tabpanel">
        {tab === 'Actions' && (
          <div className="grid gap-3">
            <div><h3 className="display m-0 text-[17px] font-normal">What should we do now?</h3><p className="m-0 mt-1 text-[12px] leading-snug text-[var(--in-faint)]">Ranked by urgency, then how soon. Advisories for public health and operations, not medical advice.</p></div>
            {shown.map((r) => <RecCard key={r.id} r={r} />)}
            {recs.length > 4 && <button type="button" onClick={() => setAll(!all)} className="text-[12.5px] text-[var(--in-accent)] text-left">{all ? 'Show fewer' : `Show ${recs.length - 4} more`}</button>}
          </div>)}
        {tab === 'Conditions' && <Conditions c={data} />}
        {tab === 'Evidence' && <Evidence e={data.explain!} c={data} />}
        {tab === 'Sources' && <Sources c={data} />}
      </div>
    </div>
  );
}
