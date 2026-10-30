// Live Stress Lab logic. Pure functions only: nothing here talks to the network and nothing invents a measurement.

export type Source = 'REAL_SENSOR' | 'SIMULATED_TEST';
export type Quality = 'OK' | 'MISSING' | 'OUT_OF_SENSOR_RANGE' | 'WARMING_UP';
export type SensorKey = 'temperature' | 'humidity' | 'gas';
export type ProvClass = 'REAL SENSOR' | 'SIMULATED' | 'HISTORICAL' | 'DERIVED';

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
  { key: 'gas', label: 'Gas sensor, raw', unit: 'ADC', color: 'var(--biosphere)', digits: 0, sensor: 'MQ-series analog output' },
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

/** Dew point in °C (Magnus formula), the temperature at which this air would be saturated. */
export function dewPointC(tC: number, rh: number): number {
  const a = 17.625, b = 243.04;
  const g = Math.log(Math.max(rh, 0.01) / 100) + (a * tC) / (b + tC);
  return (b * g) / (a - g);
}

// ---------------------------------------------------------------------------------------------------- scenarios
export type VarKey = 'temperature' | 'humidity' | 'gas' | 'pm25' | 'pm10' | 'co2';
export interface VarSpec { key: VarKey; label: string; unit: string; prov: ProvClass; min: number; max: number; step: number; source: string; note: string }

export const VARS: VarSpec[] = [
  { key: 'temperature', label: 'Temperature', unit: '°C', prov: 'REAL SENSOR', min: 0, max: 50, step: 0.5, source: 'DHT11 on the Arduino (D2)', note: 'Whole degrees, about ±2 °C.' },
  { key: 'humidity', label: 'Relative humidity', unit: '%', prov: 'REAL SENSOR', min: 20, max: 90, step: 1, source: 'DHT11 on the Arduino (D2)', note: 'Whole percent, about ±5 % RH.' },
  { key: 'gas', label: 'Gas sensor, raw', unit: 'ADC', prov: 'REAL SENSOR', min: 0, max: 1023, step: 1, source: 'MQ-series analog output on A0', note: 'A raw voltage reading. Not ppm, not AQI, not PM2.5. Uncalibrated.' },
  { key: 'pm25', label: 'PM2.5', unit: 'µg/m³', prov: 'SIMULATED', min: 0, max: 300, step: 1, source: 'set by you; no PM sensor is attached', note: 'A scenario input, not a measurement.' },
  { key: 'pm10', label: 'PM10', unit: 'µg/m³', prov: 'SIMULATED', min: 0, max: 500, step: 1, source: 'set by you; no PM sensor is attached', note: 'A scenario input, not a measurement.' },
  { key: 'co2', label: 'CO₂', unit: 'ppm', prov: 'SIMULATED', min: 350, max: 5000, step: 10, source: 'set by you; no CO₂ sensor is attached', note: 'A scenario input, not a measurement.' },
];
export const VAR = Object.fromEntries(VARS.map((v) => [v.key, v])) as Record<VarKey, VarSpec>;

export type Conditions = Record<VarKey, number>;
export interface Scenario { id: string; name: string; values: Conditions; hours: number; fromLive?: boolean }

export const DEFAULTS: Conditions = { temperature: 25, humidity: 50, gas: 100, pm25: 20, pm10: 40, co2: 450 };

export interface Derived { heatIndex: number; dewPoint: number }
export const derive = (c: Pick<Conditions, 'temperature' | 'humidity'>): Derived => ({ heatIndex: heatIndexC(c.temperature, c.humidity), dewPoint: dewPointC(c.temperature, c.humidity) });

