import { useCallback, useEffect, useRef, useState } from 'react';

/** Measures the width of a container so SVG charts draw at real pixel size (legible text on phones). */
export function useChartWidth(fallback = 560): [(el: HTMLElement | null) => void, number] {
  const [w, setW] = useState(fallback);
  const ro = useRef<ResizeObserver | null>(null);
  const ref = useCallback((el: HTMLElement | null) => {
    ro.current?.disconnect();
    ro.current = null;
    if (!el || typeof ResizeObserver === 'undefined') return;
    ro.current = new ResizeObserver((entries) => {
      const cw = Math.floor(entries[0].contentRect.width);
      if (cw > 0) setW(cw);
    });
    ro.current.observe(el);
  }, []);
  useEffect(() => () => ro.current?.disconnect(), []);
  return [ref, w];
}
