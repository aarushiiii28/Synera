import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { geoMercator, geoPath, select, zoom, zoomIdentity, type ZoomBehavior, type GeoPermissibleObjects } from 'd3';
import { color, colorRGB, compass, fmt, idw, LAYER_FMT, LAYER_VALUE, type CityMarker, type LayerDef, type LayerId } from '../../lib/india';

interface Props {
  cities: CityMarker[]; layer: LayerDef; selectedId: string | null; focusId: string | null; dimLow: boolean; onSelect: (id: string) => void;
}
type Geo = { type: 'FeatureCollection'; features: { type: 'Feature'; properties: { name: string }; geometry: GeoPermissibleObjects }[] };
interface Tf { k: number; x: number; y: number }

const MAJOR = new Set(['delhi', 'mumbai', 'kolkata', 'chennai', 'bengaluru', 'hyderabad', 'amritsar', 'ahmedabad', 'jaipur', 'lucknow', 'guwahati', 'srinagar', 'patna', 'kochi']);
let geoPromise: Promise<Geo> | null = null;
const loadGeo = () => (geoPromise ??= fetch(`${import.meta.env.BASE_URL}data/india_states.geojson`).then((r) => { if (!r.ok) throw new Error('boundary file missing'); return r.json() as Promise<Geo>; }).catch((e) => { geoPromise = null; throw e; }));

function useSize(ref: React.RefObject<HTMLElement | null>) {
  const [s, set] = useState({ w: 0, h: 0 });
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const ro = new ResizeObserver(([e]) => set({ w: Math.round(e.contentRect.width), h: Math.round(e.contentRect.height) }));
    ro.observe(el);
    return () => ro.disconnect();
  }, [ref]);
  return s;
}