/** The classic 2 x 2 comparison of the user's example: baseline, both raised (A), temperature only (B), humidity only (C). */
export function factorialScenarios(base: Conditions, tHigh: number, rhHigh: number): Scenario[] {
  const mk = (id: string, name: string, t: number, h: number): Scenario => ({ id, name, hours: 24, values: { ...base, temperature: t, humidity: h } });
  return [mk('base', 'Baseline', base.temperature, base.humidity), mk('A', 'A: hot + humid', tHigh, rhHigh), mk('B', 'B: hotter only', tHigh, base.humidity), mk('C', 'C: humid only', base.temperature, rhHigh)];
}

export type InteractionClass = 'APPROXIMATELY ADDITIVE' | 'SUPER-ADDITIVE (synergistic-like)' | 'SUB-ADDITIVE (antagonistic-like)';
export interface Contrast { baseline: number; a: number; b: number; c: number; effectT: number; effectRh: number; additive: number; interaction: number; klass: InteractionClass; curvatureT: number }

/** The deviation of the combined response from the sum of the separate responses, for the heat index (a DERIVED physical quantity), with the sign read as a class. */
export function contrast(base: Conditions, tHigh: number, rhHigh: number, tolerance = 0.25): Contrast {
  const hi = (t: number, h: number) => heatIndexC(t, h);
  const b0 = hi(base.temperature, base.humidity), a = hi(tHigh, rhHigh), b = hi(tHigh, base.humidity), c = hi(base.temperature, rhHigh);
  const effectT = b - b0, effectRh = c - b0, additive = b0 + effectT + effectRh, interaction = a - additive;
  const d = tHigh - base.temperature || 1;
  const curvatureT = hi(base.temperature + d, base.humidity) - 2 * b0 + hi(base.temperature - d, base.humidity);   // second difference along temperature: 0 for a straight line
  const klass: InteractionClass = Math.abs(interaction) <= tolerance ? 'APPROXIMATELY ADDITIVE' : interaction > 0 ? 'SUPER-ADDITIVE (synergistic-like)' : 'SUB-ADDITIVE (antagonistic-like)';
  return { baseline: b0, a, b, c, effectT, effectRh, additive, interaction, klass, curvatureT };
}

/** Heat-index surface over temperature x humidity and, for every cell, how far it sits from the additive expectation built from the baseline. */
export function interactionGrid(base: Pick<Conditions, 'temperature' | 'humidity'>, tRange: [number, number], rhRange: [number, number], n = 25) {
  const ts = Array.from({ length: n }, (_, i) => tRange[0] + ((tRange[1] - tRange[0]) * i) / (n - 1));
  const hs = Array.from({ length: n }, (_, i) => rhRange[0] + ((rhRange[1] - rhRange[0]) * i) / (n - 1));
  const b0 = heatIndexC(base.temperature, base.humidity);
  const gap = hs.map((h) => ts.map((t) => heatIndexC(t, h) - (heatIndexC(t, base.humidity) + heatIndexC(base.temperature, h) - b0)));
  const surface = hs.map((h) => ts.map((t) => heatIndexC(t, h)));
  return { ts, hs, gap, surface, maxAbsGap: Math.max(...gap.flat().map(Math.abs)) };
}

// ---------------------------------------------------------------------------------------------------- provenance
export const PROV: Record<ProvClass, { tone: string; tip: string }> = {
  'REAL SENSOR': { tone: 'var(--biosphere)', tip: 'Measured by the physical device connected to this computer.' },
  SIMULATED: { tone: 'var(--solar)', tip: 'Set by you or generated for testing. Not a measurement.' },
  HISTORICAL: { tone: 'var(--signal)', tip: 'An observation already stored in a real SYNERA dataset.' },
  DERIVED: { tone: 'var(--teal, #4fd1c5)', tip: 'Computed from other values by a stated formula.' },
};

export const qualityNote = (q: Quality): string =>
  q === 'OK' ? 'valid' : q === 'MISSING' ? 'the sensor gave no value (shown as missing, never filled in)' : q === 'WARMING_UP' ? 'the gas sensor is still warming up: treat as provisional'
    : 'outside the sensor\'s rated range: treat as unreliable';
