// Browser twin of synera_core.prediction.scenario.predict: the same arithmetic, so the page answers instantly as sliders move
// (and works on the hosted, server-less demo). src/tests/scenario.test.ts checks it against numbers computed by the Python code.

export interface ScenarioTerm { name: string; kind: 'linear' | 'square' | 'season_linear' | 'season_square' | 'product'; a: string; b?: string | null }
export interface ScenarioLocation {
  lat: number | null; lon: number | null; clim: Record<string, number[]>; sd: Record<string, number>; expected_deaths: number[]; support: number[]; weeks: number;
}
export interface LearnedTerm { term: string; kind: string; a: string; b?: string | null; coef: number; lo: number; hi: number; excludes_zero: boolean }
export interface ValidationBlock { null: number; additive: number; with_interactions: number; gradient_boosting: number }
export interface Headline { stressor: string; label: string; step: number; unit: string; direction: 'up' | 'down'; effect: number; lo: number; hi: number; season: string | null }
export interface InteractionCheck {
  pairs_tested: number; pairs_excluding_zero: number; expected_by_chance: number; largest_plausible_pct_per_sd2: number; median_interval_halfwidth: number;
  strongest: { term: string; coef: number; lo: number; hi: number };
}
export interface ScenarioModel {
  stressors: string[]; labels: Record<string, string>; units: Record<string, string>; terms: ScenarioTerm[]; intercept: number; mean: number[]; scale: number[];
  coef: number[]; boot: number[][]; penalty: { main: number; product: number }; support: { precision: number[][]; chi2_99: number }; residual_sd: number;
  season: { mean: number; sd: number; summer: number; winter: number };
  locations: Record<string, ScenarioLocation>; learned_terms: LearnedTerm[]; headline: Headline[]; interaction_check: InteractionCheck;
  validation: {
    leave_states_out: ValidationBlock; out_of_time: ValidationBlock; leave_states_out_by_fold: Record<string, number[]>;
    deciles: { predicted: number; observed: number; weeks: number }[]; calibration_slope: number; calibration_slope_ci: [number, number];
  };
  training: { rows: number; states: number; date_start: string; date_end: string; bootstrap_replicates: number };
  anomaly_sd_pooled: Record<string, number>;
  outcome: { id: string; label: string; unit: string };
  dataset: { id: string; sha256?: string; ledger_block?: number | null };
  registered?: { sha256: string; ledger_block: number | null };
}

export interface ScenarioResult {
  effect: number; lo: number; hi: number; additive: number; interaction: number; interactionLo: number; interactionHi: number;
  contributions: Record<string, number>; extraDeaths: number; expectedDeaths: number; anomalies: Record<string, number>; levels: Record<string, number>;
  support: { maha: number; unusual: boolean; maxAbs: number }; seasonCovered: boolean;
}

/** Number with sensible digits for a slider or axis label. */
export const fmtNum = (v: number) => (Math.abs(v) >= 100 ? v.toFixed(0) : Math.abs(v) >= 10 ? v.toFixed(1) : v.toFixed(2));

export type Levels = Partial<Record<string, number | null>>;

const NONNEG = new Set(['precip', 'wind', 'pm25', 'pm10', 'o3', 'no2', 'uv']);
export const SD_RANGE = 4;

// numpy.percentile (linear interpolation)
export function percentile(sorted: ArrayLike<number>, p: number): number {
  const idx = (p / 100) * (sorted.length - 1);
  const lo = Math.floor(idx), hi = Math.ceil(idx);
  return sorted[lo] + (sorted[hi] - sorted[lo]) * (idx - lo);
}

interface Boot { data: Float64Array; reps: number; k: number; product: Uint8Array }
const rawBoot = new WeakMap<ScenarioModel, Boot>();
/** Bootstrap coefficients on the raw-term scale in one flat array (fast to scan: this runs hundreds of times per slider move). */
function bootRaw(m: ScenarioModel): Boot {
  let r = rawBoot.get(m);
  if (!r) {
    const k = m.scale.length, reps = m.boot.length;
    const data = new Float64Array(reps * k);
    m.boot.forEach((row, b) => row.forEach((v, j) => { data[b * k + j] = v / m.scale[j]; }));
    r = { data, reps, k, product: Uint8Array.from(m.terms.map((tt) => (tt.kind === 'product' ? 1 : 0))) };
    rawBoot.set(m, r);
  }
  return r;
}