export function IndiaMap({ cities, layer, selectedId, focusId, dimLow, onSelect }: Props) {
  const wrap = useRef<HTMLDivElement>(null), canvas = useRef<HTMLCanvasElement>(null), svg = useRef<SVGSVGElement>(null);
  const zb = useRef<ZoomBehavior<SVGSVGElement, unknown> | null>(null);
  const { w, h } = useSize(wrap);
  const [geo, setGeo] = useState<Geo | null>(null), [geoErr, setGeoErr] = useState(false);
  const [tf, setTf] = useState<Tf>({ k: 1, x: 0, y: 0 });
  const [hover, setHover] = useState<{ c: CityMarker; x: number; y: number } | null>(null);
  const L = layer.id as LayerId;

  useEffect(() => { loadGeo().then(setGeo).catch(() => setGeoErr(true)); }, []);
  const projection = useMemo(() => (geo && w > 0 && h > 0 ? geoMercator().fitExtent([[18, 18], [w - 18, h - 18]], geo as unknown as GeoPermissibleObjects) : null), [geo, w, h]);
  const path = useMemo(() => (projection ? geoPath(projection) : null), [projection]);

  // zoom and pan
  useEffect(() => {
    if (!svg.current || w === 0) return;
    const z = zoom<SVGSVGElement, unknown>().scaleExtent([1, 9]).translateExtent([[-w * 0.15, -h * 0.15], [w * 1.15, h * 1.15]]).on('zoom', (e) => setTf({ k: e.transform.k, x: e.transform.x, y: e.transform.y }));
    zb.current = z;
    select(svg.current).call(z).on('dblclick.zoom', null);
  }, [w, h]);
  const pts = useMemo(() => cities.map((c) => ({ c, v: LAYER_VALUE[L](c) })).filter((p): p is { c: CityMarker; v: number } => p.v !== null), [cities, L]);

  // heat field: inverse-distance weighted between city points, faded with distance from the nearest city, clipped to India
  useEffect(() => {
    const cv = canvas.current;
    if (!cv || !projection || !geo || w === 0) return;
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    cv.width = w * dpr; cv.height = h * dpr;
    const ctx = cv.getContext('2d');
    if (!ctx) return;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, w, h);
    ctx.save();
    ctx.translate(tf.x, tf.y); ctx.scale(tf.k, tf.k);
    ctx.beginPath();
    geoPath(projection, ctx)(geo as unknown as GeoPermissibleObjects);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);          // the clip stays where it was drawn; the field below is drawn in screen pixels
    ctx.clip();
    const lp = pts.map((p) => ({ lon: p.c.lon, lat: p.c.lat, v: p.v }));
    if (lp.length) {
      // the field is computed on a coarse grid of screen pixels and scaled up smoothly
      const STEP = 5, cw = Math.ceil(w / STEP), ch = Math.ceil(h / STEP);
      const small = document.createElement('canvas');
      small.width = cw; small.height = ch;
      const sctx = small.getContext('2d');
      if (sctx) {
        const img = sctx.createImageData(cw, ch);
        for (let j = 0; j < ch; j++) {
          for (let i = 0; i < cw; i++) {
            const ll = projection.invert?.([((i + 0.5) * STEP - tf.x) / tf.k, ((j + 0.5) * STEP - tf.y) / tf.k]);
            const r = ll ? idw(ll[0], ll[1], lp) : null;
            if (!r) continue;
            const fade = r.nearestKm < 130 ? 1 : Math.max(0.2, 1 - (r.nearestKm - 130) / 420);
            const [R, G, B] = colorRGB(L, r.v), o = (j * cw + i) * 4;
            img.data[o] = R; img.data[o + 1] = G; img.data[o + 2] = B; img.data[o + 3] = Math.round(190 * fade);
          }
        }
        sctx.putImageData(img, 0, 0);
        ctx.imageSmoothingEnabled = true; ctx.imageSmoothingQuality = 'high';
        ctx.drawImage(small, 0, 0, cw * STEP, ch * STEP);
      }
    }
    ctx.restore();
  }, [projection, geo, pts, L, tf, w, h]);

  // labels never overlap: the selected city and the major ones win, the rest appear as space allows when zoomed in
  const labels = useMemo(() => {
    if (!projection) return new Set<string>();
    const order = [...cities].sort((a, b) => Number(b.id === selectedId) - Number(a.id === selectedId) || Number(MAJOR.has(b.id)) - Number(MAJOR.has(a.id)));
    const placed: [number, number, number, number][] = [], out = new Set<string>();
    for (const c of order) {
      const p = projection([c.lon, c.lat]);
      if (!p) continue;
      if (c.id !== selectedId && !MAJOR.has(c.id) && tf.k < 2.2) continue;
      const sx = p[0] * tf.k + tf.x + 9, sy = p[1] * tf.k + tf.y, bw = c.name.length * 6.4 + 4;
      const box: [number, number, number, number] = [sx, sy - 8, sx + bw, sy + 8];
      if (placed.some((q) => box[0] < q[2] && box[2] > q[0] && box[1] < q[3] && box[3] > q[1])) continue;
      placed.push(box); out.add(c.id);
    }
    return out;
  }, [cities, projection, tf, selectedId]);

  // fly to a city when it is chosen from the search or a list
  useEffect(() => {
    if (!focusId || !projection || !svg.current || !zb.current) return;
    const c = cities.find((x) => x.id === focusId);
    const p = c && projection([c.lon, c.lat]);
    if (!p) return;
    const k = 3.4;
    select(svg.current).transition().duration(750).call(zb.current.transform, zoomIdentity.translate(w / 2 - k * p[0], h / 2 - k * p[1] - 20).scale(k));
  }, [focusId, projection, cities, w, h]);

  const zoomBy = useCallback((f: number) => { if (svg.current && zb.current) select(svg.current).transition().duration(260).call(zb.current.scaleBy, f); }, []);
  const reset = useCallback(() => { if (svg.current && zb.current) select(svg.current).transition().duration(500).call(zb.current.transform, zoomIdentity); }, []);
  const place = (c: CityMarker) => projection?.([c.lon, c.lat]) ?? null;

  return (
    <div ref={wrap} className="relative w-full h-full overflow-hidden select-none" style={{ touchAction: 'none' }}>
      <canvas ref={canvas} className="absolute inset-0" style={{ width: w, height: h }} aria-hidden />
      {geoErr && <div role="alert" className="absolute inset-0 grid place-items-center text-center px-6 text-[13px] text-muted">The India boundary file could not be loaded, so the map cannot be drawn. Readings are still available in the city list.</div>}
      <svg ref={svg} width={w} height={h} className="absolute inset-0 cursor-grab active:cursor-grabbing" role="group" aria-label="Map of India with city markers">
        <g transform={`translate(${tf.x},${tf.y}) scale(${tf.k})`}>
          {path && geo?.features.map((f) => (
            <path key={f.properties.name} d={path(f.geometry) ?? ''} fill="rgba(237,242,244,0.02)" stroke="rgba(237,242,244,0.5)" strokeWidth={0.8} vectorEffect="non-scaling-stroke" strokeLinejoin="round">
              <title>{f.properties.name}</title>
            </path>))}
          {cities.map((c) => {
            const p = place(c);
            if (!p) return null;
            const v = LAYER_VALUE[L](c), sel = c.id === selectedId, alarm = c.risk_tier === 'HIGH' || c.risk_tier === 'SEVERE';
            const dim = dimLow && (c.risk_tier === 'LOW' || c.risk_tier === null) && !sel;
            const r = (sel ? 7 : 5) / Math.sqrt(tf.k);
            return (
              <g key={c.id} transform={`translate(${p[0]},${p[1]})`} opacity={dim ? 0.28 : 1} role="button" tabIndex={0} aria-label={`${c.name}, ${v !== null ? LAYER_FMT[L](v) : 'no data'}. Open city intelligence`} className="cursor-pointer outline-none"
                onClick={(e) => { e.stopPropagation(); onSelect(c.id); }} onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onSelect(c.id); } }}
                onPointerEnter={(e) => { const b = wrap.current!.getBoundingClientRect(); setHover({ c, x: e.clientX - b.left, y: e.clientY - b.top }); }} onPointerMove={(e) => { const b = wrap.current!.getBoundingClientRect(); setHover({ c, x: e.clientX - b.left, y: e.clientY - b.top }); }}
                onPointerLeave={() => setHover(null)}>
                {alarm && <circle r={r} fill="none" stroke={color(L, v)} strokeWidth={1.2} vectorEffect="non-scaling-stroke" className="india-ping" />}
                <circle r={r * 2.4} fill="transparent" />
                <circle r={r} fill={color(L, v)} stroke={sel ? '#EDF2F4' : '#0B1014'} strokeWidth={sel ? 2 : 1.4} vectorEffect="non-scaling-stroke" />
                {labels.has(c.id) && <text x={r + 4 / tf.k} y={3.8 / tf.k} fontSize={11.5 / tf.k} fill={sel ? '#EDF2F4' : 'rgba(237,242,244,0.86)'} stroke="#0B1014" strokeWidth={3 / tf.k} paintOrder="stroke" style={{ pointerEvents: 'none', fontFamily: 'IBM Plex Sans, sans-serif' }}>{c.name}</text>}
              </g>);
          })}
        </g>
      </svg>
      {hover && (
        <div className="pointer-events-none absolute z-20 border border-white/15 bg-[#0B1014]/95 px-3 py-2 text-[12px] leading-snug shadow-xl" style={{ left: Math.min(hover.x + 14, w - 220), top: Math.max(hover.y - 8, 8), width: 206 }}>
          <div className="flex items-baseline justify-between gap-2"><b className="text-[13px] text-[#EDF2F4]">{hover.c.name}</b><span className="text-[10px] text-[#84939C] truncate">{hover.c.state}</span></div>
          <div className="mt-1 grid grid-cols-2 gap-x-3 gap-y-0.5 num text-[11.5px] text-[#84939C]">
            <span>AQI</span><span className="text-[#EDF2F4] text-right">{fmt(hover.c.aqi)} <span className="text-[10px]">{hover.c.aqi_category ?? ''}</span></span>
            <span>Temp</span><span className="text-[#EDF2F4] text-right">{fmt(hover.c.temperature_c, 1)}°C</span>
            <span>Humidity</span><span className="text-[#EDF2F4] text-right">{fmt(hover.c.humidity_pct)}%</span>
            <span>Wind</span><span className="text-[#EDF2F4] text-right">{fmt(hover.c.wind_kmh)} km/h {compass(hover.c.wind_dir_deg)}</span>
            <span>Risk</span><span className="text-right" style={{ color: color('risk', hover.c.risk) }}>{hover.c.risk_tier ?? '—'}{hover.c.risk_driver ? ` · ${hover.c.risk_driver}` : ''}</span>
          </div>
        </div>)}
      <div className="absolute right-3 top-3 flex flex-col border border-white/15 bg-[#0B1014]/85 text-[#EDF2F4]">
        {[['+', 'Zoom in', () => zoomBy(1.6)], ['−', 'Zoom out', () => zoomBy(1 / 1.6)], ['⌂', 'Reset view', reset]].map(([t, l, f]) => (
          <button key={l as string} type="button" aria-label={l as string} onClick={f as () => void} className="w-8 h-8 text-[15px] hover:bg-white/10 border-b border-white/10 last:border-b-0">{t as string}</button>))}
      </div>
    </div>
  );
}
