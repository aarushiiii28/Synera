import { useEffect, useRef, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api, liveStreamUrl, runEventsUrl, type RunEvent } from './api';
import { boundedAppend, type LiveReading, type LiveStatus } from './live';
import { isStatic } from './snapshot';

export const useHealth = () => useQuery({ queryKey: ['health'], queryFn: api.health, refetchInterval: 15000, retry: false });
export const useDatasets = () => useQuery({ queryKey: ['datasets'], queryFn: api.datasets });
export const useStressors = () => useQuery({ queryKey: ['stressors'], queryFn: api.stressors, staleTime: Infinity });
export const useScenarioModel = (outcome: string) => useQuery({ queryKey: ['scenario-model', outcome], queryFn: () => api.scenarioModel(outcome), staleTime: Infinity });
export const useScenarioOutcomes = () => useQuery({ queryKey: ['scenario-outcomes'], queryFn: api.scenarioOutcomes, staleTime: Infinity });
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

export interface LiveFeed { status: LiveStatus | null; readings: LiveReading[]; apiError: string | null; streaming: boolean; unavailable: boolean }

/** The live sensor feed: current status, a bounded history, then every new reading over Server-Sent Events. Never invents data: an unreachable API gives an error, not readings. */
export function useLiveFeed(): LiveFeed {
  const [feed, setFeed] = useState<LiveFeed>({ status: null, readings: [], apiError: null, streaming: false, unavailable: isStatic });
  useEffect(() => {
    if (isStatic) return;                               // the recorded demo has no hardware and no API
    let es: EventSource | null = null;
    let dead = false;
    (async () => {
      try {
        const r = await api.liveReadings(0, 1500);
        if (dead) return;
        setFeed((f) => ({ ...f, status: r.status, readings: r.items, apiError: null }));
        es = new EventSource(liveStreamUrl(r.latest_seq));
        es.onopen = () => setFeed((f) => ({ ...f, streaming: true, apiError: null }));
        es.addEventListener('reading', (m) => {
          const rd = JSON.parse((m as MessageEvent).data) as LiveReading;
          setFeed((f) => {
            // a new connection restarts the sequence: drop history from a previous source so real and simulated readings are never mixed
            const base = f.readings.length && rd.source !== f.readings[f.readings.length - 1].source ? [] : f.readings;
            return { ...f, readings: boundedAppend(base.length && rd.seq < base[base.length - 1].seq ? [] : base, [rd]) };
          });
        });
        es.addEventListener('status', (m) => setFeed((f) => {
          const s = JSON.parse((m as MessageEvent).data) as LiveStatus;
          const newSession = !!f.status && s.packets_ok < f.status.packets_ok;      // the counters restarted: a different connection, so start the history afresh
          return { ...f, status: s, readings: newSession ? [] : f.readings };
        }));
        es.onerror = () => setFeed((f) => ({ ...f, streaming: false }));
      } catch (e) {
        if (!dead) setFeed((f) => ({ ...f, apiError: e instanceof Error ? e.message : 'The SYNERA API is unreachable', streaming: false }));
      }
    })();
    return () => { dead = true; es?.close(); };
  }, []);
  return feed;
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