function drawsOf(m: ScenarioModel, d: ArrayLike<number>): { total: Float64Array; inter: Float64Array } {
  const { data, reps, k, product } = bootRaw(m);
  const total = new Float64Array(reps), inter = new Float64Array(reps);
  for (let b = 0, o = 0; b < reps; b++, o += k) {
    let tot = 0, it = 0;
    for (let j = 0; j < k; j++) { const c = data[o + j] * d[j]; tot += c; if (product[j]) it += c; }
    total[b] = tot; inter[b] = it;
  }
  total.sort(); inter.sort();
  return { total, inter };
}

/** How hot this time of year normally is in the state, standardised (the heat effect depends on it). */
export function seasonOf(m: ScenarioModel, state: string, woy: number): number {
  return (m.locations[state].clim.heat_index[woy] - m.season.mean) / m.season.sd;
}

export function termValues(m: ScenarioModel, z: number[], season: number): number[] {
  const idx: Record<string, number> = {};
  m.stressors.forEach((s, i) => { idx[s] = i; });
  return m.terms.map((t) => {
    const a = z[idx[t.a]];
    switch (t.kind) {
      case 'linear': return a;
      case 'square': return a * a;
      case 'season_linear': return a * season;
      case 'season_square': return a * a * season;
      default: return a * z[idx[t.b as string]];
    }
  });
}

export function weekOfYear(date: Date): number {
  const start = Date.UTC(date.getUTCFullYear(), 0, 0);
  const doy = Math.floor((date.getTime() - start) / 86400000);
  return Math.min(Math.floor((doy - 1) / 7), 51);
}

/** Normal level and usual deviation of a stressor in a state for a week of the year. */
export function normalOf(m: ScenarioModel, state: string, woy: number, s: string): { normal: number; sd: number } {
  const loc = m.locations[state];
  return { normal: loc.clim[s][woy], sd: loc.sd[s] };
}

/** Slider limits: the state's normal +/- four usual deviations, kept inside what is physically possible. */
export function rangeOf(m: ScenarioModel, state: string, woy: number, s: string): [number, number] {
  const { normal, sd } = normalOf(m, state, woy, s);
  let lo = normal - SD_RANGE * sd, hi = normal + SD_RANGE * sd;
  if (s === 'rh') { lo = Math.max(lo, 0); hi = Math.min(hi, 100); } else if (NONNEG.has(s)) lo = Math.max(lo, 0);
  return [lo, hi];
}

function design(m: ScenarioModel, state: string, woy: number, levels: Levels) {
  const z: number[] = [], lv: Record<string, number> = {}, an: Record<string, number> = {};
  m.stressors.forEach((s) => {
    const { normal, sd } = normalOf(m, state, woy, s);
    const v = levels[s];
    const level = v === undefined || v === null ? normal : v;
    const zi = (level - normal) / sd;
    z.push(zi); lv[s] = level; an[s] = zi;
  });
  return { z, lv, an, d: termValues(m, z, seasonOf(m, state, woy)) };
}

/** Effect of scenario A minus scenario B (same place and week), with the 90% interval of the difference. */
export function compare(m: ScenarioModel, state: string, woy: number, a: Levels, b: Levels): { effect: number; lo: number; hi: number } {
  const da = design(m, state, woy, a).d, db = design(m, state, woy, b).d;
  const diff = da.map((v, k) => v - db[k]);
  const { total } = drawsOf(m, diff);
  return { effect: diff.reduce((acc, v, k) => acc + v * m.coef[k], 0), lo: percentile(total, 5), hi: percentile(total, 95) };
}

