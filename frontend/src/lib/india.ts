// India live intelligence: response types, map layers and the colour scales. Every colour scale is the one explained in the legend.

export type Kind = 'OBSERVATION' | 'MODEL_ANALYSIS' | 'FORECAST' | 'DERIVED' | 'HISTORY' | 'THRESHOLDS' | 'SATELLITE DETECTION';
export type Urgency = 'INFORMATIONAL' | 'ADVISORY' | 'HIGH_PRIORITY' | 'CRITICAL';
export type LayerId = 'aqi' | 'temperature' | 'humidity' | 'rainfall' | 'wind' | 'risk';

export interface CityMarker {
  id: string; name: string; state: string; lat: number; lon: number;
  temperature_c: number | null; humidity_pct: number | null; wind_kmh: number | null; wind_dir_deg: number | null; rain_24h_mm: number | null; rain_next_mm: number | null;
  pm25: number | null; pm10: number | null; aqi: number | null; aqi_category: string | null; aqi_level: number | null;
  heat_index_c: number | null; heat_category: string | null; heat_level: number | null; imd_heat: string | null;
  risk: number | null; risk_tier: string | null; risk_driver: string | null; completeness: number;
}
export interface SourceInfo { name: string; role: string; kind: string; status: string | null; fetched_at: string | null; note: string | null; docs: string | null }
export interface LayerDef { id: LayerId; label: string; field: keyof CityMarker; unit: string; legend: [number, number, string][]; note: string }
export interface Alert { city: string; id: string; kind: 'AIR' | 'HEAT' | 'RAIN'; level: Urgency; text: string }
export interface National { cities_with_air_data: number; aqi_categories: Record<string, number>; hotspots_air: { id: string; name: string; value: number; category: string | null }[];
  hottest: { id: string; name: string; value: number }[]; alerts: Alert[]; median_aqi: number | null }
export interface IndiaOverview { available: boolean; reason?: string; generated_at?: string; layers: LayerDef[]; cities: CityMarker[]; national?: National; sources?: SourceInfo[] }

export interface Metric { value: number | null; unit: string; label: string; kind: Kind; source: string; time: string | null }
export interface Evidence { label: string; value: number | string | null; threshold: string | null; source: string }
export interface Recommendation {
  rank: number; id: string; what_is_happening: string; why: string; action: string; who: string[]; urgency: Urgency; window: 'IMMEDIATE' | 'NEXT_HOURS' | 'FORECAST_PERIOD';
  confidence: { level: 'HIGH' | 'MEDIUM' | 'LOW'; score: number; why: string }; basis: 'THRESHOLD' | 'ENGINE'; evidence: Evidence[];
}
export interface Series { time: string[]; now_index: number; temperature_c?: (number | null)[]; humidity_pct?: (number | null)[]; apparent_c?: (number | null)[]; precip_mm?: (number | null)[]; wind_kmh?: (number | null)[];
  pm25?: (number | null)[]; pm10?: (number | null)[]; aqi?: (number | null)[]; observed_until: string | null }
export interface DailyPoint { date: string; is_today: boolean; is_future: boolean; tmax_c: number | null; tmin_c: number | null; apparent_max_c: number | null; precip_mm: number | null; uv_max: number | null; wind_max_kmh: number | null; kind: Kind }
export interface InteractionTerm { a: string; b: string; label: string; contribution_pct: number; lo_pct: number; hi_pct: number; supported: boolean; z_a: number; z_b: number }
export interface ModelSkill { r2_leave_states_out: number; calibration_slope: number; calibration_slope_ci: [number, number]; interaction_pairs_tested: number; interaction_pairs_excluding_zero: number;
  expected_by_chance: number; training: { rows: number; states: number; date_start: string; date_end: string }; ledger_block: number | null; dataset_sha256: string }
