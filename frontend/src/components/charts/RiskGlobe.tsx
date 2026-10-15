import { useEffect, useRef } from 'react';
import { useQuery } from '@tanstack/react-query';
import { geoDistance, geoGraticule10, geoOrthographic, geoPath } from 'd3';
import type { GeoPermissibleObjects } from 'd3';
import { useReducedMotion } from '../../lib/hooks';

interface Region { id: string; lat: number; lon: number }

async function loadLand(): Promise<GeoPermissibleObjects> {
  const r = await fetch('/land.geojson');
  if (!r.ok) throw new Error('land outline unavailable');
  return r.json();
}

/** Small orthographic world. Rotates to the selected city; all cities are dots, the selected one has a ring. */
export function RiskGlobe({ regions, selected, size = 260 }: { regions: Region[]; selected: string; size?: number }) {
  const land = useQuery({ queryKey: ['land'], queryFn: loadLand, staleTime: Infinity });
  const ref = useRef<HTMLCanvasElement>(null);
  const rot = useRef<[number, number]>([0, -15]);
  const reduced = useReducedMotion();
  const target = regions.find((r) => r.id === selected);

  useEffect(() => {
    const cv = ref.current;
    if (!cv || !land.data) return;
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    cv.width = size * dpr; cv.height = size * dpr;
    const ctx = cv.getContext('2d');
    if (!ctx) return;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    const proj = geoOrthographic().translate([size / 2, size / 2]).scale(size / 2 - 6).clipAngle(90);
    const path = geoPath(proj, ctx);
    const style = getComputedStyle(document.documentElement);
    const col = (n: string) => style.getPropertyValue(n).trim() || '#16b5ff';
    const draw = (r: [number, number]) => {
      proj.rotate([-r[0], -r[1]]);
      ctx.clearRect(0, 0, size, size);
      ctx.beginPath(); path({ type: 'Sphere' }); ctx.fillStyle = 'rgba(6,20,36,0.9)'; ctx.fill();
      ctx.beginPath(); path(geoGraticule10()); ctx.strokeStyle = 'rgba(110,190,255,0.14)'; ctx.lineWidth = 0.6; ctx.stroke();
      ctx.beginPath(); path(land.data); ctx.fillStyle = 'rgba(111,214,91,0.28)'; ctx.fill(); ctx.strokeStyle = 'rgba(111,214,91,0.55)'; ctx.lineWidth = 0.6; ctx.stroke();
      ctx.beginPath(); path({ type: 'Sphere' }); ctx.strokeStyle = col('--line-strong'); ctx.lineWidth = 1; ctx.stroke();
      regions.forEach((c) => {
        const p = proj([c.lon, c.lat]);
        if (!p || geoDistance([c.lon, c.lat], r) >= Math.PI / 2) return; // far side of the globe
        const isSel = c.id === selected;
        ctx.beginPath(); ctx.arc(p[0], p[1], isSel ? 4 : 2.4, 0, Math.PI * 2);
        ctx.fillStyle = isSel ? col('--solar') : col('--signal'); ctx.fill();
        if (isSel) {
          ctx.beginPath(); ctx.arc(p[0], p[1], 10, 0, Math.PI * 2);
          ctx.strokeStyle = col('--solar'); ctx.lineWidth = 1.4; ctx.stroke();
        }
      });
    };
    let raf = 0;
    const goal: [number, number] = target ? [target.lon, target.lat] : rot.current;
    const from = rot.current;
    const start = performance.now();
    const ease = (k: number) => 1 - Math.pow(1 - k, 3);
    const tick = (now: number) => {
      const k = reduced ? 1 : Math.min(1, (now - start) / 900);
      // shortest longitude path
      let dl = goal[0] - from[0];
      dl = ((dl + 540) % 360) - 180;
      const r: [number, number] = [from[0] + dl * ease(k), from[1] + (goal[1] - from[1]) * ease(k)];
      rot.current = r;
      draw(r);
      if (k < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [land.data, regions, selected, target, size, reduced]);

  return (
    <div className="relative" style={{ width: size, height: size }}>
      <canvas ref={ref} style={{ width: size, height: size }} role="img" aria-label={`Globe centred on ${selected}`} />
      {land.isLoading && <div className="absolute inset-0 grid place-items-center label">LOADING MAP</div>}
      {land.isError && <div className="absolute inset-0 grid place-items-center label text-center px-4">MAP OUTLINE NOT AVAILABLE</div>}
    </div>
  );
}