export function evaluate(m: ScenarioModel, state: string, woy: number, levels: Levels): ScenarioResult {
  const loc = m.locations[state];
  const { z, lv, an, d } = design(m, state, woy, levels);
  let effect = 0, additive = 0, interaction = 0;
  const contributions: Record<string, number> = {};
  m.stressors.forEach((s) => { contributions[s] = 0; });
  m.terms.forEach((t, k) => {
    const c = d[k] * m.coef[k];
    effect += c;
    if (t.kind === 'product') { interaction += c; contributions[t.a] += 0.5 * c; contributions[t.b as string] += 0.5 * c; }
    else { additive += c; contributions[t.a] += c; }
  });
  const { total: draws, inter: interDraws } = drawsOf(m, d);
  let maha = 0;
  for (let i = 0; i < z.length; i++) for (let j = 0; j < z.length; j++) maha += z[i] * m.support.precision[i][j] * z[j];
  const expected = loc.expected_deaths[woy];
  return {
    effect, lo: percentile(draws, 5), hi: percentile(draws, 95), additive, interaction,
    interactionLo: percentile(interDraws, 5), interactionHi: percentile(interDraws, 95), contributions,
    extraDeaths: (effect / 100) * expected, expectedDeaths: expected, anomalies: an, levels: lv,
    support: { maha, unusual: maha > m.support.chi2_99, maxAbs: Math.max(...z.map(Math.abs)) }, seasonCovered: loc.support[woy] >= 6,
  };
}

/** Dose-response: vary one stressor across its range, everything else as in the scenario. */
export function sweep(m: ScenarioModel, state: string, woy: number, levels: Levels, s: string, n = 33): { x: number; effect: number; lo: number; hi: number }[] {
  const [a, b] = rangeOf(m, state, woy, s);
  return Array.from({ length: n }, (_, i) => {
    const x = a + ((b - a) * i) / (n - 1);
    const r = evaluate(m, state, woy, { ...levels, [s]: x });
    return { x, effect: r.effect, lo: r.lo, hi: r.hi };
  });
}

/** Two stressors varied together (the interaction surface). `sure` marks cells whose 90% interval excludes zero. */
export function surface(m: ScenarioModel, state: string, woy: number, levels: Levels, a: string, b: string, n = 17) {
  const [a0, a1] = rangeOf(m, state, woy, a), [b0, b1] = rangeOf(m, state, woy, b);
  const xs = Array.from({ length: n }, (_, i) => a0 + ((a1 - a0) * i) / (n - 1));
  const ys = Array.from({ length: n }, (_, i) => b0 + ((b1 - b0) * i) / (n - 1));
  const cells = ys.map((y) => xs.map((x) => {
    const r = evaluate(m, state, woy, { ...levels, [a]: x, [b]: y });
    return { effect: r.effect, sure: r.lo > 0 || r.hi < 0, interaction: r.interaction };
  }));
  return { xs, ys, cells };
}

const signed = (v: number, d = 2) => `${v < 0 ? '−' : '+'}${Math.abs(v).toFixed(d)}%`;

/** Plain-language verdict that never claims more than the interval supports. */
export function verdict(r: ScenarioResult): { tone: 'calm' | 'watch' | 'alert'; headline: string; detail: string } {
  const sig = r.lo > 0 || r.hi < 0;
  const mag = Math.abs(r.effect);
  const dir = r.effect >= 0 ? 'more' : 'fewer';
  if (!sig) return { tone: 'calm', headline: 'No clear effect on weekly deaths', detail: `The data cannot tell this week apart from a typical one (best estimate ${signed(r.effect)}, range ${signed(r.lo)} to ${signed(r.hi)}).` };
  const tone = r.effect > 0 && mag >= 1 ? 'alert' : r.effect > 0 ? 'watch' : 'calm';
  const people = Math.abs(r.extraDeaths);
  return { tone, headline: `About ${mag.toFixed(mag < 1 ? 2 : 1)}% ${dir} deaths than a typical week`,
    detail: `Roughly ${people < 10 ? people.toFixed(1) : Math.round(people)} ${dir} deaths per week here (range ${signed(r.lo)} to ${signed(r.hi)}). An average association in past weeks, not a forecast for any one person.` };
}