export interface ScenarioResult {
  available: boolean; reason?: string; outcome?: string; effect_pct?: number; lo_pct?: number; hi_pct?: number; additive_pct?: number; interaction_pct?: number; interaction_lo_pct?: number; interaction_hi_pct?: number;
  anomalies?: Record<string, number>; contributions?: Record<string, number>; interaction_terms?: InteractionTerm[]; supported_interactions?: InteractionTerm[];
  left_at_normal?: Record<string, string>; model_skill?: ModelSkill; caveats?: string[]; extrapolation?: { unusual_combination: boolean; max_abs_anomaly: number };
}
export interface GridResult { finding_id: string; status: string; dataset_id: string; stressors: string[]; z: Record<string, number>; uplift_pp: number | null; uplift_sd: number | null; state_percentile: number | null; outcome: string; state: string; replication: string }
export interface Explain {
  drivers: { parameter: string; value: string; level: number; max: number; basis: string }[]; composite: { score: number | null; driver: string | null; tier: string | null };
  conditions: { condition: string; engine_term: InteractionTerm | null; verdict: string }[];
  engine: { scenario_model: { available: boolean; reason?: string; decomposition?: Record<string, number>; method?: string; skill?: ModelSkill; plain?: string }; grid_findings: { available: boolean; reason?: string; results?: GridResult[] } };
  basis_count: { THRESHOLD: number; ENGINE: number }; not_done: string[];
}
export interface IndiaCity {
  available: boolean; reason?: string; generated_at?: string;
  city: { id: string; name: string; state: string; lat: number; lon: number; terrain: string }; as_of?: string; timezone?: string; metrics?: Record<string, Metric>;
  derived?: { aqi: { index: number | null; category: string | null; level: number | null; driver: string | null; basis: string; kind: Kind; note: string | null; pm25_24h: number | null; pm10_24h: number | null };
    heat_stress_c: number | null; heat_index: { category: string; level: number } | null; imd_heat: { status: string | null; tmax_c: number | null; departure_c: number | null; basis: string };
    rain_24h_mm: number | null; rain: { category: string; level: number } | null; rain_next_days_max_mm: number | null; uv_max: number | null; uv: { category: string; level: number } | null;
    composite: { score: number | null; driver: string | null; tier: string | null } };
  series?: Series | null; daily?: DailyPoint[]; fires?: { count: number; high_confidence: number; days: number; box_deg: number; latest: string | null } | null;
  quality?: { issues: string[]; missing: string[]; completeness: number }; sources?: SourceInfo[];
  engine?: { scenario: ScenarioResult; grid: { available: boolean; reason?: string; results?: GridResult[] } }; recommendations?: Recommendation[]; explain?: Explain;
}

// ---- colour scales --------------------------------------------------------------------------------------------------------
const AQI_STOPS: [number, string][] = [[0, '#39B980'], [50, '#39B980'], [100, '#A3D65C'], [200, '#E9B44C'], [300, '#EE8A3A'], [400, '#E45D5D'], [500, '#A8325E']];
const TEMP_STOPS: [number, string][] = [[0, '#3C6FC9'], [12, '#4FA3D9'], [22, '#4FC7B5'], [28, '#D9D36A'], [34, '#E9A23C'], [40, '#E4572E'], [48, '#A8223E']];
const HUM_STOPS: [number, string][] = [[10, '#B88A52'], [35, '#C9C17A'], [55, '#59C0A3'], [75, '#3C9AD0'], [95, '#2F59B5']];
const RAIN_STOPS: [number, string][] = [[0, '#2A3B4A'], [2.4, '#3A6A8F'], [15.5, '#3F8CC9'], [64.5, '#5B6FE0'], [115, '#8A4FD0'], [250, '#C03FA8']];
const WIND_STOPS: [number, string][] = [[0, '#6E5A8A'], [8, '#4F7FB0'], [20, '#4FB4C9'], [40, '#7FD6B0'], [70, '#E6E9A0']];
const RISK_STOPS: [number, string][] = [[0, '#39B980'], [0.3, '#A3D65C'], [0.5, '#E9B44C'], [0.7, '#E45D5D'], [1, '#A8325E']];

const SCALES: Record<LayerId, [number, string][]> = { aqi: AQI_STOPS, temperature: TEMP_STOPS, humidity: HUM_STOPS, rainfall: RAIN_STOPS, wind: WIND_STOPS, risk: RISK_STOPS };

