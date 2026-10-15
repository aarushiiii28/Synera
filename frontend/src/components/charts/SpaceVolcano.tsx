import { useEffect, useMemo, useRef, useState, type PointerEvent } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api, type Gene, type SpaceOverview } from '../../lib/api';
import { Async } from '../States';
import { fix, int, sci } from '../../lib/format';
import { Term } from '../Term';
import { POINT_COLOR, fdrLineY, linearScale, nearestPoint, toPoints, topByP, volcanoDomain, type VolcanoPoint } from './trustLogic';

const M = { l: 54, r: 18, t: 18, b: 48 };

function Plot({ pts, overview, focus, onPick }: { pts: VolcanoPoint[]; overview: SpaceOverview; focus: VolcanoPoint | null; onPick: (p: VolcanoPoint | null) => void }) {
  const wrap = useRef<HTMLDivElement>(null);
  const canvas = useRef<HTMLCanvasElement>(null);
  const [size, setSize] = useState({ w: 800, h: 460 });
  const [hover, setHover] = useState<{ p: VolcanoPoint; x: number; y: number } | null>(null);
  const fy = fdrLineY(overview.fdr_line_p);
  const dom = useMemo(() => volcanoDomain(pts, fy), [pts, fy]);
  const top = useMemo(() => topByP(pts, 8), [pts]);
  const sx = useMemo(() => linearScale(-dom.xMax, dom.xMax, M.l, size.w - M.r), [dom, size.w]);
  const sy = useMemo(() => linearScale(0, dom.yMax, size.h - M.b, M.t), [dom, size.h]);

  useEffect(() => {
    const el = wrap.current;
    if (!el) return;
    const ro = new ResizeObserver(() => setSize({ w: Math.max(300, el.clientWidth), h: el.clientWidth < 560 ? 340 : 460 }));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  useEffect(() => {
    const c = canvas.current;
    if (!c) return;
    const dpr = window.devicePixelRatio || 1;
    c.width = size.w * dpr; c.height = size.h * dpr;
    const g = c.getContext('2d');
    if (!g) return;
    g.setTransform(dpr, 0, 0, dpr, 0, 0);
    g.clearRect(0, 0, size.w, size.h);
    const css = getComputedStyle(document.documentElement);
    const col = (n: string) => css.getPropertyValue(n).trim();
    g.font = '11px "IBM Plex Mono", monospace';
    // grid + ticks
    g.lineWidth = 1; g.fillStyle = col('--faint'); g.strokeStyle = 'rgba(110,190,255,0.10)';
    for (let x = -dom.xMax; x <= dom.xMax; x += Math.max(1, Math.round(dom.xMax / 5))) {
      g.beginPath(); g.moveTo(sx(x), M.t); g.lineTo(sx(x), size.h - M.b); g.stroke();
      g.textAlign = 'center'; g.fillText(String(x), sx(x), size.h - M.b + 16);
    }
    for (let y = 0; y <= dom.yMax; y += 1) {
      g.beginPath(); g.moveTo(M.l, sy(y)); g.lineTo(size.w - M.r, sy(y)); g.stroke();
      g.textAlign = 'right'; g.fillText(String(y), M.l - 8, sy(y) + 4);
    }
    g.strokeStyle = 'rgba(110,190,255,0.4)'; g.beginPath(); g.moveTo(sx(0), M.t); g.lineTo(sx(0), size.h - M.b); g.stroke();
    g.fillStyle = col('--muted'); g.textAlign = 'center';
    g.fillText('interaction size b_AB (log2): negative = antagonistic side, positive = synergistic side', (M.l + size.w - M.r) / 2, size.h - 8);
    g.save(); g.translate(13, (M.t + size.h - M.b) / 2); g.rotate(-Math.PI / 2); g.fillText('surprise: -log10 p  (higher = more surprising)', 0, 0); g.restore();
    // points (named types on top)
    const order = ['none', 'ANTAGONISTIC', 'SYNERGISTIC'];
    for (const t of order) {
      g.fillStyle = POINT_COLOR[t] ?? POINT_COLOR.none;
      for (const p of pts) if ((order.includes(p.type) ? p.type : 'none') === t) g.fillRect(sx(p.x) - 1, sy(p.y) - 1, t === 'none' ? 2 : 3.5, t === 'none' ? 2 : 3.5);
    }
    // FDR line
    g.setLineDash([7, 5]); g.strokeStyle = col('--alert'); g.lineWidth = 1.4;
    g.beginPath(); g.moveTo(M.l, sy(fy)); g.lineTo(size.w - M.r, sy(fy)); g.stroke(); g.setLineDash([]);
    g.fillStyle = col('--alert'); g.textAlign = 'right';
    g.fillText(`above this line = would pass FDR ${fix(overview.fdr_alpha * 100, 0)}%  (p ≤ ${sci(overview.fdr_line_p, 2)})`, size.w - M.r - 4, sy(fy) - 6);
    // top-8 labels
    g.fillStyle = col('--text'); g.lineWidth = 1;
    const placed: { x0: number; x1: number; y: number }[] = [];
    for (const p of top) {
      const right = sx(p.x) < size.w * 0.7;
      g.strokeStyle = 'rgba(234,242,251,0.5)'; g.beginPath(); g.arc(sx(p.x), sy(p.y), 3.5, 0, Math.PI * 2); g.stroke();
      g.textAlign = right ? 'left' : 'right';
      const tw = g.measureText(p.gene).width, x0 = sx(p.x) + (right ? 8 : -8 - tw);
      let ly = sy(p.y) + 4;
      while (placed.some((r) => Math.abs(r.y - ly) < 13 && x0 < r.x1 && x0 + tw > r.x0)) ly += 13;
      placed.push({ x0, x1: x0 + tw, y: ly });
      if (Math.abs(ly - (sy(p.y) + 4)) > 1) { g.strokeStyle = 'rgba(234,242,251,0.3)'; g.beginPath(); g.moveTo(sx(p.x), sy(p.y)); g.lineTo(sx(p.x) + (right ? 8 : -8), ly - 4); g.stroke(); }
      g.fillText(p.gene, sx(p.x) + (right ? 8 : -8), ly);
    }
    // focus (search / hover)
    for (const f of [focus, hover?.p ?? null]) {
      if (!f) continue;
      g.strokeStyle = col('--signal'); g.lineWidth = 2; g.beginPath(); g.arc(sx(f.x), sy(f.y), 7, 0, Math.PI * 2); g.stroke();
    }
    if (focus) { g.fillStyle = col('--signal'); g.textAlign = sx(focus.x) < size.w * 0.7 ? 'left' : 'right'; g.fillText(focus.gene, sx(focus.x) + (sx(focus.x) < size.w * 0.7 ? 12 : -12), sy(focus.y) - 8); }
  }, [pts, size, dom, sx, sy, fy, overview, top, focus, hover]);

  const move = (e: PointerEvent<HTMLCanvasElement>) => {
    const r = e.currentTarget.getBoundingClientRect();
    const px = e.clientX - r.left, py = e.clientY - r.top;
    const p = nearestPoint(pts, sx, sy, px, py, 12);
    setHover(p ? { p, x: px, y: py } : null);
  };

  return (
    <div ref={wrap} className="relative">
      <canvas ref={canvas} style={{ width: size.w, height: size.h, touchAction: 'pan-y' }} className="block cursor-crosshair"
        onPointerMove={move} onPointerLeave={() => setHover(null)} onClick={() => onPick(hover?.p ?? null)}
        role="img" aria-label={`Volcano plot of ${int(pts.length)} tested genes. None crosses the FDR line. The table below lists the strongest 20.`} />
      {hover && (
        <div className="absolute z-10 pointer-events-none border border-line-strong bg-void px-3 py-2 num text-xs leading-relaxed" style={{ left: Math.min(hover.x + 14, size.w - 190), top: Math.max(hover.y - 70, 4), width: 180 }} role="status">
          <div className="text-text text-sm">{hover.p.gene}</div>
          <div className="text-muted">b_AB <span className="text-text">{fix(hover.p.x, 2)}</span> log2</div>
          <div className="text-muted">p <span className="text-text">{sci(Math.pow(10, -hover.p.y), 2)}</span></div>
          <div className="text-muted">q <span className="text-text">{sci(hover.p.q, 2)}</span></div>
        </div>
      )}
    </div>
  );
}

export function SpaceVolcano({ overview }: { overview: SpaceOverview }) {
  const q = useQuery({ queryKey: ['genes-compact'], queryFn: () => api.genesCompact(30000), staleTime: Infinity });
  const [term, setTerm] = useState('');
  const [submitted, setSubmitted] = useState('');
  const [picked, setPicked] = useState<VolcanoPoint | null>(null);
  const search = useQuery({ queryKey: ['genes-search', submitted], queryFn: () => api.genes({ search: submitted, limit: 8 }), enabled: submitted !== '' });
  const pts = useMemo(() => (q.data ? toPoints(q.data.rows) : []), [q.data]);
  const matches = (search.data?.items ?? []) as Gene[];
  const focus = picked ?? (matches[0] ? pts.find((p) => p.gene === matches[0].gene_symbol) ?? null : null);
  const named = pts.filter((p) => p.type !== 'none').length;

  return (
    <div>
      <form className="flex flex-wrap items-center gap-3 mb-3" role="search" onSubmit={(e) => { e.preventDefault(); setPicked(null); setSubmitted(term.trim()); }}>
        <label htmlFor="gene-search" className="label">Find a gene</label>
        <input id="gene-search" value={term} onChange={(e) => { setTerm(e.target.value); if (!e.target.value) { setSubmitted(''); setPicked(null); } }} placeholder="e.g. a gene symbol" className="num bg-void border border-line-strong px-3 py-1.5 text-sm w-56" />
        <button type="submit" className="num text-xs tracking-[0.14em] border border-signal text-signal px-3 py-2 hover:bg-signal/10 cursor-pointer">HIGHLIGHT</button>
        {submitted && !search.isLoading && (matches.length === 0
          ? <span className="num text-xs text-solar">no gene matches “{submitted}”</span>
          : <span className="flex flex-wrap gap-1.5">{matches.map((m) => <button type="button" key={m.ensembl_id} onClick={() => setPicked(pts.find((p) => p.gene === m.gene_symbol) ?? null)} className="num text-[11px] border border-line-strong px-2 py-1 text-muted hover:text-text cursor-pointer">{m.gene_symbol} · q {sci(m.q, 2)}</button>)}</span>)}
      </form>
      <Async q={q} h={460}>
        {() => (
          <>
            <Plot pts={pts} overview={overview} focus={focus} onPick={setPicked} />
            <div className="flex flex-wrap gap-x-6 gap-y-1 mt-3 num text-xs text-muted">
              <span><span className="inline-block w-2.5 h-2.5 mr-1.5 align-middle" style={{ background: POINT_COLOR.none }} />{int(pts.length - named)} genes: no interaction</span>
              <span><span className="inline-block w-2.5 h-2.5 mr-1.5 align-middle" style={{ background: POINT_COLOR.SYNERGISTIC }} />{int(pts.filter((p) => p.type === 'SYNERGISTIC').length)} synergistic</span>
              <span><span className="inline-block w-2.5 h-2.5 mr-1.5 align-middle" style={{ background: POINT_COLOR.ANTAGONISTIC }} />{int(pts.filter((p) => p.type === 'ANTAGONISTIC').length)} antagonistic</span>
              <span><span className="inline-block w-5 border-t-2 border-dashed border-alert mr-1.5 align-middle" /><Term k="fdr">FDR</Term> threshold</span>
            </div>
          </>
        )}
      </Async>
    </div>
  );
}
