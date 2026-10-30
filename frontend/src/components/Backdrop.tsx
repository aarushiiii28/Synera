import { useEffect, useRef } from 'react';
import { useLocation } from 'react-router-dom';
import { geoGraticule10, geoOrthographic, geoPath } from 'd3';
import { useReducedMotion } from '../lib/hooks';

/** Seeded star-field on a canvas: varied size/brightness, very slow twinkle, static under reduced motion. */
export function Stars({ count = 260 }: { count?: number }) {
  const ref = useRef<HTMLCanvasElement>(null);
  const reduced = useReducedMotion();
  useEffect(() => {
    const cv = ref.current;
    if (!cv) return;
    const ctx = cv.getContext('2d')!;
    let seed = 20260929;
    const rnd = () => ((seed = (seed * 1664525 + 1013904223) % 4294967296) / 4294967296);
    const stars = Array.from({ length: count }, () => ({ x: rnd(), y: rnd(), r: 0.3 + rnd() ** 3 * 1.6, a: 0.25 + rnd() * 0.65, p: rnd() * 6.28, warm: rnd() > 0.82 }));
    let raf = 0;
    const draw = (t: number) => {
      const w = (cv.width = cv.clientWidth), h = (cv.height = cv.clientHeight);
      ctx.clearRect(0, 0, w, h);
      for (const s of stars) {
        const tw = reduced ? 1 : 0.75 + 0.25 * Math.sin(t / 2600 + s.p);
        ctx.globalAlpha = s.a * tw;
        ctx.fillStyle = s.warm ? '#ffd9a0' : '#cfe6ff';
        ctx.beginPath();
        ctx.arc(s.x * w, s.y * h, s.r, 0, 6.2832);
        ctx.fill();
      }
      if (!reduced) raf = requestAnimationFrame(draw);
    };
    draw(0);
    const onR = () => draw(0);
    window.addEventListener('resize', onR);
    return () => { cancelAnimationFrame(raf); window.removeEventListener('resize', onR); };
  }, [count, reduced]);
  return <canvas ref={ref} aria-hidden className="absolute inset-0 w-full h-full pointer-events-none" />;
}

/** A graticule limb cropped off the bottom-right, like the edge of a planet. Latitude/longitude, never a square grid. */
export function Graticule({ rotate = [-25, -18, 0] as [number, number, number], opacity = 1 }: { rotate?: [number, number, number]; opacity?: number }) {
  const w = 1600, h = 900;
  const proj = geoOrthographic().scale(1050).translate([w * 0.82, h * 1.12]).rotate(rotate).clipAngle(90);
  const d = geoPath(proj)(geoGraticule10()) ?? '';
  return (
    <svg viewBox={`0 0 ${w} ${h}`} preserveAspectRatio="xMidYMid slice" aria-hidden className="absolute inset-0 w-full h-full pointer-events-none" style={{ opacity }}>
      <path d={d} fill="none" stroke="var(--line)" strokeWidth={0.6} />
    </svg>
  );
}

/** Fixed full-viewport atmosphere behind all pages. */
export function Backdrop() {
  const home = useLocation().pathname === '/observatory'; // the Observatory shows the Earth itself, so no graticule behind it
  return (
    <div className="fixed inset-0 -z-0 pointer-events-none overflow-hidden" aria-hidden>
      <Stars />
      {!home && <Graticule opacity={0.7} />}
      <div className="absolute inset-0" style={{ boxShadow: 'inset 0 0 160px 40px rgba(2,6,13,0.9)' }} />
    </div>
  );
}
