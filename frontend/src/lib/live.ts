// Live Stress Lab logic. Pure functions only: nothing here talks to the network and nothing invents a measurement.

export type Source = 'REAL_SENSOR' | 'SIMULATED_TEST';
export type Quality = 'OK' | 'MISSING' | 'OUT_OF_SENSOR_RANGE' | 'WARMING_UP';
export type SensorKey = 'temperature' | 'humidity' | 'gas';

export interface LiveMeasurement { sensor: SensorKey; value: number | null; unit: string; quality: Quality }
export interface LiveReading { seq: number; device_id: string; time_ms: number; received_utc: string; source: Source; measurements: LiveMeasurement[] }
export type BridgeState = 'DISCONNECTED' | 'CONNECTING' | 'CONNECTED' | 'RECONNECTING' | 'ERROR' | 'TEST_MODE';
export interface LiveStatus {
  state: BridgeState; port: string | null; baud: number | null; device_id: string | null; source: Source | null; message: string;
  packets_ok: number; packets_rejected: number; last_error: string | null; last_packet_utc: string | null; connected_since_utc: string | null;
  receiving: boolean; seconds_since_packet: number | null; buffered: number; test_mode: boolean;
  session: { file: string; rows: number } | null;
  last_session: { file: string; rows: number; sealed: boolean; sha256?: string; ledger_block?: number } | null;
}

export const SENSORS: { key: SensorKey; label: string; unit: string; color: string; digits: number; sensor: string }[] = [
  { key: 'temperature', label: 'Temperature', unit: '°C', color: 'var(--solar)', digits: 1, sensor: 'DHT11' },
  { key: 'humidity', label: 'Relative humidity', unit: '%', color: 'var(--signal)', digits: 0, sensor: 'DHT11' },
  { key: 'gas', label: 'Smoke / gas level', unit: 'raw', color: 'var(--biosphere)', digits: 0, sensor: 'MQ gas sensor' },
];

export const valueOf = (r: LiveReading, k: SensorKey): number | null => r.measurements.find((m) => m.sensor === k)?.value ?? null;
export const qualityOf = (r: LiveReading, k: SensorKey): Quality => r.measurements.find((m) => m.sensor === k)?.quality ?? 'MISSING';
export const timeOf = (r: LiveReading): number => Date.parse(r.received_utc);

/** Keep the newest `max` readings: the page never holds an unbounded history. */
export const boundedAppend = (list: LiveReading[], more: LiveReading[], max = 1500): LiveReading[] => {
  const seen = list.length ? list[list.length - 1].seq : 0;
  const fresh = more.filter((r) => r.seq > seen);
  if (!fresh.length) return list;
  const all = list.concat(fresh);
  return all.length > max ? all.slice(all.length - max) : all;
};

export const windowOf = (list: LiveReading[], seconds: number | null): LiveReading[] => {
  if (!seconds || !list.length) return list;
  const end = timeOf(list[list.length - 1]);
  return list.filter((r) => timeOf(r) >= end - seconds * 1000);
};

export interface SeriesStats { n: number; current: number | null; previous: number | null; min: number | null; max: number | null; trend: 'rising' | 'falling' | 'steady' | null }

/** Current, previous, min and max over the VALID values only, and a trend from the last five values against the five before. */
export function seriesStats(values: (number | null)[], flatBelow = 0): SeriesStats {
  const v = values.filter((x): x is number => x !== null && Number.isFinite(x));
  if (!v.length) return { n: 0, current: null, previous: null, min: null, max: null, trend: null };
  const mean = (a: number[]) => a.reduce((s, x) => s + x, 0) / a.length;
  let trend: SeriesStats['trend'] = null;
  if (v.length >= 4) {
    const k = Math.min(5, Math.floor(v.length / 2));
    const d = mean(v.slice(-k)) - mean(v.slice(-2 * k, -k));
    trend = Math.abs(d) <= flatBelow ? 'steady' : d > 0 ? 'rising' : 'falling';
  }
  return { n: v.length, current: v[v.length - 1], previous: v.length > 1 ? v[v.length - 2] : null, min: Math.min(...v), max: Math.max(...v), trend };
}

// ---------------------------------------------------------------------------------------------------- derived physics
/** Heat index in °C: the NWS Rothfusz regression where it is valid (T >= 80 °F and RH >= 40 %), the simple average elsewhere. Same arithmetic as synera_core.data.cities.calculate_heat_index. */
export function heatIndexC(tC: number, rh: number): number {
  const t = tC * 9 / 5 + 32;
  const simple = 0.5 * (t + 61.0 + (t - 68.0) * 1.2 + rh * 0.094);
  const roth = -42.379 + 2.04901523 * t + 10.14333127 * rh - 0.22475541 * t * rh - 6.83783e-3 * t * t - 5.481717e-2 * rh * rh
    + 1.22874e-3 * t * t * rh + 8.5282e-4 * t * rh * rh - 1.99e-6 * t * t * rh * rh;
  return ((t >= 80 && rh >= 40 ? roth : simple) - 32) * 5 / 9;
}

/** The National Weather Service heat-index categories, in °C. */
export function heatCategory(hi: number): { label: string; tone: string; advice: string } {
  if (hi < 27) return { label: 'Comfortable', tone: 'var(--biosphere)', advice: 'No heat stress expected for most people.' };
  if (hi < 32) return { label: 'Caution', tone: 'var(--teal, #4fd1c5)', advice: 'Fatigue is possible with prolonged exposure and activity.' };
  if (hi < 41) return { label: 'Extreme caution', tone: 'var(--solar)', advice: 'Heat cramps and heat exhaustion are possible with prolonged exposure.' };
  if (hi < 54) return { label: 'Danger', tone: 'var(--alert)', advice: 'Heat exhaustion is likely; heat stroke is possible.' };
  return { label: 'Extreme danger', tone: 'var(--alert)', advice: 'Heat stroke is highly likely.' };
}

export interface Smoke { ready: boolean; learned: number; needed: number; baseline: number | null; current: number | null; abovePct: number | null; state: 'learning' | 'clean' | 'elevated' | 'detected' }
const NEEDED = 30;          // readings (about a minute) before a baseline is trusted

/** The gas level against the sensor's own clean-air baseline in this room (the median of its lowest fifth of readings), not against any outside standard. */
export function smokeLevel(values: (number | null)[]): Smoke {
  const v = values.filter((x): x is number => x !== null && Number.isFinite(x));
  const current = v.length ? v[v.length - 1] : null;
  if (v.length < NEEDED) return { ready: false, learned: v.length, needed: NEEDED, baseline: null, current, abovePct: null, state: 'learning' };
  const low = [...v].sort((a, b) => a - b).slice(0, Math.max(5, Math.floor(v.length / 5)));
  const baseline = Math.max(20, low[Math.floor(low.length / 2)]);               // a floor keeps a near-zero baseline from inflating every percentage
  const recent = v.slice(-3);
  const above = (recent.reduce((s, x) => s + x, 0) / recent.length / baseline - 1) * 100;
  const state: Smoke['state'] = above >= 50 ? 'detected' : above >= 15 ? 'elevated' : 'clean';
  return { ready: true, learned: v.length, needed: NEEDED, baseline, current, abovePct: above, state };
}

export const qualityNote = (q: Quality): string =>
  q === 'OK' ? 'valid' : q === 'MISSING' ? 'the sensor gave no value (shown as missing, never filled in)' : q === 'WARMING_UP' ? 'the gas sensor is still warming up: treat as provisional'
    : 'outside the sensor\'s rated range: treat as unreliable';
