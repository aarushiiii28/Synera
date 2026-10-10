import React, { useEffect, useState } from 'react';
import { geoOrthographic, geoPath, geoGraticule10 } from 'd3';

export function Graticule({ 
  w = 1600, 
  h = 900, 
  scale = 1000, 
  rotate = [-25, -18, 0] as [number, number, number] 
}) {
  const [currentRotate, setCurrentRotate] = useState(rotate);
  
  useEffect(() => {
    const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (prefersReducedMotion) return;

    let frameId: number;
    const start = performance.now();
    
    const animate = (time: number) => {
      const elapsed = time - start;
      setCurrentRotate([rotate[0] + elapsed * 0.001, rotate[1], rotate[2]]);
      frameId = requestAnimationFrame(animate);
    };
    
    frameId = requestAnimationFrame(animate);
    return () => cancelAnimationFrame(frameId);
  }, [rotate]);

  const proj = geoOrthographic()
    .scale(scale)
    .translate([w * 0.8, h * 1.05])
    .rotate(currentRotate)
    .clipAngle(90);

  return (
    <svg 
      viewBox={`0 0 ${w} ${h}`} 
      preserveAspectRatio="xMidYMid slice" 
      aria-hidden
      style={{ position: "absolute", inset: 0, width: "100%", height: "100%", pointerEvents: "none", zIndex: 0 }}
    >
      <path d={geoPath(proj)(geoGraticule10()) ?? ""} fill="none" stroke="var(--line)" strokeWidth={0.6} />
    </svg>
  );
}
