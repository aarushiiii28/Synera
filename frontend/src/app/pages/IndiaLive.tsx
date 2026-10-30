import { useEffect, useMemo, useRef, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { api, ApiError } from '../../lib/api';
import { isStatic } from '../../lib/snapshot';
import { fmt, type CityMarker, type LayerDef } from '../../lib/india';
import { Logo } from '../../components/Logo';
import { IndiaMap } from '../../components/india/IndiaMap';
import { Legend } from '../../components/india/Legend';
import { LeftBar } from '../../components/india/LeftBar';
import { CityPanel } from '../../components/india/CityPanel';
import { Timeline } from '../../components/india/Timeline';
import '../../components/india/india.css';

const REFRESH_MS = 15 * 60 * 1000;
const errText = (e: unknown) => (e instanceof ApiError || e instanceof Error ? e.message : e ? String(e) : null);
const PLATFORM = [['/observatory', 'Observatory'], ['/scenario', 'Scenario Lab'], ['/live-stress-lab', 'Live Stress Lab'], ['/discovery', 'Discovery Lab'], ['/findings', 'Findings'], ['/trust', 'Trust Center'], ['/benchmark', 'Report Card'], ['/guide', 'How it works']];

function Search({ cities, onPick }: { cities: CityMarker[]; onPick: (id: string) => void }) {
  const [q, setQ] = useState(''), [open, setOpen] = useState(false), [i, setI] = useState(0);
  const hits = useMemo(() => { const s = q.trim().toLowerCase(); return s ? cities.filter((c) => c.name.toLowerCase().includes(s) || c.state.toLowerCase().includes(s)).slice(0, 8) : []; }, [q, cities]);
  const choose = (c: CityMarker) => { onPick(c.id); setQ(''); setOpen(false); };
  return (
    <div className="relative">
      <label className="sr-only" htmlFor="in-search">Search a city</label>
      <input id="in-search" role="combobox" aria-expanded={open && q.length > 0} aria-controls="in-hits" aria-autocomplete="list" value={q} placeholder="Search city or state"
        onChange={(e) => { setQ(e.target.value); setOpen(true); setI(0); }} onFocus={() => setOpen(true)} onBlur={() => setTimeout(() => setOpen(false), 120)}
        onKeyDown={(e) => { if (e.key === 'ArrowDown') { e.preventDefault(); setI((x) => Math.min(x + 1, hits.length - 1)); } else if (e.key === 'ArrowUp') { e.preventDefault(); setI((x) => Math.max(x - 1, 0)); } else if (e.key === 'Enter' && hits[i]) choose(hits[i]); else if (e.key === 'Escape') setOpen(false); }}
        className="w-36 sm:w-44 lg:w-60 bg-[var(--in-bg2)] border border-[var(--in-line2)] px-3 py-1.5 text-[13px] placeholder:text-[var(--in-faint)]" />
      {open && q.trim() && (
        <ul id="in-hits" role="listbox" className="absolute right-0 mt-1 w-72 z-40 m-0 p-0 list-none border border-[var(--in-line2)] bg-[#0B1014] shadow-2xl max-h-72 overflow-auto">
          {hits.length === 0 ? <li className="px-3 py-2 text-[12.5px] text-[var(--in-muted)]">No supported city matches "{q}". Cities are added in one line of the city list (see docs/INDIA_LIVE.md).</li> : hits.map((c, n) => (
            <li key={c.id} role="option" aria-selected={n === i} onMouseDown={() => choose(c)} onMouseEnter={() => setI(n)} className={`px-3 py-2 text-[13px] cursor-pointer flex justify-between ${n === i ? 'bg-white/[0.08]' : ''}`}><span>{c.name}</span><span className="text-[11px] text-[var(--in-faint)]">{c.state}</span></li>))}
        </ul>)}
    </div>
  );
}

const H = ({ children }: { children: React.ReactNode }) => <h3 className="lbl m-0 mt-5 mb-1.5">{children}</h3>;

function Method({ onClose }: { onClose: () => void }) {
  const btn = useRef<HTMLButtonElement>(null);
  useEffect(() => { btn.current?.focus(); const k = (e: KeyboardEvent) => e.key === 'Escape' && onClose(); window.addEventListener('keydown', k); return () => window.removeEventListener('keydown', k); }, [onClose]);
  return (
    <div className="fixed inset-0 z-50 bg-black/70 grid place-items-center p-4" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div role="dialog" aria-modal="true" aria-label="Methodology" className="max-w-2xl w-full max-h-[86vh] overflow-auto scroll bg-[var(--in-bg)] border border-[var(--in-line2)] p-6 text-[13.5px] leading-relaxed text-[var(--in-muted)]">
        <div className="flex items-start"><h2 className="display m-0 text-[22px] font-light text-[var(--in-text)] flex-1">Methodology</h2><button ref={btn} type="button" onClick={onClose} className="px-2 py-1 border border-[var(--in-line2)] text-[12px] text-[var(--in-text)]">Close</button></div>
        <H>What the numbers are</H>
        <p className="m-0">Every value carries a tag. <b className="text-[var(--in-text)]">Station</b> is a monitor reading (CPCB or OpenAQ, when a key is configured). <b className="text-[var(--in-text)]">Model</b> is a weather or air-quality model's estimate of the present from observations and satellites (Open-Meteo and CAMS): good for the big picture, but it can differ from the nearest monitor. <b className="text-[var(--in-text)]">Forecast</b> is a prediction. <b className="text-[var(--in-text)]">Derived</b> is computed by SYNERA from those with a published formula, such as the AQI.</p>
        <H>Official thresholds</H>
        <p className="m-0">Air quality uses India's National AQI (CPCB 2014 breakpoints, 24-hour averages). Without NO₂, SO₂, O₃, CO, NH₃ and lead the figure is PM-based, and says so. Heat uses IMD's heat-wave criteria and the NWS heat-index categories. Rain uses IMD's 24-hour categories; UV uses the WHO scale. Each recommendation names which one it rests on.</p>
        <H>The SYNERA engine on a live reading</H>
        <p className="m-0">Two parts of the existing engine take the city's conditions. (1) The <b className="text-[var(--in-text)]">scenario model</b>, learned from real US weekly deaths, weather and air pollution, is evaluated for the city's current week against the city's own seasonal normal. It is an average association learned in the US and transferred in standardised units: indicative and not validated for India. Its out-of-sample skill and how many of its interactions beat chance are shown with every answer. (2) <b className="text-[var(--in-text)]">Findings on real Indian grid data</b> (heat × humidity on electricity demand, replicated on later data) are evaluated at today's conditions for the 16 states in those panels.</p>
        <H>What this does not do</H>
        <p className="m-0">It does not infer cause, it does not predict any individual's health, and it gives no medical advice. It does not run flood-depth or fire-spread models. Colour between cities on the map is interpolated for readability and fades with distance from the nearest city; it is not a measurement. State boundaries come from an open dataset and should be replaced with the Survey of India's official outline before any formal use.</p>
        <H>Setup</H>
        <p className="m-0">The map needs the SYNERA API. Optional keys add station data (OPENAQ_API_KEY, DATA_GOV_IN_API_KEY) and satellite fires (FIRMS_MAP_KEY). See docs/INDIA_LIVE.md.</p>
      </div>
    </div>
  );
}

export default function IndiaLive() {
  const [params, setParams] = useSearchParams();
  const sel = params.get('city');
  const [focus, setFocus] = useState<string | null>(sel);
  const [layerId, setLayerId] = useState('aqi'), [dimLow, setDimLow] = useState(false), [method, setMethod] = useState(false);
  const ov = useQuery({ queryKey: ['india', 'overview'], queryFn: api.indiaOverview, staleTime: 5 * 60_000, refetchInterval: isStatic ? false : REFRESH_MS, retry: 1 });
  const city = useQuery({ queryKey: ['india', 'city', sel], queryFn: () => api.indiaCity(sel!), enabled: !!sel, staleTime: 10 * 60_000, refetchInterval: isStatic ? false : REFRESH_MS, retry: 1 });
  const data = ov.data;
  const layers: LayerDef[] = data?.layers ?? [];
  const layer = layers.find((l) => l.id === layerId) ?? layers[0];
  const pick = (id: string) => { setParams({ city: id }, { replace: false }); setFocus(id); };
  const stale = data?.sources?.some((s) => s.status === 'stale');
  const status = ov.isLoading ? { t: 'CONNECTING', c: '#84939C' } : isStatic ? { t: 'RECORDED SNAPSHOT', c: '#E9B44C' } : ov.error || (data && !data.available) ? { t: 'NO LIVE DATA', c: '#E45D5D' } : stale ? { t: 'STALE DATA', c: '#E9B44C' } : { t: 'LIVE', c: '#39B980' };
  const sync = data?.generated_at ? new Date(data.generated_at) : null;

  return (
    <div className="india min-h-screen lg:h-screen flex flex-col topo">
      <header className="shrink-0 h-[52px] border-b rule flex items-center gap-3 sm:gap-4 px-3 sm:px-4 lg:px-5">
        <Link to="/" className="flex items-center gap-2.5 shrink-0" aria-label="SYNERA India Live Intelligence, home"><Logo size={24} /><span className="hidden sm:inline display font-light text-[17px] tracking-[0.22em]">SYNERA</span></Link>
        <span className="hidden md:block lbl border-l rule pl-4">India live intelligence</span>
        <span className="flex-1" />
        <div className="hidden sm:flex items-center gap-2 num text-[10.5px]" role="status" aria-live="polite"><i className="w-2 h-2 india-live-dot" style={{ background: status.c }} /><span style={{ color: status.c }}>{status.t}</span>
          <span className="text-[var(--in-faint)] hidden lg:inline">{sync ? `synced ${sync.toLocaleTimeString()}` : ''}</span></div>
        <Search cities={data?.cities ?? []} onPick={pick} />
        <button type="button" onClick={() => setMethod(true)} className="text-[12.5px] text-[var(--in-muted)] hover:text-[var(--in-text)] whitespace-nowrap">Methodology</button>
        <details className="relative hidden md:block"><summary className="cursor-pointer text-[12.5px] text-[var(--in-muted)] hover:text-[var(--in-text)] list-none whitespace-nowrap">Platform ▾</summary>
          <ul className="absolute right-0 mt-2 w-48 z-40 m-0 p-1 list-none border border-[var(--in-line2)] bg-[#0B1014]">{PLATFORM.map(([to, l]) => <li key={to}><Link to={to} className="block px-3 py-1.5 text-[13px] text-[var(--in-muted)] hover:bg-white/[0.06] hover:text-[var(--in-text)]">{l}</Link></li>)}</ul></details>
      </header>

      <div className="flex-1 min-h-0 flex flex-col lg:grid lg:grid-cols-[288px_minmax(0,1fr)_424px] lg:grid-rows-[minmax(0,1fr)_236px]">
        <aside className="order-3 lg:order-none lg:row-span-2 border-t lg:border-t-0 lg:border-r rule overflow-y-auto scroll bg-[var(--in-bg)]/60" aria-label="National summary">
          <LeftBar data={data} loading={ov.isLoading} error={errText(ov.error)} onSelect={pick} selectedId={sel} />
        </aside>

        <main id="main" className="order-1 lg:order-none relative h-[64vh] min-h-[420px] lg:h-auto lg:min-h-0" aria-label="Map of India">
          {ov.isLoading && <div className="absolute inset-0 grid place-items-center"><div className="text-center"><div className="india-skel w-48 h-2 mx-auto" /><div className="lbl mt-3">Fetching live readings for 52 cities…</div></div></div>}
          {!ov.isLoading && (ov.error || (data && !data.available)) && <div className="absolute inset-0 grid place-items-center px-8 text-center" role="alert"><div className="max-w-md"><div className="lbl text-[var(--in-crit)]">The map has no live data</div>
            <p className="text-[13.5px] leading-relaxed text-[var(--in-muted)]">{errText(ov.error) ?? data?.reason} No readings are drawn rather than invented ones.</p><button type="button" onClick={() => ov.refetch()} className="px-3 py-1.5 text-[12.5px] border border-[var(--in-line2)] hover:bg-white/[0.06]">Try again</button></div></div>}
          {data?.available && layer && <>
            <IndiaMap cities={data.cities} layer={layer} selectedId={sel} focusId={focus} dimLow={dimLow} onSelect={pick} />
            <div className="absolute left-3 top-3 flex flex-wrap gap-1 max-w-[calc(100%-70px)]" role="group" aria-label="Map layer">
              {layers.map((l) => <button key={l.id} type="button" aria-pressed={l.id === layer.id} onClick={() => setLayerId(l.id)} className={`px-2.5 py-1 text-[11px] tracking-[0.08em] uppercase border backdrop-blur ${l.id === layer.id ? 'border-[var(--in-accent)] bg-[var(--in-accent)]/20 text-[var(--in-text)]' : 'border-[var(--in-line2)] bg-[#0B1014]/80 text-[var(--in-muted)] hover:text-[var(--in-text)]'}`}>{l.label}</button>)}
              <label className="flex items-center gap-1.5 px-2.5 py-1 text-[11px] border border-[var(--in-line2)] bg-[#0B1014]/80 text-[var(--in-muted)] cursor-pointer"><input type="checkbox" checked={dimLow} onChange={(e) => setDimLow(e.target.checked)} />At-risk only</label>
            </div>
            <div className="absolute left-3 bottom-3"><Legend layer={layer} /></div>
            <div className="absolute right-3 bottom-3 hidden md:block num text-[10px] text-[var(--in-faint)] text-right">{data.cities.filter((c) => c.aqi !== null).length} cities with data · {fmt(data.national?.median_aqi)} median AQI</div>
          </>}
        </main>

        <aside className="order-2 lg:order-none lg:row-span-2 border-t lg:border-t-0 lg:border-l rule bg-[var(--in-bg)]/80 min-h-[300px] lg:min-h-0 lg:overflow-hidden" aria-label="City intelligence">
          <CityPanel key={sel ?? 'none'} id={sel} data={city.data} loading={city.isLoading} error={errText(city.error)} onRetry={() => city.refetch()} onPick={pick} />
        </aside>

        <div className="order-4 lg:order-none border-t rule bg-[var(--in-bg)]/70 min-h-[230px] lg:min-h-0"><Timeline data={sel ? city.data : undefined} loading={!!sel && city.isLoading} /></div>
      </div>
      {method && <Method onClose={() => setMethod(false)} />}
    </div>
  );
}