const hex = (h: string): [number, number, number] => [parseInt(h.slice(1, 3), 16), parseInt(h.slice(3, 5), 16), parseInt(h.slice(5, 7), 16)];
export function colorRGB(layer: LayerId, v: number): [number, number, number] {
  const s = SCALES[layer];
  if (v <= s[0][0]) return hex(s[0][1]);
  for (let i = 1; i < s.length; i++) {
    if (v <= s[i][0]) {
      const t = (v - s[i - 1][0]) / (s[i][0] - s[i - 1][0] || 1), a = hex(s[i - 1][1]), b = hex(s[i][1]);
      return [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t].map(Math.round) as [number, number, number];
    }
  }
  return hex(s[s.length - 1][1]);
}
export const color = (layer: LayerId, v: number | null | undefined, alpha = 1) => {
  if (v === null || v === undefined) return 'rgba(132,147,156,0.5)';
  const [r, g, b] = colorRGB(layer, v);
  return `rgba(${r},${g},${b},${alpha})`;
};
export const legendColor = (layer: LayerId, lo: number, hi: number) => color(layer, (lo + hi) / 2);

export const LAYER_VALUE: Record<LayerId, (c: CityMarker) => number | null> = {
  aqi: (c) => c.aqi, temperature: (c) => c.temperature_c, humidity: (c) => c.humidity_pct, rainfall: (c) => c.rain_24h_mm, wind: (c) => c.wind_kmh, risk: (c) => c.risk,
};
export const LAYER_FMT: Record<LayerId, (v: number) => string> = {
  aqi: (v) => v.toFixed(0), temperature: (v) => `${v.toFixed(1)}°C`, humidity: (v) => `${v.toFixed(0)}%`, rainfall: (v) => `${v.toFixed(1)} mm`, wind: (v) => `${v.toFixed(0)} km/h`, risk: (v) => v.toFixed(2),
};

export const URGENCY_STYLE: Record<Urgency, { label: string; color: string }> = {
  INFORMATIONAL: { label: 'Informational', color: '#63B3ED' }, ADVISORY: { label: 'Advisory', color: '#E9B44C' },
  HIGH_PRIORITY: { label: 'High priority', color: '#EE8A3A' }, CRITICAL: { label: 'Critical', color: '#E45D5D' },
};
export const WINDOW_LABEL = { IMMEDIATE: 'Immediate', NEXT_HOURS: 'Next few hours', FORECAST_PERIOD: 'Upcoming forecast period' } as const;
export const KIND_LABEL: Record<string, string> = { OBSERVATION: 'Observation', MODEL_ANALYSIS: 'Model analysis', FORECAST: 'Forecast', DERIVED: 'Derived estimate', HISTORY: 'History', THRESHOLDS: 'Official thresholds', 'SATELLITE DETECTION': 'Satellite detection' };

export const compass = (deg: number | null) => (deg === null ? '—' : ['N', 'NNE', 'NE', 'ENE', 'E', 'ESE', 'SE', 'SSE', 'S', 'SSW', 'SW', 'WSW', 'W', 'WNW', 'NW', 'NNW'][Math.round(deg / 22.5) % 16]);
export const fmt = (v: number | null | undefined, d = 0) => (v === null || v === undefined || Number.isNaN(v) ? '—' : v.toFixed(d));

/** Inverse-distance weighting of city values at a point, plus how far the nearest city is (km), so the heat field can fade where nothing is measured. */
export function idw(lon: number, lat: number, pts: { lon: number; lat: number; v: number }[], power = 2.6): { v: number; nearestKm: number } | null {
  let num = 0, den = 0, near = Infinity;
  const cl = Math.cos((lat * Math.PI) / 180);
  for (const p of pts) {
    const dx = (lon - p.lon) * 111.32 * cl, dy = (lat - p.lat) * 110.57, d = Math.hypot(dx, dy);
    if (d < near) near = d;
    if (d < 1) return { v: p.v, nearestKm: d };
    const w = 1 / Math.pow(d, power);
    num += w * p.v; den += w;
  }
  return den ? { v: num / den, nearestKm: near } : null;
}
