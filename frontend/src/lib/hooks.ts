import { useEffect, useRef, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api, runEventsUrl, type RunEvent } from './api';

export const useHealth = () => useQuery({ queryKey: ['health'], queryFn: api.health, refetchInterval: 15000, retry: false });
export const useDatasets = () => useQuery({ queryKey: ['datasets'], queryFn: api.datasets });
export const useStressors = () => useQuery({ queryKey: ['stressors'], queryFn: api.stressors, staleTime: Infinity });
export const useFindings = (o: Parameters<typeof api.findings>[0] = {}) =>
  useQuery({ queryKey: ['findings', o], queryFn: () => api.findings(o) });

export const prefersReducedMotion = () =>
  typeof window !== 'undefined' && window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;

export function useReducedMotion() {
  const [r, setR] = useState(prefersReducedMotion());
  useEffect(() => {
    const m = window.matchMedia('(prefers-reduced-motion: reduce)');
    const f = () => setR(m.matches);
    m.addEventListener?.('change', f);
    return () => m.removeEventListener?.('change', f);
  }, []);
  return r;
}

/** Live UTC clock (updates every second). */
export function useClock() {
  const [now, setNow] = useState(() => new Date());
  useEffect(() => {
    const t = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(t);
  }, []);
  return now;
}

export type StreamState = { events: RunEvent[]; done: boolean; status: string | null; error: string | null };

/** Subscribe to a run's Server-Sent Events. Reconnects are avoided: the server replays from the database. */
export function useRunStream(runId: string | null): StreamState {
  const [state, setState] = useState<StreamState>({ events: [], done: false, status: null, error: null });
  const src = useRef<EventSource | null>(null);
  useEffect(() => {
    if (!runId) return;
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setState({ events: [], done: false, status: null, error: null });
    const es = new EventSource(runEventsUrl(runId));
    src.current = es;
    es.onmessage = (m) => {
      const ev = JSON.parse(m.data) as RunEvent;
      setState((s) => ({ ...s, events: [...s.events, ev] }));
    };
    es.addEventListener('end', (m) => {
      const d = JSON.parse((m as MessageEvent).data);
      setState((s) => ({ ...s, done: true, status: d.status }));
      es.close();
    });
    es.onerror = () => {
      setState((s) => (s.done ? s : { ...s, error: 'stream interrupted' }));
      es.close();
    };
    return () => es.close();
  }, [runId]);
  return state;
}
